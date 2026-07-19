"""Divisao de paginas/blocos extraidos (fase 19.2) em chunks seguros para envio a IA,
com sobreposicao entre chunks para evitar perda de conceitos na fronteira."""

from dataclasses import dataclass, field

from app.models.document_block import DocumentBlock
from app.models.document_page import DocumentPage

CHUNK_TARGET_CHARS = 9000
CHUNK_MIN_PAGES_BEFORE_SPLIT = 1
CHARS_PER_TOKEN_ESTIMATE = 4


def is_ignorable_block(block: DocumentBlock) -> bool:
    """Cabecalhos/rodapes repetidos (fase 19.2) sao ignorados no envio a IA, mas
    permanecem intactos em document_blocks e sao contados no relatorio."""
    if block.block_type not in {"page_header", "page_footer"}:
        return False
    metadata = block.metadata_json or {}
    return bool(metadata.get("repeated"))


@dataclass
class ChunkPlan:
    chunk_id: str
    page_start: int
    page_end: int
    blocks: list[DocumentBlock] = field(default_factory=list)
    overlap_from_previous: bool = False
    token_estimate: int = 0

    @property
    def source_text(self) -> str:
        return "\n\n".join(
            f"[{block.block_code} | pagina {block.page_number}]\n{block.source_text}" for block in self.blocks
        )


def build_chunks(
    pages: list[DocumentPage],
    blocks_by_page: dict[int, list[DocumentBlock]],
    chunk_target_chars: int = CHUNK_TARGET_CHARS,
) -> tuple[list[ChunkPlan], list[int]]:
    """Retorna (chunks, ignored_block_ids_count_by_page_not_needed).

    Apenas paginas com texto util (extraction_status == 'extracted') entram nos
    chunks. Paginas vazias, com falha ou requires_ocr sao deixadas de fora do
    conteudo enviado a IA (mas contabilizadas separadamente no relatorio pelo
    chamador, que tem acesso a lista completa de paginas).
    """
    usable_pages = [p for p in pages if p.extraction_status == "extracted"]
    usable_pages.sort(key=lambda p: p.page_number)

    chunks: list[ChunkPlan] = []
    current_blocks: list[DocumentBlock] = []
    current_page_start: int | None = None
    current_page_end: int | None = None
    current_chars = 0
    chunk_index = 0
    overlap_next = False

    def flush_chunk() -> None:
        nonlocal chunk_index, current_blocks, current_page_start, current_page_end, current_chars, overlap_next
        if not current_blocks:
            return
        chunk_index += 1
        chunks.append(
            ChunkPlan(
                chunk_id=f"CHUNK-{chunk_index:04d}",
                page_start=current_page_start or 0,
                page_end=current_page_end or 0,
                blocks=list(current_blocks),
                overlap_from_previous=overlap_next,
                token_estimate=current_chars // CHARS_PER_TOKEN_ESTIMATE,
            )
        )

    for page in usable_pages:
        page_blocks = [b for b in blocks_by_page.get(page.page_number, []) if not is_ignorable_block(b)]
        if not page_blocks:
            continue

        page_chars = sum(len(b.source_text) for b in page_blocks)

        would_exceed = current_chars + page_chars > chunk_target_chars
        has_min_pages = current_page_start is not None and (
            current_page_end or 0
        ) - current_page_start + 1 >= CHUNK_MIN_PAGES_BEFORE_SPLIT

        if would_exceed and has_min_pages:
            last_page_number = current_page_end
            flush_chunk()
            overlap_next = False
            # sobreposicao: a ultima pagina do chunk anterior tambem abre o proximo
            if last_page_number is not None:
                overlap_blocks = [b for b in blocks_by_page.get(last_page_number, []) if not is_ignorable_block(b)]
                current_blocks = list(overlap_blocks)
                current_page_start = last_page_number
                current_page_end = last_page_number
                current_chars = sum(len(b.source_text) for b in overlap_blocks)
                overlap_next = True
            else:
                current_blocks = []
                current_page_start = None
                current_page_end = None
                current_chars = 0

        if current_page_start is None:
            current_page_start = page.page_number
        current_page_end = page.page_number
        # evita duplicar blocos da pagina de overlap que ja foi semeada acima
        existing_codes = {b.block_code for b in current_blocks}
        for block in page_blocks:
            if block.block_code not in existing_codes:
                current_blocks.append(block)
        current_chars = sum(len(b.source_text) for b in current_blocks)

    flush_chunk()

    ignored_page_numbers = [p.page_number for p in pages if p.extraction_status != "extracted"]
    return chunks, ignored_page_numbers
