import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LessonGeneration(Base):
    """Versao (append-only) de conteudo gerado para uma aula.

    Fase 19.1: `lesson_content_id` (generated_contents.id) era a unica referencia
    (sistema legado de roteiro). Fase 19.5: `coverage_plan_lesson_id` liga a versao
    diretamente a aula planejada pelo Plano de Cobertura (fase 19.4); o servico de
    geracao continua preenchendo `lesson_content_id` tambem (um GeneratedContent
    content_type='coverage_lesson_script' e criado na primeira geracao da aula, cf.
    CoveragePlanLesson.generated_content_id), preservando a constraint original.
    """

    __tablename__ = "lesson_generations"
    __table_args__ = (
        UniqueConstraint("lesson_content_id", "version", name="uq_lesson_generations_lesson_version"),
        UniqueConstraint(
            "coverage_plan_lesson_id", "version", name="uq_lesson_generations_plan_lesson_version"
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
    coverage_plan_lesson_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("coverage_plan_lessons.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    generated_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    structured_content: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    word_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    generation_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
        index=True,
    )
    validation_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
        index=True,
    )
    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- fase 19.5: fingerprint / staleness ---------------------------------
    coverage_plan_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_stale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    # --- fase 19.5: limite de duracao ---------------------------------------
    requires_split: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    split_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- fase 19.5: cobertura declarada (revalidada pelo servico) -----------
    covered_source_items_json: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    uncovered_source_items_json: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    source_pages_json: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    source_block_codes_json: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    unsupported_claims_json: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    warnings_json: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)

    # --- fase 19.5: regeneracao / edicao -------------------------------------
    feedback_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_manual_edit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    # --- fase 19.5: observabilidade da chamada de IA -------------------------
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    temperature: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)
    provider_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # --- fase 19.5: aprovacao / rejeicao por versao --------------------------
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

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
