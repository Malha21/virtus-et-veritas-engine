import logging
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import ebooklib
from bs4 import BeautifulSoup
from ebooklib import epub
from fastapi import HTTPException, status
from pypdf import PdfReader
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.document_block import DocumentBlock
from app.models.document_page import DocumentPage
from app.models.processing_job import ProcessingJob
from app.models.project import Project
from app.models.project_file import ProjectFile
from app.models.user import User
from app.schemas.document_extraction import DocumentExtractionSummary
from app.services.processing_service import add_processing_log, reap_if_stale
from app.services.project_service import get_project_by_id

logger = logging.getLogger(__name__)

EXTRACTION_JOB_TYPE = "document_extraction"
ACTIVE_JOB_STATUSES = ("pending", "queued", "processing")

MIN_CHARS_FOR_RELIABLE_TEXT = 10
HEADER_FOOTER_MIN_OCCURRENCES = 3
HEADER_FOOTER_MIN_RATIO = 0.4
LIST_MARKER_RE = re.compile(r"^\s*([-•*•●‣]|\d{1,3}[.)]|\([a-zA-Z0-9]+\))\s+")
HEADING_NUMBER_RE = re.compile(r"^\s*\d{1,2}(\.\d{1,2}){0,3}[.)]?\s+\S")
CAPTION_RE = re.compile(r"^(figura|fig\.?|tabela|table|imagem|quadro|gr[aá]fico)\s*\d*[:.\s-]", re.IGNORECASE)
FOOTNOTE_RE = re.compile(r"^(\(?\d{1,3}\)?[.\s]|nota\s*:|\*\s)", re.IGNORECASE)
HYPHEN_BREAK_RE = re.compile(r"(\w)-\n(\w)")
MULTISPACE_RE = re.compile(r"[ \t]{2,}")
SINGLE_SPACE_COLLAPSE_RE = re.compile(r"[ \t]+")
BLANK_RUN_RE = re.compile(r"\n{3,}")


class DocumentExtractionError(Exception):
    pass


# --------------------------------------------------------------------------
# Lookup / access control
# --------------------------------------------------------------------------

def get_project_file_for_extraction(
    db: Session, current_user: User, project_id: UUID, file_id: UUID
) -> tuple[Project, ProjectFile]:
    project = get_project_by_id(db, current_user, project_id)
    project_file = db.execute(
        select(ProjectFile).where(
            ProjectFile.id == file_id,
            ProjectFile.project_id == project.id,
            ProjectFile.organization_id == current_user.organization_id,
        )
    ).scalar_one_or_none()

    if project_file is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento não encontrado.")

    if not project_file.original_filename.lower().endswith((".pdf", ".epub")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nesta fase, apenas documentos PDF ou EPUB são suportados para extração estruturada.",
        )

    return project, project_file


def get_active_extraction_job(db: Session, project_file_id: UUID) -> ProcessingJob | None:
    job = db.execute(
        select(ProcessingJob)
        .where(
            ProcessingJob.project_file_id == project_file_id,
            ProcessingJob.job_type == EXTRACTION_JOB_TYPE,
            ProcessingJob.status.in_(ACTIVE_JOB_STATUSES),
        )
        .order_by(ProcessingJob.created_at.desc())
    ).scalars().first()
    return reap_if_stale(db, job)


def get_latest_extraction_job(db: Session, project_file_id: UUID) -> ProcessingJob | None:
    return db.execute(
        select(ProcessingJob)
        .where(
            ProcessingJob.project_file_id == project_file_id,
            ProcessingJob.job_type == EXTRACTION_JOB_TYPE,
        )
        .order_by(ProcessingJob.created_at.desc())
    ).scalars().first()


# --------------------------------------------------------------------------
# Job orchestration (ProcessingJob + BackgroundTasks, same pattern as fase 18
# video_pipeline_service.py: job criado sincronamente, execucao real agendada
# em background, progresso persistido por item a cada pagina).
# --------------------------------------------------------------------------

