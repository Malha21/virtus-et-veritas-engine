from app.services.source_inventory_chunking import build_chunks, is_ignorable_block
from tests.conftest import add_extracted_page


def test_build_chunks_single_small_page(db_session, inventory_project_file):
    page, blocks = add_extracted_page(
        db_session, inventory_project_file, 1, [("paragraph", "Texto curto de uma pagina.")]
    )
    chunks, ignored = build_chunks([page], {1: blocks})

    assert len(chunks) == 1
    assert chunks[0].page_start == 1
    assert chunks[0].page_end == 1
    assert ignored == []


def test_build_chunks_skips_non_extracted_pages(db_session, inventory_project_file):
    page1, blocks1 = add_extracted_page(db_session, inventory_project_file, 1, [("paragraph", "Pagina 1.")])
    page2, _ = add_extracted_page(db_session, inventory_project_file, 2, [], extraction_status="empty")
    page3, _ = add_extracted_page(
        db_session, inventory_project_file, 3, [], extraction_status="requires_ocr", requires_ocr=True
    )

    chunks, ignored = build_chunks([page1, page2, page3], {1: blocks1})

    assert len(chunks) == 1
    assert sorted(ignored) == [2, 3]


def test_build_chunks_splits_when_exceeding_target_chars(db_session, inventory_project_file):
    pages = []
    blocks_by_page = {}
    for page_number in range(1, 6):
        page, blocks = add_extracted_page(
            db_session, inventory_project_file, page_number, [("paragraph", "palavra " * 500)]
        )
        pages.append(page)
        blocks_by_page[page_number] = blocks

    chunks, _ = build_chunks(pages, blocks_by_page, chunk_target_chars=1500)

    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.page_start <= chunk.page_end


def test_build_chunks_overlap_shares_boundary_page(db_session, inventory_project_file):
    pages = []
    blocks_by_page = {}
    for page_number in range(1, 6):
        page, blocks = add_extracted_page(
            db_session, inventory_project_file, page_number, [("paragraph", "palavra " * 500)]
        )
        pages.append(page)
        blocks_by_page[page_number] = blocks

    chunks, _ = build_chunks(pages, blocks_by_page, chunk_target_chars=1500)

    assert len(chunks) >= 2
    # a pagina final do chunk N deve ser a pagina inicial do chunk N+1 (sobreposicao)
    assert chunks[1].page_start == chunks[0].page_end
    assert chunks[1].overlap_from_previous is True
    assert chunks[0].overlap_from_previous is False


def test_build_chunks_preserves_block_order_within_chunk(db_session, inventory_project_file):
    page, blocks = add_extracted_page(
        db_session,
        inventory_project_file,
        1,
        [("title", "Titulo"), ("paragraph", "Primeiro paragrafo"), ("paragraph", "Segundo paragrafo")],
    )
    chunks, _ = build_chunks([page], {1: blocks})

    codes = [b.block_code for b in chunks[0].blocks]
    assert codes == ["P0001-B0001", "P0001-B0002", "P0001-B0003"]


def test_is_ignorable_block_only_when_repeated_header_footer(db_session, inventory_project_file):
    page, blocks = add_extracted_page(
        db_session,
        inventory_project_file,
        1,
        [("page_header", "Cabecalho institucional"), ("paragraph", "Conteudo real")],
    )
    header_block, paragraph_block = blocks

    assert is_ignorable_block(header_block) is False  # sem metadata "repeated" ainda
    header_block.metadata_json = {"repeated": True}
    assert is_ignorable_block(header_block) is True
    assert is_ignorable_block(paragraph_block) is False


def test_build_chunks_excludes_ignorable_blocks_from_content(db_session, inventory_project_file):
    page, blocks = add_extracted_page(
        db_session,
        inventory_project_file,
        1,
        [("page_footer", "Rodape repetido"), ("paragraph", "Conteudo relevante")],
    )
    footer_block, paragraph_block = blocks
    footer_block.metadata_json = {"repeated": True}
    db_session.add(footer_block)
    db_session.flush()

    chunks, _ = build_chunks([page], {1: blocks})

    codes = [b.block_code for b in chunks[0].blocks]
    assert paragraph_block.block_code in codes
    assert footer_block.block_code not in codes
