"""Testes do servico de geracao individual das aulas (fase 19.5). Segue o mesmo
padrao de test_coverage_plan_service.py: o job real abre SessionLocal() propria,
entao os testes chamam start_*() e generate_lesson()/generate_all_lessons()
diretamente na mesma sessao transacional (com fake_lesson_generation_ai_provider),
sem passar pelo BackgroundTasks."""

from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.coverage_plan_lesson import CoveragePlanLesson
from app.models.document_page import DocumentPage
from app.models.lesson_source_item import LessonSourceItem
from app.services import lesson_generation_service as svc
from tests.conftest import make_source_item


def run_generation_inline(db_session, current_user, lesson_id, *, force=False):
    job = svc.start_lesson_generation(db_session, current_user, lesson_id, force=force)
    if job.status == "pending":
        svc.generate_lesson(db_session, current_user, job)
        db_session.commit()
    return job


def run_regeneration_inline(db_session, current_user, lesson_id, *, mode="regenerate", feedback=None):
    job = svc.start_lesson_regeneration(db_session, current_user, lesson_id, mode=mode, feedback=feedback)
    svc.generate_lesson(db_session, current_user, job)
    db_session.commit()
    return job


def run_repair_inline(db_session, current_user, lesson, plan, generation, *, missing_source_item_ids, notes=None):
    job = svc.start_repair_missing_items(
        db_session, current_user, lesson, plan, generation,
        missing_source_item_ids=missing_source_item_ids, validation_notes=notes,
    )
    svc.generate_lesson(db_session, current_user, job)
    db_session.commit()
    return job


# --------------------------------------------------------------------------
# Geracao simples
# --------------------------------------------------------------------------

def test_generate_lesson_simple_completed(db_session, current_user, coverage_plan_lesson_ready, fake_lesson_generation_ai_provider):
    lesson = coverage_plan_lesson_ready["lesson"]
    job = run_generation_inline(db_session, current_user, lesson.id)

    assert job.status == "completed"
    generation = svc.get_latest_generation(db_session, lesson.id)
    assert generation is not None
    assert generation.version == 1
    assert generation.generation_status == "completed"
    assert generation.validation_status == "valid"
    assert generation.word_count > 0
    assert generation.estimated_duration_seconds > 0
    assert generation.source_item_count == 3
    covered_codes = {c["item_code"] for c in generation.covered_source_items_json}
    assert covered_codes == {"SRC-0001", "SRC-0002", "SRC-0003"}
    assert generation.uncovered_source_items_json == []
    assert generation.requires_split is False


def test_generate_lesson_single_item(db_session, current_user, project, project_file, fake_lesson_generation_ai_provider):
    from app.models.coverage_plan import CoveragePlan
    from app.models.coverage_plan_module import CoveragePlanModule

    plan = CoveragePlan(project_id=project.id, project_file_id=project_file.id, version=1, status="ready_for_review")
    db_session.add(plan)
    db_session.flush()
    module = CoveragePlanModule(coverage_plan_id=plan.id, project_id=project.id, title="M1", module_order=1, plan_version=1)
    db_session.add(module)
    db_session.flush()
    lesson = CoveragePlanLesson(
        coverage_plan_id=plan.id, module_id=module.id, title="Aula única", lesson_order=1,
        estimated_duration_minutes=Decimal("1"), source_item_count=1, plan_version=1,
    )
    db_session.add(lesson)
    db_session.flush()
    item = make_source_item(
        db_session, project, project_file, item_code="SRC-0001", title="Único conceito",
        normalized_content="Conteúdo único desta aula com um único item.",
    )
    db_session.add(LessonSourceItem(coverage_plan_lesson_id=lesson.id, source_item_id=item.id, source_order_in_lesson=1, is_required=True))
    db_session.flush()

    job = run_generation_inline(db_session, current_user, lesson.id)
    assert job.status == "completed"
    generation = svc.get_latest_generation(db_session, lesson.id)
    assert generation.source_item_count == 1
    assert {c["item_code"] for c in generation.covered_source_items_json} == {"SRC-0001"}