def create_extraction_job(
    db: Session,
    current_user: User,
    project: Project,
    project_file: ProjectFile,
    *,
    scope: str = "all",
    page_number: int | None = None,
    force: bool = False,
) -> ProcessingJob:
    existing = get_active_extraction_job(db, project_file.id)
    if existing is not None and not force:
        return existing

    job = ProcessingJob(
        project_id=project.id,
        organization_id=current_user.organization_id,
        project_file_id=project_file.id,
        job_type=EXTRACTION_JOB_TYPE,
        status="pending",
        attempts=0,
        max_attempts=3,
        progress=0,
        current_step="Aguardando extração estruturada",
        message="Job de extração estruturada criado",
        processed_items=0,
        failed_items=0,
        payload_json={
            "project_file_id": str(project_file.id),
            "scope": scope,
            "page_number": page_number,
            "checksum": project_file.checksum,
        },
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def create_reprocess_job(
    db: Session,
    current_user: User,
    project_id: UUID,
    file_id: UUID,
    scope: str,
    page_number: int | None,
) -> ProcessingJob:
    project, project_file = get_project_file_for_extraction(db, current_user, project_id, file_id)

    if scope in {"failed", "requires_ocr"}:
        has_pages = db.execute(
            select(func.count(DocumentPage.id)).where(DocumentPage.project_file_id == project_file.id)
        ).scalar_one()
        if not has_pages:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Este documento ainda não foi extraído. Inicie a extração completa primeiro.",
            )

    if scope == "page" and page_number is not None:
        page_exists = db.execute(
            select(func.count(DocumentPage.id)).where(
                DocumentPage.project_file_id == project_file.id,
                DocumentPage.page_number == page_number,
            )
        ).scalar_one()
        if not page_exists:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Página não encontrada.")

    return create_extraction_job(
        db, current_user, project, project_file, scope=scope, page_number=page_number, force=True
    )


def resolve_target_pages(
    db: Session, project_file_id: UUID, total_pages: int, scope: str, page_number: int | None
) -> list[int]:
    if scope == "page" and page_number is not None:
        return [page_number] if 1 <= page_number <= total_pages else []

    if scope == "failed":
        rows = db.execute(
            select(DocumentPage.page_number).where(
                DocumentPage.project_file_id == project_file_id,
                DocumentPage.extraction_status == "failed",
            )
        ).scalars().all()
        return sorted(rows) or list(range(1, total_pages + 1))

    if scope == "requires_ocr":
        rows = db.execute(
            select(DocumentPage.page_number).where(
                DocumentPage.project_file_id == project_file_id,
                DocumentPage.requires_ocr.is_(True),
            )
        ).scalars().all()
        return sorted(rows) or list(range(1, total_pages + 1))

    return list(range(1, total_pages + 1))


def update_job_progress(
    db: Session, job: ProcessingJob, *, current_item: str | None = None, extra_failed: bool = False
) -> None:
    if extra_failed:
        job.failed_items = (job.failed_items or 0) + 1
    else:
        job.processed_items = (job.processed_items or 0) + 1

    total = job.total_items or 1
    done = (job.processed_items or 0) + (job.failed_items or 0)
    job.progress = max(0, min(100, round(done / total * 100)))
    job.current_step = current_item or job.current_step
    job.current_item = current_item
    db.add(job)
    db.commit()


# --------------------------------------------------------------------------
# Text normalization — apenas transformacoes seguras. Nunca resume, reescreve
# ou remove conteudo semantico; raw_text original e sempre preservado a parte.
# --------------------------------------------------------------------------

def normalize_text(raw_text: str | None) -> str:
    if not raw_text:
        return ""

    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    text = "".join(ch for ch in text if ch == "\n" or ch == "\t" or ch.isprintable())
    text = HYPHEN_BREAK_RE.sub(r"\1\2", text)
    text = SINGLE_SPACE_COLLAPSE_RE.sub(" ", text)
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(lines)
    text = BLANK_RUN_RE.sub("\n\n", text)
    return text.strip()


# --------------------------------------------------------------------------
# Extracao por pagina (pypdf, com visitor_text para capturar tamanho de fonte
# quando disponivel, usado apenas como heuristica auxiliar de segmentacao).
# --------------------------------------------------------------------------

def extract_page_raw(reader: PdfReader, page_number: int) -> dict[str, Any]:
    page = reader.pages[page_number - 1]
    spans: list[dict[str, Any]] = []

    def _visitor(text: str, cm: Any, tm: Any, font_dict: Any, font_size: Any) -> None:
        if text and text.strip() and isinstance(font_size, (int, float)) and font_size > 0:
            spans.append({"text": text.strip(), "font_size": float(font_size)})

    try:
        raw_text = page.extract_text(visitor_text=_visitor) or ""
    except Exception:  # noqa: BLE001 - visitor extraction is best-effort
        raw_text = page.extract_text() or ""
        spans = []

    has_images = False
    try:
        has_images = len(page.images) > 0
    except Exception:  # noqa: BLE001 - image inspection is best-effort
        has_images = False

    return {"raw_text": raw_text, "spans": spans, "has_images": has_images}


