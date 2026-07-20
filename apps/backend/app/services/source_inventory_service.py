import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.document_block import DocumentBlock
from app.models.document_page import DocumentPage
from app.models.processing_job import ProcessingJob
from app.models.project import Project
from app.models.project_file import ProjectFile
from app.models.source_content_item import SourceContentItem
from app.models.source_content_item_block import SourceContentItemBlock
from app.models.source_content_item_dependency import SourceContentItemDependency
from app.models.user import User
from app.prompts import (
    COVERAGE_CHECK_PROMPT_VERSION,
    SOURCE_INVENTORY_PROMPT_VERSION,
    build_coverage_check_prompt,
    build_source_inventory_chunk_prompt,
)
from app.providers.ai import (
    AIProvider,
    AIProviderRequest,
    get_ai_provider,
    resolve_default_model,
    resolve_provider_key,
    resolve_provider_name,
)
from app.schemas.source_inventory import SourceInventorySummary
from app.schemas.source_inventory_ai import AICoverageCheckResponse, AIInventoryChunkResponse, AIInventoryItemResponse
from app.services.ai_orchestrator_service import get_active_ai_provider_record, parse_json_content, register_ai_request
from app.services.document_extraction_service import get_project_file_for_extraction
from app.services.processing_service import add_processing_log, reap_if_stale
from app.services.project_service import get_project_by_id
from app.services.user_ai_credential_service import resolve_generation_api_key, resolve_generation_base_url
from app.services.source_inventory_chunking import ChunkPlan, build_chunks
from app.services.source_inventory_validator import anchor_item_to_blocks, are_likely_same_chunk_overlap_duplicate

logger = logging.getLogger(__name__)

INVENTORY_JOB_TYPE = "source_inventory"
ACTIVE_JOB_STATUSES = ("pending", "queued", "processing")
AI_TEMPERATURE = 0.2
AI_TIMEOUT_SECONDS = 90.0
AI_MAX_RETRIES = 2


class SourceInventoryError(Exception):
    pass


# --------------------------------------------------------------------------
# Precondicoes / acesso
# --------------------------------------------------------------------------

def _load_pages(db: Session, project_file_id: UUID) -> list[DocumentPage]:
    return list(
        db.execute(
            select(DocumentPage)
            .where(DocumentPage.project_file_id == project_file_id)
            .order_by(DocumentPage.page_number.asc())
        )
        .scalars()
        .all()
    )


def check_inventory_preconditions(
    pages: list[DocumentPage], continue_with_alerts: bool
) -> tuple[list[int], list[int]]:
    if not pages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Execute a extração estruturada do documento antes de gerar o inventário.",
        )

    usable = [p for p in pages if p.extraction_status == "extracted"]
    if not usable:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nenhuma página com texto extraído disponível para inventariar.",
        )

    failed_pages = sorted(p.page_number for p in pages if p.extraction_status == "failed")
    ocr_pages = sorted(p.page_number for p in pages if p.requires_ocr)

    if failed_pages and not continue_with_alerts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Existem {len(failed_pages)} página(s) com falha de extração "
                f"({failed_pages[:10]}). Reprocesse a extração ou envie "
                "continue_with_alerts=true para prosseguir com alerta."
            ),
        )

    return failed_pages, ocr_pages


def get_active_inventory_job(db: Session, project_file_id: UUID) -> ProcessingJob | None:
    job = db.execute(
        select(ProcessingJob)
        .where(
            ProcessingJob.project_file_id == project_file_id,
            ProcessingJob.job_type == INVENTORY_JOB_TYPE,
            ProcessingJob.status.in_(ACTIVE_JOB_STATUSES),
        )
        .order_by(ProcessingJob.created_at.desc())
    ).scalars().first()
    return reap_if_stale(db, job)


def get_latest_inventory_job(db: Session, project_file_id: UUID) -> ProcessingJob | None:
    return db.execute(
        select(ProcessingJob)
        .where(
            ProcessingJob.project_file_id == project_file_id,
            ProcessingJob.job_type == INVENTORY_JOB_TYPE,
        )
        .order_by(ProcessingJob.created_at.desc())
    ).scalars().first()


# --------------------------------------------------------------------------
# Criacao do job (parte sincrona: valida tudo antes de aceitar a requisicao)
# --------------------------------------------------------------------------

