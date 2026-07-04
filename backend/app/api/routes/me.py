from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.responses import success_response
from app.db.session import get_db
from app.models import (
    ConsentTier,
    Followup,
    FollowedPractice,
    FollowupStatus,
    Practice,
    SavedCase,
    Session as PhotoSession,
    SessionStatus,
    User,
)
from app.schemas.me import ApprovalRespondRequest
from app.services.consent import apply_consent
from app.services.logic import query_total
from app.services.serializers import _image_url, serialize_public_practice, serialize_public_session_card

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
