"""
Notifications API – Versand-Log und Präferenzen.
"""
import uuid
from datetime import datetime, time

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.models.employee import Employee
from app.models.notification import NotificationLog

router = APIRouter(prefix="/notifications", tags=["notifications"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class NotificationLogOut(BaseModel):
    id: uuid.UUID
    employee_id: uuid.UUID | None
    channel: str
    event_type: str
    subject: str | None
    status: str
    sent_at: datetime | None
    error: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationPreferencesUpdate(BaseModel):
    telegram_chat_id: str | None = None
    quiet_hours_start: time | None = None
    quiet_hours_end: time | None = None
    notification_prefs: dict | None = None  # { channels: {email, telegram}, events: {...} }


class NotificationPreferencesOut(BaseModel):
    telegram_chat_id: str | None
    quiet_hours_start: time
    quiet_hours_end: time
    notification_prefs: dict

    model_config = {"from_attributes": True}


# ── Endpunkte ─────────────────────────────────────────────────────────────────

@router.get("/logs", response_model=list[NotificationLogOut])
async def list_notification_logs(
    current_user: CurrentUser,
    db: DB,
    employee_id: uuid.UUID | None = None,
    channel: str | None = None,
    status: str | None = None,
):
    """
    Admin/Manager: alle Logs des Tenants.
    Employee: nur eigene Logs.
    """
    conditions = [NotificationLog.tenant_id == current_user.tenant_id]

    if current_user.role == "employee":
        # Eigene Logs ermitteln
        emp_result = await db.execute(
            select(Employee.id).where(Employee.user_id == current_user.id)
        )
        own_id = emp_result.scalar_one_or_none()
        if own_id is None:
            return []
        conditions.append(NotificationLog.employee_id == own_id)
    else:
        if employee_id:
            conditions.append(NotificationLog.employee_id == employee_id)

    if channel:
        conditions.append(NotificationLog.channel == channel)
    if status:
        conditions.append(NotificationLog.status == status)

    result = await db.execute(
        select(NotificationLog)
        .where(*conditions)
        .order_by(NotificationLog.created_at.desc())
        .limit(200)
    )
    return result.scalars().all()


@router.get("/preferences", response_model=NotificationPreferencesOut)
async def get_preferences(current_user: CurrentUser, db: DB):
    """Gibt die eigenen Notification-Präferenzen zurück."""
    emp_result = await db.execute(
        select(Employee).where(
            Employee.user_id == current_user.id,
            Employee.tenant_id == current_user.tenant_id,
        )
    )
    emp = emp_result.scalar_one_or_none()
    if not emp:
        return NotificationPreferencesOut(
            telegram_chat_id=None,
            quiet_hours_start=time(21, 0),
            quiet_hours_end=time(7, 0),
            notification_prefs={},
        )
    return NotificationPreferencesOut(
        telegram_chat_id=emp.telegram_chat_id,
        quiet_hours_start=emp.quiet_hours_start or time(21, 0),
        quiet_hours_end=emp.quiet_hours_end or time(7, 0),
        notification_prefs=emp.notification_prefs or {},
    )


@router.put("/preferences", response_model=NotificationPreferencesOut)
async def update_preferences(
    payload: NotificationPreferencesUpdate,
    current_user: CurrentUser,
    db: DB,
):
    """Aktualisiert Telegram Chat-ID, Quiet Hours und Kanal-/Event-Präferenzen."""
    emp_result = await db.execute(
        select(Employee).where(
            Employee.user_id == current_user.id,
            Employee.tenant_id == current_user.tenant_id,
        )
    )
    emp = emp_result.scalar_one_or_none()
    if not emp:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Kein Mitarbeiterprofil gefunden")

    if payload.telegram_chat_id is not None:
        emp.telegram_chat_id = payload.telegram_chat_id or None
    if payload.quiet_hours_start is not None:
        emp.quiet_hours_start = payload.quiet_hours_start
    if payload.quiet_hours_end is not None:
        emp.quiet_hours_end = payload.quiet_hours_end
    if payload.notification_prefs is not None:
        emp.notification_prefs = payload.notification_prefs

    await db.commit()
    await db.refresh(emp)
    return NotificationPreferencesOut(
        telegram_chat_id=emp.telegram_chat_id,
        quiet_hours_start=emp.quiet_hours_start or time(21, 0),
        quiet_hours_end=emp.quiet_hours_end or time(7, 0),
        notification_prefs=emp.notification_prefs or {},
    )
