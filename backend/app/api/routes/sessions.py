from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import asc, desc, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_practice
from app.core.responses import success_response
from app.core.security import utcnow
from app.db.session import get_db
from app.models import (
    ConsentTier,
    ObscureMode,
    Practice,
    Session as PhotoSession,
    SessionStatus,
)
from app.schemas.session import ConsentRequest, PublishRequest, SessionCreateRequest, SessionUpdateRequest
from app.services.images import compress_for_web, image_hash, read_upload_bytes, render_signature_png
from app.services.logic import (
    build_publish_hash,
    ensure_session_belongs_to_practice,
    is_publishable,
    next_status_after_consent,
    obscure_mode_for_consent,
    practice_default_discount,
    query_total,
    update_status_after_image_upload,
)
from app.services.seo import generate_seo
from app.services.serializers import serialize_seo, serialize_session_detail, serialize_session_summary
from app.services.storage import get_storage

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _apply_seo(db: Session, session: PhotoSession, practice: Practice) -> dict:
    seo = generate_seo(db, session=session, practice=practice)
    session.seo_title = seo["title"]
    session.seo_alt_text = seo["alt_text"]
    session.seo_meta_description = seo["meta_description"]
    session.seo_filename = seo["filename"]
    session.seo_url_slug = seo["url_slug"]
    session.seo_template_variant = seo["template_variant"]
    return seo


def _publish_session(
    db: Session,
    session: PhotoSession,
    practice: Practice,
    destinations: list[str],
) -> dict:
    if not is_publishable(session):
        raise HTTPException(status_code=400, detail="Session is not ready to publish")

    session.published_at = utcnow()
    session.status = SessionStatus.published.value
    session.published_destinations = destinations
    seo = _apply_seo(db, session, practice)
    session.publish_hash = build_publish_hash(session, session.published_at)
    return seo


def _image_paths(session: PhotoSession, image_kind: str, filename: str | None) -> tuple[str, str]:
    extension = Path(filename or "").suffix.lower() or ".jpg"
    prefix = f"{session.practice_id}/sessions/{session.id}/{image_kind}"
    return (
        f"{prefix}/original{extension}",
        f"{prefix}/web.jpg",
    )


