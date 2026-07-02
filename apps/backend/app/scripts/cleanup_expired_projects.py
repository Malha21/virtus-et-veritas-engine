from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.project import Project

RETENTION_DAYS = 10


def run_cleanup() -> None:
    now = datetime.now(UTC)
    archive_cutoff = now - timedelta(days=RETENTION_DAYS)

    expired_projects = 0
    deleted_projects = 0

    with SessionLocal() as db:
        projects_to_expire = db.execute(
            select(Project).where(
                Project.expires_at.is_not(None),
                Project.expires_at < now,
                Project.status.not_in({"archived", "deleted", "expired"}),
                Project.deleted_at.is_(None),
            )
        ).scalars().all()

        for project in projects_to_expire:
            project.status = "expired"
            expired_projects += 1

        archived_projects = db.execute(
            select(Project).where(
                Project.status == "archived",
                Project.archived_at.is_not(None),
                Project.archived_at < archive_cutoff,
                Project.deleted_at.is_(None),
            )
        ).scalars().all()

        for project in archived_projects:
            project.status = "deleted"
            project.deleted_at = now

            deleted_projects += 1

        db.commit()

    print("Cleanup summary")
    print(f"- projects expired: {expired_projects}")
    print(f"- archived projects marked deleted: {deleted_projects}")
    print("- physical files removed: 0")
    print("- note: this version only updates project retention status")


if __name__ == "__main__":
    run_cleanup()
