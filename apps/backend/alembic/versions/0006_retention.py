"""add project retention fields

Revision ID: 0006_retention
Revises: 0005_ai_content
Create Date: 2026-07-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_retention"
down_revision: str | None = "0005_ai_content"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("projects", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("projects", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("projects", "deleted_at")
    op.drop_column("projects", "expires_at")
    op.drop_column("projects", "archived_at")
