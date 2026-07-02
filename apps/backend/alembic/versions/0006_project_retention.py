"""add project retention fields

Revision ID: 0006_project_retention
Revises: 0005_ai_content
Create Date: 2026-07-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_project_retention"
down_revision: str | None = "0005_ai_content"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("projects", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("projects", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f("ix_projects_archived_at"), "projects", ["archived_at"], unique=False)
    op.create_index(op.f("ix_projects_expires_at"), "projects", ["expires_at"], unique=False)
    op.create_index(op.f("ix_projects_deleted_at"), "projects", ["deleted_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_projects_deleted_at"), table_name="projects")
    op.drop_index(op.f("ix_projects_expires_at"), table_name="projects")
    op.drop_index(op.f("ix_projects_archived_at"), table_name="projects")
    op.drop_column("projects", "deleted_at")
    op.drop_column("projects", "expires_at")
    op.drop_column("projects", "archived_at")
