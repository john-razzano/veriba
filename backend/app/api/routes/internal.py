from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_internal_admin
from app.core.responses import success_response
from app.core.security import hash_password
from app.db.session import get_db
from app.models import Credit, CreditStatus, Practice, Role, Session as PhotoSession, SessionStatus, User
from app.schemas.internal import InternalPracticeCreateRequest, InternalPracticeOwnerUpdateRequest
from app.schemas.practice import PracticeUpdateRequest
from app.services.logic import derive_initials, normalize_website, unique_widget_slug
from app.services.serializers import (
    serialize_credit,
    serialize_practice,
    serialize_session_summary,
    serialize_user,
)

router = APIRouter(prefix="/internal", tags=["internal"])


def _internal_practice_ids(db: Session) -> set[str]:
    return set(
        db.scalars(select(User.practice_id).where(User.role == Role.internal_admin.value)).all()
    )


def _practice_query(db: Session):
    query = select(Practice)
    internal_ids = _internal_practice_ids(db)
    if internal_ids:
        query = query.where(Practice.id.not_in(internal_ids))
    return query


def _practice_stats(db: Session, practice_id: str) -> dict:
    published = db.scalar(
        select(func.count()).select_from(PhotoSession).where(
            PhotoSession.practice_id == practice_id,
            PhotoSession.status == SessionStatus.published.value,
            PhotoSession.archived_at.is_(None),
        )
    ) or 0
    pending = db.scalar(
        select(func.count()).select_from(PhotoSession).where(
            PhotoSession.practice_id == practice_id,
            PhotoSession.status.in_(
                [
                    SessionStatus.draft.value,
                    SessionStatus.pending_after.value,
                    SessionStatus.pending_consent.value,
                    SessionStatus.ready_to_publish.value,
                    SessionStatus.unpublished.value,
                ]
            ),
            PhotoSession.archived_at.is_(None),
        )
    ) or 0
    team_count = db.scalar(
        select(func.count()).select_from(User).where(
            User.practice_id == practice_id,
            User.role != Role.internal_admin.value,
        )
    ) or 0
    active_credit_value = db.scalar(
        select(func.coalesce(func.sum(Credit.amount), 0)).where(
            Credit.practice_id == practice_id,
            Credit.status == CreditStatus.active.value,
        )
    ) or 0
    redeemed_credit_value = db.scalar(
        select(func.coalesce(func.sum(Credit.amount), 0)).where(
            Credit.practice_id == practice_id,
            Credit.status == CreditStatus.redeemed.value,
        )
    ) or 0
    return {
        "team_count": team_count,
        "published_sessions": published,
        "pending_sessions": pending,
        "active_credit_value": active_credit_value,
        "redeemed_credit_value": redeemed_credit_value,
    }


def _serialize_internal_practice_summary(db: Session, practice: Practice) -> dict:
    owner = db.scalar(select(User).where(User.id == practice.owner_id)) if practice.owner_id else None
    return {
        **serialize_practice(practice),
        "owner": serialize_user(owner) if owner else None,
        "stats": _practice_stats(db, practice.id),
    }


def _get_target_practice(db: Session, practice_id: str) -> Practice:
    practice = db.scalar(_practice_query(db).where(Practice.id == practice_id))
    if practice is None:
        raise HTTPException(status_code=404, detail="Practice not found")
    return practice


@router.get("/overview")
def internal_overview(
    _: User = Depends(get_internal_admin),
    db: Session = Depends(get_db),
):
    practices = db.scalars(_practice_query(db)).all()
    practice_ids = [practice.id for practice in practices]
    if practice_ids:
        total_users = db.scalar(
            select(func.count()).select_from(User).where(
                User.practice_id.in_(practice_ids),
                User.role != Role.internal_admin.value,
            )
        ) or 0
        published_sessions = db.scalar(
            select(func.count()).select_from(PhotoSession).where(
                PhotoSession.practice_id.in_(practice_ids),
                PhotoSession.status == SessionStatus.published.value,
                PhotoSession.archived_at.is_(None),
            )
        ) or 0
        pending_sessions = db.scalar(
            select(func.count()).select_from(PhotoSession).where(
                PhotoSession.practice_id.in_(practice_ids),
                PhotoSession.status.in_(
                    [
                        SessionStatus.draft.value,
                        SessionStatus.pending_after.value,
                        SessionStatus.pending_consent.value,
                        SessionStatus.ready_to_publish.value,
                        SessionStatus.unpublished.value,
                    ]
                ),
                PhotoSession.archived_at.is_(None),
            )
        ) or 0
        active_credit_value = db.scalar(
            select(func.coalesce(func.sum(Credit.amount), 0)).where(
                Credit.practice_id.in_(practice_ids),
                Credit.status == CreditStatus.active.value,
            )
        ) or 0
        redeemed_credit_value = db.scalar(
            select(func.coalesce(func.sum(Credit.amount), 0)).where(
                Credit.practice_id.in_(practice_ids),
                Credit.status == CreditStatus.redeemed.value,
            )
        ) or 0
    else:
        total_users = published_sessions = pending_sessions = active_credit_value = redeemed_credit_value = 0

    latest_practices = practices[:5]

    return success_response(
        {
            "practice_count": len(practices),
            "medspa_user_count": total_users,
            "published_session_count": published_sessions,
            "pending_session_count": pending_sessions,
            "active_credit_value": active_credit_value,
            "redeemed_credit_value": redeemed_credit_value,
            "latest_practices": [
                _serialize_internal_practice_summary(db, practice) for practice in latest_practices
            ],
        }
    )


