"""add voice provider metadata to generated audios

Revision ID: 0010_audio_voice
Revises: 0009_instructor_profiles
Create Date: 2026-07-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_audio_voice"
down_revision: str | None = "0009_instructor_profiles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("generated_audios", sa.Column("voice_provider", sa.String(length=100), nullable=True))
    op.add_column(
        "generated_audios",
        sa.Column("personalized_voice_used", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column("generated_audios", sa.Column("voice_notice", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("generated_audios", "voice_notice")
    op.drop_column("generated_audios", "personalized_voice_used")
    op.drop_column("generated_audios", "voice_provider")
