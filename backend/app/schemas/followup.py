from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class FollowupCreateRequest(BaseModel):
    patient_email: EmailStr
    patient_first_name: str | None = Field(default=None, max_length=100)
    send_at: datetime | None = None
    message: str | None = None
    patient_user_id: str | None = None  # QR-bound member account; wins over email for resolution
