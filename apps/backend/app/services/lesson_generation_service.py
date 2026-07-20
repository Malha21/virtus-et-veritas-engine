"""Servico de geracao individual, fiel e versionada das aulas (fase 19.5): gera o
roteiro completo de UMA CoveragePlanLesson por chamada, usando exclusivamente os
source_content_items vinculados a ela (LessonSourceItem.coverage_plan_lesson_id).
Segue o mesmo esqueleto arquitetural de coverage_plan_service.py: precondicoes ->
job sincrono -> execucao em background com SessionLocal() propria -> chamada de IA
validada/ancorada -> persistencia versionada (nunca sobrescreve versao anterior)."""

import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.coverage_plan import CoveragePlan
from app.models.coverage_plan_lesson import CoveragePlanLesson
from app.models.coverage_plan_module import CoveragePlanModule
from app.models.document_block import DocumentBlock
from app.models.document_page import DocumentPage
from app.models.generated_content import GeneratedContent
from app.models.lesson_generation import LessonGeneration
from app.models.lesson_source_item import LessonSourceItem
from app.models.processing_job import ProcessingJob
from app.models.project import Project
from app.models.source_content_item import SourceContentItem
from app.models.source_content_item_block import SourceContentItemBlock
from app.models.source_content_item_dependency import SourceContentItemDependency
from app.models.user import User
from app.prompts import COVERAGE_LESSON_SCRIPT_PROMPT_VERSION, build_coverage_lesson_script_prompt
from app.providers.ai import (
    AIProvider,
    AIProviderRequest,
    get_ai_provider,
    resolve_default_model,
    resolve_provider_key,
    resolve_provider_name,
)
from app.schemas.coverage_lesson_script_ai import AICoverageLessonScriptResponse
from app.schemas.coverage_plan import CoveragePlanLessonSourceItemResponse
from app.schemas.lesson_generation import (
    LessonGenerationDetail,
    LessonGenerationResponse,
    LessonGenerationValidationIssue,
    LessonGenerationValidationResponse,
)
from app.services.ai_orchestrator_service import get_active_ai_provider_record, parse_json_content, register_ai_request
from app.services.coverage_plan_config import (
    MAX_LESSON_MINUTES,
    MAX_LESSON_WORDS,
    WORDS_PER_MINUTE,
    count_words,
    words_to_minutes,
)
from app.services.coverage_plan_service import get_latest_plan, get_lesson_for_user
from app.services.coverage_plan_validator import EXCLUDED_ITEM_STATUSES, REVIEW_FLAG_STATUSES
from app.services.processing_service import add_processing_log, reap_if_stale
from app.services.project_service import get_project_by_id
from app.services.user_ai_credential_service import resolve_generation_api_key, resolve_generation_base_url

logger = logging.getLogger(__name__)

LESSON_GENERATION_JOB_TYPE = "lesson_generation"
COURSE_LESSON_GENERATION_JOB_TYPE = "course_lesson_generation"
ACTIVE_JOB_STATUSES = ("pending", "queued", "processing")
COVERAGE_LESSON_SCRIPT_CONTENT_TYPE = "coverage_lesson_script"

AI_TEMPERATURE = 0.3
AI_TIMEOUT_SECONDS = 180.0
AI_MAX_RETRIES = 2

# Padroes que nao podem vazar para a narracao final (fidelidade / anti-vazamento
# tecnico): codigos internos, referencias diretas ao "documento", etc.
FORBIDDEN_NARRATION_PATTERNS = [
    re.compile(r"\bSRC-\d+\b"),
    re.compile(r"\bP\d{4}-B\d{4}\b"),
    re.compile(r"(?i)\bo pdf\b"),
    re.compile(r"(?i)\bo documento enviado\b"),
    re.compile(r"(?i)\ba fonte diz\b"),
]
JSON_LEAK_RE = re.compile(r'[{\[]\s*"[a-zA-Z_]+"\s*:')
NUMBER_RE = re.compile(r"\b\d{2,4}(?:[.,]\d+)?%?\b")


class LessonGenerationError(Exception):
    pass


# --------------------------------------------------------------------------
# Precondicoes / acesso
# --------------------------------------------------------------------------

def load_plan_and_module(db: Session, lesson: CoveragePlanLesson) -> tuple[CoveragePlan, CoveragePlanModule]:
    plan = db.get(CoveragePlan, lesson.coverage_plan_id)
    module = db.get(CoveragePlanModule, lesson.module_id)
    if plan is None or module is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plano de cobertura ou módulo não encontrado para esta aula.",
        )
    return plan, module


def load_lesson_source_pairs(db: Session, lesson_id: UUID) -> list[tuple[LessonSourceItem, SourceContentItem]]:
    """Retorna (link, item) na ordem pedagogica (source_order_in_lesson); e a unica
    fonte de verdade usada para montar o prompt -- nenhum outro dado do inventario
    ou de outras aulas e enviado ao modelo."""
    links = list(
        db.execute(
            select(LessonSourceItem)
            .where(LessonSourceItem.coverage_plan_lesson_id == lesson_id)
            .order_by(LessonSourceItem.source_order_in_lesson.asc())
        )
        .scalars()
        .all()
    )
    if not links:
        return []
    item_ids = [link.source_item_id for link in links]
    items_by_id = {
        item.id: item
        for item in db.execute(select(SourceContentItem).where(SourceContentItem.id.in_(item_ids))).scalars().all()
    }
    return [(link, items_by_id[link.source_item_id]) for link in links if link.source_item_id in items_by_id]


def check_lesson_generation_preconditions(
    db: Session,
    lesson: CoveragePlanLesson,
    plan: CoveragePlan,
    pairs: list[tuple[LessonSourceItem, SourceContentItem]],
) -> tuple[bool, list[str]]:
    """Levanta HTTPException 400 para toda violacao bloqueante. Retorna
    (requires_review, warnings) para violacoes que apenas sinalizam, nunca bloqueiam."""
    if not pairs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Esta aula não possui nenhum item de fonte associado; associe itens no Plano de Cobertura antes de gerar.",
        )

    if plan.status in {"pending", "processing", "invalid", "stale", "failed"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"O plano de cobertura está em status '{plan.status}' e não permite geração de aulas; "
                "gere/aprove ou regenere o plano antes de gerar aulas."
            ),
        )

    rejected_codes = [item.item_code for _, item in pairs if item.status in EXCLUDED_ITEM_STATUSES]
    if rejected_codes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"A aula referencia item(ns) rejeitado(s) no inventário ({', '.join(rejected_codes)}); "
                "recalcule o Plano de Cobertura antes de gerar."
            ),
        )

    if lesson.estimated_duration_minutes > Decimal(MAX_LESSON_MINUTES):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"A estimativa desta aula ({lesson.estimated_duration_minutes} min) já excede o limite de "
                f"{MAX_LESSON_MINUTES} minutos; divida a aula no Plano de Cobertura antes de gerar o roteiro."
            ),
        )

    page_numbers: set[int] = set()
    for _, item in pairs:
        if item.page_start and item.page_end:
            page_numbers.update(range(item.page_start, item.page_end + 1))
        elif item.page_start:
            page_numbers.add(item.page_start)

    if page_numbers:
        pages = list(
            db.execute(
                select(DocumentPage).where(
                    DocumentPage.project_file_id == plan.project_file_id,
                    DocumentPage.page_number.in_(page_numbers),
                )
            )
            .scalars()
            .all()
        )
        ocr_pending = sorted(p.page_number for p in pages if p.requires_ocr)
        failed_pages = sorted(p.page_number for p in pages if p.extraction_status == "failed")
        if ocr_pending:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Existem página(s) com OCR obrigatório pendente entre as fontes desta aula "
                    f"({', '.join(map(str, ocr_pending))}); resolva o OCR antes de gerar."
                ),
            )
        if failed_pages:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Existem página(s)-fonte com falha de extração não resolvida entre as fontes desta aula "
                    f"({', '.join(map(str, failed_pages))}); reprocesse a extração antes de gerar."
                ),
            )

    warnings: list[str] = []
    requires_review = plan.status == "requires_review" or lesson.requires_review

    review_codes = [item.item_code for _, item in pairs if item.status in REVIEW_FLAG_STATUSES]
    if review_codes:
        requires_review = True
        warnings.append(
            f"item(ns) pendente(s) de revisão no inventário usados nesta geração: {', '.join(review_codes)}."
        )

    return requires_review, warnings


