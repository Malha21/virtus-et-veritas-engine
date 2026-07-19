"""fase 19.3 - associacoes do inventario integral do documento

Cria a rastreabilidade item SRC <-> bloco de origem (varios-para-varios) e a
relacao opcional de dependencia entre itens do inventario (ex: excecao depende
de regra). source_content_items (fase 19.1), document_pages e document_blocks
(fase 19.2) ja existem e nao sao alterados de forma destrutiva.

Revision ID: 0022_inventory_item_assoc
Revises: 0021_document_extraction
Create Date: 2026-07-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0022_inventory_item_assoc"
down_revision: str | None = "0021_document_extraction"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- source_content_item_blocks ---------------------------------------------------
    op.create_table(
        "source_content_item_blocks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "source_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("source_content_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "block_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("document_blocks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("source_item_id", "block_id", name="uq_source_content_item_blocks_item_block"),
    )
    op.create_index(
        "ix_source_content_item_blocks_source_item_id", "source_content_item_blocks", ["source_item_id"]
    )
    op.create_index("ix_source_content_item_blocks_block_id", "source_content_item_blocks", ["block_id"])

    # --- source_content_item_dependencies ---------------------------------------------------
    op.create_table(
        "source_content_item_dependencies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "source_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("source_content_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "depends_on_source_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("source_content_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("dependency_type", sa.String(length=30), nullable=False, server_default="depends_on"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "source_item_id",
            "depends_on_source_item_id",
            "dependency_type",
            name="uq_source_content_item_dependencies_pair_type",
        ),
        sa.CheckConstraint(
            "source_item_id != depends_on_source_item_id",
            name="ck_source_content_item_dependencies_no_self_reference",
        ),
    )
    op.create_index(
        "ix_source_content_item_dependencies_source_item_id",
        "source_content_item_dependencies",
        ["source_item_id"],
    )
    op.create_index(
        "ix_source_content_item_dependencies_depends_on_source_item_id",
        "source_content_item_dependencies",
        ["depends_on_source_item_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_source_content_item_dependencies_depends_on_source_item_id",
        table_name="source_content_item_dependencies",
    )
    op.drop_index(
        "ix_source_content_item_dependencies_source_item_id", table_name="source_content_item_dependencies"
    )
    op.drop_table("source_content_item_dependencies")

    op.drop_index("ix_source_content_item_blocks_block_id", table_name="source_content_item_blocks")
    op.drop_index("ix_source_content_item_blocks_source_item_id", table_name="source_content_item_blocks")
    op.drop_table("source_content_item_blocks")
