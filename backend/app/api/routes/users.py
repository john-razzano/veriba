from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.responses import success_response
from app.core.security import hash_password, verify_password
from app.db.session import get_db
from app.models import User
from app.schemas.user import PasswordChangeRequest, UserUpdateRequest
from app.services.logic import derive_initials
from app.services.serializers import serialize_user

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return success_response(serialize_user(current_user))


@router.patch("/me")
def update_me(
    payload: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.email and payload.email.lower() != current_user.email:
        existing = db.scalar(select(User).where(User.email == payload.email.lower()))
        if existing:
            raise HTTPException(status_code=409, detail="Email already in use")
        current_user.email = payload.email.lower()

    if payload.name:
        current_user.name = payload.name
        current_user.initials = derive_initials(payload.name)

    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return success_response(serialize_user(current_user))


@router.patch("/me/password")
def change_password(
    payload: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    current_user.password_hash = hash_password(payload.new_password)
    db.add(current_user)
    db.commit()
    return success_response({"success": True})

