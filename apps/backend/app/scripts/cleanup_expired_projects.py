from datetime import UTC, datetime, timedelta
from pathlib import Path
import shutil

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.project import Project

RETENTION_DAYS = 10


def is_inside_storage(path: Path, storage_root: Path) -> bool:
    try:
        path.resolve().relative_to(storage_root.resolve())
        return True
    except ValueError:
        return False


def remove_project_files(project: Project, storage_root: Path) -> tuple[int, list[str]]:
    errors: list[str] = []
    removed_count = 0
    project_dir = storage_root / "organizations" / str(project.organization_id) / "projects" / str(project.id)

    if not is_inside_storage(project_dir, storage_root):
        return 0, [f"Unsafe project path skipped: {project_dir}"]

    if project_dir.exists():
        try:
            shutil.rmtree(project_dir)
            removed_count += 1
        except Exception as exc:
            errors.append(f"Failed to remove {project_dir}: {exc}")

    return removed_count, errors


def run_cleanup() -> None:
    settings = get_settings()
    now = datetime.now(UTC)
    archive_cutoff = now - timedelta(days=RETENTION_DAYS)
    storage_root = Path(settings.storage_path).resolve()

    expired_projects = 0
    deleted_projects = 0
    removed_file_roots = 0
    errors: list[str] = []

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
            removed_count, project_errors = remove_project_files(project, storage_root)
            removed_file_roots += removed_count
            errors.extend(project_errors)

            project.status = "deleted"
            project.deleted_at = now

            deleted_projects += 1

        db.commit()

    print("Cleanup summary")
    print(f"- projects expired: {expired_projects}")
    print(f"- archived projects marked deleted: {deleted_projects}")
    print(f"- project storage roots removed: {removed_file_roots}")
    print(f"- errors: {len(errors)}")
    for error in errors:
        print(f"  - {error}")


if __name__ == "__main__":
    run_cleanup()