def test_generate_lesson_preserves_pedagogical_order(db_session, current_user, coverage_plan_lesson_ready, fake_lesson_generation_ai_provider):
    lesson = coverage_plan_lesson_ready["lesson"]
    run_generation_inline(db_session, current_user, lesson.id)

    prompt = fake_lesson_generation_ai_provider["calls"][0].user_prompt
    assert prompt.index("SRC-0001") < prompt.index("SRC-0002") < prompt.index("SRC-0003")


def test_missing_required_item_marks_requires_review(db_session, current_user, coverage_plan_lesson_ready, fake_lesson_generation_ai_provider):
    from tests.conftest import default_lesson_script_ai_response

    def _missing_required(user_prompt: str) -> dict:
        payload = default_lesson_script_ai_response(user_prompt)
        payload["covered_source_items"] = [c for c in payload["covered_source_items"] if c["source_item_id"] != "SRC-0002"]
        return payload

    fake_lesson_generation_ai_provider["response_override"] = _missing_required
    lesson = coverage_plan_lesson_ready["lesson"]
    job = run_generation_inline(db_session, current_user, lesson.id)

    generation = svc.get_latest_generation(db_session, lesson.id)
    assert generation.generation_status == "requires_review"
    assert generation.validation_status == "invalid"
    assert "SRC-0002" in generation.uncovered_source_items_json
    assert job.result_json["generation_status"] == "requires_review"


def test_complementary_item_not_required_can_be_absent_without_blocking(db_session, current_user, coverage_plan_lesson_ready, fake_lesson_generation_ai_provider):
    from tests.conftest import default_lesson_script_ai_response

    def _skip_optional(user_prompt: str) -> dict:
        payload = default_lesson_script_ai_response(user_prompt)
        payload["covered_source_items"] = [c for c in payload["covered_source_items"] if c["source_item_id"] != "SRC-0003"]
        return payload

    fake_lesson_generation_ai_provider["response_override"] = _skip_optional
    lesson = coverage_plan_lesson_ready["lesson"]
    run_generation_inline(db_session, current_user, lesson.id)

    generation = svc.get_latest_generation(db_session, lesson.id)
    # SRC-0003 nao e obrigatorio: pode ficar ausente sem impedir a conclusao.
    assert generation.generation_status == "completed"
    assert generation.validation_status == "valid"
    assert "SRC-0003" in generation.uncovered_source_items_json


def test_extra_source_item_declared_by_ai_is_rejected(db_session, current_user, coverage_plan_lesson_ready, fake_lesson_generation_ai_provider):
    from tests.conftest import default_lesson_script_ai_response

    def _extra_item(user_prompt: str) -> dict:
        payload = default_lesson_script_ai_response(user_prompt)
        payload["covered_source_items"].append(
            {"source_item_id": "SRC-9999", "coverage_description": "item de fora", "coverage_type": "full"}
        )
        return payload

    fake_lesson_generation_ai_provider["response_override"] = _extra_item
    lesson = coverage_plan_lesson_ready["lesson"]
    run_generation_inline(db_session, current_user, lesson.id)

    generation = svc.get_latest_generation(db_session, lesson.id)
    assert generation.generation_status == "requires_review"
    assert generation.validation_status == "invalid"
    assert all(c["item_code"] != "SRC-9999" for c in generation.covered_source_items_json)


def test_ai_invalid_response_marks_generation_failed(db_session, current_user, coverage_plan_lesson_ready, fake_lesson_generation_ai_provider):
    def _broken(user_prompt: str) -> dict:
        return {"lesson_title": "x", "generation_status": "completed", "target_duration_minutes": 5, "estimated_duration_minutes": 5, "word_count": 0, "script": ""}

    fake_lesson_generation_ai_provider["response_override"] = _broken
    lesson = coverage_plan_lesson_ready["lesson"]
    job = run_generation_inline(db_session, current_user, lesson.id)

    assert job.status == "failed"
    generation = svc.get_latest_generation(db_session, lesson.id)
    assert generation.generation_status == "failed"
    assert generation.validation_status == "invalid"
    assert generation.error_message


