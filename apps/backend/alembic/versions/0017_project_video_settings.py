"""create project_video_settings table

Revision ID: 0017_project_video_settings
Revises: 0016_generated_video_avatars
Create Date: 2026-07-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0017_project_video_settings"
down_revision: str | None = "0016_generated_video_avatars"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "project_video_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("default_provider", sa.String(length=50), nullable=True),
        sa.Column(
            "default_mock_avatar_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("generated_video_avatars.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "default_heygen_avatar_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("generated_video_avatars.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "default_did_avatar_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("generated_video_avatars.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "default_sync_avatar_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("generated_video_avatars.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("default_resolution", sa.String(length=50), nullable=False, server_default="1080p"),
        sa.Column("default_format", sa.String(length=20), nullable=False, server_default="mp4"),
        sa.Column("auto_download_completed_videos", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )
    op.create_index("ix_project_video_settings_project_id", "project_video_settings", ["project_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_project_video_settings_project_id", table_name="project_video_settings")
    op.drop_table("project_video_settings")
