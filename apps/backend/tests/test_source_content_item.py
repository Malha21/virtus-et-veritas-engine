import pytest
from sqlalchemy.exc import IntegrityError

from app.models.source_content_item import SourceContentItem
from app.schemas.source_content_item import SourceContentItemCreate, SourceContentItemResponse


def _build_item(project, project_file, item_code="ITEM-001", source_order=1):
    return SourceContentItem(
        project_id=project.id,
        project_file_id=project_file.id,
        item_code=item_code,
        title="Conceito de dominacao",
        source_text="Texto original extraido do documento.",
        content_type="concept",
        page_start=3,
        page_end=4,
        source_order=source_order,
        importance="essential",
        status="pending",
    )


def test_create_source_content_item(db_session, project, project_file):
    item = _build_item(project, project_file)
    db_session.add(item)
    db_session.flush()

    assert item.id is not None
    assert item.project_id == project.id
    assert item.project_file_id == project_file.id
    assert item.content_type == "concept"
    assert item.created_at is not None


def test_item_code_unique_within_project(db_session, project, project_file):
    db_session.add(_build_item(project, project_file, item_code="DUP-001"))
    db_session.flush()

    db_session.add(_build_item(project, project_file, item_code="DUP-001", source_order=2))
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_same_item_code_allowed_across_different_projects(
    db_session, project, project_file, other_project, other_project_file
):
    db_session.add(_build_item(project, project_file, item_code="SHARED-001"))
    db_session.flush()

    db_session.add(_build_item(other_project, other_project_file, item_code="SHARED-001"))
    db_session.flush()  # nao deve levantar IntegrityError


def test_page_ordering_preserved(db_session, project, project_file):
    first = _build_item(project, project_file, item_code="ORD-1", source_order=0)
    second = _build_item(project, project_file, item_code="ORD-2", source_order=1)
    db_session.add_all([first, second])
    db_session.flush()

    assert first.source_order < second.source_order


def test_schema_serialization_from_orm(db_session, project, project_file):
    item = _build_item(project, project_file, item_code="SER-001")
    db_session.add(item)
    db_session.flush()

    response = SourceContentItemResponse.model_validate(item)
    assert response.item_code == "SER-001"
    assert response.content_type == "concept"
    assert response.importance == "essential"


def test_schema_create_validates_content_type():
    with pytest.raises(ValueError):
        SourceContentItemCreate(
            project_id="00000000-0000-0000-0000-000000000000",
            project_file_id="00000000-0000-0000-0000-000000000000",
            item_code="X",
            title="Titulo",
            source_text="Texto",
            content_type="not_a_valid_type",
        )


def test_schema_page_end_before_page_start_is_invalid():
    with pytest.raises(ValueError):
        SourceContentItemCreate(
            project_id="00000000-0000-0000-0000-000000000000",
            project_file_id="00000000-0000-0000-0000-000000000000",
            item_code="X",
            title="Titulo",
            source_text="Texto",
            page_start=10,
            page_end=5,
        )


def test_schema_page_start_must_be_positive():
    with pytest.raises(ValueError):
        SourceContentItemCreate(
            project_id="00000000-0000-0000-0000-000000000000",
            project_file_id="00000000-0000-0000-0000-000000000000",
            item_code="X",
            title="Titulo",
            source_text="Texto",
            page_start=0,
        )
