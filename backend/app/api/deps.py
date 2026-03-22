import hashlib
from datetime import datetime, timezone
from typing import Annotated
import uuid

from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User
from app.models.superadmin import SuperAdmin
from app.models.audit import ApiKey
from app.schemas.auth import TokenData

# auto_error=False: erlaubt Requests ohne Authorization-Header (API-Key-Fallback)
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> User:
    """
    Authentifizierung via:
    1. X-API-Key Header (SHA-256-Hash gegen api_keys-Tabelle)
    2. Authorization: Bearer <JWT> (Fallback)
    """
    # ── 1. API-Key-Auth ───────────────────────────────────────────────────────
    if x_api_key:
        key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()
        ak_result = await db.execute(
            select(ApiKey).where(
                ApiKey.key_hash == key_hash,
                ApiKey.is_active == True,  # noqa: E712
            )
        )
        ak = ak_result.scalar_one_or_none()

        if ak and (ak.expires_at is None or ak.expires_at > datetime.now(timezone.utc)):
            # Admin-User des Tenants als Kontext zurückgeben
            user_result = await db.execute(
                select(User).where(
                    User.tenant_id == ak.tenant_id,
                    User.role == "admin",
                    User.is_active == True,  # noqa: E712
                ).limit(1)
            )
            user = user_result.scalar_one_or_none()
            if user:
                # last_used_at aktualisieren (fire-and-forget, kein await nötig)
                ak.last_used_at = datetime.now(timezone.utc)
                await db.commit()
                return user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ungültiger oder abgelaufener API-Key",
        )

    # ── 2. JWT Bearer Auth ────────────────────────────────────────────────────
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not credentials:
        raise credentials_exception

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


async def get_parent_viewer_or_higher(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Allows admin, manager, and parent_viewer roles (read-only portal access)."""
    if current_user.role not in ("admin", "manager", "parent_viewer"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    return current_user


def get_token_data(user: User) -> TokenData:
    return TokenData(
        user_id=user.id,
        tenant_id=user.tenant_id,
        role=user.role,
    )


async def get_current_superadmin(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SuperAdmin:
    exc = HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="SuperAdmin-Berechtigung erforderlich",
    )
    if not credentials:
        raise exc
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
ParentViewerOrHigher = Annotated[User, Depends(get_parent_viewer_or_higher)]
SuperAdminUser = Annotated[SuperAdmin, Depends(get_current_superadmin)]
DB = Annotated[AsyncSession, Depends(get_db)]