# --------------------------------------------------------------------------
# Extracao por capitulo (ebooklib). EPUB nao tem "paginas" no sentido do PDF;
# cada item do spine (ordem de leitura) vira uma "pagina" sequencial, para
# reaproveitar sem alteracoes o restante do pipeline (normalizacao, segmentacao,
# persistencia por page_number).
# --------------------------------------------------------------------------

EPUB_BLOCK_TAGS = ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote", "td", "th"]
EPUB_HEADING_FONT_SIZES = {"h1": 24.0, "h2": 22.0, "h3": 20.0, "h4": 18.0, "h5": 16.0, "h6": 14.0}
EPUB_BASELINE_FONT_SIZE = 12.0


def extract_epub_chapters(epub_path: Path) -> list[dict[str, Any]]:
    book = epub.read_epub(str(epub_path))
    chapters: list[dict[str, Any]] = []

    for idref, _linear in book.spine:
        item = book.get_item_with_id(idref)
        if item is None or item.get_type() != ebooklib.ITEM_DOCUMENT:
            continue

        soup = BeautifulSoup(item.get_content(), "html.parser")
        for tag in soup(["script", "style"]):
            tag.decompose()

        has_images = soup.find("img") is not None
        body = soup.body or soup

        # Extrai por elemento de bloco (h1..h6, p, li, ...), atribuindo um
        # "font_size" sintetico por tag - reaproveita a mesma heuristica de
        # deteccao de titulo/heading usada para PDF (baseada em tamanho de
        # fonte), sem precisar de logica nova em classify_chunk.
        text_parts: list[str] = []
        spans: list[dict[str, Any]] = []
        for element in body.find_all(EPUB_BLOCK_TAGS):
            if element.find(EPUB_BLOCK_TAGS):
                continue  # evita duplicar texto de elementos aninhados (ex.: <p> dentro de <blockquote>)
            text = element.get_text(separator=" ", strip=True)
            if not text:
                continue
            text_parts.append(text)
            font_size = EPUB_HEADING_FONT_SIZES.get(element.name, EPUB_BASELINE_FONT_SIZE)
            # Um span por palavra (nao um por elemento): reaproveita a mesma logica
            # de "tamanho de fonte dominante por contagem" usada para PDF, que so
            # funciona com uma amostragem densa (no PDF, o visitor_text do pypdf
            # dispara varias vezes por linha).
            for word in text.split():
                spans.append({"text": word, "font_size": font_size})

        if not text_parts:
            fallback_text = soup.get_text(separator="\n").strip()
            if fallback_text:
                text_parts.append(fallback_text)

        raw_text = "\n\n".join(text_parts)
        chapters.append({"raw_text": raw_text, "spans": spans, "has_images": has_images})

    return chapters


def _font_size_for_text(spans: list[dict[str, Any]], text: str) -> float | None:
    matches = [span["font_size"] for span in spans if span["text"] and span["text"] in text]
    if not matches:
        return None
    return sum(matches) / len(matches)


def _looks_like_table(lines: list[str]) -> bool:
    if len(lines) < 2:
        return False
    column_counts = []
    for line in lines:
        columns = [part for part in MULTISPACE_RE.split(line.strip()) if part]
        column_counts.append(len(columns))
    consistent = sum(1 for count in column_counts if count >= 2)
    return consistent >= max(2, len(lines) - 1)


def _table_rows(lines: list[str]) -> list[list[str]]:
    return [[part for part in MULTISPACE_RE.split(line.strip()) if part] for line in lines]


def classify_chunk(lines: list[str], dominant_font_size: float | None, chunk_font_size: float | None) -> str:
    joined = " ".join(line.strip() for line in lines).strip()
    if not joined:
        return "unknown"

    word_count = len(joined.split())

    if _looks_like_table(lines):
        return "table"

    if CAPTION_RE.match(joined):
        return "image_caption"

    if word_count <= 25 and FOOTNOTE_RE.match(joined) and len(joined) < 300:
        return "footnote"

    if joined.startswith(('"', "“", "‘", "«")):
        return "quotation"

    is_heading_like = word_count <= 14 and (
        joined.isupper() or HEADING_NUMBER_RE.match(joined) or (chunk_font_size and dominant_font_size and chunk_font_size >= dominant_font_size * 1.15)
    )
    if is_heading_like:
        return "title" if len(lines) == 1 and word_count <= 8 else "heading"

    return "paragraph"


