import pytest

from app.schemas.source_content_item import SourceContentItemCreate
from app.schemas.source_inventory import SourceInventoryItemManualUpdate, SourceInventoryReprocessRequest
from app.schemas.source_inventory_ai import AIInventoryChunkResponse, AIInventoryItemResponse


def test_expanded_content_types_accept_fase_19_3_values():
    for content_type in ["fact", "step", "rule", "exception", "case", "classification", "reference"]:
        item = SourceContentItemCreate(
            project_id="00000000-0000-0000-0000-000000000000",
            project_file_id="00000000-0000-0000-0000-000000000000",
            item_code="SRC-0001",
            title="Titulo",
            source_text="Texto",
            content_type=content_type,
        )
        assert item.content_type == content_type


def test_expanded_statuses_accept_fase_19_3_values():
    for status_value in ["generated", "validated", "possible_duplicate", "fragmented", "requires_review"]:
        item = SourceContentItemCreate(
            project_id="00000000-0000-0000-0000-000000000000",
            project_file_id="00000000-0000-0000-0000-000000000000",
            item_code="SRC-0001",
            title="Titulo",
            source_text="Texto",
            status=status_value,
        )
        assert item.status == status_value


def test_fase_19_1_content_types_still_valid():
    # garante que a ampliacao nao foi destrutiva
    for content_type in ["concept", "definition", "table", "quotation", "other"]:
        item = SourceContentItemCreate(
            project_id="00000000-0000-0000-0000-000000000000",
            project_file_id="00000000-0000-0000-0000-000000000000",
            item_code="SRC-0001",
            title="Titulo",
            source_text="Texto",
            content_type=content_type,
        )
        assert item.content_type == content_type


def test_ai_item_response_rejects_invalid_content_type():
    with pytest.raises(ValueError):
        AIInventoryItemResponse(
            temporary_id="TMP-0001",
            title="T",
            normalized_content="C",
            source_text="S",
            content_type="not_a_type",
            importance="relevant",
            page_start=1,
            page_end=1,
            source_order=1,
        )


def test_ai_item_response_rejects_page_end_before_start():
    with pytest.raises(ValueError):
        AIInventoryItemResponse(
            temporary_id="TMP-0001",
            title="T",
            normalized_content="C",
            source_text="S",
            content_type="concept",
            importance="relevant",
            page_start=5,
            page_end=2,
            source_order=1,
        )


def test_ai_chunk_response_parses_nested_items():
    response = AIInventoryChunkResponse(
        chunk_id="CHUNK-0001",
        items=[
            {
                "temporary_id": "TMP-0001",
                "title": "T",
                "normalized_content": "C",
                "source_text": "S",
                "content_type": "concept",
                "importance": "relevant",
                "page_start": 1,
                "page_end": 1,
                "source_order": 1,
            }
        ],
    )
    assert len(response.items) == 1
    assert response.items[0].temporary_id == "TMP-0001"


def test_reprocess_request_default_mode():
    request = SourceInventoryReprocessRequest()
    assert request.mode == "reprocess_failed"


def test_reprocess_request_rejects_invalid_mode():
    with pytest.raises(ValueError):
        SourceInventoryReprocessRequest(mode="not_a_mode")


def test_reprocess_request_pages_mode_requires_page_numbers():
    with pytest.raises(ValueError):
        SourceInventoryReprocessRequest(mode="reprocess_pages")


def test_reprocess_request_pages_mode_with_numbers_is_valid():
    request = SourceInventoryReprocessRequest(mode="reprocess_pages", page_numbers=[1, 2, 3])
    assert request.page_numbers == [1, 2, 3]


def test_manual_update_has_no_source_text_field():
    # garante deliberadamente que source_text nao pode ser editado por este schema
    assert "source_text" not in SourceInventoryItemManualUpdate.model_fields


def test_manual_update_rejects_invalid_importance():
    with pytest.raises(ValueError):
        SourceInventoryItemManualUpdate(importance="not_a_level")
