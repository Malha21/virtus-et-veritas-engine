"""Validacao deterministica dos itens retornados pela IA (ancoragem) e do
inventario persistido como um todo (usado pelo endpoint /validate)."""

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from app.models.document_block import DocumentBlock
from app.models.source_content_item import SourceContentItem
from app.schemas.source_content_item import (
    SOURCE_CONTENT_ITEM_CONTENT_TYPES,
    SOURCE_CONTENT_ITEM_IMPORTANCE_LEVELS,
)
from app.schemas.source_inventory import InventoryValidationIssue, InventoryValidationResult
from app.schemas.source_inventory_ai import AIInventoryItemResponse

MIN_ANCHOR_WORD_OVERLAP_RATIO = 0.55
DUPLICATE_SIMILARITY_THRESHOLD = 0.82


def _normalize_for_comparison(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _word_overlap_ratio(source_text: str, reference_text: str) -> float:
    source_words = set(_normalize_for_comparison(source_text).split())
    reference_words = set(_normalize_for_comparison(reference_text).split())
    if not source_words:
        return 0.0
    return len(source_words & reference_words) / len(source_words)


@dataclass
class AnchorResult:
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    resolved_blocks: list[DocumentBlock] = field(default_factory=list)


def anchor_item_to_blocks(
    item: AIInventoryItemResponse,
    blocks_by_code: dict[str, DocumentBlock],
    chunk_page_start: int,
    chunk_page_end: int,
) -> AnchorResult:
    """Verifica se um item retornado pela IA esta de fato ancorado no chunk real:
    blocos existem, paginas estao dentro do intervalo do chunk, e o source_text
    tem sobreposicao substancial com o texto dos blocos referenciados."""
    errors: list[str] = []
    resolved: list[DocumentBlock] = []

    if not item.source_block_codes:
        errors.append("item nao referencia nenhum block_code")

    for code in item.source_block_codes:
        block = blocks_by_code.get(code)
        if block is None:
            errors.append(f"block_code inexistente no chunk: {code}")
            continue
        resolved.append(block)

    if item.page_start < chunk_page_start or item.page_end > chunk_page_end:
        errors.append(
            f"paginas {item.page_start}-{item.page_end} fora do intervalo do chunk "
            f"({chunk_page_start}-{chunk_page_end})"
        )

    if resolved:
        reference_text = "\n".join(b.source_text for b in resolved)
        overlap = _word_overlap_ratio(item.source_text, reference_text)
        if overlap < MIN_ANCHOR_WORD_OVERLAP_RATIO:
            errors.append(
                f"source_text pouco ancorado nos blocos referenciados (sobreposicao de palavras: {overlap:.0%})"
            )

    return AnchorResult(is_valid=not errors, errors=errors, resolved_blocks=resolved)


def are_likely_same_chunk_overlap_duplicate(
    item_a_normalized: str,
    item_a_block_codes: set[str],
    item_a_pages: tuple[int, int],
    item_b_normalized: str,
    item_b_block_codes: set[str],
    item_b_pages: tuple[int, int],
) -> tuple[bool, float]:
    """Camada 2 de deduplicacao: similaridade textual entre candidatos pre-selecionados
    (apenas itens com paginas sobrepostas ou adjacentes, nunca comparacao geral)."""
    pages_overlap_or_adjacent = not (item_a_pages[1] < item_b_pages[0] - 1 or item_b_pages[1] < item_a_pages[0] - 1)
    if not pages_overlap_or_adjacent:
        return False, 0.0

    ratio = SequenceMatcher(
        None, _normalize_for_comparison(item_a_normalized), _normalize_for_comparison(item_b_normalized)
    ).ratio()
    if ratio < DUPLICATE_SIMILARITY_THRESHOLD:
        return False, ratio

    shared_blocks = item_a_block_codes & item_b_block_codes
    total_blocks = item_a_block_codes | item_b_block_codes
    block_overlap = len(shared_blocks) / len(total_blocks) if total_blocks else 0.0

    # alta similaridade textual + blocos majoritariamente compartilhados = quase certamente
    # o mesmo conteudo capturado duas vezes pela sobreposicao de chunks (seguro fundir).
    # alta similaridade sem blocos compartilhados = repeticao real do documento (nao fundir).
    is_chunk_overlap_artifact = block_overlap >= 0.5
    return is_chunk_overlap_artifact, ratio


def validate_persisted_inventory(items: list[SourceContentItem]) -> InventoryValidationResult:
    """Validacao determinística do inventario ja persistido (endpoint /validate)."""
    issues: list[InventoryValidationIssue] = []
    valid_count = 0

    for item in items:
        item_issues: list[str] = []
        if not item.title or not item.title.strip():
            item_issues.append("titulo vazio")
        if not item.source_text or not item.source_text.strip():
            item_issues.append("source_text vazio")
        if not item.normalized_content or not item.normalized_content.strip():
            item_issues.append("normalized_content vazio")
        if item.content_type not in SOURCE_CONTENT_ITEM_CONTENT_TYPES:
            item_issues.append(f"content_type invalido: {item.content_type}")
        if item.importance not in SOURCE_CONTENT_ITEM_IMPORTANCE_LEVELS:
            item_issues.append(f"importance invalido: {item.importance}")
        if item.page_start is not None and item.page_start <= 0:
            item_issues.append("page_start deve ser maior que zero")
        if item.page_start is not None and item.page_end is not None and item.page_end < item.page_start:
            item_issues.append("page_end menor que page_start")
        if item.source_order < 0:
            item_issues.append("source_order negativo")

        if item_issues:
            for message in item_issues:
                issues.append(
                    InventoryValidationIssue(
                        source_item_id=item.id,
                        item_code=item.item_code,
                        issue_type="field_validation",
                        message=message,
                    )
                )
        else:
            valid_count += 1

    status = "valid" if not issues else "requires_review"
    return InventoryValidationResult(
        status=status,
        total_items=len(items),
        valid_items=valid_count,
        invalid_items=len(items) - valid_count,
        issues=issues,
    )