def compute_lesson_source_fingerprint(
    lesson: CoveragePlanLesson, plan: CoveragePlan, pairs: list[tuple[LessonSourceItem, SourceContentItem]]
) -> str:
    """Fingerprint deterministico da aula: muda sempre que o plano e' regenerado
    (plan.version), a aula e editada (title/objective) ou qualquer item vinculado
    muda (conteudo, obrigatoriedade, ordem, tipo de cobertura) ou e adicionado/
    removido. Usado para detectar gerações desatualizadas (is_stale) sem depender
    de updated_at."""
    parts = [f"lesson:{lesson.id}:{lesson.title}:{lesson.learning_objective or ''}", f"plan_version:{plan.version}"]
    for link, item in pairs:
        content_hash = hashlib.sha256((item.normalized_content or item.source_text or "").encode("utf-8")).hexdigest()
        parts.append(
            f"{item.item_code}:{link.coverage_type}:{link.is_required}:{link.source_order_in_lesson}:{content_hash}"
        )
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# Preparacao do contexto para o prompt (fonte da verdade exclusiva)
# --------------------------------------------------------------------------

def _prepare_items_for_prompt(
    db: Session, pairs: list[tuple[LessonSourceItem, SourceContentItem]]
) -> list[dict[str, Any]]:
    item_ids = [item.id for _, item in pairs]
    item_by_id = {item.id: item for _, item in pairs}

    blocks_by_item: dict[UUID, list[str]] = {}
    if item_ids:
        block_links = list(
            db.execute(select(SourceContentItemBlock).where(SourceContentItemBlock.source_item_id.in_(item_ids)))
            .scalars()
            .all()
        )
        block_ids = [link.block_id for link in block_links]
        blocks_by_id = {}
        if block_ids:
            blocks_by_id = {
                block.id: block
                for block in db.execute(select(DocumentBlock).where(DocumentBlock.id.in_(block_ids))).scalars().all()
            }
        for link in sorted(block_links, key=lambda link: link.source_order):
            block = blocks_by_id.get(link.block_id)
            if block is not None:
                blocks_by_item.setdefault(link.source_item_id, []).append(block.block_code)

    deps_by_item: dict[UUID, list[str]] = {}
    if item_ids:
        dependencies = list(
            db.execute(
                select(SourceContentItemDependency).where(SourceContentItemDependency.source_item_id.in_(item_ids))
            )
            .scalars()
            .all()
        )
        for dependency in dependencies:
            target = item_by_id.get(dependency.depends_on_source_item_id)
            if target is not None:
                deps_by_item.setdefault(dependency.source_item_id, []).append(target.item_code)

    prepared: list[dict[str, Any]] = []
    for link, item in pairs:
        prepared.append(
            {
                "source_item_id": item.item_code,
                "item_code": item.item_code,
                "title": item.title,
                "normalized_content": item.normalized_content or item.source_text,
                "source_text": item.source_text,
                "content_type": item.content_type,
                "importance": item.importance,
                "source_order_in_lesson": link.source_order_in_lesson,
                "coverage_type": link.coverage_type,
                "is_required": link.is_required,
                "page_start": item.page_start,
                "page_end": item.page_end,
                "block_codes": blocks_by_item.get(item.id, []),
                "depends_on_item_codes": deps_by_item.get(item.id, []),
                "requires_review": item.status in REVIEW_FLAG_STATUSES,
            }
        )
    return prepared


# --------------------------------------------------------------------------
# Jobs (parte sincrona)
# --------------------------------------------------------------------------

def get_active_lesson_generation_job(db: Session, lesson_id: UUID) -> ProcessingJob | None:
    job = db.execute(
        select(ProcessingJob)
        .where(
            ProcessingJob.coverage_plan_lesson_id == lesson_id,
            ProcessingJob.job_type == LESSON_GENERATION_JOB_TYPE,
            ProcessingJob.status.in_(ACTIVE_JOB_STATUSES),
        )
        .order_by(ProcessingJob.created_at.desc())
    ).scalars().first()
    return reap_if_stale(db, job)


def get_latest_lesson_generation_job(db: Session, lesson_id: UUID) -> ProcessingJob | None:
    return db.execute(
        select(ProcessingJob)
        .where(ProcessingJob.coverage_plan_lesson_id == lesson_id, ProcessingJob.job_type == LESSON_GENERATION_JOB_TYPE)
        .order_by(ProcessingJob.created_at.desc())
    ).scalars().first()


def get_active_course_lesson_generation_job(db: Session, project_id: UUID) -> ProcessingJob | None:
    job = db.execute(
        select(ProcessingJob)
        .where(
            ProcessingJob.project_id == project_id,
            ProcessingJob.job_type == COURSE_LESSON_GENERATION_JOB_TYPE,
            ProcessingJob.status.in_(ACTIVE_JOB_STATUSES),
        )
        .order_by(ProcessingJob.created_at.desc())
    ).scalars().first()
    return reap_if_stale(db, job)


def get_latest_course_lesson_generation_job(db: Session, project_id: UUID) -> ProcessingJob | None:
    return db.execute(
        select(ProcessingJob)
        .where(ProcessingJob.project_id == project_id, ProcessingJob.job_type == COURSE_LESSON_GENERATION_JOB_TYPE)
        .order_by(ProcessingJob.created_at.desc())
    ).scalars().first()


