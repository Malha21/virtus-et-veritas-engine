from uuid import UUID
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

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
    presentation_decks: int


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
    presentation_decks: list[GeneratedContentResponse]


class PresentationSlideUpdate(BaseModel):
    slide_number: int | str | None = None
    title: str | None = None
    subtitle: str | None = None
    bullets: list[Any] | None = None
    speaker_notes: str | None = None
    visual_suggestion: str | None = None
    interaction_question: str | None = None

    model_config = ConfigDict(extra="ignore")


class PresentationDeckUpdateRequest(BaseModel):
    presentation_title: str | None = None
    target_audience: str | None = None
    estimated_duration: str | None = None
    visual_style: str | None = None
    presentation_objective: str | None = None
    slides: list[PresentationSlideUpdate] | None = None
    closing_message: str | None = None

    model_config = ConfigDict(extra="ignore")


class LessonScriptUpdateRequest(BaseModel):
    lesson_script: dict[str, Any] | None = None

    model_config = ConfigDict(extra="allow")


class ModuleQuizUpdateRequest(BaseModel):
    module_quiz: dict[str, Any] | None = None

    model_config = ConfigDict(extra="allow")
