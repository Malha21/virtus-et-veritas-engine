"""create instructor profiles

Revision ID: 0009_instructor_profiles
Revises: 0008_audio
Create Date: 2026-07-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_instructor_profiles"
down_revision: str | None = "0008_audio"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "instructor_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("teaching_style", sa.Text(), nullable=True),
        sa.Column("voice_provider", sa.String(length=100), nullable=True),
        sa.Column("voice_id", sa.String(length=255), nullable=True),
        sa.Column("voice_name", sa.String(length=255), nullable=True),
        sa.Column("voice_sample_notes", sa.Text(), nullable=True),
        sa.Column("avatar_provider", sa.String(length=100), nullable=True),
        sa.Column("avatar_id", sa.String(length=255), nullable=True),
        sa.Column("avatar_name", sa.String(length=255), nullable=True),
        sa.Column("avatar_style", sa.Text(), nullable=True),
        sa.Column("avatar_image_path", sa.String(length=1000), nullable=True),
        sa.Column("consent_voice_clone", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("consent_avatar_use", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("consent_terms_text", sa.Text(), nullable=True),
        sa.Column("consent_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(op.f("ix_instructor_profiles_user_id"), "instructor_profiles", ["user_id"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_instructor_profiles_user_id"), table_name="instructor_profiles")
    op.drop_table("instructor_profiles")