def segment_page_blocks(raw_text: str, spans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not raw_text or not raw_text.strip():
        return []

    normalized_for_split = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    raw_groups = [group for group in re.split(r"\n\s*\n", normalized_for_split) if group.strip()]

    font_sizes = [span["font_size"] for span in spans]
    dominant_font_size = max(set(font_sizes), key=font_sizes.count) if font_sizes else None

    blocks: list[dict[str, Any]] = []

    for group in raw_groups:
        lines = [line for line in group.split("\n") if line.strip()]
        if not lines:
            continue

        if len(lines) >= 2 and all(LIST_MARKER_RE.match(line) for line in lines):
            for line in lines:
                blocks.append(
                    {
                        "block_type": "list_item",
                        "source_text": line.strip(),
                        "confidence_score": 70.0,
                    }
                )
            continue

        group_text = "\n".join(lines)
        chunk_font_size = _font_size_for_text(spans, group_text)
        block_type = classify_chunk(lines, dominant_font_size, chunk_font_size)

        metadata: dict[str, Any] = {}
        confidence = 55.0
        if block_type == "table":
            metadata["table_rows"] = _table_rows(lines)
            confidence = 50.0
        elif block_type in {"title", "heading"}:
            confidence = 65.0
        elif block_type in {"image_caption", "footnote", "quotation"}:
            confidence = 60.0

        blocks.append(
            {
                "block_type": block_type,
                "source_text": group_text,
                "confidence_score": confidence,
                "metadata_json": metadata or None,
            }
        )

    return blocks


# --------------------------------------------------------------------------
# Deteccao de cabecalhos/rodapes repetidos entre paginas
# --------------------------------------------------------------------------

def detect_repeated_edges(pages_blocks: dict[int, list[dict[str, Any]]]) -> tuple[set[str], set[str]]:
    total_pages = len(pages_blocks)
    if total_pages < 2:
        return set(), set()

    first_lines: list[str] = []
    last_lines: list[str] = []
    for blocks in pages_blocks.values():
        if not blocks:
            continue
        first_lines.append(normalize_text(blocks[0]["source_text"]).lower())
        last_lines.append(normalize_text(blocks[-1]["source_text"]).lower())

    threshold = max(HEADER_FOOTER_MIN_OCCURRENCES, round(total_pages * HEADER_FOOTER_MIN_RATIO))

    def _repeated(values: list[str]) -> set[str]:
        counts: dict[str, int] = {}
        for value in values:
            if not value:
                continue
            key = re.sub(r"\d+", "#", value)
            counts[key] = counts.get(key, 0) + 1
        return {key for key, count in counts.items() if count >= threshold}

    return _repeated(first_lines), _repeated(last_lines)


# --------------------------------------------------------------------------
# Persistencia (idempotente): upsert de pagina por (project_file_id,
# page_number); blocos da pagina sao apagados e recriados a cada extracao
# daquela pagina especifica — nunca afeta outras paginas ou documentos.
# --------------------------------------------------------------------------

def upsert_page(
    db: Session,
    project_file_id: UUID,
    page_number: int,
    *,
    raw_text: str,
    normalized_text: str,
    extraction_status: str,
    extraction_method: str,
    has_text: bool,
    requires_ocr: bool,
    metadata_json: dict[str, Any] | None,
) -> DocumentPage:
    page = db.execute(
        select(DocumentPage).where(
            DocumentPage.project_file_id == project_file_id,
            DocumentPage.page_number == page_number,
        )
    ).scalar_one_or_none()

    if page is None:
        page = DocumentPage(project_file_id=project_file_id, page_number=page_number)

    page.raw_text = raw_text
    page.normalized_text = normalized_text
    page.character_count = len(normalized_text)
    page.word_count = len(normalized_text.split())
    page.extraction_status = extraction_status
    page.extraction_method = extraction_method
    page.has_text = has_text
    page.requires_ocr = requires_ocr
    page.metadata_json = metadata_json
    page.updated_at = datetime.now(UTC)
    db.add(page)
    db.flush()
    return page


def replace_page_blocks(
    db: Session, project_file_id: UUID, page: DocumentPage, blocks: list[dict[str, Any]]
) -> int:
    db.execute(delete(DocumentBlock).where(DocumentBlock.page_id == page.id))

    for index, block in enumerate(blocks):
        block_code = f"P{page.page_number:04d}-B{index + 1:04d}"
        normalized = normalize_text(block["source_text"])
        db.add(
            DocumentBlock(
                project_file_id=project_file_id,
                page_id=page.id,
                block_code=block_code,
                block_type=block["block_type"],
                block_order=index,
                source_text=block["source_text"],
                normalized_text=normalized,
                confidence_score=block.get("confidence_score"),
                metadata_json=block.get("metadata_json"),
            )
        )
    db.flush()
    return len(blocks)


# --------------------------------------------------------------------------
# Orquestracao principal
# --------------------------------------------------------------------------

def extract_document(db: Session, current_user: User, job: ProcessingJob) -> None:
    project = get_project_by_id(db, current_user, job.project_id)
    project_file = db.get(ProjectFile, job.project_file_id)
    if project_file is None:
        raise DocumentExtractionError("Documento não encontrado para extração.")

    settings = get_settings()
    document_path = Path(settings.storage_path) / project_file.storage_path
    if not document_path.exists():
        raise DocumentExtractionError("Arquivo não encontrado no storage.")

    is_epub = project_file.original_filename.lower().endswith(".epub")
    reader: PdfReader | None = None
    epub_chapters: list[dict[str, Any]] | None = None
    extraction_method = "epub_chapter_text" if is_epub else "native_pdf_text"

    if is_epub:
        try:
            epub_chapters = extract_epub_chapters(document_path)
            total_pages = len(epub_chapters)
        except Exception as exc:  # noqa: BLE001 - abrangente: qualquer falha ao abrir o EPUB e fatal para o job
            raise DocumentExtractionError("Não foi possível abrir o EPUB para extração.") from exc
    else:
        try:
            reader = PdfReader(str(document_path))
            total_pages = len(reader.pages)
        except Exception as exc:  # noqa: BLE001 - abrangente: qualquer falha ao abrir o PDF e fatal para o job
            raise DocumentExtractionError("Não foi possível abrir o PDF para extração.") from exc

    if total_pages == 0:
        raise DocumentExtractionError("O documento não possui páginas/capítulos.")

    payload = job.payload_json or {}
    scope = payload.get("scope", "all")
    requested_page = payload.get("page_number")
    target_pages = resolve_target_pages(db, project_file.id, total_pages, scope, requested_page)

    job.total_items = len(target_pages)
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
        message="Extração estruturada iniciada",
        context_json={"project_file_id": str(project_file.id), "total_pages": total_pages, "scope": scope},
    )

    pages_blocks: dict[int, list[dict[str, Any]]] = {}
    pages_meta: dict[int, dict[str, Any]] = {}
    started_at = time.monotonic()

    for page_number in target_pages:
        try:
            raw = extract_page_raw(reader, page_number) if reader is not None else epub_chapters[page_number - 1]
            raw_text = raw["raw_text"]
            normalized = normalize_text(raw_text)
            char_count = len(normalized)
            has_text = char_count > 0
            blocks = segment_page_blocks(raw_text, raw["spans"])

            # EPUB e texto nativo por definicao: uma imagem no capitulo nunca
            # indica necessidade de OCR (diferente de uma pagina de PDF escaneada).
            image_suggests_ocr = raw["has_images"] and not is_epub

            if char_count == 0:
                page_status = "requires_ocr" if image_suggests_ocr else "empty"
                requires_ocr = image_suggests_ocr
            elif char_count < MIN_CHARS_FOR_RELIABLE_TEXT and image_suggests_ocr:
                page_status = "requires_ocr"
                requires_ocr = True
            else:
                page_status = "extracted"
                requires_ocr = False

            page = upsert_page(
                db,
                project_file.id,
                page_number,
                raw_text=raw_text,
                normalized_text=normalized,
                extraction_status=page_status,
                extraction_method=extraction_method,
                has_text=has_text,
                requires_ocr=requires_ocr,
                metadata_json={"has_images": raw["has_images"]},
            )
            replace_page_blocks(db, project_file.id, page, blocks)
            db.commit()

            pages_blocks[page_number] = blocks
            pages_meta[page_number] = {"page_id": page.id, "has_images": raw["has_images"]}

            update_job_progress(db, job, current_item=f"Página {page_number}/{total_pages}")
        except Exception as exc:  # noqa: BLE001 - falha de uma pagina nao pode abortar o job inteiro
            db.rollback()
            logger.warning("Falha ao extrair página %s do documento %s: %s", page_number, project_file.id, exc)
            upsert_page(
                db,
                project_file.id,
                page_number,
                raw_text="",
                normalized_text="",
                extraction_status="failed",
                extraction_method=extraction_method,
                has_text=False,
                requires_ocr=False,
                metadata_json={"error": str(exc)[:500]},
            )
            db.commit()
            add_processing_log(
                db,
                project_id=project.id,
                organization_id=current_user.organization_id,
                job_id=job.id,
                level="error",
                message=f"Falha ao extrair página {page_number}",
                context_json={"page_number": page_number, "error": str(exc)[:500]},
            )
            update_job_progress(db, job, current_item=f"Página {page_number}/{total_pages}", extra_failed=True)

    finalize_header_footer_detection(db, project_file.id, pages_blocks, pages_meta)

    elapsed_seconds = round(time.monotonic() - started_at, 2)
    job.status = "completed" if (job.failed_items or 0) == 0 else "partially_completed"
    job.current_step = "Extração estruturada concluída"
    job.message = f"Extração concluída em {elapsed_seconds}s"
    job.finished_at = datetime.now(UTC)
    job.result_json = {
        "total_pages": total_pages,
        "processed_pages": job.processed_items,
        "failed_pages": job.failed_items,
        "elapsed_seconds": elapsed_seconds,
    }
    db.add(job)
    db.commit()

    add_processing_log(
        db,
        project_id=project.id,
        organization_id=current_user.organization_id,
        job_id=job.id,
        message="Extração estruturada concluída",
        context_json=job.result_json,
    )


