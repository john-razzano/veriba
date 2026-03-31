from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import select

from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.core.responses import success_response
from app.db.session import SessionLocal
from app.models import Practice, Session as PhotoSession, SessionStatus
from app.services.serializers import serialize_public_session

router = APIRouter(prefix="/widget", tags=["widget"])
widget_limit = get_settings().widget_rate_limit


def _resolve_practice_and_session(db, practice_slug: str, session_id: str | None = None):
    practice = db.scalar(select(Practice).where(Practice.widget_slug == practice_slug))
    if practice is None:
        raise HTTPException(status_code=404, detail="Practice not found")
    if session_id is None:
        return practice, None
    session = db.scalar(
        select(PhotoSession).where(
            PhotoSession.id == session_id,
            PhotoSession.practice_id == practice.id,
            PhotoSession.status == SessionStatus.published.value,
            PhotoSession.archived_at.is_(None),
        )
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return practice, session


@router.get("/{practice_slug}/gallery")
@limiter.limit(widget_limit)
def widget_gallery(
    request: Request,
    practice_slug: str,
    category: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    with SessionLocal() as db:
        practice, _ = _resolve_practice_and_session(db, practice_slug)
        query = select(PhotoSession).where(
            PhotoSession.practice_id == practice.id,
            PhotoSession.status == SessionStatus.published.value,
            PhotoSession.archived_at.is_(None),
        )
        if category:
            query = query.where(PhotoSession.category == category)
        sessions = db.scalars(query.order_by(PhotoSession.published_at.desc()).offset(offset).limit(limit)).all()
        total = len(
            db.scalars(query).all()
        )
        return success_response(
            {
                "practice": {"name": practice.name, "location": practice.location},
                "sessions": [serialize_public_session(item) for item in sessions],
                "total": total,
            }
        )


@router.get("/{practice_slug}/session/{session_id}")
@limiter.limit(widget_limit)
def widget_session_detail(request: Request, practice_slug: str, session_id: str):
    with SessionLocal() as db:
        practice, session = _resolve_practice_and_session(db, practice_slug, session_id)
        return success_response(
            {
                "practice": {"name": practice.name, "location": practice.location},
                "session": serialize_public_session(session),
            }
        )


@router.post("/{practice_slug}/session/{session_id}/view")
@limiter.limit(widget_limit)
def widget_track_view(request: Request, practice_slug: str, session_id: str):
    with SessionLocal() as db:
        _, session = _resolve_practice_and_session(db, practice_slug, session_id)
        session.page_views += 1
        db.add(session)
        db.commit()
        return success_response({"recorded": True})

