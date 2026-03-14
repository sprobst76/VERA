import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.core.config import settings
from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, Token, RefreshRequest


def _pw_min_length(v: str) -> str:
    if len(v) < 8:
        raise ValueError("Passwort muss mindestens 8 Zeichen lang sein")
    return v


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        return _pw_min_length(v)


class AcceptInviteRequest(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        return _pw_min_length(v)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        return _pw_min_length(v)


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=status.HTTP_410_GONE, include_in_schema=False)
async def register(payload: RegisterRequest, db: DB):
    """Selbst-Registrierung ist deaktiviert. Tenants werden durch SuperAdmins angelegt."""
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Selbst-Registrierung ist deaktiviert. Wende dich an den Administrator.",
    )


@router.post("/login", response_model=Token)
async def login(payload: LoginRequest, db: DB):
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Account is deactivated")

    access_token = create_access_token(user.id, user.tenant_id, user.role)
    refresh_token = create_refresh_token(user.id, user.tenant_id)

    return Token(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=Token)
async def refresh_token(payload: RefreshRequest, db: DB):
    try:
        token_data = decode_token(payload.refresh_token)
        if token_data.get("type") != "refresh":
            raise ValueError("Not a refresh token")
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    import uuid
    user_id = uuid.UUID(token_data["sub"])
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    access_token = create_access_token(user.id, user.tenant_id, user.role)
    new_refresh_token = create_refresh_token(user.id, user.tenant_id)

    return Token(access_token=access_token, refresh_token=new_refresh_token)


@router.get("/me")
async def get_me(current_user: CurrentUser):
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "role": current_user.role,
        "tenant_id": str(current_user.tenant_id),
        "is_active": current_user.is_active,
        "ical_token": current_user.ical_token,
    }


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(payload: ChangePasswordRequest, current_user: CurrentUser, db: DB):
    """Allows any authenticated user to change their own password."""
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Aktuelles Passwort ist falsch")
    current_user.hashed_password = hash_password(payload.new_password)
    await db.commit()


# ── Invite endpoints ─────────────────────────────────────────────────────────

@router.get("/invite/{token}")
async def check_invite(token: str, db: DB):
    """Validates an invite token and returns the associated email."""
    now = datetime.now(timezone.utc)
    result = await db.execute(select(User).where(User.invite_token == token))
    user = result.scalar_one_or_none()
    if not user or not user.invite_expires_at or user.invite_expires_at < now:
        raise HTTPException(status_code=404, detail="Einladungslink ungültig oder abgelaufen")
    return {"email": user.email}


@router.post("/accept-invite", response_model=Token)
async def accept_invite(payload: AcceptInviteRequest, db: DB):
    """Sets the password via invite token and returns login tokens."""
    now = datetime.now(timezone.utc)
    result = await db.execute(select(User).where(User.invite_token == payload.token))
    user = result.scalar_one_or_none()
    if not user or not user.invite_expires_at or user.invite_expires_at < now:
        raise HTTPException(status_code=400, detail="Einladungslink ungültig oder abgelaufen")

    user.hashed_password = hash_password(payload.new_password)
    user.is_active = True
    user.invite_token = None
    user.invite_expires_at = None
    await db.commit()

    access_token = create_access_token(user.id, user.tenant_id, user.role)
    refresh_token = create_refresh_token(user.id, user.tenant_id)
    return Token(access_token=access_token, refresh_token=refresh_token)


# ── Password reset endpoints ──────────────────────────────────────────────────

@router.post("/forgot-password")
async def forgot_password(payload: ForgotPasswordRequest, db: DB):
    """Sends a password-reset e-mail. Always returns 200 to prevent user enumeration."""
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if user and user.is_active:
        token = secrets.token_urlsafe(32)
        user.reset_token = token
        user.reset_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        await db.commit()

        link = f"{settings.FRONTEND_URL}/auth/reset-password?token={token}"
        # Best-effort email – failures are silently ignored
        try:
            from app.services.notification_service import NotificationService
            ns = NotificationService()
            await ns._send_email(
                to=user.email,
                subject="VERA – Passwort zurücksetzen",
                body=(
                    f"Hallo,\n\n"
                    f"du hast eine Anfrage zum Zurücksetzen deines Passworts gestellt.\n\n"
                    f"Klicke auf den folgenden Link, um ein neues Passwort zu vergeben "
                    f"(gültig für 1 Stunde):\n\n{link}\n\n"
                    f"Falls du diese Anfrage nicht gestellt hast, ignoriere diese E-Mail.\n\n"
                    f"Dein VERA-Team"
                ),
            )
        except Exception:
            pass

    return {"message": "Falls ein Konto mit dieser E-Mail-Adresse existiert, wurde eine E-Mail gesendet."}


@router.get("/check-reset/{token}")
async def check_reset(token: str, db: DB):
    """Validates a reset token and returns the associated email."""
    now = datetime.now(timezone.utc)
    result = await db.execute(select(User).where(User.reset_token == token))
    user = result.scalar_one_or_none()
    if not user or not user.reset_expires_at or user.reset_expires_at < now:
        raise HTTPException(status_code=404, detail="Link ungültig oder abgelaufen")
    return {"email": user.email}


@router.post("/reset-password")
async def reset_password(payload: ResetPasswordRequest, db: DB):
    """Sets a new password via reset token."""
    now = datetime.now(timezone.utc)
    result = await db.execute(select(User).where(User.reset_token == payload.token))
    user = result.scalar_one_or_none()
    if not user or not user.reset_expires_at or user.reset_expires_at < now:
        raise HTTPException(status_code=400, detail="Link ungültig oder abgelaufen")

    user.hashed_password = hash_password(payload.new_password)
    user.reset_token = None
    user.reset_expires_at = None
    await db.commit()
    return {"message": "Passwort erfolgreich geändert"}
