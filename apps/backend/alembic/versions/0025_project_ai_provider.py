"""seleção de provedor de IA por projeto

Adiciona projects.ai_provider (nullable): quando preenchido ("openai",
"anthropic" ou "gemini"), sobrepoe o provedor padrao do sistema
(AI_PROVIDER no .env) para toda geracao desse projeto. Projetos existentes
ficam com NULL e continuam usando o padrao do sistema, sem nenhuma
migracao de dados necessaria.

Revision ID: 0025_project_ai_provider
Revises: 0024_lesson_generation_engine
Create Date: 2026-07-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025_project_ai_provider"
down_revision: str | None = "0024_lesson_generation_engine"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("ai_provider", sa.String(length=40), nullable=True))


def downgrade() -> None:
    op.drop_column("projects", "ai_provider")