def finalize_header_footer_detection(
    db: Session,
    project_file_id: UUID,
    pages_blocks: dict[int, list[dict[str, Any]]],
    pages_meta: dict[int, dict[str, Any]],
) -> None:
    if not pages_blocks:
        return

    repeated_headers, repeated_footers = detect_repeated_edges(pages_blocks)
    if not repeated_headers and not repeated_footers:
        return

    for page_number, blocks in pages_blocks.items():
        if not blocks:
            continue
        page_id = pages_meta[page_number]["page_id"]
        db_blocks = list(
            db.execute(
                select(DocumentBlock)
                .where(DocumentBlock.page_id == page_id)
                .order_by(DocumentBlock.block_order.asc())
            )
            .scalars()
            .all()
        )
        if not db_blocks:
            continue

        first_key = re.sub(r"\d+", "#", normalize_text(db_blocks[0].source_text).lower())
        last_key = re.sub(r"\d+", "#", normalize_text(db_blocks[-1].source_text).lower())

        changed = False
        if first_key in repeated_headers:
            db_blocks[0].block_type = "page_header"
            db_blocks[0].metadata_json = {**(db_blocks[0].metadata_json or {}), "repeated": True}
            changed = True
        if len(db_blocks) > 1 and last_key in repeated_footers:
            db_blocks[-1].block_type = "page_footer"
            db_blocks[-1].metadata_json = {**(db_blocks[-1].metadata_json or {}), "repeated": True}
            changed = True

        if changed:
            non_edge_blocks = [
                b for b in db_blocks if b.block_type not in {"page_header", "page_footer"}
            ]
            if not non_edge_blocks:
                page = db.get(DocumentPage, page_id)
                if page is not None and page.extraction_status == "extracted":
                    page.extraction_status = "extracted"
                    page.metadata_json = {**(page.metadata_json or {}), "only_header_footer": True}
                    db.add(page)
            db.add_all(db_blocks)

    db.commit()


