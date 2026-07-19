import uuid

import pytest
from pydantic import ValidationError

from app.schemas.coverage_plan import (
    CoveragePlanLessonSplitRequest,
    CoveragePlanLessonUpdate,
    CoveragePlanModuleUpdate,
    CoveragePlanRegenerateRequest,
)


def test_regenerate_request_rejects_invalid_mode():
    with pytest.raises(ValidationError):
        CoveragePlanRegenerateRequest(mode="not-a-real-mode")


def test_regenerate_request_accepts_known_mode():
    request = CoveragePlanRegenerateRequest(mode="recalculate_estimates")
    assert request.mode == "recalculate_estimates"


def test_module_update_rejects_invalid_status():
    with pytest.raises(ValidationError):
        CoveragePlanModuleUpdate(status="not-a-real-status")


def test_lesson_update_rejects_invalid_status():
    with pytest.raises(ValidationError):
        CoveragePlanLessonUpdate(status="not-a-real-status")


def test_lesson_split_rejects_overlapping_items():
    shared_id = uuid.uuid4()
    with pytest.raises(ValidationError):
        CoveragePlanLessonSplitRequest(
            first_title="Parte 1",
            second_title="Parte 2",
            first_source_item_ids=[shared_id],
            second_source_item_ids=[shared_id],
        )


def test_lesson_split_accepts_disjoint_items():
    request = CoveragePlanLessonSplitRequest(
        first_title="Parte 1",
        second_title="Parte 2",
        first_source_item_ids=[uuid.uuid4()],
        second_source_item_ids=[uuid.uuid4()],
    )
    assert request.first_title == "Parte 1"
