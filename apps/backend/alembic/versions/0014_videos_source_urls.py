"""add source image/video url fields to generated videos

Revision ID: 0014_videos_source_urls
Revises: 0013_generated_videos_provider
Create Date: 2026-07-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014_videos_source_urls"
down_revision: str | None = "0013_generated_videos_provider"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("generated_videos", sa.Column("source_image_url", sa.Text(), nullable=True))
    op.add_column("generated_videos", sa.Column("source_video_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("generated_videos", "source_video_url")
    op.drop_column("generated_videos", "source_image_url")