def run_document_extraction(job_id: UUID, user_id: UUID) -> None:
    with SessionLocal() as db:
        job = db.get(ProcessingJob, job_id)
        user = db.get(User, user_id)
        if job is None or user is None:
            return

        try:
            extract_document(db, user, job)
        except Exception as exc:  # noqa: BLE001 - rede de seguranca do background task
            db.rollback()
            job = db.get(ProcessingJob, job_id)
            if job is not None:
                job.status = "failed"
                job.error_message = str(exc)[:2000]
                job.message = "Falha na extração estruturada"
                job.finished_at = datetime.now(UTC)
                db.add(job)
                db.commit()
                logger.error("Falha na extração do documento (job %s): %s", job_id, exc)


# --------------------------------------------------------------------------
# Leitura / resumo
# --------------------------------------------------------------------------

def build_extraction_summary(db: Session, project_file: ProjectFile) -> DocumentExtractionSummary:
    pages = list(
        db.execute(
            select(DocumentPage).where(DocumentPage.project_file_id == project_file.id)
        ).scalars().all()
    )

    total_blocks = db.execute(
        select(func.count(DocumentBlock.id)).where(DocumentBlock.project_file_id == project_file.id)
    ).scalar_one()

    block_type_rows = db.execute(
        select(DocumentBlock.block_type, func.count(DocumentBlock.id))
        .where(DocumentBlock.project_file_id == project_file.id)
        .group_by(DocumentBlock.block_type)
    ).all()

    latest_job = get_latest_extraction_job(db, project_file.id)

    status_value = "not_started"
    if latest_job is not None:
        status_value = latest_job.status

    return DocumentExtractionSummary(
        project_file_id=project_file.id,
        total_pages=len(pages),
        extracted_pages=sum(1 for p in pages if p.extraction_status == "extracted"),
        empty_pages=sum(1 for p in pages if p.extraction_status == "empty"),
        failed_pages=sum(1 for p in pages if p.extraction_status == "failed"),
        requires_ocr_pages=sum(1 for p in pages if p.requires_ocr),
        total_characters=sum(p.character_count for p in pages),
        total_words=sum(p.word_count for p in pages),
        total_blocks=total_blocks,
        blocks_by_type={block_type: count for block_type, count in block_type_rows},
        extraction_method=pages[0].extraction_method if pages else None,
        status=status_value,
        last_extracted_at=latest_job.finished_at if latest_job else None,
    )


