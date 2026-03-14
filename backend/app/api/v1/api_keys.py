"""
API Key Management – CRUD für Tenant-API-Keys.

Keys werden gehasht gespeichert (SHA-256), der Klartext nur beim Anlegen zurückgegeben.
Authentifizierung via X-API-Key Header für externe Clients (n8n, Zapier etc.).
"""
import hashlib
import secrets
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import DB, AdminUser
from app.models.audit import ApiKey

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


class ApiKeyCreate(BaseModel):
    name: str
    scopes: list[str] = ["read"]  # read | write | admin
    expires_at: datetime | None = None


class ApiKeyOut(BaseModel):
    id: uuid.UUID
    name: str
    key_prefix: str  # erste 12 Zeichen des Keys (zur Wiedererkennung)
    scopes: list[str]
    is_active: bool
    expires_at: datetime | None
    created_at: datetime
    last_used_at: datetime | None

    model_config = {"from_attributes": True}


class ApiKeyCreatedOut(ApiKeyOut):
    """Nur beim Erstellen: enthält den vollständigen Key (danach nicht mehr abrufbar)."""
    key: str


@router.get("", response_model=list[ApiKeyOut])
async def list_api_keys(current_user: AdminUser, db: DB):
    """Listet alle API-Keys des Tenants (ohne Klartext-Key)."""
    result = await db.execute(
        select(ApiKey)
        .where(ApiKey.tenant_id == current_user.tenant_id)
        .order_by(ApiKey.created_at.desc())
    )
    keys = result.scalars().all()

    # key_prefix aus key_hash ableiten (erste 12 Zeichen des gespeicherten Prefix-Feldes fehlen
    # im Modell – wir rekonstruieren es aus key_hash[:12] als Platzhalter oder verwenden
    # den tatsächlich gespeicherten key_hash-Wert in gekürzter Form)
    out = []
    for k in keys:
        out.append(ApiKeyOut(
            id=k.id,
            name=k.name,
            key_prefix=k.key_hash[:12] + "…",
            scopes=k.scopes or ["read"],
            is_active=k.is_active,
            expires_at=k.expires_at,
            created_at=k.created_at,
            last_used_at=k.last_used_at,
        ))
    return out


@router.post("", response_model=ApiKeyCreatedOut, status_code=status.HTTP_201_CREATED)
async def create_api_key(payload: ApiKeyCreate, current_user: AdminUser, db: DB):
    """
    Legt einen neuen API-Key an.
    Der vollständige Key wird NUR in der Antwort zurückgegeben und danach nicht mehr angezeigt.
    """
    raw_key = f"vera_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    key_prefix = raw_key[:12]  # "vera_" + 7 Zeichen

    api_key = ApiKey(
        tenant_id=current_user.tenant_id,
        name=payload.name,
        key_hash=key_hash,
        scopes=payload.scopes,
        is_active=True,
        expires_at=payload.expires_at,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)

    return ApiKeyCreatedOut(
        id=api_key.id,
        name=api_key.name,
        key_prefix=key_prefix,
        scopes=api_key.scopes or ["read"],
        is_active=api_key.is_active,
        expires_at=api_key.expires_at,
        created_at=api_key.created_at,
        last_used_at=api_key.last_used_at,
        key=raw_key,
    )


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(key_id: uuid.UUID, current_user: AdminUser, db: DB):
    """Widerruft einen API-Key (löscht ihn)."""
    result = await db.execute(
        select(ApiKey).where(
            ApiKey.id == key_id,
            ApiKey.tenant_id == current_user.tenant_id,
        )
    )
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=404, detail="API-Key nicht gefunden")
    await db.delete(key)
    await db.commit()
