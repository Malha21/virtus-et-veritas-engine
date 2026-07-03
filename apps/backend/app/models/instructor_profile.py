import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class InstructorProfile(Base):
    __tablename__ = "instructor_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    teaching_style: Mapped[str | None] = mapped_column(Text, nullable=True)
    voice_provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    voice_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    voice_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    voice_sample_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar_provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    avatar_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_style: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar_image_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    consent_voice_clone: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    consent_avatar_use: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    consent_terms_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    consent_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=True,
    )
