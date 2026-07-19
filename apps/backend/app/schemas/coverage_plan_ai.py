"""Schemas de validacao da resposta estruturada da IA para o plano de cobertura
(fase 19.4). Nao expostos via API; todo source_item_id retornado e revalidado
contra o inventario real antes de qualquer persistencia (nunca confiamos cegamente
no que a IA retorna)."""

from pydantic import BaseModel, Field, model_validator

AI_RELATIONSHIP_TYPES = {"primary", "supporting", "reference"}


class AICoveragePlanSourceItem(BaseModel):
    source_item_id: str = Field(min_length=1)
    source_order_in_lesson: int = Field(ge=0)
    is_required: bool = True
    relationship_type: str = "primary"

    @model_validator(mode="after")
    def validate_relationship_type(self) -> "AICoveragePlanSourceItem":
        if self.relationship_type not in AI_RELATIONSHIP_TYPES:
            raise ValueError(f"relationship_type invalido: {self.relationship_type}")
        return self


class AICoveragePlanLesson(BaseModel):
    temporary_id: str = Field(min_length=1, max_length=50)
    title: str = Field(min_length=1, max_length=500)
    description: str = ""
    learning_objective: str = ""
    lesson_order: int = Field(ge=0)
    estimated_word_count: int = Field(ge=0)
    estimated_duration_minutes: float = Field(ge=0)
    source_items: list[AICoveragePlanSourceItem] = Field(default_factory=list)
    grouping_reason: str = ""
    dependencies: list[str] = Field(default_factory=list)
    requires_review: bool = False
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_has_items(self) -> "AICoveragePlanLesson":
        if not self.source_items:
            raise ValueError("aula sem nenhum source_item nao e permitida (aula sem fonte).")
        return self


class AICoveragePlanModule(BaseModel):
    temporary_id: str = Field(min_length=1, max_length=50)
    title: str = Field(min_length=1, max_length=500)
    description: str = ""
    learning_objective: str = ""
    module_order: int = Field(ge=0)
    lessons: list[AICoveragePlanLesson] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_has_lessons(self) -> "AICoveragePlanModule":
        if not self.lessons:
            raise ValueError("modulo sem nenhuma aula nao e permitido (modulo vazio).")
        return self


class AICoveragePlanResponse(BaseModel):
    plan_version: int = 1
    modules: list[AICoveragePlanModule] = Field(default_factory=list)
    mapped_source_item_ids: list[str] = Field(default_factory=list)
    unmapped_source_item_ids: list[str] = Field(default_factory=list)
    duplicate_mappings: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
