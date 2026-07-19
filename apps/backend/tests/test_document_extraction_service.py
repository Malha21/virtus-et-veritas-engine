import pytest
from sqlalchemy import select

from app.models.document_block import DocumentBlock
from app.models.document_page import DocumentPage
from app.services.document_extraction_service import (
    DocumentExtractionError,
    classify_chunk,
    create_extraction_job,
    detect_repeated_edges,
    extract_document,
    get_active_extraction_job,
    normalize_text,
    segment_page_blocks,
)


def run_extraction(db_session, current_user, project, project_file, **kwargs):
    job = create_extraction_job(db_session, current_user, project, project_file, **kwargs)
    extract_document(db_session, current_user, job)
    db_session.refresh(job)
    return job


# --------------------------------------------------------------------------
# normalize_text
# --------------------------------------------------------------------------

def test_normalize_text_joins_hyphenated_line_breaks():
    raw = "Este e um exem-\nplo de quebra artificial."
    assert "exemplo" in normalize_text(raw)


def test_normalize_text_collapses_duplicate_spaces():
    raw = "Palavra1     Palavra2\tPalavra3"
    normalized = normalize_text(raw)
    assert "Palavra1 Palavra2 Palavra3" == normalized


def test_normalize_text_preserves_numbers_dates_and_accents():
    raw = "Em 11/07/2026, o valor era 2026 e o tema era Educação."
    normalized = normalize_text(raw)
    assert "11/07/2026" in normalized
    assert "2026" in normalized
    assert "Educação" in normalized


def test_normalize_text_does_not_remove_list_markers():
    raw = "- Item um\n- Item dois"
    normalized = normalize_text(raw)
    assert "Item um" in normalized
    assert "Item dois" in normalized


def test_normalize_text_empty_input_returns_empty_string():
    assert normalize_text("") == ""
    assert normalize_text(None) == ""


# --------------------------------------------------------------------------
# segmentacao heuristica
# --------------------------------------------------------------------------

def test_segment_page_blocks_detects_list_items():
    raw = "- Primeiro item\n- Segundo item\n- Terceiro item"
    blocks = segment_page_blocks(raw, [])
    assert len(blocks) == 3
    assert all(block["block_type"] == "list_item" for block in blocks)


def test_segment_page_blocks_detects_caption():
    raw = "Figura 1: Uma legenda de exemplo"
    blocks = segment_page_blocks(raw, [])
    assert blocks[0]["block_type"] == "image_caption"


def test_segment_page_blocks_detects_table_like_lines():
    raw = "Nome     Idade     Cidade\nAna      30        Recife\nJoao     25        Salvador"
    blocks = segment_page_blocks(raw, [])
    assert blocks[0]["block_type"] == "table"
    assert "table_rows" in (blocks[0].get("metadata_json") or {})


def test_segment_page_blocks_empty_text_returns_no_blocks():
    assert segment_page_blocks("", []) == []
    assert segment_page_blocks("   \n\n  ", []) == []


def test_classify_chunk_all_caps_short_is_heading_like():
    result = classify_chunk(["CAPITULO UM"], dominant_font_size=None, chunk_font_size=None)
    assert result in {"title", "heading"}


def test_classify_chunk_long_text_is_paragraph():
    text = " ".join(["palavra"] * 40)
    result = classify_chunk([text], dominant_font_size=None, chunk_font_size=None)
    assert result == "paragraph"


# --------------------------------------------------------------------------
# deteccao de cabecalho/rodape repetido
# --------------------------------------------------------------------------

def test_detect_repeated_edges_finds_repeated_header():
    pages_blocks = {
        1: [{"source_text": "Meu Livro - Capitulo 1"}, {"source_text": "Corpo da pagina 1"}],
        2: [{"source_text": "Meu Livro - Capitulo 1"}, {"source_text": "Corpo da pagina 2"}],
        3: [{"source_text": "Meu Livro - Capitulo 1"}, {"source_text": "Corpo da pagina 3"}],
    }
    headers, _ = detect_repeated_edges(pages_blocks)
    assert len(headers) == 1


def test_detect_repeated_edges_ignores_unique_content():
    pages_blocks = {
        1: [{"source_text": "Introducao unica"}],
        2: [{"source_text": "Conteudo totalmente diferente"}],
    }
    headers, footers = detect_repeated_edges(pages_blocks)
    assert headers == set()
    assert footers == set()


# --------------------------------------------------------------------------
# extracao end-to-end (PDF real gerado via reportlab)
# --------------------------------------------------------------------------

def test_extract_document_creates_one_page_row_per_pdf_page(db_session, current_user, project, real_project_file):
    job = run_extraction(db_session, current_user, project, real_project_file)

    pages = db_session.execute(
        select(DocumentPage).where(DocumentPage.project_file_id == real_project_file.id)
    ).scalars().all()
    assert len(pages) == 4
    assert job.total_items == 4
    assert job.status in {"completed", "partially_completed"}