def _create_job(
    db: Session,
    current_user: User,
    lesson: CoveragePlanLesson,
    plan: CoveragePlan,
    *,
    mode: str,
    feedback: str | None = None,
    repair_generation_id: UUID | None = None,
    missing_item_codes: list[str] | None = None,
    validation_notes: str | None = None,
) -> ProcessingJob:
    job = ProcessingJob(
        project_id=plan.project_id,
        organization_id=current_user.organization_id,
        project_file_id=plan.project_file_id,
        coverage_plan_lesson_id=lesson.id,
        job_type=LESSON_GENERATION_JOB_TYPE,
        status="pending",
        attempts=0,
        max_attempts=3,
        progress=0,
        current_step="Aguardando geração da aula",
        message=f"Job de geração de aula criado (modo: {mode})",
        total_items=1,
        processed_items=0,
        failed_items=0,
        payload_json={
            "coverage_plan_lesson_id": str(lesson.id),
            "mode": mode,
            "feedback": feedback,
            "repair_generation_id": str(repair_generation_id) if repair_generation_id else None,
            "missing_item_codes": missing_item_codes or [],
            "validation_notes": validation_notes,
        },
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def start_lesson_generation(db: Session, current_user: User, lesson_id: UUID, *, force: bool = False) -> ProcessingJob:
    lesson = get_lesson_for_user(db, current_user, lesson_id)
    plan, _module = load_plan_and_module(db, lesson)
    pairs = load_lesson_source_pairs(db, lesson.id)
    check_lesson_generation_preconditions(db, lesson, plan, pairs)

    existing_job = get_active_lesson_generation_job(db, lesson.id)
    if existing_job is not None:
        return existing_job

    mode = "regenerate" if force else "generate_if_missing"
    return _create_job(db, current_user, lesson, plan, mode=mode)


def start_lesson_regeneration(
    db: Session, current_user: User, lesson_id: UUID, *, mode: str = "regenerate", feedback: str | None = None
) -> ProcessingJob:
    lesson = get_lesson_for_user(db, current_user, lesson_id)
    plan, _module = load_plan_and_module(db, lesson)
    pairs = load_lesson_source_pairs(db, lesson.id)
    check_lesson_generation_preconditions(db, lesson, plan, pairs)

    existing_job = get_active_lesson_generation_job(db, lesson.id)
    if existing_job is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Já existe um job de geração ativo para esta aula."
        )

    return _create_job(db, current_user, lesson, plan, mode=mode, feedback=feedback)


def start_repair_missing_items(
    db: Session,
    current_user: User,
    lesson: CoveragePlanLesson,
    plan: CoveragePlan,
    generation: LessonGeneration,
    *,
    missing_source_item_ids: list[UUID],
    validation_notes: str | None,
) -> ProcessingJob:
    pairs = load_lesson_source_pairs(db, lesson.id)
    check_lesson_generation_preconditions(db, lesson, plan, pairs)

    valid_ids_by_item_id = {item.id: item.item_code for _, item in pairs}
    invalid_ids = [str(i) for i in missing_source_item_ids if i not in valid_ids_by_item_id]
    if invalid_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"source_item_id(s) não pertencem a esta aula: {', '.join(invalid_ids)}.",
        )

    missing_item_codes = [valid_ids_by_item_id[i] for i in missing_source_item_ids]

    existing_job = get_active_lesson_generation_job(db, lesson.id)
    if existing_job is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Já existe um job de geração ativo para esta aula."
        )

    return _create_job(
        db,
        current_user,
        lesson,
        plan,
        mode="repair_missing_items",
        repair_generation_id=generation.id,
        missing_item_codes=missing_item_codes,
        validation_notes=validation_notes,
    )


def start_course_lesson_generation(
    db: Session, current_user: User, project_id: UUID, *, force: bool = False, only_pending: bool = True
) -> ProcessingJob:
    project = get_project_by_id(db, current_user, project_id)
    plan = get_latest_plan(db, project.id)
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Nenhum plano de cobertura gerado para este projeto."
        )
    if plan.status in {"pending", "processing", "invalid", "stale", "failed"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"O plano de cobertura está em status '{plan.status}' e não permite geração em lote das aulas.",
        )

    existing_job = get_active_course_lesson_generation_job(db, project.id)
    if existing_job is not None:
        return existing_job

    modules = list(
        db.execute(
            select(CoveragePlanModule)
            .where(CoveragePlanModule.coverage_plan_id == plan.id)
            .order_by(CoveragePlanModule.module_order.asc())
        )
        .scalars()
        .all()
    )
    all_lessons = list(
        db.execute(
            select(CoveragePlanLesson)
            .where(CoveragePlanLesson.coverage_plan_id == plan.id)
            .order_by(CoveragePlanLesson.lesson_order.asc())
        )
        .scalars()
        .all()
    )
    lessons_by_module: dict[UUID, list[CoveragePlanLesson]] = {}
    for lesson in all_lessons:
        lessons_by_module.setdefault(lesson.module_id, []).append(lesson)
    ordered_lessons = [lesson for module in modules for lesson in lessons_by_module.get(module.id, [])]

    job = ProcessingJob(
        project_id=project.id,
        organization_id=current_user.organization_id,
        project_file_id=plan.project_file_id,
        job_type=COURSE_LESSON_GENERATION_JOB_TYPE,
        status="pending",
        attempts=0,
        max_attempts=1,
        progress=0,
        current_step="Aguardando geração em lote das aulas",
        message="Job de geração em lote criado",
        total_items=len(ordered_lessons),
        processed_items=0,
        failed_items=0,
        payload_json={
            "coverage_plan_id": str(plan.id),
            "lesson_ids": [str(lesson.id) for lesson in ordered_lessons],
            "force": force,
            "only_pending": only_pending,
        },
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def retry_failed_course_lessons(db: Session, current_user: User, project_id: UUID) -> ProcessingJob:
    project = get_project_by_id(db, current_user, project_id)
    plan = get_latest_plan(db, project.id)
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Nenhum plano de cobertura gerado para este projeto."
        )

    last_job = get_latest_course_lesson_generation_job(db, project.id)
    if last_job is None or not last_job.result_json:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nenhuma geração em lote anterior encontrada para reprocessar falhas.",
        )
    failed_lesson_ids = [
        UUID(entry["lesson_id"])
        for entry in (last_job.result_json.get("lessons") or [])
        if entry.get("outcome") == "failed"
    ]
    if not failed_lesson_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não há aulas com falha na última geração em lote para reprocessar.",
        )

    existing_job = get_active_course_lesson_generation_job(db, project.id)
    if existing_job is not None:
        return existing_job

    job = ProcessingJob(
        project_id=project.id,
        organization_id=current_user.organization_id,
        project_file_id=plan.project_file_id,
        job_type=COURSE_LESSON_GENERATION_JOB_TYPE,
        status="pending",
        attempts=0,
        max_attempts=1,
        progress=0,
        current_step="Aguardando reprocessamento das aulas com falha",
        message="Job de retry criado",
        total_items=len(failed_lesson_ids),
        processed_items=0,
        failed_items=0,
        payload_json={
            "coverage_plan_id": str(plan.id),
            "lesson_ids": [str(i) for i in failed_lesson_ids],
            "force": True,
            "only_pending": False,
        },
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def cancel_course_lesson_generation(db: Session, current_user: User, project_id: UUID) -> ProcessingJob:
    project = get_project_by_id(db, current_user, project_id)
    job = get_active_course_lesson_generation_job(db, project.id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Nenhum job de geração em lote ativo para este projeto."
        )
    if job.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Só é possível cancelar um job que ainda não começou a processar (limitação da arquitetura "
                "atual, baseada em BackgroundTasks sem supervisor externo capaz de interromper um job em execução)."
            ),
        )
    job.status = "cancelled"
    job.finished_at = datetime.now(UTC)
    job.message = "Cancelado pelo usuário antes do início do processamento."
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


# --------------------------------------------------------------------------
# Execucao em background (uma aula)
# --------------------------------------------------------------------------

