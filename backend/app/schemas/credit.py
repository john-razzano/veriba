from pydantic import BaseModel, Field


class CreditRedeemRequest(BaseModel):
    redeemed_by: str = Field(min_length=1, max_length=255)
    notes: str | None = None


class CreditVoidRequest(BaseModel):
    reason: str = Field(min_length=1)

