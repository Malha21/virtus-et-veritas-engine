"""Servico do plano de cobertura (fase 19.4): organiza o inventario aprovado
(fase 19.3) em modulos e aulas (<= 10 minutos cada), sem jamais cortar,
resumir ou deixar um item sem destino. Segue o mesmo esqueleto arquitetural de
source_inventory_service.py: precondicoes -> job sincrono -> execucao em
background com SessionLocal() propria -> chamada de IA validada/ancorada ->
persistencia idempotente com supersede (nunca DELETE de planos ja gerados)."""

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.coverage_plan import CoveragePlan
from app.models.coverage_plan_lesson import CoveragePlanLesson
from app.models.coverage_plan_module import CoveragePlanModule
from app.models.lesson_source_item import LessonSourceItem
from app.models.processing_job import ProcessingJob
from app.models.project import Project
from app.models.project_file import ProjectFile
from app.models.source_content_item import SourceContentItem
from app.models.source_content_item_dependency import SourceContentItemDependency
from app.models.user import User
from app.prompts import COVERAGE_PLAN_PROMPT_VERSION, build_coverage_plan_prompt
from app.providers.ai import (
    AIProvider,
    AIProviderRequest,
    get_ai_provider,
    resolve_default_model,
    resolve_provider_key,
    resolve_provider_name,
)
from app.schemas.coverage_plan import CoveragePlanSummary, UnmappedSourceItemResponse
from app.schemas.coverage_plan_ai import AICoveragePlanResponse
from app.services.ai_orchestrator_service import get_active_ai_provider_record, parse_json_content, register_ai_request
from app.services.coverage_plan_config import (
    LESSON_CLOSING_WORDS,
    LESSON_INTRO_WORDS,
    MAX_LESSON_MINUTES,
    MAX_LESSON_WORDS,
    TRANSITION_WORDS_PER_ITEM,
    content_type_multiplier,
    count_words,
    words_to_minutes,
)
from app.services.coverage_plan_validator import (
    EXCLUDED_ITEM_STATUSES,
    REVIEW_FLAG_STATUSES,
    validate_ai_plan_against_inventory,
    validate_persisted_coverage,
)
from app.services.document_extraction_service import get_project_file_for_extraction
from app.services.processing_service import add_processing_log
from app.services.project_service import get_project_by_id
from app.services.user_ai_credential_service import resolve_generation_api_key

logger = logging.getLogger(__name__)

COVERAGE_PLAN_JOB_TYPE = "coverage_plan"
ACTIVE_JOB_STATUSES = ("pending", "queued", "processing")
AI_TEMPERATURE = 0.2
AI_TIMEOUT_SECONDS = 120.0
AI_MAX_RETRIES = 2
BATCH_TARGET_CHARS = 12000

RELATIONSHIP_TO_COVERAGE_TYPE = {
    "primary": "planned_primary",
    "supporting": "planned_supporting",
    "reference": "planned_reference",
}


class CoveragePlanError(Exception):
    pass


# --------------------------------------------------------------------------
# Precondicoes / acesso
# --------------------------------------------------------------------------

def _eligible_items_query(project_file_id: UUID):
    return (
        select(SourceContentItem)
        .where(
            SourceContentItem.project_file_id == project_file_id,
            SourceContentItem.status.not_in(EXCLUDED_ITEM_STATUSES),
        )
        .order_by(SourceContentItem.source_order.asc())
    )


def load_inventory(db: Session, project_file_id: UUID) -> list[SourceContentItem]:
    return list(db.execute(_eligible_items_query(project_file_id)).scalars().all())


def check_coverage_plan_preconditions(items: list[SourceContentItem]) -> tuple[int, int]:
    """So bloqueia (400) quando nao ha nenhum item elegivel. Itens requires_review e
    paginas com OCR pendente nunca bloqueiam a geracao -- apenas geram alerta e marcam
    o plano como requires_review / impedem aprovacao final (checado em approve_plan)."""
    if not items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Execute e aprove o inventário do documento antes de gerar o plano de cobertura.",
        )
    requires_review_count = sum(1 for item in items if item.status in REVIEW_FLAG_STATUSES)
    return requires_review_count, len(items)


def get_active_coverage_plan_job(db: Session, project_file_id: UUID) -> ProcessingJob | None:
    return db.execute(
        select(ProcessingJob)
        .where(
            ProcessingJob.project_file_id == project_file_id,
            ProcessingJob.job_type == COVERAGE_PLAN_JOB_TYPE,
            ProcessingJob.status.in_(ACTIVE_JOB_STATUSES),
        )
        .order_by(ProcessingJob.created_at.desc())
    ).scalars().first()


def get_latest_coverage_plan_job(db: Session, project_file_id: UUID) -> ProcessingJob | None:
    return db.execute(
        select(ProcessingJob)
        .where(
            ProcessingJob.project_file_id == project_file_id,
            ProcessingJob.job_type == COVERAGE_PLAN_JOB_TYPE,
        )
        .order_by(ProcessingJob.created_at.desc())
    ).scalars().first()


def get_latest_plan(db: Session, project_id: UUID) -> CoveragePlan | None:
    return db.execute(
        select(CoveragePlan).where(CoveragePlan.project_id == project_id).order_by(CoveragePlan.version.desc())
    ).scalars().first()


def get_plan_by_version(db: Session, project_id: UUID, version: int) -> CoveragePlan:
    plan = db.execute(
        select(CoveragePlan).where(CoveragePlan.project_id == project_id, CoveragePlan.version == version)
    ).scalar_one_or_none()
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Versão do plano de cobertura não encontrada.")
    return plan


def list_plan_versions(db: Session, project_id: UUID) -> list[CoveragePlan]:
    return list(
        db.execute(
            select(CoveragePlan).where(CoveragePlan.project_id == project_id).order_by(CoveragePlan.version.desc())
        )
        .scalars()
        .all()
    )


def compute_inventory_fingerprint(items: list[SourceContentItem]) -> str:
    """Fingerprint deterministico do inventario elegivel (fase 19.4): muda sempre que
    um item e adicionado ou removido do conjunto elegivel, ou tem
    item_code/status/importance/source_order/normalized_content alterados. Usado
    para detectar quando um plano de cobertura existente ficou desatualizado em
    relacao ao estado atual do inventario (source_content_items), sem depender de
    updated_at (que pode mudar por motivos alheios ao conteudo relevante para o
    plano)."""
    parts = sorted(
        f"{item.id}:{item.item_code}:{item.status}:{item.importance}:{item.source_order}:"
        f"{hashlib.sha256((item.normalized_content or '').encode('utf-8')).hexdigest()}"
        for item in items
    )
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return digest


# --------------------------------------------------------------------------
# Criacao do job (parte sincrona)
# --------------------------------------------------------------------------