def start_inventory_generation(
    db: Session,
    current_user: User,
    project_id: UUID,
    file_id: UUID,
    *,
    force: bool = False,
    continue_with_alerts: bool = False,
) -> ProcessingJob:
    project, project_file = get_project_file_for_extraction(db, current_user, project_id, file_id)
    pages = _load_pages(db, project_file.id)
    check_inventory_preconditions(pages, continue_with_alerts)

    existing = get_active_inventory_job(db, project_file.id)
    if existing is not None and not force:
        return existing

    has_existing_items = db.execute(
        select(func.count(SourceContentItem.id)).where(SourceContentItem.project_file_id == project_file.id)
    ).scalar_one()
    mode = "generate_if_missing" if not has_existing_items else "reprocess_failed"

    return _create_job(db, current_user, project, project_file, mode=mode, continue_with_alerts=continue_with_alerts)


def start_inventory_reprocess(
    db: Session,
    current_user: User,
    project_id: UUID,
    file_id: UUID,
    *,
    mode: str,
    page_numbers: list[int] | None,
    continue_with_alerts: bool = False,
) -> ProcessingJob:
    project, project_file = get_project_file_for_extraction(db, current_user, project_id, file_id)
    pages = _load_pages(db, project_file.id)

    if mode != "validate_only":
        check_inventory_preconditions(pages, continue_with_alerts)

    if mode == "reprocess_pages" and page_numbers:
        valid_numbers = {p.page_number for p in pages}
        invalid = [n for n in page_numbers if n not in valid_numbers]
        if invalid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Páginas inexistentes: {invalid}",
            )

    existing = get_active_inventory_job(db, project_file.id)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Já existe um job de inventário ativo para este documento.",
        )

    return _create_job(
        db,
        current_user,
        project,
        project_file,
        mode=mode,
        page_numbers=page_numbers,
        continue_with_alerts=continue_with_alerts,
    )


