from pydantic import BaseModel, Field

from app.models import ConsentTier, ObscureMode, SessionCategory, SessionStatus


class SessionCreateRequest(BaseModel):
    patient_initials: str = Field(min_length=1, max_length=10)
    treatment: str = Field(min_length=1, max_length=255)
    category: SessionCategory = SessionCategory.other
    status: SessionStatus = SessionStatus.draft


class SessionUpdateRequest(BaseModel):
    patient_initials: str | None = Field(default=None, min_length=1, max_length=10)
    treatment: str | None = Field(default=None, min_length=1, max_length=255)
    category: SessionCategory | None = None
    obscure_mode: ObscureMode | None = None
    treatment_details: str | None = None


class ConsentRequest(BaseModel):
    consent_tier: ConsentTier
    obscure_mode: ObscureMode | None = None
    discount_applied: int | None = Field(default=None, ge=0)
    signature_svg: str | None = None


class PublishRequest(BaseModel):
    destinations: list[str] = Field(default_factory=lambda: ["widget", "gallery"])
    treatment_details: str | None = None