def start_coverage_plan_generation(
    db: Session,
    current_user: User,
    project_id: UUID,
    file_id: UUID,
    *,
    force: bool = False,
    continue_with_alerts: bool = False,
) -> ProcessingJob:
    project, project_file = get_project_file_for_extraction(db, current_user, project_id, file_id)
    items = load_inventory(db, project_file.id)
    check_coverage_plan_preconditions(items)

    existing_job = get_active_coverage_plan_job(db, project_file.id)
    if existing_job is not None and not force:
        return existing_job

    existing_plan = get_latest_plan(db, project.id)
    mode = "generate_if_missing" if existing_plan is None else ("regenerate_draft" if force else "generate_if_missing")

    return _create_job(db, current_user, project, project_file, mode=mode, continue_with_alerts=continue_with_alerts)


def start_coverage_plan_regenerate(
    db: Session,
    current_user: User,
    project_id: UUID,
    file_id: UUID,
    *,
    mode: str,
) -> ProcessingJob:
    project, project_file = get_project_file_for_extraction(db, current_user, project_id, file_id)
    items = load_inventory(db, project_file.id)
    check_coverage_plan_preconditions(items)

    existing_job = get_active_coverage_plan_job(db, project_file.id)
    if existing_job is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Já existe um job de plano de cobertura ativo para este documento.",
        )

    return _create_job(db, current_user, project, project_file, mode=mode, continue_with_alerts=True)


