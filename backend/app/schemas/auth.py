from typing import Literal

from pydantic import BaseModel, EmailStr, Field, model_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: str = Field(min_length=1, max_length=255)
    role: Literal["provider", "member"] = "provider"
    practice_name: str | None = Field(default=None, min_length=1, max_length=255)
    practice_location: str | None = Field(default=None, min_length=1, max_length=255)
    practice_website: str | None = None

    @model_validator(mode="after")
    def require_practice_fields_for_providers(self) -> "RegisterRequest":
        if self.role == "provider" and not (self.practice_name and self.practice_location):
            raise ValueError(
                "practice_name and practice_location are required for provider accounts"
            )
        return self


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)
