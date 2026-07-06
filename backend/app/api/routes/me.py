from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.responses import success_response
from app.core.security import utcnow
from app.db.session import get_db
from app.models import (
    ConsentTier,
    ConsultRequest,
    Credit,
    CreditStatus,
    Followup,
    FollowedPractice,
    FollowupStatus,
    Practice,
    PushToken,
    SavedCase,
    Session as PhotoSession,
    SessionStatus,
    User,
)
from app.schemas.me import ApprovalRespondRequest, ConsultCreateRequest, PushTokenDeleteRequest, PushTokenRequest
from app.services.consent import apply_consent
from app.services.logic import query_total
from app.services.serializers import _image_url, serialize_consult, serialize_public_practice, serialize_public_session_card

router = APIRouter(prefix="/me", tags=["consumer"])


# ---------------------------------------------------------------------------
# Saves
# ---------------------------------------------------------------------------

@router.post("/saves/{session_id}")
def save_case(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = db.scalar(
        select(PhotoSession).where(
            PhotoSession.id == session_id,
            PhotoSession.status == SessionStatus.published.value,
            PhotoSession.archived_at.is_(None),
        )
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    existing = db.scalar(
        select(SavedCase).where(
            SavedCase.user_id == current_user.id,
            SavedCase.session_id == session_id,
        )
    )
    if existing:
        return success_response({"session_id": session_id, "saved_at": existing.created_at.isoformat()})

    save = SavedCase(user_id=current_user.id, session_id=session_id)
    db.add(save)
    db.commit()
    db.refresh(save)
    return success_response({"session_id": session_id, "saved_at": save.created_at.isoformat()}, status_code=201)


@router.delete("/saves/{session_id}")
def unsave_case(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing = db.scalar(
        select(SavedCase).where(
            SavedCase.user_id == current_user.id,
            SavedCase.session_id == session_id,
        )
    )
    if existing:
        db.delete(existing)
        db.commit()
    return success_response({"removed": existing is not None})


@router.get("/saves")
def list_saves(
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    base_q = (
        select(SavedCase)
        .join(PhotoSession, PhotoSession.id == SavedCase.session_id)
        .where(
            SavedCase.user_id == current_user.id,
            PhotoSession.status == SessionStatus.published.value,
            PhotoSession.archived_at.is_(None),
        )
        .order_by(SavedCase.created_at.desc())
    )
    total = query_total(db, base_q)
    saves = db.scalars(base_q.limit(limit).offset(offset)).all()

    items = []
    for save in saves:
        photo_session = db.get(PhotoSession, save.session_id)
        practice = db.get(Practice, photo_session.practice_id)
        owner = db.get(User, practice.owner_id) if practice.owner_id else None
        card = serialize_public_session_card(photo_session, practice, owner=owner)
        card["saved_at"] = save.created_at.isoformat()
        items.append(card)

    return success_response({"sessions": items, "total": total})


# ---------------------------------------------------------------------------
# Follows
# ---------------------------------------------------------------------------

@router.post("/follows/{practice_id}")
def follow_practice(
    practice_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    practice = db.get(Practice, practice_id)
    if practice is None:
        raise HTTPException(status_code=404, detail="Practice not found")

    existing = db.scalar(
        select(FollowedPractice).where(
            FollowedPractice.user_id == current_user.id,
            FollowedPractice.practice_id == practice_id,
        )
    )
    if existing:
        return success_response({"practice_id": practice_id, "followed_at": existing.created_at.isoformat()})

    follow = FollowedPractice(user_id=current_user.id, practice_id=practice_id)
    db.add(follow)
    db.commit()
    db.refresh(follow)
    return success_response({"practice_id": practice_id, "followed_at": follow.created_at.isoformat()}, status_code=201)


@router.delete("/follows/{practice_id}")
def unfollow_practice(
    practice_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing = db.scalar(
        select(FollowedPractice).where(
            FollowedPractice.user_id == current_user.id,
            FollowedPractice.practice_id == practice_id,
        )
    )
    if existing:
        db.delete(existing)
        db.commit()
    return success_response({"removed": existing is not None})


@router.get("/follows")
def list_follows(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    follows = db.scalars(
        select(FollowedPractice)
        .where(FollowedPractice.user_id == current_user.id)
        .order_by(FollowedPractice.created_at.desc())
    ).all()

    items = []
    for follow in follows:
        practice = db.get(Practice, follow.practice_id)
        owner = db.get(User, practice.owner_id) if practice.owner_id else None
        published_count = db.scalar(
            select(func.count(PhotoSession.id)).where(
                PhotoSession.practice_id == practice.id,
                PhotoSession.status == SessionStatus.published.value,
                PhotoSession.archived_at.is_(None),
            )
        ) or 0
        card = serialize_public_practice(practice, owner=owner, published_session_count=published_count)
        card["followed_at"] = follow.created_at.isoformat()
        items.append(card)

    return success_response({"practices": items, "total": len(items)})


# ---------------------------------------------------------------------------
# Results — sessions linked to the caller via followup email
# ---------------------------------------------------------------------------

@router.get("/results")
def list_results(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Sessions where any followup's patient_email matches the caller.
    Includes unpublished sessions so members can see their own pending cases.
    """
    followups = db.scalars(
        select(Followup)
        .where(func.lower(Followup.patient_email) == current_user.email.lower())
        .order_by(Followup.created_at.desc())
    ).all()

    seen_session_ids: set[str] = set()
    items = []
    for followup in followups:
        if followup.session_id in seen_session_ids:
            continue
        seen_session_ids.add(followup.session_id)
        photo_session = db.get(PhotoSession, followup.session_id)
        practice = db.get(Practice, photo_session.practice_id)
        owner = db.get(User, practice.owner_id) if practice.owner_id else None
        card = serialize_public_session_card(photo_session, practice, owner=owner)
        card["status"] = photo_session.status
        card["consent_tier"] = photo_session.consent_tier
        items.append(card)

    return success_response({"sessions": items, "total": len(items)})


# ---------------------------------------------------------------------------
# Approvals (in-app consent)
# ---------------------------------------------------------------------------

@router.get("/approvals")
def list_approvals(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    actionable = {FollowupStatus.sent.value, FollowupStatus.opened.value}
    followups = db.scalars(
        select(Followup)
        .where(
            func.lower(Followup.patient_email) == current_user.email.lower(),
            Followup.status.in_(actionable),
        )
        .order_by(Followup.created_at.desc())
    ).all()

    items = []
    for followup in followups:
        photo_session = db.get(PhotoSession, followup.session_id)
        practice = db.get(Practice, followup.practice_id)
        items.append({
            "id": followup.id,
            "requested_at": followup.created_at.isoformat(),
            "practice": {
                "id": practice.id,
                "name": practice.name,
                "location": practice.location,
            },
            "session": {
                "id": photo_session.id,
                "treatment": photo_session.treatment,
                "category": photo_session.category,
                "before_image_url": _image_url(photo_session.before_image_key),
                "after_image_url": _image_url(photo_session.after_image_key),
            },
            "discount_offer": {
                "full": practice.default_discount_full,
                "partial": practice.default_discount_partial,
                "full_blur": practice.default_discount_blur,
            },
        })

    return success_response({"approvals": items})


@router.post("/approvals/{followup_id}/respond")
def respond_to_approval(
    followup_id: str,
    payload: ApprovalRespondRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    followup = db.get(Followup, followup_id)
    if followup is None:
        raise HTTPException(status_code=404, detail="Approval not found")

    if followup.patient_email.lower() != current_user.email.lower():
        raise HTTPException(status_code=403, detail="This approval does not belong to you")

    if followup.status == FollowupStatus.completed.value:
        raise HTTPException(status_code=409, detail="This approval has already been completed")

    if followup.status in {FollowupStatus.expired.value, FollowupStatus.cancelled.value}:
        raise HTTPException(status_code=409, detail="This approval is no longer active")

    if payload.decision != ConsentTier.decline and not payload.signature_svg:
        raise HTTPException(status_code=422, detail="Signature is required unless declining")

    photo_session = db.get(PhotoSession, followup.session_id)
    if not photo_session.after_image_key:
        raise HTTPException(status_code=400, detail="After photo must be uploaded before consent")

    practice = db.get(Practice, followup.practice_id)

    result = apply_consent(
        db,
        followup=followup,
        practice=practice,
        session=photo_session,
        consent_tier=payload.decision.value,
        signature_svg=payload.signature_svg,
        patient_email=current_user.email,
    )

    return success_response({
        "consent_tier": result.consent_tier,
        "reward_earned": result.reward,
    })


# ---------------------------------------------------------------------------
# Consult requests (member side)
# ---------------------------------------------------------------------------

@router.post("/consults")
def create_consult(
    payload: ConsultCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from fastapi import HTTPException
    practice = db.get(Practice, payload.practice_id)
    if practice is None:
        raise HTTPException(status_code=404, detail="Practice not found")

    existing = db.scalar(
        select(ConsultRequest).where(
            ConsultRequest.user_id == current_user.id,
            ConsultRequest.practice_id == payload.practice_id,
            ConsultRequest.status == "new",
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="You already have an open request with this clinic.")

    consult = ConsultRequest(
        practice_id=payload.practice_id,
        user_id=current_user.id,
        session_id=payload.session_id,
        message=payload.message,
        contact_email=payload.contact_email,
        contact_phone=payload.contact_phone,
        status="new",
    )
    db.add(consult)
    db.commit()
    db.refresh(consult)
    return success_response(serialize_consult(consult, db), status_code=201)


@router.get("/consults")
def list_my_consults(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    consults = db.scalars(
        select(ConsultRequest)
        .where(ConsultRequest.user_id == current_user.id)
        .order_by(ConsultRequest.created_at.desc())
    ).all()
    return success_response({"consults": [serialize_consult(c, db) for c in consults]})


# ---------------------------------------------------------------------------
# Push tokens
# ---------------------------------------------------------------------------

@router.post("/push-token")
def upsert_push_token(
    payload: PushTokenRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing = db.scalar(select(PushToken).where(PushToken.token == payload.token))
    if existing:
        existing.user_id = current_user.id
        existing.platform = payload.platform
        db.add(existing)
    else:
        db.add(PushToken(user_id=current_user.id, token=payload.token, platform=payload.platform))
    db.commit()
    return success_response({"stored": True})


@router.delete("/push-token")
def delete_push_token(
    payload: PushTokenDeleteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing = db.scalar(select(PushToken).where(PushToken.token == payload.token))
    if existing:
        db.delete(existing)
        db.commit()
    return success_response({"removed": existing is not None})


# ---------------------------------------------------------------------------
# Activity feed (Inbox)
# ---------------------------------------------------------------------------

def _naive(dt):
    """Strip tz for cross-DB datetime comparison (SQLite=naive, PostgreSQL=tz-aware)."""
    if dt is None:
        return None
    return dt.replace(tzinfo=None) if dt.tzinfo else dt


@router.get("/activity")
def list_activity(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    email_lower = current_user.email.lower()
    now_naive = _naive(utcnow())
    expiry_window = now_naive + timedelta(days=21)

    followups = db.scalars(
        select(Followup).where(func.lower(Followup.patient_email) == email_lower)
    ).all()

    credits = db.scalars(
        select(Credit).where(func.lower(Credit.patient_email) == email_lower)
    ).all()

    consult_rows = db.scalars(
        select(ConsultRequest).where(ConsultRequest.user_id == current_user.id)
    ).all()

    # Cache practice lookups within this request
    _practice_cache: dict[str, Practice] = {}

    def _practice(pid: str) -> Practice | None:
        if pid not in _practice_cache:
            _practice_cache[pid] = db.get(Practice, pid)
        return _practice_cache[pid]

    events: list[dict] = []
    published_session_ids: set[str] = set()  # deduplicate case_published

    for followup in followups:
        if followup.status != FollowupStatus.completed.value:
            continue

        photo_session = db.get(PhotoSession, followup.session_id)
        practice = _practice(followup.practice_id)
        if not photo_session or not practice:
            continue

        # approval_completed
        ts = photo_session.consent_at or followup.updated_at
        events.append({
            "id": f"approval_completed-{followup.id}",
            "kind": "approval_completed",
            "text": (
                f"You approved {practice.name}'s request to publish "
                f"your {photo_session.treatment}."
            ),
            "timestamp": ts,
            "session_id": followup.session_id,
        })

        # case_published — one event per session even if multiple followups
        if (
            photo_session.status == SessionStatus.published.value
            and photo_session.published_at
            and followup.session_id not in published_session_ids
        ):
            published_session_ids.add(followup.session_id)
            events.append({
                "id": f"case_published-{followup.session_id}",
                "kind": "case_published",
                "text": (
                    f"{practice.name} published your {photo_session.treatment} "
                    f"before & after."
                ),
                "timestamp": photo_session.published_at,
                "session_id": followup.session_id,
            })

    for credit in credits:
        practice = _practice(credit.practice_id)
        if not practice:
            continue

        # credit_earned
        events.append({
            "id": f"credit_earned-{credit.id}",
            "kind": "credit_earned",
            "text": f"You earned a ${credit.amount} reward at {practice.name}.",
            "timestamp": credit.earned_at,
            "session_id": credit.session_id,
        })

        # credit_expiring — active credits expiring within 21 days
        if credit.status == CreditStatus.active.value and _naive(credit.expires_at) <= expiry_window:
            events.append({
                "id": f"credit_expiring-{credit.id}",
                "kind": "credit_expiring",
                "text": f"Your ${credit.amount} reward at {practice.name} expires soon.",
                "timestamp": credit.expires_at,
                "session_id": credit.session_id,
            })

    for consult in consult_rows:
        practice = _practice(consult.practice_id)
        if not practice:
            continue
        events.append({
            "id": f"consult_request-{consult.id}",
            "kind": "consult_request",
            "text": f"You requested a consult with {practice.name}.",
            "timestamp": consult.created_at,
            "session_id": consult.session_id,
        })

    events.sort(key=lambda e: _naive(e["timestamp"]) or now_naive, reverse=True)
    total = len(events)
    items = events[:50]

    for item in items:
        item["timestamp"] = item["timestamp"].isoformat()

    return success_response({"items": items, "total": total})
