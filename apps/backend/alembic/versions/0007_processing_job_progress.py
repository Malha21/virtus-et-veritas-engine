"""add progress fields to processing jobs

Revision ID: 0007_job_progress
Revises: 0006_retention
Create Date: 2026-07-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_job_progress"
down_revision: str | None = "0006_retention"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("processing_jobs", sa.Column("progress", sa.Integer(), server_default="0", nullable=False))
    op.add_column("processing_jobs", sa.Column("current_step", sa.String(length=255), nullable=True))
    op.add_column("processing_jobs", sa.Column("message", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("processing_jobs", "message")
    op.drop_column("processing_jobs", "current_step")
    op.drop_column("processing_jobs", "progress")
