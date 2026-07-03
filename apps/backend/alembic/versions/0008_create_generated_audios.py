"""create generated audios

Revision ID: 0008_audio
Revises: 0007_job_progress
Create Date: 2026-07-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_audio"
down_revision: str | None = "0007_job_progress"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "generated_audios",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("generated_content_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("block_index", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("voice", sa.String(length=100), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("format", sa.String(length=20), server_default="mp3", nullable=False),
        sa.Column("file_path", sa.String(length=1000), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=50), server_default="completed", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["generated_content_id"], ["generated_contents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_generated_audios_block_index"), "generated_audios", ["block_index"], unique=False)
    op.create_index(op.f("ix_generated_audios_generated_content_id"), "generated_audios", ["generated_content_id"], unique=False)
    op.create_index(op.f("ix_generated_audios_project_id"), "generated_audios", ["project_id"], unique=False)
    op.create_index(op.f("ix_generated_audios_status"), "generated_audios", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_generated_audios_status"), table_name="generated_audios")
    op.drop_index(op.f("ix_generated_audios_project_id"), table_name="generated_audios")
    op.drop_index(op.f("ix_generated_audios_generated_content_id"), table_name="generated_audios")
    op.drop_index(op.f("ix_generated_audios_block_index"), table_name="generated_audios")
    op.drop_table("generated_audios")
