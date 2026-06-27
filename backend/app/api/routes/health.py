from datetime import timedelta

from fastapi import APIRouter, Request
from sqlalchemy import text

from app.core.responses import success_response
from app.db.session import SessionLocal
from app.services.storage import get_storage

router = APIRouter(prefix="/health", tags=["health"])


def _database_status() -> str:
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return "connected"
    except Exception:
        return "disconnected"


def _storage_status() -> str:
    try:
        return get_storage().healthcheck()
    except Exception:
        return "disconnected"


@router.get("")
def healthcheck(request: Request):
    started_at = request.app.state.started_at
    uptime = str((request.app.state.now_fn() - started_at)).split(".")[0]
    return success_response(
        {
            "status": "healthy",
            "version": request.app.version,
            "database": _database_status(),
            "storage": _storage_status(),
            "uptime": uptime,
        }
    )


@router.get("/db")
def db_health():
    return success_response({"database": _database_status()})


@router.get("/storage")
def storage_health():
    return success_response({"storage": _storage_status()})

