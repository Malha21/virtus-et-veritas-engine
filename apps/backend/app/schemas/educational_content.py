from uuid import UUID

from pydantic import BaseModel

from app.schemas.content import GeneratedContentResponse


class EducationalContentCounts(BaseModel):
    lesson_scripts: int
    module_quizzes: int
    complementary_materials: int
    course_summaries: int


class GenerateEducationalContentResponse(BaseModel):
    project_id: UUID
    processing_status: str
    message: str
    contents_created: EducationalContentCounts


class EducationalContentSummaryResponse(BaseModel):
    lesson_scripts: list[GeneratedContentResponse]
    module_quizzes: list[GeneratedContentResponse]
    complementary_materials: list[GeneratedContentResponse]
    course_summaries: list[GeneratedContentResponse]
