from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, or_, select

from app.core.responses import success_response
from app.db.session import SessionLocal
from app.models import Practice, Session as PhotoSession, SessionPhoto, SessionStatus, User
from app.services.serializers import (
    serialize_public_case_study,
    serialize_public_practice,
    serialize_public_session_card,
)

router = APIRouter(prefix="/gallery", tags=["gallery"])


def _published_sessions_base():
    return (
        select(PhotoSession, Practice)
        .join(Practice, Practice.id == PhotoSession.practice_id)
        .where(
            PhotoSession.status == SessionStatus.published.value,
            PhotoSession.archived_at.is_(None),
        )
    )


def _owner_for_practice(db, practice: Practice) -> User | None:
    if practice.owner_id is None:
        return None
    return db.scalar(select(User).where(User.id == practice.owner_id))


def _featured_session_for_practice(db, practice_id: str, *, practice: Practice | None = None) -> PhotoSession | None:
    # Use pinned session when set and still published/not archived
    if practice is not None and practice.featured_session_id:
        pinned = db.scalar(
            select(PhotoSession).where(
                PhotoSession.id == practice.featured_session_id,
                PhotoSession.status == SessionStatus.published.value,
                PhotoSession.archived_at.is_(None),
            )
        )
        if pinned:
            return pinned
    # Fall back to latest published
    return db.scalar(
        select(PhotoSession)
        .where(
            PhotoSession.practice_id == practice_id,
            PhotoSession.status == SessionStatus.published.value,
            PhotoSession.archived_at.is_(None),
        )
        .order_by(PhotoSession.published_at.desc(), PhotoSession.updated_at.desc())
        .limit(1)
    )


def _practice_count_subquery():
    return (
        select(
            PhotoSession.practice_id.label("practice_id"),
            func.count(PhotoSession.id).label("published_session_count"),
            func.max(PhotoSession.published_at).label("latest_published_at"),
        )
        .where(
            PhotoSession.status == SessionStatus.published.value,
            PhotoSession.archived_at.is_(None),
        )
        .group_by(PhotoSession.practice_id)
        .subquery()
    )


@router.get("/home")
def public_gallery_home(
    featured_sessions_limit: int = Query(default=6, ge=1, le=12),
    featured_practices_limit: int = Query(default=3, ge=1, le=8),
):
    with SessionLocal() as db:
        session_rows = db.execute(
            _published_sessions_base()
            .order_by(PhotoSession.published_at.desc(), PhotoSession.updated_at.desc())
            .limit(featured_sessions_limit)
        ).all()

        practice_counts = _practice_count_subquery()
        practice_rows = db.execute(
            select(Practice, practice_counts.c.published_session_count)
            .join(practice_counts, practice_counts.c.practice_id == Practice.id)
            .order_by(
                practice_counts.c.published_session_count.desc(),
                practice_counts.c.latest_published_at.desc(),
            )
            .limit(featured_practices_limit)
        ).all()

        featured_sessions = []
        for session, practice in session_rows:
            owner = _owner_for_practice(db, practice)
            featured_sessions.append(
                serialize_public_session_card(session, practice, owner=owner)
            )

        featured_practices = []
        for practice, published_session_count in practice_rows:
            owner = _owner_for_practice(db, practice)
            featured_session = _featured_session_for_practice(db, practice.id, practice=practice)
            featured_practices.append(
                serialize_public_practice(
                    practice,
                    owner=owner,
                    published_session_count=published_session_count or 0,
                    featured_session=featured_session,
                )
            )

        return success_response(
            {
                "featured_sessions": featured_sessions,
                "featured_practices": featured_practices,
            }
        )


@router.get("/sessions")
def list_public_sessions(
    query: str | None = Query(default=None, min_length=1),
    category: str | None = Query(default=None),
    location: str | None = Query(default=None, min_length=1),
    practice_slug: str | None = Query(default=None, min_length=1),
    limit: int = Query(default=12, ge=1, le=48),
    offset: int = Query(default=0, ge=0),
):
    with SessionLocal() as db:
        base = _published_sessions_base()

        if query:
            normalized = f"%{query.strip().lower()}%"
            base = base.where(
                or_(
                    func.lower(PhotoSession.treatment).like(normalized),
                    func.lower(func.coalesce(PhotoSession.treatment_details, "")).like(
                        normalized
                    ),
                    func.lower(Practice.name).like(normalized),
                    func.lower(Practice.location).like(normalized),
                )
            )
        if category:
            base = base.where(PhotoSession.category == category)
        if location:
            normalized_location = f"%{location.strip().lower()}%"
            base = base.where(func.lower(Practice.location).like(normalized_location))
        if practice_slug:
            base = base.where(Practice.widget_slug == practice_slug)

        total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
        rows = db.execute(
            base.order_by(PhotoSession.published_at.desc(), PhotoSession.updated_at.desc())
            .offset(offset)
            .limit(limit)
        ).all()
        available_categories = db.scalars(
            select(PhotoSession.category)
            .where(
                PhotoSession.status == SessionStatus.published.value,
                PhotoSession.archived_at.is_(None),
            )
            .distinct()
            .order_by(PhotoSession.category.asc())
        ).all()

        sessions = []
        for session, practice in rows:
            owner = _owner_for_practice(db, practice)
            sessions.append(serialize_public_session_card(session, practice, owner=owner))

        return success_response(
            {
                "sessions": sessions,
                "total": total,
                "limit": limit,
                "offset": offset,
                "filters": {
                    "query": query,
                    "category": category,
                    "location": location,
                    "practice_slug": practice_slug,
                },
                "available_categories": available_categories,
            }
        )


