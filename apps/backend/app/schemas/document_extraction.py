from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

REPROCESS_SCOPES = {"all", "failed", "requires_ocr", "page"}


class DocumentExtractionRequest(BaseModel):
    force: bool = False


class DocumentReprocessRequest(BaseModel):
    scope: str = "failed"
    page_number: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_scope(self) -> "DocumentReprocessRequest":
        if self.scope not in REPROCESS_SCOPES:
            raise ValueError(f"scope invalido: {self.scope}")
        if self.scope == "page" and self.page_number is None:
            raise ValueError("page_number e obrigatorio quando scope='page'.")
        return self


class DocumentExtractionSummary(BaseModel):
    project_file_id: UUID
    total_pages: int = Field(default=0, ge=0)
    extracted_pages: int = Field(default=0, ge=0)
    empty_pages: int = Field(default=0, ge=0)
    failed_pages: int = Field(default=0, ge=0)
    requires_ocr_pages: int = Field(default=0, ge=0)
    total_characters: int = Field(default=0, ge=0)
    total_words: int = Field(default=0, ge=0)
    total_blocks: int = Field(default=0, ge=0)
    blocks_by_type: dict[str, int] = {}
    extraction_method: str | None = None
    status: str = "not_started"
    last_extracted_at: datetime | None = None