# --------------------------------------------------------------------------
# Precondicoes bloqueantes
# --------------------------------------------------------------------------

def test_lesson_without_source_items_blocks_generation(db_session, current_user, project, project_file):
    from app.models.coverage_plan import CoveragePlan
    from app.models.coverage_plan_module import CoveragePlanModule

    plan = CoveragePlan(project_id=project.id, project_file_id=project_file.id, version=1, status="ready_for_review")
    db_session.add(plan)
    db_session.flush()
    module = CoveragePlanModule(coverage_plan_id=plan.id, project_id=project.id, title="M1", module_order=1, plan_version=1)
    db_session.add(module)
    db_session.flush()
    lesson = CoveragePlanLesson(coverage_plan_id=plan.id, module_id=module.id, title="Aula vazia", lesson_order=1, plan_version=1)
    db_session.add(lesson)
    db_session.flush()

    with pytest.raises(HTTPException) as exc_info:
        svc.start_lesson_generation(db_session, current_user, lesson.id)
    assert exc_info.value.status_code == 400


def test_stale_plan_blocks_generation(db_session, current_user, coverage_plan_lesson_ready):
    plan = coverage_plan_lesson_ready["plan"]
    lesson = coverage_plan_lesson_ready["lesson"]
    plan.status = "stale"
    db_session.add(plan)
    db_session.flush()

    with pytest.raises(HTTPException) as exc_info:
        svc.start_lesson_generation(db_session, current_user, lesson.id)
    assert exc_info.value.status_code == 400


def test_ocr_pending_blocks_generation(db_session, current_user, coverage_plan_lesson_ready, project_file):
    lesson = coverage_plan_lesson_ready["lesson"]
    db_session.add(DocumentPage(project_file_id=project_file.id, page_number=1, requires_ocr=True, extraction_status="extracted"))
    db_session.flush()

    with pytest.raises(HTTPException) as exc_info:
        svc.start_lesson_generation(db_session, current_user, lesson.id)
    assert exc_info.value.status_code == 400
    assert "OCR" in exc_info.value.detail


def test_failed_page_blocks_generation(db_session, current_user, coverage_plan_lesson_ready, project_file):
    lesson = coverage_plan_lesson_ready["lesson"]
    db_session.add(DocumentPage(project_file_id=project_file.id, page_number=1, requires_ocr=False, extraction_status="failed"))
    db_session.flush()

    with pytest.raises(HTTPException) as exc_info:
        svc.start_lesson_generation(db_session, current_user, lesson.id)
    assert exc_info.value.status_code == 400
    assert "falha de extração" in exc_info.value.detail


def test_lesson_over_duration_limit_blocks_generation(db_session, current_user, coverage_plan_lesson_ready):
    lesson = coverage_plan_lesson_ready["lesson"]
    lesson.estimated_duration_minutes = Decimal("11")
    db_session.add(lesson)
    db_session.flush()

    with pytest.raises(HTTPException) as exc_info:
        svc.start_lesson_generation(db_session, current_user, lesson.id)
    assert exc_info.value.status_code == 400
    assert "dividida" in exc_info.value.detail


def test_rejected_source_item_blocks_generation(db_session, current_user, coverage_plan_lesson_ready):
    item = coverage_plan_lesson_ready["items"][0]
    item.status = "rejected"
    db_session.add(item)
    db_session.flush()

    with pytest.raises(HTTPException) as exc_info:
        svc.start_lesson_generation(db_session, current_user, coverage_plan_lesson_ready["lesson"].id)
    assert exc_info.value.status_code == 400


# --------------------------------------------------------------------------
# Duracao / requires_split
# --------------------------------------------------------------------------

