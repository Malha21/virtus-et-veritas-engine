from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.document_block import DocumentBlockResponse

DOCUMENT_PAGE_EXTRACTION_STATUSES = {
    "pending",
    "processing",
    "extracted",
    "empty",
    "failed",
    "requires_ocr",
    "reviewed",
}


class DocumentPageBase(BaseModel):
    page_number: int = Field(gt=0)
    raw_text: str | None = None
    normalized_text: str | None = None
    character_count: int = Field(default=0, ge=0)
    word_count: int = Field(default=0, ge=0)
    extraction_status: str = "pending"
    extraction_method: str | None = None
    has_text: bool = False
    requires_ocr: bool = False
    metadata_json: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_status(self) -> "DocumentPageBase":
        if self.extraction_status not in DOCUMENT_PAGE_EXTRACTION_STATUSES:
            raise ValueError(f"extraction_status invalido: {self.extraction_status}")
        return self


class DocumentPageResponse(DocumentPageBase):
    id: UUID
    project_file_id: UUID
    block_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentPageDetailResponse(DocumentPageResponse):
    blocks: list[DocumentBlockResponse] = []


class DocumentPageListResponse(BaseModel):
    items: list[DocumentPageResponse]
    page: int
    page_size: int
    total: int
    total_pages: int


class DocumentPageFilter(BaseModel):
    extraction_status: str | None = None
    requires_ocr: bool | None = None
