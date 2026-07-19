from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.coverage_plan_lesson import CoveragePlanLesson
from app.models.coverage_plan_module import CoveragePlanModule
from app.models.lesson_source_item import LessonSourceItem
from app.services import coverage_plan_service as svc
from app.services.coverage_plan_config import MAX_LESSON_MINUTES
from tests.conftest import make_source_item


def run_generation_inline(db_session, current_user, project, project_file, **kwargs):
    job = svc.start_coverage_plan_generation(db_session, current_user, project.id, project_file.id, **kwargs)
    svc.generate_coverage_plan(db_session, current_user, job)
    db_session.commit()
    return job


def _make_items(db_session, project, project_file, count, words_per_item=20, content_type="concept"):
    items = []
    for i in range(1, count + 1):
        content = " ".join([f"palavra{i}-{w}" for w in range(words_per_item)])
        items.append(
            make_source_item(
                db_session,
                project,
                project_file,
                item_code=f"SRC-{i:04d}",
                title=f"Item {i}",
                normalized_content=content,
                content_type=content_type,
                source_order=i * 10,
                page_start=1,
                page_end=1,
            )
        )
    db_session.commit()
    return items


def _mapped_item_ids_for_plan(db_session, plan_id):
    lesson_ids = db_session.execute(
        select(CoveragePlanLesson.id).where(CoveragePlanLesson.coverage_plan_id == plan_id)
    ).scalars().all()
    if not lesson_ids:
        return set()
    links = db_session.execute(
        select(LessonSourceItem).where(LessonSourceItem.coverage_plan_lesson_id.in_(lesson_ids))
    ).scalars().all()
    return {link.source_item_id for link in links}


# --------------------------------------------------------------------------
# Estimativa e divisao (unidade)
# --------------------------------------------------------------------------

def test_estimate_lesson_duration_scales_with_word_count(db_session, project, inventory_project_file):
    short_item = make_source_item(
        db_session, project, inventory_project_file, item_code="SRC-0001", title="Curto", normalized_content="uma frase curta"
    )
    long_item = make_source_item(
        db_session,
        project,
        inventory_project_file,
        item_code="SRC-0002",
        title="Longo",
        normalized_content=" ".join(["palavra"] * 500),
        content_type="procedure",
    )
    short_estimate = svc.estimate_lesson_duration([short_item])
    long_estimate = svc.estimate_lesson_duration([long_item])
    assert long_estimate.total_words > short_estimate.total_words
    assert long_estimate.duration_minutes > short_estimate.duration_minutes


def test_split_oversized_lessons_preserves_every_item(db_session, project, inventory_project_file):
    items = _make_items(db_session, project, inventory_project_file, count=12, words_per_item=60, content_type="procedure")
    lesson = svc.PendingLesson(
        title="Aula Grande",
        description="",
        learning_objective="",
        items=items,
        relationship_by_item_id={item.id: "primary" for item in items},
        required_by_item_id={item.id: True for item in items},
        order_by_item_id={item.id: i for i, item in enumerate(items, start=1)},
        grouping_reason="teste",
    )
    result = svc.split_oversized_lessons([lesson])

    assert len(result) > 1
    all_item_ids = [item.id for split_lesson in result for item in split_lesson.items]
    assert sorted(all_item_ids) == sorted(item.id for item in items)
    assert len(all_item_ids) == len(set(all_item_ids))
    for split_lesson in result:
        assert split_lesson.estimate is not None
        # cada aula individual respeita o limite, exceto o caso extremo de item unico gigante (nao aplicavel aqui)
        assert split_lesson.estimate.duration_minutes <= Decimal(MAX_LESSON_MINUTES) or len(split_lesson.items) == 1


# --------------------------------------------------------------------------
# Geracao end-to-end (com IA falsa deterministica)
# --------------------------------------------------------------------------