def list_document_pages(
    db: Session,
    project_file: ProjectFile,
    *,
    page: int = 1,
    page_size: int = 50,
    extraction_status: str | None = None,
    requires_ocr: bool | None = None,
) -> tuple[list[DocumentPage], int]:
    conditions = [DocumentPage.project_file_id == project_file.id]
    if extraction_status:
        conditions.append(DocumentPage.extraction_status == extraction_status)
    if requires_ocr is not None:
        conditions.append(DocumentPage.requires_ocr.is_(requires_ocr))

    total = db.execute(select(func.count(DocumentPage.id)).where(*conditions)).scalar_one()

    rows = db.execute(
        select(DocumentPage)
        .where(*conditions)
        .order_by(DocumentPage.page_number.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()

    return list(rows), total


def get_block_counts_by_page(db: Session, page_ids: list[UUID]) -> dict[UUID, int]:
    if not page_ids:
        return {}
    rows = db.execute(
        select(DocumentBlock.page_id, func.count(DocumentBlock.id))
        .where(DocumentBlock.page_id.in_(page_ids))
        .group_by(DocumentBlock.page_id)
    ).all()
    return {page_id: count for page_id, count in rows}


def get_document_page_detail(
    db: Session, project_file: ProjectFile, page_number: int
) -> tuple[DocumentPage, list[DocumentBlock]]:
    doc_page = db.execute(
        select(DocumentPage).where(
            DocumentPage.project_file_id == project_file.id,
            DocumentPage.page_number == page_number,
        )
    ).scalar_one_or_none()

    if doc_page is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Página não encontrada.")

    blocks = list(
        db.execute(
            select(DocumentBlock)
            .where(DocumentBlock.page_id == doc_page.id)
            .order_by(DocumentBlock.block_order.asc())
        )
        .scalars()
        .all()
    )
    return doc_page, blocks


def list_document_blocks(
    db: Session,
    project_file: ProjectFile,
    *,
    page_number: int | None = None,
    block_type: str | None = None,
) -> list[DocumentBlock]:
    conditions = [DocumentBlock.project_file_id == project_file.id]
    query = select(DocumentBlock).join(DocumentPage, DocumentBlock.page_id == DocumentPage.id)

    if page_number is not None:
        conditions.append(DocumentPage.page_number == page_number)
    if block_type:
        conditions.append(DocumentBlock.block_type == block_type)

    rows = db.execute(
        query.where(*conditions).order_by(DocumentPage.page_number.asc(), DocumentBlock.block_order.asc())
    ).scalars().all()
    return list(rows)
