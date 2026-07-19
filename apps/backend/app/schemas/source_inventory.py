from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.schemas.source_content_item import (
    SOURCE_CONTENT_ITEM_CONTENT_TYPES,
    SOURCE_CONTENT_ITEM_IMPORTANCE_LEVELS,
    SourceContentItemResponse,
)

REPROCESS_MODES = {
    "generate_if_missing",
    "reprocess_failed",
    "reprocess_pages",
    "full_rebuild",
    "validate_only",
}

DEPENDENCY_TYPES = {
    "explains",
    "exemplifies",
    "continues",
    "qualifies",
    "contradicts",
    "depends_on",
    "exception_to",
    "part_of",
}


class SourceInventoryGenerateRequest(BaseModel):
    force: bool = False
    continue_with_alerts: bool = False


class SourceInventoryReprocessRequest(BaseModel):
    mode: str = "reprocess_failed"
    page_numbers: list[int] | None = None
    continue_with_alerts: bool = False

    @model_validator(mode="after")
    def validate_mode(self) -> "SourceInventoryReprocessRequest":
        if self.mode not in REPROCESS_MODES:
            raise ValueError(f"mode invalido: {self.mode}")
        if self.mode == "reprocess_pages" and not self.page_numbers:
            raise ValueError("page_numbers e obrigatorio quando mode='reprocess_pages'.")
        if self.page_numbers is not None and any(p <= 0 for p in self.page_numbers):
            raise ValueError("page_numbers deve conter apenas valores maiores que zero.")
        return self


class SourceInventoryItemManualUpdate(BaseModel):
    """Edicao humana de um item do inventario. source_text original nao e editavel aqui
    de proposito (rastreabilidade com o documento fonte deve ser preservada)."""

    title: str | None = Field(default=None, min_length=1, max_length=500)
    normalized_content: str | None = Field(default=None, min_length=1)
    content_type: str | None = None
    importance: str | None = None
    review_note: str | None = None

    @model_validator(mode="after")
    def validate_enums(self) -> "SourceInventoryItemManualUpdate":
        if self.content_type is not None and self.content_type not in SOURCE_CONTENT_ITEM_CONTENT_TYPES:
            raise ValueError(f"content_type invalido: {self.content_type}")
        if self.importance is not None and self.importance not in SOURCE_CONTENT_ITEM_IMPORTANCE_LEVELS:
            raise ValueError(f"importance invalido: {self.importance}")
        return self


class SourceContentItemBlockResponse(BaseModel):
    id: UUID
    source_item_id: UUID
    block_id: UUID
    block_code: str
    page_number: int
    source_order: int
    is_primary: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class SourceItemDependencyResponse(BaseModel):
    id: UUID
    source_item_id: UUID
    depends_on_source_item_id: UUID
    dependency_type: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SourceContentItemDetailResponse(SourceContentItemResponse):
    blocks: list[SourceContentItemBlockResponse] = []
    dependencies: list[SourceItemDependencyResponse] = []
    dependents: list[SourceItemDependencyResponse] = []


class SourceInventorySummary(BaseModel):
    project_id: UUID
    project_file_id: UUID
    status: str = "not_started"
    inventory_version: int = 0
    total_pages: int = 0
    pages_processed: int = 0
    pages_not_processed: int = 0
    pages_requires_ocr: int = 0
    total_blocks: int = 0
    blocks_analyzed: int = 0
    blocks_ignored: int = 0
    total_chunks: int = 0
    chunks_completed: int = 0
    chunks_failed: int = 0
    total_items: int = 0
    items_by_type: dict[str, int] = {}
    items_by_importance: dict[str, int] = {}
    possible_duplicates: int = 0
    fragmented_items: int = 0
    requires_review_items: int = 0
    approved_items: int = 0
    rejected_items: int = 0
    page_coverage_percentage: float = 0.0
    block_coverage_percentage: float = 0.0
    model_name: str | None = None
    prompt_version: str | None = None
    generated_at: datetime | None = None


class InventoryValidationIssue(BaseModel):
    source_item_id: UUID | None = None
    item_code: str | None = None
    issue_type: str
    message: str


class InventoryValidationResult(BaseModel):
    status: str
    total_items: int
    valid_items: int
    invalid_items: int
    issues: list[InventoryValidationIssue] = []
