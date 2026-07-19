from app.models.coverage_plan import CoveragePlan
from app.models.coverage_plan_lesson import CoveragePlanLesson
from app.models.coverage_plan_module import CoveragePlanModule
from app.models.lesson_source_item import LessonSourceItem
from app.models.source_content_item_dependency import SourceContentItemDependency
from app.services.coverage_plan_validator import validate_persisted_coverage
from tests.conftest import make_source_item


def _make_plan(db_session, project, project_file):
    plan = CoveragePlan(project_id=project.id, project_file_id=project_file.id, version=1)
    db_session.add(plan)
    db_session.flush()
    return plan


def _make_module_with_lesson(db_session, plan, project, *, module_order=1, lesson_order=1, title="Aula"):
    module = CoveragePlanModule(
        coverage_plan_id=plan.id, project_id=project.id, title=f"Módulo {module_order}", module_order=module_order
    )
    db_session.add(module)
    db_session.flush()
    lesson = CoveragePlanLesson(
        coverage_plan_id=plan.id, module_id=module.id, title=title, lesson_order=lesson_order
    )
    db_session.add(lesson)
    db_session.flush()
    return module, lesson


def _link(db_session, lesson, item, order=1):
    link = LessonSourceItem(coverage_plan_lesson_id=lesson.id, source_item_id=item.id, source_order_in_lesson=order)
    db_session.add(link)
    db_session.flush()
    return link


def test_validate_reports_unmapped_item(db_session, project, inventory_project_file):
    plan = _make_plan(db_session, project, inventory_project_file)
    module, lesson = _make_module_with_lesson(db_session, plan, project)
    mapped_item = make_source_item(
        db_session, project, inventory_project_file, item_code="SRC-0001", title="Mapeado", normalized_content="x"
    )
    _link(db_session, lesson, mapped_item)
    orphan_item = make_source_item(
        db_session, project, inventory_project_file, item_code="SRC-0002", title="Órfão", normalized_content="y"
    )
    lesson.source_item_count = 1
    db_session.add(lesson)
    db_session.commit()

    result = validate_persisted_coverage(db_session, plan)
    assert result.unmapped_items == 1
    assert result.status == "invalid"
    assert any(issue.issue_type == "unmapped_item" and issue.source_item_id == orphan_item.id for issue in result.issues)


def test_validate_reports_lesson_without_sources(db_session, project, inventory_project_file):
    plan = _make_plan(db_session, project, inventory_project_file)
    _make_module_with_lesson(db_session, plan, project)
    db_session.commit()

    result = validate_persisted_coverage(db_session, plan)
    assert result.lessons_without_sources == 1
    assert result.status == "invalid"


def test_validate_reports_module_without_lessons(db_session, project, inventory_project_file):
    plan = _make_plan(db_session, project, inventory_project_file)
    module = CoveragePlanModule(coverage_plan_id=plan.id, project_id=project.id, title="Vazio", module_order=1)
    db_session.add(module)
    db_session.commit()

    result = validate_persisted_coverage(db_session, plan)
    assert result.modules_without_lessons == 1
    assert result.status == "invalid"


def test_validate_reports_lesson_over_limit(db_session, project, inventory_project_file):
    from decimal import Decimal

    plan = _make_plan(db_session, project, inventory_project_file)
    module, lesson = _make_module_with_lesson(db_session, plan, project)
    item = make_source_item(
        db_session, project, inventory_project_file, item_code="SRC-0001", title="Item", normalized_content="x"
    )
    _link(db_session, lesson, item)
    lesson.source_item_count = 1
    lesson.estimated_duration_minutes = Decimal("15.00")
    db_session.add(lesson)
    db_session.commit()

    result = validate_persisted_coverage(db_session, plan)
    assert result.lessons_over_limit == 1
    assert result.status == "invalid"


def test_validate_valid_plan_status(db_session, project, inventory_project_file):
    plan = _make_plan(db_session, project, inventory_project_file)
    module, lesson = _make_module_with_lesson(db_session, plan, project)
    item = make_source_item(
        db_session,
        project,
        inventory_project_file,
        item_code="SRC-0001",
        title="Item",
        normalized_content="x",
        status="approved",
    )
    _link(db_session, lesson, item)
    lesson.source_item_count = 1
    db_session.add(lesson)
    db_session.commit()

    result = validate_persisted_coverage(db_session, plan)
    assert result.status == "valid"
    assert result.unmapped_items == 0
    assert result.mapped_items == 1


def test_validate_requires_review_when_item_pending_review(db_session, project, inventory_project_file):
    plan = _make_plan(db_session, project, inventory_project_file)
    module, lesson = _make_module_with_lesson(db_session, plan, project)
    item = make_source_item(
        db_session,
        project,
        inventory_project_file,
        item_code="SRC-0001",
        title="Item",
        normalized_content="x",
        status="requires_review",
    )
    _link(db_session, lesson, item)
    lesson.source_item_count = 1
    db_session.add(lesson)
    db_session.commit()

    result = validate_persisted_coverage(db_session, plan)
    assert result.status == "requires_review"
    assert result.requires_review_source_items == 1


def test_validate_detects_dependency_violation(db_session, project, inventory_project_file):
    plan = _make_plan(db_session, project, inventory_project_file)
    module1, lesson1 = _make_module_with_lesson(db_session, plan, project, module_order=1, lesson_order=1)
    module2, lesson2 = _make_module_with_lesson(db_session, plan, project, module_order=2, lesson_order=1)

    rule_item = make_source_item(
        db_session, project, inventory_project_file, item_code="SRC-0001", title="Regra", normalized_content="regra"
    )
    exception_item = make_source_item(
        db_session, project, inventory_project_file, item_code="SRC-0002", title="Exceção", normalized_content="excecao"
    )
    db_session.add(
        SourceContentItemDependency(
            source_item_id=exception_item.id, depends_on_source_item_id=rule_item.id, dependency_type="exception_to"
        )
    )
    # excecao (modulo 1) aparece ANTES da regra (modulo 2) -> violacao
    _link(db_session, lesson1, exception_item)
    _link(db_session, lesson2, rule_item)
    lesson1.source_item_count = 1
    lesson2.source_item_count = 1
    db_session.add_all([lesson1, lesson2])
    db_session.commit()

    result = validate_persisted_coverage(db_session, plan)
    assert result.dependency_violations == 1