def run_lesson_generation(job_id: UUID, user_id: UUID) -> None:
    with SessionLocal() as db:
        job = db.get(ProcessingJob, job_id)
        user = db.get(User, user_id)
        if job is None or user is None:
            return
        try:
            generate_lesson(db, user, job)
        except Exception as exc:  # noqa: BLE001 - rede de seguranca do background task
            db.rollback()
            job = db.get(ProcessingJob, job_id)
            if job is not None:
                job.status = "failed"
                job.error_message = str(exc)[:2000]
                job.message = "Falha na geração da aula"
                job.finished_at = datetime.now(UTC)
                db.add(job)
                db.commit()
                logger.error("Falha na geração de aula (job %s): %s", job_id, exc)


def _next_version(db: Session, lesson_id: UUID) -> int:
    current = db.execute(
        select(func.max(LessonGeneration.version)).where(LessonGeneration.coverage_plan_lesson_id == lesson_id)
    ).scalar_one()
    return (current or 0) + 1


def _mark_stale_if_fingerprint_changed(db: Session, lesson_id: UUID, fingerprint: str) -> None:
    generations = list(
        db.execute(
            select(LessonGeneration).where(
                LessonGeneration.coverage_plan_lesson_id == lesson_id, LessonGeneration.is_stale.is_(False)
            )
        )
        .scalars()
        .all()
    )
    changed = False
    for generation in generations:
        if generation.source_fingerprint and generation.source_fingerprint != fingerprint:
            generation.is_stale = True
            db.add(generation)
            changed = True
    if changed:
        db.commit()


def generate_lesson(db: Session, current_user: User, job: ProcessingJob) -> None:
    lesson = db.get(CoveragePlanLesson, job.coverage_plan_lesson_id)
    if lesson is None:
        raise LessonGenerationError("Aula do plano de cobertura não encontrada para gerar.")
    plan, module = load_plan_and_module(db, lesson)
    project = get_project_by_id(db, current_user, plan.project_id)
    settings = get_settings()

    payload = job.payload_json or {}
    mode = payload.get("mode", "generate_if_missing")
    feedback = payload.get("feedback")
    repair_generation_id = payload.get("repair_generation_id")
    missing_item_codes = payload.get("missing_item_codes") or []
    validation_notes = payload.get("validation_notes")

    job.status = "processing"
    job.started_at = job.started_at or datetime.now(UTC)
    job.attempts = (job.attempts or 0) + 1
    db.add(job)
    db.commit()

    add_processing_log(
        db,
        project_id=project.id,
        organization_id=current_user.organization_id,
        job_id=job.id,
        message="Geração da aula iniciada",
        context_json={"coverage_plan_lesson_id": str(lesson.id), "mode": mode},
    )

    pairs = load_lesson_source_pairs(db, lesson.id)
    requires_review_flag, precondition_warnings = check_lesson_generation_preconditions(db, lesson, plan, pairs)
    fingerprint = compute_lesson_source_fingerprint(lesson, plan, pairs)

    if mode == "generate_if_missing":
        latest = get_latest_generation(db, lesson.id)
        if (
            latest is not None
            and latest.source_fingerprint == fingerprint
            and latest.generation_status in {"completed", "approved"}
            and not latest.is_stale
        ):
            _finalize_job(
                db,
                job,
                generation=latest,
                warnings=["geração já existente e atualizada em relação às fontes foi reaproveitada (generate_if_missing)."],
            )
            return

    _mark_stale_if_fingerprint_changed(db, lesson.id, fingerprint)

    next_version = _next_version(db, lesson.id)
    prepared_items = _prepare_items_for_prompt(db, pairs)

    provider_key = resolve_provider_key(settings, project.ai_provider)
    user_api_key = resolve_generation_api_key(db, current_user, provider_key)
    user_base_url = resolve_generation_base_url(db, current_user, provider_key)
    ai_provider = get_ai_provider(settings, provider_key, api_key_override=user_api_key, base_url_override=user_base_url)
    provider_record = get_active_ai_provider_record(db, provider_key, resolve_provider_name(settings, provider_key))

    ai_response, warnings, usage = call_model(
        ai_provider,
        settings,
        db,
        project,
        module,
        lesson,
        job,
        provider_record.id,
        prepared_items,
        feedback=feedback if mode == "regenerate_with_feedback" else None,
        repair_notes=validation_notes if mode == "repair_missing_items" else None,
        missing_item_codes=missing_item_codes if mode == "repair_missing_items" else None,
    )
    all_warnings = precondition_warnings + warnings

    if ai_response is None:
        generation = _persist_failed_generation(
            db, current_user, project, lesson, plan, next_version, fingerprint, all_warnings,
            error="Falha na chamada de IA ou resposta inválida.",
        )
        job.failed_items = 1
        _finalize_job(db, job, generation=generation, warnings=all_warnings, failed=True)
        return

    validation = validate_structured_response(ai_response, pairs)
    all_warnings.extend(validation.warnings)

    generation = persist_generation(
        db,
        current_user,
        project,
        lesson,
        plan,
        next_version,
        fingerprint,
        ai_response,
        validation,
        usage,
        settings,
        pairs,
        prepared_items,
        requires_review=requires_review_flag,
        feedback_notes=feedback,
    )

    job.processed_items = 1
    job.progress = 100
    db.add(job)
    db.commit()

    _finalize_job(db, job, generation=generation, warnings=all_warnings)


def _finalize_job(
    db: Session, job: ProcessingJob, *, generation: LessonGeneration, warnings: list[str], failed: bool = False
) -> None:
    job = db.get(ProcessingJob, job.id) or job
    job.status = "failed" if failed else "completed"
    job.current_step = "Falha na geração da aula" if failed else "Geração da aula concluída"
    job.current_item = None
    job.message = f"Aula versão {generation.version} — status {generation.generation_status}."
    job.finished_at = datetime.now(UTC)
    job.result_json = {
        "lesson_generation_id": str(generation.id),
        "version": generation.version,
        "generation_status": generation.generation_status,
        "validation_status": generation.validation_status,
        "word_count": generation.word_count,
        "requires_split": generation.requires_split,
        "warnings": warnings[:200],
    }
    db.add(job)
    db.commit()


# --------------------------------------------------------------------------
# Chamada de IA (uma aula por chamada)
# --------------------------------------------------------------------------

