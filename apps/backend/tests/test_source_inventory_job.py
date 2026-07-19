import uuid

import pytest
from fastapi import HTTPException

from app.models.organization import Organization
from app.services.source_inventory_service import (
    get_active_inventory_job,
    get_latest_inventory_job,
    start_inventory_generation,
    start_inventory_reprocess,
)
from tests.conftest import _make_extracted_project_file, _make_project, add_extracted_page


def test_generate_blocked_without_any_extraction(db_session, current_user, project, inventory_project_file):
    with pytest.raises(HTTPException) as exc_info:
        start_inventory_generation(db_session, current_user, project.id, inventory_project_file.id)
    assert exc_info.value.status_code == 400


def test_generate_blocked_by_failed_pages_without_alert_flag(db_session, current_user, project, inventory_project_file):
    add_extracted_page(db_session, inventory_project_file, 1, [("paragraph", "texto valido")])
    add_extracted_page(db_session, inventory_project_file, 2, [], extraction_status="failed")

    with pytest.raises(HTTPException) as exc_info:
        start_inventory_generation(db_session, current_user, project.id, inventory_project_file.id)
    assert exc_info.value.status_code == 400


def test_generate_allowed_with_continue_with_alerts(db_session, current_user, project, inventory_project_file):
    add_extracted_page(db_session, inventory_project_file, 1, [("paragraph", "texto valido")])
    add_extracted_page(db_session, inventory_project_file, 2, [], extraction_status="failed")

    job = start_inventory_generation(
        db_session, current_user, project.id, inventory_project_file.id, continue_with_alerts=True
    )
    assert job is not None
    assert job.status == "pending"


def test_generate_prevents_duplicate_active_job(db_session, current_user, project, inventory_project_file):
    add_extracted_page(db_session, inventory_project_file, 1, [("paragraph", "texto")])

    job1 = start_inventory_generation(db_session, current_user, project.id, inventory_project_file.id)
    job2 = start_inventory_generation(db_session, current_user, project.id, inventory_project_file.id)

    assert job1.id == job2.id
    assert get_active_inventory_job(db_session, inventory_project_file.id) is not None


def test_reprocess_conflicts_with_active_job(db_session, current_user, project, inventory_project_file):
    add_extracted_page(db_session, inventory_project_file, 1, [("paragraph", "texto")])
    start_inventory_generation(db_session, current_user, project.id, inventory_project_file.id)

    with pytest.raises(HTTPException) as exc_info:
        start_inventory_reprocess(
            db_session, current_user, project.id, inventory_project_file.id, mode="full_rebuild", page_numbers=None
        )
    assert exc_info.value.status_code == 409


def test_reprocess_pages_rejects_unknown_page_number(db_session, current_user, project, inventory_project_file):
    add_extracted_page(db_session, inventory_project_file, 1, [("paragraph", "texto")])

    with pytest.raises(HTTPException) as exc_info:
        start_inventory_reprocess(
            db_session,
            current_user,
            project.id,
            inventory_project_file.id,
            mode="reprocess_pages",
            page_numbers=[999],
        )
    assert exc_info.value.status_code == 400


def test_validate_only_mode_does_not_require_no_failed_pages(db_session, current_user, project, inventory_project_file):
    add_extracted_page(db_session, inventory_project_file, 1, [("paragraph", "texto")])
    add_extracted_page(db_session, inventory_project_file, 2, [], extraction_status="failed")

    job = start_inventory_reprocess(
        db_session, current_user, project.id, inventory_project_file.id, mode="validate_only", page_numbers=None
    )
    assert job is not None


def test_get_latest_inventory_job_after_none_exists(db_session, inventory_project_file):
    assert get_latest_inventory_job(db_session, inventory_project_file.id) is None


def test_generate_isolated_between_organizations(db_session, current_user):
    other_org = Organization(name="Outra Org", slug=f"outra-org-{uuid.uuid4().hex[:8]}")
    db_session.add(other_org)
    db_session.flush()
    foreign_project = _make_project(db_session, other_org, title="Projeto de outra organizacao")
    foreign_file = _make_extracted_project_file(db_session, foreign_project)
    add_extracted_page(db_session, foreign_file, 1, [("paragraph", "texto")])

    # current_user pertence a organizacao do fixture "project", nao a "other_org"
    with pytest.raises(HTTPException) as exc_info:
        start_inventory_generation(db_session, current_user, foreign_project.id, foreign_file.id)
    assert exc_info.value.status_code == 404
