import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.models  # noqa: F401
from app.api.router import api_router
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.core.responses import register_exception_handlers
from app.core.security import utcnow
from app.db.migrations import run_migrations
from app.scripts.seed_internal_admin import ensure_internal_admin

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()

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

    @app.on_event("startup")
    def on_startup() -> None:
        if settings.run_migrations_on_startup:
            run_migrations()
        if settings.seed_internal_admin_on_startup:
            result = ensure_internal_admin()
            logger.info(
                "Internal admin ready at %s (%s)",
                result["route"],
                "created" if result["created"] else "existing",
            )

    return app


app = create_app()