def call_model(
    ai_provider: AIProvider,
    settings,
    db: Session,
    project: Project,
    module: CoveragePlanModule,
    lesson: CoveragePlanLesson,
    job: ProcessingJob,
    provider_record_id: UUID,
    prepared_items: list[dict[str, Any]],
    *,
    feedback: str | None = None,
    repair_notes: str | None = None,
    missing_item_codes: list[str] | None = None,
) -> tuple[AICoverageLessonScriptResponse | None, list[str], dict[str, Any]]:
    warnings: list[str] = []
    target_duration = float(lesson.target_duration_minutes or lesson.estimated_duration_minutes or MAX_LESSON_MINUTES)
    provider_key = resolve_provider_key(settings, project.ai_provider)
    default_model = resolve_default_model(settings, provider_key)

    system_prompt, user_prompt = build_coverage_lesson_script_prompt(
        project_title=project.title,
        module_title=module.title,
        module_objective=module.learning_objective or "",
        lesson_title=lesson.title,
        lesson_description=lesson.description or "",
        lesson_objective=lesson.learning_objective or "",
        target_duration_minutes=target_duration,
        max_lesson_minutes=MAX_LESSON_MINUTES,
        words_per_minute=WORDS_PER_MINUTE,
        items=prepared_items,
        generation_language="pt-BR",
        feedback=feedback,
        repair_notes=repair_notes,
        missing_item_codes=missing_item_codes,
    )

    response = ai_provider.generate_text(
        AIProviderRequest(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=default_model,
            temperature=AI_TEMPERATURE,
            timeout=AI_TIMEOUT_SECONDS,
            max_retries=AI_MAX_RETRIES,
        )
    )
    register_ai_request(
        db,
        project_id=project.id,
        job_id=job.id,
        provider_id=provider_record_id,
        request_type="coverage_lesson_script",
        prompt_version=COVERAGE_LESSON_SCRIPT_PROMPT_VERSION,
        response=response,
        model_name=default_model,
    )

    usage = {
        "input_tokens": (response.usage or {}).get("input_tokens"),
        "output_tokens": (response.usage or {}).get("output_tokens"),
        "provider_name": resolve_provider_name(settings, provider_key),
        "temperature": AI_TEMPERATURE,
    }

    if not response.success:
        warnings.append(f"falha na chamada de IA: {response.error}")
        return None, warnings, usage

    try:
        raw_payload = parse_json_content(response.content)
        ai_response = AICoverageLessonScriptResponse(**raw_payload)
    except (ValueError, ValidationError) as exc:
        warnings.append(f"resposta de IA inválida: {exc}")
        return None, warnings, usage

    return ai_response, warnings, usage


# --------------------------------------------------------------------------
# Validacao estrutural / cobertura / ancoragem (nunca confia cegamente na IA)
# --------------------------------------------------------------------------

@dataclass
class LessonValidationResult:
    status: str  # valid | invalid | requires_review | requires_split
    covered_item_codes: set[str] = field(default_factory=set)
    missing_required_item_codes: list[str] = field(default_factory=list)
    extra_item_codes: list[str] = field(default_factory=list)
    requires_split: bool = False
    split_reason: str | None = None
    issues: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _check_forbidden_narration(script_text: str) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for pattern in FORBIDDEN_NARRATION_PATTERNS:
        if pattern.search(script_text):
            issues.append(
                {
                    "issue_type": "technical_leak",
                    "severity": "error",
                    "message": "A narração contém uma referência técnica interna não permitida (ex: código SRC/bloco, ou menção direta ao documento/PDF).",
                }
            )
            break
    if "```" in script_text or JSON_LEAK_RE.search(script_text):
        issues.append(
            {
                "issue_type": "json_in_script",
                "severity": "error",
                "message": "O roteiro parece conter JSON ou marcação técnica em vez de texto narrado.",
            }
        )
    return issues


def _check_anchoring(script_text: str, pairs: list[tuple[LessonSourceItem, SourceContentItem]]) -> list[dict[str, Any]]:
    """Validacao preliminar (nao semantica): todo numero de 2+ digitos citado no
    roteiro deve ter correspondencia aparente nas fontes da aula. Nao bloqueia a
    geracao (apenas marca requires_review) para evitar falsos positivos -- a
    auditoria semantica completa e escopo da fase 19.6."""
    source_blob = " ".join(f"{item.normalized_content or ''} {item.source_text or ''}" for _, item in pairs)
    source_numbers = set(NUMBER_RE.findall(source_blob))
    script_numbers = set(NUMBER_RE.findall(script_text))
    unsupported = sorted(script_numbers - source_numbers)
    if not unsupported:
        return []
    return [
        {
            "issue_type": "unanchored_number",
            "severity": "warning",
            "message": (
                f"Número(s) no roteiro sem correspondência aparente nas fontes desta aula: "
                f"{', '.join(unsupported[:20])}. Revise manualmente antes de aprovar."
            ),
        }
    ]


def validate_structured_response(
    ai_response: AICoverageLessonScriptResponse, pairs: list[tuple[LessonSourceItem, SourceContentItem]]
) -> LessonValidationResult:
    valid_codes = {item.item_code for _, item in pairs}
    required_codes = {item.item_code for link, item in pairs if link.is_required}

    covered_codes_declared = {c.source_item_id for c in ai_response.covered_source_items}
    covered_valid = covered_codes_declared & valid_codes
    extra_codes = sorted(covered_codes_declared - valid_codes)
    missing_required = sorted(required_codes - covered_valid)

    issues: list[dict[str, Any]] = []
    warnings = list(ai_response.warnings)

    if extra_codes:
        issues.append(
            {
                "issue_type": "extra_source_item",
                "severity": "error",
                "message": f"A IA declarou cobertura de item(ns) fora desta aula: {', '.join(extra_codes)}.",
            }
        )
    if missing_required:
        issues.append(
            {
                "issue_type": "missing_required_item",
                "severity": "error",
                "message": f"Item(ns) obrigatório(s) não cobertos no roteiro: {', '.join(missing_required)}.",
            }
        )
    if ai_response.unsupported_claims_declared:
        issues.append(
            {
                "issue_type": "unsupported_claims",
                "severity": "error",
                "message": (
                    "A própria IA declarou afirmações sem suporte direto nas fontes: "
                    f"{'; '.join(ai_response.unsupported_claims_declared)}."
                ),
            }
        )

    script_text = ai_response.script or ""
    if not script_text.strip():
        issues.append({"issue_type": "empty_script", "severity": "error", "message": "Roteiro vazio."})

    technical_issues = _check_forbidden_narration(script_text)
    issues.extend(technical_issues)

    anchoring_issues = _check_anchoring(script_text, pairs)
    issues.extend(anchoring_issues)

    blocking = bool(
        extra_codes
        or missing_required
        or ai_response.unsupported_claims_declared
        or technical_issues
        or not script_text.strip()
    )

    if ai_response.requires_split:
        result_status = "requires_split"
    elif blocking:
        result_status = "invalid"
    elif anchoring_issues:
        result_status = "requires_review"
    else:
        result_status = "valid"

    return LessonValidationResult(
        status=result_status,
        covered_item_codes=covered_valid,
        missing_required_item_codes=missing_required,
        extra_item_codes=extra_codes,
        requires_split=ai_response.requires_split,
        split_reason=ai_response.split_reason,
        issues=issues,
        warnings=warnings,
    )


# --------------------------------------------------------------------------
# Persistencia versionada
# --------------------------------------------------------------------------

def get_latest_generation(db: Session, lesson_id: UUID) -> LessonGeneration | None:
    return db.execute(
        select(LessonGeneration)
        .where(LessonGeneration.coverage_plan_lesson_id == lesson_id)
        .order_by(LessonGeneration.version.desc())
    ).scalars().first()


def get_approved_generation(db: Session, lesson_id: UUID) -> LessonGeneration | None:
    return db.execute(
        select(LessonGeneration)
        .where(
            LessonGeneration.coverage_plan_lesson_id == lesson_id,
            LessonGeneration.generation_status == "approved",
        )
        .order_by(LessonGeneration.version.desc())
    ).scalars().first()


