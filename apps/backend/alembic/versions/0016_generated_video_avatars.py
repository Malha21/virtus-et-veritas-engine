"""create generated_video_avatars table

Revision ID: 0016_generated_video_avatars
Revises: 0015_generated_videos_comparison
Create Date: 2026-07-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016_generated_video_avatars"
down_revision: str | None = "0015_generated_videos_comparison"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "generated_video_avatars",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("avatar_id", sa.String(length=255), nullable=True),
        sa.Column("source_image_url", sa.Text(), nullable=True),
        sa.Column("source_video_url", sa.Text(), nullable=True),
        sa.Column("default_model", sa.String(length=100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("extra_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )
    op.create_index("ix_generated_video_avatars_project_id", "generated_video_avatars", ["project_id"])
    op.create_index("ix_generated_video_avatars_provider", "generated_video_avatars", ["provider"])


def downgrade() -> None:
    op.drop_index("ix_generated_video_avatars_provider", table_name="generated_video_avatars")
    op.drop_index("ix_generated_video_avatars_project_id", table_name="generated_video_avatars")
    op.drop_table("generated_video_avatars")
