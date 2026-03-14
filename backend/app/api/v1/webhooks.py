"""
Webhooks API – CRUD für Webhook-Konfigurationen.

Events: shift.created, shift.updated, shift.cancelled,
        absence.approved, payroll.created,
        compliance.violation, care_absence.created
"""
import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, HttpUrl
from sqlalchemy import select

from app.api.deps import DB, AdminUser, CurrentUser
from app.models.audit import Webhook

WEBHOOK_EVENTS = [
    "shift.created",
    "shift.updated",
    "shift.cancelled",
    "absence.approved",
    "payroll.created",
    "compliance.violation",
    "care_absence.created",
]

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


class WebhookCreate(BaseModel):
    name: str
    url: str
    events: list[str]
    secret: str | None = None


class WebhookUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    events: list[str] | None = None
    secret: str | None = None
    is_active: bool | None = None


class WebhookOut(BaseModel):
    id: uuid.UUID
    name: str
    url: str
    events: list[str]
    is_active: bool
    last_triggered: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("", response_model=list[WebhookOut])
async def list_webhooks(current_user: AdminUser, db: DB):
    result = await db.execute(
        select(Webhook).where(Webhook.tenant_id == current_user.tenant_id)
        .order_by(Webhook.created_at.desc())
    )
    return result.scalars().all()


@router.post("", response_model=WebhookOut, status_code=status.HTTP_201_CREATED)
async def create_webhook(payload: WebhookCreate, current_user: AdminUser, db: DB):
    unknown = set(payload.events) - set(WEBHOOK_EVENTS)
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unbekannte Events: {', '.join(unknown)}")
    wh = Webhook(
        tenant_id=current_user.tenant_id,
        name=payload.name,
        url=payload.url,
        events=payload.events,
        secret=payload.secret,
    )
    db.add(wh)
    await db.commit()
    await db.refresh(wh)
    return wh


@router.put("/{webhook_id}", response_model=WebhookOut)
async def update_webhook(webhook_id: uuid.UUID, payload: WebhookUpdate, current_user: AdminUser, db: DB):
    result = await db.execute(
        select(Webhook).where(Webhook.id == webhook_id, Webhook.tenant_id == current_user.tenant_id)
    )
    wh = result.scalar_one_or_none()
    if not wh:
        raise HTTPException(status_code=404, detail="Webhook nicht gefunden")
    if payload.events is not None:
        unknown = set(payload.events) - set(WEBHOOK_EVENTS)
        if unknown:
            raise HTTPException(status_code=422, detail=f"Unbekannte Events: {', '.join(unknown)}")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(wh, field, value)
    await db.commit()
    await db.refresh(wh)
    return wh


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(webhook_id: uuid.UUID, current_user: AdminUser, db: DB):
    result = await db.execute(
        select(Webhook).where(Webhook.id == webhook_id, Webhook.tenant_id == current_user.tenant_id)
    )
    wh = result.scalar_one_or_none()
    if not wh:
        raise HTTPException(status_code=404, detail="Webhook nicht gefunden")
    await db.delete(wh)
    await db.commit()


@router.post("/{webhook_id}/test", response_model=dict)
async def test_webhook(webhook_id: uuid.UUID, current_user: AdminUser, db: DB):
    """Sendet einen Test-Ping an die Webhook-URL."""
    result = await db.execute(
        select(Webhook).where(Webhook.id == webhook_id, Webhook.tenant_id == current_user.tenant_id)
    )
    wh = result.scalar_one_or_none()
    if not wh:
        raise HTTPException(status_code=404, detail="Webhook nicht gefunden")

    payload = {
        "event": "test.ping",
        "tenant_id": str(current_user.tenant_id),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": {"message": "VERA Webhook Test – alles funktioniert!"},
    }
    ok, msg = await _dispatch_single(wh, payload)
    return {"success": ok, "message": msg}


@router.get("/events", response_model=list[str])
async def list_events(current_user: CurrentUser):
    """Gibt alle verfügbaren Webhook-Events zurück."""
    return WEBHOOK_EVENTS


# ── Dispatch-Funktionen ────────────────────────────────────────────────────────

async def dispatch_event(db, tenant_id: uuid.UUID, event: str, data: dict):
    """
    Sendet das Event an alle aktiven Webhooks des Tenants, die auf dieses Event abonniert sind.
    Fire-and-forget: Fehler werden geloggt aber nicht weitergeworfen.
    """
    result = await db.execute(
        select(Webhook).where(
            Webhook.tenant_id == tenant_id,
            Webhook.is_active == True,
        )
    )
    webhooks = result.scalars().all()

    payload = {
        "event": event,
        "tenant_id": str(tenant_id),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }

    for wh in webhooks:
        if event not in wh.events:
            continue
        ok, _ = await _dispatch_single(wh, payload)
        if ok:
            wh.last_triggered = datetime.now(timezone.utc)

    if webhooks:
        await db.commit()


async def _dispatch_single(wh: Webhook, payload: dict) -> tuple[bool, str]:
    """HTTP POST an eine einzelne Webhook-URL. Gibt (success, message) zurück."""
    body = json.dumps(payload, default=str).encode()
    headers = {"Content-Type": "application/json", "User-Agent": "VERA-Webhook/1.0"}

    if wh.secret:
        sig = hmac.new(wh.secret.encode(), body, hashlib.sha256).hexdigest()  # type: ignore[attr-defined]
        headers["X-VERA-Signature"] = f"sha256={sig}"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(wh.url, content=body, headers=headers)
        if resp.status_code < 300:
            return True, f"HTTP {resp.status_code}"
        return False, f"HTTP {resp.status_code}: {resp.text[:200]}"
    except Exception as exc:
        return False, str(exc)