def _create_job(
    db: Session,
    current_user: User,
    project: Project,
    project_file: ProjectFile,
    *,
    mode: str,
    page_numbers: list[int] | None = None,
    continue_with_alerts: bool = False,
) -> ProcessingJob:
    job = ProcessingJob(
        project_id=project.id,
        organization_id=current_user.organization_id,
        project_file_id=project_file.id,
        job_type=INVENTORY_JOB_TYPE,
        status="pending",
        attempts=0,
        max_attempts=3,
        progress=0,
        current_step="Aguardando geração do inventário",
        message="Job de inventário criado",
        processed_items=0,
        failed_items=0,
        payload_json={
            "project_file_id": str(project_file.id),
            "mode": mode,
            "page_numbers": page_numbers,
            "continue_with_alerts": continue_with_alerts,
            "checksum": project_file.checksum,
        },
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def run_source_inventory(job_id: UUID, user_id: UUID) -> None:
    with SessionLocal() as db:
        job = db.get(ProcessingJob, job_id)
        user = db.get(User, user_id)
        if job is None or user is None:
            return
        try:
            generate_inventory(db, user, job)
        except Exception as exc:  # noqa: BLE001 - rede de seguranca do background task
            db.rollback()
            job = db.get(ProcessingJob, job_id)
            if job is not None:
                job.status = "failed"
                job.error_message = str(exc)[:2000]
                job.message = "Falha na geração do inventário"
                job.finished_at = datetime.now(UTC)
                db.add(job)
                db.commit()
                logger.error("Falha no inventario do documento (job %s): %s", job_id, exc)


# --------------------------------------------------------------------------
# Numeracao estavel de codigos SRC
# --------------------------------------------------------------------------

def next_item_code(db: Session, project_id: UUID) -> str:
    existing_codes = db.execute(
        select(SourceContentItem.item_code).where(SourceContentItem.project_id == project_id)
    ).scalars().all()
    max_number = 0
    for code in existing_codes:
        try:
            number = int(code.split("-")[-1])
        except (ValueError, IndexError):
            continue
        max_number = max(max_number, number)
    return f"SRC-{max_number + 1:04d}"


# --------------------------------------------------------------------------
# Chamada de IA por chunk (com validacao/ancoragem determinística)
# --------------------------------------------------------------------------

class ResolvedItem:
    def __init__(self, ai_item: AIInventoryItemResponse, chunk: ChunkPlan, resolved_blocks: list[DocumentBlock]):
        self.ai_item = ai_item
        self.chunk = chunk
        self.resolved_blocks = resolved_blocks
        self.merged_from: list["ResolvedItem"] = []
        self.superseded = False


def analyze_chunk(
    ai_provider: AIProvider,
    settings,
    db: Session,
    project: Project,
    job: ProcessingJob,
    provider_record_id: UUID,
    chunk: ChunkPlan,
) -> tuple[list[ResolvedItem], list[str]]:
    warnings: list[str] = []
    blocks_by_code = {b.block_code: b for b in chunk.blocks}
    default_model = resolve_default_model(settings, resolve_provider_key(settings, project.ai_provider))

    system_prompt, user_prompt = build_source_inventory_chunk_prompt(
        project_title=project.title,
        chunk_id=chunk.chunk_id,
        page_start=chunk.page_start,
        page_end=chunk.page_end,
        blocks=[
            {
                "block_code": b.block_code,
                "block_type": b.block_type,
                "page_number": b.page_number,
                "source_text": b.source_text,
            }
            for b in chunk.blocks
        ],
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
        request_type="source_inventory_chunk",
        prompt_version=SOURCE_INVENTORY_PROMPT_VERSION,
        response=response,
        model_name=default_model,
    )

    if not response.success:
        raise SourceInventoryError(response.error or f"Falha ao processar {chunk.chunk_id} com IA.")

    try:
        raw_payload = parse_json_content(response.content)
    except Exception as exc:
        raise SourceInventoryError(f"Resposta de IA invalida para {chunk.chunk_id}: {exc}") from exc

    raw_items = raw_payload.get("items", [])
    if not isinstance(raw_items, list):
        raw_items = []

    resolved_items: list[ResolvedItem] = []
    for raw_item in raw_items:
        try:
            ai_item = AIInventoryItemResponse(**raw_item)
        except ValidationError as exc:
            warnings.append(f"{chunk.chunk_id}: item descartado por schema invalido ({exc.error_count()} erros)")
            continue

        anchor = anchor_item_to_blocks(ai_item, blocks_by_code, chunk.page_start, chunk.page_end)
        if not anchor.is_valid:
            ai_item.requires_review = True
            ai_item.review_reason = (ai_item.review_reason or "") + " | ancoragem: " + "; ".join(anchor.errors)
            warnings.append(f"{chunk.chunk_id}/{ai_item.temporary_id}: {'; '.join(anchor.errors)}")

        resolved_items.append(ResolvedItem(ai_item, chunk, anchor.resolved_blocks))

    chunk_warnings = raw_payload.get("chunk_warnings", [])
    if isinstance(chunk_warnings, list):
        warnings.extend(str(w) for w in chunk_warnings)

    return resolved_items, warnings


def run_coverage_check(
    ai_provider: AIProvider,
    settings,
    db: Session,
    project: Project,
    job: ProcessingJob,
    provider_record_id: UUID,
    chunk: ChunkPlan,
    items: list[ResolvedItem],
) -> list[dict[str, str]]:
    items_summary = "\n".join(
        f"- {item.ai_item.title}: {item.ai_item.normalized_content[:200]}" for item in items
    ) or "(nenhum item identificado)"

    default_model = resolve_default_model(settings, resolve_provider_key(settings, project.ai_provider))
    system_prompt, user_prompt = build_coverage_check_prompt(chunk.chunk_id, chunk.source_text, items_summary)

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
        request_type="source_inventory_coverage_check",
        prompt_version=COVERAGE_CHECK_PROMPT_VERSION,
        response=response,
        model_name=default_model,
    )

    if not response.success:
        return []

    try:
        raw_payload = parse_json_content(response.content)
        coverage = AICoverageCheckResponse(**raw_payload)
    except Exception as exc:  # noqa: BLE001 - cobertura e best-effort, nao pode derrubar o chunk
        logger.warning("Falha ao validar cobertura de %s: %s", chunk.chunk_id, exc)
        return []

    if coverage.coverage_status == "complete":
        return []

    return [{"excerpt": m.excerpt, "reason": m.reason} for m in coverage.missing_content]


# --------------------------------------------------------------------------
# Consolidacao de fragmentos e deduplicacao entre chunks adjacentes
# --------------------------------------------------------------------------

