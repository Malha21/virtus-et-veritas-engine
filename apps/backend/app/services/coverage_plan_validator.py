"""Validacao deterministica do plano de cobertura (fase 19.4): tanto da resposta bruta
da IA (antes de persistir) quanto da estrutura ja persistida (endpoint /validate e
pre-condicao de /approve). Nunca confiamos apenas na IA -- todo source_item_id retornado
e revalidado contra o inventario real."""

from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.coverage_plan import CoveragePlan
from app.models.coverage_plan_lesson import CoveragePlanLesson
from app.models.coverage_plan_module import CoveragePlanModule
from app.models.document_page import DocumentPage
from app.models.lesson_source_item import LessonSourceItem
from app.models.source_content_item import SourceContentItem
from app.models.source_content_item_dependency import SourceContentItemDependency
from app.schemas.coverage_plan import CoveragePlanValidationIssue, CoveragePlanValidationResponse
from app.schemas.coverage_plan_ai import AICoveragePlanResponse
from app.services.coverage_plan_config import MAX_LESSON_MINUTES, TARGET_MIN_LESSON_MINUTES

# Itens rejeitados nunca devem ser planejados; qualquer outro status e elegivel
# (itens ainda nao revisados entram no plano com alerta, nunca ficam de fora em silencio).
EXCLUDED_ITEM_STATUSES = {"rejected"}
REVIEW_FLAG_STATUSES = {"pending", "requires_review", "possible_duplicate", "fragmented", "mapped"}


@dataclass
class AIPlanValidationResult:
    mapped_item_codes: set[str] = field(default_factory=set)
    unmapped_item_codes: set[str] = field(default_factory=set)
    duplicate_item_codes: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def validate_ai_plan_against_inventory(
    ai_response: AICoveragePlanResponse, valid_item_codes: set[str]
) -> AIPlanValidationResult:
    """Verifica cada source_item_id retornado pela IA contra os codigos reais do
    inventario. Itens referenciados que nao existem sao removidos da aula (nunca
    persistidos como se existissem) e viram warning; a aula so e descartada se
    ficar sem nenhum item valido (aula sem fonte nao e permitida)."""
    result = AIPlanValidationResult()
    seen_counts: dict[str, int] = {}

    for module in ai_response.modules:
        for lesson in module.lessons:
            valid_refs = []
            for ref in lesson.source_items:
                if ref.source_item_id not in valid_item_codes:
                    result.warnings.append(
                        f"{module.temporary_id}/{lesson.temporary_id}: item_code inexistente no "
                        f"inventario ignorado ({ref.source_item_id})"
                    )
                    continue
                valid_refs.append(ref)
                seen_counts[ref.source_item_id] = seen_counts.get(ref.source_item_id, 0) + 1
                result.mapped_item_codes.add(ref.source_item_id)
            lesson.source_items = valid_refs

    result.unmapped_item_codes = valid_item_codes - result.mapped_item_codes
    result.duplicate_item_codes = {code: count for code, count in seen_counts.items() if count > 1}
    return result


def _lesson_position_index(
    modules: list[CoveragePlanModule], lessons_by_module: dict[UUID, list[CoveragePlanLesson]]
) -> dict[UUID, tuple[int, int]]:
    """Posicao (module_order, lesson_order) de cada aula, para checar dependencias."""
    positions: dict[UUID, tuple[int, int]] = {}
    for module in modules:
        for lesson in lessons_by_module.get(module.id, []):
            positions[lesson.id] = (module.module_order, lesson.lesson_order)
    return positions


