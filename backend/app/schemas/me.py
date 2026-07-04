from pydantic import BaseModel

from app.models import ConsentTier


class ApprovalRespondRequest(BaseModel):
    decision: ConsentTier
    signature_svg: str | None = None
