import pytest
from sqlalchemy.exc import IntegrityError

from app.models.document_block import DocumentBlock
from app.models.document_page import DocumentPage


def _make_page(project_file, page_number=1):
    return DocumentPage(
        project_file_id=project_file.id,
        page_number=page_number,
        raw_text="texto",
        normalized_text="texto",
        character_count=5,
        word_count=1,
        extraction_status="extracted",
        has_text=True,
    )


def test_page_number_unique_within_document(db_session, project_file):
    db_session.add(_make_page(project_file, page_number=1))
    db_session.flush()

    db_session.add(_make_page(project_file, page_number=1))
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_same_page_number_allowed_across_documents(db_session, project_file, other_project_file):
    db_session.add(_make_page(project_file, page_number=1))
    db_session.add(_make_page(other_project_file, page_number=1))
    db_session.flush()  # nao deve levantar erro


def test_page_number_must_be_positive(db_session, project_file):
    db_session.add(_make_page(project_file, page_number=0))
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_block_code_unique_within_document(db_session, project_file):
    page1 = _make_page(project_file, page_number=1)
    page2 = _make_page(project_file, page_number=2)
    db_session.add_all([page1, page2])
    db_session.flush()

    db_session.add(
        DocumentBlock(
            project_file_id=project_file.id,
            page_id=page1.id,
            block_code="P0001-B0001",
            block_type="paragraph",
            block_order=0,
            source_text="texto",
        )
    )
    db_session.flush()

    db_session.add(
        DocumentBlock(
            project_file_id=project_file.id,
            page_id=page2.id,
            block_code="P0001-B0001",
            block_type="paragraph",
            block_order=0,
            source_text="texto duplicado",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_block_order_unique_within_page(db_session, project_file):
    page = _make_page(project_file, page_number=1)
    db_session.add(page)
    db_session.flush()

    db_session.add(
        DocumentBlock(
            project_file_id=project_file.id,
            page_id=page.id,
            block_code="P0001-B0001",
            block_type="paragraph",
            block_order=0,
            source_text="primeiro",
        )
    )
    db_session.flush()

    db_session.add(
        DocumentBlock(
            project_file_id=project_file.id,
            page_id=page.id,
            block_code="P0001-B0002",
            block_type="paragraph",
            block_order=0,
            source_text="segundo com mesma ordem",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_block_order_must_be_non_negative(db_session, project_file):
    page = _make_page(project_file, page_number=1)
    db_session.add(page)
    db_session.flush()

    db_session.add(
        DocumentBlock(
            project_file_id=project_file.id,
            page_id=page.id,
            block_code="P0001-B0001",
            block_type="paragraph",
            block_order=-1,
            source_text="texto",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_confidence_score_out_of_range_rejected_at_db_level(db_session, project_file):
    page = _make_page(project_file, page_number=1)
    db_session.add(page)
    db_session.flush()

    db_session.add(
        DocumentBlock(
            project_file_id=project_file.id,
            page_id=page.id,
            block_code="P0001-B0001",
            block_type="paragraph",
            block_order=0,
            source_text="texto",
            confidence_score=150,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_deleting_project_file_cascades_to_pages_and_blocks(db_session, project_file):
    page = _make_page(project_file, page_number=1)
    db_session.add(page)
    db_session.flush()
    db_session.add(
        DocumentBlock(
            project_file_id=project_file.id,
            page_id=page.id,
            block_code="P0001-B0001",
            block_type="paragraph",
            block_order=0,
            source_text="texto",
        )
    )
    db_session.flush()
    page_id = page.id

    db_session.delete(project_file)
    db_session.flush()
    db_session.expire_all()

    assert db_session.get(DocumentPage, page_id) is None


def test_deleting_page_cascades_to_blocks(db_session, project_file):
    page = _make_page(project_file, page_number=1)
    db_session.add(page)
    db_session.flush()
    block = DocumentBlock(
        project_file_id=project_file.id,
        page_id=page.id,
        block_code="P0001-B0001",
        block_type="paragraph",
        block_order=0,
        source_text="texto",
    )
    db_session.add(block)
    db_session.flush()
    block_id = block.id

    db_session.delete(page)
    db_session.flush()
    db_session.expire_all()

    assert db_session.get(DocumentBlock, block_id) is None
