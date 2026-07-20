"""host customizado por chave de API

Permite que o usuario informe um host/endpoint customizado por credencial
(ex.: proxy, gateway proprio, Azure OpenAI). Quando em branco, a geracao
usa o host padrao de cada provedor.

Revision ID: 0028_credential_base_url
Revises: 0027_market_bestsellers
Create Date: 2026-07-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0028_credential_base_url"
down_revision: str | None = "0027_market_bestsellers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_ai_credentials",
        sa.Column("base_url", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_ai_credentials", "base_url")
