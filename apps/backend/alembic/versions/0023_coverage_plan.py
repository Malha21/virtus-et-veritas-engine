"""fase 19.4 - plano de cobertura, estrutura pedagogica e divisao das aulas

Cria a estrutura pedagogica (modulos/aulas) que liga o inventario aprovado
(fase 19.3) a geracao individual de aulas (fase 19.5):

- coverage_plans: versao do plano de cobertura por documento (project_file)
- coverage_plan_modules: modulos (unidades tematicas) de um plano
- coverage_plan_lessons: aulas planejadas (<=10min) dentro de um modulo

lesson_source_items (fase 19.1) e alterada de forma aditiva: passa a aceitar
tambem uma aula planejada (coverage_plan_lesson_id), alem da aula legada
(lesson_content_id, que passa a ser opcional). Nenhuma tabela/coluna anterior
e removida ou tem seu significado alterado.

Revision ID: 0023_coverage_plan
Revises: 0022_inventory_item_assoc
Create Date: 2026-07-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0023_coverage_plan"
down_revision: str | None = "0022_inventory_item_assoc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- coverage_plans ---------------------------------------------------
    op.create_table(
        "coverage_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "project_file_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("project_files.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("inventory_item_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("inventory_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("total_modules", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_lessons", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("mapped_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unmapped_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_total_words", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_total_minutes", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("model_name", sa.String(length=100), nullable=True),
        sa.Column("prompt_version", sa.String(length=50), nullable=True),
        sa.Column("settings_json", postgresql.JSONB(), nullable=True),
        sa.Column("report_data", postgresql.JSONB(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "approved_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("project_id", "version", name="uq_coverage_plans_project_version"),
    )
    op.create_index("ix_coverage_plans_project_id", "coverage_plans", ["project_id"])
    op.create_index("ix_coverage_plans_project_file_id", "coverage_plans", ["project_file_id"])
    op.create_index("ix_coverage_plans_status", "coverage_plans", ["status"])

    # --- coverage_plan_modules ---------------------------------------------------
    op.create_table(
        "coverage_plan_modules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "coverage_plan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("coverage_plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("learning_objective", sa.Text(), nullable=True),
        sa.Column("module_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_total_minutes", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("estimated_total_words", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_item_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="planned"),
        sa.Column("plan_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_coverage_plan_modules_coverage_plan_id", "coverage_plan_modules", ["coverage_plan_id"])
    op.create_index("ix_coverage_plan_modules_project_id", "coverage_plan_modules", ["project_id"])
    op.create_index("ix_coverage_plan_modules_module_order", "coverage_plan_modules", ["module_order"])
    op.create_index("ix_coverage_plan_modules_status", "coverage_plan_modules", ["status"])

    # --- coverage_plan_lessons ---------------------------------------------------
    op.create_table(
        "coverage_plan_lessons",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "coverage_plan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("coverage_plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "module_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("coverage_plan_modules.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("learning_objective", sa.Text(), nullable=True),
        sa.Column("lesson_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("target_duration_minutes", sa.Numeric(5, 2), nullable=True),
        sa.Column("estimated_duration_minutes", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("estimated_source_words", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_explanation_words", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_transition_words", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_word_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_item_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="planned"),
        sa.Column("plan_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("requires_review", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("grouping_reason", sa.Text(), nullable=True),
        sa.Column("warnings_json", postgresql.JSONB(), nullable=True),
        sa.Column(
            "generated_content_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("generated_contents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_coverage_plan_lessons_coverage_plan_id", "coverage_plan_lessons", ["coverage_plan_id"])
    op.create_index("ix_coverage_plan_lessons_module_id", "coverage_plan_lessons", ["module_id"])
    op.create_index("ix_coverage_plan_lessons_lesson_order", "coverage_plan_lessons", ["lesson_order"])
    op.create_index("ix_coverage_plan_lessons_status", "coverage_plan_lessons", ["status"])
    op.create_index(
        "ix_coverage_plan_lessons_generated_content_id", "coverage_plan_lessons", ["generated_content_id"]
    )

    # --- lesson_source_items: extensao aditiva para aceitar aula planejada -----------
    op.add_column(
        "lesson_source_items",
        sa.Column(
            "coverage_plan_lesson_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("coverage_plan_lessons.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.alter_column("lesson_source_items", "lesson_content_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)
    op.create_index(
        "ix_lesson_source_items_coverage_plan_lesson_id", "lesson_source_items", ["coverage_plan_lesson_id"]
    )
    op.create_unique_constraint(
        "uq_lesson_source_items_plan_lesson_source",
        "lesson_source_items",
        ["coverage_plan_lesson_id", "source_item_id"],
    )
    op.create_check_constraint(
        "ck_lesson_source_items_lesson_ref_xor",
        "lesson_source_items",
        "(lesson_content_id IS NOT NULL AND coverage_plan_lesson_id IS NULL) "
        "OR (lesson_content_id IS NULL AND coverage_plan_lesson_id IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_lesson_source_items_lesson_ref_xor", "lesson_source_items", type_="check")
    op.drop_constraint("uq_lesson_source_items_plan_lesson_source", "lesson_source_items", type_="unique")
    op.drop_index("ix_lesson_source_items_coverage_plan_lesson_id", table_name="lesson_source_items")
    op.alter_column("lesson_source_items", "lesson_content_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)
    op.drop_column("lesson_source_items", "coverage_plan_lesson_id")

    op.drop_index("ix_coverage_plan_lessons_generated_content_id", table_name="coverage_plan_lessons")
    op.drop_index("ix_coverage_plan_lessons_status", table_name="coverage_plan_lessons")
    op.drop_index("ix_coverage_plan_lessons_lesson_order", table_name="coverage_plan_lessons")
    op.drop_index("ix_coverage_plan_lessons_module_id", table_name="coverage_plan_lessons")
    op.drop_index("ix_coverage_plan_lessons_coverage_plan_id", table_name="coverage_plan_lessons")
    op.drop_table("coverage_plan_lessons")

    op.drop_index("ix_coverage_plan_modules_status", table_name="coverage_plan_modules")
    op.drop_index("ix_coverage_plan_modules_module_order", table_name="coverage_plan_modules")
    op.drop_index("ix_coverage_plan_modules_project_id", table_name="coverage_plan_modules")
    op.drop_index("ix_coverage_plan_modules_coverage_plan_id", table_name="coverage_plan_modules")
    op.drop_table("coverage_plan_modules")

    op.drop_index("ix_coverage_plans_status", table_name="coverage_plans")
    op.drop_index("ix_coverage_plans_project_file_id", table_name="coverage_plans")
    op.drop_index("ix_coverage_plans_project_id", table_name="coverage_plans")
    op.drop_table("coverage_plans")
