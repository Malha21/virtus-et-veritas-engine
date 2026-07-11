import pytest
from sqlalchemy.exc import IntegrityError

from app.models.lesson_source_item import LessonSourceItem
from app.models.source_content_item import SourceContentItem
from app.schemas.lesson_source_item import LessonSourceItemCreate


def _make_source_item(db_session, project, project_file, item_code="ITEM-001"):
    item = SourceContentItem(
        project_id=project.id,
        project_file_id=project_file.id,
        item_code=item_code,
        title="Item de conhecimento",
        source_text="Texto original.",
        content_type="concept",
        source_order=0,
    )
    db_session.add(item)
    db_session.flush()
    return item


def test_create_lesson_source_item(db_session, project, project_file, lesson_content):
    source_item = _make_source_item(db_session, project, project_file)
    link = LessonSourceItem(
        lesson_content_id=lesson_content.id,
        source_item_id=source_item.id,
        coverage_type="full",
        source_order_in_lesson=0,
        is_required=True,
    )
    db_session.add(link)
    db_session.flush()

    assert link.id is not None
    assert link.lesson_content_id == lesson_content.id
    assert link.source_item_id == source_item.id


def test_duplicate_lesson_source_item_is_rejected(db_session, project, project_file, lesson_content):
    source_item = _make_source_item(db_session, project, project_file)
    db_session.add(
        LessonSourceItem(lesson_content_id=lesson_content.id, source_item_id=source_item.id)
    )
    db_session.flush()

    db_session.add(
        LessonSourceItem(lesson_content_id=lesson_content.id, source_item_id=source_item.id)
    )
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_same_source_item_can_be_used_in_multiple_lessons(
    db_session, project, project_file, lesson_content, other_lesson_content
):
    source_item = _make_source_item(db_session, project, project_file)
    db_session.add(
        LessonSourceItem(lesson_content_id=lesson_content.id, source_item_id=source_item.id)
    )
    db_session.add(
        LessonSourceItem(lesson_content_id=other_lesson_content.id, source_item_id=source_item.id)
    )
    db_session.flush()  # nao deve levantar erro: mesmo item em duas aulas diferentes


def test_schema_rejects_invalid_coverage_type():
    with pytest.raises(ValueError):
        LessonSourceItemCreate(
            lesson_content_id="00000000-0000-0000-0000-000000000000",
            source_item_id="00000000-0000-0000-0000-000000000000",
            coverage_type="not_valid",
        )


def test_schema_rejects_coverage_score_out_of_range():
    with pytest.raises(ValueError):
        LessonSourceItemCreate(
            lesson_content_id="00000000-0000-0000-0000-000000000000",
            source_item_id="00000000-0000-0000-0000-000000000000",
            coverage_score=101,
        )
