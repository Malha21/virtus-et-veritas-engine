import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LessonSourceItem(Base):
    """Relaciona um source_content_item a uma aula.

    Duas gerações de "aula" podem ser referenciadas, nunca as duas ao mesmo tempo:
    - lesson_content_id: aula do sistema legado (generated_contents.content_type='lesson_script');
    - coverage_plan_lesson_id: aula planejada pelo Plano de Cobertura (fase 19.4), antes de
      qualquer roteiro ser gerado (isso só acontece na fase 19.5).
    """

    __tablename__ = "lesson_source_items"
    __table_args__ = (
        UniqueConstraint(
            "lesson_content_id", "source_item_id", name="uq_lesson_source_items_lesson_source"
        ),
        UniqueConstraint(
            "coverage_plan_lesson_id", "source_item_id", name="uq_lesson_source_items_plan_lesson_source"
        ),
        CheckConstraint(
            "(lesson_content_id IS NOT NULL AND coverage_plan_lesson_id IS NULL) "
            "OR (lesson_content_id IS NULL AND coverage_plan_lesson_id IS NOT NULL)",
            name="ck_lesson_source_items_lesson_ref_xor",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    lesson_content_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("generated_contents.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    coverage_plan_lesson_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("coverage_plan_lessons.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    source_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_content_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    coverage_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="planned",
        server_default="planned",
        index=True,
    )
    coverage_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    coverage_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    source_order_in_lesson: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
