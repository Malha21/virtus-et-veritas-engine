"""chaves de API individuais por usuario

Cada usuario pode cadastrar suas proprias chaves de API por provedor
(anthropic/openai/gemini), cifradas em repouso (Fernet). O admin seguem
usando as chaves globais do .env como fallback; demais usuarios precisam
cadastrar a propria chave antes de gerar conteudo com IA.

Revision ID: 0026_user_ai_credentials
Revises: 0025_project_ai_provider
Create Date: 2026-07-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0026_user_ai_credentials"
down_revision: str | None = "0025_project_ai_provider"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_ai_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_type", sa.String(length=40), nullable=False),
        sa.Column("encrypted_api_key", sa.Text(), nullable=False),
        sa.Column("key_last_four", sa.String(length=4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "provider_type", name="uq_user_ai_credentials_user_provider"),
    )
    op.create_index(
        op.f("ix_user_ai_credentials_user_id"), "user_ai_credentials", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_user_ai_credentials_user_id"), table_name="user_ai_credentials")
    op.drop_table("user_ai_credentials")
