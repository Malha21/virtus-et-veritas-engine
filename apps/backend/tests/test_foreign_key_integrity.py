import pytest
from sqlalchemy.exc import IntegrityError

from app.models.lesson_source_item import LessonSourceItem
from app.models.source_content_item import SourceContentItem


def test_source_content_item_requires_existing_project_file(db_session, project):
    bogus_file_id = "00000000-0000-0000-0000-000000000000"
    item = SourceContentItem(
        project_id=project.id,
        project_file_id=bogus_file_id,
        item_code="FK-1",
        title="Titulo",
        source_text="Texto",
    )
    db_session.add(item)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_deleting_project_file_cascades_to_source_content_items(db_session, project, project_file):
    item = SourceContentItem(
        project_id=project.id,
        project_file_id=project_file.id,
        item_code="CASCADE-1",
        title="Titulo",
        source_text="Texto",
    )
    db_session.add(item)
    db_session.flush()
    item_id = item.id

    db_session.delete(project_file)
    db_session.flush()
    db_session.expire_all()  # o cascade roda no Postgres, nao na identity map do SQLAlchemy

    remaining = db_session.get(SourceContentItem, item_id)
    assert remaining is None


def test_deleting_lesson_content_cascades_to_lesson_source_items(
    db_session, project, project_file, lesson_content
):
    source_item = SourceContentItem(
        project_id=project.id,
        project_file_id=project_file.id,
        item_code="CASCADE-2",
        title="Titulo",
        source_text="Texto",
    )
    db_session.add(source_item)
    db_session.flush()

    link = LessonSourceItem(lesson_content_id=lesson_content.id, source_item_id=source_item.id)
    db_session.add(link)
    db_session.flush()
    link_id = link.id

    db_session.delete(lesson_content)
    db_session.flush()
    db_session.expire_all()  # o cascade roda no Postgres, nao na identity map do SQLAlchemy

    remaining = db_session.get(LessonSourceItem, link_id)
    assert remaining is None