def consolidate_fragments(all_items: list[ResolvedItem]) -> list[ResolvedItem]:
    """Funde o ultimo item de um chunk com o primeiro item do chunk seguinte quando
    ambos estao marcados possible_fragment e pertencem a paginas adjacentes/sobrepostas."""
    if len(all_items) < 2:
        return all_items

    result: list[ResolvedItem] = []
    skip_next = False

    for index, item in enumerate(all_items):
        if skip_next:
            skip_next = False
            continue

        if index + 1 < len(all_items):
            next_item = all_items[index + 1]
            same_or_adjacent_chunk = next_item.chunk.chunk_id != item.chunk.chunk_id and next_item.chunk.overlap_from_previous
            both_fragments = item.ai_item.possible_fragment and next_item.ai_item.possible_fragment
            pages_touch = item.ai_item.page_end >= next_item.ai_item.page_start - 1

            if same_or_adjacent_chunk and both_fragments and pages_touch:
                merged_blocks = list(item.resolved_blocks)
                existing_codes = {b.block_code for b in merged_blocks}
                for block in next_item.resolved_blocks:
                    if block.block_code not in existing_codes:
                        merged_blocks.append(block)

                item.ai_item.source_text = f"{item.ai_item.source_text}\n{next_item.ai_item.source_text}"
                item.ai_item.normalized_content = (
                    f"{item.ai_item.normalized_content} {next_item.ai_item.normalized_content}"
                )
                item.ai_item.page_end = max(item.ai_item.page_end, next_item.ai_item.page_end)
                item.ai_item.requires_review = item.ai_item.requires_review or next_item.ai_item.requires_review
                item.resolved_blocks = merged_blocks
                item.merged_from.append(next_item)
                skip_next = True

        result.append(item)

    return result


def deduplicate_items(all_items: list[ResolvedItem]) -> list[ResolvedItem]:
    """Camadas 1 e 2 de deduplicacao, comparando apenas candidatos com paginas
    sobrepostas ou adjacentes (nunca todos-contra-todos)."""
    survivors: list[ResolvedItem] = []

    for item in all_items:
        item_key = _normalized_hash(item.ai_item.normalized_content)
        item_blocks = {b.block_code for b in item.resolved_blocks}
        item_pages = (item.ai_item.page_start, item.ai_item.page_end)

        duplicate_of: ResolvedItem | None = None
        for existing in survivors:
            existing_key = _normalized_hash(existing.ai_item.normalized_content)
            existing_blocks = {b.block_code for b in existing.resolved_blocks}
            existing_pages = (existing.ai_item.page_start, existing.ai_item.page_end)

            # camada 1: identico
            if item_key == existing_key and item_blocks == existing_blocks:
                duplicate_of = existing
                break

            # camada 2: similaridade textual + blocos majoritariamente compartilhados
            is_overlap_artifact, _ratio = are_likely_same_chunk_overlap_duplicate(
                item.ai_item.normalized_content,
                item_blocks,
                item_pages,
                existing.ai_item.normalized_content,
                existing_blocks,
                existing_pages,
            )
            if is_overlap_artifact:
                duplicate_of = existing
                break

        if duplicate_of is not None:
            duplicate_of.merged_from.append(item)
            merged_codes = {b.block_code for b in duplicate_of.resolved_blocks}
            for block in item.resolved_blocks:
                if block.block_code not in merged_codes:
                    duplicate_of.resolved_blocks.append(block)
            item.superseded = True
            continue

        survivors.append(item)

    return survivors


def _normalized_hash(text: str) -> str:
    return " ".join(text.strip().lower().split())


# --------------------------------------------------------------------------
# Persistencia
# --------------------------------------------------------------------------

