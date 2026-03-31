from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import asc, desc, func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_practice
from app.core.responses import success_response
from app.core.security import utcnow
from app.db.session import get_db
from app.models import Credit, CreditStatus, Practice
from app.schemas.credit import CreditRedeemRequest, CreditVoidRequest
from app.services.logic import query_total
from app.services.serializers import serialize_credit

router = APIRouter(prefix="/credits", tags=["credits"])


def _credit_query(practice_id: str):
    return select(Credit).where(Credit.practice_id == practice_id)


@router.get("")
def list_credits(
    status: str | None = Query(default=None),
    patient_initials: str | None = Query(default=None),
    sort: str = Query(default="created_at", pattern="^(created_at|expires_at|amount)$"),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    practice: Practice = Depends(get_current_practice),
    db: Session = Depends(get_db),
):
    query = _credit_query(practice.id)
    if status:
        query = query.where(Credit.status == status)
    if patient_initials:
        query = query.where(Credit.patient_initials == patient_initials)
    total = query_total(db, query)
    sort_column = getattr(Credit, sort)
    ordering = asc(sort_column) if order == "asc" else desc(sort_column)
    credits = db.scalars(query.order_by(ordering).offset(offset).limit(limit)).all()

    total_active_value = db.scalar(
        select(func.coalesce(func.sum(Credit.amount), 0)).where(
            Credit.practice_id == practice.id,
            Credit.status == CreditStatus.active.value,
        )
    ) or 0
    total_redeemed_value = db.scalar(
        select(func.coalesce(func.sum(Credit.amount), 0)).where(
            Credit.practice_id == practice.id,
            Credit.status == CreditStatus.redeemed.value,
        )
    ) or 0
    total_expired_value = db.scalar(
        select(func.coalesce(func.sum(Credit.amount), 0)).where(
            Credit.practice_id == practice.id,
            Credit.status == CreditStatus.expired.value,
        )
    ) or 0

    return success_response(
        {
            "credits": [serialize_credit(item) for item in credits],
            "total": total,
            "total_active_value": total_active_value,
            "total_redeemed_value": total_redeemed_value,
            "total_expired_value": total_expired_value,
        }
    )


@router.get("/lookup/{code}")
def lookup_credit(code: str, practice: Practice = Depends(get_current_practice), db: Session = Depends(get_db)):
    credit = db.scalar(
        select(Credit).where(Credit.practice_id == practice.id, Credit.code == code)
    )
    if credit is None:
        raise HTTPException(status_code=404, detail="Credit not found")
    return success_response(
        {
            "id": credit.id,
            "code": credit.code,
            "amount": credit.amount,
            "status": credit.status,
            "patient_initials": credit.patient_initials,
            "treatment": credit.session.treatment if credit.session else None,
            "expires_at": credit.expires_at,
        }
    )


@router.get("/stats")
def credit_stats(practice: Practice = Depends(get_current_practice), db: Session = Depends(get_db)):
    credits = db.scalars(_credit_query(practice.id)).all()
    now = utcnow()
    active = [item for item in credits if item.status == CreditStatus.active.value]
    redeemed = [item for item in credits if item.status == CreditStatus.redeemed.value]
    expired = [item for item in credits if item.status == CreditStatus.expired.value]
    voided = [item for item in credits if item.status == CreditStatus.voided.value]
    issued_count = len(credits)
    active_value = sum(item.amount for item in active)
    redeemed_value = sum(item.amount for item in redeemed)
    expiring = [item for item in active if now <= item.expires_at <= now + timedelta(days=30)]
    return success_response(
        {
            "total_issued": issued_count,
            "total_active": len(active),
            "total_redeemed": len(redeemed),
            "total_expired": len(expired),
            "total_voided": len(voided),
            "active_value": active_value,
            "redeemed_value": redeemed_value,
            "average_credit_amount": int(sum(item.amount for item in credits) / issued_count) if issued_count else 0,
            "redemption_rate": (len(redeemed) / issued_count) if issued_count else 0,
            "credits_expiring_30d": len(expiring),
            "credits_expiring_30d_value": sum(item.amount for item in expiring),
        }
    )


@router.get("/{credit_id}")
def get_credit(
    credit_id: str,
    practice: Practice = Depends(get_current_practice),
    db: Session = Depends(get_db),
):
    credit = db.scalar(select(Credit).where(Credit.id == credit_id, Credit.practice_id == practice.id))
    if credit is None:
        raise HTTPException(status_code=404, detail="Credit not found")
    return success_response(serialize_credit(credit))


@router.post("/{credit_id}/redeem")
def redeem_credit(
    credit_id: str,
    payload: CreditRedeemRequest,
    practice: Practice = Depends(get_current_practice),
    db: Session = Depends(get_db),
):
    credit = db.scalar(select(Credit).where(Credit.id == credit_id, Credit.practice_id == practice.id))
    if credit is None:
        raise HTTPException(status_code=404, detail="Credit not found")
    if credit.status != CreditStatus.active.value:
        raise HTTPException(status_code=400, detail="Only active credits can be redeemed")
    credit.status = CreditStatus.redeemed.value
    credit.redeemed_at = utcnow()
    credit.redeemed_by = payload.redeemed_by
    credit.redeem_notes = payload.notes
    db.add(credit)
    db.commit()
    db.refresh(credit)
    return success_response(serialize_credit(credit))


@router.post("/{credit_id}/void")
def void_credit(
    credit_id: str,
    payload: CreditVoidRequest,
    practice: Practice = Depends(get_current_practice),
    db: Session = Depends(get_db),
):
    credit = db.scalar(select(Credit).where(Credit.id == credit_id, Credit.practice_id == practice.id))
    if credit is None:
        raise HTTPException(status_code=404, detail="Credit not found")
    if credit.status != CreditStatus.active.value:
        raise HTTPException(status_code=400, detail="Only active credits can be voided")
    credit.status = CreditStatus.voided.value
    credit.void_reason = payload.reason
    db.add(credit)
    db.commit()
    db.refresh(credit)
    return success_response(serialize_credit(credit))

