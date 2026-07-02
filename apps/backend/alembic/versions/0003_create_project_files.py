"""create project files table

Revision ID: 0003_create_project_files
Revises: 0002_create_projects
Create Date: 2026-07-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_create_project_files"
down_revision: str | None = "0002_create_projects"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "project_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_type", sa.String(length=80), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=50), server_default="uploaded", nullable=False),
        sa.Column("extracted_text_path", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_project_files_project_id"), "project_files", ["project_id"], unique=False)
    op.create_index(op.f("ix_project_files_organization_id"), "project_files", ["organization_id"], unique=False)
    op.create_index(op.f("ix_project_files_file_type"), "project_files", ["file_type"], unique=False)
    op.create_index(op.f("ix_project_files_status"), "project_files", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_project_files_status"), table_name="project_files")
    op.drop_index(op.f("ix_project_files_file_type"), table_name="project_files")
    op.drop_index(op.f("ix_project_files_organization_id"), table_name="project_files")
    op.drop_index(op.f("ix_project_files_project_id"), table_name="project_files")
    op.drop_table("project_files")
