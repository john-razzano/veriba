from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

import logging

from app.api.deps import get_current_practice
from app.core.config import get_settings
from app.core.responses import success_response
from app.core.security import create_upload_token, utcnow
from app.db.session import get_db
from app.models import Followup, FollowupStatus, Practice, Role, Session as PhotoSession, User

logger = logging.getLogger(__name__)
from app.schemas.followup import FollowupCreateRequest
from app.services.email import followup_email_subject, render_followup_email, send_email
from app.services.logic import ensure_followup_belongs_to_session, ensure_session_belongs_to_practice, followup_send_at
from app.services.serializers import serialize_followup

router = APIRouter(prefix="/sessions", tags=["followups"])


def _followup_upload_url(token: str) -> str:
    settings = get_settings()
    return f"{settings.patient_portal_base_url.rstrip('/')}/{token}"


def _send_followup_email(followup: Followup, practice: Practice, session: PhotoSession, db=None) -> None:
    html = render_followup_email(
        practice_name=practice.name,
        patient_first_name=followup.patient_first_name,
        upload_url=_followup_upload_url(followup.upload_token),
        message=followup.custom_message,
        reward_amount=practice.default_discount_full,
    )
    send_email(
        to_email=followup.patient_email,
        subject=followup_email_subject(practice.name),
        html=html,
    )
    followup.status = FollowupStatus.sent.value
    followup.sent_at = utcnow()

    # Push notification at send-time — log-and-continue on any failure
    try:
        if db is not None:
            from app.services.push import send_followup_push
            send_followup_push(followup, session, practice.name, db)
    except Exception:
        logger.exception("Push notification failed for followup %s", followup.id)


@router.post("/{session_id}/followup")
def create_followup(
    session_id: str,
    payload: FollowupCreateRequest,
    practice: Practice = Depends(get_current_practice),
    db: Session = Depends(get_db),
):
    from fastapi import HTTPException as _HTTPException
    session = ensure_session_belongs_to_practice(db, session_id, practice.id)

    # Validate patient_user_id when provided; resolve email server-side if omitted
    patient_user_id = None
    linked_user = None
    if payload.patient_user_id:
        linked_user = db.get(User, payload.patient_user_id)
        if linked_user is None or linked_user.role != Role.member.value:
            raise _HTTPException(status_code=422, detail="patient_user_id must refer to an existing member account")
        patient_user_id = payload.patient_user_id

    if payload.patient_email:
        patient_email = payload.patient_email.lower()
    else:
        # QR-linked path: no explicit email — use the linked user's own account email
        # for internal DB record / future email flows; never reflected back in response
        patient_email = linked_user.email  # guaranteed non-None (validator above ensures user_id present)

    scheduled_for = followup_send_at(session, payload.send_at)
    followup = Followup(
        session_id=session.id,
        practice_id=practice.id,
        patient_email=patient_email,
        patient_user_id=patient_user_id,
        patient_first_name=payload.patient_first_name,
        upload_token=create_upload_token(),
        token_expires_at=utcnow() + timedelta(days=30),
        custom_message=payload.message,
        status=FollowupStatus.scheduled.value,
        send_at=scheduled_for,
    )
    db.add(followup)
    db.flush()
    if scheduled_for <= utcnow():
        _send_followup_email(followup, practice, session, db=db)
    db.commit()
    db.refresh(followup)
    return success_response(serialize_followup(followup, db=db), status_code=201)


@router.get("/{session_id}/followups")
def list_followups(
    session_id: str,
    practice: Practice = Depends(get_current_practice),
    db: Session = Depends(get_db),
):
    ensure_session_belongs_to_practice(db, session_id, practice.id)
    followups = db.scalars(
        select(Followup)
        .where(
            Followup.session_id == session_id,
            Followup.practice_id == practice.id,
        )
        .order_by(Followup.created_at.desc())
    ).all()
    return success_response({"followups": [serialize_followup(item, db=db) for item in followups]})


@router.post("/{session_id}/followup/{followup_id}/resend")
def resend_followup(
    session_id: str,
    followup_id: str,
    practice: Practice = Depends(get_current_practice),
    db: Session = Depends(get_db),
):
    session = ensure_session_belongs_to_practice(db, session_id, practice.id)
    followup = ensure_followup_belongs_to_session(
        db,
        session_id=session_id,
        practice_id=practice.id,
        followup_id=followup_id,
    )
    followup.upload_token = create_upload_token()
    followup.token_expires_at = utcnow() + timedelta(days=30)
    followup.send_at = utcnow()
    followup.sent_at = None
    followup.opened_at = None
    followup.upload_completed_at = None
    followup.status = FollowupStatus.scheduled.value
    _send_followup_email(followup, practice, session, db=db)
    db.add(followup)
    db.commit()
    db.refresh(followup)
    return success_response(serialize_followup(followup, db=db))


@router.delete("/{session_id}/followup/{followup_id}")
def cancel_followup(
    session_id: str,
    followup_id: str,
    practice: Practice = Depends(get_current_practice),
    db: Session = Depends(get_db),
):
    ensure_session_belongs_to_practice(db, session_id, practice.id)
    followup = ensure_followup_belongs_to_session(
        db,
        session_id=session_id,
        practice_id=practice.id,
        followup_id=followup_id,
    )
    if followup.sent_at is not None:
        raise HTTPException(status_code=400, detail="Only scheduled follow-ups can be cancelled")
    followup.status = FollowupStatus.cancelled.value
    db.add(followup)
    db.commit()
    return success_response({"cancelled": True})

