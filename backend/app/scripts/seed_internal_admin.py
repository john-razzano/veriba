from __future__ import annotations

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import Practice, Role, User
from app.services.logic import derive_initials, unique_widget_slug

INTERNAL_ADMIN_EMAIL = "admin@veriba-internal.studio"
INTERNAL_ADMIN_PASSWORD = "veriba-internal-2026"
INTERNAL_ADMIN_NAME = "Veriba Internal Admin"
INTERNAL_PRACTICE_NAME = "Veriba Internal Ops"
INTERNAL_PRACTICE_LOCATION = "Remote"
INTERNAL_PRACTICE_SLUG = "veriba-internal"


def seed_internal_admin(*, reset_existing: bool = True) -> dict:
    with SessionLocal() as db:
        practice = db.scalar(select(Practice).where(Practice.widget_slug == INTERNAL_PRACTICE_SLUG))
        if practice is None:
            practice = Practice(
                name=INTERNAL_PRACTICE_NAME,
                location=INTERNAL_PRACTICE_LOCATION,
                widget_slug=INTERNAL_PRACTICE_SLUG
                if db.scalar(select(Practice).where(Practice.widget_slug == INTERNAL_PRACTICE_SLUG)) is None
                else unique_widget_slug(db, INTERNAL_PRACTICE_NAME),
                auto_publish=False,
            )
            db.add(practice)
            db.flush()

        user = db.scalar(select(User).where(User.email == INTERNAL_ADMIN_EMAIL))
        created = user is None
        if user is None:
            user = User(
                email=INTERNAL_ADMIN_EMAIL,
                password_hash=hash_password(INTERNAL_ADMIN_PASSWORD),
                name=INTERNAL_ADMIN_NAME,
                initials=derive_initials(INTERNAL_ADMIN_NAME),
                role=Role.internal_admin.value,
                practice_id=practice.id,
            )
            db.add(user)
            db.flush()
        else:
            user.role = Role.internal_admin.value
            user.practice_id = practice.id
            if reset_existing:
                user.password_hash = hash_password(INTERNAL_ADMIN_PASSWORD)
                user.name = INTERNAL_ADMIN_NAME
                user.initials = derive_initials(INTERNAL_ADMIN_NAME)
            db.add(user)
            db.flush()

        practice.owner_id = user.id
        db.add(practice)
        db.commit()

        return {
            "email": INTERNAL_ADMIN_EMAIL,
            "password": INTERNAL_ADMIN_PASSWORD,
            "practice_name": practice.name,
            "route": "/veriba-admin/",
            "created": created,
        }


def ensure_internal_admin() -> dict:
    return seed_internal_admin(reset_existing=False)


def main() -> None:
    result = seed_internal_admin()
    print("Internal admin account ready:")
    print(f"- route: {result['route']}")
    print(f"- email: {result['email']}")
    print(f"- password: {result['password']}")
    print(f"- workspace: {result['practice_name']}")


if __name__ == "__main__":
    main()