@router.get("")
def list_sessions(
    status: str | None = Query(default=None),
    category: str | None = Query(default=None),
    sort: str = Query(default="created_at", pattern="^(created_at|updated_at|page_views)$"),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    practice: Practice = Depends(get_current_practice),
    db: Session = Depends(get_db),
):
    query = select(PhotoSession).where(
        PhotoSession.practice_id == practice.id,
        PhotoSession.archived_at.is_(None),
    )
    if status:
        query = query.where(PhotoSession.status == status)
    if category:
        query = query.where(PhotoSession.category == category)

    total = query_total(db, query)
    sort_column = getattr(PhotoSession, sort)
    ordering = asc(sort_column) if order == "asc" else desc(sort_column)
    sessions = db.scalars(query.order_by(ordering).offset(offset).limit(limit)).all()

    return success_response(
        {
            "sessions": [serialize_session_summary(session) for session in sessions],
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    )


@router.post("")
def create_session(
    payload: SessionCreateRequest,
    practice: Practice = Depends(get_current_practice),
    db: Session = Depends(get_db),
):
    if payload.status.value not in {
        SessionStatus.draft.value,
        SessionStatus.pending_after.value,
    }:
        raise HTTPException(status_code=400, detail="Sessions must start as draft or pending_after")

    session = PhotoSession(
        practice_id=practice.id,
        patient_initials=payload.patient_initials,
        treatment=payload.treatment,
        category=payload.category.value,
        status=payload.status.value,
        obscure_mode=ObscureMode.none.value,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return success_response(serialize_session_detail(session), status_code=201)


@router.post("/{session_id}/images/{image_kind}")
async def upload_image(
    session_id: str,
    image_kind: str,
    file: UploadFile = File(...),
    capture_hash: str | None = Form(default=None),
    capture_lat: float | None = Form(default=None),
    capture_lng: float | None = Form(default=None),
    captured_at: datetime | None = Form(default=None),
    practice: Practice = Depends(get_current_practice),
    db: Session = Depends(get_db),
):
    if image_kind not in {"before", "after"}:
        raise HTTPException(status_code=404, detail="Unknown image slot")

    session = ensure_session_belongs_to_practice(db, session_id, practice.id)
    original = await read_upload_bytes(file)
    server_hash = image_hash(original)
    compressed, width, height = compress_for_web(original)
    storage = get_storage()
    original_key, web_key = _image_paths(session, image_kind, file.filename)
    storage.save_bytes(original_key, original)
    storage.save_bytes(web_key, compressed)
    hash_match = capture_hash is None or capture_hash == server_hash

    parsed_captured_at = captured_at
    if image_kind == "before":
        session.before_original_image_key = original_key
        session.before_image_key = web_key
        session.before_image_width = width
        session.before_image_height = height
        session.capture_hash = capture_hash or server_hash
        session.capture_lat = capture_lat
        session.capture_lng = capture_lng
        session.captured_at = parsed_captured_at or session.captured_at or utcnow()
        session.sign_hash = server_hash
        session.signed_at = utcnow()
    else:
        session.after_original_image_key = original_key
        session.after_image_key = web_key
        session.after_image_width = width
        session.after_image_height = height
        session.after_capture_hash = server_hash
        session.after_captured_at = parsed_captured_at or session.after_captured_at or utcnow()
        session.after_provenance = "Uploaded in-app by provider"

    session.status = update_status_after_image_upload(session)
    if session.after_image_key and session.consent_tier and session.consent_tier != ConsentTier.decline.value:
        if practice.auto_publish:
            _publish_session(db, session, practice, session.published_destinations or ["widget", "gallery"])
        else:
            session.status = next_status_after_consent(practice)

    db.add(session)
    db.commit()
    db.refresh(session)

    return success_response(
        {
            "image_url": get_storage().public_url(web_key),
            "capture_hash": capture_hash or server_hash,
            "capture_coordinates": (
                {"lat": capture_lat, "lng": capture_lng}
                if capture_lat is not None and capture_lng is not None
                else None
            ),
            "captured_at": parsed_captured_at or session.captured_at,
            "server_hash": server_hash,
            "hash_match": hash_match,
            "chain_of_custody_updated": True,
        }
    )


@router.get("/{session_id}/images/{image_kind}")
def get_image(
    session_id: str,
    image_kind: str,
    size: str = Query(default="medium", pattern="^(thumb|medium|full)$"),
    practice: Practice = Depends(get_current_practice),
    db: Session = Depends(get_db),
):
    session = ensure_session_belongs_to_practice(db, session_id, practice.id)
    if image_kind == "before":
        key = session.before_original_image_key if size == "full" and session.before_original_image_key else session.before_image_key
        width = session.before_image_width
        height = session.before_image_height
    elif image_kind == "after":
        key = session.after_original_image_key if size == "full" and session.after_original_image_key else session.after_image_key
        width = session.after_image_width
        height = session.after_image_height
    else:
        raise HTTPException(status_code=404, detail="Unknown image slot")

    if not key:
        raise HTTPException(status_code=404, detail="Image not found")

    return success_response({"url": get_storage().public_url(key), "size": size, "width": width, "height": height})


@router.post("/{session_id}/images/{image_kind}/presign")
def presign_image_upload(
    session_id: str,
    image_kind: str,
    practice: Practice = Depends(get_current_practice),
    db: Session = Depends(get_db),
):
    if image_kind not in {"before", "after"}:
        raise HTTPException(status_code=404, detail="Unknown image slot")
    session = ensure_session_belongs_to_practice(db, session_id, practice.id)
    _, web_key = _image_paths(session, image_kind, f"{image_kind}.jpg")
    presigned = get_storage().presign_upload(web_key, expires_in=3600)
    return success_response(
        {
            "upload_url": presigned.upload_url,
            "expires_in": presigned.expires_in,
            "fields": presigned.fields,
        }
    )


@router.post("/{session_id}/consent")
def record_consent(
    session_id: str,
    payload: ConsentRequest,
    practice: Practice = Depends(get_current_practice),
    db: Session = Depends(get_db),
):
    session = ensure_session_belongs_to_practice(db, session_id, practice.id)

    if payload.consent_tier.value != ConsentTier.decline.value and not (
        session.before_image_key and session.after_image_key
    ):
        raise HTTPException(status_code=400, detail="Both before and after images are required")

    session.consent_tier = payload.consent_tier.value
    session.obscure_mode = (
        payload.obscure_mode.value
        if payload.obscure_mode
        else obscure_mode_for_consent(payload.consent_tier.value)
    )
    session.discount_applied = (
        0
        if payload.consent_tier.value == ConsentTier.decline.value
        else payload.discount_applied or practice_default_discount(practice, payload.consent_tier.value)
    )
    session.consent_at = utcnow()

    if payload.signature_svg and payload.consent_tier.value != ConsentTier.decline.value:
        signature_key = f"{practice.id}/sessions/{session.id}/consent/signature.png"
        get_storage().save_bytes(signature_key, render_signature_png(payload.signature_svg))
        session.consent_signature_key = signature_key

    if payload.consent_tier.value == ConsentTier.decline.value:
        session.status = SessionStatus.declined.value
    elif practice.auto_publish:
        _publish_session(db, session, practice, session.published_destinations or ["widget", "gallery"])
    else:
        session.status = next_status_after_consent(practice)

    db.add(session)
    db.commit()
    db.refresh(session)
    return success_response(
        {
            "consent_tier": session.consent_tier,
            "obscure_mode": session.obscure_mode,
            "consent_at": session.consent_at,
            "discount_applied": session.discount_applied,
            "signature_url": (
                get_storage().public_url(session.consent_signature_key)
                if session.consent_signature_key
                else None
            ),
            "chain_of_custody_updated": True,
            "session_status": session.status,
        }
    )


@router.post("/{session_id}/consent/decline")
def decline_consent(
    session_id: str,
    practice: Practice = Depends(get_current_practice),
    db: Session = Depends(get_db),
):
    session = ensure_session_belongs_to_practice(db, session_id, practice.id)
    session.consent_tier = ConsentTier.decline.value
    session.obscure_mode = ObscureMode.full.value
    session.discount_applied = 0
    session.consent_at = utcnow()
    session.status = SessionStatus.declined.value
    db.add(session)
    db.commit()
    db.refresh(session)
    return success_response(serialize_session_detail(session))


@router.post("/{session_id}/publish")
def publish_session(
    session_id: str,
    payload: PublishRequest,
    practice: Practice = Depends(get_current_practice),
    db: Session = Depends(get_db),
):
    session = ensure_session_belongs_to_practice(db, session_id, practice.id)
    if payload.treatment_details is not None:
        session.treatment_details = payload.treatment_details
    seo = _publish_session(db, session, practice, payload.destinations)
    db.add(session)
    db.commit()
    db.refresh(session)
    return success_response(
        {
            "status": session.status,
            "published_at": session.published_at,
            "publish_hash": session.publish_hash,
            "seo": serialize_seo(session),
            "destinations": session.published_destinations,
            "chain_of_custody_updated": True,
        }
    )


@router.post("/{session_id}/unpublish")
def unpublish_session(
    session_id: str,
    practice: Practice = Depends(get_current_practice),
    db: Session = Depends(get_db),
):
    session = ensure_session_belongs_to_practice(db, session_id, practice.id)
    if session.status != SessionStatus.published.value:
        raise HTTPException(status_code=400, detail="Only published sessions can be unpublished")
    session.status = SessionStatus.unpublished.value
    db.add(session)
    db.commit()
    db.refresh(session)
    return success_response(serialize_session_detail(session))


@router.get("/{session_id}/seo")
def get_session_seo(
    session_id: str,
    practice: Practice = Depends(get_current_practice),
    db: Session = Depends(get_db),
):
    session = ensure_session_belongs_to_practice(db, session_id, practice.id)
    return success_response(serialize_seo(session))


@router.post("/{session_id}/seo/regenerate")
def regenerate_session_seo(
    session_id: str,
    practice: Practice = Depends(get_current_practice),
    db: Session = Depends(get_db),
):
    session = ensure_session_belongs_to_practice(db, session_id, practice.id)
    _apply_seo(db, session, practice)
    if session.published_at:
        session.publish_hash = build_publish_hash(session, session.published_at)
    db.add(session)
    db.commit()
    db.refresh(session)
    return success_response(serialize_seo(session))


@router.get("/{session_id}")
def get_session(
    session_id: str,
    practice: Practice = Depends(get_current_practice),
    db: Session = Depends(get_db),
):
    session = ensure_session_belongs_to_practice(db, session_id, practice.id)
    return success_response(serialize_session_detail(session))


@router.patch("/{session_id}")
def update_session(
    session_id: str,
    payload: SessionUpdateRequest,
    practice: Practice = Depends(get_current_practice),
    db: Session = Depends(get_db),
):
    session = ensure_session_belongs_to_practice(db, session_id, practice.id)
    seo_sensitive = False
    for field in ("patient_initials", "treatment", "treatment_details"):
        value = getattr(payload, field)
        if value is not None:
            setattr(session, field, value)
            seo_sensitive = True

    if payload.category is not None:
        session.category = payload.category.value
    if payload.obscure_mode is not None:
        session.obscure_mode = payload.obscure_mode.value
        seo_sensitive = True

    if session.status == SessionStatus.published.value and seo_sensitive:
        _apply_seo(db, session, practice)
        if session.published_at:
            session.publish_hash = build_publish_hash(session, session.published_at)

    db.add(session)
    db.commit()
    db.refresh(session)
    return success_response(serialize_session_detail(session))


@router.delete("/{session_id}")
def delete_session(
    session_id: str,
    practice: Practice = Depends(get_current_practice),
    db: Session = Depends(get_db),
):
    session = ensure_session_belongs_to_practice(db, session_id, practice.id)
    session.archived_at = utcnow()
    db.add(session)
    db.commit()
    return success_response({"archived": True})
