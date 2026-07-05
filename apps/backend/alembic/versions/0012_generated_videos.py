"""create generated videos

Revision ID: 0012_generated_videos
Revises: 0011_instructor_assets
Create Date: 2026-07-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012_generated_videos"
down_revision: str | None = "0011_instructor_assets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "generated_videos",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lesson_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("module_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("audio_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("avatar_id", sa.String(length=255), nullable=True),
        sa.Column("avatar_name", sa.String(length=255), nullable=True),
        sa.Column("provider", sa.String(length=100), server_default="mock", nullable=False),
        sa.Column("status", sa.String(length=50), server_default="pending", nullable=False),
        sa.Column("resolution", sa.String(length=50), server_default="1080p", nullable=False),
        sa.Column("format", sa.String(length=20), server_default="mp4", nullable=False),
        sa.Column("file_path", sa.String(length=1000), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("extra_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["audio_id"], ["generated_audios.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["lesson_id"], ["generated_contents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_generated_videos_audio_id"), "generated_videos", ["audio_id"], unique=False)
    op.create_index(op.f("ix_generated_videos_lesson_id"), "generated_videos", ["lesson_id"], unique=False)
    op.create_index(op.f("ix_generated_videos_module_id"), "generated_videos", ["module_id"], unique=False)
    op.create_index(op.f("ix_generated_videos_project_id"), "generated_videos", ["project_id"], unique=False)
    op.create_index(op.f("ix_generated_videos_status"), "generated_videos", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_generated_videos_status"), table_name="generated_videos")
    op.drop_index(op.f("ix_generated_videos_project_id"), table_name="generated_videos")
    op.drop_index(op.f("ix_generated_videos_module_id"), table_name="generated_videos")
    op.drop_index(op.f("ix_generated_videos_lesson_id"), table_name="generated_videos")
    op.drop_index(op.f("ix_generated_videos_audio_id"), table_name="generated_videos")
    op.drop_table("generated_videos")
