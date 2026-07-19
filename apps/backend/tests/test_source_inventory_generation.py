from sqlalchemy import select

from app.models.source_content_item import SourceContentItem
from app.schemas.source_inventory_ai import AIInventoryItemResponse
from app.services.source_inventory_chunking import ChunkPlan
from app.services.source_inventory_service import (
    ResolvedItem,
    _create_job,
    consolidate_fragments,
    deduplicate_items,
    generate_inventory,
)
from tests.conftest import add_extracted_page


def _make_ai_item(**overrides) -> AIInventoryItemResponse:
    base = {
        "temporary_id": "TMP-0001",
        "title": "Titulo",
        "normalized_content": "conteudo normalizado",
        "source_text": "texto original",
        "content_type": "concept",
        "importance": "relevant",
        "page_start": 1,
        "page_end": 1,
        "source_block_codes": ["P0001-B0001"],
        "source_order": 1,
    }
    base.update(overrides)
    return AIInventoryItemResponse(**base)


def run_generation(db_session, current_user, project, project_file, **kwargs):
    job = _create_job(db_session, current_user, project, project_file, mode=kwargs.pop("mode", "generate_if_missing"), **kwargs)
    generate_inventory(db_session, current_user, job)
    db_session.refresh(job)
    return job


# --------------------------------------------------------------------------
# Deduplicacao e fragmentos (unitario, sobre ResolvedItem)
# --------------------------------------------------------------------------

def test_deduplicate_items_merges_chunk_overlap_duplicate(db_session, inventory_project_file):
    _, blocks = add_extracted_page(
        db_session, inventory_project_file, 6, [("paragraph", "o conceito de lideranca envolve influenciar pessoas")]
    )
    chunk1 = ChunkPlan(chunk_id="CHUNK-0001", page_start=1, page_end=6, blocks=blocks)
    chunk2 = ChunkPlan(chunk_id="CHUNK-0002", page_start=6, page_end=11, blocks=blocks, overlap_from_previous=True)

    shared_text = "o conceito de lideranca envolve influenciar pessoas"
    item_a = ResolvedItem(
        _make_ai_item(
            page_start=6, page_end=6, source_block_codes=[blocks[0].block_code], normalized_content=shared_text
        ),
        chunk1,
        list(blocks),
    )
    item_b = ResolvedItem(
        _make_ai_item(
            page_start=6, page_end=6, source_block_codes=[blocks[0].block_code], normalized_content=shared_text
        ),
        chunk2,
        list(blocks),
    )

    survivors = deduplicate_items([item_a, item_b])

    assert len(survivors) == 1
    assert item_b.superseded is True


def test_deduplicate_items_keeps_distinct_items(db_session, inventory_project_file):
    _, blocks = add_extracted_page(
        db_session, inventory_project_file, 1, [("paragraph", "conceito um"), ("paragraph", "conceito totalmente diferente")]
    )
    item_a = ResolvedItem(
        _make_ai_item(source_block_codes=[blocks[0].block_code], normalized_content="conceito um sobre lideranca"),
        ChunkPlan(chunk_id="CHUNK-0001", page_start=1, page_end=1, blocks=blocks),
        [blocks[0]],
    )
    item_b = ResolvedItem(
        _make_ai_item(source_block_codes=[blocks[1].block_code], normalized_content="receita de bolo de chocolate"),
        ChunkPlan(chunk_id="CHUNK-0001", page_start=1, page_end=1, blocks=blocks),
        [blocks[1]],
    )

    survivors = deduplicate_items([item_a, item_b])
    assert len(survivors) == 2


def test_consolidate_fragments_merges_boundary_items(db_session, inventory_project_file):
    _, blocks6 = add_extracted_page(db_session, inventory_project_file, 6, [("paragraph", "inicio do conceito que continua")])
    _, blocks7 = add_extracted_page(db_session, inventory_project_file, 7, [("paragraph", "final do conceito iniciado antes")])

    chunk1 = ChunkPlan(chunk_id="CHUNK-0001", page_start=1, page_end=6, blocks=blocks6)
    chunk2 = ChunkPlan(chunk_id="CHUNK-0002", page_start=6, page_end=11, blocks=blocks7, overlap_from_previous=True)

    item_a = ResolvedItem(
        _make_ai_item(page_start=6, page_end=6, possible_fragment=True, source_text="inicio do conceito que continua"),
        chunk1,
        list(blocks6),
    )
    item_b = ResolvedItem(
        _make_ai_item(page_start=7, page_end=7, possible_fragment=True, source_text="final do conceito iniciado antes"),
        chunk2,
        list(blocks7),
    )

    consolidated = consolidate_fragments([item_a, item_b])

    assert len(consolidated) == 1
    assert "inicio do conceito" in consolidated[0].ai_item.source_text
    assert "final do conceito" in consolidated[0].ai_item.source_text


