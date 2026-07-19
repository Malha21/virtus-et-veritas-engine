from app.schemas.source_inventory_ai import AIInventoryItemResponse
from app.services.source_inventory_validator import (
    anchor_item_to_blocks,
    are_likely_same_chunk_overlap_duplicate,
    validate_persisted_inventory,
)
from tests.conftest import add_extracted_page


def _make_ai_item(**overrides) -> AIInventoryItemResponse:
    base = {
        "temporary_id": "TMP-0001",
        "title": "Titulo",
        "normalized_content": "Conteudo normalizado",
        "source_text": "texto original do bloco",
        "content_type": "concept",
        "importance": "relevant",
        "page_start": 1,
        "page_end": 1,
        "source_block_codes": ["P0001-B0001"],
        "source_order": 1,
    }
    base.update(overrides)
    return AIInventoryItemResponse(**base)


def test_anchor_item_valid_when_source_text_matches_block(db_session, inventory_project_file):
    _, blocks = add_extracted_page(db_session, inventory_project_file, 1, [("paragraph", "texto original do bloco")])
    blocks_by_code = {b.block_code: b for b in blocks}

    item = _make_ai_item(source_text="texto original do bloco")
    result = anchor_item_to_blocks(item, blocks_by_code, chunk_page_start=1, chunk_page_end=1)

    assert result.is_valid is True
    assert len(result.resolved_blocks) == 1


def test_anchor_item_invalid_when_block_code_missing(db_session, inventory_project_file):
    _, blocks = add_extracted_page(db_session, inventory_project_file, 1, [("paragraph", "texto original")])
    blocks_by_code = {b.block_code: b for b in blocks}

    item = _make_ai_item(source_block_codes=["P9999-B9999"])
    result = anchor_item_to_blocks(item, blocks_by_code, chunk_page_start=1, chunk_page_end=1)

    assert result.is_valid is False
    assert any("inexistente" in e for e in result.errors)


def test_anchor_item_invalid_when_source_text_unrelated(db_session, inventory_project_file):
    _, blocks = add_extracted_page(
        db_session, inventory_project_file, 1, [("paragraph", "conteudo totalmente diferente sobre outro assunto")]
    )
    blocks_by_code = {b.block_code: b for b in blocks}

    item = _make_ai_item(source_text="frase inventada sem relacao nenhuma com o bloco original")
    result = anchor_item_to_blocks(item, blocks_by_code, chunk_page_start=1, chunk_page_end=1)

    assert result.is_valid is False
    assert any("ancorado" in e for e in result.errors)


def test_anchor_item_invalid_when_pages_outside_chunk_range(db_session, inventory_project_file):
    _, blocks = add_extracted_page(db_session, inventory_project_file, 1, [("paragraph", "texto do bloco")])
    blocks_by_code = {b.block_code: b for b in blocks}

    item = _make_ai_item(source_text="texto do bloco", page_start=5, page_end=5)
    result = anchor_item_to_blocks(item, blocks_by_code, chunk_page_start=1, chunk_page_end=1)

    assert result.is_valid is False
    assert any("fora do intervalo" in e for e in result.errors)


def test_dedup_detects_chunk_overlap_artifact():
    is_dup, ratio = are_likely_same_chunk_overlap_duplicate(
        "o conceito de lideranca envolve influenciar pessoas",
        {"P0006-B0001"},
        (6, 6),
        "o conceito de lideranca envolve influenciar pessoas",
        {"P0006-B0001"},
        (6, 6),
    )
    assert is_dup is True
    assert ratio > 0.8


def test_dedup_does_not_merge_distant_repetition():
    is_dup, _ratio = are_likely_same_chunk_overlap_duplicate(
        "o conceito de lideranca envolve influenciar pessoas",
        {"P0002-B0001"},
        (2, 2),
        "o conceito de lideranca envolve influenciar pessoas",
        {"P0050-B0001"},
        (50, 50),
    )
    assert is_dup is False


def test_dedup_ignores_unrelated_content():
    is_dup, ratio = are_likely_same_chunk_overlap_duplicate(
        "conceito de lideranca", {"P0001-B0001"}, (1, 1), "receita de bolo de chocolate", {"P0002-B0001"}, (2, 2)
    )
    assert is_dup is False
    assert ratio < 0.5


def test_validate_persisted_inventory_flags_empty_fields(project, project_file):
    from app.models.source_content_item import SourceContentItem

    valid_item = SourceContentItem(
        project_id=project.id,
        project_file_id=project_file.id,
        item_code="SRC-0001",
        title="Titulo valido",
        source_text="texto",
        normalized_content="conteudo",
        content_type="concept",
        importance="relevant",
        page_start=1,
        page_end=1,
        source_order=0,
    )
    invalid_item = SourceContentItem(
        project_id=project.id,
        project_file_id=project_file.id,
        item_code="SRC-0002",
        title="",
        source_text="texto",
        normalized_content="conteudo",
        content_type="not_a_type",
        importance="relevant",
        page_start=0,
        page_end=1,
        source_order=0,
    )

    result = validate_persisted_inventory([valid_item, invalid_item])

    assert result.total_items == 2
    assert result.valid_items == 1
    assert result.invalid_items == 1
    assert result.status == "requires_review"
    assert any(issue.item_code == "SRC-0002" for issue in result.issues)
