from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.ai_provider import AIProvider
from app.models.organization import Organization
from app.models.user import User
from app.providers.ai import PROVIDER_KEYS, resolve_provider_name


def run_seed() -> None:
    settings = get_settings()

    with SessionLocal() as db:
        organization = db.execute(
            select(Organization).where(Organization.slug == settings.seed_organization_slug)
        ).scalar_one_or_none()

        if organization is None:
            organization = Organization(
                name=settings.seed_organization_name,
                slug=settings.seed_organization_slug,
                status="active",
            )
            db.add(organization)
            db.commit()
            db.refresh(organization)

        admin_email = settings.seed_admin_email.lower()
        admin = db.execute(select(User).where(User.email == admin_email)).scalar_one_or_none()

        if admin is None:
            admin = User(
                organization_id=organization.id,
                name=settings.seed_admin_name,
                email=admin_email,
                password_hash=hash_password(settings.seed_admin_password),
                role="admin",
                status="active",
            )
            db.add(admin)

        for provider_key in PROVIDER_KEYS:
            provider = db.execute(
                select(AIProvider).where(AIProvider.provider_type == provider_key)
            ).scalar_one_or_none()

            if provider is None:
                provider = AIProvider(
                    name=resolve_provider_name(settings, provider_key),
                    provider_type=provider_key,
                    status="active",
                )
                db.add(provider)

        db.commit()


if __name__ == "__main__":
    run_seed()