def test_consolidate_fragments_does_not_merge_unrelated_items(db_session, inventory_project_file):
    _, blocks1 = add_extracted_page(db_session, inventory_project_file, 1, [("paragraph", "assunto A")])
    _, blocks2 = add_extracted_page(db_session, inventory_project_file, 2, [("paragraph", "assunto B")])

    chunk1 = ChunkPlan(chunk_id="CHUNK-0001", page_start=1, page_end=1, blocks=blocks1)
    chunk2 = ChunkPlan(chunk_id="CHUNK-0002", page_start=2, page_end=2, blocks=blocks2)

    item_a = ResolvedItem(_make_ai_item(possible_fragment=False), chunk1, list(blocks1))
    item_b = ResolvedItem(_make_ai_item(possible_fragment=False), chunk2, list(blocks2))

    consolidated = consolidate_fragments([item_a, item_b])
    assert len(consolidated) == 2


# --------------------------------------------------------------------------
# Geracao ponta-a-ponta (com IA falsa e deterministica)
# --------------------------------------------------------------------------

def test_completeness_all_known_content_represented(db_session, current_user, project, inventory_project_file, fake_ai_provider):
    known_pieces = {
        "definicao": "Definicao: lideranca e a capacidade de influenciar pessoas.",
        "fato1": "Fato: a empresa foi fundada em 1998.",
        "fato2": "Fato: existem 42 filiais ativas.",
        "lista": "Lista de valores: integridade, respeito e transparencia.",
        "procedimento": "Procedimento: primeiro planeje, depois execute, por fim avalie.",
        "excecao": "Excecao: a regra nao se aplica a contratos temporarios.",
        "exemplo": "Exemplo: um lider que ouviu a equipe antes de decidir.",
        "conclusao": "Conclusao: lideranca eficaz exige pratica constante.",
        "observacao": "Observacao: este ponto requer atencao especial do leitor.",
    }
    add_extracted_page(
        db_session,
        inventory_project_file,
        1,
        [("paragraph", text) for text in known_pieces.values()],
    )

    job = run_generation(db_session, current_user, project, inventory_project_file)
    assert job.status in {"completed", "partially_completed"}

    items = db_session.execute(
        select(SourceContentItem).where(SourceContentItem.project_file_id == inventory_project_file.id)
    ).scalars().all()

    all_text = " ".join(f"{i.title} {i.source_text} {i.normalized_content}" for i in items)
    for key, text in known_pieces.items():
        assert text in all_text, f"conteudo '{key}' nao encontrado no inventario"


def test_anchoring_rejects_hallucinated_item_as_requires_review(
    db_session, current_user, project, inventory_project_file, fake_ai_provider
):
    add_extracted_page(db_session, inventory_project_file, 1, [("paragraph", "O documento fala apenas sobre maçãs.")])

    fake_ai_provider["chunk_overrides"]["CHUNK-0001"] = {
        "chunk_id": "CHUNK-0001",
        "items": [
            {
                "temporary_id": "TMP-0001",
                "title": "Informacao inventada",
                "normalized_content": "O documento fala sobre bananas e laranjas importadas do Chile.",
                "source_text": "Texto que nao existe no documento original sobre frutas importadas.",
                "content_type": "fact",
                "importance": "relevant",
                "page_start": 1,
                "page_end": 1,
                "source_block_codes": ["P0001-B0001"],
                "source_order": 1,
                "depends_on_temporary_ids": [],
                "possible_duplicate": False,
                "possible_fragment": False,
                "requires_review": False,
                "review_reason": None,
            }
        ],
        "chunk_warnings": [],
        "unprocessed_content": [],
    }

    job = run_generation(db_session, current_user, project, inventory_project_file)
    items = db_session.execute(
        select(SourceContentItem).where(SourceContentItem.project_file_id == inventory_project_file.id)
    ).scalars().all()

    assert len(items) == 1
    # item mal ancorado (texto nao corresponde ao bloco real) deve ser marcado para revisao,
    # nunca aceito silenciosamente como conteudo valido do documento
    assert items[0].status == "requires_review"
    assert "ancoragem" in (items[0].metadata_json or {}).get("review_reason", "")
    assert job.result_json["warnings"]


