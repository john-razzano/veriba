from datetime import timedelta

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.core.responses import success_response
from app.core.security import utcnow
from app.db.session import SessionLocal
from app.models import Credit, ConsentTier, Followup, FollowupStatus, Practice, Session as PhotoSession, SessionStatus
from app.schemas.patient import PatientConsentRequest
from app.services.consent import apply_consent
from app.services.images import compress_for_web, image_hash, read_upload_bytes
from app.services.logic import (
    create_credit,
    expire_followup_if_needed,
    publish_if_needed,
)
from app.services.serializers import serialize_patient_context
from app.services.storage import get_storage

router = APIRouter(prefix="/patient/upload", tags=["patient"])
patient_limit = get_settings().patient_rate_limit


def _resolve_followup(db: Session, token: str) -> tuple[Followup | None, Practice | None, PhotoSession | None]:
    followup = db.scalar(select(Followup).where(Followup.upload_token == token))
    if followup is None:
        return None, None, None

    expire_followup_if_needed(followup)
    session = db.scalar(select(PhotoSession).where(PhotoSession.id == followup.session_id))
    practice = db.scalar(select(Practice).where(Practice.id == followup.practice_id))
    return followup, practice, session


def _invalid_token_response():
    return success_response(
        {
            "valid": False,
            "error": "This link has expired. Please contact your provider for a new one.",
        }
    )


@router.get("/{token}")
@limiter.limit(patient_limit)
def validate_token(request: Request, token: str):
    with SessionLocal() as db:
        followup, practice, session = _resolve_followup(db, token)
        if (
            followup is None
            or practice is None
            or session is None
            or followup.status in {FollowupStatus.expired.value, FollowupStatus.cancelled.value}
        ):
            return _invalid_token_response()

        if followup.opened_at is None:
            followup.opened_at = utcnow()
            if followup.status == FollowupStatus.sent.value:
                followup.status = FollowupStatus.opened.value
            db.add(followup)
            db.commit()
            db.refresh(followup)

        return success_response(serialize_patient_context(practice, session, followup))


@router.post("/{token}/photo")
@limiter.limit(patient_limit)
async def upload_patient_photo(request: Request, token: str, file: UploadFile = File(...)):
    with SessionLocal() as db:
        followup, practice, session = _resolve_followup(db, token)
        if (
            followup is None
            or practice is None
            or session is None
            or followup.status in {FollowupStatus.expired.value, FollowupStatus.cancelled.value, FollowupStatus.completed.value}
        ):
            raise HTTPException(status_code=404, detail="Upload link is invalid or expired")

        original = await read_upload_bytes(file)
        compressed, width, height = compress_for_web(original)
        server_hash = image_hash(original)
        storage = get_storage()
        prefix = f"{session.practice_id}/sessions/{session.id}/after"
        ext = file.filename.split(".")[-1] if file.filename and "." in file.filename else "jpg"
        original_key = f"{prefix}/original.{ext.lower()}"
        web_key = f"{prefix}/web.jpg"
        storage.save_bytes(original_key, original)
        storage.save_bytes(web_key, compressed)

        session.after_original_image_key = original_key
        session.after_image_key = web_key
        session.after_image_width = width
        session.after_image_height = height
        session.after_capture_hash = server_hash
        session.after_captured_at = utcnow()
        session.after_provenance = "Uploaded by patient via email link"
        session.status = SessionStatus.pending_consent.value

        followup.upload_completed_at = utcnow()
        if session.consent_tier and session.consent_tier != ConsentTier.decline.value:
            create_credit(
                db,
                practice=practice,
                session=session,
                patient_email=followup.patient_email,
                consent_tier=session.consent_tier,
                followup=followup,
            )
            publish_if_needed(db, session, practice)
            followup.status = FollowupStatus.completed.value
        else:
            followup.status = FollowupStatus.opened.value

        db.add_all([session, followup])
        db.commit()
        return success_response(
            {
                "success": True,
                "message": "Photo uploaded successfully! Please select your sharing preference below to claim your reward.",
            }
        )


@router.post("/{token}/consent")
@limiter.limit(patient_limit)
def submit_patient_consent(request: Request, token: str, payload: PatientConsentRequest):
    with SessionLocal() as db:
        followup, practice, session = _resolve_followup(db, token)
        if (
            followup is None
            or practice is None
            or session is None
            or followup.status in {FollowupStatus.expired.value, FollowupStatus.cancelled.value, FollowupStatus.completed.value}
        ):
            raise HTTPException(status_code=404, detail="Upload link is invalid or expired")

        if not session.after_image_key:
            raise HTTPException(status_code=400, detail="After photo must be uploaded before consent")

        result = apply_consent(
            db,
            followup=followup,
            practice=practice,
            session=session,
            consent_tier=payload.consent_tier.value,
            signature_svg=payload.signature_data,
            patient_email=followup.patient_email,
            request_ip=request.headers.get("x-forwarded-for", request.client.host if request.client else None),
            request_ua=request.headers.get("user-agent"),
            consent_form_version=payload.consent_form_version,
        )
        return success_response(
            {
                "success": True,
                "consent_tier": result.consent_tier,
                "reward_earned": result.reward,
                "message": (
                    f"Thank you! Your reward code is {result.reward['code']}."
                    if result.reward
                    else "Your sharing preference has been saved."
                ),
            }
        )


@router.get("/{token}/status")
@limiter.limit(patient_limit)
def patient_status(request: Request, token: str):
    with SessionLocal() as db:
        followup, _, session = _resolve_followup(db, token)
        if followup is None or session is None:
            raise HTTPException(status_code=404, detail="Upload link is invalid or expired")

        existing_credit = db.scalar(select(Credit).where(Credit.session_id == session.id))
        return success_response(
            {
                "photo_uploaded": bool(session.after_image_key),
                "consent_given": bool(session.consent_tier),
                "reward_earned": existing_credit is not None,
                "reward_code": existing_credit.code if existing_credit else None,
                "session_status": session.status,
            }
        )
