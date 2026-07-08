from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from jwt import InvalidTokenError
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.responses import success_response
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    sha256_hexdigest,
    utcnow,
    verify_password,
)
from app.db.session import get_db
from app.models import Practice, RefreshToken, Role, User
from app.schemas.auth import LoginRequest, OAuthRequest, RefreshRequest, RegisterRequest
from app.services.logic import derive_initials, normalize_website, unique_widget_slug
from app.services.oauth import verify_apple, verify_google
from app.services.serializers import serialize_practice, serialize_user

router = APIRouter(prefix="/auth", tags=["auth"])


def issue_tokens(db: Session, user: User) -> dict:
    settings = get_settings()
    expires_at = utcnow() + timedelta(days=settings.refresh_token_expire_days)
    token_record = RefreshToken(user_id=user.id, token_hash="pending", expires_at=expires_at)
    db.add(token_record)
    db.flush()
    refresh_token = create_refresh_token(user.id, token_record.id)
    token_record.token_hash = sha256_hexdigest(refresh_token)
    access_token = create_access_token(user.id, user.practice_id, user.role)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post("/register")
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.scalar(select(User).where(User.email == payload.email.lower()))
    if existing:
        raise HTTPException(status_code=409, detail="Email already in use")

    if payload.role == "member":
        user = User(
            email=payload.email.lower(),
            password_hash=hash_password(payload.password),
            name=payload.name,
            initials=derive_initials(payload.name),
            role=Role.member.value,
            practice_id=None,
        )
        db.add(user)
        db.flush()

        tokens = issue_tokens(db, user)
        db.commit()
        db.refresh(user)

        return success_response(
            {
                "user": serialize_user(user),
                "practice": None,
                **tokens,
            },
            status_code=201,
        )

    practice = Practice(
        name=payload.practice_name,
        location=payload.practice_location,
        website=normalize_website(payload.practice_website),
        widget_slug=unique_widget_slug(db, payload.practice_name),
    )
    db.add(practice)
    db.flush()

    user = User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        name=payload.name,
        initials=derive_initials(payload.name),
        role=Role.owner.value,
        practice_id=practice.id,
    )
    db.add(user)
    db.flush()

    practice.owner_id = user.id
    tokens = issue_tokens(db, user)
    db.commit()
    db.refresh(user)
    db.refresh(practice)

    return success_response(
        {
            "user": serialize_user(user),
            "practice": serialize_practice(practice),
            **tokens,
        },
        status_code=201,
    )


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or user.password_hash is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    tokens = issue_tokens(db, user)
    db.commit()

    return success_response({**tokens, "user": serialize_user(user)})


@router.post("/refresh")
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    try:
        decoded = decode_token(payload.refresh_token, "refresh")
    except InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid refresh token") from exc

    token_record = db.scalar(
        select(RefreshToken).where(
            RefreshToken.id == decoded.get("jti"),
            RefreshToken.token_hash == sha256_hexdigest(payload.refresh_token),
        )
    )
    if (
        token_record is None
        or token_record.revoked
        or token_record.expires_at <= utcnow()
    ):
        raise HTTPException(status_code=401, detail="Refresh token has expired or been revoked")

    user = db.scalar(select(User).where(User.id == decoded["sub"]))
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")

    token_record.revoked = True
    tokens = issue_tokens(db, user)
    db.commit()
    return success_response(tokens)


@router.post("/oauth")
def oauth_login(payload: OAuthRequest, db: Session = Depends(get_db)):
    settings = get_settings()
    try:
        if payload.provider == "google":
            if not settings.google_ios_client_id:
                raise HTTPException(status_code=503, detail="Google sign-in not configured")
            claims = verify_google(payload.id_token, settings.google_ios_client_id)
        else:  # apple
            claims = verify_apple(payload.id_token, settings.apple_bundle_id)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Sign-in failed")

    provider = payload.provider
    subject = claims["sub"]
    raw_email = claims.get("email", "") or ""
    email = raw_email.strip().lower() or None
    email_verified = bool(claims.get("email_verified", False))

    # 1. Subject match → existing linked account
    user = db.scalar(
        select(User).where(User.auth_provider == provider, User.oauth_subject == subject)
    )

    # 2. Verified email match → link provider to existing account
    if user is None and email and email_verified:
        user = db.scalar(select(User).where(User.email == email))
        if user:
            user.auth_provider = provider
            user.oauth_subject = subject
            db.add(user)

    # 3. Create new member
    if user is None:
        if not email:
            raise HTTPException(
                status_code=409,
                detail=(
                    "We couldn't retrieve your account email — remove Veriba from "
                    "Settings → Apple ID → Sign-In & Security and try again."
                ),
            )
        name = (
            payload.full_name
            or claims.get("name", "")
            or email.split("@")[0]
        ).strip() or "User"
        user = User(
            email=email,
            password_hash=None,
            name=name,
            initials=derive_initials(name),
            role=Role.member.value,
            auth_provider=provider,
            oauth_subject=subject,
        )
        db.add(user)
        db.flush()

    tokens = issue_tokens(db, user)
    db.commit()
    db.refresh(user)
    return success_response({**tokens, "user": serialize_user(user)})


@router.post("/logout")
def logout(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_id == current_user.id,
            RefreshToken.revoked.is_(False),
        )
        .values(revoked=True)
    )
    db.commit()
    return success_response({"success": True})

