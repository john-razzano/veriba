from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_practice
from app.core.responses import success_response
from app.core.security import utcnow
from app.db.session import get_db
from app.models import ConsultRequest, Practice
from app.services.serializers import serialize_consult

router = APIRouter(prefix="/consults", tags=["consults"])


@router.get("")
def list_consults_for_practice(
    status: str = Query(default="new", pattern="^(new|handled|all)$"),
    practice: Practice = Depends(get_current_practice),
    db: Session = Depends(get_db),
):
    q = select(ConsultRequest).where(ConsultRequest.practice_id == practice.id)
    if status != "all":
        q = q.where(ConsultRequest.status == status)
    q = q.order_by(ConsultRequest.created_at.desc())
    consults = db.scalars(q).all()
    return success_response({"consults": [serialize_consult(c, db) for c in consults], "total": len(consults)})


@router.post("/{consult_id}/handled")
def mark_handled(
    consult_id: str,
    practice: Practice = Depends(get_current_practice),
    db: Session = Depends(get_db),
):
    from fastapi import HTTPException
    consult = db.get(ConsultRequest, consult_id)
    if consult is None or consult.practice_id != practice.id:
        raise HTTPException(status_code=404, detail="Consult request not found")
    if consult.status != "handled":
        consult.status = "handled"
        consult.handled_at = utcnow()
        db.add(consult)
        db.commit()
    return success_response(serialize_consult(consult, db))
