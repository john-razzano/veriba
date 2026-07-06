from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_practice
from app.core.responses import success_response
from app.db.session import get_db
from app.models import Practice, Role, User

router = APIRouter(prefix="/members", tags=["members"])


@router.get("/lookup")
def lookup_member(
    user_id: str | None = Query(default=None),
    email: str | None = Query(default=None),
    practice: Practice = Depends(get_current_practice),
    db: Session = Depends(get_db),
):
    """Exact-match member lookup for QR/manual identity binding.

    Returns name + initials only — never the account email.
    Requires practice auth. Accepts user_id or email (not both required).
    """
    from fastapi import HTTPException
    if not user_id and not email:
        raise HTTPException(status_code=422, detail="Provide user_id or email")

    if user_id:
        user = db.get(User, user_id)
    else:
        user = db.scalar(
            select(User).where(User.email == email.strip().lower(), User.role == Role.member.value)
        )

    if user is None or user.role != Role.member.value:
        return success_response({"member": None})

    return success_response({
        "member": {"id": user.id, "name": user.name, "initials": user.initials},
    })