def test_requires_split_declared_by_ai(db_session, current_user, coverage_plan_lesson_ready, fake_lesson_generation_ai_provider):
    from tests.conftest import default_lesson_script_ai_response

    def _split(user_prompt: str) -> dict:
        payload = default_lesson_script_ai_response(user_prompt)
        payload["generation_status"] = "requires_split"
        payload["requires_split"] = True
        payload["split_reason"] = "Conteúdo excede o limite de 10 minutos mesmo sem cortes."
        return payload

    fake_lesson_generation_ai_provider["response_override"] = _split
    lesson = coverage_plan_lesson_ready["lesson"]
    run_generation_inline(db_session, current_user, lesson.id)

    generation = svc.get_latest_generation(db_session, lesson.id)
    assert generation.generation_status == "requires_split"
    assert generation.requires_split is True
    assert generation.split_reason


def test_requires_split_when_word_count_exceeds_limit(db_session, current_user, coverage_plan_lesson_ready, fake_lesson_generation_ai_provider):
    from tests.conftest import default_lesson_script_ai_response

    def _huge_script(user_prompt: str) -> dict:
        payload = default_lesson_script_ai_response(user_prompt)
        long_text = " ".join(["palavra"] * 1400)
        payload["script"] = f"{payload['opening']} {long_text} {payload['closing']}"
        payload["development"] = long_text
        return payload

    fake_lesson_generation_ai_provider["response_override"] = _huge_script
    lesson = coverage_plan_lesson_ready["lesson"]
    run_generation_inline(db_session, current_user, lesson.id)

    generation = svc.get_latest_generation(db_session, lesson.id)
    assert generation.requires_split is True
    assert generation.generation_status == "requires_split"
    assert generation.word_count > 1300
    # nunca trunca: o script completo continua persistido integralmente
    assert generation.generated_content is not None
    assert len(generation.generated_content.split()) == generation.word_count


def test_word_count_and_duration_calculated_in_backend(db_session, current_user, coverage_plan_lesson_ready, fake_lesson_generation_ai_provider):
    lesson = coverage_plan_lesson_ready["lesson"]
    run_generation_inline(db_session, current_user, lesson.id)
    generation = svc.get_latest_generation(db_session, lesson.id)

    expected_words = len(generation.generated_content.split())
    assert generation.word_count == expected_words
    expected_seconds = int(round(expected_words / 130 * 60))
    assert abs(generation.estimated_duration_seconds - expected_seconds) <= 1


# --------------------------------------------------------------------------
# Versionamento / fingerprint / stale
# --------------------------------------------------------------------------

def test_versioning_first_generation_is_version_1(db_session, current_user, coverage_plan_lesson_ready, fake_lesson_generation_ai_provider):
    lesson = coverage_plan_lesson_ready["lesson"]
    run_generation_inline(db_session, current_user, lesson.id)
    generation = svc.get_latest_generation(db_session, lesson.id)
    assert generation.version == 1


def test_regenerate_creates_version_2_and_preserves_version_1(db_session, current_user, coverage_plan_lesson_ready, fake_lesson_generation_ai_provider):
    lesson = coverage_plan_lesson_ready["lesson"]
    run_generation_inline(db_session, current_user, lesson.id)
    run_regeneration_inline(db_session, current_user, lesson.id)

    generations = svc.list_generations(db_session, lesson.id)
    versions = sorted(g.version for g in generations)
    assert versions == [1, 2]
    latest = svc.get_latest_generation(db_session, lesson.id)
    assert latest.version == 2


def test_source_fingerprint_changes_when_item_content_changes(db_session, current_user, coverage_plan_lesson_ready, fake_lesson_generation_ai_provider):
    lesson = coverage_plan_lesson_ready["lesson"]
    run_generation_inline(db_session, current_user, lesson.id)
    v1 = svc.get_latest_generation(db_session, lesson.id)
    assert v1.is_stale is False

    item = coverage_plan_lesson_ready["items"][0]
    item.normalized_content = "Conteúdo totalmente alterado depois da primeira geração."
    db_session.add(item)
    db_session.commit()

    run_regeneration_inline(db_session, current_user, lesson.id)

    db_session.refresh(v1)
    assert v1.is_stale is True
    v2 = svc.get_latest_generation(db_session, lesson.id)
    assert v2.version == 2
    assert v2.source_fingerprint != v1.source_fingerprint


