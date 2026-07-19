import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CoveragePlanModule(Base):
    """Unidade tematica coerente do plano de cobertura (fase 19.4): agrupa aulas
    (CoveragePlanLesson) que cobrem um conjunto relacionado de source_content_items."""

    __tablename__ = "coverage_plan_modules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    coverage_plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("coverage_plans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    learning_objective: Mapped[str | None] = mapped_column(Text, nullable=True)
    module_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0", index=True)
    estimated_total_minutes: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), nullable=False, default=Decimal("0"), server_default="0"
    )
    estimated_total_words: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    source_item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="planned", server_default="planned", index=True
    )
    plan_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
