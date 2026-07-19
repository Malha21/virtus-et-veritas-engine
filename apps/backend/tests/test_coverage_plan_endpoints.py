"""Testes de endpoint via TestClient, seguindo o mesmo padrao de
test_source_inventory_endpoints.py: o job real usa SessionLocal() propria e
chama IA de verdade, entao POSTs substituem run_coverage_plan_generation por um
dublê; GETs populam dados chamando generate_coverage_plan() diretamente na mesma
sessao transacional (com fake_coverage_plan_ai_provider)."""

import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.deps import get_current_user
from app.core.database import get_db
from app.main import app
from app.models.coverage_plan_lesson import CoveragePlanLesson
from app.models.coverage_plan_module import CoveragePlanModule
from app.services import coverage_plan_service as svc
from app.services.coverage_plan_service import (
    generate_coverage_plan,
    start_coverage_plan_generation,
    start_coverage_plan_regenerate,
)
from tests.conftest import make_source_item


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
def _stub_background_coverage_plan(monkeypatch):
    calls = []

    def _fake_run(job_id, user_id):
        calls.append((job_id, user_id))

    monkeypatch.setattr("app.api.v1.coverage_plan.run_coverage_plan_generation", _fake_run)
    return calls


def _make_items(db_session, project, project_file, count=4):
    items = []
    for i in range(1, count + 1):
        items.append(
            make_source_item(
                db_session,
                project,
                project_file,
                item_code=f"SRC-{i:04d}",
                title=f"Item {i}",
                normalized_content=f"conteudo do item {i} " * 5,
                source_order=i * 10,
            )
        )
    db_session.commit()
    return items


def run_generation_inline(db_session, current_user, project, project_file):
    job = start_coverage_plan_generation(db_session, current_user, project.id, project_file.id)
    generate_coverage_plan(db_session, current_user, job)
    db_session.commit()
    return job


def run_regenerate_inline(db_session, current_user, project, project_file, mode="regenerate_draft"):
    job = start_coverage_plan_regenerate(db_session, current_user, project.id, project_file.id, mode=mode)
    generate_coverage_plan(db_session, current_user, job)
    db_session.commit()
    return job


