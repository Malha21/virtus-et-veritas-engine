import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CoveragePlan(Base):
    """Versao do plano de cobertura (fase 19.4): liga o inventario aprovado (fase 19.3)
    a estrutura pedagogica (modulos/aulas) que sera roteirizada na fase 19.5."""

    __tablename__ = "coverage_plans"
    __table_args__ = (UniqueConstraint("project_id", "version", name="uq_coverage_plans_project_version"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project_files.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="pending", server_default="pending", index=True
    )
    inventory_item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    inventory_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    total_modules: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    total_lessons: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    total_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    mapped_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    unmapped_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    estimated_total_words: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    estimated_total_minutes: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), nullable=False, default=Decimal("0"), server_default="0"
    )
    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    settings_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    report_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
