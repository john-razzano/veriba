import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import app.models  # noqa: F401
from app.api.router import api_router
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.core.responses import register_exception_handlers
from app.core.security import utcnow
from app.db.base import Base
from app.db.session import engine


def create_app() -> FastAPI:
    settings = get_settings()
    os.makedirs(settings.storage_root, exist_ok=True)

    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        debug=settings.debug,
    )
    app.state.started_at = utcnow()
    app.state.now_fn = utcnow
    app.state.limiter = limiter
    allowed_origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_prefix)
    app.mount("/storage", StaticFiles(directory=settings.storage_root), name="storage")

    @app.on_event("startup")
    def on_startup() -> None:
        Base.metadata.create_all(bind=engine)

    return app


app = create_app()
