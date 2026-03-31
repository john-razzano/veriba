from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_practice
from app.core.config import get_settings
from app.core.responses import success_response
from app.core.security import create_upload_token, utcnow
from app.db.session import get_db
from app.models import Followup, FollowupStatus, Practice, Session as PhotoSession
from app.schemas.followup import FollowupCreateRequest
from app.services.email import followup_email_subject, render_followup_email, send_email
from app.services.logic import ensure_followup_belongs_to_session, ensure_session_belongs_to_practice, followup_send_at
from app.services.serializers import serialize_followup

router = APIRouter(prefix="/sessions", tags=["followups"])


def _followup_upload_url(token: str) -> str:
    settings = get_settings()
    return f"{settings.patient_portal_base_url.rstrip('/')}/{token}"


def _send_followup_email(followup: Followup, practice: Practice, session: PhotoSession) -> None:
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


@router.post("/{session_id}/followup")
def create_followup(
    session_id: str,
    payload: FollowupCreateRequest,
    practice: Practice = Depends(get_current_practice),
    db: Session = Depends(get_db),
):
    session = ensure_session_belongs_to_practice(db, session_id, practice.id)
    scheduled_for = followup_send_at(session, payload.send_at)
    followup = Followup(
        session_id=session.id,
        practice_id=practice.id,
        patient_email=payload.patient_email.lower(),
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
        _send_followup_email(followup, practice, session)
    db.commit()
    db.refresh(followup)
    return success_response(serialize_followup(followup), status_code=201)


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
    return success_response({"followups": [serialize_followup(item) for item in followups]})


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
    _send_followup_email(followup, practice, session)
    db.add(followup)
    db.commit()
    db.refresh(followup)
    return success_response(serialize_followup(followup))


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

