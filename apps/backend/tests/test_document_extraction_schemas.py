import pytest

from app.schemas.document_block import DocumentBlockBase
from app.schemas.document_extraction import DocumentReprocessRequest
from app.schemas.document_page import DocumentPageBase


def test_document_page_schema_rejects_invalid_status():
    with pytest.raises(ValueError):
        DocumentPageBase(page_number=1, extraction_status="not_a_status")


def test_document_page_schema_rejects_non_positive_page_number():
    with pytest.raises(ValueError):
        DocumentPageBase(page_number=0)


def test_document_page_schema_accepts_valid_payload():
    page = DocumentPageBase(page_number=1, extraction_status="extracted", character_count=10, word_count=2)
    assert page.page_number == 1


def test_document_block_schema_rejects_invalid_block_type():
    with pytest.raises(ValueError):
        DocumentBlockBase(block_code="P0001-B0001", block_type="not_a_type", source_text="texto")


def test_document_block_schema_rejects_confidence_out_of_range():
    with pytest.raises(ValueError):
        DocumentBlockBase(block_code="P0001-B0001", source_text="texto", confidence_score=101)


def test_document_block_schema_rejects_negative_block_order():
    with pytest.raises(ValueError):
        DocumentBlockBase(block_code="P0001-B0001", source_text="texto", block_order=-1)


def test_reprocess_request_defaults_to_failed_scope():
    request = DocumentReprocessRequest()
    assert request.scope == "failed"


def test_reprocess_request_rejects_invalid_scope():
    with pytest.raises(ValueError):
        DocumentReprocessRequest(scope="not_a_scope")


def test_reprocess_request_page_scope_requires_page_number():
    with pytest.raises(ValueError):
        DocumentReprocessRequest(scope="page")


def test_reprocess_request_page_scope_with_page_number_is_valid():
    request = DocumentReprocessRequest(scope="page", page_number=3)
    assert request.page_number == 3
