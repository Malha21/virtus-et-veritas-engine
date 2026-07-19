import pytest
from sqlalchemy import select

from app.models.document_block import DocumentBlock
from app.models.document_page import DocumentPage
from app.services.document_extraction_service import (
    DocumentExtractionError,
    create_extraction_job,
    extract_document,
)
from tests.conftest import make_epub_bytes


def run_extraction(db_session, current_user, project, project_file, **kwargs):
    job = create_extraction_job(db_session, current_user, project, project_file, **kwargs)
    extract_document(db_session, current_user, job)
    db_session.refresh(job)
    return job


def test_extract_epub_creates_one_page_row_per_chapter(db_session, current_user, project, real_epub_project_file):
    run_extraction(db_session, current_user, project, real_epub_project_file)
    pages = db_session.execute(
        select(DocumentPage).where(DocumentPage.project_file_id == real_epub_project_file.id)
    ).scalars().all()
    assert len(pages) == 4


def test_extract_epub_preserves_chapter_order_and_numbers(db_session, current_user, project, real_epub_project_file):
    run_extraction(db_session, current_user, project, real_epub_project_file)
    pages = db_session.execute(
        select(DocumentPage)
        .where(DocumentPage.project_file_id == real_epub_project_file.id)
        .order_by(DocumentPage.page_number.asc())
    ).scalars().all()
    assert [p.page_number for p in pages] == [1, 2, 3, 4]
    assert "Introducao" in pages[0].raw_text


def test_extract_epub_detects_blank_chapter_as_empty(db_session, current_user, project, real_epub_project_file):
    run_extraction(db_session, current_user, project, real_epub_project_file)
    blank_page = db_session.execute(
        select(DocumentPage).where(
            DocumentPage.project_file_id == real_epub_project_file.id,
            DocumentPage.page_number == 3,
        )
    ).scalar_one()
    assert blank_page.extraction_status == "empty"
    assert blank_page.requires_ocr is False


def test_extract_epub_uses_epub_extraction_method(db_session, current_user, project, real_epub_project_file):
    run_extraction(db_session, current_user, project, real_epub_project_file)
    page = db_session.execute(
        select(DocumentPage).where(
            DocumentPage.project_file_id == real_epub_project_file.id,
            DocumentPage.page_number == 1,
        )
    ).scalar_one()
    assert page.extraction_method == "epub_chapter_text"


def test_extract_epub_is_idempotent_no_duplicate_rows(db_session, current_user, project, real_epub_project_file):
    run_extraction(db_session, current_user, project, real_epub_project_file)
    run_extraction(db_session, current_user, project, real_epub_project_file, force=True)
    pages = db_session.execute(
        select(DocumentPage).where(DocumentPage.project_file_id == real_epub_project_file.id)
    ).scalars().all()
    assert len(pages) == 4


def test_extract_epub_corrupted_file_raises(db_session, current_user, project, corrupted_epub_project_file):
    job = create_extraction_job(db_session, current_user, project, corrupted_epub_project_file)
    with pytest.raises(DocumentExtractionError):
        extract_document(db_session, current_user, job)


def test_extract_epub_detects_h1_as_title_or_heading_block(db_session, current_user, project, written_pdf_files):
    from tests.conftest import _write_real_epub_project_file

    epub_bytes = make_epub_bytes(
        ["Capitulo Um\nTexto normal do primeiro paragrafo do capitulo."],
        heading_chapters={1},
    )
    project_file = _write_real_epub_project_file(db_session, project, epub_bytes, written_pdf_files)

    run_extraction(db_session, current_user, project, project_file)

    blocks = db_session.execute(
        select(DocumentBlock)
        .where(DocumentBlock.project_file_id == project_file.id)
        .order_by(DocumentBlock.block_order.asc())
    ).scalars().all()

    assert blocks[0].source_text == "Capitulo Um"
    assert blocks[0].block_type in {"title", "heading"}
    assert blocks[1].block_type == "paragraph"
