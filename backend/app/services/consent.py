from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.security import utcnow
from app.models import (
    ConsentTier,
    Followup,
    FollowupStatus,
    Practice,
    Session as PhotoSession,
    SessionStatus,
)
from app.services.images import render_signature_png
from app.services.logic import (
    create_credit,
    obscure_mode_for_consent,
    practice_default_discount,
    publish_if_needed,
)
from app.services.serializers import serialize_credit
from app.services.storage import get_storage


@dataclass
class ConsentResult:
    consent_tier: str
    reward: dict | None


def apply_consent(
    db: Session,
    *,
    followup: Followup,
    practice: Practice,
    session: PhotoSession,
    consent_tier: str,
    signature_svg: str | None,
    patient_email: str,
    request_ip: str | None = None,
    request_ua: str | None = None,
    consent_form_version: str | None = None,
) -> ConsentResult:
    """Apply a consent decision, issue credit if applicable, update statuses, and commit."""
    session.consent_tier = consent_tier
    session.consent_at = utcnow()
    session.discount_applied = practice_default_discount(practice, consent_tier)
    session.obscure_mode = obscure_mode_for_consent(consent_tier)
    session.consent_ip = request_ip
    session.consent_user_agent = request_ua
    session.consent_form_version = consent_form_version

    if signature_svg and consent_tier != ConsentTier.decline.value:
        signature_key = f"{practice.id}/sessions/{session.id}/consent/signature.png"
        get_storage().save_bytes(signature_key, render_signature_png(signature_svg))
        session.consent_signature_key = signature_key

    reward = None
    if consent_tier == ConsentTier.decline.value:
        session.status = SessionStatus.declined.value
        session.discount_applied = 0
    else:
        credit = create_credit(
            db,
            practice=practice,
            session=session,
            patient_email=patient_email,
            consent_tier=consent_tier,
            followup=followup,
        )
        reward = serialize_credit(credit)
        publish_if_needed(db, session, practice)

    followup.status = FollowupStatus.completed.value
    db.add_all([session, followup])
    db.commit()

    return ConsentResult(consent_tier=consent_tier, reward=reward)
