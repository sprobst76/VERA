import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, Token, RefreshRequest


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Passwort muss mindestens 8 Zeichen lang sein")
        return v

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