def test_generate_coverage_plan_full_coverage(
    db_session, current_user, project, inventory_project_file, fake_coverage_plan_ai_provider
):
    items = _make_items(db_session, project, inventory_project_file, count=6, words_per_item=15)
    job = run_generation_inline(db_session, current_user, project, inventory_project_file)
    assert job.status in {"completed", "partially_completed"}

    plan = svc.get_latest_plan(db_session, project.id)
    assert plan is not None
    assert plan.total_items == len(items)
    assert plan.unmapped_items == 0
    assert plan.mapped_items == len(items)

    mapped_ids = _mapped_item_ids_for_plan(db_session, plan.id)
    assert mapped_ids == {item.id for item in items}

    lessons = db_session.execute(
        select(CoveragePlanLesson).where(CoveragePlanLesson.coverage_plan_id == plan.id)
    ).scalars().all()
    assert all(lesson.source_item_count > 0 for lesson in lessons)

    modules = db_session.execute(
        select(CoveragePlanModule).where(CoveragePlanModule.coverage_plan_id == plan.id)
    ).scalars().all()
    assert len(modules) > 0


def test_generate_coverage_plan_splits_large_content(
    db_session, current_user, project, inventory_project_file, fake_coverage_plan_ai_provider
):
    # 30 itens de ~120 palavras cada, tipo "procedure" (peso alto) -> muito acima de 3000 palavras totais
    items = _make_items(db_session, project, inventory_project_file, count=30, words_per_item=120, content_type="procedure")
    run_generation_inline(db_session, current_user, project, inventory_project_file)

    plan = svc.get_latest_plan(db_session, project.id)
    assert plan.unmapped_items == 0

    lessons = db_session.execute(
        select(CoveragePlanLesson).where(CoveragePlanLesson.coverage_plan_id == plan.id)
    ).scalars().all()
    assert len(lessons) > 1
    for lesson in lessons:
        assert lesson.estimated_duration_minutes <= Decimal(MAX_LESSON_MINUTES) or lesson.source_item_count == 1

    mapped_ids = _mapped_item_ids_for_plan(db_session, plan.id)
    assert mapped_ids == {item.id for item in items}


def test_generate_coverage_plan_never_drops_pedagogical_types(
    db_session, current_user, project, inventory_project_file, fake_coverage_plan_ai_provider
):
    """definicao, regra, excecao, procedimento, exemplo e conclusao devem sobreviver a divisao."""
    specs = [
        ("SRC-0001", "definition", "Definição do conceito central com bastante detalhe " * 20),
        ("SRC-0002", "rule", "Regra geral aplicável ao conceito com bastante detalhe " * 20),
        ("SRC-0003", "exception", "Exceção importante à regra geral com bastante detalhe " * 20),
        ("SRC-0004", "procedure", "Procedimento passo a passo detalhado com bastante detalhe " * 20),
        ("SRC-0005", "example", "Exemplo prático de aplicação com bastante detalhe " * 20),
        ("SRC-0006", "conclusion", "Conclusão final do assunto com bastante detalhe " * 20),
    ]
    items = [
        make_source_item(
            db_session,
            project,
            inventory_project_file,
            item_code=code,
            title=f"Item {code}",
            normalized_content=content,
            content_type=content_type,
            source_order=index * 10,
        )
        for index, (code, content_type, content) in enumerate(specs, start=1)
    ]
    db_session.commit()

    # forca todos os 6 itens em uma unica aula proposta pela IA (grande o suficiente para exigir divisao)
    fake_coverage_plan_ai_provider["batch_overrides"]["BATCH-0001"] = {
        "plan_version": 1,
        "modules": [
            {
                "temporary_id": "MOD-TMP-0001",
                "title": "Módulo Único",
                "description": "",
                "learning_objective": "",
                "module_order": 1,
                "lessons": [
                    {
                        "temporary_id": "LES-TMP-0001",
                        "title": "Aula Completa",
                        "description": "",
                        "learning_objective": "",
                        "lesson_order": 1,
                        "estimated_word_count": 100,
                        "estimated_duration_minutes": 1,
                        "source_items": [
                            {
                                "source_item_id": item.item_code,
                                "source_order_in_lesson": i + 1,
                                "is_required": True,
                                "relationship_type": "primary",
                            }
                            for i, item in enumerate(items)
                        ],
                        "grouping_reason": "todos juntos para forçar divisão",
                        "dependencies": [],
                        "requires_review": False,
                        "warnings": [],
                    }
                ],
            }
        ],
        "mapped_source_item_ids": [item.item_code for item in items],
        "unmapped_source_item_ids": [],
        "duplicate_mappings": [],
        "warnings": [],
    }

    run_generation_inline(db_session, current_user, project, inventory_project_file)

    plan = svc.get_latest_plan(db_session, project.id)
    mapped_ids = _mapped_item_ids_for_plan(db_session, plan.id)
    assert mapped_ids == {item.id for item in items}, "nenhum tipo pedagogico pode desaparecer apos a divisao"

    # o conteudo original de cada item permanece intacto (nunca resumido/cortado)
    for item, (_, _, original_content) in zip(items, specs, strict=True):
        db_session.refresh(item)
        assert item.normalized_content == original_content


