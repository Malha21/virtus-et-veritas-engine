import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LessonSourceItem(Base):
    """Relaciona um source_content_item a uma aula (generated_contents.content_type='lesson_script')."""

    __tablename__ = "lesson_source_items"
    __table_args__ = (
        UniqueConstraint(
            "lesson_content_id", "source_item_id", name="uq_lesson_source_items_lesson_source"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    lesson_content_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("generated_contents.id", ondelete="CASCADE"),
        nullable=False,
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
