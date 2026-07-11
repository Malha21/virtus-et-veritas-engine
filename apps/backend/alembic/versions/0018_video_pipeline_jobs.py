"""create video_pipeline_jobs and video_pipeline_job_items tables

Revision ID: 0018_video_pipeline_jobs
Revises: 0017_project_video_settings
Create Date: 2026-07-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0018_video_pipeline_jobs"
down_revision: str | None = "0017_project_video_settings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "video_pipeline_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scope", sa.String(length=20), nullable=False),
        sa.Column("module_index", sa.Integer(), nullable=True),
        sa.Column(
            "lesson_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("generated_contents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("lesson_index", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("total_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_item_label", sa.String(length=255), nullable=True),
        sa.Column("provider", sa.String(length=50), nullable=True),
        sa.Column(
            "video_avatar_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("generated_video_avatars.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("skip_existing_audio", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("skip_existing_video", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("force_regenerate_audio", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("force_regenerate_video", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )
    op.create_index("ix_video_pipeline_jobs_project_id", "video_pipeline_jobs", ["project_id"])
    op.create_index("ix_video_pipeline_jobs_status", "video_pipeline_jobs", ["status"])

    op.create_table(
        "video_pipeline_job_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("video_pipeline_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "lesson_content_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("generated_contents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("module_index", sa.Integer(), nullable=True),
        sa.Column("lesson_index", sa.Integer(), nullable=True),
        sa.Column("lesson_title", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column(
            "generated_audio_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("generated_audios.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "generated_video_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("generated_videos.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )
    op.create_index("ix_video_pipeline_job_items_job_id", "video_pipeline_job_items", ["job_id"])
    op.create_index("ix_video_pipeline_job_items_project_id", "video_pipeline_job_items", ["project_id"])
    op.create_index(
        "ix_video_pipeline_job_items_lesson_content_id", "video_pipeline_job_items", ["lesson_content_id"]
    )
    op.create_index("ix_video_pipeline_job_items_status", "video_pipeline_job_items", ["status"])


def downgrade() -> None:
    op.drop_index("ix_video_pipeline_job_items_status", table_name="video_pipeline_job_items")
    op.drop_index("ix_video_pipeline_job_items_lesson_content_id", table_name="video_pipeline_job_items")
    op.drop_index("ix_video_pipeline_job_items_project_id", table_name="video_pipeline_job_items")
    op.drop_index("ix_video_pipeline_job_items_job_id", table_name="video_pipeline_job_items")
    op.drop_table("video_pipeline_job_items")

    op.drop_index("ix_video_pipeline_jobs_status", table_name="video_pipeline_jobs")
    op.drop_index("ix_video_pipeline_jobs_project_id", table_name="video_pipeline_jobs")
    op.drop_table("video_pipeline_jobs")
