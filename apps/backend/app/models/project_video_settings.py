import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ProjectVideoSettings(Base):
    __tablename__ = "project_video_settings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    default_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    default_mock_avatar_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("generated_video_avatars.id", ondelete="SET NULL"),
        nullable=True,
    )
    default_heygen_avatar_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("generated_video_avatars.id", ondelete="SET NULL"),
        nullable=True,
    )
    default_did_avatar_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("generated_video_avatars.id", ondelete="SET NULL"),
        nullable=True,
    )
    default_sync_avatar_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("generated_video_avatars.id", ondelete="SET NULL"),
        nullable=True,
    )
    default_resolution: Mapped[str] = mapped_column(String(50), nullable=False, default="1080p", server_default="1080p")
    default_format: Mapped[str] = mapped_column(String(20), nullable=False, default="mp4", server_default="mp4")
    auto_download_completed_videos: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=True,
    )
