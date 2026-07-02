from uuid import UUID

from pydantic import BaseModel


class GeneratedStructureContentIds(BaseModel):
    document_analysis_id: UUID
    course_structure_id: UUID


class GenerateStructureResponse(BaseModel):
    project_id: UUID
    processing_status: str
    message: str
    contents: GeneratedStructureContentIds