def get_generation_by_version(db: Session, lesson_id: UUID, version: int) -> LessonGeneration:
    generation = db.execute(
        select(LessonGeneration).where(
            LessonGeneration.coverage_plan_lesson_id == lesson_id, LessonGeneration.version == version
        )
    ).scalar_one_or_none()
    if generation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Versão de geração da aula não encontrada.")
    return generation


def list_generations(db: Session, lesson_id: UUID) -> list[LessonGeneration]:
    return list(
        db.execute(
            select(LessonGeneration)
            .where(LessonGeneration.coverage_plan_lesson_id == lesson_id)
            .order_by(LessonGeneration.version.desc())
        )
        .scalars()
        .all()
    )


def _get_or_create_generated_content(
    db: Session, current_user: User, project: Project, plan: CoveragePlan, lesson: CoveragePlanLesson, title: str
) -> GeneratedContent:
    if lesson.generated_content_id is not None:
        content = db.get(GeneratedContent, lesson.generated_content_id)
        if content is not None:
            return content
    content = GeneratedContent(
        project_id=plan.project_id,
        organization_id=project.organization_id,
        content_type=COVERAGE_LESSON_SCRIPT_CONTENT_TYPE,
        title=title,
        version=1,
        language="pt-BR",
        content_json={"coverage_plan_lesson_id": str(lesson.id)},
        status="generated",
        created_by_ai_provider_id=None,
    )
    db.add(content)
    db.flush()
    lesson.generated_content_id = content.id
    db.add(lesson)
    return content


def persist_generation(
    db: Session,
    current_user: User,
    project: Project,
    lesson: CoveragePlanLesson,
    plan: CoveragePlan,
    version: int,
    fingerprint: str,
    ai_response: AICoverageLessonScriptResponse,
    validation: LessonValidationResult,
    usage: dict[str, Any],
    settings,
    pairs: list[tuple[LessonSourceItem, SourceContentItem]],
    prepared_items: list[dict[str, Any]],
    *,
    requires_review: bool,
    feedback_notes: str | None = None,
) -> LessonGeneration:
    script_text = ai_response.script
    word_count = count_words(script_text)
    duration_minutes = words_to_minutes(word_count)
    duration_seconds = int((duration_minutes * 60).to_integral_value())

    exceeds_limit = duration_minutes > Decimal(MAX_LESSON_MINUTES) or word_count > MAX_LESSON_WORDS
    requires_split = bool(validation.requires_split or exceeds_limit)
    split_reason = validation.split_reason
    if exceeds_limit and not split_reason:
        split_reason = (
            f"Roteiro gerado com {word_count} palavras (~{duration_minutes} min), acima do limite de "
            f"{MAX_LESSON_WORDS} palavras ({MAX_LESSON_MINUTES} min). A aula precisa ser dividida no Plano de Cobertura."
        )

    if requires_split:
        generation_status = "requires_split"
        validation_status = "requires_split"
    elif validation.status == "invalid":
        generation_status = "requires_review"
        validation_status = "invalid"
    elif validation.status == "requires_review" or requires_review:
        generation_status = "requires_review"
        validation_status = "requires_review"
    else:
        generation_status = "completed"
        validation_status = "valid"

    content = _get_or_create_generated_content(
        db, current_user, project, plan, lesson, ai_response.lesson_title or lesson.title
    )
    content.title = ai_response.lesson_title or lesson.title
    content.content_text = script_text
    content.content_json = {
        "coverage_plan_lesson_id": str(lesson.id),
        "opening": ai_response.opening,
        "development": ai_response.development,
        "closing": ai_response.closing,
        "summary": ai_response.summary,
        "key_points": ai_response.key_points,
        "latest_version": version,
    }
    content.status = "generated"
    db.add(content)
    db.flush()

    item_by_code = {item.item_code: item for _, item in pairs}
    covered_payload = []
    for covered in ai_response.covered_source_items:
        item = item_by_code.get(covered.source_item_id)
        if item is None:
            continue
        covered_payload.append(
            {
                "source_item_id": str(item.id),
                "item_code": item.item_code,
                "coverage_description": covered.coverage_description,
                "coverage_type": covered.coverage_type,
            }
        )
    covered_codes = {entry["item_code"] for entry in covered_payload}
    uncovered_payload = [item.item_code for _, item in pairs if item.item_code not in covered_codes]

    source_pages = sorted(
        {
            page
            for prepared in prepared_items
            for page in (
                range(prepared["page_start"], prepared["page_end"] + 1)
                if prepared.get("page_start") and prepared.get("page_end")
                else ([prepared["page_start"]] if prepared.get("page_start") else [])
            )
        }
    )
    valid_block_codes = sorted({code for prepared in prepared_items for code in prepared.get("block_codes", [])})
    declared_blocks = sorted(set(ai_response.source_block_codes) & set(valid_block_codes))
    final_block_codes = declared_blocks or valid_block_codes

    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    total_tokens = (input_tokens or 0) + (output_tokens or 0) if (input_tokens or output_tokens) else None
    temperature = usage.get("temperature")

    generation = LessonGeneration(
        lesson_content_id=content.id,
        coverage_plan_lesson_id=lesson.id,
        version=version,
        generated_content=script_text,
        structured_content={
            "opening": ai_response.opening,
            "development": ai_response.development,
            "closing": ai_response.closing,
            "summary": ai_response.summary,
            "key_points": ai_response.key_points,
            "learning_objective": ai_response.learning_objective,
            "lesson_title": ai_response.lesson_title,
            "target_duration_minutes": ai_response.target_duration_minutes,
        },
        word_count=word_count,
        estimated_duration_seconds=duration_seconds,
        source_item_count=len(pairs),
        generation_status=generation_status,
        validation_status=validation_status,
        model_name=resolve_default_model(settings, resolve_provider_key(settings, project.ai_provider)),
        prompt_version=COVERAGE_LESSON_SCRIPT_PROMPT_VERSION,
        coverage_plan_version=plan.version,
        source_fingerprint=fingerprint,
        is_stale=False,
        requires_split=requires_split,
        split_reason=split_reason,
        covered_source_items_json=covered_payload,
        uncovered_source_items_json=uncovered_payload,
        source_pages_json=source_pages,
        source_block_codes_json=final_block_codes,
        unsupported_claims_json=ai_response.unsupported_claims_declared,
        warnings_json=validation.warnings[:100],
        feedback_notes=feedback_notes,
        is_manual_edit=False,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        provider_name=usage.get("provider_name"),
        temperature=Decimal(str(temperature)) if temperature is not None else None,
        created_by=current_user.id,
    )
    db.add(generation)

    if generation_status != "completed":
        lesson.status = "requires_review"
        db.add(lesson)

    db.commit()
    db.refresh(generation)
    return generation


def _persist_failed_generation(
    db: Session,
    current_user: User,
    project: Project,
    lesson: CoveragePlanLesson,
    plan: CoveragePlan,
    version: int,
    fingerprint: str,
    warnings: list[str],
    *,
    error: str,
) -> LessonGeneration:
    content = _get_or_create_generated_content(db, current_user, project, plan, lesson, lesson.title)
    db.flush()

    generation = LessonGeneration(
        lesson_content_id=content.id,
        coverage_plan_lesson_id=lesson.id,
        version=version,
        source_item_count=0,
        generation_status="failed",
        validation_status="invalid",
        prompt_version=COVERAGE_LESSON_SCRIPT_PROMPT_VERSION,
        coverage_plan_version=plan.version,
        source_fingerprint=fingerprint,
        error_message=error[:2000],
        warnings_json=warnings[:100],
        created_by=current_user.id,
    )
    db.add(generation)
    db.commit()
    db.refresh(generation)
    return generation


