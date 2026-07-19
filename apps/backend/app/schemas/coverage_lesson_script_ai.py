"""Schema de validacao da resposta estruturada da IA para o roteiro de uma aula
do Plano de Cobertura (fase 19.5). Nao exposto via API; todo source_item_id
(item_code) retornado e revalidado contra os itens realmente vinculados a aula
antes de qualquer persistencia (nunca confiamos cegamente no que a IA retorna --
cf. app/services/lesson_generation_service.py::validate_structured_response)."""

from pydantic import BaseModel, Field, model_validator

AI_LESSON_GENERATION_STATUSES = {"completed", "requires_split"}
AI_COVERAGE_TYPES = {"full", "partial", "reference"}


class AICoveredSourceItem(BaseModel):
    source_item_id: str = Field(min_length=1)
    coverage_description: str = ""
    coverage_type: str = "full"

    @model_validator(mode="after")
    def validate_coverage_type(self) -> "AICoveredSourceItem":
        if self.coverage_type not in AI_COVERAGE_TYPES:
            raise ValueError(f"coverage_type invalido: {self.coverage_type}")
        return self


class AICoverageLessonScriptResponse(BaseModel):
    lesson_title: str = Field(min_length=1, max_length=500)
    learning_objective: str = ""
    generation_status: str = "completed"
    target_duration_minutes: float = Field(ge=0)
    estimated_duration_minutes: float = Field(ge=0)
    word_count: int = Field(ge=0)
    opening: str = ""
    development: str = ""
    closing: str = ""
    script: str = Field(min_length=1)
    summary: str = ""
    key_points: list[str] = Field(default_factory=list)
    covered_source_items: list[AICoveredSourceItem] = Field(default_factory=list)
    uncovered_source_items: list[str] = Field(default_factory=list)
    source_pages: list[int] = Field(default_factory=list)
    source_block_codes: list[str] = Field(default_factory=list)
    unsupported_claims_declared: list[str] = Field(default_factory=list)
    requires_split: bool = False
    split_reason: str | None = None
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_status(self) -> "AICoverageLessonScriptResponse":
        if self.generation_status not in AI_LESSON_GENERATION_STATUSES:
            raise ValueError(f"generation_status invalido: {self.generation_status}")
        if self.generation_status == "requires_split" and not self.split_reason:
            raise ValueError("split_reason e obrigatorio quando generation_status='requires_split'.")
        if self.generation_status == "completed" and not self.script.strip():
            raise ValueError("script nao pode ser vazio quando generation_status='completed'.")
        return self
