import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SourceContentItemDependency(Base):
    """Relacao opcional entre dois source_content_items (ex: excecao depende de regra)."""

    __tablename__ = "source_content_item_dependencies"
    __table_args__ = (
        UniqueConstraint(
            "source_item_id",
            "depends_on_source_item_id",
            "dependency_type",
            name="uq_source_content_item_dependencies_pair_type",
        ),
        CheckConstraint(
            "source_item_id != depends_on_source_item_id",
            name="ck_source_content_item_dependencies_no_self_reference",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    source_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_content_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    depends_on_source_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_content_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dependency_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="depends_on",
        server_default="depends_on",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