def test_generate_prevents_duplicate_active_job(
    db_session, current_user, project, inventory_project_file, fake_coverage_plan_ai_provider
):
    _make_items(db_session, project, inventory_project_file, count=3)
    job1 = svc.start_coverage_plan_generation(db_session, current_user, project.id, inventory_project_file.id)
    job2 = svc.start_coverage_plan_generation(db_session, current_user, project.id, inventory_project_file.id)
    assert job1.id == job2.id


def test_generate_if_missing_reuses_existing_plan(
    db_session, current_user, project, inventory_project_file, fake_coverage_plan_ai_provider
):
    _make_items(db_session, project, inventory_project_file, count=3)
    run_generation_inline(db_session, current_user, project, inventory_project_file)
    first_plan = svc.get_latest_plan(db_session, project.id)

    run_generation_inline(db_session, current_user, project, inventory_project_file)
    second_plan = svc.get_latest_plan(db_session, project.id)

    assert first_plan.id == second_plan.id
    assert second_plan.version == 1


def test_force_regenerate_creates_new_version(
    db_session, current_user, project, inventory_project_file, fake_coverage_plan_ai_provider
):
    _make_items(db_session, project, inventory_project_file, count=3)
    run_generation_inline(db_session, current_user, project, inventory_project_file)
    run_generation_inline(db_session, current_user, project, inventory_project_file, force=True)

    versions = svc.list_plan_versions(db_session, project.id)
    assert len(versions) == 2
    assert {v.version for v in versions} == {1, 2}
    stale = [v for v in versions if v.version == 1][0]
    assert stale.status == "stale"


def test_generate_if_missing_detects_new_item_and_marks_stale(
    db_session, current_user, project, inventory_project_file, fake_coverage_plan_ai_provider
):
    _make_items(db_session, project, inventory_project_file, count=3)
    run_generation_inline(db_session, current_user, project, inventory_project_file)
    first_plan = svc.get_latest_plan(db_session, project.id)
    original_fingerprint = first_plan.inventory_fingerprint

    make_source_item(
        db_session,
        project,
        inventory_project_file,
        item_code="SRC-9990",
        title="Item novo",
        normalized_content="conteudo adicionado depois da primeira geracao do plano",
    )
    db_session.commit()

    job = run_generation_inline(db_session, current_user, project, inventory_project_file)

    # nao cria nova versao implicitamente (generate_if_missing nao usa force)
    versions = svc.list_plan_versions(db_session, project.id)
    assert len(versions) == 1
    plan = versions[0]
    assert plan.id == first_plan.id
    assert plan.status == "stale"
    # plano antigo nao e sobrescrito: fingerprint gravado continua o original
    assert plan.inventory_fingerprint == original_fingerprint

    warnings = (job.result_json or {}).get("warnings", [])
    assert any("inventário foi alterado" in w for w in warnings)


def test_generate_if_missing_detects_removed_item_and_marks_stale(
    db_session, current_user, project, inventory_project_file, fake_coverage_plan_ai_provider
):
    items = _make_items(db_session, project, inventory_project_file, count=3)
    run_generation_inline(db_session, current_user, project, inventory_project_file)
    first_plan = svc.get_latest_plan(db_session, project.id)

    # "remove" um item do inventario elegivel (rejeitado = excluido de load_inventory)
    items[0].status = "rejected"
    db_session.add(items[0])
    db_session.commit()

    run_generation_inline(db_session, current_user, project, inventory_project_file)

    versions = svc.list_plan_versions(db_session, project.id)
    assert len(versions) == 1
    plan = versions[0]
    assert plan.id == first_plan.id
    assert plan.status == "stale"


