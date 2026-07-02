"""create generated contents and ai requests

Revision ID: 0005_ai_content
Revises: 0004_processing
Create Date: 2026-07-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_ai_content"
down_revision: str | None = "0004_processing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "generated_contents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("language", sa.String(length=20), server_default="pt-BR", nullable=False),
        sa.Column("content_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("content_text", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), server_default="generated", nullable=False),
        sa.Column("created_by_ai_provider_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_ai_provider_id"], ["ai_providers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_generated_contents_project_id"), "generated_contents", ["project_id"], unique=False)
    op.create_index(op.f("ix_generated_contents_organization_id"), "generated_contents", ["organization_id"], unique=False)
    op.create_index(op.f("ix_generated_contents_content_type"), "generated_contents", ["content_type"], unique=False)
    op.create_index(op.f("ix_generated_contents_status"), "generated_contents", ["status"], unique=False)

    op.create_table(
        "ai_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_type", sa.String(length=100), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=True),
        sa.Column("prompt_version", sa.String(length=80), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("estimated_cost", sa.Numeric(12, 6), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["processing_jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["provider_id"], ["ai_providers.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ai_requests_project_id"), "ai_requests", ["project_id"], unique=False)
    op.create_index(op.f("ix_ai_requests_job_id"), "ai_requests", ["job_id"], unique=False)
    op.create_index(op.f("ix_ai_requests_provider_id"), "ai_requests", ["provider_id"], unique=False)
    op.create_index(op.f("ix_ai_requests_request_type"), "ai_requests", ["request_type"], unique=False)
    op.create_index(op.f("ix_ai_requests_status"), "ai_requests", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ai_requests_status"), table_name="ai_requests")
    op.drop_index(op.f("ix_ai_requests_request_type"), table_name="ai_requests")
    op.drop_index(op.f("ix_ai_requests_provider_id"), table_name="ai_requests")
    op.drop_index(op.f("ix_ai_requests_job_id"), table_name="ai_requests")
    op.drop_index(op.f("ix_ai_requests_project_id"), table_name="ai_requests")
    op.drop_table("ai_requests")
    op.drop_index(op.f("ix_generated_contents_status"), table_name="generated_contents")
    op.drop_index(op.f("ix_generated_contents_content_type"), table_name="generated_contents")
    op.drop_index(op.f("ix_generated_contents_organization_id"), table_name="generated_contents")
    op.drop_index(op.f("ix_generated_contents_project_id"), table_name="generated_contents")
    op.drop_table("generated_contents")
