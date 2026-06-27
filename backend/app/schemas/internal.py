from pydantic import BaseModel, EmailStr, Field

from app.schemas.practice import DefaultDiscountsUpdate


class InternalPracticeCreateRequest(BaseModel):
    owner_name: str = Field(min_length=1, max_length=255)
    owner_email: EmailStr
    owner_password: str = Field(min_length=8)
    practice_name: str = Field(min_length=1, max_length=255)
    practice_location: str = Field(min_length=1, max_length=255)
    practice_website: str | None = None
    auto_publish: bool = False
    credit_expiration_days: int | None = Field(default=None, ge=30, le=365)
    default_discounts: DefaultDiscountsUpdate | None = None


class InternalPracticeOwnerUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    email: EmailStr | None = None
