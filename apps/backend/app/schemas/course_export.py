from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

TextFormat = Literal["md", "txt"]


class CourseExportCreate(BaseModel):
    include_document_base: bool = True
    include_course_summary: bool = True
    include_course_structure: bool = True
    include_lesson_scripts: bool = True
    include_quizzes: bool = True
    include_materials: bool = True
    include_presentation: bool = True
    include_teleprompter: bool = True
    include_audio: bool = True
    include_video: bool = True
    only_completed_video: bool = True
    format_text: TextFormat = "md"


class CourseExportRead(BaseModel):
    id: UUID
    project_id: UUID
    status: str
    export_type: str
    options_json: dict | None
    file_size_bytes: int | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime | None
    download_url: str | None = None

    model_config = ConfigDict(from_attributes=True)


class CourseExportListRead(BaseModel):
    items: list[CourseExportRead]