# --------------------------------------------------------------------------
# Edicao humana (nunca sobrescreve versao anterior)
# --------------------------------------------------------------------------

def edit_generation_manual(
    db: Session,
    current_user: User,
    lesson: CoveragePlanLesson,
    plan: CoveragePlan,
    generated_content_text: str,
    structured_content: dict[str, Any] | None = None,
) -> LessonGeneration:
    pairs = load_lesson_source_pairs(db, lesson.id)
    if not pairs:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Aula sem fontes associadas; não é possível editar.")
    if not generated_content_text.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="O conteúdo editado não pode ser vazio.")

    latest = get_latest_generation(db, lesson.id)
    if latest is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Gere a aula pelo menos uma vez antes de editar manualmente."
        )

    project = get_project_by_id(db, current_user, plan.project_id)
    fingerprint = compute_lesson_source_fingerprint(lesson, plan, pairs)

    word_count = count_words(generated_content_text)
    duration_minutes = words_to_minutes(word_count)
    duration_seconds = int((duration_minutes * 60).to_integral_value())
    requires_split = duration_minutes > Decimal(MAX_LESSON_MINUTES) or word_count > MAX_LESSON_WORDS

    version = _next_version(db, lesson.id)

    content = _get_or_create_generated_content(db, current_user, project, plan, lesson, lesson.title)
    content.content_text = generated_content_text
    if structured_content:
        content.content_json = {**(content.content_json or {}), **structured_content, "latest_version": version}
    db.add(content)

    generation = LessonGeneration(
        lesson_content_id=content.id,
        coverage_plan_lesson_id=lesson.id,
        version=version,
        generated_content=generated_content_text,
        structured_content=structured_content or latest.structured_content,
        word_count=word_count,
        estimated_duration_seconds=duration_seconds,
        source_item_count=len(pairs),
        generation_status="requires_split" if requires_split else "requires_review",
        validation_status="requires_split" if requires_split else "requires_review",
        model_name=latest.model_name,
        prompt_version=latest.prompt_version,
        coverage_plan_version=plan.version,
        source_fingerprint=fingerprint,
        requires_split=requires_split,
        split_reason=(
            f"Edição manual resultou em {word_count} palavras, acima do limite de {MAX_LESSON_WORDS}."
            if requires_split
            else None
        ),
        covered_source_items_json=latest.covered_source_items_json,
        uncovered_source_items_json=latest.uncovered_source_items_json,
        source_pages_json=latest.source_pages_json,
        source_block_codes_json=latest.source_block_codes_json,
        is_manual_edit=True,
        created_by=current_user.id,
    )
    db.add(generation)

    lesson.status = "requires_review"
    db.add(lesson)
    db.commit()
    db.refresh(generation)
    return generation


# --------------------------------------------------------------------------
# Validacao (sincrona, sem chamar IA) / aprovacao / rejeicao
# --------------------------------------------------------------------------

def validate_generation(
    db: Session, lesson: CoveragePlanLesson, plan: CoveragePlan, generation: LessonGeneration
) -> LessonGenerationValidationResponse:
    pairs = load_lesson_source_pairs(db, lesson.id)
    required_codes = {item.item_code for link, item in pairs if link.is_required}
    valid_codes = {item.item_code for _, item in pairs}
    covered_codes = {entry["item_code"] for entry in (generation.covered_source_items_json or [])}
    missing_required = sorted(required_codes - covered_codes)
    extra_codes = sorted(covered_codes - valid_codes)

    current_fingerprint = compute_lesson_source_fingerprint(lesson, plan, pairs)
    is_stale = generation.source_fingerprint != current_fingerprint

    script_text = generation.generated_content or ""
    issues: list[dict[str, Any]] = []
    issues.extend(_check_forbidden_narration(script_text))
    issues.extend(_check_anchoring(script_text, pairs))
    if missing_required:
        issues.append(
            {
                "issue_type": "missing_required_item",
                "severity": "error",
                "message": f"Item(ns) obrigatório(s) não cobertos: {', '.join(missing_required)}.",
            }
        )
    if extra_codes:
        issues.append(
            {
                "issue_type": "extra_source_item",
                "severity": "error",
                "message": f"Versão referencia item(ns) fora desta aula: {', '.join(extra_codes)}.",
            }
        )

    blocking = any(issue["severity"] == "error" for issue in issues)
    if generation.requires_split:
        result_status = "requires_split"
    elif blocking:
        result_status = "invalid"
    elif is_stale:
        result_status = "requires_review"
    else:
        result_status = "valid"

    generation.is_stale = is_stale
    generation.validation_status = result_status
    if result_status == "invalid" and generation.generation_status == "completed":
        generation.generation_status = "requires_review"
    db.add(generation)
    db.commit()
    db.refresh(generation)

    return LessonGenerationValidationResponse(
        status=result_status,
        covered_item_count=len(covered_codes & valid_codes),
        expected_item_count=len(required_codes),
        missing_required_item_codes=missing_required,
        extra_item_codes=extra_codes,
        requires_split=generation.requires_split,
        split_reason=generation.split_reason,
        issues=[LessonGenerationValidationIssue(**issue) for issue in issues],
        warnings=generation.warnings_json or [],
    )


def approve_generation(
    db: Session, current_user: User, lesson: CoveragePlanLesson, plan: CoveragePlan, generation: LessonGeneration
) -> LessonGeneration:
    pairs = load_lesson_source_pairs(db, lesson.id)
    check_lesson_generation_preconditions(db, lesson, plan, pairs)

    if generation.requires_split:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Esta versão excede o limite de duração (requires_split) e não pode ser aprovada; divida a aula no Plano de Cobertura.",
        )
    if generation.generation_status not in {"completed", "requires_review"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Esta versão está em status '{generation.generation_status}' e não pode ser aprovada.",
        )
    if generation.validation_status != "valid":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Esta versão ainda não está validada como 'valid'; corrija pendências e valide novamente antes de aprovar.",
        )

    current_fingerprint = compute_lesson_source_fingerprint(lesson, plan, pairs)
    if generation.is_stale or generation.source_fingerprint != current_fingerprint:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="As fontes desta aula mudaram desde esta geração (versão desatualizada); gere uma nova versão antes de aprovar.",
        )
    if generation.coverage_plan_version != plan.version:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O plano de cobertura foi regenerado desde esta geração; gere uma nova versão antes de aprovar.",
        )

    required_codes = {item.item_code for link, item in pairs if link.is_required}
    valid_codes = {item.item_code for _, item in pairs}
    covered_codes = {entry["item_code"] for entry in (generation.covered_source_items_json or [])}
    missing_required = sorted(required_codes - covered_codes)
    if missing_required:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Item(ns) obrigatório(s) ainda não cobertos: {', '.join(missing_required)}; não é possível aprovar.",
        )
    extra_codes = sorted(covered_codes - valid_codes)
    if extra_codes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Versão referencia item(ns) fora desta aula: {', '.join(extra_codes)}; não é possível aprovar.",
        )

    previously_approved = list(
        db.execute(
            select(LessonGeneration).where(
                LessonGeneration.coverage_plan_lesson_id == lesson.id,
                LessonGeneration.generation_status == "approved",
                LessonGeneration.id != generation.id,
            )
        )
        .scalars()
        .all()
    )
    for previous in previously_approved:
        previous.generation_status = "completed"
        db.add(previous)

    generation.generation_status = "approved"
    generation.validation_status = "approved"
    generation.approved_at = datetime.now(UTC)
    generation.approved_by = current_user.id
    db.add(generation)

    lesson.status = "approved"
    db.add(lesson)
    db.commit()
    db.refresh(generation)
    return generation


