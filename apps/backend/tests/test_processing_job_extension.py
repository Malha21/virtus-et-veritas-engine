import pytest

from app.models.processing_job import ProcessingJob
from app.schemas.processing import ProcessingJobProgressUpdate, ProcessingJobResponse


def test_create_generation_job_with_new_fields(db_session, project, project_file, lesson_content):
    job = ProcessingJob(
        project_id=project.id,
        organization_id=project.organization_id,
        project_file_id=project_file.id,
        lesson_content_id=lesson_content.id,
        job_type="source_inventory",
        status="pending",
        total_items=50,
        processed_items=0,
        failed_items=0,
        current_item="Pagina 1",
        max_attempts=3,
    )
    db_session.add(job)
    db_session.flush()

    assert job.id is not None
    assert job.job_type == "source_inventory"
    assert job.project_file_id == project_file.id
    assert job.lesson_content_id == lesson_content.id


def test_update_job_progress_and_resume_after_failure(db_session, project):
    job = ProcessingJob(
        project_id=project.id,
        organization_id=project.organization_id,
        job_type="lesson_generation",
        status="processing",
        total_items=10,
        processed_items=3,
        attempts=1,
        max_attempts=3,
    )
    db_session.add(job)
    db_session.flush()

    job.status = "failed"
    job.error_message = "timeout"
    db_session.flush()

    job.status = "processing"
    job.attempts += 1
    job.processed_items = 4
    job.current_item = "item-5"
    db_session.flush()

    assert job.attempts == 2
    assert job.processed_items == 4
    assert job.status == "processing"


def test_job_filters_by_course_document_lesson_and_type(
    db_session, project, project_file, lesson_content
):
    db_session.add(
        ProcessingJob(
            project_id=project.id,
            organization_id=project.organization_id,
            project_file_id=project_file.id,
            lesson_content_id=lesson_content.id,
            job_type="course_audit",
            status="queued",
        )
    )
    db_session.flush()

    found = (
        db_session.query(ProcessingJob)
        .filter(
            ProcessingJob.project_id == project.id,
            ProcessingJob.project_file_id == project_file.id,
            ProcessingJob.lesson_content_id == lesson_content.id,
            ProcessingJob.job_type == "course_audit",
        )
        .one()
    )
    assert found.status == "queued"


def test_response_schema_serializes_new_fields(db_session, project, project_file):
    job = ProcessingJob(
        project_id=project.id,
        organization_id=project.organization_id,
        project_file_id=project_file.id,
        job_type="document_extraction",
        status="completed",
        total_items=20,
        processed_items=20,
        failed_items=0,
    )
    db_session.add(job)
    db_session.flush()

    response = ProcessingJobResponse.model_validate(job)
    assert response.project_file_id == project_file.id
    assert response.total_items == 20
    assert response.processed_items == 20


def test_progress_update_schema_rejects_processed_over_total():
    with pytest.raises(ValueError):
        ProcessingJobProgressUpdate(total_items=5, processed_items=6)


def test_progress_update_schema_rejects_negative_failed_items():
    with pytest.raises(ValueError):
        ProcessingJobProgressUpdate(failed_items=-1)


def test_progress_update_schema_rejects_progress_out_of_range():
    with pytest.raises(ValueError):
        ProcessingJobProgressUpdate(progress=150)
