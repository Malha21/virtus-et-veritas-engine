from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

DOCUMENT_BLOCK_TYPES = {
    "title",
    "heading",
    "paragraph",
    "list_item",
    "table",
    "table_row",
    "image_caption",
    "footnote",
    "quotation",
    "page_header",
    "page_footer",
    "unknown",
}


class DocumentBlockBase(BaseModel):
    block_code: str = Field(min_length=1, max_length=30)
    block_type: str = "unknown"
    block_order: int = Field(default=0, ge=0)
    source_text: str = Field(min_length=1)
    normalized_text: str | None = None
    bounding_box: dict[str, Any] | None = None
    confidence_score: Decimal | None = Field(default=None, ge=0, le=100)
    metadata_json: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_block_type(self) -> "DocumentBlockBase":
        if self.block_type not in DOCUMENT_BLOCK_TYPES:
            raise ValueError(f"block_type invalido: {self.block_type}")
        return self


class DocumentBlockResponse(DocumentBlockBase):
    id: UUID
    project_file_id: UUID
    page_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentBlockListResponse(BaseModel):
    items: list[DocumentBlockResponse]


class DocumentBlockFilter(BaseModel):
    page_number: int | None = Field(default=None, gt=0)
    block_type: str | None = None
