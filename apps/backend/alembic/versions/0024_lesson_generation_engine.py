"""fase 19.5 - geracao individual, fiel e versionada das aulas

Estende lesson_generations (fase 19.1, migration 0020) de forma aditiva para
suportar a geracao de roteiro por CoveragePlanLesson (fase 19.4):

- coverage_plan_lesson_id: liga a versao diretamente a aula planejada, sem
  depender apenas da indirecao via generated_contents.id (lesson_content_id
  continua preenchido tambem, para nao quebrar a constraint/uso existente).
- source_fingerprint / coverage_plan_version: deteccao deterministica de
  gerações desatualizadas (is_stale) quando o plano ou as fontes da aula mudam.
- covered/uncovered_source_items_json, source_pages_json, source_block_codes_json,
  unsupported_claims_json: cobertura declarada pela IA, revalidada pelo servico
  antes de persistir (nunca confiada cegamente).
- requires_split / split_reason: aula que excede o limite de duracao nunca e
  cortada -- fica marcada para retorno ao Plano de Cobertura.
- tokens/custo, temperatura e provedor: observabilidade da chamada de IA.
- aprovacao/rejeicao/edicao manual: campos para o ciclo humano por versao.

Nenhuma coluna ou tabela anterior e removida ou tem seu significado alterado.

Revision ID: 0024_lesson_generation_engine
Revises: 0023_coverage_plan
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0024_lesson_generation_engine"
down_revision: str | None = "0023_coverage_plan"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # processing_jobs: coluna direta para filtrar jobs de geracao de aula por
    # CoveragePlanLesson antes de existir qualquer GeneratedContent (so criado na
    # primeira geracao bem-sucedida) -- mesmo padrao ja usado por project_file_id
    # e lesson_content_id nesta tabela para os demais job_type.
    op.add_column(
        "processing_jobs",
        sa.Column(
            "coverage_plan_lesson_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("coverage_plan_lessons.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_processing_jobs_coverage_plan_lesson_id", "processing_jobs", ["coverage_plan_lesson_id"]
    )

    op.add_column(
        "lesson_generations",
        sa.Column(
            "coverage_plan_lesson_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("coverage_plan_lessons.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.add_column("lesson_generations", sa.Column("coverage_plan_version", sa.Integer(), nullable=True))
    op.add_column("lesson_generations", sa.Column("source_fingerprint", sa.String(length=64), nullable=True))
    op.add_column(
        "lesson_generations",
        sa.Column("is_stale", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "lesson_generations",
        sa.Column("requires_split", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column("lesson_generations", sa.Column("split_reason", sa.Text(), nullable=True))
    op.add_column("lesson_generations", sa.Column("covered_source_items_json", postgresql.JSONB(), nullable=True))
    op.add_column("lesson_generations", sa.Column("uncovered_source_items_json", postgresql.JSONB(), nullable=True))
    op.add_column("lesson_generations", sa.Column("source_pages_json", postgresql.JSONB(), nullable=True))
    op.add_column("lesson_generations", sa.Column("source_block_codes_json", postgresql.JSONB(), nullable=True))
    op.add_column("lesson_generations", sa.Column("unsupported_claims_json", postgresql.JSONB(), nullable=True))
    op.add_column("lesson_generations", sa.Column("warnings_json", postgresql.JSONB(), nullable=True))
    op.add_column("lesson_generations", sa.Column("feedback_notes", sa.Text(), nullable=True))
    op.add_column(
        "lesson_generations",
        sa.Column("is_manual_edit", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column("lesson_generations", sa.Column("input_tokens", sa.Integer(), nullable=True))
    op.add_column("lesson_generations", sa.Column("output_tokens", sa.Integer(), nullable=True))
    op.add_column("lesson_generations", sa.Column("total_tokens", sa.Integer(), nullable=True))
    op.add_column("lesson_generations", sa.Column("estimated_cost", sa.Numeric(10, 4), nullable=True))
    op.add_column("lesson_generations", sa.Column("temperature", sa.Numeric(3, 2), nullable=True))
    op.add_column("lesson_generations", sa.Column("provider_name", sa.String(length=50), nullable=True))
    op.add_column(
        "lesson_generations",
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column("lesson_generations", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "lesson_generations",
        sa.Column(
            "approved_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column("lesson_generations", sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "lesson_generations",
        sa.Column(
            "rejected_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column("lesson_generations", sa.Column("rejection_reason", sa.Text(), nullable=True))

    op.create_index(
        "ix_lesson_generations_coverage_plan_lesson_id",
        "lesson_generations",
        ["coverage_plan_lesson_id"],
    )
    op.create_unique_constraint(
        "uq_lesson_generations_plan_lesson_version",
        "lesson_generations",
        ["coverage_plan_lesson_id", "version"],
    )


def downgrade() -> None:
    op.drop_index("ix_processing_jobs_coverage_plan_lesson_id", table_name="processing_jobs")
    op.drop_column("processing_jobs", "coverage_plan_lesson_id")

    op.drop_constraint("uq_lesson_generations_plan_lesson_version", "lesson_generations", type_="unique")
    op.drop_index("ix_lesson_generations_coverage_plan_lesson_id", table_name="lesson_generations")

    op.drop_column("lesson_generations", "rejection_reason")
    op.drop_column("lesson_generations", "rejected_by")
    op.drop_column("lesson_generations", "rejected_at")
    op.drop_column("lesson_generations", "approved_by")
    op.drop_column("lesson_generations", "approved_at")
    op.drop_column("lesson_generations", "created_by")
    op.drop_column("lesson_generations", "provider_name")
    op.drop_column("lesson_generations", "temperature")
    op.drop_column("lesson_generations", "estimated_cost")
    op.drop_column("lesson_generations", "total_tokens")
    op.drop_column("lesson_generations", "output_tokens")
    op.drop_column("lesson_generations", "input_tokens")
    op.drop_column("lesson_generations", "is_manual_edit")
    op.drop_column("lesson_generations", "feedback_notes")
    op.drop_column("lesson_generations", "warnings_json")
    op.drop_column("lesson_generations", "unsupported_claims_json")
    op.drop_column("lesson_generations", "source_block_codes_json")
    op.drop_column("lesson_generations", "source_pages_json")
    op.drop_column("lesson_generations", "uncovered_source_items_json")
    op.drop_column("lesson_generations", "covered_source_items_json")
    op.drop_column("lesson_generations", "split_reason")
    op.drop_column("lesson_generations", "requires_split")
    op.drop_column("lesson_generations", "is_stale")
    op.drop_column("lesson_generations", "source_fingerprint")
    op.drop_column("lesson_generations", "coverage_plan_version")
    op.drop_column("lesson_generations", "coverage_plan_lesson_id")