def test_generate_if_missing_reuses_up_to_date_generation(db_session, current_user, coverage_plan_lesson_ready, fake_lesson_generation_ai_provider):
    lesson = coverage_plan_lesson_ready["lesson"]
    run_generation_inline(db_session, current_user, lesson.id)
    assert len(fake_lesson_generation_ai_provider["calls"]) == 1

    run_generation_inline(db_session, current_user, lesson.id, force=False)
    # fingerprint inalterado: nao deve chamar a IA de novo, nem criar nova versao
    assert len(fake_lesson_generation_ai_provider["calls"]) == 1
    generations = svc.list_generations(db_session, lesson.id)
    assert len(generations) == 1


def test_generate_if_missing_creates_new_version_when_stale(db_session, current_user, coverage_plan_lesson_ready, fake_lesson_generation_ai_provider):
    lesson = coverage_plan_lesson_ready["lesson"]
    run_generation_inline(db_session, current_user, lesson.id)

    item = coverage_plan_lesson_ready["items"][0]
    item.normalized_content = "Conteúdo alterado para forçar nova versão."
    db_session.add(item)
    db_session.commit()

    run_generation_inline(db_session, current_user, lesson.id, force=False)
    generations = svc.list_generations(db_session, lesson.id)
    assert len(generations) == 2


# --------------------------------------------------------------------------
# Jobs duplicados
# --------------------------------------------------------------------------

def test_duplicate_active_job_is_reused_by_generate(db_session, current_user, coverage_plan_lesson_ready):
    lesson = coverage_plan_lesson_ready["lesson"]
    job1 = svc.start_lesson_generation(db_session, current_user, lesson.id)
    job2 = svc.start_lesson_generation(db_session, current_user, lesson.id)
    assert job1.id == job2.id


def test_duplicate_active_job_blocks_regenerate(db_session, current_user, coverage_plan_lesson_ready):
    lesson = coverage_plan_lesson_ready["lesson"]
    svc.start_lesson_generation(db_session, current_user, lesson.id)

    with pytest.raises(HTTPException) as exc_info:
        svc.start_lesson_regeneration(db_session, current_user, lesson.id)
    assert exc_info.value.status_code == 409


# --------------------------------------------------------------------------
# Reparo de item ausente
# --------------------------------------------------------------------------

def test_repair_missing_items_covers_the_gap(db_session, current_user, coverage_plan_lesson_ready, fake_lesson_generation_ai_provider):
    from tests.conftest import default_lesson_script_ai_response

    def _missing_required(user_prompt: str) -> dict:
        payload = default_lesson_script_ai_response(user_prompt)
        payload["covered_source_items"] = [c for c in payload["covered_source_items"] if c["source_item_id"] != "SRC-0002"]
        return payload

    fake_lesson_generation_ai_provider["response_override"] = _missing_required
    lesson = coverage_plan_lesson_ready["lesson"]
    plan = coverage_plan_lesson_ready["plan"]
    run_generation_inline(db_session, current_user, lesson.id)
    v1 = svc.get_latest_generation(db_session, lesson.id)
    assert v1.generation_status == "requires_review"

    missing_item = next(i for i in coverage_plan_lesson_ready["items"] if i.item_code == "SRC-0002")
    fake_lesson_generation_ai_provider["response_override"] = None
    run_repair_inline(db_session, current_user, lesson, plan, v1, missing_source_item_ids=[missing_item.id])

    v2 = svc.get_latest_generation(db_session, lesson.id)
    assert v2.version == 2
    assert v2.generation_status == "completed"
    assert "SRC-0002" in {c["item_code"] for c in v2.covered_source_items_json}


def test_repair_missing_items_rejects_id_outside_lesson(db_session, current_user, coverage_plan_lesson_ready, fake_lesson_generation_ai_provider):
    lesson = coverage_plan_lesson_ready["lesson"]
    plan = coverage_plan_lesson_ready["plan"]
    run_generation_inline(db_session, current_user, lesson.id)
    v1 = svc.get_latest_generation(db_session, lesson.id)

    with pytest.raises(HTTPException) as exc_info:
        svc.start_repair_missing_items(
            db_session, current_user, lesson, plan, v1, missing_source_item_ids=[uuid4()], validation_notes=None
        )
    assert exc_info.value.status_code == 400