def persist_chunk_items(
    db: Session,
    project: Project,
    project_file: ProjectFile,
    items: list[ResolvedItem],
) -> list[SourceContentItem]:
    temp_id_to_persisted: dict[str, SourceContentItem] = {}
    persisted: list[SourceContentItem] = []

    for item in items:
        ai_item = item.ai_item
        status_value = "generated"
        if ai_item.requires_review:
            status_value = "requires_review"
        elif ai_item.possible_duplicate:
            status_value = "possible_duplicate"
        elif ai_item.possible_fragment:
            status_value = "fragmented"

        primary_block_order = item.resolved_blocks[0].block_order if item.resolved_blocks else 0

        content_row = SourceContentItem(
            project_id=project.id,
            project_file_id=project_file.id,
            item_code=next_item_code(db, project.id),
            title=ai_item.title,
            source_text=ai_item.source_text,
            normalized_content=ai_item.normalized_content,
            content_type=ai_item.content_type,
            importance=ai_item.importance,
            page_start=ai_item.page_start,
            page_end=ai_item.page_end,
            source_order=ai_item.page_start * 1000 + primary_block_order,
            status=status_value,
            metadata_json={
                "chunk_id": item.chunk.chunk_id,
                "prompt_version": SOURCE_INVENTORY_PROMPT_VERSION,
                "possible_duplicate": ai_item.possible_duplicate,
                "possible_fragment": ai_item.possible_fragment,
                "review_reason": ai_item.review_reason,
                "merged_from_count": len(item.merged_from),
            },
        )
        db.add(content_row)
        db.flush()

        for order, block in enumerate(item.resolved_blocks):
            db.add(
                SourceContentItemBlock(
                    source_item_id=content_row.id,
                    block_id=block.id,
                    source_order=order,
                    is_primary=(order == 0),
                )
            )

        temp_id_to_persisted[f"{item.chunk.chunk_id}:{ai_item.temporary_id}"] = content_row
        persisted.append(content_row)

    for item in items:
        for dep_temp_id in item.ai_item.depends_on_temporary_ids:
            dep_key = f"{item.chunk.chunk_id}:{dep_temp_id}"
            dependent = temp_id_to_persisted.get(f"{item.chunk.chunk_id}:{item.ai_item.temporary_id}")
            depends_on = temp_id_to_persisted.get(dep_key)
            if dependent is None or depends_on is None or dependent.id == depends_on.id:
                continue
            db.add(
                SourceContentItemDependency(
                    source_item_id=dependent.id,
                    depends_on_source_item_id=depends_on.id,
                    dependency_type="depends_on",
                )
            )

    db.flush()
    return persisted


def create_fallback_item(
    db: Session,
    project: Project,
    project_file: ProjectFile,
    chunk: ChunkPlan,
    excerpt: str,
    reason: str,
) -> SourceContentItem:
    """Item de seguranca criado quando a checagem de cobertura encontra conteudo
    do chunk nao representado por nenhum item — nunca descartamos silenciosamente."""
    content_row = SourceContentItem(
        project_id=project.id,
        project_file_id=project_file.id,
        item_code=next_item_code(db, project.id),
        title=excerpt[:120],
        source_text=excerpt,
        normalized_content=excerpt,
        content_type="other",
        importance="relevant",
        page_start=chunk.page_start,
        page_end=chunk.page_end,
        source_order=chunk.page_start * 1000 + 9000,
        status="requires_review",
        metadata_json={
            "chunk_id": chunk.chunk_id,
            "prompt_version": COVERAGE_CHECK_PROMPT_VERSION,
            "source": "coverage_check_gap",
            "review_reason": reason,
        },
    )
    db.add(content_row)
    db.flush()
    return content_row


# --------------------------------------------------------------------------
# Reprocessamento: itens de paginas-alvo sao superseded (nunca apagados)
# --------------------------------------------------------------------------

def supersede_items_for_pages(db: Session, project_file_id: UUID, page_numbers: set[int]) -> int:
    items = db.execute(
        select(SourceContentItem).where(
            SourceContentItem.project_file_id == project_file_id,
            SourceContentItem.status != "approved",
        )
    ).scalars().all()

    superseded_count = 0
    for item in items:
        item_pages = set(range(item.page_start or 0, (item.page_end or item.page_start or 0) + 1))
        if item_pages & page_numbers:
            item.status = "rejected"
            item.metadata_json = {**(item.metadata_json or {}), "superseded_by_reprocess": True}
            db.add(item)
            superseded_count += 1

    db.flush()
    return superseded_count


# --------------------------------------------------------------------------
# Orquestracao principal
# --------------------------------------------------------------------------

