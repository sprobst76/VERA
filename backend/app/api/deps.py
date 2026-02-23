from typing import Annotated
import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User
from app.models.superadmin import SuperAdmin
from app.schemas.auth import TokenData

security = HTTPBearer()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            raise credentials_exception
        user_id = uuid.UUID(payload["sub"])
    except (ValueError, KeyError):
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise credentials_exception

    return user


async def get_current_active_admin(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if current_user.role not in ("admin",):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    return current_user


async def get_current_manager_or_admin(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Allows admin and manager (Verwalter) roles."""
    if current_user.role not in ("admin", "manager"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions – admin or manager required",
        )
    return current_user


def get_token_data(user: User) -> TokenData:
    return TokenData(
        user_id=user.id,
        tenant_id=user.tenant_id,
        role=user.role,
    )


async def get_current_superadmin(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SuperAdmin:
    exc = HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="SuperAdmin-Berechtigung erforderlich",
    )
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "superadmin":
            raise exc
        superadmin_id = uuid.UUID(payload["sub"])
    except (ValueError, KeyError):
        raise exc

    result = await db.execute(select(SuperAdmin).where(SuperAdmin.id == superadmin_id))
    sa = result.scalar_one_or_none()
    if sa is None or not sa.is_active:
        raise exc
    return sa


CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(get_current_active_admin)]
ManagerOrAdmin = Annotated[User, Depends(get_current_manager_or_admin)]
SuperAdminUser = Annotated[SuperAdmin, Depends(get_current_superadmin)]
DB = Annotated[AsyncSession, Depends(get_db)]