# --------------------------------------------------------------------------
# Edicao humana
# --------------------------------------------------------------------------

def test_manual_edit_creates_new_version(db_session, current_user, coverage_plan_lesson_ready, fake_lesson_generation_ai_provider):
    lesson = coverage_plan_lesson_ready["lesson"]
    plan = coverage_plan_lesson_ready["plan"]
    run_generation_inline(db_session, current_user, lesson.id)

    edited = svc.edit_generation_manual(db_session, current_user, lesson, plan, "Roteiro editado manualmente pelo revisor.")
    assert edited.version == 2
    assert edited.is_manual_edit is True
    assert edited.generation_status == "requires_review"

    v1 = svc.get_generation_by_version(db_session, lesson.id, 1)
    assert v1.generated_content != edited.generated_content


def test_manual_edit_over_limit_marks_requires_split(db_session, current_user, coverage_plan_lesson_ready, fake_lesson_generation_ai_provider):
    lesson = coverage_plan_lesson_ready["lesson"]
    plan = coverage_plan_lesson_ready["plan"]
    run_generation_inline(db_session, current_user, lesson.id)

    huge_text = " ".join(["palavra"] * 1400)
    edited = svc.edit_generation_manual(db_session, current_user, lesson, plan, huge_text)
    assert edited.requires_split is True


# --------------------------------------------------------------------------
# Aprovacao / rejeicao
# --------------------------------------------------------------------------

def test_approve_generation_success(db_session, current_user, coverage_plan_lesson_ready, fake_lesson_generation_ai_provider):
    lesson = coverage_plan_lesson_ready["lesson"]
    plan = coverage_plan_lesson_ready["plan"]
    run_generation_inline(db_session, current_user, lesson.id)
    generation = svc.get_latest_generation(db_session, lesson.id)

    approved = svc.approve_generation(db_session, current_user, lesson, plan, generation)
    assert approved.generation_status == "approved"
    assert approved.approved_at is not None
    assert approved.approved_by == current_user.id
    db_session.refresh(lesson)
    assert lesson.status == "approved"


def test_approve_generation_blocked_when_requires_split(db_session, current_user, coverage_plan_lesson_ready, fake_lesson_generation_ai_provider):
    from tests.conftest import default_lesson_script_ai_response

    def _split(user_prompt: str) -> dict:
        payload = default_lesson_script_ai_response(user_prompt)
        payload["generation_status"] = "requires_split"
        payload["requires_split"] = True
        payload["split_reason"] = "excede o limite"
        return payload

    fake_lesson_generation_ai_provider["response_override"] = _split
    lesson = coverage_plan_lesson_ready["lesson"]
    plan = coverage_plan_lesson_ready["plan"]
    run_generation_inline(db_session, current_user, lesson.id)
    generation = svc.get_latest_generation(db_session, lesson.id)

    with pytest.raises(HTTPException) as exc_info:
        svc.approve_generation(db_session, current_user, lesson, plan, generation)
    assert exc_info.value.status_code == 400


def test_approve_generation_blocked_when_stale(db_session, current_user, coverage_plan_lesson_ready, fake_lesson_generation_ai_provider):
    lesson = coverage_plan_lesson_ready["lesson"]
    plan = coverage_plan_lesson_ready["plan"]
    run_generation_inline(db_session, current_user, lesson.id)
    generation = svc.get_latest_generation(db_session, lesson.id)

    item = coverage_plan_lesson_ready["items"][0]
    item.normalized_content = "Conteúdo mudou depois da geração, antes da aprovação."
    db_session.add(item)
    db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        svc.approve_generation(db_session, current_user, lesson, plan, generation)
    assert exc_info.value.status_code == 400