def test_generate_if_missing_detects_edited_item_and_marks_stale(
    db_session, current_user, project, inventory_project_file, fake_coverage_plan_ai_provider
):
    items = _make_items(db_session, project, inventory_project_file, count=3)
    run_generation_inline(db_session, current_user, project, inventory_project_file)
    first_plan = svc.get_latest_plan(db_session, project.id)

    items[0].normalized_content = (items[0].normalized_content or "") + " conteudo editado manualmente"
    db_session.add(items[0])
    db_session.commit()

    run_generation_inline(db_session, current_user, project, inventory_project_file)

    versions = svc.list_plan_versions(db_session, project.id)
    assert len(versions) == 1
    assert versions[0].id == first_plan.id
    assert versions[0].status == "stale"


def test_generate_if_missing_unchanged_inventory_reuses_plan_silently(
    db_session, current_user, project, inventory_project_file, fake_coverage_plan_ai_provider
):
    _make_items(db_session, project, inventory_project_file, count=3)
    run_generation_inline(db_session, current_user, project, inventory_project_file)
    first_plan = svc.get_latest_plan(db_session, project.id)

    run_generation_inline(db_session, current_user, project, inventory_project_file)
    second_plan = svc.get_latest_plan(db_session, project.id)

    assert first_plan.id == second_plan.id
    assert second_plan.version == 1
    assert second_plan.status != "stale"


def test_force_regenerate_after_stale_detection_creates_new_version_and_preserves_previous(
    db_session, current_user, project, inventory_project_file, fake_coverage_plan_ai_provider
):
    _make_items(db_session, project, inventory_project_file, count=3)
    run_generation_inline(db_session, current_user, project, inventory_project_file)

    make_source_item(
        db_session,
        project,
        inventory_project_file,
        item_code="SRC-9991",
        title="Item novo 2",
        normalized_content="mais conteudo novo apos a primeira geracao",
    )
    db_session.commit()

    # generate_if_missing (sem force) so marca stale, nunca gera versao nova sozinho
    run_generation_inline(db_session, current_user, project, inventory_project_file)
    versions = svc.list_plan_versions(db_session, project.id)
    assert len(versions) == 1
    assert versions[0].status == "stale"

    # regeneracao explicita (force=True) gera nova versao e preserva o historico
    run_generation_inline(db_session, current_user, project, inventory_project_file, force=True)
    versions = svc.list_plan_versions(db_session, project.id)
    assert len(versions) == 2
    assert {v.version for v in versions} == {1, 2}
    v1 = next(v for v in versions if v.version == 1)
    v2 = next(v for v in versions if v.version == 2)
    assert v1.status == "stale"
    assert v2.status in {"ready_for_review", "requires_review"}


def test_generate_blocked_without_any_eligible_items(db_session, current_user, project, inventory_project_file):
    with pytest.raises(HTTPException) as exc_info:
        svc.start_coverage_plan_generation(db_session, current_user, project.id, inventory_project_file.id)
    assert exc_info.value.status_code == 400


# --------------------------------------------------------------------------
# Edicao manual
# --------------------------------------------------------------------------

def test_recalculate_lesson_estimates_reflects_current_items(
    db_session, current_user, project, inventory_project_file, fake_coverage_plan_ai_provider
):
    _make_items(db_session, project, inventory_project_file, count=4, words_per_item=15)
    run_generation_inline(db_session, current_user, project, inventory_project_file)
    plan = svc.get_latest_plan(db_session, project.id)
    lesson = db_session.execute(
        select(CoveragePlanLesson).where(CoveragePlanLesson.coverage_plan_id == plan.id)
    ).scalars().first()

    original_words = lesson.estimated_word_count
    original_item_count = lesson.source_item_count
    extra_item = make_source_item(
        db_session,
        project,
        inventory_project_file,
        item_code="SRC-9999",
        title="Extra",
        normalized_content=" ".join(["palavra"] * 100),
    )
    db_session.commit()

    updated = svc.add_source_item_to_lesson(db_session, lesson.id, extra_item.id, current_user=current_user)
    assert updated.estimated_word_count > original_words
    assert updated.source_item_count == original_item_count + 1