def _create_job(
    db: Session,
    current_user: User,
    project: Project,
    project_file: ProjectFile,
    *,
    mode: str,
    continue_with_alerts: bool = False,
) -> ProcessingJob:
    job = ProcessingJob(
        project_id=project.id,
        organization_id=current_user.organization_id,
        project_file_id=project_file.id,
        job_type=COVERAGE_PLAN_JOB_TYPE,
        status="pending",
        attempts=0,
        max_attempts=3,
        progress=0,
        current_step="Aguardando geração do plano de cobertura",
        message="Job de plano de cobertura criado",
        processed_items=0,
        failed_items=0,
        payload_json={
            "project_file_id": str(project_file.id),
            "mode": mode,
            "continue_with_alerts": continue_with_alerts,
        },
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def run_coverage_plan_generation(job_id: UUID, user_id: UUID) -> None:
    with SessionLocal() as db:
        job = db.get(ProcessingJob, job_id)
        user = db.get(User, user_id)
        if job is None or user is None:
            return
        try:
            generate_coverage_plan(db, user, job)
        except Exception as exc:  # noqa: BLE001 - rede de seguranca do background task
            db.rollback()
            job = db.get(ProcessingJob, job_id)
            if job is not None:
                job.status = "failed"
                job.error_message = str(exc)[:2000]
                job.message = "Falha na geração do plano de cobertura"
                job.finished_at = datetime.now(UTC)
                db.add(job)
                db.commit()
                logger.error("Falha no plano de cobertura (job %s): %s", job_id, exc)


# --------------------------------------------------------------------------
# Preparacao do inventario para o prompt
# --------------------------------------------------------------------------

def prepare_inventory_for_planning(db: Session, items: list[SourceContentItem]) -> list[dict[str, Any]]:
    item_by_id = {item.id: item for item in items}
    dependencies = list(
        db.execute(
            select(SourceContentItemDependency).where(
                SourceContentItemDependency.source_item_id.in_(list(item_by_id.keys()))
            )
        )
        .scalars()
        .all()
    ) if item_by_id else []

    deps_by_item: dict[UUID, list[str]] = {}
    for dep in dependencies:
        target = item_by_id.get(dep.depends_on_source_item_id)
        if target is None:
            continue
        deps_by_item.setdefault(dep.source_item_id, []).append(target.item_code)

    prepared = []
    for item in items:
        prepared.append(
            {
                "source_item_id": item.item_code,
                "item_code": item.item_code,
                "title": item.title,
                "normalized_content": item.normalized_content or item.source_text,
                "content_type": item.content_type,
                "importance": item.importance,
                "source_order": item.source_order,
                "page_start": item.page_start,
                "page_end": item.page_end,
                "depends_on_item_codes": deps_by_item.get(item.id, []),
            }
        )
    return prepared


def build_item_batches(
    items: list[dict[str, Any]], target_chars: int = BATCH_TARGET_CHARS
) -> list[list[dict[str, Any]]]:
    """Particiona os itens (ja ordenados por source_order) em lotes seguros para a IA.
    Cada item e uma unidade atomica (nunca fragmentado); o limite so decide onde um
    lote termina e o proximo comeca, preservando a ordem original entre lotes."""
    batches: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_chars = 0
    for item in items:
        item_chars = len(item["normalized_content"] or "") + len(item["title"] or "")
        if current and current_chars + item_chars > target_chars:
            batches.append(current)
            current = []
            current_chars = 0
        current.append(item)
        current_chars += item_chars
    if current:
        batches.append(current)
    return batches


# --------------------------------------------------------------------------
# Estimativa deterministica de palavras/duracao (nunca usada para cortar conteudo)
# --------------------------------------------------------------------------

@dataclass
class LessonEstimate:
    source_words: int
    explanation_words: int
    transition_words: int
    total_words: int
    duration_minutes: Decimal


def estimate_item_words(item: SourceContentItem) -> tuple[int, int]:
    text = item.normalized_content or item.source_text or ""
    source_words = count_words(text)
    explanation_words = round(source_words * content_type_multiplier(item.content_type))
    return source_words, explanation_words


def estimate_lesson_duration(items: list[SourceContentItem]) -> LessonEstimate:
    source_total = 0
    explanation_total = 0
    for item in items:
        source_words, explanation_words = estimate_item_words(item)
        source_total += source_words
        explanation_total += explanation_words
    transition_total = LESSON_INTRO_WORDS + LESSON_CLOSING_WORDS
    if len(items) > 1:
        transition_total += TRANSITION_WORDS_PER_ITEM * (len(items) - 1)
    total_words = source_total + explanation_total + transition_total
    return LessonEstimate(
        source_words=source_total,
        explanation_words=explanation_total,
        transition_words=transition_total,
        total_words=total_words,
        duration_minutes=words_to_minutes(total_words),
    )


# --------------------------------------------------------------------------
# Estruturas intermediarias (antes de persistir)
# --------------------------------------------------------------------------

@dataclass
class PendingLesson:
    title: str
    description: str
    learning_objective: str
    items: list[SourceContentItem]
    relationship_by_item_id: dict[UUID, str]
    required_by_item_id: dict[UUID, bool]
    order_by_item_id: dict[UUID, int]
    grouping_reason: str = ""
    dependencies: list[str] = field(default_factory=list)
    requires_review: bool = False
    warnings: list[str] = field(default_factory=list)
    estimate: LessonEstimate | None = None


@dataclass
class PendingModule:
    title: str
    description: str
    learning_objective: str
    lessons: list[PendingLesson] = field(default_factory=list)


def _partition_items_by_duration(items: list[SourceContentItem]) -> list[list[SourceContentItem]]:
    groups: list[list[SourceContentItem]] = []
    current: list[SourceContentItem] = []
    for item in items:
        candidate = current + [item]
        estimate = estimate_lesson_duration(candidate)
        if estimate.total_words > MAX_LESSON_WORDS and current:
            groups.append(current)
            current = [item]
        else:
            current = candidate
    if current:
        groups.append(current)
    return groups


def split_oversized_lessons(lessons: list[PendingLesson]) -> list[PendingLesson]:
    """Divide deterministicamente aulas que excedem o limite de duracao, preservando
    a ordem original e todos os itens -- nunca reduz conteudo para caber. Titulos
    "Parte N" so sao usados aqui porque a aula original ja foi agrupada pela IA como
    um unico assunto coerente; a divisao apenas fatia esse mesmo assunto em sequencia."""
    result: list[PendingLesson] = []
    for lesson in lessons:
        groups = _partition_items_by_duration(lesson.items)
        if len(groups) <= 1:
            lesson.estimate = estimate_lesson_duration(lesson.items)
            if lesson.estimate.duration_minutes > Decimal(MAX_LESSON_MINUTES):
                lesson.warnings.append(
                    "item unico excede a duracao maxima recomendada; mantido integralmente sem cortes."
                )
                lesson.requires_review = True
            result.append(lesson)
            continue

        for index, group in enumerate(groups, start=1):
            split_lesson = PendingLesson(
                title=f"{lesson.title} — Parte {index}",
                description=lesson.description,
                learning_objective=lesson.learning_objective,
                items=group,
                relationship_by_item_id=lesson.relationship_by_item_id,
                required_by_item_id=lesson.required_by_item_id,
                order_by_item_id=lesson.order_by_item_id,
                grouping_reason=(
                    f"{lesson.grouping_reason} Dividida automaticamente por exceder o limite de "
                    f"{MAX_LESSON_MINUTES} minutos; mantém a sequência original do conteúdo "
                    f"(parte {index} de {len(groups)})."
                ).strip(),
                dependencies=lesson.dependencies,
                requires_review=lesson.requires_review,
                warnings=list(lesson.warnings) + ["aula dividida automaticamente por limite de duração."],
            )
            split_lesson.estimate = estimate_lesson_duration(group)
            result.append(split_lesson)
    return result


def _fallback_module_for_unmapped(items: list[SourceContentItem]) -> PendingModule:
    """Rede de seguranca: se, apos a resposta da IA, algum item elegivel continuar sem
    aula, ele nunca fica sem destino -- vai para aulas de revisao automaticas."""
    lessons: list[PendingLesson] = []
    for index, group in enumerate(_partition_items_by_duration(items), start=1):
        lessons.append(
            PendingLesson(
                title=f"Itens pendentes de organização {index}",
                description="Itens do inventário não organizados automaticamente pela IA nesta rodada.",
                learning_objective="Garantir que nenhum item do inventário fique sem aula associada.",
                items=group,
                relationship_by_item_id={item.id: "primary" for item in group},
                required_by_item_id={item.id: True for item in group},
                order_by_item_id={item.id: i for i, item in enumerate(group, start=1)},
                grouping_reason="Criado automaticamente para cobrir itens não mapeados pela IA.",
                requires_review=True,
                warnings=["aula de segurança: revise o agrupamento manualmente."],
            )
        )
    return PendingModule(
        title="Itens Pendentes de Organização",
        description="Módulo de segurança criado automaticamente para garantir cobertura total do inventário.",
        learning_objective="Assegurar que nenhum item aprovado fique sem aula associada.",
        lessons=lessons,
    )


# --------------------------------------------------------------------------
# Chamada de IA por lote
# --------------------------------------------------------------------------

def propose_structure_for_batch(
    ai_provider: AIProvider,
    settings,
    db: Session,
    project: Project,
    job: ProcessingJob,
    provider_record_id: UUID,
    batch_id: str,
    batch_items: list[dict[str, Any]],
) -> tuple[AICoveragePlanResponse | None, list[str]]:
    warnings: list[str] = []
    default_model = resolve_default_model(settings, resolve_provider_key(settings, project.ai_provider))
    system_prompt, user_prompt = build_coverage_plan_prompt(
        project_title=project.title,
        batch_id=batch_id,
        items=batch_items,
        words_per_minute=130,
        max_lesson_minutes=MAX_LESSON_MINUTES,
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
        request_type="coverage_plan_batch",
        prompt_version=COVERAGE_PLAN_PROMPT_VERSION,
        response=response,
        model_name=default_model,
    )

    if not response.success:
        warnings.append(f"{batch_id}: falha na chamada de IA - {response.error}")
        return None, warnings

    try:
        raw_payload = parse_json_content(response.content)
        ai_response = AICoveragePlanResponse(**raw_payload)
    except (ValueError, ValidationError) as exc:
        warnings.append(f"{batch_id}: resposta de IA inválida - {exc}")
        return None, warnings

    return ai_response, warnings


# --------------------------------------------------------------------------
# Orquestracao principal
# --------------------------------------------------------------------------

def generate_coverage_plan(db: Session, current_user: User, job: ProcessingJob) -> None:
    project = get_project_by_id(db, current_user.organization_id, job.project_id)
    project_file = db.get(ProjectFile, job.project_file_id)
    if project_file is None:
        raise CoveragePlanError("Documento não encontrado para gerar o plano de cobertura.")

    settings = get_settings()
    payload = job.payload_json or {}
    mode = payload.get("mode", "generate_if_missing")

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
        message="Geração do plano de cobertura iniciada",
        context_json={"project_file_id": str(project_file.id), "mode": mode},
    )

    items = load_inventory(db, project_file.id)
    fingerprint = compute_inventory_fingerprint(items)
    existing_plan = get_latest_plan(db, project.id)

    if mode == "generate_if_missing" and existing_plan is not None and existing_plan.status not in {"failed", "invalid"}:
        if existing_plan.inventory_fingerprint == fingerprint:
            _finalize_job(
                db, job, plan=existing_plan, warnings=["plano já existente reaproveitado (generate_if_missing)."]
            )
            return

        # O inventario mudou desde a ultima geracao deste plano (fingerprint
        # diferente): nunca reaproveitar silenciosamente um plano desatualizado.
        # Preserva o plano existente (nao sobrescreve, nao apaga, nao gera nova
        # versao implicitamente) e apenas sinaliza que uma regeneracao explicita
        # (force=true ou /regenerate) e necessaria. Planos ja aprovados nunca sao
        # rebaixados automaticamente, mesmo com o inventario desatualizado --
        # mesmo criterio usado ao final desta funcao (linha ~734) para planos
        # substituidos por uma nova versao.
        if existing_plan.status not in {"approved", "stale"}:
            existing_plan.status = "stale"
            db.add(existing_plan)
            db.commit()
        _finalize_job(
            db,
            job,
            plan=existing_plan,
            warnings=[
                "O inventário foi alterado desde a última geração deste plano de cobertura "
                "(fingerprint do inventário diferente do fingerprint gravado no plano); o plano "
                "existente não foi reutilizado como se estivesse atualizado. Gere uma nova versão "
                "explicitamente (force=true ou /regenerate) para refletir o inventário atual."
            ],
        )
        return

    if mode == "validate_only":
        if existing_plan is None:
            raise CoveragePlanError("Nenhum plano de cobertura existente para validar.")
        result = validate_persisted_coverage(db, existing_plan)
        existing_plan.report_data = {**(existing_plan.report_data or {}), "last_validation": result.model_dump(mode="json")}
        existing_plan.status = "requires_review" if result.status != "valid" else existing_plan.status
        db.add(existing_plan)
        db.commit()
        _finalize_job(db, job, plan=existing_plan, warnings=[])
        return

    if mode == "recalculate_estimates" or mode == "preserve_manual_changes":
        if existing_plan is None:
            raise CoveragePlanError("Nenhum plano de cobertura existente para recalcular.")
        lessons = list(
            db.execute(select(CoveragePlanLesson).where(CoveragePlanLesson.coverage_plan_id == existing_plan.id))
            .scalars()
            .all()
        )
        for lesson in lessons:
            _recalculate_lesson_row(db, lesson)
        db.commit()
        _recompute_plan_aggregates(db, existing_plan)
        result = validate_persisted_coverage(db, existing_plan)
        existing_plan.status = "requires_review" if result.status != "valid" else "generated"
        existing_plan.report_data = {**(existing_plan.report_data or {}), "last_validation": result.model_dump(mode="json")}
        db.add(existing_plan)
        db.commit()
        _finalize_job(db, job, plan=existing_plan, warnings=[])
        return

    # generate_if_missing (primeira vez), regenerate_draft, rebuild_from_inventory: pipeline completo de IA
    check_coverage_plan_preconditions(items)
    next_version = (existing_plan.version + 1) if existing_plan else 1

    prepared_items = prepare_inventory_for_planning(db, items)
    item_by_code = {item.item_code: item for item in items}
    valid_codes = set(item_by_code.keys())
    batches = build_item_batches(prepared_items)

    job.total_items = len(batches)
    db.add(job)
    db.commit()

    provider_key = resolve_provider_key(settings, project.ai_provider)
    user_api_key = resolve_generation_api_key(db, current_user, provider_key)
    ai_provider = get_ai_provider(settings, provider_key, api_key_override=user_api_key)
    provider_record = get_active_ai_provider_record(db, provider_key, resolve_provider_name(settings, provider_key))

    pending_modules: list[PendingModule] = []
    all_mapped_codes: set[str] = set()
    all_warnings: list[str] = []

    for index, batch in enumerate(batches, start=1):
        batch_id = f"BATCH-{index:04d}"
        job.current_item = f"{batch_id} ({len(batch)} itens)"
        db.add(job)
        db.commit()

        ai_response, warnings = propose_structure_for_batch(
            ai_provider, settings, db, project, job, provider_record.id, batch_id, batch
        )
        all_warnings.extend(warnings)

        if ai_response is None:
            job.failed_items = (job.failed_items or 0) + 1
            db.add(job)
            db.commit()
            continue

        validation = validate_ai_plan_against_inventory(ai_response, valid_codes)
        all_warnings.extend(validation.warnings)
        all_mapped_codes |= validation.mapped_item_codes

        for module in ai_response.modules:
            pending_lessons: list[PendingLesson] = []
            for lesson in module.lessons:
                resolved_items = [item_by_code[ref.source_item_id] for ref in lesson.source_items if ref.source_item_id in item_by_code]
                if not resolved_items:
                    all_warnings.append(f"{batch_id}: aula '{lesson.title}' descartada por ficar sem itens válidos.")
                    continue
                pending_lessons.append(
                    PendingLesson(
                        title=lesson.title,
                        description=lesson.description,
                        learning_objective=lesson.learning_objective,
                        items=resolved_items,
                        relationship_by_item_id={
                            item_by_code[ref.source_item_id].id: ref.relationship_type
                            for ref in lesson.source_items
                            if ref.source_item_id in item_by_code
                        },
                        required_by_item_id={
                            item_by_code[ref.source_item_id].id: ref.is_required
                            for ref in lesson.source_items
                            if ref.source_item_id in item_by_code
                        },
                        order_by_item_id={
                            item_by_code[ref.source_item_id].id: ref.source_order_in_lesson
                            for ref in lesson.source_items
                            if ref.source_item_id in item_by_code
                        },
                        grouping_reason=lesson.grouping_reason,
                        dependencies=lesson.dependencies,
                        requires_review=lesson.requires_review,
                        warnings=list(lesson.warnings),
                    )
                )
            if pending_lessons:
                pending_modules.append(
                    PendingModule(
                        title=module.title,
                        description=module.description,
                        learning_objective=module.learning_objective,
                        lessons=pending_lessons,
                    )
                )

        job.processed_items = (job.processed_items or 0) + 1
        total = job.total_items or 1
        done = (job.processed_items or 0) + (job.failed_items or 0)
        job.progress = max(0, min(100, round(done / total * 100)))
        db.add(job)
        db.commit()

    # rede de seguranca: nenhum item elegivel pode ficar sem aula
    unmapped_codes = valid_codes - all_mapped_codes
    if unmapped_codes:
        unmapped_items = [item_by_code[code] for code in unmapped_codes]
        pending_modules.append(_fallback_module_for_unmapped(unmapped_items))
        all_warnings.append(f"{len(unmapped_items)} item(ns) cobertos por aula(s) de segurança automática.")

    # divisao de aulas excedentes (preserva 100% dos itens, apenas fatia a aula)
    for module in pending_modules:
        module.lessons = split_oversized_lessons(module.lessons)

    coverage_plan = CoveragePlan(
        project_id=project.id,
        project_file_id=project_file.id,
        version=next_version,
        status="processing",
        inventory_item_count=len(items),
        inventory_fingerprint=fingerprint,
        model_name=resolve_default_model(settings, provider_key),
        prompt_version=COVERAGE_PLAN_PROMPT_VERSION,
        settings_json={
            "words_per_minute": 130,
            "max_lesson_minutes": MAX_LESSON_MINUTES,
            "batch_count": len(batches),
            "mode": mode,
        },
    )
    db.add(coverage_plan)
    db.flush()

    persist_structure(db, coverage_plan, pending_modules)

    if existing_plan is not None and existing_plan.status not in {"approved"}:
        existing_plan.status = "stale"
        db.add(existing_plan)

    db.commit()

    _recompute_plan_aggregates(db, coverage_plan)
    result = validate_persisted_coverage(db, coverage_plan)
    coverage_plan.status = {"valid": "ready_for_review", "requires_review": "requires_review", "invalid": "invalid"}[
        result.status
    ]
    coverage_plan.report_data = {
        "validation": result.model_dump(mode="json"),
        "ai_warnings": all_warnings[:200],
    }
    db.add(coverage_plan)
    db.commit()

    _finalize_job(db, job, plan=coverage_plan, warnings=all_warnings)


