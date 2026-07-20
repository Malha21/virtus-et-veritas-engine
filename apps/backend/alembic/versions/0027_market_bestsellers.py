"""ranking de livros mais vendidos (insights de mercado)

Guarda snapshots do ranking mensal geral do PublishNews (mercado editorial
brasileiro, dados via Nielsen BookScan), usado para exibir "top 10 livros
mais vendidos" e "temas em alta" (categorias agregadas por volume de
vendas) no dashboard. Atualizado automaticamente por um job agendado.

Revision ID: 0027_market_bestsellers
Revises: 0026_user_ai_credentials
Create Date: 2026-07-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0027_market_bestsellers"
down_revision: str | None = "0026_user_ai_credentials"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_bestsellers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False, server_default="publishnews"),
        sa.Column("period_type", sa.String(length=20), nullable=False, server_default="mensal"),
        sa.Column("period_label", sa.String(length=60), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("author", sa.String(length=255), nullable=True),
        sa.Column("publisher", sa.String(length=255), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("sales_volume", sa.Integer(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_market_bestsellers_fetched_at"), "market_bestsellers", ["fetched_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_market_bestsellers_fetched_at"), table_name="market_bestsellers")
    op.drop_table("market_bestsellers")
