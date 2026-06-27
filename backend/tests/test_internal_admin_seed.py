from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hash_password, verify_password
from app.db.session import SessionLocal
from app.main import create_app
from app.models import Role, User
from app.scripts.seed_internal_admin import (
    INTERNAL_ADMIN_EMAIL,
    INTERNAL_ADMIN_PASSWORD,
    ensure_internal_admin,
    seed_internal_admin,
)


def _read_internal_admin() -> dict | None:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == INTERNAL_ADMIN_EMAIL))
        if user is None:
            return None

        return {
            "role": user.role,
            "practice_id": user.practice_id,
            "password_hash": user.password_hash,
        }


def test_app_startup_seeds_internal_admin_when_enabled(monkeypatch):
    monkeypatch.setenv("SEED_INTERNAL_ADMIN_ON_STARTUP", "true")
    get_settings.cache_clear()

    try:
        with TestClient(create_app()):
            admin = _read_internal_admin()

        assert admin is not None
        assert admin["role"] == Role.internal_admin.value
        assert verify_password(INTERNAL_ADMIN_PASSWORD, admin["password_hash"])
    finally:
        get_settings.cache_clear()


def test_ensure_internal_admin_preserves_existing_password():
    seed_internal_admin(reset_existing=True)

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == INTERNAL_ADMIN_EMAIL))
        assert user is not None
        user.password_hash = hash_password("changed-secret")
        db.add(user)
        db.commit()

    ensure_internal_admin()
    admin = _read_internal_admin()

    assert admin is not None
    assert admin["role"] == Role.internal_admin.value
    assert verify_password("changed-secret", admin["password_hash"])


def test_manual_seed_resets_existing_password_to_default():
    seed_internal_admin(reset_existing=True)

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == INTERNAL_ADMIN_EMAIL))
        assert user is not None
        user.password_hash = hash_password("changed-secret")
        db.add(user)
        db.commit()

    seed_internal_admin(reset_existing=True)
    admin = _read_internal_admin()

    assert admin is not None
    assert verify_password(INTERNAL_ADMIN_PASSWORD, admin["password_hash"])
