from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

COURSE_COVERAGE_REPORT_STATUSES = {
    "pending",
    "processing",
    "passed",
    "failed",
    "requires_review",
    "approved_with_exceptions",
}


class CourseCoverageReportBase(BaseModel):
    version: int = Field(default=1, gt=0)
    total_source_items: int = Field(default=0, ge=0)
    covered_items: int = Field(default=0, ge=0)
    partially_covered_items: int = Field(default=0, ge=0)
    uncovered_items: int = Field(default=0, ge=0)
    coverage_percentage: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    unsupported_claims: int = Field(default=0, ge=0)
    duration_violations: int = Field(default=0, ge=0)
    duplicate_content_count: int = Field(default=0, ge=0)
    fidelity_score: Decimal | None = Field(default=None, ge=0, le=100)
    report_data: dict[str, Any] | None = None
    status: str = "pending"

    @model_validator(mode="after")
    def validate_counts(self) -> "CourseCoverageReportBase":
        if self.status not in COURSE_COVERAGE_REPORT_STATUSES:
            raise ValueError(f"status invalido: {self.status}")
        covered_sum = self.covered_items + self.partially_covered_items + self.uncovered_items
        if covered_sum > self.total_source_items:
            raise ValueError(
                "A soma de covered_items, partially_covered_items e uncovered_items nao pode "
                "exceder total_source_items."
            )
        return self


class CourseCoverageReportCreate(CourseCoverageReportBase):
    project_id: UUID


class CourseCoverageReportResponse(CourseCoverageReportBase):
    id: UUID
    project_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CourseCoverageReportListResponse(BaseModel):
    items: list[CourseCoverageReportResponse]


class CourseCoverageReportFilter(BaseModel):
    project_id: UUID | None = None
    status: str | None = None
