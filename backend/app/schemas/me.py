from pydantic import BaseModel, EmailStr

from app.models import ConsentTier


class ApprovalRespondRequest(BaseModel):
    decision: ConsentTier
    signature_svg: str | None = None


class ConsultCreateRequest(BaseModel):
    practice_id: str
    session_id: str | None = None
    message: str | None = None
    contact_email: str
    contact_phone: str | None = None


class PushTokenRequest(BaseModel):
    token: str
    platform: str  # "ios" | "android"


class PushTokenDeleteRequest(BaseModel):
    token: str