def generate_inventory(db: Session, current_user: User, job: ProcessingJob) -> None:
    project = get_project_by_id(db, current_user, job.project_id)
    project_file = db.get(ProjectFile, job.project_file_id)
    if project_file is None:
        raise SourceInventoryError("Documento não encontrado para inventariar.")

    settings = get_settings()
    payload = job.payload_json or {}
    mode = payload.get("mode", "generate_if_missing")
    page_numbers = payload.get("page_numbers")

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
        message="Geração de inventário iniciada",
        context_json={"project_file_id": str(project_file.id), "mode": mode},
    )

    resolved_model_name = resolve_default_model(settings, resolve_provider_key(settings, project.ai_provider))

    if mode == "validate_only":
        _finalize_job(db, job, chunks_total=0, chunks_failed=0, warnings=[], model_name=resolved_model_name)
        return

    pages = _load_pages(db, project_file.id)
    all_blocks = list(
        db.execute(
            select(DocumentBlock)
            .where(DocumentBlock.project_file_id == project_file.id)
            .order_by(DocumentBlock.page_id, DocumentBlock.block_order)
        )
        .scalars()
        .all()
    )
    page_by_id = {p.id: p for p in pages}
    blocks_by_page: dict[int, list[DocumentBlock]] = {}
    for block in all_blocks:
        page = page_by_id.get(block.page_id)
        if page is None:
            continue
        # DocumentBlock nao tem coluna page_number (so page_id); anexamos aqui
        # como atributo transiente para uso no prompt/ancoragem/persistencia.
        block.page_number = page.page_number
        blocks_by_page.setdefault(page.page_number, []).append(block)

    target_pages = pages
    if mode == "reprocess_pages" and page_numbers:
        target_page_set = set(page_numbers)
        target_pages = [p for p in pages if p.page_number in target_page_set]
        supersede_items_for_pages(db, project_file.id, target_page_set)
        db.commit()
    elif mode == "reprocess_failed":
        latest_previous = get_latest_inventory_job(db, project_file.id)
        failed_ranges: set[int] = set()
        if latest_previous and latest_previous.result_json:
            for chunk_result in latest_previous.result_json.get("chunks", []):
                if chunk_result.get("status") == "failed":
                    failed_ranges.update(range(chunk_result["page_start"], chunk_result["page_end"] + 1))
        if failed_ranges:
            target_pages = [p for p in pages if p.page_number in failed_ranges]
            supersede_items_for_pages(db, project_file.id, failed_ranges)
            db.commit()
    elif mode == "full_rebuild":
        all_page_numbers = {p.page_number for p in pages}
        supersede_items_for_pages(db, project_file.id, all_page_numbers)
        db.commit()

    chunks, ignored_pages = build_chunks(target_pages, blocks_by_page)
    job.total_items = len(chunks)
    db.add(job)
    db.commit()

    if not chunks:
        _finalize_job(
            db,
            job,
            chunks_total=0,
            chunks_failed=0,
            warnings=["nenhum chunk gerado para o escopo solicitado"],
            model_name=resolved_model_name,
        )
        return

    provider_key = resolve_provider_key(settings, project.ai_provider)
    user_api_key = resolve_generation_api_key(db, current_user, provider_key)
    user_base_url = resolve_generation_base_url(db, current_user, provider_key)
    ai_provider = get_ai_provider(settings, provider_key, api_key_override=user_api_key, base_url_override=user_base_url)
    provider_record = get_active_ai_provider_record(db, provider_key, resolve_provider_name(settings, provider_key))

    all_items: list[ResolvedItem] = []
    all_warnings: list[str] = []
    chunk_results: list[dict[str, Any]] = []

    for chunk in chunks:
        job.current_item = f"{chunk.chunk_id} (páginas {chunk.page_start}-{chunk.page_end})"
        db.add(job)
        db.commit()

        try:
            resolved_items, warnings = analyze_chunk(
                ai_provider, settings, db, project, job, provider_record.id, chunk
            )
            gaps = run_coverage_check(ai_provider, settings, db, project, job, provider_record.id, chunk, resolved_items)
            for gap in gaps:
                fallback = create_fallback_item(db, project, project_file, chunk, gap["excerpt"], gap["reason"])
                db.commit()
                all_warnings.append(f"{chunk.chunk_id}: item de seguranca criado ({fallback.item_code})")

            all_items.extend(resolved_items)
            all_warnings.extend(warnings)
            chunk_results.append(
                {
                    "chunk_id": chunk.chunk_id,
                    "page_start": chunk.page_start,
                    "page_end": chunk.page_end,
                    "status": "completed",
                    "item_count": len(resolved_items),
                    "gaps_found": len(gaps),
                }
            )
            job.processed_items = (job.processed_items or 0) + 1
        except Exception as exc:  # noqa: BLE001 - falha de um chunk nao aborta o documento inteiro
            db.rollback()
            job = db.get(ProcessingJob, job.id)
            logger.warning("Falha ao processar %s: %s", chunk.chunk_id, exc)
            all_warnings.append(f"{chunk.chunk_id}: falha - {exc}")
            chunk_results.append(
                {
                    "chunk_id": chunk.chunk_id,
                    "page_start": chunk.page_start,
                    "page_end": chunk.page_end,
                    "status": "failed",
                    "item_count": 0,
                    "gaps_found": 0,
                }
            )
            job.failed_items = (job.failed_items or 0) + 1

        total = job.total_items or 1
        done = (job.processed_items or 0) + (job.failed_items or 0)
        job.progress = max(0, min(100, round(done / total * 100)))
        db.add(job)
        db.commit()

    consolidated = consolidate_fragments(all_items)
    deduplicated = deduplicate_items(consolidated)
    surviving = [item for item in deduplicated if not item.superseded]

    persist_chunk_items(db, project, project_file, surviving)
    db.commit()

    _finalize_job(
        db,
        job,
        chunks_total=len(chunks),
        chunks_failed=sum(1 for c in chunk_results if c["status"] == "failed"),
        warnings=all_warnings,
        chunk_results=chunk_results,
        ignored_pages=ignored_pages,
        items_created=len(surviving),
        model_name=resolved_model_name,
    )


