"""create course_exports table

Revision ID: 0019_course_exports
Revises: 0018_video_pipeline_jobs
Create Date: 2026-07-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0019_course_exports"
down_revision: str | None = "0018_video_pipeline_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "course_exports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("export_type", sa.String(length=50), nullable=False, server_default="full_course"),
        sa.Column("options_json", postgresql.JSONB(), nullable=True),
        sa.Column("file_path", sa.Text(), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )
    op.create_index("ix_course_exports_project_id", "course_exports", ["project_id"])
    op.create_index("ix_course_exports_status", "course_exports", ["status"])


def downgrade() -> None:
    op.drop_index("ix_course_exports_status", table_name="course_exports")
    op.drop_index("ix_course_exports_project_id", table_name="course_exports")
    op.drop_table("course_exports")