def validate_persisted_coverage(db: Session, coverage_plan: CoveragePlan) -> CoveragePlanValidationResponse:
    modules = list(
        db.execute(
            select(CoveragePlanModule)
            .where(CoveragePlanModule.coverage_plan_id == coverage_plan.id)
            .order_by(CoveragePlanModule.module_order.asc())
        )
        .scalars()
        .all()
    )
    lessons = list(
        db.execute(
            select(CoveragePlanLesson)
            .where(CoveragePlanLesson.coverage_plan_id == coverage_plan.id)
            .order_by(CoveragePlanLesson.lesson_order.asc())
        )
        .scalars()
        .all()
    )
    lesson_ids = [lesson.id for lesson in lessons]
    lessons_by_module: dict[UUID, list[CoveragePlanLesson]] = {}
    for lesson in lessons:
        lessons_by_module.setdefault(lesson.module_id, []).append(lesson)

    eligible_items = list(
        db.execute(
            select(SourceContentItem).where(
                SourceContentItem.project_file_id == coverage_plan.project_file_id,
                SourceContentItem.status.not_in(EXCLUDED_ITEM_STATUSES),
            )
        )
        .scalars()
        .all()
    )
    eligible_by_id = {item.id: item for item in eligible_items}

    links: list[LessonSourceItem] = []
    if lesson_ids:
        links = list(
            db.execute(
                select(LessonSourceItem).where(LessonSourceItem.coverage_plan_lesson_id.in_(lesson_ids))
            )
            .scalars()
            .all()
        )

    mapping_counts: dict[UUID, int] = {}
    for link in links:
        mapping_counts[link.source_item_id] = mapping_counts.get(link.source_item_id, 0) + 1

    mapped_ids = {item_id for item_id in mapping_counts if item_id in eligible_by_id}
    unmapped_items = [item for item in eligible_items if item.id not in mapped_ids]
    duplicate_mappings = sum(1 for count in mapping_counts.values() if count > 1)

    issues: list[CoveragePlanValidationIssue] = []
    for item in unmapped_items:
        issues.append(
            CoveragePlanValidationIssue(
                issue_type="unmapped_item",
                severity="error",
                message=f"Item {item.item_code} nao esta associado a nenhuma aula.",
                source_item_id=item.id,
            )
        )

    lessons_over_limit = 0
    lessons_under_recommended = 0
    lessons_without_sources = 0
    for lesson in lessons:
        if lesson.estimated_duration_minutes > Decimal(MAX_LESSON_MINUTES):
            lessons_over_limit += 1
            issues.append(
                CoveragePlanValidationIssue(
                    issue_type="lesson_over_limit",
                    severity="error",
                    message=(
                        f"Aula '{lesson.title}' com duracao estimada de "
                        f"{lesson.estimated_duration_minutes} min, acima do limite de {MAX_LESSON_MINUTES} min."
                    ),
                    lesson_id=lesson.id,
                    module_id=lesson.module_id,
                )
            )
        if lesson.estimated_duration_minutes < Decimal(TARGET_MIN_LESSON_MINUTES):
            lessons_under_recommended += 1
        if lesson.source_item_count == 0:
            lessons_without_sources += 1
            issues.append(
                CoveragePlanValidationIssue(
                    issue_type="lesson_without_sources",
                    severity="error",
                    message=f"Aula '{lesson.title}' nao possui nenhum source_content_item.",
                    lesson_id=lesson.id,
                    module_id=lesson.module_id,
                )
            )

    modules_without_lessons = 0
    for module in modules:
        if not lessons_by_module.get(module.id):
            modules_without_lessons += 1
            issues.append(
                CoveragePlanValidationIssue(
                    issue_type="module_without_lessons",
                    severity="error",
                    message=f"Modulo '{module.title}' nao possui nenhuma aula.",
                    module_id=module.id,
                )
            )
        if not module.title or not module.title.strip():
            issues.append(
                CoveragePlanValidationIssue(
                    issue_type="empty_title", severity="error", message="Modulo com titulo vazio.", module_id=module.id
                )
            )

    # dependencias: se um item aparece pela primeira vez antes do item do qual depende
    positions = _lesson_position_index(modules, lessons_by_module)
    lesson_by_id = {lesson.id: lesson for lesson in lessons}
    first_position_by_item: dict[UUID, tuple[int, int]] = {}
    for link in links:
        lesson = lesson_by_id.get(link.coverage_plan_lesson_id)
        if lesson is None:
            continue
        position = positions.get(lesson.id)
        if position is None:
            continue
        current = first_position_by_item.get(link.source_item_id)
        if current is None or position < current:
            first_position_by_item[link.source_item_id] = position

    dependencies = list(
        db.execute(
            select(SourceContentItemDependency).where(
                SourceContentItemDependency.source_item_id.in_(list(eligible_by_id.keys()))
                if eligible_by_id
                else SourceContentItemDependency.source_item_id.is_(None)
            )
        )
        .scalars()
        .all()
    )
    dependency_violations = 0
    for dependency in dependencies:
        item_position = first_position_by_item.get(dependency.source_item_id)
        dep_position = first_position_by_item.get(dependency.depends_on_source_item_id)
        if item_position is None or dep_position is None:
            continue
        if item_position < dep_position:
            dependency_violations += 1
            issues.append(
                CoveragePlanValidationIssue(
                    issue_type="dependency_violation",
                    severity="warning",
                    message=(
                        f"Item {eligible_by_id[dependency.source_item_id].item_code} aparece antes do item "
                        f"{eligible_by_id[dependency.depends_on_source_item_id].item_code} "
                        f"({dependency.dependency_type}), do qual depende."
                    ),
                    source_item_id=dependency.source_item_id,
                )
            )

    requires_review_source_items = sum(1 for item in eligible_items if item.status in REVIEW_FLAG_STATUSES)

    pages_requires_ocr = db.execute(
        select(func.count(DocumentPage.id)).where(
            DocumentPage.project_file_id == coverage_plan.project_file_id,
            DocumentPage.requires_ocr.is_(True),
        )
    ).scalar_one()

    blocking = (
        len(unmapped_items) > 0
        or lessons_over_limit > 0
        or lessons_without_sources > 0
        or modules_without_lessons > 0
    )
    if blocking:
        status_value = "invalid"
    elif requires_review_source_items > 0 or pages_requires_ocr > 0 or dependency_violations > 0:
        status_value = "requires_review"
    else:
        status_value = "valid"

    return CoveragePlanValidationResponse(
        status=status_value,
        total_source_items=len(eligible_items),
        mapped_items=len(mapped_ids),
        unmapped_items=len(unmapped_items),
        duplicate_mappings=duplicate_mappings,
        lessons_over_limit=lessons_over_limit,
        lessons_under_recommended_duration=lessons_under_recommended,
        modules_without_lessons=modules_without_lessons,
        lessons_without_sources=lessons_without_sources,
        dependency_violations=dependency_violations,
        requires_review_source_items=requires_review_source_items,
        pages_requires_ocr=pages_requires_ocr,
        issues=issues[:500],
        warnings=[],
    )
