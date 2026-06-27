import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_veriba.db"
os.environ["STORAGE_BACKEND"] = "local"
os.environ["STORAGE_ROOT"] = str(Path(__file__).resolve().parent / "storage")
os.environ["PUBLIC_STORAGE_BASE_URL"] = "http://testserver/storage"

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

