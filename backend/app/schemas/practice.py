from pydantic import BaseModel, Field


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

