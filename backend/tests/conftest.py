import os

import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_veriba.db"
os.environ["RUN_MIGRATIONS_ON_STARTUP"] = "false"

import app.services.storage as _storage_module


class _InMemoryStorage:
    def __init__(self):
        self._files: dict[str, bytes] = {}

    def save_bytes(self, key: str, data: bytes, content_type: str | None = None) -> str:
        self._files[key] = data
        return self.public_url(key)

    def public_url(self, key: str) -> str:
        return f"http://testserver/storage/{key}"

    def delete_prefix(self, prefix: str) -> int:
        keys = [k for k in list(self._files) if k.startswith(prefix)]
        for k in keys:
            del self._files[k]
        return len(keys)

    def healthcheck(self) -> str:
        return "connected"


_storage_module._storage_instance = _InMemoryStorage()

from app.db.base import Base
from app.db.session import engine
from app.main import app


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client

