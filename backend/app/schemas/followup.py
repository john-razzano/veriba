from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, model_validator


class FollowupCreateRequest(BaseModel):
    patient_email: EmailStr | None = None  # required when patient_user_id absent
    patient_first_name: str | None = Field(default=None, max_length=100)
    send_at: datetime | None = None
    message: str | None = None
    patient_user_id: str | None = None  # QR-bound member; wins over email for resolution

    @model_validator(mode="after")
    def require_email_or_user_id(self) -> "FollowupCreateRequest":
        if not self.patient_email and not self.patient_user_id:
            raise ValueError("Provide patient_email or patient_user_id (or both)")
        return self
