from datetime import UTC

from app.core.config import get_settings
from app.models import (
    ConsentTier,
    Credit,
    Followup,
    ObscureMode,
    Practice,
    Session,
    User,
)
from app.services.logic import build_credit_description, practice_default_discount
from app.services.storage import get_storage


def _iso(value):
    return value.isoformat() if value else None


def serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "initials": user.initials,
        "practice_id": user.practice_id,
        "role": user.role,
        "created_at": _iso(user.created_at),
    }


def serialize_practice(practice: Practice) -> dict:
    coordinates = None
    if practice.lat is not None and practice.lng is not None:
        coordinates = {"lat": practice.lat, "lng": practice.lng}
    return {
        "id": practice.id,
        "name": practice.name,
        "location": practice.location,
        "coordinates": coordinates,
        "website": practice.website,
        "widget_slug": practice.widget_slug,
        "default_discounts": {
            "full": practice.default_discount_full,
            "partial": practice.default_discount_partial,
            "full_blur": practice.default_discount_blur,
        },
        "credit_expiration_days": practice.credit_expiration_days,
        "auto_publish": practice.auto_publish,
        "owner_id": practice.owner_id,
        "created_at": _iso(practice.created_at),
        "updated_at": _iso(practice.updated_at),
    }


def serialize_seo(session: Session) -> dict | None:
    if not session.seo_title:
        return None
    return {
        "title": session.seo_title,
        "alt_text": session.seo_alt_text,
        "meta_description": session.seo_meta_description,
        "filename": session.seo_filename,
        "url_slug": session.seo_url_slug,
    }


def chain_of_custody(session: Session) -> dict:
    checkpoints = []
    if session.capture_hash:
        checkpoints.append(
            {
                "step": "captured",
                "label": "Captured in-app",
                "detail": "Photo taken via Veriba camera",
                "timestamp": _iso(session.captured_at),
                "hash": session.capture_hash,
                "verified": True,
            }
        )
    if session.sign_hash:
        checkpoints.append(
            {
                "step": "signed",
                "label": "Cryptographically signed",
                "detail": "SHA-256 hash recorded at capture",
                "timestamp": _iso(session.signed_at or session.captured_at),
                "hash": session.sign_hash,
                "verified": True,
            }
        )
    if session.capture_lat is not None and session.capture_lng is not None:
        checkpoints.append(
            {
                "step": "geotagged",
                "label": "Geo-tagged & timestamped",
                "detail": f"{session.capture_lat:.2f}, {session.capture_lng:.2f}",
                "timestamp": _iso(session.captured_at),
                "hash": None,
                "verified": True,
            }
        )
    if session.after_image_key and session.after_provenance:
        checkpoints.append(
            {
                "step": "after_uploaded",
                "label": "After photo uploaded",
                "detail": session.after_provenance,
                "timestamp": _iso(session.after_captured_at),
                "hash": session.after_capture_hash,
                "verified": True,
            }
        )
    if session.consent_at:
        detail = "Consent declined" if session.consent_tier == ConsentTier.decline.value else f"{session.consent_tier} consent recorded"
        checkpoints.append(
            {
                "step": "consent",
                "label": "Consent recorded",
                "detail": detail,
                "timestamp": _iso(session.consent_at),
                "hash": None,
                "verified": True,
            }
        )
    if session.published_at:
        checkpoints.append(
            {
                "step": "published",
                "label": "Published to web",
                "detail": "Widget + gallery publishing completed",
                "timestamp": _iso(session.published_at),
                "hash": session.publish_hash,
                "verified": True,
            }
        )
    return {
        "all_verified": bool(checkpoints) and all(item["verified"] for item in checkpoints),
        "checkpoints": checkpoints,
    }


def _image_url(key: str | None) -> str | None:
    if not key:
        return None
    return get_storage().public_url(key)


def serialize_session_summary(session: Session) -> dict:
    return {
        "id": session.id,
        "patient_initials": session.patient_initials,
        "treatment": session.treatment,
        "category": session.category,
        "status": session.status,
        "obscure_mode": session.obscure_mode,
        "consent_tier": session.consent_tier,
        "before_image_url": _image_url(session.before_image_key),
        "after_image_url": _image_url(session.after_image_key),
        "page_views": session.page_views,
        "captured_at": _iso(session.captured_at),
        "published_at": _iso(session.published_at),
        "created_at": _iso(session.created_at),
        "updated_at": _iso(session.updated_at),
    }


def serialize_session_detail(session: Session) -> dict:
    return {
        **serialize_session_summary(session),
        "chain_of_custody": chain_of_custody(session),
        "consent_signature_url": _image_url(session.consent_signature_key),
        "consent_at": _iso(session.consent_at),
        "discount_applied": session.discount_applied,
        "seo": serialize_seo(session),
    }


