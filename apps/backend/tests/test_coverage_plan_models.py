import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.coverage_plan import CoveragePlan
from app.models.coverage_plan_lesson import CoveragePlanLesson
from app.models.coverage_plan_module import CoveragePlanModule
from app.models.lesson_source_item import LessonSourceItem
from tests.conftest import make_source_item


def _make_plan(db_session, project, project_file, version=1):
    plan = CoveragePlan(project_id=project.id, project_file_id=project_file.id, version=version)
    db_session.add(plan)
    db_session.flush()
    return plan


def _make_module(db_session, plan, project, order=1):
    module = CoveragePlanModule(
        coverage_plan_id=plan.id, project_id=project.id, title="Módulo Teste", module_order=order
    )
    db_session.add(module)
    db_session.flush()
    return module


def _make_lesson(db_session, plan, module, order=1, title="Aula Teste"):
    lesson = CoveragePlanLesson(coverage_plan_id=plan.id, module_id=module.id, title=title, lesson_order=order)
    db_session.add(lesson)
    db_session.flush()
    return lesson


def test_create_plan_module_lesson_chain(db_session, project, inventory_project_file):
    plan = _make_plan(db_session, project, inventory_project_file)
    module = _make_module(db_session, plan, project)
    lesson = _make_lesson(db_session, plan, module)

    assert lesson.module_id == module.id
    assert module.coverage_plan_id == plan.id


def test_lesson_source_item_accepts_coverage_plan_lesson(db_session, project, inventory_project_file):
    plan = _make_plan(db_session, project, inventory_project_file)
    module = _make_module(db_session, plan, project)
    lesson = _make_lesson(db_session, plan, module)
    item = make_source_item(
        db_session, project, inventory_project_file, item_code="SRC-0001", title="Item", normalized_content="conteudo"
    )

    link = LessonSourceItem(coverage_plan_lesson_id=lesson.id, source_item_id=item.id)
    db_session.add(link)
    db_session.flush()

    assert link.lesson_content_id is None
    assert link.coverage_plan_lesson_id == lesson.id


def test_lesson_source_item_xor_constraint_rejects_both_null(db_session, project, inventory_project_file):
    item = make_source_item(
        db_session, project, inventory_project_file, item_code="SRC-0001", title="Item", normalized_content="conteudo"
    )
    link = LessonSourceItem(source_item_id=item.id)
    db_session.add(link)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_lesson_source_item_xor_constraint_rejects_both_set(db_session, project, inventory_project_file, lesson_content):
    plan = _make_plan(db_session, project, inventory_project_file)
    module = _make_module(db_session, plan, project)
    lesson = _make_lesson(db_session, plan, module)
    item = make_source_item(
        db_session, project, inventory_project_file, item_code="SRC-0001", title="Item", normalized_content="conteudo"
    )
    link = LessonSourceItem(
        coverage_plan_lesson_id=lesson.id, lesson_content_id=lesson_content.id, source_item_id=item.id
    )
    db_session.add(link)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_legacy_lesson_content_id_still_works(db_session, project, lesson_content):
    # lesson_content_id continua aceitando a aula legada (generated_contents), sem quebra
    from app.models.project_file import ProjectFile

    project_file = ProjectFile(
        project_id=project.id,
        organization_id=project.organization_id,
        file_type="source_pdf",
        original_filename="doc.pdf",
        storage_path=f"/storage/{uuid.uuid4().hex}.pdf",
    )
    db_session.add(project_file)
    db_session.flush()
    real_item = make_source_item(
        db_session, project, project_file, item_code="SRC-0001", title="Item", normalized_content="conteudo"
    )
    link = LessonSourceItem(lesson_content_id=lesson_content.id, source_item_id=real_item.id)
    db_session.add(link)
    db_session.flush()
    assert link.coverage_plan_lesson_id is None


def test_coverage_plan_unique_version_per_project(db_session, project, inventory_project_file):
    _make_plan(db_session, project, inventory_project_file, version=1)
    duplicate = CoveragePlan(project_id=project.id, project_file_id=inventory_project_file.id, version=1)
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()
