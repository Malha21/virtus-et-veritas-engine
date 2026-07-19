"""Schemas de validacao da resposta estruturada da IA (nao expostos via API)."""

from pydantic import BaseModel, Field, model_validator

from app.schemas.source_content_item import (
    SOURCE_CONTENT_ITEM_CONTENT_TYPES,
    SOURCE_CONTENT_ITEM_IMPORTANCE_LEVELS,
)


class AIInventoryItemResponse(BaseModel):
    temporary_id: str = Field(min_length=1, max_length=50)
    title: str = Field(min_length=1, max_length=500)
    normalized_content: str = Field(min_length=1)
    source_text: str = Field(min_length=1)
    content_type: str
    importance: str
    page_start: int = Field(gt=0)
    page_end: int = Field(gt=0)
    source_block_codes: list[str] = Field(default_factory=list)
    source_order: int = Field(ge=0)
    depends_on_temporary_ids: list[str] = Field(default_factory=list)
    possible_duplicate: bool = False
    possible_fragment: bool = False
    requires_review: bool = False
    review_reason: str | None = None

    @model_validator(mode="after")
    def validate_fields(self) -> "AIInventoryItemResponse":
        if self.page_end < self.page_start:
            raise ValueError("page_end nao pode ser menor que page_start.")
        if self.content_type not in SOURCE_CONTENT_ITEM_CONTENT_TYPES:
            raise ValueError(f"content_type invalido: {self.content_type}")
        if self.importance not in SOURCE_CONTENT_ITEM_IMPORTANCE_LEVELS:
            raise ValueError(f"importance invalido: {self.importance}")
        return self


class AIInventoryChunkResponse(BaseModel):
    chunk_id: str
    items: list[AIInventoryItemResponse] = Field(default_factory=list)
    chunk_warnings: list[str] = Field(default_factory=list)
    unprocessed_content: list[str] = Field(default_factory=list)


class AICoverageMissingContent(BaseModel):
    excerpt: str
    reason: str = ""


class AICoverageCheckResponse(BaseModel):
    chunk_id: str
    coverage_status: str = "complete"
    missing_content: list[AICoverageMissingContent] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
