"""add provider comparison fields to generated videos

Revision ID: 0015_generated_videos_comparison
Revises: 0014_videos_source_urls
Create Date: 2026-07-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_generated_videos_comparison"
down_revision: str | None = "0014_videos_source_urls"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("generated_videos", sa.Column("generation_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("generated_videos", sa.Column("generation_completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("generated_videos", sa.Column("provider_latency_seconds", sa.Float(), nullable=True))
    op.add_column("generated_videos", sa.Column("estimated_cost_usd", sa.Float(), nullable=True))
    op.add_column("generated_videos", sa.Column("quality_rating", sa.Integer(), nullable=True))
    op.add_column("generated_videos", sa.Column("quality_notes", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("generated_videos", "quality_notes")
    op.drop_column("generated_videos", "quality_rating")
    op.drop_column("generated_videos", "estimated_cost_usd")
    op.drop_column("generated_videos", "provider_latency_seconds")
    op.drop_column("generated_videos", "generation_completed_at")
    op.drop_column("generated_videos", "generation_started_at")