def _finalize_job(db: Session, job: ProcessingJob, *, plan: CoveragePlan, warnings: list[str]) -> None:
    job = db.get(ProcessingJob, job.id) or job
    job.status = "completed" if not job.failed_items else "partially_completed"
    job.current_step = "Plano de cobertura gerado"
    job.current_item = None
    job.message = f"Plano versão {plan.version} com {plan.total_lessons} aula(s) em {plan.total_modules} módulo(s)."
    job.finished_at = datetime.now(UTC)
    job.result_json = {
        "coverage_plan_id": str(plan.id),
        "version": plan.version,
        "status": plan.status,
        "total_modules": plan.total_modules,
        "total_lessons": plan.total_lessons,
        "mapped_items": plan.mapped_items,
        "unmapped_items": plan.unmapped_items,
        "warnings": warnings[:200],
        "model_name": plan.model_name,
        "prompt_version": plan.prompt_version,
    }
    db.add(job)
    db.commit()


# --------------------------------------------------------------------------
# Persistencia
# --------------------------------------------------------------------------

def persist_structure(db: Session, coverage_plan: CoveragePlan, modules: list[PendingModule]) -> None:
    for module_index, module in enumerate(modules, start=1):
        module_row = CoveragePlanModule(
            coverage_plan_id=coverage_plan.id,
            project_id=coverage_plan.project_id,
            title=module.title,
            description=module.description,
            learning_objective=module.learning_objective,
            module_order=module_index,
            status="planned",
            plan_version=coverage_plan.version,
        )
        db.add(module_row)
        db.flush()

        module_minutes = Decimal("0")
        module_words = 0
        module_items = 0

        for lesson_index, lesson in enumerate(module.lessons, start=1):
            estimate = lesson.estimate or estimate_lesson_duration(lesson.items)
            lesson_row = CoveragePlanLesson(
                coverage_plan_id=coverage_plan.id,
                module_id=module_row.id,
                title=lesson.title,
                description=lesson.description,
                learning_objective=lesson.learning_objective,
                lesson_order=lesson_index,
                estimated_duration_minutes=estimate.duration_minutes,
                estimated_source_words=estimate.source_words,
                estimated_explanation_words=estimate.explanation_words,
                estimated_transition_words=estimate.transition_words,
                estimated_word_count=estimate.total_words,
                source_item_count=len(lesson.items),
                status="requires_review" if lesson.requires_review else "planned",
                plan_version=coverage_plan.version,
                requires_review=lesson.requires_review,
                grouping_reason=lesson.grouping_reason,
                warnings_json=lesson.warnings + ([f"depende de: {', '.join(lesson.dependencies)}"] if lesson.dependencies else []),
            )
            db.add(lesson_row)
            db.flush()

            for item in lesson.items:
                order = lesson.order_by_item_id.get(item.id, 0)
                relationship = lesson.relationship_by_item_id.get(item.id, "primary")
                is_required = lesson.required_by_item_id.get(item.id, True)
                db.add(
                    LessonSourceItem(
                        coverage_plan_lesson_id=lesson_row.id,
                        source_item_id=item.id,
                        coverage_type=RELATIONSHIP_TO_COVERAGE_TYPE.get(relationship, "planned_primary"),
                        source_order_in_lesson=order,
                        is_required=is_required,
                    )
                )

            module_minutes += estimate.duration_minutes
            module_words += estimate.total_words
            module_items += len(lesson.items)

        module_row.estimated_total_minutes = module_minutes
        module_row.estimated_total_words = module_words
        module_row.source_item_count = module_items
        db.add(module_row)

    db.flush()