@router.get("/sessions/{session_id}")
def get_public_session(session_id: str):
    with SessionLocal() as db:
        row = db.execute(
            _published_sessions_base().where(PhotoSession.id == session_id).limit(1)
        ).first()
        if row is None:
            raise HTTPException(status_code=404, detail="Case study not found")

        session, practice = row
        owner = _owner_for_practice(db, practice)
        related_sessions = db.scalars(
            select(PhotoSession)
            .where(
                PhotoSession.practice_id == practice.id,
                PhotoSession.status == SessionStatus.published.value,
                PhotoSession.archived_at.is_(None),
                PhotoSession.id != session.id,
            )
            .order_by(PhotoSession.published_at.desc(), PhotoSession.updated_at.desc())
            .limit(3)
        ).all()
        published_count = db.scalar(
            select(func.count())
            .select_from(PhotoSession)
            .where(
                PhotoSession.practice_id == practice.id,
                PhotoSession.status == SessionStatus.published.value,
                PhotoSession.archived_at.is_(None),
            )
        ) or 0

        session_photo_rows = db.scalars(
            select(SessionPhoto)
            .where(SessionPhoto.session_id == session.id)
            .order_by(SessionPhoto.sort_order, SessionPhoto.created_at)
        ).all()
        from app.services.storage import get_storage as _gs
        _store = _gs()
        case_photos = [
            {"id": p.id, "url": _store.public_url(p.image_key), "blurhash": p.blurhash, "label": p.label}
            for p in session_photo_rows
        ]

        return success_response(
            {
                "session": serialize_public_case_study(session, practice, owner=owner, photos=case_photos),
                "practice": serialize_public_practice(
                    practice,
                    owner=owner,
                    published_session_count=published_count,
                    featured_session=session,
                ),
                "related_sessions": [
                    serialize_public_session_card(item, practice, owner=owner)
                    for item in related_sessions
                ],
            }
        )


@router.get("/practices")
def list_public_practices(
    query: str | None = Query(default=None, min_length=1),
    location: str | None = Query(default=None, min_length=1),
    limit: int = Query(default=12, ge=1, le=48),
    offset: int = Query(default=0, ge=0),
):
    with SessionLocal() as db:
        practice_counts = _practice_count_subquery()
        base = select(Practice, practice_counts.c.published_session_count).join(
            practice_counts, practice_counts.c.practice_id == Practice.id
        )

        if query:
            normalized = f"%{query.strip().lower()}%"
            base = base.where(
                or_(
                    func.lower(Practice.name).like(normalized),
                    func.lower(func.coalesce(Practice.website, "")).like(normalized),
                    func.lower(Practice.location).like(normalized),
                )
            )
        if location:
            normalized_location = f"%{location.strip().lower()}%"
            base = base.where(func.lower(Practice.location).like(normalized_location))

        total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
        rows = db.execute(
            base.order_by(
                practice_counts.c.published_session_count.desc(),
                Practice.name.asc(),
            )
            .offset(offset)
            .limit(limit)
        ).all()

        practices = []
        for practice, published_session_count in rows:
            owner = _owner_for_practice(db, practice)
            featured_session = _featured_session_for_practice(db, practice.id, practice=practice)
            practices.append(
                serialize_public_practice(
                    practice,
                    owner=owner,
                    published_session_count=published_session_count or 0,
                    featured_session=featured_session,
                )
            )

        return success_response(
            {
                "practices": practices,
                "total": total,
                "limit": limit,
                "offset": offset,
                "filters": {"query": query, "location": location},
            }
        )


@router.get("/practices/{practice_slug}")
def get_public_practice(practice_slug: str):
    with SessionLocal() as db:
        practice = db.scalar(select(Practice).where(Practice.widget_slug == practice_slug))
        if practice is None:
            raise HTTPException(status_code=404, detail="Provider not found")

        published_sessions = db.scalars(
            select(PhotoSession)
            .where(
                PhotoSession.practice_id == practice.id,
                PhotoSession.status == SessionStatus.published.value,
                PhotoSession.archived_at.is_(None),
            )
            .order_by(PhotoSession.published_at.desc(), PhotoSession.updated_at.desc())
        ).all()
        if not published_sessions:
            raise HTTPException(status_code=404, detail="Provider has no public cases")

        owner = _owner_for_practice(db, practice)
        featured_session = _featured_session_for_practice(db, practice.id, practice=practice) or published_sessions[0]
        return success_response(
            {
                "practice": serialize_public_practice(
                    practice,
                    owner=owner,
                    published_session_count=len(published_sessions),
                    featured_session=featured_session,
                ),
                "sessions": [
                    serialize_public_session_card(item, practice, owner=owner)
                    for item in published_sessions
                ],
            }
        )
