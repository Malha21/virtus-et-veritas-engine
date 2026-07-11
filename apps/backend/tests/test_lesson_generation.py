import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.models.lesson_generation import LessonGeneration
from app.schemas.lesson_generation import LessonGenerationCreate


def test_create_lesson_generation(db_session, lesson_content):
    generation = LessonGeneration(
        lesson_content_id=lesson_content.id,
        version=1,
        generated_content="Texto da aula gerado.",
        structured_content={"objective": "Ensinar X", "topics": ["a", "b"]},
        word_count=120,
        estimated_duration_seconds=300,
        source_item_count=3,
        generation_status="completed",
        validation_status="pending",
    )
    db_session.add(generation)
    db_session.flush()

    assert generation.id is not None
    assert generation.version == 1


def test_version_unique_within_lesson(db_session, lesson_content):
    db_session.add(LessonGeneration(lesson_content_id=lesson_content.id, version=1))
    db_session.flush()

    db_session.add(LessonGeneration(lesson_content_id=lesson_content.id, version=1))
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_multiple_versions_are_appended_not_overwritten(db_session, lesson_content):
    db_session.add(LessonGeneration(lesson_content_id=lesson_content.id, version=1, word_count=100))
    db_session.add(LessonGeneration(lesson_content_id=lesson_content.id, version=2, word_count=150))
    db_session.flush()

    versions = db_session.execute(
        select(LessonGeneration.version)
        .where(LessonGeneration.lesson_content_id == lesson_content.id)
        .order_by(LessonGeneration.version)
    ).scalars().all()
    assert versions == [1, 2]


def test_latest_version_lookup(db_session, lesson_content):
    db_session.add(LessonGeneration(lesson_content_id=lesson_content.id, version=1))
    db_session.add(LessonGeneration(lesson_content_id=lesson_content.id, version=2))
    db_session.add(LessonGeneration(lesson_content_id=lesson_content.id, version=3))
    db_session.flush()

    latest_version = db_session.execute(
        select(func.max(LessonGeneration.version)).where(
            LessonGeneration.lesson_content_id == lesson_content.id
        )
    ).scalar_one()
    assert latest_version == 3


def test_version_can_repeat_across_different_lessons(db_session, lesson_content, other_lesson_content):
    db_session.add(LessonGeneration(lesson_content_id=lesson_content.id, version=1))
    db_session.add(LessonGeneration(lesson_content_id=other_lesson_content.id, version=1))
    db_session.flush()  # nao deve levantar erro


def test_schema_rejects_invalid_generation_status():
    with pytest.raises(ValueError):
        LessonGenerationCreate(
            lesson_content_id="00000000-0000-0000-0000-000000000000",
            generation_status="not_a_status",
        )


def test_schema_rejects_negative_word_count():
    with pytest.raises(ValueError):
        LessonGenerationCreate(
            lesson_content_id="00000000-0000-0000-0000-000000000000",
            word_count=-1,
        )


def test_schema_rejects_version_zero():
    with pytest.raises(ValueError):
        LessonGenerationCreate(
            lesson_content_id="00000000-0000-0000-0000-000000000000",
            version=0,
        )