def _finalize_job(
    db: Session,
    job: ProcessingJob,
    *,
    chunks_total: int,
    chunks_failed: int,
    warnings: list[str],
    chunk_results: list[dict[str, Any]] | None = None,
    ignored_pages: list[int] | None = None,
    items_created: int = 0,
    model_name: str | None = None,
) -> None:
    job = db.get(ProcessingJob, job.id) or job
    job.status = "completed" if chunks_failed == 0 else "partially_completed"
    job.current_step = "Inventário gerado"
    job.current_item = None
    job.message = f"{items_created} itens criados/atualizados"
    job.finished_at = datetime.now(UTC)
    job.result_json = {
        "chunks_total": chunks_total,
        "chunks_failed": chunks_failed,
        "items_created": items_created,
        "ignored_pages": ignored_pages or [],
        "warnings": warnings[:200],
        "chunks": chunk_results or [],
        "model_name": model_name or get_settings().ai_default_model,
        "prompt_version": SOURCE_INVENTORY_PROMPT_VERSION,
    }
    db.add(job)
    db.commit()


# --------------------------------------------------------------------------
# Leitura / resumo
# --------------------------------------------------------------------------

def build_inventory_summary(db: Session, project: Project, project_file: ProjectFile) -> SourceInventorySummary:
    pages = _load_pages(db, project_file.id)
    total_pages = len(pages)
    pages_processed = sum(1 for p in pages if p.extraction_status == "extracted")
    pages_not_processed = total_pages - pages_processed
    pages_ocr = sum(1 for p in pages if p.requires_ocr)

    total_blocks = db.execute(
        select(func.count(DocumentBlock.id)).where(DocumentBlock.project_file_id == project_file.id)
    ).scalar_one()

    items = db.execute(
        select(SourceContentItem).where(SourceContentItem.project_file_id == project_file.id)
    ).scalars().all()

    blocks_analyzed = db.execute(
        select(func.count(func.distinct(SourceContentItemBlock.block_id)))
        .join(SourceContentItem, SourceContentItemBlock.source_item_id == SourceContentItem.id)
        .where(SourceContentItem.project_file_id == project_file.id)
    ).scalar_one()

    items_by_type: dict[str, int] = {}
    items_by_importance: dict[str, int] = {}
    for item in items:
        items_by_type[item.content_type] = items_by_type.get(item.content_type, 0) + 1
        items_by_importance[item.importance] = items_by_importance.get(item.importance, 0) + 1

    latest_job = get_latest_inventory_job(db, project_file.id)
    result = latest_job.result_json if latest_job and latest_job.result_json else {}

    return SourceInventorySummary(
        project_id=project.id,
        project_file_id=project_file.id,
        status=latest_job.status if latest_job else "not_started",
        total_pages=total_pages,
        pages_processed=pages_processed,
        pages_not_processed=pages_not_processed,
        pages_requires_ocr=pages_ocr,
        total_blocks=total_blocks,
        blocks_analyzed=blocks_analyzed,
        blocks_ignored=total_blocks - blocks_analyzed if total_blocks >= blocks_analyzed else 0,
        total_chunks=result.get("chunks_total", 0),
        chunks_completed=(result.get("chunks_total", 0) - result.get("chunks_failed", 0)),
        chunks_failed=result.get("chunks_failed", 0),
        total_items=len(items),
        items_by_type=items_by_type,
        items_by_importance=items_by_importance,
        possible_duplicates=sum(1 for i in items if i.status == "possible_duplicate"),
        fragmented_items=sum(1 for i in items if i.status == "fragmented"),
        requires_review_items=sum(1 for i in items if i.status == "requires_review"),
        approved_items=sum(1 for i in items if i.status == "approved"),
        rejected_items=sum(1 for i in items if i.status == "rejected"),
        page_coverage_percentage=round(pages_processed / total_pages * 100, 2) if total_pages else 0.0,
        block_coverage_percentage=round(blocks_analyzed / total_blocks * 100, 2) if total_blocks else 0.0,
        model_name=result.get("model_name"),
        prompt_version=result.get("prompt_version"),
        generated_at=latest_job.finished_at if latest_job else None,
    )


