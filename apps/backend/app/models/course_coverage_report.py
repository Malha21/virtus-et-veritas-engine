import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CourseCoverageReport(Base):
    """Relatorio (append-only) de auditoria de cobertura e fidelidade de um curso (project)."""

    __tablename__ = "course_coverage_reports"
    __table_args__ = (
        UniqueConstraint("project_id", "version", name="uq_course_coverage_reports_project_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    total_source_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    covered_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    partially_covered_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    uncovered_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    coverage_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=0, server_default="0"
    )
    unsupported_claims: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    duration_violations: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    duplicate_content_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    fidelity_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    report_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
        server_default="pending",
        index=True,
    )
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
