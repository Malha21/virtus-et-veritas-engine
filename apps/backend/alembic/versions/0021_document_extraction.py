"""fase 19.2 - extracao estruturada do documento (document_pages, document_blocks)

Cria a base de rastreabilidade documento -> pagina -> bloco -> texto original:

- document_pages: uma linha por pagina extraida de um project_file, preservando
  raw_text (original) e normalized_text (normalizado) separadamente;
- document_blocks: segmentacao heuristica de cada pagina em blocos (titulo,
  paragrafo, lista, tabela, cabecalho/rodape repetido, etc.), com ordem de
  leitura e codigo rastreavel (ex: P0007-B0002).

Revision ID: 0021_document_extraction
Revises: 0020_fidelity_coverage_engine
Create Date: 2026-07-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0021_document_extraction"
down_revision: str | None = "0020_fidelity_coverage_engine"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- document_pages ---------------------------------------------------
    op.create_table(
        "document_pages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_file_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("project_files.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("normalized_text", sa.Text(), nullable=True),
        sa.Column("character_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("word_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("extraction_status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("extraction_method", sa.String(length=50), nullable=True),
        sa.Column("has_text", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("requires_ocr", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("project_file_id", "page_number", name="uq_document_pages_file_page"),
        sa.CheckConstraint("page_number > 0", name="ck_document_pages_page_number_positive"),
    )
    op.create_index("ix_document_pages_project_file_id", "document_pages", ["project_file_id"])
    op.create_index("ix_document_pages_page_number", "document_pages", ["page_number"])
    op.create_index("ix_document_pages_extraction_status", "document_pages", ["extraction_status"])

    # --- document_blocks ---------------------------------------------------
    op.create_table(
        "document_blocks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_file_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("project_files.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "page_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("document_pages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("block_code", sa.String(length=30), nullable=False),
        sa.Column("block_type", sa.String(length=30), nullable=False, server_default="unknown"),
        sa.Column("block_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=True),
        sa.Column("bounding_box", postgresql.JSONB(), nullable=True),
        sa.Column("confidence_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("project_file_id", "block_code", name="uq_document_blocks_file_block_code"),
        sa.UniqueConstraint("page_id", "block_order", name="uq_document_blocks_page_order"),
        sa.CheckConstraint("block_order >= 0", name="ck_document_blocks_order_non_negative"),
        sa.CheckConstraint(
            "confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 100)",
            name="ck_document_blocks_confidence_range",
        ),
    )
    op.create_index("ix_document_blocks_project_file_id", "document_blocks", ["project_file_id"])
    op.create_index("ix_document_blocks_page_id", "document_blocks", ["page_id"])
    op.create_index("ix_document_blocks_block_type", "document_blocks", ["block_type"])


def downgrade() -> None:
    op.drop_index("ix_document_blocks_block_type", table_name="document_blocks")
    op.drop_index("ix_document_blocks_page_id", table_name="document_blocks")
    op.drop_index("ix_document_blocks_project_file_id", table_name="document_blocks")
    op.drop_table("document_blocks")

    op.drop_index("ix_document_pages_extraction_status", table_name="document_pages")
    op.drop_index("ix_document_pages_page_number", table_name="document_pages")
    op.drop_index("ix_document_pages_project_file_id", table_name="document_pages")
    op.drop_table("document_pages")