def _recompute_plan_aggregates(db: Session, coverage_plan: CoveragePlan) -> None:
    modules = list(
        db.execute(select(CoveragePlanModule).where(CoveragePlanModule.coverage_plan_id == coverage_plan.id))
        .scalars()
        .all()
    )
    lessons = list(
        db.execute(select(CoveragePlanLesson).where(CoveragePlanLesson.coverage_plan_id == coverage_plan.id))
        .scalars()
        .all()
    )
    lesson_ids = [lesson.id for lesson in lessons]
    mapped_item_ids: set[UUID] = set()
    if lesson_ids:
        links = list(
            db.execute(select(LessonSourceItem).where(LessonSourceItem.coverage_plan_lesson_id.in_(lesson_ids)))
            .scalars()
            .all()
        )
        mapped_item_ids = {link.source_item_id for link in links}

    eligible_items = load_inventory(db, coverage_plan.project_file_id)
    eligible_ids = {item.id for item in eligible_items}

    coverage_plan.total_modules = len(modules)
    coverage_plan.total_lessons = len(lessons)
    coverage_plan.total_items = len(eligible_items)
    coverage_plan.mapped_items = len(mapped_item_ids & eligible_ids)
    coverage_plan.unmapped_items = len(eligible_ids - mapped_item_ids)
    coverage_plan.estimated_total_words = sum(lesson.estimated_word_count for lesson in lessons)
    coverage_plan.estimated_total_minutes = sum((lesson.estimated_duration_minutes for lesson in lessons), Decimal("0"))
    db.add(coverage_plan)
    db.commit()


# --------------------------------------------------------------------------
# Recalculo reutilizavel (fase 19.4: mover item, dividir, unir, reprocessar)
# --------------------------------------------------------------------------

def _recalculate_lesson_row(db: Session, lesson: CoveragePlanLesson) -> CoveragePlanLesson:
    links = list(
        db.execute(
            select(LessonSourceItem)
            .where(LessonSourceItem.coverage_plan_lesson_id == lesson.id)
            .order_by(LessonSourceItem.source_order_in_lesson.asc())
        )
        .scalars()
        .all()
    )
    item_ids = [link.source_item_id for link in links]
    items = []
    if item_ids:
        items = list(db.execute(select(SourceContentItem).where(SourceContentItem.id.in_(item_ids))).scalars().all())
    items_by_id = {item.id: item for item in items}
    ordered_items = [items_by_id[i] for i in item_ids if i in items_by_id]

    estimate = estimate_lesson_duration(ordered_items) if ordered_items else LessonEstimate(0, 0, 0, 0, Decimal("0"))
    lesson.estimated_duration_minutes = estimate.duration_minutes
    lesson.estimated_source_words = estimate.source_words
    lesson.estimated_explanation_words = estimate.explanation_words
    lesson.estimated_transition_words = estimate.transition_words
    lesson.estimated_word_count = estimate.total_words
    lesson.source_item_count = len(ordered_items)
    lesson.requires_review = estimate.duration_minutes > Decimal(MAX_LESSON_MINUTES) or not ordered_items
    lesson.updated_at = datetime.now(UTC)
    db.add(lesson)
    return lesson


