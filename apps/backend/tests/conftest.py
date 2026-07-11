import uuid

import pytest
from sqlalchemy import event
from sqlalchemy.orm import sessionmaker

from app.core.database import engine
from app.models.generated_content import GeneratedContent
from app.models.organization import Organization
from app.models.project import Project
from app.models.project_file import ProjectFile
from app.models.user import User


@pytest.fixture()
def db_session():
    """Sessao de teste isolada por SAVEPOINT: tudo e revertido ao final, mesmo com commits internos."""
    connection = engine.connect()
    outer_transaction = connection.begin()
    session_factory = sessionmaker(bind=connection)
    session = session_factory()

    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess, trans):
        nonlocal nested
        if not nested.is_active:
            nested = connection.begin_nested()

    try:
        yield session
    finally:
        session.close()
        outer_transaction.rollback()
        connection.close()


@pytest.fixture()
def organization(db_session):
    org = Organization(name="Test Org", slug=f"test-org-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    db_session.flush()
    return org


def _make_project(db_session, organization, title="Curso Teste"):
    user = User(
        organization_id=organization.id,
        name="Tester",
        email=f"{uuid.uuid4().hex}@test.local",
        password_hash="hashed",
    )
    db_session.add(user)
    db_session.flush()

    project = Project(
        organization_id=organization.id,
        owner_id=user.id,
        title=title,
        slug=f"{title.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}",
    )
    db_session.add(project)
    db_session.flush()
    return project


@pytest.fixture()
def project(db_session, organization):
    return _make_project(db_session, organization)


@pytest.fixture()
def other_project(db_session, organization):
    return _make_project(db_session, organization, title="Outro Curso")


def _make_project_file(db_session, project):
    project_file = ProjectFile(
        project_id=project.id,
        organization_id=project.organization_id,
        file_type="source_pdf",
        original_filename="documento.pdf",
        storage_path=f"/storage/{uuid.uuid4().hex}.pdf",
    )
    db_session.add(project_file)
    db_session.flush()
    return project_file


@pytest.fixture()
def project_file(db_session, project):
    return _make_project_file(db_session, project)


@pytest.fixture()
def other_project_file(db_session, other_project):
    return _make_project_file(db_session, other_project)


def _make_lesson_content(db_session, project, title="Aula 1"):
    content = GeneratedContent(
        project_id=project.id,
        organization_id=project.organization_id,
        content_type="lesson_script",
        title=title,
        version=1,
        content_json={"lesson_script": {"lesson_title": title}},
    )
    db_session.add(content)
    db_session.flush()
    return content


@pytest.fixture()
def lesson_content(db_session, project):
    return _make_lesson_content(db_session, project)


@pytest.fixture()
def other_lesson_content(db_session, project):
    return _make_lesson_content(db_session, project, title="Aula 2")
