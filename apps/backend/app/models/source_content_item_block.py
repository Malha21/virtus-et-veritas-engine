import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SourceContentItemBlock(Base):
    """Associacao N:N entre um source_content_item e os document_blocks que o originaram.

    Necessaria porque um item do inventario pode ser composto por varios blocos
    (ex: um paragrafo dividido em duas paginas) e um bloco pode alimentar mais de
    um item (ex: uma tabela com duas informacoes distintas).
    """

    __tablename__ = "source_content_item_blocks"
    __table_args__ = (
        UniqueConstraint("source_item_id", "block_id", name="uq_source_content_item_blocks_item_block"),
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
    block_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_blocks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