def test_remove_last_item_from_lesson_is_blocked(
    db_session, current_user, project, inventory_project_file, fake_coverage_plan_ai_provider
):
    _make_items(db_session, project, inventory_project_file, count=1)
    run_generation_inline(db_session, current_user, project, inventory_project_file)
    plan = svc.get_latest_plan(db_session, project.id)
    lesson = db_session.execute(
        select(CoveragePlanLesson).where(CoveragePlanLesson.coverage_plan_id == plan.id)
    ).scalars().first()
    link = db_session.execute(
        select(LessonSourceItem).where(LessonSourceItem.coverage_plan_lesson_id == lesson.id)
    ).scalars().first()

    with pytest.raises(HTTPException) as exc_info:
        svc.remove_source_item_from_lesson(db_session, lesson.id, link.source_item_id)
    assert exc_info.value.status_code == 400


def test_split_lesson_manual_preserves_items_and_rejects_loss(
    db_session, current_user, project, inventory_project_file, fake_coverage_plan_ai_provider
):
    items = _make_items(db_session, project, inventory_project_file, count=4, words_per_item=10)
    run_generation_inline(db_session, current_user, project, inventory_project_file)
    plan = svc.get_latest_plan(db_session, project.id)
    lesson = db_session.execute(
        select(CoveragePlanLesson).where(CoveragePlanLesson.coverage_plan_id == plan.id)
    ).scalars().first()
    links = db_session.execute(
        select(LessonSourceItem).where(LessonSourceItem.coverage_plan_lesson_id == lesson.id)
    ).scalars().all()
    item_ids = [link.source_item_id for link in links]
    assert len(item_ids) >= 2

    half = len(item_ids) // 2 or 1
    first_half, second_half = item_ids[:half], item_ids[half:]
    if not second_half:
        pytest.skip("aula com um unico item, divisao nao se aplica")

    with pytest.raises(HTTPException) as exc_info:
        svc.split_lesson_manual(
            db_session,
            lesson.id,
            first_title="Primeira Parte",
            second_title="Segunda Parte",
            first_source_item_ids=first_half,
            second_source_item_ids=[],
        )
    assert exc_info.value.status_code == 400

    first, second = svc.split_lesson_manual(
        db_session,
        lesson.id,
        first_title="Primeira Parte",
        second_title="Segunda Parte",
        first_source_item_ids=first_half,
        second_source_item_ids=second_half,
    )
    assert first.source_item_count == len(first_half)
    assert second.source_item_count == len(second_half)
    assert second.lesson_order == first.lesson_order + 1


def test_merge_lessons_manual_blocks_when_over_limit(
    db_session, current_user, project, inventory_project_file, fake_coverage_plan_ai_provider
):
    items = _make_items(db_session, project, inventory_project_file, count=20, words_per_item=100, content_type="procedure")
    run_generation_inline(db_session, current_user, project, inventory_project_file)
    plan = svc.get_latest_plan(db_session, project.id)
    lessons = db_session.execute(
        select(CoveragePlanLesson)
        .where(CoveragePlanLesson.coverage_plan_id == plan.id)
        .order_by(CoveragePlanLesson.lesson_order.asc())
    ).scalars().all()
    if len(lessons) < 2:
        pytest.skip("geracao nao produziu aulas suficientes para testar uniao bloqueada")

    with pytest.raises(HTTPException) as exc_info:
        svc.merge_lessons_manual(db_session, [lesson.id for lesson in lessons], title="Aula Unificada")
    assert exc_info.value.status_code == 400


# --------------------------------------------------------------------------
# Isolamento multi-tenant (update_lesson / add_source_item_to_lesson)
# --------------------------------------------------------------------------

def test_update_lesson_move_to_module_within_same_plan_succeeds(
    db_session, current_user, project, inventory_project_file, fake_coverage_plan_ai_provider
):
    _make_items(db_session, project, inventory_project_file, count=3)
    run_generation_inline(db_session, current_user, project, inventory_project_file)
    plan = svc.get_latest_plan(db_session, project.id)
    lesson = db_session.execute(
        select(CoveragePlanLesson).where(CoveragePlanLesson.coverage_plan_id == plan.id)
    ).scalars().first()

    second_module = CoveragePlanModule(
        coverage_plan_id=plan.id,
        project_id=project.id,
        title="Segundo módulo",
        module_order=2,
    )
    db_session.add(second_module)
    db_session.commit()

    updated = svc.update_lesson(db_session, lesson, current_user=current_user, module_id=second_module.id)
    assert updated.module_id == second_module.id


