"""Testes de endpoint via TestClient. O job de extracao real usa SessionLocal()
proprio (fora da transacao de teste), entao os testes de POST substituem
run_document_extraction por um dublê para nunca escrever na base real fora do
rollback do teste; os testes de GET populam dados chamando extract_document()
diretamente na mesma sessao transacional (mesmo padrao dos demais arquivos)."""

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.database import get_db
from app.main import app
from app.services.document_extraction_service import create_extraction_job, extract_document


@pytest.fixture()
def client(db_session, current_user):
    def _get_db_override():
        yield db_session

    def _get_current_user_override():
        return current_user

    app.dependency_overrides[get_db] = _get_db_override
    app.dependency_overrides[get_current_user] = _get_current_user_override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _stub_background_extraction(monkeypatch):
    calls = []

    def _fake_run_document_extraction(job_id, user_id):
        calls.append((job_id, user_id))

    monkeypatch.setattr(
        "app.api.v1.document_extraction.run_document_extraction", _fake_run_document_extraction
    )
    return calls


def run_extraction_inline(db_session, current_user, project, project_file):
    job = create_extraction_job(db_session, current_user, project, project_file)
    extract_document(db_session, current_user, job)
    db_session.commit()
    return job


def test_post_extraction_returns_pending_job(client, project, real_project_file):
    response = client.post(f"/api/v1/projects/{project.id}/files/{real_project_file.id}/extraction")
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["job_type"] == "document_extraction"
    assert payload["data"]["status"] == "pending"


def test_post_extraction_is_idempotent_for_concurrent_calls(client, project, real_project_file):
    first = client.post(f"/api/v1/projects/{project.id}/files/{real_project_file.id}/extraction")
    second = client.post(f"/api/v1/projects/{project.id}/files/{real_project_file.id}/extraction")
    assert first.json()["data"]["id"] == second.json()["data"]["id"]


def test_post_extraction_rejects_non_pdf(client, project, project_file, db_session):
    project_file.original_filename = "arquivo.docx"
    db_session.add(project_file)
    db_session.flush()
    response = client.post(f"/api/v1/projects/{project.id}/files/{project_file.id}/extraction")
    assert response.status_code == 400


def test_post_extraction_unknown_document_returns_404(client, project):
    import uuid

    response = client.post(f"/api/v1/projects/{project.id}/files/{uuid.uuid4()}/extraction")
    assert response.status_code == 404


def test_get_extraction_summary_not_started(client, project, real_project_file):
    response = client.get(f"/api/v1/projects/{project.id}/files/{real_project_file.id}/extraction")
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "not_started"


def test_get_extraction_summary_after_extraction(client, db_session, current_user, project, real_project_file):
    run_extraction_inline(db_session, current_user, project, real_project_file)

    response = client.get(f"/api/v1/projects/{project.id}/files/{real_project_file.id}/extraction")
    data = response.json()["data"]
    assert data["total_pages"] == 4
    assert data["status"] in {"completed", "partially_completed"}


def test_get_pages_endpoint_returns_paginated_list(client, db_session, current_user, project, real_project_file):
    run_extraction_inline(db_session, current_user, project, real_project_file)

    response = client.get(
        f"/api/v1/projects/{project.id}/files/{real_project_file.id}/pages",
        params={"page": 1, "page_size": 2},
    )
    data = response.json()["data"]
    assert data["total"] == 4
    assert len(data["items"]) == 2
    assert data["items"][0]["page_number"] == 1


def test_get_page_detail_endpoint_returns_blocks(client, db_session, current_user, project, real_project_file):
    run_extraction_inline(db_session, current_user, project, real_project_file)

    response = client.get(f"/api/v1/projects/{project.id}/files/{real_project_file.id}/pages/1")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["page_number"] == 1
    assert "blocks" in data


def test_get_page_detail_endpoint_404_for_missing_page(client, project, real_project_file):
    response = client.get(f"/api/v1/projects/{project.id}/files/{real_project_file.id}/pages/999")
    assert response.status_code == 404


def test_get_blocks_endpoint_filters_by_type(client, db_session, current_user, project, real_project_file):
    run_extraction_inline(db_session, current_user, project, real_project_file)

    response = client.get(
        f"/api/v1/projects/{project.id}/files/{real_project_file.id}/blocks",
        params={"block_type": "image_caption"},
    )
    items = response.json()["data"]["items"]
    assert all(item["block_type"] == "image_caption" for item in items)


def test_post_reprocess_without_prior_extraction_returns_400(client, project, real_project_file):
    response = client.post(
        f"/api/v1/projects/{project.id}/files/{real_project_file.id}/extraction/reprocess",
        json={"scope": "failed"},
    )
    assert response.status_code == 400


def test_post_reprocess_page_scope_requires_page_number(client, project, real_project_file):
    response = client.post(
        f"/api/v1/projects/{project.id}/files/{real_project_file.id}/extraction/reprocess",
        json={"scope": "page"},
    )
    assert response.status_code == 422


def test_endpoints_isolated_between_projects(client, other_project, real_project_file):
    response = client.get(f"/api/v1/projects/{other_project.id}/files/{real_project_file.id}/extraction")
    assert response.status_code == 404
