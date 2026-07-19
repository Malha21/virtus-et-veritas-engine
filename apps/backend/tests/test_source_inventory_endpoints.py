"""Testes de endpoint via TestClient. O job real usa SessionLocal() propria (fora
da transacao de teste) e chama IA de verdade; os testes de POST substituem
run_source_inventory por um dublê para nunca escrever na base real fora do
rollback do teste. Os testes de GET populam dados chamando generate_inventory()
diretamente na mesma sessao transacional (com fake_ai_provider), mesmo padrao
usado para document_extraction."""

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.database import get_db
from app.main import app
from app.services.source_inventory_service import _create_job, generate_inventory
from tests.conftest import add_extracted_page


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
def _stub_background_inventory(monkeypatch):
    calls = []

    def _fake_run_source_inventory(job_id, user_id):
        calls.append((job_id, user_id))

    monkeypatch.setattr("app.api.v1.source_inventory.run_source_inventory", _fake_run_source_inventory)
    return calls


def run_generation_inline(db_session, current_user, project, project_file):
    job = _create_job(db_session, current_user, project, project_file, mode="generate_if_missing")
    generate_inventory(db_session, current_user, job)
    db_session.commit()
    return job


def test_post_generate_returns_pending_job(client, project, inventory_project_file, db_session):
    add_extracted_page(db_session, inventory_project_file, 1, [("paragraph", "texto valido")])
    db_session.commit()

    response = client.post(f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/inventory/generate")
    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["job_type"] == "source_inventory"
    assert payload["data"]["status"] == "pending"


def test_post_generate_without_extraction_returns_400(client, project, inventory_project_file):
    response = client.post(f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/inventory/generate")
    assert response.status_code == 400


def test_get_summary_not_started(client, project, inventory_project_file):
    response = client.get(f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/inventory/summary")
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "not_started"


def test_get_summary_after_generation(client, db_session, current_user, project, inventory_project_file, fake_ai_provider):
    add_extracted_page(db_session, inventory_project_file, 1, [("paragraph", "conteudo de teste")])
    run_generation_inline(db_session, current_user, project, inventory_project_file)

    response = client.get(f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/inventory/summary")
    data = response.json()["data"]
    assert data["total_items"] >= 1
    assert data["status"] in {"completed", "partially_completed"}


def test_list_inventory_endpoint(client, db_session, current_user, project, inventory_project_file, fake_ai_provider):
    add_extracted_page(
        db_session, inventory_project_file, 1, [("paragraph", "item um"), ("paragraph", "item dois")]
    )
    run_generation_inline(db_session, current_user, project, inventory_project_file)

    response = client.get(f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/inventory")
    data = response.json()["data"]
    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert data["items"][0]["item_code"] == "SRC-0001"


def test_list_inventory_filters_by_importance(client, db_session, current_user, project, inventory_project_file, fake_ai_provider):
    add_extracted_page(db_session, inventory_project_file, 1, [("paragraph", "algum conteudo")])
    run_generation_inline(db_session, current_user, project, inventory_project_file)

    response = client.get(
        f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/inventory",
        params={"importance": "relevant"},
    )
    data = response.json()["data"]
    assert all(item["importance"] == "relevant" for item in data["items"])


def test_get_item_detail_returns_blocks(client, db_session, current_user, project, inventory_project_file, fake_ai_provider):
    add_extracted_page(db_session, inventory_project_file, 1, [("paragraph", "conteudo detalhado")])
    run_generation_inline(db_session, current_user, project, inventory_project_file)

    list_response = client.get(f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/inventory")
    item_id = list_response.json()["data"]["items"][0]["id"]

    response = client.get(f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/inventory/{item_id}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data["blocks"]) >= 1


def test_patch_item_updates_title_and_normalized_content(
    client, db_session, current_user, project, inventory_project_file, fake_ai_provider
):
    add_extracted_page(db_session, inventory_project_file, 1, [("paragraph", "conteudo original")])
    run_generation_inline(db_session, current_user, project, inventory_project_file)

    list_response = client.get(f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/inventory")
    item_id = list_response.json()["data"]["items"][0]["id"]

    response = client.patch(
        f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/inventory/{item_id}",
        json={"title": "Titulo revisado manualmente"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["title"] == "Titulo revisado manualmente"


def test_patch_item_rejects_source_text_field(
    client, db_session, current_user, project, inventory_project_file, fake_ai_provider
):
    add_extracted_page(db_session, inventory_project_file, 1, [("paragraph", "conteudo original")])
    run_generation_inline(db_session, current_user, project, inventory_project_file)

    list_response = client.get(f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/inventory")
    item_id = list_response.json()["data"]["items"][0]["id"]

    response = client.patch(
        f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/inventory/{item_id}",
        json={"title": "Novo titulo", "source_text": "tentativa de alterar o texto original"},
    )
    assert response.status_code == 200
    # o schema ignora campos desconhecidos (source_text nao existe no update manual);
    # o texto original deve permanecer intacto
    detail = client.get(f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/inventory/{item_id}")
    assert detail.json()["data"]["source_text"] == "conteudo original"


def test_approve_and_reject_item(client, db_session, current_user, project, inventory_project_file, fake_ai_provider):
    add_extracted_page(db_session, inventory_project_file, 1, [("paragraph", "conteudo para aprovar")])
    run_generation_inline(db_session, current_user, project, inventory_project_file)

    list_response = client.get(f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/inventory")
    item_id = list_response.json()["data"]["items"][0]["id"]

    approve_response = client.post(
        f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/inventory/{item_id}/approve"
    )
    assert approve_response.json()["data"]["status"] == "approved"

    reject_response = client.post(
        f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/inventory/{item_id}/reject"
    )
    assert reject_response.json()["data"]["status"] == "rejected"


def test_validate_endpoint_returns_deterministic_result(
    client, db_session, current_user, project, inventory_project_file, fake_ai_provider
):
    add_extracted_page(db_session, inventory_project_file, 1, [("paragraph", "conteudo valido")])
    run_generation_inline(db_session, current_user, project, inventory_project_file)

    response = client.post(f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/inventory/validate")
    data = response.json()["data"]
    assert data["total_items"] >= 1
    assert data["status"] in {"valid", "requires_review"}


def test_reprocess_full_rebuild_without_prior_items_returns_400_via_preconditions(
    client, project, inventory_project_file
):
    response = client.post(
        f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/inventory/reprocess",
        json={"mode": "full_rebuild"},
    )
    assert response.status_code == 400


def test_reprocess_pages_requires_page_numbers_at_schema_level(client, project, inventory_project_file):
    response = client.post(
        f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/inventory/reprocess",
        json={"mode": "reprocess_pages"},
    )
    assert response.status_code == 422


def test_endpoints_isolated_between_projects(client, other_project, inventory_project_file):
    response = client.get(f"/api/v1/projects/{other_project.id}/files/{inventory_project_file.id}/inventory/summary")
    assert response.status_code == 404
