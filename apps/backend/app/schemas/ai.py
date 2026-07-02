from uuid import UUID

from pydantic import BaseModel, field_validator

ALLOWED_GENERATION_LANGUAGES = {"pt-BR", "en-US"}


class GenerateStructureRequest(BaseModel):
    generation_language: str = "pt-BR"

    @field_validator("generation_language")
    @classmethod
    def validate_generation_language(cls, value: str) -> str:
        if value not in ALLOWED_GENERATION_LANGUAGES:
            raise ValueError("Idioma de geração inválido.")
        return value


class GeneratedStructureContentIds(BaseModel):
    document_analysis_id: UUID
    course_structure_id: UUID


class GenerateStructureResponse(BaseModel):
    project_id: UUID
    processing_status: str
    message: str
    contents: GeneratedStructureContentIds
