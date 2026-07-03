import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.security import utcnow
from app.db.base import Base


class Role(str, Enum):
    owner = "owner"
    provider = "provider"
    staff = "staff"
    member = "member"
    internal_admin = "internal_admin"


class SessionCategory(str, Enum):
    botox = "Botox"
    fillers = "Fillers"
    skin = "Skin"
    hair = "Hair"
    body = "Body"
    other = "Other"


class SessionStatus(str, Enum):
    draft = "draft"
    pending_after = "pending_after"
    pending_consent = "pending_consent"
    ready_to_publish = "ready_to_publish"
    published = "published"
    declined = "declined"
    unpublished = "unpublished"


class ObscureMode(str, Enum):
    none = "none"
    eyes = "eyes"
    upper = "upper"
    full = "full"


class ConsentTier(str, Enum):
    full = "full"
    partial = "partial"
    full_blur = "full_blur"
    decline = "decline"


class FollowupStatus(str, Enum):
    scheduled = "scheduled"
    sent = "sent"
    opened = "opened"
    completed = "completed"
    expired = "expired"
    cancelled = "cancelled"


class CreditStatus(str, Enum):
    active = "active"
    redeemed = "redeemed"
    expired = "expired"
    voided = "voided"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class Practice(Base, TimestampMixin):
    __tablename__ = "practices"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    lat: Mapped[float | None] = mapped_column(nullable=True)
    lng: Mapped[float | None] = mapped_column(nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    widget_slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    default_discount_full: Mapped[int] = mapped_column(Integer, default=150)
    default_discount_partial: Mapped[int] = mapped_column(Integer, default=75)
    default_discount_blur: Mapped[int] = mapped_column(Integer, default=25)
    credit_expiration_days: Mapped[int] = mapped_column(Integer, default=180)
    auto_publish: Mapped[bool] = mapped_column(Boolean, default=False)
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    owner: Mapped["User | None"] = relationship(foreign_keys=[owner_id], post_update=True)
    users: Mapped[list["User"]] = relationship(
        back_populates="practice", foreign_keys="User.practice_id"
    )
    sessions: Mapped[list["Session"]] = relationship(back_populates="practice")
    followups: Mapped[list["Followup"]] = relationship(back_populates="practice")
    credits: Mapped[list["Credit"]] = relationship(back_populates="practice")


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    initials: Mapped[str] = mapped_column(String(5), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default=Role.owner.value)
    practice_id: Mapped[str | None] = mapped_column(
        ForeignKey("practices.id"), index=True, nullable=True
    )

    practice: Mapped[Practice | None] = relationship(
        back_populates="users", foreign_keys=[practice_id]
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(back_populates="user")


class Session(Base, TimestampMixin):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    practice_id: Mapped[str] = mapped_column(ForeignKey("practices.id"), index=True)
    patient_initials: Mapped[str] = mapped_column(String(10), nullable=False)
    treatment: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(50), default=SessionCategory.other.value)
    status: Mapped[str] = mapped_column(String(20), default=SessionStatus.draft.value)
    obscure_mode: Mapped[str] = mapped_column(String(10), default=ObscureMode.none.value)
    treatment_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    before_image_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    before_original_image_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    after_image_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    after_original_image_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    before_image_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    before_image_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    after_image_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    after_image_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    capture_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    capture_lat: Mapped[float | None] = mapped_column(nullable=True)
    capture_lng: Mapped[float | None] = mapped_column(nullable=True)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sign_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    after_capture_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    after_captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    after_provenance: Mapped[str | None] = mapped_column(String(50), nullable=True)
    consent_tier: Mapped[str | None] = mapped_column(String(20), nullable=True)
    consent_signature_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consent_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    consent_user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    consent_form_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    discount_applied: Mapped[int | None] = mapped_column(Integer, nullable=True)
    publish_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_destinations: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    seo_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    seo_alt_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    seo_meta_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    seo_filename: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    seo_url_slug: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    seo_template_variant: Mapped[int] = mapped_column(Integer, default=0)
    page_views: Mapped[int] = mapped_column(Integer, default=0)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    practice: Mapped[Practice] = relationship(back_populates="sessions")
    followups: Mapped[list["Followup"]] = relationship(back_populates="session")
    credits: Mapped[list["Credit"]] = relationship(back_populates="session")


class RefreshToken(Base, TimestampMixin):
    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped[User] = relationship(back_populates="refresh_tokens")


class Followup(Base, TimestampMixin):
    __tablename__ = "followups"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    practice_id: Mapped[str] = mapped_column(ForeignKey("practices.id"), index=True)
    patient_email: Mapped[str] = mapped_column(String(255), nullable=False)
    patient_first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    upload_token: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    token_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    custom_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=FollowupStatus.scheduled.value)
    send_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    upload_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reminder_1_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reminder_2_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    session: Mapped[Session] = relationship(back_populates="followups")
    practice: Mapped[Practice] = relationship(back_populates="followups")
    credits: Mapped[list["Credit"]] = relationship(back_populates="followup")


class Credit(Base, TimestampMixin):
    __tablename__ = "credits"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    practice_id: Mapped[str] = mapped_column(ForeignKey("practices.id"), index=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    followup_id: Mapped[str | None] = mapped_column(ForeignKey("followups.id"))
    patient_initials: Mapped[str] = mapped_column(String(10), nullable=False)
    patient_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    consent_tier: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=CreditStatus.active.value)
    earned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    redeemed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    redeem_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    void_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    practice: Mapped[Practice] = relationship(back_populates="credits")
    session: Mapped[Session] = relationship(back_populates="credits")
    followup: Mapped[Followup | None] = relationship(back_populates="credits")
