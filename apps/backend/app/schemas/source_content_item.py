from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

SOURCE_CONTENT_ITEM_CONTENT_TYPES = {
    # fase 19.1
    "concept",
    "definition",
    "explanation",
    "procedure",
    "example",
    "list",
    "argument",
    "conclusion",
    "observation",
    "exercise",
    "table",
    "image_caption",
    "quotation",
    "other",
    # ampliado de forma nao destrutiva na fase 19.3
    "fact",
    "step",
    "rule",
    "exception",
    "case",
    "classification",
    "comparison",
    "distinction",
    "cause",
    "consequence",
    "warning",
    "recommendation",
    "question",
    "reference",
}

SOURCE_CONTENT_ITEM_IMPORTANCE_LEVELS = {"essential", "relevant", "complementary"}

SOURCE_CONTENT_ITEM_STATUSES = {
    # fase 19.1
    "pending",
    "mapped",
    "reviewed",
    "approved",
    "rejected",
    # ampliado de forma nao destrutiva na fase 19.3
    "generated",
    "validated",
    "possible_duplicate",
    "fragmented",
    "requires_review",
}


class SourceContentItemBase(BaseModel):
    item_code: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=500)
    source_text: str = Field(min_length=1)
    normalized_content: str | None = None
    content_type: str = "other"
    page_start: int | None = Field(default=None, gt=0)
    page_end: int | None = Field(default=None, gt=0)
    source_order: int = Field(default=0, ge=0)
    importance: str = "relevant"
    status: str = "pending"
    metadata_json: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_pages(self) -> "SourceContentItemBase":
        if self.page_start is not None and self.page_end is not None and self.page_end < self.page_start:
            raise ValueError("page_end nao pode ser menor que page_start.")
        if self.content_type not in SOURCE_CONTENT_ITEM_CONTENT_TYPES:
            raise ValueError(f"content_type invalido: {self.content_type}")
        if self.importance not in SOURCE_CONTENT_ITEM_IMPORTANCE_LEVELS:
            raise ValueError(f"importance invalido: {self.importance}")
        if self.status not in SOURCE_CONTENT_ITEM_STATUSES:
            raise ValueError(f"status invalido: {self.status}")
        return self


class SourceContentItemCreate(SourceContentItemBase):
    project_id: UUID
    project_file_id: UUID


class SourceContentItemUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    source_text: str | None = Field(default=None, min_length=1)
    normalized_content: str | None = None
    content_type: str | None = None
    page_start: int | None = Field(default=None, gt=0)
    page_end: int | None = Field(default=None, gt=0)
    source_order: int | None = Field(default=None, ge=0)
    importance: str | None = None
    status: str | None = None
    metadata_json: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_optional_fields(self) -> "SourceContentItemUpdate":
        if self.page_start is not None and self.page_end is not None and self.page_end < self.page_start:
            raise ValueError("page_end nao pode ser menor que page_start.")
        if self.content_type is not None and self.content_type not in SOURCE_CONTENT_ITEM_CONTENT_TYPES:
            raise ValueError(f"content_type invalido: {self.content_type}")
        if self.importance is not None and self.importance not in SOURCE_CONTENT_ITEM_IMPORTANCE_LEVELS:
            raise ValueError(f"importance invalido: {self.importance}")
        if self.status is not None and self.status not in SOURCE_CONTENT_ITEM_STATUSES:
            raise ValueError(f"status invalido: {self.status}")
        return self


class SourceContentItemResponse(SourceContentItemBase):
    id: UUID
    project_id: UUID
    project_file_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SourceContentItemListResponse(BaseModel):
    items: list[SourceContentItemResponse]
    page: int
    page_size: int
    total: int
    total_pages: int


class SourceContentItemFilter(BaseModel):
    project_id: UUID | None = None
    project_file_id: UUID | None = None
    content_type: str | None = None
    status: str | None = None
    importance: str | None = None