def test_reject_generation(db_session, current_user, coverage_plan_lesson_ready, fake_lesson_generation_ai_provider):
    lesson = coverage_plan_lesson_ready["lesson"]
    run_generation_inline(db_session, current_user, lesson.id)
    generation = svc.get_latest_generation(db_session, lesson.id)

    rejected = svc.reject_generation(db_session, current_user, generation, "Conteúdo não ficou claro o suficiente.")
    assert rejected.generation_status == "rejected"
    assert rejected.rejected_by == current_user.id
    assert rejected.rejection_reason == "Conteúdo não ficou claro o suficiente."


def test_only_one_approved_version_per_lesson(db_session, current_user, coverage_plan_lesson_ready, fake_lesson_generation_ai_provider):
    lesson = coverage_plan_lesson_ready["lesson"]
    plan = coverage_plan_lesson_ready["plan"]
    run_generation_inline(db_session, current_user, lesson.id)
    v1 = svc.get_latest_generation(db_session, lesson.id)
    svc.approve_generation(db_session, current_user, lesson, plan, v1)

    run_regeneration_inline(db_session, current_user, lesson.id)
    v2 = svc.get_latest_generation(db_session, lesson.id)
    svc.approve_generation(db_session, current_user, lesson, plan, v2)

    db_session.refresh(v1)
    assert v1.generation_status == "completed"
    assert v2.generation_status == "approved"


# --------------------------------------------------------------------------
# Geracao em lote
# --------------------------------------------------------------------------

def _make_second_lesson(db_session, project, project_file, plan, module, *, item_code="SRC-1001"):
    lesson = CoveragePlanLesson(
        coverage_plan_id=plan.id, module_id=module.id, title="Segunda Aula", lesson_order=2,
        estimated_duration_minutes=Decimal("2"), source_item_count=1, plan_version=1,
    )
    db_session.add(lesson)
    db_session.flush()
    item = make_source_item(
        db_session, project, project_file, item_code=item_code, title="Item da segunda aula",
        normalized_content="Conteúdo exclusivo da segunda aula do lote de teste.",
    )
    db_session.add(LessonSourceItem(coverage_plan_lesson_id=lesson.id, source_item_id=item.id, source_order_in_lesson=1, is_required=True))
    db_session.flush()
    return lesson, item


def test_batch_generation_processes_all_lessons(db_session, current_user, coverage_plan_lesson_ready, project, project_file, fake_lesson_generation_ai_provider):
    plan = coverage_plan_lesson_ready["plan"]
    module = coverage_plan_lesson_ready["module"]
    second_lesson, _item = _make_second_lesson(db_session, project, project_file, plan, module)

    job = svc.start_course_lesson_generation(db_session, current_user, project.id)
    svc.generate_all_lessons(db_session, current_user, job)
    db_session.commit()

    assert job.status == "completed"
    assert job.result_json["completed_lessons"] == 2
    assert job.result_json["failed_lessons"] == 0
    assert svc.get_latest_generation(db_session, coverage_plan_lesson_ready["lesson"].id) is not None
    assert svc.get_latest_generation(db_session, second_lesson.id) is not None


def test_batch_generation_partial_failure_does_not_stop_others(db_session, current_user, coverage_plan_lesson_ready, project, project_file, fake_lesson_generation_ai_provider):
    plan = coverage_plan_lesson_ready["plan"]
    module = coverage_plan_lesson_ready["module"]
    second_lesson, _item = _make_second_lesson(db_session, project, project_file, plan, module, item_code="SRC-1002")

    def _fail_second_lesson(user_prompt: str) -> dict:
        if "SRC-1002" in user_prompt:
            return {"lesson_title": "x", "generation_status": "completed", "target_duration_minutes": 5, "estimated_duration_minutes": 5, "word_count": 0, "script": ""}
        from tests.conftest import default_lesson_script_ai_response
        return default_lesson_script_ai_response(user_prompt)

    fake_lesson_generation_ai_provider["response_override"] = _fail_second_lesson

    job = svc.start_course_lesson_generation(db_session, current_user, project.id)
    svc.generate_all_lessons(db_session, current_user, job)
    db_session.commit()

    assert job.status == "completed_with_errors"
    assert job.result_json["completed_lessons"] == 1
    assert job.result_json["failed_lessons"] == 1
    assert svc.get_latest_generation(db_session, coverage_plan_lesson_ready["lesson"].id).generation_status == "completed"
    assert svc.get_latest_generation(db_session, second_lesson.id).generation_status == "failed"


