import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CoveragePlanLesson(Base):
    """Aula planejada do plano de cobertura (fase 19.4). Ainda nao e o roteiro (isso e a
    fase 19.5): apenas o recorte de source_content_items que a aula devera cobrir, com
    duracao/palavras estimadas. Ligada aos itens via lesson_source_items.coverage_plan_lesson_id."""

    __tablename__ = "coverage_plan_lessons"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    coverage_plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("coverage_plans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    module_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("coverage_plan_modules.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    learning_objective: Mapped[str | None] = mapped_column(Text, nullable=True)
    lesson_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0", index=True)
    target_duration_minutes: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    estimated_duration_minutes: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("0"), server_default="0"
    )
    estimated_source_words: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    estimated_explanation_words: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    estimated_transition_words: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    estimated_word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    source_item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="planned", server_default="planned", index=True
    )
    plan_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    requires_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    grouping_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    warnings_json: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    generated_content_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("generated_contents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
