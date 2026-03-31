from fastapi import APIRouter

from app.api.routes import (
    auth,
    credits,
    followups,
    gallery,
    health,
    patient,
    practices,
    sessions,
    users,
    widget,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(practices.router)
api_router.include_router(sessions.router)
api_router.include_router(followups.router)
api_router.include_router(patient.router)
api_router.include_router(credits.router)
api_router.include_router(gallery.router)
api_router.include_router(widget.router)
api_router.include_router(health.router)
