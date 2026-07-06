import hashlib
from datetime import datetime, timezone
from typing import Annotated
import uuid

from fastapi import Depends, HTTPException, status, Header, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User
from app.models.employee import Employee
from app.models.superadmin import SuperAdmin
from app.models.audit import ApiKey
from app.schemas.auth import TokenData

# auto_error=False: erlaubt Requests ohne Authorization-Header (API-Key-Fallback)
security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
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
                # Scope enforcement (D-10, D-11). Missing scopes default to
                # least-privilege read-only, NOT admin (D-14 superseded —
                # see migration l6m7n8o9p0q1 for the backfill of legacy keys).
                scopes = ak.scopes if ak.scopes else ["read"]
                if isinstance(scopes, str):
                    scopes = [scopes]
                is_write_method = request.method.upper() in ("POST", "PUT", "PATCH", "DELETE")
                if is_write_method and "write" not in scopes and "admin" not in scopes:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="API-Key hat keine Schreibberechtigung",
                    )
                # Marks this request as API-key-authenticated so admin-gated
                # endpoints can additionally require an explicit "admin" scope
                # (a write-scoped key must not inherit the resolved user's
                # admin role for tenant-administration endpoints).
                request.state.auth_via_api_key = True
                request.state.api_key_scopes = scopes
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

    # token_version check (D-06) — treat missing ver as 0 for pre-deploy compat
    token_ver = payload.get("ver", 0)
    if token_ver != user.token_version:
        raise credentials_exception

    return user


async def get_current_active_admin(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if current_user.role not in ("admin",):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    # An API key resolves to a real admin user of the tenant (see
    # get_current_user), which would otherwise let a mere "write"-scoped
    # integration key (e.g. Shiftjuggler sync) reach tenant-administration
    # endpoints (api-keys, admin-settings, ...). Require an explicit
    # "admin" scope for those when auth came via API key.
    if getattr(request.state, "auth_via_api_key", False):
        if "admin" not in getattr(request.state, "api_key_scopes", []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="API-Key benötigt admin-Scope für diesen Endpoint",
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


async def get_own_employee_id(current_user: User, db: AsyncSession) -> uuid.UUID | None:
    """Employee.id linked to this User via user_id, or None if unlinked.

    Was duplicated as an inline query in payroll.py (3x), compliance.py,
    reports.py, and shifts.py (as a private _own_employee_id) — the same
    ownership-scoping lookup copy-pasted per router. Centralized here so
    a future change (e.g. caching, soft-delete handling) only needs one
    place to touch.
    """
    result = await db.execute(select(Employee.id).where(Employee.user_id == current_user.id))
    return result.scalar_one_or_none()


CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(get_current_active_admin)]
ManagerOrAdmin = Annotated[User, Depends(get_current_manager_or_admin)]
ParentViewerOrHigher = Annotated[User, Depends(get_parent_viewer_or_higher)]
SuperAdminUser = Annotated[SuperAdmin, Depends(get_current_superadmin)]
DB = Annotated[AsyncSession, Depends(get_db)]
