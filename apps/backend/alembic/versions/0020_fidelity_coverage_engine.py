"""fase 19.1 - fundacao do motor de fidelidade e cobertura

Cria a base de rastreabilidade documento -> pagina -> bloco -> item do
inventario -> aula -> geracao -> auditoria:

- source_content_items: unidades de conhecimento inventariadas por documento (project_file)
- lesson_source_items: relacao aula (generated_contents) <-> source_content_items
- lesson_generations: versoes (append-only) de conteudo gerado por aula
- course_coverage_reports: relatorios (append-only) de cobertura/fidelidade por curso (project)
- processing_jobs: colunas novas para suportar jobs longos e retomaveis desta fase
  (project_file_id, lesson_content_id, total_items, processed_items, failed_items, current_item)

Revision ID: 0020_fidelity_coverage_engine
Revises: 0019_course_exports
Create Date: 2026-07-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0020_fidelity_coverage_engine"
down_revision: str | None = "0019_course_exports"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- source_content_items ---------------------------------------------------
    op.create_table(
        "source_content_items",
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
        sa.Column("item_code", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("normalized_content", sa.Text(), nullable=True),
        sa.Column("content_type", sa.String(length=50), nullable=False, server_default="other"),
        sa.Column("page_start", sa.Integer(), nullable=True),
        sa.Column("page_end", sa.Integer(), nullable=True),
        sa.Column("source_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("importance", sa.String(length=20), nullable=False, server_default="relevant"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("project_id", "item_code", name="uq_source_content_items_project_item_code"),
    )
    op.create_index("ix_source_content_items_project_id", "source_content_items", ["project_id"])
    op.create_index("ix_source_content_items_project_file_id", "source_content_items", ["project_file_id"])
    op.create_index("ix_source_content_items_content_type", "source_content_items", ["content_type"])
    op.create_index("ix_source_content_items_source_order", "source_content_items", ["source_order"])
    op.create_index("ix_source_content_items_status", "source_content_items", ["status"])

    # --- lesson_source_items ------------------------------------------------------
    op.create_table(
        "lesson_source_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "lesson_content_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("generated_contents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("source_content_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("coverage_type", sa.String(length=20), nullable=False, server_default="planned"),
        sa.Column("coverage_notes", sa.Text(), nullable=True),
        sa.Column("coverage_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("source_order_in_lesson", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "lesson_content_id", "source_item_id", name="uq_lesson_source_items_lesson_source"
        ),
    )
    op.create_index("ix_lesson_source_items_lesson_content_id", "lesson_source_items", ["lesson_content_id"])
    op.create_index("ix_lesson_source_items_source_item_id", "lesson_source_items", ["source_item_id"])
    op.create_index("ix_lesson_source_items_coverage_type", "lesson_source_items", ["coverage_type"])

    # --- lesson_generations ---------------------------------------------------
    op.create_table(
        "lesson_generations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "lesson_content_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("generated_contents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("generated_content", sa.Text(), nullable=True),
        sa.Column("structured_content", postgresql.JSONB(), nullable=True),
        sa.Column("word_count", sa.Integer(), nullable=True),
        sa.Column("estimated_duration_seconds", sa.Integer(), nullable=True),
        sa.Column("source_item_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("generation_status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("validation_status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("model_name", sa.String(length=100), nullable=True),
        sa.Column("prompt_version", sa.String(length=50), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("lesson_content_id", "version", name="uq_lesson_generations_lesson_version"),
    )
    op.create_index("ix_lesson_generations_lesson_content_id", "lesson_generations", ["lesson_content_id"])
    op.create_index("ix_lesson_generations_generation_status", "lesson_generations", ["generation_status"])
    op.create_index("ix_lesson_generations_validation_status", "lesson_generations", ["validation_status"])

    # --- course_coverage_reports ---------------------------------------------------
    op.create_table(
        "course_coverage_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("total_source_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("covered_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("partially_covered_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("uncovered_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("coverage_percentage", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("unsupported_claims", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_violations", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicate_content_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fidelity_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("report_data", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("project_id", "version", name="uq_course_coverage_reports_project_version"),
    )
    op.create_index("ix_course_coverage_reports_project_id", "course_coverage_reports", ["project_id"])
    op.create_index("ix_course_coverage_reports_status", "course_coverage_reports", ["status"])

    # --- processing_jobs: extensao para jobs desta fase (reuso do sistema existente) ---
    op.add_column(
        "processing_jobs",
        sa.Column(
            "project_file_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("project_files.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "processing_jobs",
        sa.Column(
            "lesson_content_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("generated_contents.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column("processing_jobs", sa.Column("total_items", sa.Integer(), nullable=True))
    op.add_column("processing_jobs", sa.Column("processed_items", sa.Integer(), nullable=True))
    op.add_column("processing_jobs", sa.Column("failed_items", sa.Integer(), nullable=True))
    op.add_column("processing_jobs", sa.Column("current_item", sa.String(length=255), nullable=True))
    op.create_index("ix_processing_jobs_project_file_id", "processing_jobs", ["project_file_id"])
    op.create_index("ix_processing_jobs_lesson_content_id", "processing_jobs", ["lesson_content_id"])


def downgrade() -> None:
    op.drop_index("ix_processing_jobs_lesson_content_id", table_name="processing_jobs")
    op.drop_index("ix_processing_jobs_project_file_id", table_name="processing_jobs")
    op.drop_column("processing_jobs", "current_item")
    op.drop_column("processing_jobs", "failed_items")
    op.drop_column("processing_jobs", "processed_items")
    op.drop_column("processing_jobs", "total_items")
    op.drop_column("processing_jobs", "lesson_content_id")
    op.drop_column("processing_jobs", "project_file_id")

    op.drop_index("ix_course_coverage_reports_status", table_name="course_coverage_reports")
    op.drop_index("ix_course_coverage_reports_project_id", table_name="course_coverage_reports")
    op.drop_table("course_coverage_reports")

    op.drop_index("ix_lesson_generations_validation_status", table_name="lesson_generations")
    op.drop_index("ix_lesson_generations_generation_status", table_name="lesson_generations")
    op.drop_index("ix_lesson_generations_lesson_content_id", table_name="lesson_generations")
    op.drop_table("lesson_generations")

    op.drop_index("ix_lesson_source_items_coverage_type", table_name="lesson_source_items")
    op.drop_index("ix_lesson_source_items_source_item_id", table_name="lesson_source_items")
    op.drop_index("ix_lesson_source_items_lesson_content_id", table_name="lesson_source_items")
    op.drop_table("lesson_source_items")

    op.drop_index("ix_source_content_items_status", table_name="source_content_items")
    op.drop_index("ix_source_content_items_source_order", table_name="source_content_items")
    op.drop_index("ix_source_content_items_content_type", table_name="source_content_items")
    op.drop_index("ix_source_content_items_project_file_id", table_name="source_content_items")
    op.drop_index("ix_source_content_items_project_id", table_name="source_content_items")
    op.drop_table("source_content_items")
