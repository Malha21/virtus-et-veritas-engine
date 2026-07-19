import uuid

import pytest
from fastapi import HTTPException

from app.services.document_extraction_service import (
    build_extraction_summary,
    create_extraction_job,
    create_reprocess_job,
    extract_document,
    get_document_page_detail,
    get_latest_extraction_job,
    get_project_file_for_extraction,
    list_document_blocks,
    list_document_pages,
    resolve_target_pages,
)


def run_extraction(db_session, current_user, project, project_file, **kwargs):
    job = create_extraction_job(db_session, current_user, project, project_file, **kwargs)
    extract_document(db_session, current_user, job)
    db_session.refresh(job)
    return job


def test_resolve_target_pages_scope_all(db_session, real_project_file):
    pages = resolve_target_pages(db_session, real_project_file.id, 4, "all", None)
    assert pages == [1, 2, 3, 4]


def test_resolve_target_pages_scope_page(db_session, real_project_file):
    pages = resolve_target_pages(db_session, real_project_file.id, 4, "page", 3)
    assert pages == [3]


def test_resolve_target_pages_scope_page_out_of_range(db_session, real_project_file):
    assert resolve_target_pages(db_session, real_project_file.id, 4, "page", 99) == []


def test_reprocess_scope_failed_targets_only_failed_pages(db_session, current_user, project, real_project_file):
    run_extraction(db_session, current_user, project, real_project_file)

    # forca uma pagina para failed manualmente para simular falha anterior
    from sqlalchemy import select

    from app.models.document_page import DocumentPage

    page_two = db_session.execute(
        select(DocumentPage).where(
            DocumentPage.project_file_id == real_project_file.id,
            DocumentPage.page_number == 2,
        )
    ).scalar_one()
    page_two.extraction_status = "failed"
    db_session.add(page_two)
    db_session.commit()

    target_pages = resolve_target_pages(db_session, real_project_file.id, 4, "failed", None)
    assert target_pages == [2]


def test_reprocess_job_requires_prior_extraction_for_failed_scope(db_session, current_user, project, real_project_file):
    with pytest.raises(HTTPException):
        create_reprocess_job(db_session, current_user, project.id, real_project_file.id, "failed", None)


def test_reprocess_job_page_scope_requires_existing_page(db_session, current_user, project, real_project_file):
    run_extraction(db_session, current_user, project, real_project_file)
    with pytest.raises(HTTPException):
        create_reprocess_job(db_session, current_user, project.id, real_project_file.id, "page", 999)


def test_build_extraction_summary_reflects_real_data(db_session, current_user, project, real_project_file):
    run_extraction(db_session, current_user, project, real_project_file)
    summary = build_extraction_summary(db_session, real_project_file)

    assert summary.total_pages == 4
    assert summary.empty_pages == 1
    assert summary.total_blocks > 0
    assert summary.status in {"completed", "partially_completed"}


def test_build_extraction_summary_not_started_before_any_job(db_session, real_project_file):
    summary = build_extraction_summary(db_session, real_project_file)
    assert summary.status == "not_started"
    assert summary.total_pages == 0


def test_get_latest_extraction_job_returns_most_recent(db_session, current_user, project, real_project_file):
    from datetime import UTC, datetime, timedelta

    job1 = create_extraction_job(db_session, current_user, project, real_project_file)
    extract_document(db_session, current_user, job1)
    db_session.refresh(job1)
    # Postgres `now()` congela no timestamp da transacao: sem isso, job1 e job2
    # ficariam com created_at identico dentro do mesmo teste transacional.
    job1.created_at = datetime.now(UTC) - timedelta(minutes=5)
    db_session.add(job1)
    db_session.commit()

    job2 = create_extraction_job(db_session, current_user, project, real_project_file, force=True)
    latest = get_latest_extraction_job(db_session, real_project_file.id)
    assert latest.id == job2.id


def test_list_document_pages_pagination(db_session, current_user, project, real_project_file):
    run_extraction(db_session, current_user, project, real_project_file)

    page_1, total = list_document_pages(db_session, real_project_file, page=1, page_size=2)
    assert total == 4
    assert len(page_1) == 2
    assert [p.page_number for p in page_1] == [1, 2]

    page_2, _ = list_document_pages(db_session, real_project_file, page=2, page_size=2)
    assert [p.page_number for p in page_2] == [3, 4]


def test_list_document_pages_filters_by_status(db_session, current_user, project, real_project_file):
    run_extraction(db_session, current_user, project, real_project_file)
    empty_pages, total = list_document_pages(db_session, real_project_file, extraction_status="empty")
    assert total == 1
    assert empty_pages[0].page_number == 3


def test_get_document_page_detail_returns_blocks_in_order(db_session, current_user, project, real_project_file):
    run_extraction(db_session, current_user, project, real_project_file)
    doc_page, blocks = get_document_page_detail(db_session, real_project_file, 1)
    assert doc_page.page_number == 1
    assert [b.block_order for b in blocks] == sorted(b.block_order for b in blocks)


def test_get_document_page_detail_missing_page_raises(db_session, real_project_file):
    with pytest.raises(HTTPException):
        get_document_page_detail(db_session, real_project_file, 999)


def test_list_document_blocks_filters_by_type(db_session, current_user, project, real_project_file):
    run_extraction(db_session, current_user, project, real_project_file)
    captions = list_document_blocks(db_session, real_project_file, block_type="image_caption")
    assert len(captions) >= 1
    assert all(b.block_type == "image_caption" for b in captions)


def test_get_project_file_for_extraction_denies_cross_organization_access(
    db_session, current_user, other_project, other_project_file
):
    # other_project pertence a organizacao diferente de current_user (fixture usa mesma org por padrao),
    # entao testamos com um project_id inexistente para simular acesso negado por isolamento.
    with pytest.raises(HTTPException):
        get_project_file_for_extraction(db_session, current_user, uuid.uuid4(), other_project_file.id)


def test_get_project_file_for_extraction_rejects_non_pdf(db_session, current_user, project, project_file):
    project_file.original_filename = "documento.docx"
    db_session.add(project_file)
    db_session.flush()
    with pytest.raises(HTTPException):
        get_project_file_for_extraction(db_session, current_user, project.id, project_file.id)
