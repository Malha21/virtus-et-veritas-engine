from uuid import UUID

from pydantic import BaseModel, field_validator

from app.schemas.content import GeneratedContentResponse

ALLOWED_GENERATION_LANGUAGES = {"pt-BR", "en-US"}


class GenerateEducationalContentRequest(BaseModel):
    generation_language: str = "pt-BR"

    @field_validator("generation_language")
    @classmethod
    def validate_generation_language(cls, value: str) -> str:
        if value not in ALLOWED_GENERATION_LANGUAGES:
            raise ValueError("Idioma de geração inválido.")
        return value


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
