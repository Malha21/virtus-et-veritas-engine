"""create instructor assets

Revision ID: 0011_instructor_assets
Revises: 0010_audio_voice
Create Date: 2026-07-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011_instructor_assets"
down_revision: str | None = "0010_audio_voice"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "instructor_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("instructor_profile_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("asset_type", sa.String(length=50), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("stored_filename", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=1000), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("consent_confirmed", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["instructor_profile_id"], ["instructor_profiles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_instructor_assets_asset_type"), "instructor_assets", ["asset_type"], unique=False)
    op.create_index(op.f("ix_instructor_assets_instructor_profile_id"), "instructor_assets", ["instructor_profile_id"], unique=False)
    op.create_index(op.f("ix_instructor_assets_user_id"), "instructor_assets", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_instructor_assets_user_id"), table_name="instructor_assets")
    op.drop_index(op.f("ix_instructor_assets_instructor_profile_id"), table_name="instructor_assets")
    op.drop_index(op.f("ix_instructor_assets_asset_type"), table_name="instructor_assets")
    op.drop_table("instructor_assets")
