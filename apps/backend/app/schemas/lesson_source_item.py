from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

LESSON_SOURCE_ITEM_COVERAGE_TYPES = {
    "planned",
    "full",
    "partial",
    "missing",
    "supplemental",
    # ampliado de forma nao destrutiva na fase 19.4 (plano de cobertura): distingue a aula
    # principal de um item de usos complementares/retomadas antes de qualquer roteiro existir.
    "planned_primary",
    "planned_supporting",
    "planned_reference",
}


class LessonSourceItemBase(BaseModel):
    coverage_type: str = "planned"
    coverage_notes: str | None = None
    coverage_score: Decimal | None = Field(default=None, ge=0, le=100)
    source_order_in_lesson: int = Field(default=0, ge=0)
    is_required: bool = True

    @model_validator(mode="after")
    def validate_coverage_type(self) -> "LessonSourceItemBase":
        if self.coverage_type not in LESSON_SOURCE_ITEM_COVERAGE_TYPES:
            raise ValueError(f"coverage_type invalido: {self.coverage_type}")
        return self


class LessonSourceItemCreate(LessonSourceItemBase):
    lesson_content_id: UUID
    source_item_id: UUID


class LessonSourceItemUpdate(BaseModel):
    coverage_type: str | None = None
    coverage_notes: str | None = None
    coverage_score: Decimal | None = Field(default=None, ge=0, le=100)
    source_order_in_lesson: int | None = Field(default=None, ge=0)
    is_required: bool | None = None

    @model_validator(mode="after")
    def validate_coverage_type(self) -> "LessonSourceItemUpdate":
        if self.coverage_type is not None and self.coverage_type not in LESSON_SOURCE_ITEM_COVERAGE_TYPES:
            raise ValueError(f"coverage_type invalido: {self.coverage_type}")
        return self


class LessonSourceItemResponse(LessonSourceItemBase):
    id: UUID
    lesson_content_id: UUID
    source_item_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LessonSourceItemListResponse(BaseModel):
    items: list[LessonSourceItemResponse]


class LessonSourceItemFilter(BaseModel):
    lesson_content_id: UUID | None = None
    source_item_id: UUID | None = None
    coverage_type: str | None = None
    is_required: bool | None = None