@router.get("/practices")
def list_practices(
    query: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(get_internal_admin),
    db: Session = Depends(get_db),
):
    practice_query = _practice_query(db)
    if query:
        pattern = f"%{query.strip()}%"
        practice_query = practice_query.where(
            Practice.name.ilike(pattern)
            | Practice.location.ilike(pattern)
            | Practice.widget_slug.ilike(pattern)
        )

    practices = db.scalars(practice_query.order_by(Practice.created_at.desc()).offset(offset).limit(limit)).all()
    total = db.scalar(select(func.count()).select_from(practice_query.subquery())) or 0

    return success_response(
        {
            "practices": [_serialize_internal_practice_summary(db, practice) for practice in practices],
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    )


@router.post("/practices")
def create_practice(
    payload: InternalPracticeCreateRequest,
    _: User = Depends(get_internal_admin),
    db: Session = Depends(get_db),
):
    existing = db.scalar(select(User).where(User.email == payload.owner_email.lower()))
    if existing:
        raise HTTPException(status_code=409, detail="Owner email already in use")

    practice = Practice(
        name=payload.practice_name,
        location=payload.practice_location,
        website=normalize_website(payload.practice_website),
        widget_slug=unique_widget_slug(db, payload.practice_name),
        auto_publish=payload.auto_publish,
    )
    if payload.credit_expiration_days is not None:
        practice.credit_expiration_days = payload.credit_expiration_days
    if payload.default_discounts:
        if payload.default_discounts.full is not None:
            practice.default_discount_full = payload.default_discounts.full
        if payload.default_discounts.partial is not None:
            practice.default_discount_partial = payload.default_discounts.partial
        if payload.default_discounts.full_blur is not None:
            practice.default_discount_blur = payload.default_discounts.full_blur

    db.add(practice)
    db.flush()

    owner = User(
        email=payload.owner_email.lower(),
        password_hash=hash_password(payload.owner_password),
        name=payload.owner_name,
        initials=derive_initials(payload.owner_name),
        role=Role.owner.value,
        practice_id=practice.id,
    )
    db.add(owner)
    db.flush()

    practice.owner_id = owner.id
    db.commit()
    db.refresh(practice)

    return success_response(
        {
            "practice": _serialize_internal_practice_summary(db, practice),
            "owner": serialize_user(owner),
        },
        status_code=201,
    )


@router.get("/practices/{practice_id}")
def get_practice_detail(
    practice_id: str,
    _: User = Depends(get_internal_admin),
    db: Session = Depends(get_db),
):
    practice = _get_target_practice(db, practice_id)
    users = db.scalars(
        select(User).where(
            User.practice_id == practice.id,
            User.role != Role.internal_admin.value,
        ).order_by(User.created_at.asc())
    ).all()
    recent_sessions = db.scalars(
        select(PhotoSession).where(
            PhotoSession.practice_id == practice.id,
            PhotoSession.archived_at.is_(None),
        ).order_by(PhotoSession.updated_at.desc()).limit(8)
    ).all()
    recent_credits = db.scalars(
        select(Credit).where(Credit.practice_id == practice.id).order_by(Credit.created_at.desc()).limit(8)
    ).all()
    owner = db.scalar(select(User).where(User.id == practice.owner_id)) if practice.owner_id else None

    return success_response(
        {
            "practice": serialize_practice(practice),
            "owner": serialize_user(owner) if owner else None,
            "users": [serialize_user(user) for user in users],
            "stats": _practice_stats(db, practice.id),
            "recent_sessions": [serialize_session_summary(session) for session in recent_sessions],
            "recent_credits": [serialize_credit(credit) for credit in recent_credits],
        }
    )


@router.patch("/practices/{practice_id}")
def update_practice(
    practice_id: str,
    payload: PracticeUpdateRequest,
    _: User = Depends(get_internal_admin),
    db: Session = Depends(get_db),
):
    practice = _get_target_practice(db, practice_id)

    for field in ("name", "location", "website", "lat", "lng", "credit_expiration_days", "auto_publish"):
        value = getattr(payload, field)
        if value is not None:
            setattr(practice, field, value if field != "website" else normalize_website(value))

    if payload.default_discounts:
        if payload.default_discounts.full is not None:
            practice.default_discount_full = payload.default_discounts.full
        if payload.default_discounts.partial is not None:
            practice.default_discount_partial = payload.default_discounts.partial
        if payload.default_discounts.full_blur is not None:
            practice.default_discount_blur = payload.default_discounts.full_blur

    db.add(practice)
    db.commit()
    db.refresh(practice)
    return success_response(_serialize_internal_practice_summary(db, practice))


@router.patch("/practices/{practice_id}/owner")
def update_practice_owner(
    practice_id: str,
    payload: InternalPracticeOwnerUpdateRequest,
    _: User = Depends(get_internal_admin),
    db: Session = Depends(get_db),
):
    practice = _get_target_practice(db, practice_id)
    if not practice.owner_id:
        raise HTTPException(status_code=404, detail="Practice owner not found")

    owner = db.scalar(select(User).where(User.id == practice.owner_id))
    if owner is None:
        raise HTTPException(status_code=404, detail="Practice owner not found")

    if payload.email and payload.email.lower() != owner.email:
        existing = db.scalar(select(User).where(User.email == payload.email.lower()))
        if existing:
            raise HTTPException(status_code=409, detail="Email already in use")
        owner.email = payload.email.lower()

    if payload.name is not None:
        owner.name = payload.name
        owner.initials = derive_initials(payload.name)

    db.add(owner)
    db.commit()
    db.refresh(owner)
    return success_response(serialize_user(owner))