def test_update_lesson_move_to_module_of_different_project_same_org_is_blocked(
    db_session,
    current_user,
    project,
    inventory_project_file,
    other_project,
    other_inventory_project_file,
    fake_coverage_plan_ai_provider,
):
    _make_items(db_session, project, inventory_project_file, count=2)
    _make_items(db_session, other_project, other_inventory_project_file, count=2)
    run_generation_inline(db_session, current_user, project, inventory_project_file)
    run_generation_inline(db_session, current_user, other_project, other_inventory_project_file)

    plan_a = svc.get_latest_plan(db_session, project.id)
    plan_b = svc.get_latest_plan(db_session, other_project.id)
    lesson_a = db_session.execute(
        select(CoveragePlanLesson).where(CoveragePlanLesson.coverage_plan_id == plan_a.id)
    ).scalars().first()
    module_b = db_session.execute(
        select(CoveragePlanModule).where(CoveragePlanModule.coverage_plan_id == plan_b.id)
    ).scalars().first()
    original_module_id = lesson_a.module_id

    with pytest.raises(HTTPException) as exc_info:
        svc.update_lesson(db_session, lesson_a, current_user=current_user, module_id=module_b.id)
    assert exc_info.value.status_code == 400

    db_session.refresh(lesson_a)
    assert lesson_a.module_id == original_module_id


def test_update_lesson_move_to_module_of_other_organization_is_blocked(
    db_session,
    current_user,
    project,
    inventory_project_file,
    other_org_project,
    other_org_current_user,
    other_org_inventory_project_file,
    fake_coverage_plan_ai_provider,
):
    _make_items(db_session, project, inventory_project_file, count=2)
    _make_items(db_session, other_org_project, other_org_inventory_project_file, count=2)
    run_generation_inline(db_session, current_user, project, inventory_project_file)
    run_generation_inline(db_session, other_org_current_user, other_org_project, other_org_inventory_project_file)

    plan_a = svc.get_latest_plan(db_session, project.id)
    plan_c = svc.get_latest_plan(db_session, other_org_project.id)
    lesson_a = db_session.execute(
        select(CoveragePlanLesson).where(CoveragePlanLesson.coverage_plan_id == plan_a.id)
    ).scalars().first()
    module_c = db_session.execute(
        select(CoveragePlanModule).where(CoveragePlanModule.coverage_plan_id == plan_c.id)
    ).scalars().first()
    original_module_id = lesson_a.module_id

    # nao deve revelar a existencia do modulo de outra organizacao: 404 generico
    with pytest.raises(HTTPException) as exc_info:
        svc.update_lesson(db_session, lesson_a, current_user=current_user, module_id=module_c.id)
    assert exc_info.value.status_code == 404

    db_session.refresh(lesson_a)
    assert lesson_a.module_id == original_module_id


def test_add_source_item_to_lesson_from_different_project_same_org_is_blocked(
    db_session,
    current_user,
    project,
    inventory_project_file,
    other_project,
    other_inventory_project_file,
    fake_coverage_plan_ai_provider,
):
    _make_items(db_session, project, inventory_project_file, count=2)
    other_item = make_source_item(
        db_session,
        other_project,
        other_inventory_project_file,
        item_code="SRC-OTHER-0001",
        title="Item de outro projeto",
        normalized_content="conteudo de outro documento do mesmo tenant",
    )
    db_session.commit()
    run_generation_inline(db_session, current_user, project, inventory_project_file)
    plan = svc.get_latest_plan(db_session, project.id)
    lesson = db_session.execute(
        select(CoveragePlanLesson).where(CoveragePlanLesson.coverage_plan_id == plan.id)
    ).scalars().first()
    original_count = lesson.source_item_count

    with pytest.raises(HTTPException) as exc_info:
        svc.add_source_item_to_lesson(db_session, lesson.id, other_item.id, current_user=current_user)
    assert exc_info.value.status_code == 400

    db_session.refresh(lesson)
    assert lesson.source_item_count == original_count
    link = db_session.execute(
        select(LessonSourceItem).where(
            LessonSourceItem.coverage_plan_lesson_id == lesson.id,
            LessonSourceItem.source_item_id == other_item.id,
        )
    ).scalar_one_or_none()
    assert link is None


