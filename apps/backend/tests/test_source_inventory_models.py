import pytest
from sqlalchemy.exc import IntegrityError

from app.models.source_content_item import SourceContentItem
from app.models.source_content_item_block import SourceContentItemBlock
from app.models.source_content_item_dependency import SourceContentItemDependency
from tests.conftest import add_extracted_page


def _make_item(project, project_file, item_code="SRC-0001"):
    return SourceContentItem(
        project_id=project.id,
        project_file_id=project_file.id,
        item_code=item_code,
        title="Item de teste",
        source_text="texto",
        normalized_content="conteudo",
        content_type="concept",
        importance="relevant",
        page_start=1,
        page_end=1,
        source_order=0,
    )


def test_item_block_association_unique(db_session, project, inventory_project_file):
    _, blocks = add_extracted_page(db_session, inventory_project_file, 1, [("paragraph", "texto")])
    item = _make_item(project, inventory_project_file)
    db_session.add(item)
    db_session.flush()

    db_session.add(SourceContentItemBlock(source_item_id=item.id, block_id=blocks[0].id))
    db_session.flush()

    db_session.add(SourceContentItemBlock(source_item_id=item.id, block_id=blocks[0].id))
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_item_can_reference_multiple_blocks(db_session, project, inventory_project_file):
    _, blocks = add_extracted_page(
        db_session, inventory_project_file, 1, [("paragraph", "parte um"), ("paragraph", "parte dois")]
    )
    item = _make_item(project, inventory_project_file)
    db_session.add(item)
    db_session.flush()

    db_session.add(SourceContentItemBlock(source_item_id=item.id, block_id=blocks[0].id, source_order=0, is_primary=True))
    db_session.add(SourceContentItemBlock(source_item_id=item.id, block_id=blocks[1].id, source_order=1))
    db_session.flush()  # nao deve levantar erro


def test_block_can_be_referenced_by_multiple_items(db_session, project, inventory_project_file):
    _, blocks = add_extracted_page(db_session, inventory_project_file, 1, [("table", "tabela com dois fatos")])
    item1 = _make_item(project, inventory_project_file, item_code="SRC-0001")
    item2 = _make_item(project, inventory_project_file, item_code="SRC-0002")
    db_session.add_all([item1, item2])
    db_session.flush()

    db_session.add(SourceContentItemBlock(source_item_id=item1.id, block_id=blocks[0].id))
    db_session.add(SourceContentItemBlock(source_item_id=item2.id, block_id=blocks[0].id))
    db_session.flush()  # nao deve levantar erro


def test_dependency_no_self_reference(db_session, project, inventory_project_file):
    item = _make_item(project, inventory_project_file)
    db_session.add(item)
    db_session.flush()

    db_session.add(
        SourceContentItemDependency(source_item_id=item.id, depends_on_source_item_id=item.id, dependency_type="depends_on")
    )
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_dependency_unique_pair_and_type(db_session, project, inventory_project_file):
    item1 = _make_item(project, inventory_project_file, item_code="SRC-0001")
    item2 = _make_item(project, inventory_project_file, item_code="SRC-0002")
    db_session.add_all([item1, item2])
    db_session.flush()

    db_session.add(
        SourceContentItemDependency(
            source_item_id=item1.id, depends_on_source_item_id=item2.id, dependency_type="exception_to"
        )
    )
    db_session.flush()

    db_session.add(
        SourceContentItemDependency(
            source_item_id=item1.id, depends_on_source_item_id=item2.id, dependency_type="exception_to"
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_deleting_source_item_cascades_to_blocks_and_dependencies(db_session, project, inventory_project_file):
    _, blocks = add_extracted_page(db_session, inventory_project_file, 1, [("paragraph", "texto")])
    item1 = _make_item(project, inventory_project_file, item_code="SRC-0001")
    item2 = _make_item(project, inventory_project_file, item_code="SRC-0002")
    db_session.add_all([item1, item2])
    db_session.flush()

    assoc = SourceContentItemBlock(source_item_id=item1.id, block_id=blocks[0].id)
    dependency = SourceContentItemDependency(
        source_item_id=item2.id, depends_on_source_item_id=item1.id, dependency_type="depends_on"
    )
    db_session.add_all([assoc, dependency])
    db_session.flush()
    assoc_id, dependency_id = assoc.id, dependency.id

    db_session.delete(item1)
    db_session.flush()
    db_session.expire_all()

    assert db_session.get(SourceContentItemBlock, assoc_id) is None
    assert db_session.get(SourceContentItemDependency, dependency_id) is None


def test_deleting_document_block_cascades_to_association(db_session, project, inventory_project_file):
    _, blocks = add_extracted_page(db_session, inventory_project_file, 1, [("paragraph", "texto")])
    item = _make_item(project, inventory_project_file)
    db_session.add(item)
    db_session.flush()

    assoc = SourceContentItemBlock(source_item_id=item.id, block_id=blocks[0].id)
    db_session.add(assoc)
    db_session.flush()
    assoc_id = assoc.id

    db_session.delete(blocks[0])
    db_session.flush()
    db_session.expire_all()

    assert db_session.get(SourceContentItemBlock, assoc_id) is None
    # o item do inventario em si nao deve ser apagado so porque um bloco de origem sumiu
    assert db_session.get(SourceContentItem, item.id) is not None
