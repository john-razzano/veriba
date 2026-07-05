import re

from pydantic import BaseModel, Field, field_validator

_HTTP_RE = re.compile(r"^https?://", re.IGNORECASE)


def _normalize_url(v: str | None) -> str | None:
    if v is None:
        return None
    stripped = v.strip()
    if not stripped:
        return None
    if not _HTTP_RE.match(stripped):
        stripped = f"https://{stripped}"
    return stripped


class DefaultDiscountsUpdate(BaseModel):
    full: int | None = Field(default=None, ge=0)
    partial: int | None = Field(default=None, ge=0)
    full_blur: int | None = Field(default=None, ge=0)


class PracticeUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    location: str | None = Field(default=None, min_length=1, max_length=255)
    website: str | None = None
    lat: float | None = None
    lng: float | None = None
    default_discounts: DefaultDiscountsUpdate | None = None
    credit_expiration_days: int | None = Field(default=None, ge=30, le=365)
    auto_publish: bool | None = None
    bio: str | None = Field(default=None, max_length=600)
    booking_url: str | None = None
    featured_session_id: str | None = None
    services: list[str] | None = None

    @field_validator("website", "booking_url", mode="before")
    @classmethod
    def normalize_url_field(cls, v: object) -> str | None:
        if not isinstance(v, str):
            return v  # type: ignore[return-value]
        return _normalize_url(v)

    @field_validator("services", mode="before")
    @classmethod
    def validate_services(cls, v: object) -> list[str] | None:
        if v is None:
            return None
        if not isinstance(v, list):
            raise ValueError("services must be a list")
        if len(v) > 30:
            raise ValueError("services must have at most 30 items")
        seen: set[str] = set()
        result: list[str] = []
        for item in v:
            stripped = str(item).strip()
            if not stripped:
                continue
            if len(stripped) > 60:
                raise ValueError("each service must be at most 60 characters")
            lower = stripped.lower()
            if lower not in seen:
                seen.add(lower)
                result.append(stripped)
        return result or None