def test_extract_document_preserves_page_order_and_numbers(db_session, current_user, project, real_project_file):
    run_extraction(db_session, current_user, project, real_project_file)

    pages = db_session.execute(
        select(DocumentPage)
        .where(DocumentPage.project_file_id == real_project_file.id)
        .order_by(DocumentPage.page_number.asc())
    ).scalars().all()
    assert [p.page_number for p in pages] == [1, 2, 3, 4]


def test_extract_document_detects_blank_page(db_session, current_user, project, real_project_file):
    run_extraction(db_session, current_user, project, real_project_file)

    blank_page = db_session.execute(
        select(DocumentPage).where(
            DocumentPage.project_file_id == real_project_file.id,
            DocumentPage.page_number == 3,
        )
    ).scalar_one()
    assert blank_page.extraction_status == "empty"
    assert blank_page.character_count == 0
    assert blank_page.requires_ocr is False


def test_extract_document_preserves_raw_text_separately_from_normalized(
    db_session, current_user, project, real_project_file
):
    run_extraction(db_session, current_user, project, real_project_file)

    first_page = db_session.execute(
        select(DocumentPage).where(
            DocumentPage.project_file_id == real_project_file.id,
            DocumentPage.page_number == 1,
        )
    ).scalar_one()
    assert first_page.raw_text
    assert first_page.normalized_text
    assert "2026" in first_page.raw_text
    assert "2026" in first_page.normalized_text


def test_extract_document_creates_blocks_in_reading_order(db_session, current_user, project, real_project_file):
    run_extraction(db_session, current_user, project, real_project_file)

    first_page = db_session.execute(
        select(DocumentPage).where(
            DocumentPage.project_file_id == real_project_file.id,
            DocumentPage.page_number == 1,
        )
    ).scalar_one()
    blocks = db_session.execute(
        select(DocumentBlock)
        .where(DocumentBlock.page_id == first_page.id)
        .order_by(DocumentBlock.block_order.asc())
    ).scalars().all()

    assert len(blocks) >= 1
    orders = [b.block_order for b in blocks]
    assert orders == sorted(orders)
    codes = [b.block_code for b in blocks]
    assert codes == sorted(codes)


def test_extract_document_detects_list_items_block(db_session, current_user, project, real_project_file):
    run_extraction(db_session, current_user, project, real_project_file)

    page_two = db_session.execute(
        select(DocumentPage).where(
            DocumentPage.project_file_id == real_project_file.id,
            DocumentPage.page_number == 2,
        )
    ).scalar_one()
    blocks = db_session.execute(
        select(DocumentBlock).where(DocumentBlock.page_id == page_two.id)
    ).scalars().all()
    assert any(b.block_type == "list_item" for b in blocks)


def test_extract_document_detects_caption_block(db_session, current_user, project, real_project_file):
    run_extraction(db_session, current_user, project, real_project_file)

    page_four = db_session.execute(
        select(DocumentPage).where(
            DocumentPage.project_file_id == real_project_file.id,
            DocumentPage.page_number == 4,
        )
    ).scalar_one()
    blocks = db_session.execute(
        select(DocumentBlock).where(DocumentBlock.page_id == page_four.id)
    ).scalars().all()
    assert any(b.block_type == "image_caption" for b in blocks)


def test_extract_document_is_idempotent_no_duplicate_rows(db_session, current_user, project, real_project_file):
    run_extraction(db_session, current_user, project, real_project_file)
    run_extraction(db_session, current_user, project, real_project_file, force=True)

    pages = db_session.execute(
        select(DocumentPage).where(DocumentPage.project_file_id == real_project_file.id)
    ).scalars().all()
    assert len(pages) == 4

    for page in pages:
        blocks = db_session.execute(
            select(DocumentBlock).where(DocumentBlock.page_id == page.id)
        ).scalars().all()
        block_orders = [b.block_order for b in blocks]
        assert len(block_orders) == len(set(block_orders))


def test_extract_document_isolated_between_documents(
    db_session, current_user, project, real_project_file, other_project_file
):
    run_extraction(db_session, current_user, project, real_project_file)

    other_pages = db_session.execute(
        select(DocumentPage).where(DocumentPage.project_file_id == other_project_file.id)
    ).scalars().all()
    assert other_pages == []


def test_extract_document_missing_file_raises(db_session, current_user, project, project_file):
    job = create_extraction_job(db_session, current_user, project, project_file)
    with pytest.raises(DocumentExtractionError):
        extract_document(db_session, current_user, job)


def test_extract_document_corrupted_pdf_raises(db_session, current_user, project, corrupted_project_file):
    job = create_extraction_job(db_session, current_user, project, corrupted_project_file)
    with pytest.raises(DocumentExtractionError):
        extract_document(db_session, current_user, job)


def test_active_extraction_job_prevents_duplicate(db_session, current_user, project, real_project_file):
    job1 = create_extraction_job(db_session, current_user, project, real_project_file)
    job2 = create_extraction_job(db_session, current_user, project, real_project_file)
    assert job1.id == job2.id
    assert get_active_extraction_job(db_session, real_project_file.id) is not None
