import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_practice
from app.core.responses import success_response
from app.core.security import utcnow
from app.db.session import get_db
from app.models import Practice, Session as PhotoSession, SessionStatus
from app.schemas.practice import PracticeUpdateRequest
from app.services.images import compress_for_web, read_upload_bytes
from app.services.serializers import serialize_practice
from app.services.storage import get_storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/practices", tags=["practices"])


@router.get("/me")
def get_practice(practice: Practice = Depends(get_current_practice)):
    return success_response(serialize_practice(practice))


@router.patch("/me")
def update_practice(
    payload: PracticeUpdateRequest,
    practice: Practice = Depends(get_current_practice),
    db: Session = Depends(get_db),
):
    if payload.name is not None and payload.name != practice.name:
        logger.info("Practice %s renamed: %r → %r", practice.id, practice.name, payload.name)
        practice.name = payload.name
    if payload.location is not None and payload.location != practice.location:
        logger.info("Practice %s location changed: %r → %r", practice.id, practice.location, payload.location)
        practice.location = payload.location

    for field in ("website", "lat", "lng", "credit_expiration_days", "auto_publish"):
        value = getattr(payload, field)
        if value is not None:
            setattr(practice, field, value)

    if payload.default_discounts:
        if payload.default_discounts.full is not None:
            practice.default_discount_full = payload.default_discounts.full
        if payload.default_discounts.partial is not None:
            practice.default_discount_partial = payload.default_discounts.partial
        if payload.default_discounts.full_blur is not None:
            practice.default_discount_blur = payload.default_discounts.full_blur

    # bio and booking_url are explicitly nullable — only update when provided
    if "bio" in payload.model_fields_set:
        practice.bio = payload.bio or None
    if "booking_url" in payload.model_fields_set:
        practice.booking_url = payload.booking_url

    db.add(practice)
    db.commit()
    db.refresh(practice)
    return success_response(serialize_practice(practice))


@router.post("/me/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    practice: Practice = Depends(get_current_practice),
    db: Session = Depends(get_db),
):
    data = await read_upload_bytes(file)
    compressed, _, _ = compress_for_web(data)
    key = f"{practice.id}/profile/avatar.jpg"
    avatar_url = get_storage().save_bytes(key, compressed, content_type="image/jpeg")
    practice.avatar_key = key
    db.add(practice)
    db.commit()
    return success_response({"avatar_url": avatar_url})


@router.delete("/me/avatar")
def delete_avatar(
    practice: Practice = Depends(get_current_practice),
    db: Session = Depends(get_db),
):
    if practice.avatar_key:
        get_storage().delete_prefix(practice.avatar_key)
        practice.avatar_key = None
        db.add(practice)
        db.commit()
    return success_response({"removed": practice.avatar_key is None})


@router.get("/me/stats")
def practice_stats(
    practice: Practice = Depends(get_current_practice),
    db: Session = Depends(get_db),
):
    week_ago = utcnow() - timedelta(days=7)
    sessions = select(PhotoSession).where(
        PhotoSession.practice_id == practice.id,
        PhotoSession.archived_at.is_(None),
    )
    published = db.scalar(
        select(func.count()).select_from(PhotoSession).where(
            PhotoSession.practice_id == practice.id,
            PhotoSession.status == SessionStatus.published.value,
            PhotoSession.archived_at.is_(None),
        )
    ) or 0
    pending = db.scalar(
        select(func.count()).select_from(PhotoSession).where(
            PhotoSession.practice_id == practice.id,
            PhotoSession.status.in_(
                [
                    SessionStatus.pending_after.value,
                    SessionStatus.pending_consent.value,
                    SessionStatus.ready_to_publish.value,
                ]
            ),
            PhotoSession.archived_at.is_(None),
        )
    ) or 0
    declined = db.scalar(
        select(func.count()).select_from(PhotoSession).where(
            PhotoSession.practice_id == practice.id,
            PhotoSession.status == SessionStatus.declined.value,
            PhotoSession.archived_at.is_(None),
        )
    ) or 0
    profile_views_total = db.scalar(
        select(func.coalesce(func.sum(PhotoSession.page_views), 0)).where(
            PhotoSession.practice_id == practice.id,
            PhotoSession.archived_at.is_(None),
        )
    ) or 0
    profile_views_this_week = db.scalar(
        select(func.coalesce(func.sum(PhotoSession.page_views), 0)).where(
            PhotoSession.practice_id == practice.id,
            PhotoSession.updated_at >= week_ago,
            PhotoSession.archived_at.is_(None),
        )
    ) or 0

    return success_response(
        {
            "total_published": published,
            "total_pending": pending,
            "total_declined": declined,
            "profile_views_total": profile_views_total,
            "profile_views_this_week": profile_views_this_week,
            "seo_impressions_total": 0,
            "seo_impressions_this_week": 0,
        }
    )