def recalculate_lesson_estimates(db: Session, lesson_id: UUID) -> CoveragePlanLesson:
    lesson = db.get(CoveragePlanLesson, lesson_id)
    if lesson is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aula do plano de cobertura não encontrada.")
    _recalculate_lesson_row(db, lesson)
    db.commit()
    db.refresh(lesson)
    _touch_module(db, lesson.module_id)
    plan = db.get(CoveragePlan, lesson.coverage_plan_id)
    if plan is not None:
        _recompute_plan_aggregates(db, plan)
        if plan.status == "approved":
            plan.status = "requires_review"
            db.add(plan)
            db.commit()
    return lesson


def _touch_module(db: Session, module_id: UUID) -> None:
    module = db.get(CoveragePlanModule, module_id)
    if module is None:
        return
    lessons = list(
        db.execute(select(CoveragePlanLesson).where(CoveragePlanLesson.module_id == module.id)).scalars().all()
    )
    module.estimated_total_minutes = sum((lesson.estimated_duration_minutes for lesson in lessons), Decimal("0"))
    module.estimated_total_words = sum(lesson.estimated_word_count for lesson in lessons)
    module.source_item_count = sum(lesson.source_item_count for lesson in lessons)
    db.add(module)
    db.commit()


# --------------------------------------------------------------------------
# Edicao manual: mover item, dividir aula, unir aulas
# --------------------------------------------------------------------------

def add_source_item_to_lesson(
    db: Session,
    lesson_id: UUID,
    source_item_id: UUID,
    *,
    current_user: User,
    coverage_type: str = "planned_supporting",
    is_required: bool = True,
    source_order_in_lesson: int = 0,
    coverage_notes: str | None = None,
) -> CoveragePlanLesson:
    lesson = db.get(CoveragePlanLesson, lesson_id)
    if lesson is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aula do plano de cobertura não encontrada.")
    plan = db.get(CoveragePlan, lesson.coverage_plan_id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aula do plano de cobertura não encontrada.")

    item = db.get(SourceContentItem, source_item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item do inventário não encontrado.")

    # Nunca revela a existencia de um item de outra organizacao: mesmo tratamento
    # (404 generico) usado pelo restante do projeto para recursos fora do tenant.
    get_project_by_id(db, current_user.organization_id, item.project_id)

    if item.project_file_id != plan.project_file_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O item do inventário pertence a um documento diferente do plano de cobertura desta aula.",
        )

    existing = db.execute(
        select(LessonSourceItem).where(
            LessonSourceItem.coverage_plan_lesson_id == lesson.id,
            LessonSourceItem.source_item_id == item.id,
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(
            LessonSourceItem(
                coverage_plan_lesson_id=lesson.id,
                source_item_id=item.id,
                coverage_type=coverage_type,
                is_required=is_required,
                source_order_in_lesson=source_order_in_lesson,
                coverage_notes=coverage_notes,
            )
        )
        db.commit()
    return recalculate_lesson_estimates(db, lesson.id)


def remove_source_item_from_lesson(db: Session, lesson_id: UUID, source_item_id: UUID) -> CoveragePlanLesson:
    lesson = db.get(CoveragePlanLesson, lesson_id)
    if lesson is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aula do plano de cobertura não encontrada.")

    link = db.execute(
        select(LessonSourceItem).where(
            LessonSourceItem.coverage_plan_lesson_id == lesson.id,
            LessonSourceItem.source_item_id == source_item_id,
        )
    ).scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item não associado a esta aula.")

    current_count = db.execute(
        select(LessonSourceItem).where(LessonSourceItem.coverage_plan_lesson_id == lesson.id)
    ).scalars().all()
    if len(current_count) <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não é possível remover o único item de uma aula (aula sem fonte não é permitida).",
        )

    other_mappings = db.execute(
        select(LessonSourceItem).where(
            LessonSourceItem.source_item_id == source_item_id,
            LessonSourceItem.id != link.id,
        )
    ).scalars().all()
    if link.is_required and not other_mappings:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não é possível remover: este é o único destino do item obrigatório no plano.",
        )

    db.delete(link)
    db.commit()
    return recalculate_lesson_estimates(db, lesson.id)


def split_lesson_manual(
    db: Session,
    lesson_id: UUID,
    *,
    first_title: str,
    second_title: str,
    first_source_item_ids: list[UUID],
    second_source_item_ids: list[UUID],
    first_description: str | None = None,
    second_description: str | None = None,
    first_learning_objective: str | None = None,
    second_learning_objective: str | None = None,
) -> tuple[CoveragePlanLesson, CoveragePlanLesson]:
    lesson = db.get(CoveragePlanLesson, lesson_id)
    if lesson is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aula do plano de cobertura não encontrada.")

    links = list(
        db.execute(select(LessonSourceItem).where(LessonSourceItem.coverage_plan_lesson_id == lesson.id)).scalars().all()
    )
    current_ids = {link.source_item_id for link in links}
    requested_ids = set(first_source_item_ids) | set(second_source_item_ids)
    if requested_ids != current_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A divisão deve conter exatamente todos os itens já presentes na aula, sem perdas.",
        )

    links_by_item = {link.source_item_id: link for link in links}

    siblings = list(
        db.execute(
            select(CoveragePlanLesson)
            .where(CoveragePlanLesson.module_id == lesson.module_id)
            .order_by(CoveragePlanLesson.lesson_order.asc())
        )
        .scalars()
        .all()
    )
    for sibling in siblings:
        if sibling.lesson_order > lesson.lesson_order:
            sibling.lesson_order += 1
            db.add(sibling)

    second_lesson = CoveragePlanLesson(
        coverage_plan_id=lesson.coverage_plan_id,
        module_id=lesson.module_id,
        title=second_title,
        description=second_description if second_description is not None else lesson.description,
        learning_objective=second_learning_objective if second_learning_objective is not None else lesson.learning_objective,
        lesson_order=lesson.lesson_order + 1,
        status=lesson.status,
        plan_version=lesson.plan_version,
        grouping_reason="Aula dividida manualmente a partir de: " + lesson.title,
    )
    db.add(second_lesson)
    db.flush()

    for item_id in second_source_item_ids:
        link = links_by_item[item_id]
        link.coverage_plan_lesson_id = second_lesson.id
        db.add(link)

    lesson.title = first_title
    lesson.description = first_description if first_description is not None else lesson.description
    lesson.learning_objective = (
        first_learning_objective if first_learning_objective is not None else lesson.learning_objective
    )
    db.add(lesson)
    db.commit()

    recalculate_lesson_estimates(db, lesson.id)
    recalculate_lesson_estimates(db, second_lesson.id)
    db.refresh(lesson)
    db.refresh(second_lesson)
    return lesson, second_lesson