def test_batch_generation_skips_approved_lessons_without_force(db_session, current_user, coverage_plan_lesson_ready, project, project_file, fake_lesson_generation_ai_provider):
    plan = coverage_plan_lesson_ready["plan"]
    module = coverage_plan_lesson_ready["module"]
    lesson = coverage_plan_lesson_ready["lesson"]
    run_generation_inline(db_session, current_user, lesson.id)
    v1 = svc.get_latest_generation(db_session, lesson.id)
    svc.approve_generation(db_session, current_user, lesson, plan, v1)

    second_lesson, _item = _make_second_lesson(db_session, project, project_file, plan, module, item_code="SRC-1003")

    job = svc.start_course_lesson_generation(db_session, current_user, project.id)
    svc.generate_all_lessons(db_session, current_user, job)
    db_session.commit()

    assert job.result_json["skipped_lessons"] >= 1
    assert job.result_json["approved_lessons"] == 1
    # a aula aprovada continua na versao 1 (nao foi regenerada silenciosamente)
    generations = svc.list_generations(db_session, lesson.id)
    assert len(generations) == 1


def test_retry_failed_only_reprocesses_failures(db_session, current_user, coverage_plan_lesson_ready, project, project_file, fake_lesson_generation_ai_provider):
    plan = coverage_plan_lesson_ready["plan"]
    module = coverage_plan_lesson_ready["module"]
    second_lesson, _item = _make_second_lesson(db_session, project, project_file, plan, module, item_code="SRC-1004")

    def _fail_second_lesson(user_prompt: str) -> dict:
        if "SRC-1004" in user_prompt:
            return {"lesson_title": "x", "generation_status": "completed", "target_duration_minutes": 5, "estimated_duration_minutes": 5, "word_count": 0, "script": ""}
        from tests.conftest import default_lesson_script_ai_response
        return default_lesson_script_ai_response(user_prompt)

    fake_lesson_generation_ai_provider["response_override"] = _fail_second_lesson
    job = svc.start_course_lesson_generation(db_session, current_user, project.id)
    svc.generate_all_lessons(db_session, current_user, job)
    db_session.commit()
    assert job.result_json["failed_lessons"] == 1

    fake_lesson_generation_ai_provider["response_override"] = None
    retry_job = svc.retry_failed_course_lessons(db_session, current_user, project.id)
    assert len(retry_job.payload_json["lesson_ids"]) == 1
    assert retry_job.payload_json["lesson_ids"][0] == str(second_lesson.id)

    svc.generate_all_lessons(db_session, current_user, retry_job)
    db_session.commit()
    assert retry_job.result_json["completed_lessons"] == 1
    assert svc.get_latest_generation(db_session, second_lesson.id).generation_status == "completed"


def test_cancel_course_generation_only_before_processing(db_session, current_user, coverage_plan_lesson_ready):
    plan = coverage_plan_lesson_ready["plan"]
    job = svc.start_course_lesson_generation(db_session, current_user, plan.project_id)
    cancelled = svc.cancel_course_lesson_generation(db_session, current_user, plan.project_id)
    assert cancelled.status == "cancelled"

    job2 = svc.start_course_lesson_generation(db_session, current_user, plan.project_id)
    job2.status = "processing"
    db_session.add(job2)
    db_session.commit()
    with pytest.raises(HTTPException) as exc_info:
        svc.cancel_course_lesson_generation(db_session, current_user, plan.project_id)
    assert exc_info.value.status_code == 400


# --------------------------------------------------------------------------
# Isolamento multi-tenant
# --------------------------------------------------------------------------

def test_generation_of_other_organization_lesson_is_blocked(db_session, other_org_current_user, coverage_plan_lesson_ready):
    lesson = coverage_plan_lesson_ready["lesson"]
    with pytest.raises(HTTPException) as exc_info:
        svc.start_lesson_generation(db_session, other_org_current_user, lesson.id)
    assert exc_info.value.status_code == 404