def list_inventory_items(
    db: Session,
    project_file: ProjectFile,
    *,
    page: int = 1,
    page_size: int = 50,
    content_type: str | None = None,
    importance: str | None = None,
    status_filter: str | None = None,
    page_number: int | None = None,
    requires_review: bool | None = None,
    possible_duplicate: bool | None = None,
    search: str | None = None,
) -> tuple[list[SourceContentItem], int]:
    conditions = [SourceContentItem.project_file_id == project_file.id]
    if content_type:
        conditions.append(SourceContentItem.content_type == content_type)
    if importance:
        conditions.append(SourceContentItem.importance == importance)
    if status_filter:
        conditions.append(SourceContentItem.status == status_filter)
    if requires_review is True:
        conditions.append(SourceContentItem.status == "requires_review")
    if possible_duplicate is True:
        conditions.append(SourceContentItem.status == "possible_duplicate")
    if page_number is not None:
        conditions.append(SourceContentItem.page_start <= page_number)
        conditions.append(SourceContentItem.page_end >= page_number)
    if search:
        like_value = f"%{search}%"
        conditions.append(SourceContentItem.title.ilike(like_value))

    total = db.execute(select(func.count(SourceContentItem.id)).where(*conditions)).scalar_one()

    rows = db.execute(
        select(SourceContentItem)
        .where(*conditions)
        .order_by(SourceContentItem.source_order.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()

    return list(rows), total


def get_inventory_item_detail(
    db: Session, project_file: ProjectFile, source_item_id: UUID
) -> tuple[SourceContentItem, list[SourceContentItemBlock], list[SourceContentItemDependency], list[SourceContentItemDependency]]:
    item = db.execute(
        select(SourceContentItem).where(
            SourceContentItem.id == source_item_id,
            SourceContentItem.project_file_id == project_file.id,
        )
    ).scalar_one_or_none()

    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item do inventário não encontrado.")

    blocks = list(
        db.execute(
            select(SourceContentItemBlock)
            .where(SourceContentItemBlock.source_item_id == item.id)
            .order_by(SourceContentItemBlock.source_order.asc())
        )
        .scalars()
        .all()
    )
    dependencies = list(
        db.execute(
            select(SourceContentItemDependency).where(SourceContentItemDependency.source_item_id == item.id)
        )
        .scalars()
        .all()
    )
    dependents = list(
        db.execute(
            select(SourceContentItemDependency).where(
                SourceContentItemDependency.depends_on_source_item_id == item.id
            )
        )
        .scalars()
        .all()
    )

    return item, blocks, dependencies, dependents


def update_inventory_item(
    db: Session,
    project_file: ProjectFile,
    source_item_id: UUID,
    *,
    title: str | None = None,
    normalized_content: str | None = None,
    content_type: str | None = None,
    importance: str | None = None,
    review_note: str | None = None,
) -> SourceContentItem:
    item, _, _, _ = get_inventory_item_detail(db, project_file, source_item_id)

    if title is not None:
        item.title = title
    if normalized_content is not None:
        item.normalized_content = normalized_content
    if content_type is not None:
        item.content_type = content_type
    if importance is not None:
        item.importance = importance
    if review_note is not None:
        item.metadata_json = {**(item.metadata_json or {}), "review_note": review_note}

    item.updated_at = datetime.now(UTC)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def set_inventory_item_status(
    db: Session, project_file: ProjectFile, source_item_id: UUID, new_status: str
) -> SourceContentItem:
    item, _, _, _ = get_inventory_item_detail(db, project_file, source_item_id)
    item.status = new_status
    item.updated_at = datetime.now(UTC)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item
