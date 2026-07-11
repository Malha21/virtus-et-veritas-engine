import pytest
from sqlalchemy.exc import IntegrityError

from app.models.course_coverage_report import CourseCoverageReport
from app.schemas.course_coverage_report import CourseCoverageReportCreate


def test_create_course_coverage_report(db_session, project):
    report = CourseCoverageReport(
        project_id=project.id,
        version=1,
        total_source_items=10,
        covered_items=8,
        partially_covered_items=1,
        uncovered_items=1,
        coverage_percentage=90.0,
        fidelity_score=95.5,
        status="passed",
    )
    db_session.add(report)
    db_session.flush()

    assert report.id is not None
    assert report.version == 1


def test_version_unique_within_project(db_session, project):
    db_session.add(CourseCoverageReport(project_id=project.id, version=1))
    db_session.flush()

    db_session.add(CourseCoverageReport(project_id=project.id, version=1))
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_previous_reports_are_not_overwritten(db_session, project):
    db_session.add(CourseCoverageReport(project_id=project.id, version=1, coverage_percentage=50.0))
    db_session.add(CourseCoverageReport(project_id=project.id, version=2, coverage_percentage=80.0))
    db_session.flush()

    reports = (
        db_session.query(CourseCoverageReport)
        .filter(CourseCoverageReport.project_id == project.id)
        .order_by(CourseCoverageReport.version)
        .all()
    )
    assert [r.version for r in reports] == [1, 2]
    assert float(reports[0].coverage_percentage) == 50.0
    assert float(reports[1].coverage_percentage) == 80.0


def test_schema_rejects_coverage_percentage_out_of_range():
    with pytest.raises(ValueError):
        CourseCoverageReportCreate(project_id="00000000-0000-0000-0000-000000000000", coverage_percentage=150)


def test_schema_rejects_fidelity_score_out_of_range():
    with pytest.raises(ValueError):
        CourseCoverageReportCreate(project_id="00000000-0000-0000-0000-000000000000", fidelity_score=-1)


def test_schema_rejects_invalid_status():
    with pytest.raises(ValueError):
        CourseCoverageReportCreate(project_id="00000000-0000-0000-0000-000000000000", status="not_a_status")


def test_schema_rejects_item_counts_exceeding_total():
    with pytest.raises(ValueError):
        CourseCoverageReportCreate(
            project_id="00000000-0000-0000-0000-000000000000",
            total_source_items=5,
            covered_items=4,
            partially_covered_items=1,
            uncovered_items=1,
        )