def merge_lessons_manual(
    db: Session,
    lesson_ids: list[UUID],
    *,
    title: str,
    description: str | None = None,
    learning_objective: str | None = None,
) -> CoveragePlanLesson:
    lessons = list(db.execute(select(CoveragePlanLesson).where(CoveragePlanLesson.id.in_(lesson_ids))).scalars().all())
    if len(lessons) != len(lesson_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Uma ou mais aulas não foram encontradas.")

    module_ids = {lesson.module_id for lesson in lessons}
    if len(module_ids) > 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Só é possível unir aulas do mesmo módulo nesta fase.",
        )

    lessons.sort(key=lambda lesson: lesson.lesson_order)
    survivor = lessons[0]
    others = lessons[1:]

    all_items: list[SourceContentItem] = []
    for lesson in lessons:
        links = list(
            db.execute(select(LessonSourceItem).where(LessonSourceItem.coverage_plan_lesson_id == lesson.id))
            .scalars()
            .all()
        )
        ids = [link.source_item_id for link in links]
        if ids:
            all_items.extend(db.execute(select(SourceContentItem).where(SourceContentItem.id.in_(ids))).scalars().all())

    combined_estimate = estimate_lesson_duration(all_items)
    if combined_estimate.duration_minutes > Decimal(MAX_LESSON_MINUTES):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"A união resultaria em {combined_estimate.duration_minutes} min, acima do limite de "
                f"{MAX_LESSON_MINUTES} min. Não é permitido unir aulas que ultrapassem o limite."
            ),
        )

    for other in others:
        links = list(
            db.execute(select(LessonSourceItem).where(LessonSourceItem.coverage_plan_lesson_id == other.id))
            .scalars()
            .all()
        )
        for link in links:
            duplicate = db.execute(
                select(LessonSourceItem).where(
                    LessonSourceItem.coverage_plan_lesson_id == survivor.id,
                    LessonSourceItem.source_item_id == link.source_item_id,
                )
            ).scalar_one_or_none()
            if duplicate is not None:
                db.delete(link)
            else:
                link.coverage_plan_lesson_id = survivor.id
                db.add(link)
        db.delete(other)

    survivor.title = title
    if description is not None:
        survivor.description = description
    if learning_objective is not None:
        survivor.learning_objective = learning_objective
    db.add(survivor)
    db.commit()

    result = recalculate_lesson_estimates(db, survivor.id)

    remaining = list(
        db.execute(
            select(CoveragePlanLesson)
            .where(CoveragePlanLesson.module_id == survivor.module_id)
            .order_by(CoveragePlanLesson.lesson_order.asc())
        )
        .scalars()
        .all()
    )
    for order, lesson in enumerate(remaining, start=1):
        lesson.lesson_order = order
        db.add(lesson)
    db.commit()

    return result


# --------------------------------------------------------------------------
# Aprovacao
# --------------------------------------------------------------------------

def approve_plan(db: Session, current_user: User, coverage_plan: CoveragePlan) -> CoveragePlan:
    result = validate_persisted_coverage(db, coverage_plan)
    if result.unmapped_items > 0 or result.lessons_over_limit > 0 or result.lessons_without_sources > 0 or result.modules_without_lessons > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O plano possui pendências bloqueantes (itens sem aula, aula sem fonte, módulo vazio ou aula acima do limite) e não pode ser aprovado.",
        )
    if result.pages_requires_ocr > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Existem páginas com OCR pendente; a aprovação final está bloqueada até que sejam resolvidas.",
        )
    if result.requires_review_source_items > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Existem itens do inventário pendentes de revisão; a aprovação final está bloqueada até que sejam resolvidos.",
        )

    coverage_plan.status = "approved"
    coverage_plan.approved_at = datetime.now(UTC)
    coverage_plan.approved_by = current_user.id
    coverage_plan.report_data = {**(coverage_plan.report_data or {}), "approval_validation": result.model_dump(mode="json")}
    db.add(coverage_plan)
    db.commit()
    db.refresh(coverage_plan)
    return coverage_plan


# --------------------------------------------------------------------------
# Acesso por module_id/lesson_id isolado (rotas nao aninhadas em project/file)
# --------------------------------------------------------------------------

def get_module_for_user(db: Session, current_user: User, module_id: UUID) -> CoveragePlanModule:
    module = db.get(CoveragePlanModule, module_id)
    if module is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Módulo do plano de cobertura não encontrado.")
    get_project_by_id(db, current_user.organization_id, module.project_id)
    return module


def get_lesson_for_user(db: Session, current_user: User, lesson_id: UUID) -> CoveragePlanLesson:
    lesson = db.get(CoveragePlanLesson, lesson_id)
    if lesson is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aula do plano de cobertura não encontrada.")
    module = db.get(CoveragePlanModule, lesson.module_id)
    if module is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aula do plano de cobertura não encontrada.")
    get_project_by_id(db, current_user.organization_id, module.project_id)
    return lesson


def update_module(db: Session, module: CoveragePlanModule, **fields: Any) -> CoveragePlanModule:
    for key, value in fields.items():
        if value is not None:
            setattr(module, key, value)
    module.updated_at = datetime.now(UTC)
    db.add(module)
    db.commit()
    db.refresh(module)
    return module


def update_lesson(
    db: Session, lesson: CoveragePlanLesson, *, current_user: User, **fields: Any
) -> CoveragePlanLesson:
    target_module_id = fields.pop("module_id", None)
    if target_module_id is not None and target_module_id != lesson.module_id:
        target_module = db.get(CoveragePlanModule, target_module_id)
        if target_module is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Módulo do plano de cobertura não encontrado.",
            )
        # Nunca revela a existencia de um modulo de outra organizacao: mesmo
        # tratamento (404 generico) usado pelo restante do projeto para
        # recursos fora do tenant.
        get_project_by_id(db, current_user.organization_id, target_module.project_id)
        if target_module.coverage_plan_id != lesson.coverage_plan_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Não é possível mover a aula para um módulo de outro plano de cobertura.",
            )
        lesson.module_id = target_module_id

    for key, value in fields.items():
        if value is not None:
            setattr(lesson, key, value)
    lesson.updated_at = datetime.now(UTC)
    db.add(lesson)
    db.commit()
    db.refresh(lesson)
    plan = db.get(CoveragePlan, lesson.coverage_plan_id)
    if plan is not None and plan.status == "approved":
        plan.status = "requires_review"
        db.add(plan)
        db.commit()
    return lesson


# --------------------------------------------------------------------------
# Leitura / resumo
# --------------------------------------------------------------------------

