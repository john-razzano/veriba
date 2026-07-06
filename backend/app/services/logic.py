import re
import unicodedata
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.security import random_code, sha256_hexdigest, utcnow
from app.models import (
    ConsentTier,
    Credit,
    CreditStatus,
    Followup,
    FollowupStatus,
    ObscureMode,
    Practice,
    RefreshToken,
    Role,
    Session as PhotoSession,
    SessionCategory,
    SessionStatus,
    User,
)

FOLLOWUP_DELAYS = {
    SessionCategory.botox.value: 14,
    SessionCategory.fillers.value: 7,
    "Chemical Peel": 10,
    "Microneedling": 7,
    "Laser Resurfacing": 14,
    "Hair Restoration – PRP": 30,
    "CoolSculpting": 60,
    "Thread Lift": 21,
    SessionCategory.other.value: 14,
}


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    lowered = normalized.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return slug or "item"


def derive_initials(value: str) -> str:
    letters = re.findall(r"[A-Za-z0-9]", value)
    if not letters:
        return "NA"

    parts = re.findall(r"[A-Za-z0-9]+", value)
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()[:5]
    return "".join(letters[:2]).upper()


def normalize_website(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip()
    if cleaned.startswith("http://") or cleaned.startswith("https://"):
        return cleaned
    return f"https://{cleaned}"


def unique_widget_slug(db: Session, practice_name: str) -> str:
    base = slugify(practice_name)
    candidate = base
    suffix = 2
    while db.scalar(select(Practice).where(Practice.widget_slug == candidate)):
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def persist_refresh_token(db: Session, user: User, raw_token: str, expires_at: datetime) -> RefreshToken:
    record = RefreshToken(
        user_id=user.id,
        token_hash=sha256_hexdigest(raw_token),
        expires_at=expires_at,
    )
    db.add(record)
    db.flush()
    return record


def practice_default_discount(practice: Practice, consent_tier: str) -> int:
    if consent_tier == ConsentTier.full.value:
        return practice.default_discount_full
    if consent_tier == ConsentTier.partial.value:
        return practice.default_discount_partial
    if consent_tier == ConsentTier.full_blur.value:
        return practice.default_discount_blur
    return 0


def obscure_mode_for_consent(consent_tier: str) -> str:
    if consent_tier == ConsentTier.partial.value:
        return ObscureMode.eyes.value
    if consent_tier == ConsentTier.full_blur.value:
        return ObscureMode.full.value
    return ObscureMode.none.value


def next_status_after_consent(practice: Practice) -> str:
    return SessionStatus.published.value if practice.auto_publish else SessionStatus.ready_to_publish.value


def update_status_after_image_upload(session: PhotoSession) -> str:
    if session.before_image_key and session.after_image_key:
        return SessionStatus.pending_consent.value
    if session.before_image_key:
        return SessionStatus.pending_after.value
    return SessionStatus.draft.value


def followup_send_at(session: PhotoSession, send_at: datetime | None) -> datetime:
    if send_at:
        return send_at.astimezone(UTC) if send_at.tzinfo else send_at.replace(tzinfo=UTC)
    base = session.captured_at or session.created_at or utcnow()
    delay_days = FOLLOWUP_DELAYS.get(session.category, FOLLOWUP_DELAYS[SessionCategory.other.value])
    return base + timedelta(days=delay_days)


def build_publish_hash(session: PhotoSession, published_at: datetime) -> str:
    payload = ":".join(
        [
            session.capture_hash or "",
            session.after_capture_hash or "",
            session.consent_tier or "",
            str(session.discount_applied or 0),
            published_at.isoformat(),
        ]
    )
    return sha256_hexdigest(payload)


def generate_reward_code(session: PhotoSession, amount: int) -> str:
    initials = derive_initials(session.patient_initials)
    return f"VERIBA-{initials}-{amount}-{random_code()}"


def ensure_session_belongs_to_practice(db: Session, session_id: str, practice_id: str) -> PhotoSession:
    session = db.scalar(
        select(PhotoSession).where(
            PhotoSession.id == session_id,
            PhotoSession.practice_id == practice_id,
            PhotoSession.archived_at.is_(None),
        )
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


def ensure_followup_belongs_to_session(
    db: Session, *, session_id: str, practice_id: str, followup_id: str
) -> Followup:
    followup = db.scalar(
        select(Followup).where(
            Followup.id == followup_id,
            Followup.session_id == session_id,
            Followup.practice_id == practice_id,
        )
    )
    if followup is None:
        raise HTTPException(status_code=404, detail="Follow-up not found")
    return followup


def expire_followup_if_needed(followup: Followup) -> None:
    if followup.token_expires_at < utcnow() and followup.status not in {
        FollowupStatus.completed.value,
        FollowupStatus.cancelled.value,
    }:
        followup.status = FollowupStatus.expired.value


def build_credit_description(amount: int) -> str:
    return f"${amount} off your next visit"


def existing_credit_for_session(db: Session, session_id: str) -> Credit | None:
    return db.scalar(select(Credit).where(Credit.session_id == session_id))


def create_credit(
    db: Session,
    *,
    practice: Practice,
    session: PhotoSession,
    patient_email: str | None,
    consent_tier: str,
    followup: Followup | None = None,
) -> Credit:
    existing = existing_credit_for_session(db, session.id)
    if existing is not None:
        return existing

    amount = practice_default_discount(practice, consent_tier)
    earned_at = utcnow()
    expires_at = earned_at + timedelta(days=practice.credit_expiration_days)
    credit = Credit(
        practice_id=practice.id,
        session_id=session.id,
        followup_id=followup.id if followup else None,
        patient_initials=session.patient_initials,
        patient_email=patient_email,
        code=generate_reward_code(session, amount),
        amount=amount,
        description=build_credit_description(amount),
        consent_tier=consent_tier,
        status=CreditStatus.active.value,
        earned_at=earned_at,
        expires_at=expires_at,
    )
    db.add(credit)
    db.flush()
    return credit


def publish_if_needed(db: Session, session: PhotoSession, practice: Practice) -> None:
    from app.services.seo import generate_seo

    # full_blur requires pixel-level image obscuration before publication.
    # Hold at ready_to_publish until that tooling is implemented.
    if session.consent_tier == ConsentTier.full_blur.value:
        session.status = SessionStatus.ready_to_publish.value
        return

    if practice.auto_publish:
        now = utcnow()
        session.published_at = now
        session.status = SessionStatus.published.value
        session.published_destinations = ["widget", "gallery"]
        seo = generate_seo(db, session=session, practice=practice)
        session.seo_title = seo["title"]
        session.seo_alt_text = seo["alt_text"]
        session.seo_meta_description = seo["meta_description"]
        session.seo_filename = seo["filename"]
        session.seo_url_slug = seo["url_slug"]
        session.seo_template_variant = seo["template_variant"]
        session.publish_hash = build_publish_hash(session, now)
    else:
        session.status = next_status_after_consent(practice)


def is_publishable(session: PhotoSession) -> bool:
    return bool(
        session.before_image_key
        and session.after_image_key
        and session.consent_tier
        and session.consent_tier != ConsentTier.decline.value
    )


def resolve_followup_member(followup: Followup, db: Session) -> User | None:
    """Resolve the member user for a followup.

    patient_user_id wins when set; otherwise case-insensitive email match
    against member-role users. This single rule is used in push, approvals,
    results, and the followup serializer.
    """
    if followup.patient_user_id:
        user = db.get(User, followup.patient_user_id)
        return user if user and user.role == Role.member.value else None
    return db.scalar(
        select(User).where(
            func.lower(User.email) == followup.patient_email.lower(),
            User.role == Role.member.value,
        )
    )


def query_total(db: Session, query: Select) -> int:
    subquery = query.subquery()
    return db.scalar(select(func.count()).select_from(subquery)) or 0

