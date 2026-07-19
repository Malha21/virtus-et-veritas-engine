from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

COVERAGE_PLAN_STATUSES = {
    "pending",
    "processing",
    "generated",
    "requires_review",
    "invalid",
    "ready_for_review",
    "approved",
    "stale",
    "failed",
}

COVERAGE_PLAN_MODULE_STATUSES = {"planned", "requires_review", "approved", "stale"}
COVERAGE_PLAN_LESSON_STATUSES = {"planned", "requires_review", "approved", "stale"}

COVERAGE_PLAN_REGENERATE_MODES = {
    "generate_if_missing",
    "regenerate_draft",
    "validate_only",
    "recalculate_estimates",
    "rebuild_from_inventory",
    "preserve_manual_changes",
}


class CoveragePlanGenerateRequest(BaseModel):
    force: bool = False
    continue_with_alerts: bool = False


class CoveragePlanRegenerateRequest(BaseModel):
    mode: str = "regenerate_draft"

    @model_validator(mode="after")
    def validate_mode(self) -> "CoveragePlanRegenerateRequest":
        if self.mode not in COVERAGE_PLAN_REGENERATE_MODES:
            raise ValueError(f"mode invalido: {self.mode}")
        return self


class CoveragePlanLessonSourceItemResponse(BaseModel):
    source_item_id: UUID
    item_code: str
    title: str
    content_type: str
    importance: str
    page_start: int | None
    page_end: int | None
    status: str
    coverage_type: str
    source_order_in_lesson: int
    is_required: bool
    coverage_notes: str | None = None

    model_config = ConfigDict(from_attributes=True)


class CoveragePlanLessonResponse(BaseModel):
    id: UUID
    coverage_plan_id: UUID
    module_id: UUID
    title: str
    description: str | None
    learning_objective: str | None
    lesson_order: int
    target_duration_minutes: Decimal | None
    estimated_duration_minutes: Decimal
    estimated_source_words: int
    estimated_explanation_words: int
    estimated_transition_words: int
    estimated_word_count: int
    source_item_count: int
    status: str
    plan_version: int
    requires_review: bool
    grouping_reason: str | None
    warnings_json: list[str] | None = None
    generated_content_id: UUID | None
    created_at: datetime
    updated_at: datetime
    source_items: list[CoveragePlanLessonSourceItemResponse] = []

    model_config = ConfigDict(from_attributes=True)


class CoveragePlanModuleResponse(BaseModel):
    id: UUID
    coverage_plan_id: UUID
    project_id: UUID
    title: str
    description: str | None
    learning_objective: str | None
    module_order: int
    estimated_total_minutes: Decimal
    estimated_total_words: int
    source_item_count: int
    status: str
    plan_version: int
    created_at: datetime
    updated_at: datetime
    lessons: list[CoveragePlanLessonResponse] = []

    model_config = ConfigDict(from_attributes=True)


class CoveragePlanResponse(BaseModel):
    id: UUID
    project_id: UUID
    project_file_id: UUID
    version: int
    status: str
    inventory_item_count: int
    total_modules: int
    total_lessons: int
    total_items: int
    mapped_items: int
    unmapped_items: int
    estimated_total_words: int
    estimated_total_minutes: Decimal
    model_name: str | None
    prompt_version: str | None
    settings_json: dict | None
    report_data: dict | None
    error_message: str | None
    approved_at: datetime | None
    approved_by: UUID | None
    created_at: datetime
    updated_at: datetime
    modules: list[CoveragePlanModuleResponse] = []

    model_config = ConfigDict(from_attributes=True)


class CoveragePlanVersionResponse(BaseModel):
    id: UUID
    version: int
    status: str
    total_modules: int
    total_lessons: int
    total_items: int
    mapped_items: int
    unmapped_items: int
    created_at: datetime
    approved_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class UnmappedSourceItemResponse(BaseModel):
    source_item_id: UUID
    item_code: str
    title: str
    content_type: str
    importance: str
    page_start: int | None
    page_end: int | None
    status: str
    reason: str
    recommended_action: str


class CoveragePlanSummary(BaseModel):
    project_id: UUID
    project_file_id: UUID
    status: str = "not_started"
    version: int = 0
    total_modules: int = 0
    total_lessons: int = 0
    total_items: int = 0
    mapped_items: int = 0
    unmapped_items: int = 0
    lessons_over_limit: int = 0
    lessons_under_recommended_duration: int = 0
    modules_without_lessons: int = 0
    lessons_without_sources: int = 0
    dependency_violations: int = 0
    requires_review_items: int = 0
    pages_requires_ocr: int = 0
    estimated_total_words: int = 0
    estimated_total_minutes: Decimal = Decimal("0")
    model_name: str | None = None
    prompt_version: str | None = None
    generated_at: datetime | None = None
    approved_at: datetime | None = None
    warnings: list[str] = []


class CoveragePlanValidationIssue(BaseModel):
    issue_type: str
    severity: str = "warning"
    message: str
    module_id: UUID | None = None
    lesson_id: UUID | None = None
    source_item_id: UUID | None = None


class CoveragePlanValidationResponse(BaseModel):
    status: str
    total_source_items: int
    mapped_items: int
    unmapped_items: int
    duplicate_mappings: int
    lessons_over_limit: int
    lessons_under_recommended_duration: int
    modules_without_lessons: int
    lessons_without_sources: int
    dependency_violations: int
    requires_review_source_items: int
    pages_requires_ocr: int
    issues: list[CoveragePlanValidationIssue] = []
    warnings: list[str] = []


class CoveragePlanModuleUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    learning_objective: str | None = None
    module_order: int | None = Field(default=None, ge=0)
    status: str | None = None

    @model_validator(mode="after")
    def validate_status(self) -> "CoveragePlanModuleUpdate":
        if self.status is not None and self.status not in COVERAGE_PLAN_MODULE_STATUSES:
            raise ValueError(f"status invalido: {self.status}")
        return self


class CoveragePlanLessonUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    learning_objective: str | None = None
    lesson_order: int | None = Field(default=None, ge=0)
    module_id: UUID | None = None
    status: str | None = None

    @model_validator(mode="after")
    def validate_status(self) -> "CoveragePlanLessonUpdate":
        if self.status is not None and self.status not in COVERAGE_PLAN_LESSON_STATUSES:
            raise ValueError(f"status invalido: {self.status}")
        return self


class CoveragePlanLessonSplitRequest(BaseModel):
    first_title: str = Field(min_length=1, max_length=500)
    second_title: str = Field(min_length=1, max_length=500)
    first_source_item_ids: list[UUID] = Field(min_length=1)
    second_source_item_ids: list[UUID] = Field(min_length=1)
    first_description: str | None = None
    second_description: str | None = None
    first_learning_objective: str | None = None
    second_learning_objective: str | None = None

    @model_validator(mode="after")
    def validate_disjoint(self) -> "CoveragePlanLessonSplitRequest":
        first = set(self.first_source_item_ids)
        second = set(self.second_source_item_ids)
        if first & second:
            raise ValueError("um source_item_id nao pode aparecer nas duas metades da divisao.")
        return self


class CoveragePlanLessonMergeRequest(BaseModel):
    lesson_ids: list[UUID] = Field(min_length=2)
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    learning_objective: str | None = None


class CoveragePlanLessonSourceItemAddRequest(BaseModel):
    source_item_id: UUID
    coverage_type: str = "planned_supporting"
    is_required: bool = True
    source_order_in_lesson: int = Field(default=0, ge=0)
    coverage_notes: str | None = None


class CoveragePlanApprovalRequest(BaseModel):
    confirm: bool = True