def reject_generation(db: Session, current_user: User, generation: LessonGeneration, reason: str) -> LessonGeneration:
    generation.generation_status = "rejected"
    generation.rejected_at = datetime.now(UTC)
    generation.rejected_by = current_user.id
    generation.rejection_reason = reason
    db.add(generation)
    db.commit()
    db.refresh(generation)
    return generation


# --------------------------------------------------------------------------
# Geracao em lote (uma chamada de IA por aula, nunca o curso inteiro de uma vez)
# --------------------------------------------------------------------------

def run_course_lesson_generation(job_id: UUID, user_id: UUID) -> None:
    with SessionLocal() as db:
        job = db.get(ProcessingJob, job_id)
        user = db.get(User, user_id)
        if job is None or user is None:
            return
        try:
            generate_all_lessons(db, user, job)
        except Exception as exc:  # noqa: BLE001 - rede de seguranca do background task
            db.rollback()
            job = db.get(ProcessingJob, job_id)
            if job is not None:
                job.status = "failed"
                job.error_message = str(exc)[:2000]
                job.message = "Falha na geração em lote das aulas"
                job.finished_at = datetime.now(UTC)
                db.add(job)
                db.commit()
                logger.error("Falha na geração em lote (job %s): %s", job_id, exc)


def generate_all_lessons(db: Session, current_user: User, job: ProcessingJob) -> None:
    payload = job.payload_json or {}
    lesson_ids = [UUID(i) for i in payload.get("lesson_ids", [])]
    force = bool(payload.get("force", False))
    only_pending = bool(payload.get("only_pending", True))

    job.status = "processing"
    job.started_at = job.started_at or datetime.now(UTC)
    db.add(job)
    db.commit()

    completed = 0
    failed = 0
    skipped = 0
    approved = 0
    stale = 0
    per_lesson_results: list[dict[str, Any]] = []
    total = len(lesson_ids) or 1

    for index, lesson_id in enumerate(lesson_ids, start=1):
        lesson = db.get(CoveragePlanLesson, lesson_id)
        if lesson is None:
            skipped += 1
            per_lesson_results.append({"lesson_id": str(lesson_id), "outcome": "skipped", "reason": "aula não encontrada"})
            continue

        job.current_item = lesson.title
        job.progress = max(0, min(100, round(index / total * 100)))
        db.add(job)
        db.commit()

        latest = get_latest_generation(db, lesson.id)
        if latest is not None and latest.generation_status == "approved" and not force:
            skipped += 1
            approved += 1
            per_lesson_results.append({"lesson_id": str(lesson.id), "outcome": "skipped_approved"})
            job.processed_items = index
            db.add(job)
            db.commit()
            continue

        try:
            plan, _module = load_plan_and_module(db, lesson)
            pairs = load_lesson_source_pairs(db, lesson.id)
            check_lesson_generation_preconditions(db, lesson, plan, pairs)
        except HTTPException as exc:
            skipped += 1
            per_lesson_results.append({"lesson_id": str(lesson.id), "outcome": "skipped", "reason": str(exc.detail)})
            job.processed_items = index
            db.add(job)
            db.commit()
            continue

        fingerprint = compute_lesson_source_fingerprint(lesson, plan, pairs)
        if (
            only_pending
            and not force
            and latest is not None
            and latest.source_fingerprint == fingerprint
            and latest.generation_status in {"completed", "approved"}
            and not latest.is_stale
        ):
            skipped += 1
            per_lesson_results.append({"lesson_id": str(lesson.id), "outcome": "skipped_up_to_date"})
            job.processed_items = index
            db.add(job)
            db.commit()
            continue

        lesson_job = _create_job(db, current_user, lesson, plan, mode="regenerate" if force else "generate_if_missing")
        outcome = "failed"
        try:
            generate_lesson(db, current_user, lesson_job)
            lesson_job = db.get(ProcessingJob, lesson_job.id)
            if lesson_job is not None and lesson_job.status == "completed":
                completed += 1
                outcome = "completed"
            else:
                failed += 1
                outcome = "failed"
        except Exception as exc:  # noqa: BLE001 - uma falha de aula nunca deve interromper as demais
            db.rollback()
            failed += 1
            outcome = "failed"
            logger.error("Falha ao gerar aula %s no lote (job %s): %s", lesson.id, job.id, exc)

        per_lesson_results.append({"lesson_id": str(lesson.id), "outcome": outcome})

        job = db.get(ProcessingJob, job.id)
        job.processed_items = index
        job.failed_items = failed
        db.add(job)
        db.commit()

    job = db.get(ProcessingJob, job.id)
    job.status = "completed" if failed == 0 else "completed_with_errors"
    job.progress = 100
    job.current_item = None
    job.failed_items = failed
    job.finished_at = datetime.now(UTC)
    job.message = f"{completed} aula(s) geradas, {failed} falha(s), {skipped} pulada(s)."
    job.result_json = {
        "total_lessons": len(lesson_ids),
        "completed_lessons": completed,
        "failed_lessons": failed,
        "skipped_lessons": skipped,
        "approved_lessons": approved,
        "stale_lessons": stale,
        "current_lesson": None,
        "progress_percentage": 100,
        "lessons": per_lesson_results[:500],
    }
    db.add(job)
    db.commit()


# --------------------------------------------------------------------------
# Leitura / montagem de resposta
# --------------------------------------------------------------------------

def build_generation_detail(
    db: Session, generation: LessonGeneration, lesson: CoveragePlanLesson, module: CoveragePlanModule
) -> LessonGenerationDetail:
    latest = get_latest_generation(db, lesson.id)
    approved = get_approved_generation(db, lesson.id)
    pairs = load_lesson_source_pairs(db, lesson.id)
    source_items = [
        CoveragePlanLessonSourceItemResponse(
            source_item_id=item.id,
            item_code=item.item_code,
            title=item.title,
            content_type=item.content_type,
            importance=item.importance,
            page_start=item.page_start,
            page_end=item.page_end,
            status=item.status,
            coverage_type=link.coverage_type,
            source_order_in_lesson=link.source_order_in_lesson,
            is_required=link.is_required,
            coverage_notes=link.coverage_notes,
        )
        for link, item in pairs
    ]
    base = LessonGenerationResponse.model_validate(generation)
    return LessonGenerationDetail(
        **base.model_dump(),
        lesson_id=lesson.id,
        lesson_title=lesson.title,
        module_id=module.id,
        module_title=module.title,
        target_duration_minutes=lesson.target_duration_minutes,
        is_approved_version=(approved is not None and approved.id == generation.id),
        is_latest_version=(latest is not None and latest.id == generation.id),
        source_items=source_items,
    )
