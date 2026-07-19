from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.coverage_plan import CoveragePlanLessonSourceItemResponse

LESSON_GENERATION_STATUSES = {
    "pending",
    "queued",
    "processing",
    "completed",
    "failed",
    "requires_review",
    "requires_split",
    "approved",
    "rejected",
    "stale",
    "cancelled",
}

LESSON_GENERATION_VALIDATION_STATUSES = {
    "pending",
    "valid",
    "invalid",
    "requires_review",
    "requires_split",
    "approved",
}

# Fase 19.5: modos aceitos por /generate e /regenerate (uma aula por chamada, nunca o
# modulo/curso inteiro). preserve_manual_edits e usado pela geracao em lote, para nunca
# sobrescrever silenciosamente uma versao editada manualmente ou ja aprovada.
LESSON_GENERATION_MODES = {
    "generate_if_missing",
    "regenerate",
    "regenerate_with_feedback",
    "validate_only",
    "repair_missing_items",
    "preserve_manual_edits",
}

# Subconjunto aceito pelo endpoint generico /regenerate (repair/validate tem
# endpoints proprios e dedicados; preserve_manual_edits/generate_if_missing sao
# uso interno da geracao em lote).
LESSON_REGENERATE_ALLOWED_MODES = {"regenerate", "regenerate_with_feedback"}


class LessonGenerationBase(BaseModel):
    version: int = Field(default=1, gt=0)
    generated_content: str | None = None
    structured_content: dict[str, Any] | None = None
    word_count: int | None = Field(default=None, ge=0)
    estimated_duration_seconds: int | None = Field(default=None, ge=0)
    source_item_count: int = Field(default=0, ge=0)
    generation_status: str = "pending"
    validation_status: str = "pending"
    model_name: str | None = None
    prompt_version: str | None = None
    error_message: str | None = None

    coverage_plan_version: int | None = None
    source_fingerprint: str | None = None
    is_stale: bool = False

    requires_split: bool = False
    split_reason: str | None = None

    covered_source_items_json: list[dict[str, Any]] | None = None
    uncovered_source_items_json: list[dict[str, Any]] | None = None
    source_pages_json: list[int] | None = None
    source_block_codes_json: list[str] | None = None
    unsupported_claims_json: list[str] | None = None
    warnings_json: list[str] | None = None

    feedback_notes: str | None = None
    is_manual_edit: bool = False

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost: Decimal | None = None
    temperature: Decimal | None = None
    provider_name: str | None = None

    approved_at: datetime | None = None
    approved_by: UUID | None = None
    rejected_at: datetime | None = None
    rejected_by: UUID | None = None
    rejection_reason: str | None = None

    @model_validator(mode="after")
    def validate_statuses(self) -> "LessonGenerationBase":
        if self.generation_status not in LESSON_GENERATION_STATUSES:
            raise ValueError(f"generation_status invalido: {self.generation_status}")
        if self.validation_status not in LESSON_GENERATION_VALIDATION_STATUSES:
            raise ValueError(f"validation_status invalido: {self.validation_status}")
        return self


class LessonGenerationCreate(LessonGenerationBase):
    lesson_content_id: UUID
    coverage_plan_lesson_id: UUID | None = None


class LessonGenerationUpdate(BaseModel):
    """Edicao humana manual (fase 19.5): nunca sobrescreve a versao original -- o
    servico sempre cria uma nova versao a partir desta edicao."""

    generated_content: str = Field(min_length=1)
    structured_content: dict[str, Any] | None = None


class LessonGenerationResponse(LessonGenerationBase):
    id: UUID
    lesson_content_id: UUID
    coverage_plan_lesson_id: UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LessonGenerationDetail(LessonGenerationResponse):
    lesson_id: UUID
    lesson_title: str
    module_id: UUID
    module_title: str
    target_duration_minutes: Decimal | None = None
    is_approved_version: bool = False
    is_latest_version: bool = False
    source_items: list[CoveragePlanLessonSourceItemResponse] = []


class LessonGenerationListResponse(BaseModel):
    items: list[LessonGenerationResponse]
    latest_version: int | None = None
    approved_version: int | None = None


class LessonGenerationFilter(BaseModel):
    lesson_content_id: UUID | None = None
    coverage_plan_lesson_id: UUID | None = None
    generation_status: str | None = None
    validation_status: str | None = None


class LessonGenerationRequest(BaseModel):
    force: bool = False


class LessonRegenerationRequest(BaseModel):
    mode: str = "regenerate"
    feedback: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_mode(self) -> "LessonRegenerationRequest":
        if self.mode not in LESSON_REGENERATE_ALLOWED_MODES:
            raise ValueError(f"mode invalido: {self.mode}")
        if self.mode == "regenerate_with_feedback" and not (self.feedback and self.feedback.strip()):
            raise ValueError("feedback e obrigatorio quando mode='regenerate_with_feedback'.")
        return self


class LessonGenerationValidationIssue(BaseModel):
    issue_type: str
    severity: str = "warning"
    message: str
    source_item_id: UUID | None = None


class LessonGenerationValidationResponse(BaseModel):
    status: str
    covered_item_count: int
    expected_item_count: int
    missing_required_item_codes: list[str] = []
    extra_item_codes: list[str] = []
    requires_split: bool = False
    split_reason: str | None = None
    issues: list[LessonGenerationValidationIssue] = []
    warnings: list[str] = []


class LessonGenerationRepairRequest(BaseModel):
    missing_source_item_ids: list[UUID] = Field(min_length=1)
    validation_notes: str | None = Field(default=None, max_length=2000)


class LessonGenerationApprovalRequest(BaseModel):
    confirm: bool = True


class LessonGenerationRejectionRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class GenerateAllLessonsRequest(BaseModel):
    force: bool = False
    only_pending: bool = True


class CourseLessonGenerationSummary(BaseModel):
    total_lessons: int = 0
    completed_lessons: int = 0
    failed_lessons: int = 0
    skipped_lessons: int = 0
    approved_lessons: int = 0
    stale_lessons: int = 0
    current_lesson: str | None = None
    progress_percentage: int = 0


class GenerateAllLessonsResponse(BaseModel):
    job_id: UUID
    status: str
    summary: CourseLessonGenerationSummary