def test_add_source_item_to_lesson_from_other_organization_is_blocked(
    db_session,
    current_user,
    project,
    inventory_project_file,
    other_org_project,
    other_org_inventory_project_file,
    fake_coverage_plan_ai_provider,
):
    _make_items(db_session, project, inventory_project_file, count=2)
    foreign_item = make_source_item(
        db_session,
        other_org_project,
        other_org_inventory_project_file,
        item_code="SRC-FOREIGN-0001",
        title="Item de outra organização",
        normalized_content="conteudo pertencente a outra organizacao",
    )
    db_session.commit()
    run_generation_inline(db_session, current_user, project, inventory_project_file)
    plan = svc.get_latest_plan(db_session, project.id)
    lesson = db_session.execute(
        select(CoveragePlanLesson).where(CoveragePlanLesson.coverage_plan_id == plan.id)
    ).scalars().first()
    original_count = lesson.source_item_count

    # nao deve revelar a existencia do item de outra organizacao: 404 generico
    with pytest.raises(HTTPException) as exc_info:
        svc.add_source_item_to_lesson(db_session, lesson.id, foreign_item.id, current_user=current_user)
    assert exc_info.value.status_code == 404

    db_session.refresh(lesson)
    assert lesson.source_item_count == original_count
    link = db_session.execute(
        select(LessonSourceItem).where(
            LessonSourceItem.coverage_plan_lesson_id == lesson.id,
            LessonSourceItem.source_item_id == foreign_item.id,
        )
    ).scalar_one_or_none()
    assert link is None


# --------------------------------------------------------------------------
# Aprovacao
# --------------------------------------------------------------------------

def test_approve_plan_blocked_with_unmapped_required_item(
    db_session, current_user, project, inventory_project_file, fake_coverage_plan_ai_provider
):
    _make_items(db_session, project, inventory_project_file, count=3)
    run_generation_inline(db_session, current_user, project, inventory_project_file)
    plan = svc.get_latest_plan(db_session, project.id)

    # cria um item elegivel extra apos a geracao, nunca associado a nenhuma aula
    make_source_item(
        db_session, project, inventory_project_file, item_code="SRC-9998", title="Orfao", normalized_content="conteudo orfao"
    )
    db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        svc.approve_plan(db_session, current_user, plan)
    assert exc_info.value.status_code == 400


def test_approve_plan_succeeds_when_fully_covered(
    db_session, current_user, project, inventory_project_file, fake_coverage_plan_ai_provider
):
    _make_items(db_session, project, inventory_project_file, count=3)
    run_generation_inline(db_session, current_user, project, inventory_project_file)
    plan = svc.get_latest_plan(db_session, project.id)

    approved = svc.approve_plan(db_session, current_user, plan)
    assert approved.status == "approved"
    assert approved.approved_at is not None
    assert approved.approved_by == current_user.id


def test_approve_plan_blocked_with_requires_review_item(
    db_session, current_user, project, inventory_project_file, fake_coverage_plan_ai_provider
):
    _make_items(db_session, project, inventory_project_file, count=3)
    make_source_item(
        db_session,
        project,
        inventory_project_file,
        item_code="SRC-0004",
        title="Item pendente de revisão",
        normalized_content="conteudo pendente de revisao humana da fase 19.3",
        status="requires_review",
        source_order=40,
    )
    db_session.commit()

    run_generation_inline(db_session, current_user, project, inventory_project_file)
    plan = svc.get_latest_plan(db_session, project.id)
    original_status = plan.status

    with pytest.raises(HTTPException) as exc_info:
        svc.approve_plan(db_session, current_user, plan)
    assert exc_info.value.status_code == 400

    db_session.refresh(plan)
    assert plan.status == original_status
    assert plan.status != "approved"
    assert plan.approved_at is None
    assert plan.approved_by is None
