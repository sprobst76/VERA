"""
Notification Service – Telegram + SendGrid E-Mail + Web Push Versand.

Graceful Degradation: Wenn TELEGRAM_BOT_TOKEN, SENDGRID_API_KEY oder
VAPID_PRIVATE_KEY nicht gesetzt sind, wird der Versand übersprungen.
Quiet Hours werden pro Mitarbeiter respektiert (Standard: 21:00–07:00).
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from app.core.config import settings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.models.employee import Employee
    from app.models.shift import Shift
    from app.models.absence import EmployeeAbsence

_BERLIN = ZoneInfo("Europe/Berlin")

EVENT_SHIFT_ASSIGNED   = "shift_assigned"
EVENT_SHIFT_CHANGED    = "shift_changed"
EVENT_SHIFT_REMINDER   = "shift_reminder"
EVENT_ABSENCE_APPROVED = "absence_approved"
EVENT_ABSENCE_REJECTED = "absence_rejected"


def _is_quiet_now(employee: "Employee") -> bool:
    """True wenn die aktuelle Berliner Zeit in den Quiet Hours liegt."""
    from datetime import time as time_type
    now   = datetime.now(_BERLIN).time()
    start = employee.quiet_hours_start or time_type(21, 0)
    end   = employee.quiet_hours_end   or time_type(7, 0)
    # wrap-around (z.B. 21:00–07:00 geht über Mitternacht)
    if start > end:
        return now >= start or now <= end
    return start <= now <= end


class NotificationService:

    def __init__(self, db: "AsyncSession"):
        self.db = db

    async def dispatch(
        self,
        employee: "Employee",
        event_type: str,
        message: str,
        subject: str | None = None,
        tenant_id: uuid.UUID | None = None,
    ) -> None:
        """Sendet via alle konfigurierten Kanäle; loggt Ergebnis in NotificationLog."""
        from app.models.notification import NotificationLog

        tid = tenant_id or employee.tenant_id

        if _is_quiet_now(employee):
            log = NotificationLog(
                tenant_id=tid,
                employee_id=employee.id,
                channel="all",
                event_type=event_type,
                subject=subject,
                body=message,
                status="skipped_quiet_hours",
            )
            self.db.add(log)
            await self.db.commit()
            return

        prefs    = employee.notification_prefs or {}
        channels = prefs.get("channels", {})

        # ── Telegram ──────────────────────────────────────────────────────────
        if channels.get("telegram", False) and employee.telegram_chat_id:
            ok, err = await self._send_telegram(employee.telegram_chat_id, message)
            self.db.add(NotificationLog(
                tenant_id=tid,
                employee_id=employee.id,
                channel="telegram",
                event_type=event_type,
                subject=subject,
                body=message,
                status="sent" if ok else "failed",
                sent_at=datetime.now(timezone.utc) if ok else None,
                error=err,
            ))

        # ── E-Mail ────────────────────────────────────────────────────────────
        if channels.get("email", True) and employee.email:
            ok, err = await self._send_email(
                to=employee.email,
                subject=subject or "VERA – Benachrichtigung",
                body=message,
            )
            self.db.add(NotificationLog(
                tenant_id=tid,
                employee_id=employee.id,
                channel="email",
                event_type=event_type,
                subject=subject,
                body=message,
                status="sent" if ok else "failed",
                sent_at=datetime.now(timezone.utc) if ok else None,
                error=err,
            ))

        # ── Web Push ──────────────────────────────────────────────────────────
        if channels.get("push", False):
            ok, err = await self._send_push(
                employee_id=employee.id,
                title=subject or "VERA",
                body=message,
            )
            self.db.add(NotificationLog(
                tenant_id=tid,
                employee_id=employee.id,
                channel="push",
                event_type=event_type,
                subject=subject,
                body=message,
                status="sent" if ok else "failed",
                sent_at=datetime.now(timezone.utc) if ok else None,
                error=err,
            ))

        await self.db.commit()

    async def _send_telegram(self, chat_id: str, message: str) -> tuple[bool, str | None]:
        token = settings.TELEGRAM_BOT_TOKEN
        if not token:
            return False, "TELEGRAM_BOT_TOKEN nicht konfiguriert"
        try:
            from telegram import Bot
            bot = Bot(token=token)
            async with bot:
                await bot.send_message(chat_id=chat_id, text=message)
            return True, None
        except Exception as e:
            return False, str(e)[:200]

    async def _send_email(self, to: str, subject: str, body: str) -> tuple[bool, str | None]:
        api_key    = settings.SENDGRID_API_KEY
        from_email = settings.SENDGRID_FROM_EMAIL
        if not api_key:
            return False, "SENDGRID_API_KEY nicht konfiguriert"
        if not from_email:
            return False, "SENDGRID_FROM_EMAIL nicht konfiguriert"
        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail
            mail = Mail(
                from_email=from_email,
                to_emails=to,
                subject=subject,
                plain_text_content=body,
            )
            await asyncio.to_thread(SendGridAPIClient(api_key).send, mail)
            return True, None
        except Exception as e:
            return False, str(e)[:200]

    async def _send_push(
        self, employee_id: uuid.UUID, title: str, body: str
    ) -> tuple[bool, str | None]:
        """Sendet Web Push an alle registrierten Browser-Subscriptions des Mitarbeiters."""
        if not settings.VAPID_PRIVATE_KEY:
            return False, "VAPID_PRIVATE_KEY nicht konfiguriert"
        try:
            from pywebpush import webpush, WebPushException
            from sqlalchemy import select as sa_select
            from app.models.push_subscription import PushSubscription

            result = await self.db.execute(
                sa_select(PushSubscription).where(
                    PushSubscription.employee_id == employee_id
                )
            )
            subs = result.scalars().all()
            if not subs:
                return False, "Keine Push-Subscriptions vorhanden"

            payload = json.dumps({"title": title, "body": body, "url": "/"})
            sent_any = False
            last_err: str | None = None

            for sub in subs:
                try:
                    await asyncio.to_thread(
                        webpush,
                        subscription_info={
                            "endpoint": sub.endpoint,
                            "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                        },
                        data=payload,
                        vapid_private_key=settings.VAPID_PRIVATE_KEY,
                        vapid_claims={"sub": settings.VAPID_CLAIMS_SUB},
                    )
                    sent_any = True
                except WebPushException as e:
                    last_err = str(e)[:200]
                    # 410 Gone → Subscription abgelaufen, aus DB entfernen
                    if e.response is not None and e.response.status_code == 410:
                        await self.db.delete(sub)
                        await self.db.flush()

            return sent_any, None if sent_any else last_err
        except Exception as e:
            return False, str(e)[:200]


# ── Convenience-Funktionen für API-Endpunkte ────────────────────────────────

_WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


async def notify_shift_assigned(
    shift: "Shift",
    employee: "Employee",
    db: "AsyncSession",
) -> None:
    """Benachrichtigung wenn ein Dienst zugewiesen wird."""
    prefs  = employee.notification_prefs or {}
    events = prefs.get("events", {})
    if not events.get("shift_assigned", True):
        return

    wday = _WEEKDAYS[shift.date.weekday()]
    msg = (
        f"Hallo {employee.first_name},\n\n"
        f"Du wurdest für folgenden Dienst eingeplant:\n"
        f"Datum:  {wday}, {shift.date.strftime('%d.%m.%Y')}\n"
        f"Zeit:   {shift.start_time.strftime('%H:%M')} – {shift.end_time.strftime('%H:%M')} Uhr\n"
    )
    if shift.location:
        msg += f"Ort:    {shift.location}\n"
    msg += "\nVERA Schichtplanner"

    svc = NotificationService(db)
    try:
        await svc.dispatch(
            employee=employee,
            event_type=EVENT_SHIFT_ASSIGNED,
            message=msg,
            subject=f"Neuer Dienst: {shift.date.strftime('%d.%m.%Y')}",
            tenant_id=shift.tenant_id,
        )
    except Exception:
        pass  # Notification-Fehler nie die API-Response blockieren


async def notify_shift_changed(
    shift: "Shift",
    employee: "Employee",
    changed_fields: list[str],
    db: "AsyncSession",
) -> None:
    """Benachrichtigung wenn Zeit oder Ort eines Dienstes geändert wird."""
    prefs  = employee.notification_prefs or {}
    events = prefs.get("events", {})
    if not events.get("shift_changed", True):
        return

    wday    = _WEEKDAYS[shift.date.weekday()]
    changes = ", ".join(changed_fields)
    msg = (
        f"Hallo {employee.first_name},\n\n"
        f"Dein Dienst am {wday}, {shift.date.strftime('%d.%m.%Y')} "
        f"wurde geändert ({changes}):\n"
        f"Zeit:   {shift.start_time.strftime('%H:%M')} – {shift.end_time.strftime('%H:%M')} Uhr\n"
    )
    if shift.location:
        msg += f"Ort:    {shift.location}\n"
    msg += "\nVERA Schichtplanner"

    svc = NotificationService(db)
    try:
        await svc.dispatch(
            employee=employee,
            event_type=EVENT_SHIFT_CHANGED,
            message=msg,
            subject=f"Dienständerung: {shift.date.strftime('%d.%m.%Y')}",
            tenant_id=shift.tenant_id,
        )
    except Exception:
        pass


async def notify_absence_decision(
    absence: "EmployeeAbsence",
    employee: "Employee",
    decision: str,
    db: "AsyncSession",
) -> None:
    """Benachrichtigung wenn ein Abwesenheitsantrag genehmigt oder abgelehnt wird."""
    prefs  = employee.notification_prefs or {}
    events = prefs.get("events", {})
    key = EVENT_ABSENCE_APPROVED if decision == "approved" else EVENT_ABSENCE_REJECTED
    if not events.get(key, True):
        return

    label = "genehmigt ✓" if decision == "approved" else "abgelehnt ✗"
    msg = (
        f"Hallo {employee.first_name},\n\n"
        f"Dein Abwesenheitsantrag wurde {label}:\n"
        f"Zeitraum: {absence.start_date.strftime('%d.%m.%Y')} – "
        f"{absence.end_date.strftime('%d.%m.%Y')}\n"
        f"Art:      {absence.type}\n"
    )
    if absence.notes:
        msg += f"Notiz:    {absence.notes}\n"
    msg += "\nVERA Schichtplanner"

    svc = NotificationService(db)
    try:
        await svc.dispatch(
            employee=employee,
            event_type=key,
            message=msg,
            subject=f"Abwesenheitsantrag {label}: {absence.start_date.strftime('%d.%m.%Y')}",
            tenant_id=absence.tenant_id,
        )
    except Exception:
        pass