def serialize_followup(followup: Followup) -> dict:
    settings = get_settings()
    upload_url = f"{settings.patient_portal_base_url.rstrip('/')}/{followup.upload_token}"
    return {
        "id": followup.id,
        "session_id": followup.session_id,
        "patient_email": followup.patient_email,
        "patient_first_name": followup.patient_first_name,
        "send_at": _iso(followup.send_at),
        "status": followup.status,
        "upload_token": followup.upload_token,
        "upload_url": upload_url,
        "sent_at": _iso(followup.sent_at),
        "opened_at": _iso(followup.opened_at),
        "upload_completed_at": _iso(followup.upload_completed_at),
        "expires_at": _iso(followup.token_expires_at),
        "created_at": _iso(followup.created_at),
    }


def serialize_credit(credit: Credit) -> dict:
    return {
        "id": credit.id,
        "session_id": credit.session_id,
        "patient_initials": credit.patient_initials,
        "patient_email": credit.patient_email,
        "code": credit.code,
        "amount": credit.amount,
        "description": credit.description,
        "consent_tier": credit.consent_tier,
        "status": credit.status,
        "earned_at": _iso(credit.earned_at),
        "expires_at": _iso(credit.expires_at),
        "redeemed_at": _iso(credit.redeemed_at),
        "redeemed_by": credit.redeemed_by,
        "notes": credit.redeem_notes,
        "void_reason": credit.void_reason,
    }


def serialize_patient_context(practice: Practice, session: Session, followup: Followup) -> dict:
    reward_amount = practice.default_discount_full
    return {
        "valid": True,
        "practice_name": practice.name,
        "patient_first_name": followup.patient_first_name,
        "treatment": session.treatment,
        "before_image_url": _image_url(session.before_image_key),
        "captured_at": _iso(session.captured_at),
        "reward_amount": reward_amount,
        "reward_description": build_credit_description(reward_amount),
        "consent_options": [
            {
                "tier": ConsentTier.full.value,
                "label": "Full face — no obscuring",
                "reward": f"${practice.default_discount_full} off",
            },
            {
                "tier": ConsentTier.partial.value,
                "label": "Eyes blurred",
                "reward": f"${practice.default_discount_partial} off",
            },
            {
                "tier": ConsentTier.full_blur.value,
                "label": "Full face blur",
                "reward": f"${practice.default_discount_blur} off",
            },
            {
                "tier": ConsentTier.decline.value,
                "label": "I don't want my photos shared",
                "reward": "No reward",
            },
        ],
        "expires_at": _iso(followup.token_expires_at),
    }


def serialize_public_session(session: Session) -> dict:
    return {
        "id": session.id,
        "treatment": session.treatment,
        "category": session.category,
        "before_image_url": _image_url(session.before_image_key),
        "after_image_url": _image_url(session.after_image_key),
        "obscure_mode": session.obscure_mode,
        "seo": serialize_seo(session),
        "chain_of_custody": {
            "all_verified": chain_of_custody(session)["all_verified"],
            "checkpoint_count": len(chain_of_custody(session)["checkpoints"]),
        },
        "published_at": _iso(session.published_at),
    }


def serialize_public_practice(
    practice: Practice,
    *,
    owner: User | None = None,
    published_session_count: int = 0,
    featured_session: Session | None = None,
) -> dict:
    coordinates = None
    if practice.lat is not None and practice.lng is not None:
        coordinates = {"lat": practice.lat, "lng": practice.lng}

    provider_name = owner.name if owner is not None else practice.name
    provider_initials = owner.initials if owner is not None else None

    return {
        "id": practice.id,
        "name": practice.name,
        "location": practice.location,
        "website": practice.website,
        "widget_slug": practice.widget_slug,
        "coordinates": coordinates,
        "provider_name": provider_name,
        "provider_initials": provider_initials,
        "published_session_count": published_session_count,
        "featured_treatment": featured_session.treatment if featured_session else None,
        "featured_image_url": (
            (
                _image_url(featured_session.after_image_key)
                or _image_url(featured_session.before_image_key)
            )
            if featured_session
            else None
        ),
    }


def serialize_public_session_card(
    session: Session,
    practice: Practice,
    *,
    owner: User | None = None,
) -> dict:
    return {
        **serialize_public_session(session),
        "practice": {
            "id": practice.id,
            "name": practice.name,
            "location": practice.location,
            "widget_slug": practice.widget_slug,
            "website": practice.website,
        },
        "provider": {
            "name": owner.name if owner is not None else practice.name,
            "initials": owner.initials if owner is not None else None,
        },
    }


def serialize_public_case_study(
    session: Session,
    practice: Practice,
    *,
    owner: User | None = None,
) -> dict:
    return {
        **serialize_public_session_card(session, practice, owner=owner),
        "treatment_details": session.treatment_details,
        "page_views": session.page_views,
        "chain_of_custody": chain_of_custody(session),
        "seo": serialize_seo(session),
    }
