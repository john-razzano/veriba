from pydantic import BaseModel

from app.models import ConsentTier


class PatientConsentRequest(BaseModel):
    consent_tier: ConsentTier
    signature_data: str | None = None
    consent_form_version: str | None = None

