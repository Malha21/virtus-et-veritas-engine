"""add heygen provider job fields to generated videos

Revision ID: 0013_generated_videos_provider
Revises: 0012_generated_videos
Create Date: 2026-07-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013_generated_videos_provider"
down_revision: str | None = "0012_generated_videos"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("generated_videos", sa.Column("provider_job_id", sa.String(length=255), nullable=True))
    op.add_column("generated_videos", sa.Column("remote_video_url", sa.Text(), nullable=True))
    op.add_column("generated_videos", sa.Column("remote_asset_id", sa.String(length=255), nullable=True))
    op.add_column("generated_videos", sa.Column("last_status_check_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "generated_videos",
        sa.Column("provider_response", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_index(
        op.f("ix_generated_videos_provider_job_id"),
        "generated_videos",
        ["provider_job_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_generated_videos_provider_job_id"), table_name="generated_videos")
    op.drop_column("generated_videos", "provider_response")
    op.drop_column("generated_videos", "last_status_check_at")
    op.drop_column("generated_videos", "remote_asset_id")
    op.drop_column("generated_videos", "remote_video_url")
    op.drop_column("generated_videos", "provider_job_id")