def test_coverage_check_creates_fallback_item_for_gap(
    db_session, current_user, project, inventory_project_file, fake_ai_provider
):
    add_extracted_page(db_session, inventory_project_file, 1, [("paragraph", "Texto principal do documento.")])

    fake_ai_provider["coverage_overrides"]["CHUNK-0001"] = {
        "chunk_id": "CHUNK-0001",
        "coverage_status": "incomplete",
        "missing_content": [
            {"excerpt": "Uma nota de rodape importante que ficou de fora.", "reason": "nao foi capturada por nenhum item"}
        ],
        "warnings": [],
    }

    run_generation(db_session, current_user, project, inventory_project_file)

    items = db_session.execute(
        select(SourceContentItem).where(SourceContentItem.project_file_id == inventory_project_file.id)
    ).scalars().all()

    fallback_items = [i for i in items if (i.metadata_json or {}).get("source") == "coverage_check_gap"]
    assert len(fallback_items) == 1
    assert fallback_items[0].status == "requires_review"
    assert "nota de rodape" in fallback_items[0].source_text


def test_src_codes_are_sequential_and_unique(db_session, current_user, project, inventory_project_file, fake_ai_provider):
    add_extracted_page(
        db_session,
        inventory_project_file,
        1,
        [("paragraph", "primeiro paragrafo"), ("paragraph", "segundo paragrafo"), ("paragraph", "terceiro paragrafo")],
    )

    run_generation(db_session, current_user, project, inventory_project_file)

    items = db_session.execute(
        select(SourceContentItem)
        .where(SourceContentItem.project_file_id == inventory_project_file.id)
        .order_by(SourceContentItem.item_code)
    ).scalars().all()

    codes = [i.item_code for i in items]
    assert codes == sorted(codes)
    assert len(codes) == len(set(codes))
    assert codes[0] == "SRC-0001"


def test_source_order_follows_document_order(db_session, current_user, project, inventory_project_file, fake_ai_provider):
    add_extracted_page(db_session, inventory_project_file, 1, [("paragraph", "conteudo da pagina um")])
    add_extracted_page(db_session, inventory_project_file, 2, [("paragraph", "conteudo da pagina dois")])

    run_generation(db_session, current_user, project, inventory_project_file)

    items = db_session.execute(
        select(SourceContentItem)
        .where(SourceContentItem.project_file_id == inventory_project_file.id)
        .order_by(SourceContentItem.source_order.asc())
    ).scalars().all()

    assert items[0].page_start == 1
    assert items[-1].page_start == 2
    assert all(items[i].source_order <= items[i + 1].source_order for i in range(len(items) - 1))


def test_items_are_isolated_between_documents(
    db_session, current_user, project, inventory_project_file, other_inventory_project_file, fake_ai_provider
):
    add_extracted_page(db_session, inventory_project_file, 1, [("paragraph", "conteudo do documento 1")])

    run_generation(db_session, current_user, project, inventory_project_file)

    other_items = db_session.execute(
        select(SourceContentItem).where(SourceContentItem.project_file_id == other_inventory_project_file.id)
    ).scalars().all()
    assert other_items == []


def test_full_rebuild_does_not_delete_approved_items(
    db_session, current_user, project, inventory_project_file, fake_ai_provider
):
    add_extracted_page(db_session, inventory_project_file, 1, [("paragraph", "conteudo original")])
    run_generation(db_session, current_user, project, inventory_project_file)

    items = db_session.execute(
        select(SourceContentItem).where(SourceContentItem.project_file_id == inventory_project_file.id)
    ).scalars().all()
    assert len(items) == 1
    items[0].status = "approved"
    db_session.add(items[0])
    db_session.commit()
    approved_id = items[0].id

    run_generation(db_session, current_user, project, inventory_project_file, mode="full_rebuild")

    still_present = db_session.get(SourceContentItem, approved_id)
    assert still_present is not None
    assert still_present.status == "approved"  # nao foi superseded, nunca apagado


def test_full_rebuild_supersedes_non_approved_items_instead_of_deleting(
    db_session, current_user, project, inventory_project_file, fake_ai_provider
):
    add_extracted_page(db_session, inventory_project_file, 1, [("paragraph", "conteudo original")])
    job1 = run_generation(db_session, current_user, project, inventory_project_file)
    assert job1.status == "completed"

    first_items = db_session.execute(
        select(SourceContentItem).where(SourceContentItem.project_file_id == inventory_project_file.id)
    ).scalars().all()
    first_id = first_items[0].id

    run_generation(db_session, current_user, project, inventory_project_file, mode="full_rebuild")

    original = db_session.get(SourceContentItem, first_id)
    assert original is not None  # preservado, nao apagado
    assert original.status == "rejected"
    assert (original.metadata_json or {}).get("superseded_by_reprocess") is True

    all_items = db_session.execute(
        select(SourceContentItem).where(SourceContentItem.project_file_id == inventory_project_file.id)
    ).scalars().all()
    assert len(all_items) == 2  # o superseded + o novo gerado