def test_post_generate_returns_pending_job(client, project, inventory_project_file, db_session):
    _make_items(db_session, project, inventory_project_file)
    response = client.post(f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/coverage-plan/generate")
    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["job_type"] == "coverage_plan"
    assert payload["data"]["status"] == "pending"


def test_post_generate_without_inventory_returns_400(client, project, inventory_project_file):
    response = client.post(f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/coverage-plan/generate")
    assert response.status_code == 400


def test_get_summary_not_started(client, project, inventory_project_file):
    response = client.get(f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/coverage-plan/summary")
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "not_started"


def test_get_summary_after_generation(
    client, db_session, current_user, project, inventory_project_file, fake_coverage_plan_ai_provider
):
    _make_items(db_session, project, inventory_project_file)
    run_generation_inline(db_session, current_user, project, inventory_project_file)

    response = client.get(f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/coverage-plan/summary")
    data = response.json()["data"]
    assert data["total_items"] == 4
    assert data["unmapped_items"] == 0


def test_get_coverage_plan_returns_modules_and_lessons(
    client, db_session, current_user, project, inventory_project_file, fake_coverage_plan_ai_provider
):
    _make_items(db_session, project, inventory_project_file)
    run_generation_inline(db_session, current_user, project, inventory_project_file)

    response = client.get(f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/coverage-plan")
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data["modules"]) > 0
    assert len(data["modules"][0]["lessons"]) > 0
    assert len(data["modules"][0]["lessons"][0]["source_items"]) > 0


def test_get_coverage_plan_without_plan_returns_404(client, project, inventory_project_file):
    response = client.get(f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/coverage-plan")
    assert response.status_code == 404


def test_validate_endpoint(
    client, db_session, current_user, project, inventory_project_file, fake_coverage_plan_ai_provider
):
    _make_items(db_session, project, inventory_project_file)
    run_generation_inline(db_session, current_user, project, inventory_project_file)

    response = client.post(f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/coverage-plan/validate")
    data = response.json()["data"]
    assert data["status"] == "valid"
    assert data["unmapped_items"] == 0


def test_unmapped_items_endpoint(
    client, db_session, current_user, project, inventory_project_file, fake_coverage_plan_ai_provider
):
    _make_items(db_session, project, inventory_project_file)
    run_generation_inline(db_session, current_user, project, inventory_project_file)
    make_source_item(
        db_session, project, inventory_project_file, item_code="SRC-9999", title="Órfão", normalized_content="conteudo"
    )
    db_session.commit()

    response = client.get(f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/coverage-plan/unmapped-items")
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["item_code"] == "SRC-9999"


def test_approve_endpoint_blocks_and_then_succeeds(
    client, db_session, current_user, project, inventory_project_file, fake_coverage_plan_ai_provider
):
    _make_items(db_session, project, inventory_project_file)
    run_generation_inline(db_session, current_user, project, inventory_project_file)

    ok_response = client.post(f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/coverage-plan/approve")
    assert ok_response.status_code == 200
    assert ok_response.json()["data"]["status"] == "approved"


def test_versions_endpoint(
    client, db_session, current_user, project, inventory_project_file, fake_coverage_plan_ai_provider
):
    _make_items(db_session, project, inventory_project_file)
    run_generation_inline(db_session, current_user, project, inventory_project_file)

    response = client.get(f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/coverage-plan/versions")
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["version"] == 1


def test_endpoints_isolated_between_projects(client, other_project, inventory_project_file):
    response = client.get(f"/api/v1/projects/{other_project.id}/files/{inventory_project_file.id}/coverage-plan/summary")
    assert response.status_code == 404


def test_patch_module_endpoint(
    client, db_session, current_user, project, inventory_project_file, fake_coverage_plan_ai_provider
):
    _make_items(db_session, project, inventory_project_file)
    run_generation_inline(db_session, current_user, project, inventory_project_file)

    plan_response = client.get(f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/coverage-plan")
    module_id = plan_response.json()["data"]["modules"][0]["id"]

    response = client.patch(f"/api/v1/coverage-plan/modules/{module_id}", json={"title": "Novo título do módulo"})
    assert response.status_code == 200
    assert response.json()["data"]["title"] == "Novo título do módulo"


def test_add_and_remove_lesson_source_item_endpoint(
    client, db_session, current_user, project, inventory_project_file, fake_coverage_plan_ai_provider
):
    _make_items(db_session, project, inventory_project_file)
    run_generation_inline(db_session, current_user, project, inventory_project_file)

    plan_response = client.get(f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/coverage-plan")
    lesson = plan_response.json()["data"]["modules"][0]["lessons"][0]
    lesson_id = lesson["id"]

    extra_item = make_source_item(
        db_session, project, inventory_project_file, item_code="SRC-8888", title="Extra", normalized_content="conteudo extra"
    )
    db_session.commit()

    add_response = client.post(
        f"/api/v1/coverage-plan/lessons/{lesson_id}/source-items",
        json={"source_item_id": str(extra_item.id), "is_required": False},
    )
    assert add_response.status_code == 200
    assert add_response.json()["data"]["source_item_count"] == lesson["source_item_count"] + 1

    remove_response = client.request(
        "DELETE", f"/api/v1/coverage-plan/lessons/{lesson_id}/source-items/{extra_item.id}"
    )
    assert remove_response.status_code == 200
    assert remove_response.json()["data"]["source_item_count"] == lesson["source_item_count"]


# --------------------------------------------------------------------------
# POST /regenerate
# --------------------------------------------------------------------------

def test_post_regenerate_endpoint_returns_pending_job(client, db_session, project, inventory_project_file):
    _make_items(db_session, project, inventory_project_file)
    response = client.post(
        f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/coverage-plan/regenerate",
        json={"mode": "regenerate_draft"},
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["job_type"] == "coverage_plan"
    assert payload["status"] == "pending"


def test_post_regenerate_without_existing_plan_creates_first_version(
    db_session, current_user, project, inventory_project_file, fake_coverage_plan_ai_provider
):
    _make_items(db_session, project, inventory_project_file)
    run_regenerate_inline(db_session, current_user, project, inventory_project_file, mode="regenerate_draft")

    versions = svc.list_plan_versions(db_session, project.id)
    assert len(versions) == 1
    assert versions[0].version == 1


def test_post_regenerate_creates_new_version_and_preserves_previous(
    db_session, current_user, project, inventory_project_file, fake_coverage_plan_ai_provider
):
    _make_items(db_session, project, inventory_project_file)
    run_generation_inline(db_session, current_user, project, inventory_project_file)
    run_regenerate_inline(db_session, current_user, project, inventory_project_file, mode="regenerate_draft")

    versions = svc.list_plan_versions(db_session, project.id)
    assert len(versions) == 2
    assert {v.version for v in versions} == {1, 2}
    stale_version = next(v for v in versions if v.version == 1)
    assert stale_version.status == "stale"


def test_post_regenerate_conflicts_with_active_job(client, db_session, project, inventory_project_file):
    _make_items(db_session, project, inventory_project_file)
    gen_response = client.post(f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/coverage-plan/generate")
    assert gen_response.status_code == 200
    assert gen_response.json()["data"]["status"] == "pending"

    response = client.post(
        f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/coverage-plan/regenerate",
        json={"mode": "regenerate_draft"},
    )
    assert response.status_code == 409


def test_post_regenerate_isolated_between_projects(client, other_project, inventory_project_file):
    response = client.post(
        f"/api/v1/projects/{other_project.id}/files/{inventory_project_file.id}/coverage-plan/regenerate",
        json={"mode": "regenerate_draft"},
    )
    assert response.status_code == 404


# --------------------------------------------------------------------------
# GET /job
# --------------------------------------------------------------------------

def test_get_job_endpoint_existing_job_returns_status_and_progress(
    client, db_session, current_user, project, inventory_project_file
):
    _make_items(db_session, project, inventory_project_file)
    job = start_coverage_plan_generation(db_session, current_user, project.id, inventory_project_file.id)
    db_session.commit()

    response = client.get(f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/coverage-plan/job")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["id"] == str(job.id)
    assert data["job_type"] == "coverage_plan"
    assert data["status"] == "pending"
    assert "progress" in data


def test_get_job_endpoint_no_job_returns_none(client, project, inventory_project_file):
    response = client.get(f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/coverage-plan/job")
    assert response.status_code == 200
    assert response.json()["data"] is None


def test_get_job_endpoint_isolated_between_organizations(
    client, other_org_project, other_org_inventory_project_file
):
    response = client.get(
        f"/api/v1/projects/{other_org_project.id}/files/{other_org_inventory_project_file.id}/coverage-plan/job"
    )
    assert response.status_code == 404


# --------------------------------------------------------------------------
# GET /versions
# --------------------------------------------------------------------------

def test_versions_endpoint_lists_active_and_stale_versions_in_order(
    client, db_session, current_user, project, inventory_project_file, fake_coverage_plan_ai_provider
):
    _make_items(db_session, project, inventory_project_file)
    run_generation_inline(db_session, current_user, project, inventory_project_file)
    run_regenerate_inline(db_session, current_user, project, inventory_project_file, mode="regenerate_draft")

    response = client.get(f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/coverage-plan/versions")
    assert response.status_code == 200
    data = response.json()["data"]
    assert [v["version"] for v in data] == [2, 1]
    assert data[1]["status"] == "stale"
    assert data[0]["status"] in {"ready_for_review", "requires_review"}


def test_versions_endpoint_isolated_between_organizations(
    client, other_org_project, other_org_inventory_project_file
):
    response = client.get(
        f"/api/v1/projects/{other_org_project.id}/files/{other_org_inventory_project_file.id}/coverage-plan/versions"
    )
    assert response.status_code == 404


# --------------------------------------------------------------------------
# GET /versions/{version}
# --------------------------------------------------------------------------

def test_get_version_endpoint_returns_full_plan(
    client, db_session, current_user, project, inventory_project_file, fake_coverage_plan_ai_provider
):
    _make_items(db_session, project, inventory_project_file)
    run_generation_inline(db_session, current_user, project, inventory_project_file)

    response = client.get(f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/coverage-plan/versions/1")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["version"] == 1
    assert len(data["modules"]) > 0
    assert len(data["modules"][0]["lessons"]) > 0
    assert len(data["modules"][0]["lessons"][0]["source_items"]) > 0


def test_get_version_endpoint_nonexistent_version_returns_404(
    client, db_session, current_user, project, inventory_project_file, fake_coverage_plan_ai_provider
):
    _make_items(db_session, project, inventory_project_file)
    run_generation_inline(db_session, current_user, project, inventory_project_file)

    response = client.get(f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/coverage-plan/versions/99")
    assert response.status_code == 404


def test_get_version_endpoint_isolated_between_organizations(
    client, other_org_project, other_org_inventory_project_file
):
    response = client.get(
        f"/api/v1/projects/{other_org_project.id}/files/{other_org_inventory_project_file.id}/coverage-plan/versions/1"
    )
    assert response.status_code == 404


# --------------------------------------------------------------------------
# POST /recalculate
# --------------------------------------------------------------------------

def test_recalculate_endpoint_updates_plan_metrics(
    client, db_session, current_user, project, inventory_project_file, fake_coverage_plan_ai_provider
):
    _make_items(db_session, project, inventory_project_file, count=4)
    run_generation_inline(db_session, current_user, project, inventory_project_file)
    plan = svc.get_latest_plan(db_session, project.id)
    lesson = db_session.execute(
        select(CoveragePlanLesson).where(CoveragePlanLesson.coverage_plan_id == plan.id)
    ).scalars().first()

    # corrompe deliberadamente os numeros persistidos para provar que o endpoint recalcula de verdade
    lesson.estimated_word_count = 0
    lesson.estimated_duration_minutes = Decimal("0")
    db_session.add(lesson)
    db_session.commit()

    response = client.post(f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/coverage-plan/recalculate")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] in {"valid", "requires_review"}

    db_session.refresh(lesson)
    assert lesson.estimated_word_count > 0
    assert lesson.estimated_duration_minutes > Decimal("0")


def test_recalculate_endpoint_isolated_between_organizations(
    client, other_org_project, other_org_inventory_project_file
):
    response = client.post(
        f"/api/v1/projects/{other_org_project.id}/files/{other_org_inventory_project_file.id}/coverage-plan/recalculate"
    )
    assert response.status_code == 404


# --------------------------------------------------------------------------
# PATCH /coverage-plan/lessons/{id}
# --------------------------------------------------------------------------

def test_patch_lesson_endpoint_success(
    client, db_session, current_user, project, inventory_project_file, fake_coverage_plan_ai_provider
):
    _make_items(db_session, project, inventory_project_file)
    run_generation_inline(db_session, current_user, project, inventory_project_file)
    plan_response = client.get(f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/coverage-plan")
    lesson_id = plan_response.json()["data"]["modules"][0]["lessons"][0]["id"]

    response = client.patch(f"/api/v1/coverage-plan/lessons/{lesson_id}", json={"title": "Novo título da aula"})
    assert response.status_code == 200
    assert response.json()["data"]["title"] == "Novo título da aula"


def test_patch_lesson_endpoint_move_to_valid_module_in_same_plan(
    client, db_session, current_user, project, inventory_project_file, fake_coverage_plan_ai_provider
):
    _make_items(db_session, project, inventory_project_file, count=4)
    run_generation_inline(db_session, current_user, project, inventory_project_file)
    plan = svc.get_latest_plan(db_session, project.id)
    lesson = db_session.execute(
        select(CoveragePlanLesson).where(CoveragePlanLesson.coverage_plan_id == plan.id)
    ).scalars().first()

    second_module = CoveragePlanModule(
        coverage_plan_id=plan.id, project_id=project.id, title="Módulo destino", module_order=99
    )
    db_session.add(second_module)
    db_session.commit()

    response = client.patch(f"/api/v1/coverage-plan/lessons/{lesson.id}", json={"module_id": str(second_module.id)})
    assert response.status_code == 200
    assert response.json()["data"]["module_id"] == str(second_module.id)


def test_patch_lesson_endpoint_module_of_other_project_same_org_is_blocked(
    client,
    db_session,
    current_user,
    project,
    inventory_project_file,
    other_project,
    other_inventory_project_file,
    fake_coverage_plan_ai_provider,
):
    _make_items(db_session, project, inventory_project_file, count=2)
    _make_items(db_session, other_project, other_inventory_project_file, count=2)
    run_generation_inline(db_session, current_user, project, inventory_project_file)
    run_generation_inline(db_session, current_user, other_project, other_inventory_project_file)

    plan_a = svc.get_latest_plan(db_session, project.id)
    plan_b = svc.get_latest_plan(db_session, other_project.id)
    lesson_a = db_session.execute(
        select(CoveragePlanLesson).where(CoveragePlanLesson.coverage_plan_id == plan_a.id)
    ).scalars().first()
    module_b = db_session.execute(
        select(CoveragePlanModule).where(CoveragePlanModule.coverage_plan_id == plan_b.id)
    ).scalars().first()

    response = client.patch(f"/api/v1/coverage-plan/lessons/{lesson_a.id}", json={"module_id": str(module_b.id)})
    assert response.status_code == 400


def test_patch_lesson_endpoint_module_of_other_organization_is_blocked(
    client,
    db_session,
    current_user,
    project,
    inventory_project_file,
    other_org_project,
    other_org_current_user,
    other_org_inventory_project_file,
    fake_coverage_plan_ai_provider,
):
    _make_items(db_session, project, inventory_project_file, count=2)
    _make_items(db_session, other_org_project, other_org_inventory_project_file, count=2)
    run_generation_inline(db_session, current_user, project, inventory_project_file)
    run_generation_inline(db_session, other_org_current_user, other_org_project, other_org_inventory_project_file)

    plan_a = svc.get_latest_plan(db_session, project.id)
    plan_c = svc.get_latest_plan(db_session, other_org_project.id)
    lesson_a = db_session.execute(
        select(CoveragePlanLesson).where(CoveragePlanLesson.coverage_plan_id == plan_a.id)
    ).scalars().first()
    module_c = db_session.execute(
        select(CoveragePlanModule).where(CoveragePlanModule.coverage_plan_id == plan_c.id)
    ).scalars().first()

    response = client.patch(f"/api/v1/coverage-plan/lessons/{lesson_a.id}", json={"module_id": str(module_c.id)})
    assert response.status_code == 404


def test_patch_lesson_endpoint_invalid_title_returns_422(
    client, db_session, current_user, project, inventory_project_file, fake_coverage_plan_ai_provider
):
    _make_items(db_session, project, inventory_project_file)
    run_generation_inline(db_session, current_user, project, inventory_project_file)
    plan_response = client.get(f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/coverage-plan")
    lesson_id = plan_response.json()["data"]["modules"][0]["lessons"][0]["id"]

    response = client.patch(f"/api/v1/coverage-plan/lessons/{lesson_id}", json={"title": ""})
    assert response.status_code == 422


def test_patch_lesson_endpoint_nonexistent_lesson_returns_404(client):
    response = client.patch(f"/api/v1/coverage-plan/lessons/{uuid.uuid4()}", json={"title": "Qualquer"})
    assert response.status_code == 404


# --------------------------------------------------------------------------
# POST /coverage-plan/lessons/{id}/recalculate
# --------------------------------------------------------------------------

def test_recalculate_lesson_endpoint_success_updates_metrics(
    client, db_session, current_user, project, inventory_project_file, fake_coverage_plan_ai_provider
):
    _make_items(db_session, project, inventory_project_file, count=4)
    run_generation_inline(db_session, current_user, project, inventory_project_file)
    plan = svc.get_latest_plan(db_session, project.id)
    lesson = db_session.execute(
        select(CoveragePlanLesson).where(CoveragePlanLesson.coverage_plan_id == plan.id)
    ).scalars().first()
    lesson.estimated_word_count = 0
    db_session.add(lesson)
    db_session.commit()

    response = client.post(f"/api/v1/coverage-plan/lessons/{lesson.id}/recalculate")
    assert response.status_code == 200
    assert response.json()["data"]["estimated_word_count"] > 0


def test_recalculate_lesson_endpoint_nonexistent_lesson_returns_404(client):
    response = client.post(f"/api/v1/coverage-plan/lessons/{uuid.uuid4()}/recalculate")
    assert response.status_code == 404


# --------------------------------------------------------------------------
# POST /coverage-plan/lessons/{id}/split
# --------------------------------------------------------------------------

def test_split_lesson_endpoint_success_creates_two_lessons_preserving_items(
    client, db_session, current_user, project, inventory_project_file, fake_coverage_plan_ai_provider
):
    _make_items(db_session, project, inventory_project_file, count=4)
    run_generation_inline(db_session, current_user, project, inventory_project_file)
    plan_response = client.get(f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/coverage-plan")
    lesson = plan_response.json()["data"]["modules"][0]["lessons"][0]
    lesson_id = lesson["id"]
    item_ids = [item["source_item_id"] for item in lesson["source_items"]]
    assert len(item_ids) == 4

    response = client.post(
        f"/api/v1/coverage-plan/lessons/{lesson_id}/split",
        json={
            "first_title": "Primeira metade",
            "second_title": "Segunda metade",
            "first_source_item_ids": item_ids[:2],
            "second_source_item_ids": item_ids[2:],
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["first"]["source_item_count"] == 2
    assert data["second"]["source_item_count"] == 2
    assert data["first"]["title"] == "Primeira metade"
    assert data["second"]["title"] == "Segunda metade"
    assert data["second"]["lesson_order"] == data["first"]["lesson_order"] + 1

    plan_response_after = client.get(f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/coverage-plan")
    lessons_after = plan_response_after.json()["data"]["modules"][0]["lessons"]
    assert all(lesson["source_item_count"] > 0 for lesson in lessons_after)
    all_item_ids_after = {item["source_item_id"] for lesson in lessons_after for item in lesson["source_items"]}
    assert all_item_ids_after == set(item_ids)


def test_split_lesson_endpoint_rejects_missing_item(
    client, db_session, current_user, project, inventory_project_file, fake_coverage_plan_ai_provider
):
    _make_items(db_session, project, inventory_project_file, count=4)
    run_generation_inline(db_session, current_user, project, inventory_project_file)
    plan_response = client.get(f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/coverage-plan")
    lesson = plan_response.json()["data"]["modules"][0]["lessons"][0]
    lesson_id = lesson["id"]
    item_ids = [item["source_item_id"] for item in lesson["source_items"]]

    response = client.post(
        f"/api/v1/coverage-plan/lessons/{lesson_id}/split",
        json={
            "first_title": "Primeira metade",
            "second_title": "Segunda metade",
            "first_source_item_ids": item_ids[:1],
            "second_source_item_ids": item_ids[2:],
        },
    )
    assert response.status_code == 400


def test_split_lesson_endpoint_rejects_duplicate_item(
    client, db_session, current_user, project, inventory_project_file, fake_coverage_plan_ai_provider
):
    _make_items(db_session, project, inventory_project_file, count=4)
    run_generation_inline(db_session, current_user, project, inventory_project_file)
    plan_response = client.get(f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/coverage-plan")
    lesson = plan_response.json()["data"]["modules"][0]["lessons"][0]
    lesson_id = lesson["id"]
    item_ids = [item["source_item_id"] for item in lesson["source_items"]]

    response = client.post(
        f"/api/v1/coverage-plan/lessons/{lesson_id}/split",
        json={
            "first_title": "Primeira metade",
            "second_title": "Segunda metade",
            "first_source_item_ids": item_ids,
            "second_source_item_ids": item_ids[:1],
        },
    )
    assert response.status_code == 422


def test_split_lesson_endpoint_invalid_payload_returns_422(
    client, db_session, current_user, project, inventory_project_file, fake_coverage_plan_ai_provider
):
    _make_items(db_session, project, inventory_project_file, count=4)
    run_generation_inline(db_session, current_user, project, inventory_project_file)
    plan_response = client.get(f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/coverage-plan")
    lesson_id = plan_response.json()["data"]["modules"][0]["lessons"][0]["id"]

    response = client.post(
        f"/api/v1/coverage-plan/lessons/{lesson_id}/split",
        json={
            "first_title": "",
            "second_title": "Segunda",
            "first_source_item_ids": [],
            "second_source_item_ids": [],
        },
    )
    assert response.status_code == 422


def test_split_lesson_endpoint_lesson_of_other_organization_returns_404(
    client, db_session, other_org_current_user, other_org_project, other_org_inventory_project_file, fake_coverage_plan_ai_provider
):
    _make_items(db_session, other_org_project, other_org_inventory_project_file, count=4)
    run_generation_inline(db_session, other_org_current_user, other_org_project, other_org_inventory_project_file)
    plan = svc.get_latest_plan(db_session, other_org_project.id)
    lesson = db_session.execute(
        select(CoveragePlanLesson).where(CoveragePlanLesson.coverage_plan_id == plan.id)
    ).scalars().first()

    response = client.post(
        f"/api/v1/coverage-plan/lessons/{lesson.id}/split",
        json={
            "first_title": "X",
            "second_title": "Y",
            "first_source_item_ids": [str(uuid.uuid4())],
            "second_source_item_ids": [str(uuid.uuid4())],
        },
    )
    assert response.status_code == 404


# --------------------------------------------------------------------------
# POST /coverage-plan/lessons/merge
# --------------------------------------------------------------------------

def test_merge_lessons_endpoint_success_preserves_items_and_recalculates(
    client, db_session, current_user, project, inventory_project_file, fake_coverage_plan_ai_provider
):
    _make_items(db_session, project, inventory_project_file, count=8)
    run_generation_inline(db_session, current_user, project, inventory_project_file)
    plan_response = client.get(f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/coverage-plan")
    lessons = plan_response.json()["data"]["modules"][0]["lessons"]
    if len(lessons) < 2:
        pytest.skip("geracao nao produziu aulas suficientes para testar uniao bem-sucedida")
    lesson_ids = [lessons[0]["id"], lessons[1]["id"]]
    total_items_before = lessons[0]["source_item_count"] + lessons[1]["source_item_count"]

    response = client.post("/api/v1/coverage-plan/lessons/merge", json={"lesson_ids": lesson_ids, "title": "Aula Unificada"})
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["title"] == "Aula Unificada"
    assert data["source_item_count"] == total_items_before
    assert Decimal(str(data["estimated_duration_minutes"])) <= Decimal("10")

    plan_response_after = client.get(f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/coverage-plan")
    lessons_after = plan_response_after.json()["data"]["modules"][0]["lessons"]
    assert len(lessons_after) == len(lessons) - 1
    orders = [lesson["lesson_order"] for lesson in lessons_after]
    assert orders == list(range(1, len(orders) + 1))


def test_merge_lessons_endpoint_blocks_when_over_duration_limit(
    client, db_session, current_user, project, inventory_project_file, fake_coverage_plan_ai_provider
):
    for i in range(1, 21):
        make_source_item(
            db_session,
            project,
            inventory_project_file,
            item_code=f"SRC-{i:04d}",
            title=f"Item {i}",
            normalized_content=" ".join([f"palavra{i}"] * 100),
            content_type="procedure",
            source_order=i * 10,
        )
    db_session.commit()
    run_generation_inline(db_session, current_user, project, inventory_project_file)
    plan_response = client.get(f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/coverage-plan")
    lessons = plan_response.json()["data"]["modules"][0]["lessons"]
    if len(lessons) < 2:
        pytest.skip("geracao nao produziu aulas suficientes para testar bloqueio de uniao")

    response = client.post(
        "/api/v1/coverage-plan/lessons/merge",
        json={"lesson_ids": [lessons[0]["id"], lessons[1]["id"]], "title": "X"},
    )
    assert response.status_code == 400


def test_merge_lessons_endpoint_blocks_different_modules(
    client, db_session, current_user, project, inventory_project_file, fake_coverage_plan_ai_provider
):
    _make_items(db_session, project, inventory_project_file, count=4)
    run_generation_inline(db_session, current_user, project, inventory_project_file)
    plan = svc.get_latest_plan(db_session, project.id)
    lesson = db_session.execute(
        select(CoveragePlanLesson).where(CoveragePlanLesson.coverage_plan_id == plan.id)
    ).scalars().first()

    other_module = CoveragePlanModule(
        coverage_plan_id=plan.id, project_id=project.id, title="Outro módulo", module_order=2
    )
    db_session.add(other_module)
    db_session.commit()
    other_lesson = CoveragePlanLesson(
        coverage_plan_id=plan.id, module_id=other_module.id, title="Aula em outro módulo", lesson_order=1
    )
    db_session.add(other_lesson)
    db_session.commit()

    response = client.post(
        "/api/v1/coverage-plan/lessons/merge",
        json={"lesson_ids": [str(lesson.id), str(other_lesson.id)], "title": "X"},
    )
    assert response.status_code == 400


def test_merge_lessons_endpoint_nonexistent_lesson_returns_404(
    client, db_session, current_user, project, inventory_project_file, fake_coverage_plan_ai_provider
):
    _make_items(db_session, project, inventory_project_file, count=4)
    run_generation_inline(db_session, current_user, project, inventory_project_file)
    plan_response = client.get(f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/coverage-plan")
    lesson_id = plan_response.json()["data"]["modules"][0]["lessons"][0]["id"]

    response = client.post(
        "/api/v1/coverage-plan/lessons/merge",
        json={"lesson_ids": [lesson_id, str(uuid.uuid4())], "title": "X"},
    )
    assert response.status_code == 404


def test_merge_lessons_endpoint_organizations_different_returns_404(
    client,
    db_session,
    current_user,
    project,
    inventory_project_file,
    other_org_current_user,
    other_org_project,
    other_org_inventory_project_file,
    fake_coverage_plan_ai_provider,
):
    _make_items(db_session, project, inventory_project_file, count=4)
    _make_items(db_session, other_org_project, other_org_inventory_project_file, count=4)
    run_generation_inline(db_session, current_user, project, inventory_project_file)
    run_generation_inline(db_session, other_org_current_user, other_org_project, other_org_inventory_project_file)

    plan_a = svc.get_latest_plan(db_session, project.id)
    plan_c = svc.get_latest_plan(db_session, other_org_project.id)
    lesson_a = db_session.execute(
        select(CoveragePlanLesson).where(CoveragePlanLesson.coverage_plan_id == plan_a.id)
    ).scalars().first()
    lesson_c = db_session.execute(
        select(CoveragePlanLesson).where(CoveragePlanLesson.coverage_plan_id == plan_c.id)
    ).scalars().first()

    response = client.post(
        "/api/v1/coverage-plan/lessons/merge",
        json={"lesson_ids": [str(lesson_a.id), str(lesson_c.id)], "title": "X"},
    )
    assert response.status_code == 404


# --------------------------------------------------------------------------
# Source items via HTTP: isolamento e protecoes adicionais
# --------------------------------------------------------------------------

def test_add_lesson_source_item_endpoint_item_from_other_project_is_blocked(
    client,
    db_session,
    current_user,
    project,
    inventory_project_file,
    other_project,
    other_inventory_project_file,
    fake_coverage_plan_ai_provider,
):
    _make_items(db_session, project, inventory_project_file, count=2)
    other_item = make_source_item(
        db_session,
        other_project,
        other_inventory_project_file,
        item_code="SRC-OTHERPROJ-0001",
        title="Item de outro projeto",
        normalized_content="conteudo de outro projeto do mesmo tenant",
    )
    db_session.commit()
    run_generation_inline(db_session, current_user, project, inventory_project_file)
    plan_response = client.get(f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/coverage-plan")
    lesson_id = plan_response.json()["data"]["modules"][0]["lessons"][0]["id"]

    response = client.post(
        f"/api/v1/coverage-plan/lessons/{lesson_id}/source-items", json={"source_item_id": str(other_item.id)}
    )
    assert response.status_code == 400


def test_add_lesson_source_item_endpoint_item_from_other_organization_is_blocked(
    client,
    db_session,
    current_user,
    project,
    inventory_project_file,
    other_org_project,
    other_org_inventory_project_file,
    fake_coverage_plan_ai_provider,
):
    _make_items(db_session, project, inventory_project_file, count=2)
    foreign_item = make_source_item(
        db_session,
        other_org_project,
        other_org_inventory_project_file,
        item_code="SRC-FOREIGNORG-0001",
        title="Item de outra organização",
        normalized_content="conteudo de outra organizacao",
    )
    db_session.commit()
    run_generation_inline(db_session, current_user, project, inventory_project_file)
    plan_response = client.get(f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/coverage-plan")
    lesson_id = plan_response.json()["data"]["modules"][0]["lessons"][0]["id"]

    response = client.post(
        f"/api/v1/coverage-plan/lessons/{lesson_id}/source-items", json={"source_item_id": str(foreign_item.id)}
    )
    assert response.status_code == 404


def test_remove_lesson_source_item_endpoint_blocks_last_item(
    client, db_session, current_user, project, inventory_project_file, fake_coverage_plan_ai_provider
):
    _make_items(db_session, project, inventory_project_file, count=1)
    run_generation_inline(db_session, current_user, project, inventory_project_file)
    plan_response = client.get(f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/coverage-plan")
    lesson = plan_response.json()["data"]["modules"][0]["lessons"][0]
    item_id = lesson["source_items"][0]["source_item_id"]

    response = client.request("DELETE", f"/api/v1/coverage-plan/lessons/{lesson['id']}/source-items/{item_id}")
    assert response.status_code == 400


def test_remove_lesson_source_item_endpoint_blocks_orphaning_required_item(
    client, db_session, current_user, project, inventory_project_file, fake_coverage_plan_ai_provider
):
    _make_items(db_session, project, inventory_project_file, count=4)
    run_generation_inline(db_session, current_user, project, inventory_project_file)
    plan_response = client.get(f"/api/v1/projects/{project.id}/files/{inventory_project_file.id}/coverage-plan")
    lesson = plan_response.json()["data"]["modules"][0]["lessons"][0]
    lesson_id = lesson["id"]

    extra_item = make_source_item(
        db_session, project, inventory_project_file, item_code="SRC-6666", title="Extra", normalized_content="conteudo extra"
    )
    db_session.commit()
    extra_add = client.post(
        f"/api/v1/coverage-plan/lessons/{lesson_id}/source-items",
        json={"source_item_id": str(extra_item.id), "is_required": False},
    )
    assert extra_add.status_code == 200

    # remove um item obrigatorio original: a aula tem outros itens (nao e o ultimo),
    # mas este item especifico nao tem nenhum outro destino no plano -> bloqueado
    required_item_id = lesson["source_items"][0]["source_item_id"]
    response = client.request(
        "DELETE", f"/api/v1/coverage-plan/lessons/{lesson_id}/source-items/{required_item_id}"
    )
    assert response.status_code == 400