def build_coverage_plan_summary(db: Session, project: Project, project_file: ProjectFile) -> CoveragePlanSummary:
    plan = get_latest_plan(db, project.id)
    if plan is None:
        return CoveragePlanSummary(project_id=project.id, project_file_id=project_file.id)

    result = validate_persisted_coverage(db, plan)
    return CoveragePlanSummary(
        project_id=project.id,
        project_file_id=project_file.id,
        status=plan.status,
        version=plan.version,
        total_modules=plan.total_modules,
        total_lessons=plan.total_lessons,
        total_items=plan.total_items,
        mapped_items=plan.mapped_items,
        unmapped_items=plan.unmapped_items,
        lessons_over_limit=result.lessons_over_limit,
        lessons_under_recommended_duration=result.lessons_under_recommended_duration,
        modules_without_lessons=result.modules_without_lessons,
        lessons_without_sources=result.lessons_without_sources,
        dependency_violations=result.dependency_violations,
        requires_review_items=result.requires_review_source_items,
        pages_requires_ocr=result.pages_requires_ocr,
        estimated_total_words=plan.estimated_total_words,
        estimated_total_minutes=plan.estimated_total_minutes,
        model_name=plan.model_name,
        prompt_version=plan.prompt_version,
        generated_at=plan.updated_at,
        approved_at=plan.approved_at,
        warnings=(plan.report_data or {}).get("ai_warnings", [])[:20] if plan.report_data else [],
    )


def build_plan_response_data(db: Session, coverage_plan: CoveragePlan) -> dict[str, Any]:
    """Monta o plano completo (modulos > aulas > itens) pronto para
    CoveragePlanResponse.model_validate(...), evitando N+1 fora deste helper."""
    modules = list(
        db.execute(
            select(CoveragePlanModule)
            .where(CoveragePlanModule.coverage_plan_id == coverage_plan.id)
            .order_by(CoveragePlanModule.module_order.asc())
        )
        .scalars()
        .all()
    )
    lessons = list(
        db.execute(
            select(CoveragePlanLesson)
            .where(CoveragePlanLesson.coverage_plan_id == coverage_plan.id)
            .order_by(CoveragePlanLesson.lesson_order.asc())
        )
        .scalars()
        .all()
    )
    lessons_by_module: dict[UUID, list[CoveragePlanLesson]] = {}
    for lesson in lessons:
        lessons_by_module.setdefault(lesson.module_id, []).append(lesson)

    lesson_ids = [lesson.id for lesson in lessons]
    links: list[LessonSourceItem] = []
    if lesson_ids:
        links = list(
            db.execute(
                select(LessonSourceItem)
                .where(LessonSourceItem.coverage_plan_lesson_id.in_(lesson_ids))
                .order_by(LessonSourceItem.source_order_in_lesson.asc())
            )
            .scalars()
            .all()
        )
    item_ids = {link.source_item_id for link in links}
    items_by_id: dict[UUID, SourceContentItem] = {}
    if item_ids:
        items_by_id = {
            item.id: item
            for item in db.execute(select(SourceContentItem).where(SourceContentItem.id.in_(item_ids))).scalars().all()
        }
    links_by_lesson: dict[UUID, list[LessonSourceItem]] = {}
    for link in links:
        links_by_lesson.setdefault(link.coverage_plan_lesson_id, []).append(link)

    module_data = []
    for module in modules:
        lesson_data = []
        for lesson in lessons_by_module.get(module.id, []):
            source_item_data = []
            for link in links_by_lesson.get(lesson.id, []):
                item = items_by_id.get(link.source_item_id)
                if item is None:
                    continue
                source_item_data.append(
                    {
                        "source_item_id": item.id,
                        "item_code": item.item_code,
                        "title": item.title,
                        "content_type": item.content_type,
                        "importance": item.importance,
                        "page_start": item.page_start,
                        "page_end": item.page_end,
                        "status": item.status,
                        "coverage_type": link.coverage_type,
                        "source_order_in_lesson": link.source_order_in_lesson,
                        "is_required": link.is_required,
                        "coverage_notes": link.coverage_notes,
                    }
                )
            lesson_dict = {
                key: getattr(lesson, key)
                for key in (
                    "id",
                    "coverage_plan_id",
                    "module_id",
                    "title",
                    "description",
                    "learning_objective",
                    "lesson_order",
                    "target_duration_minutes",
                    "estimated_duration_minutes",
                    "estimated_source_words",
                    "estimated_explanation_words",
                    "estimated_transition_words",
                    "estimated_word_count",
                    "source_item_count",
                    "status",
                    "plan_version",
                    "requires_review",
                    "grouping_reason",
                    "warnings_json",
                    "generated_content_id",
                    "created_at",
                    "updated_at",
                )
            }
            lesson_dict["source_items"] = source_item_data
            lesson_data.append(lesson_dict)

        module_dict = {
            key: getattr(module, key)
            for key in (
                "id",
                "coverage_plan_id",
                "project_id",
                "title",
                "description",
                "learning_objective",
                "module_order",
                "estimated_total_minutes",
                "estimated_total_words",
                "source_item_count",
                "status",
                "plan_version",
                "created_at",
                "updated_at",
            )
        }
        module_dict["lessons"] = lesson_data
        module_data.append(module_dict)

    plan_dict = {
        key: getattr(coverage_plan, key)
        for key in (
            "id",
            "project_id",
            "project_file_id",
            "version",
            "status",
            "inventory_item_count",
            "total_modules",
            "total_lessons",
            "total_items",
            "mapped_items",
            "unmapped_items",
            "estimated_total_words",
            "estimated_total_minutes",
            "model_name",
            "prompt_version",
            "settings_json",
            "report_data",
            "error_message",
            "approved_at",
            "approved_by",
            "created_at",
            "updated_at",
        )
    }
    plan_dict["modules"] = module_data
    return plan_dict


def list_unmapped_items(db: Session, coverage_plan: CoveragePlan) -> list[UnmappedSourceItemResponse]:
    eligible_items = load_inventory(db, coverage_plan.project_file_id)
    lesson_ids = [
        lesson.id
        for lesson in db.execute(
            select(CoveragePlanLesson).where(CoveragePlanLesson.coverage_plan_id == coverage_plan.id)
        )
        .scalars()
        .all()
    ]
    mapped_ids: set[UUID] = set()
    if lesson_ids:
        links = db.execute(
            select(LessonSourceItem).where(LessonSourceItem.coverage_plan_lesson_id.in_(lesson_ids))
        ).scalars().all()
        mapped_ids = {link.source_item_id for link in links}

    unmapped: list[UnmappedSourceItemResponse] = []
    for item in eligible_items:
        if item.id in mapped_ids:
            continue
        reason = "Não incluído em nenhuma aula pela última geração do plano."
        if item.status in REVIEW_FLAG_STATUSES:
            reason = f"Item com status '{item.status}' pendente de revisão no inventário e sem aula associada."
        unmapped.append(
            UnmappedSourceItemResponse(
                source_item_id=item.id,
                item_code=item.item_code,
                title=item.title,
                content_type=item.content_type,
                importance=item.importance,
                page_start=item.page_start,
                page_end=item.page_end,
                status=item.status,
                reason=reason,
                recommended_action="Associe manualmente a uma aula existente ou reprocesse o plano.",
            )
        )
    return unmapped
