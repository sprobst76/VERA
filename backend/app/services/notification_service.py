"""
Notification Service – Telegram + SMTP E-Mail + Web Push Versand.

Graceful Degradation: Wenn TELEGRAM_BOT_TOKEN, SMTP_HOST/USER/PASSWORD oder
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
    from app.models.shift_swap import ShiftSwapOffer

_BERLIN = ZoneInfo("Europe/Berlin")

EVENT_SHIFT_ASSIGNED    = "shift_assigned"
EVENT_SHIFT_CHANGED     = "shift_changed"
EVENT_SHIFT_REMINDER    = "shift_reminder"
EVENT_ABSENCE_APPROVED  = "absence_approved"
EVENT_ABSENCE_REJECTED  = "absence_rejected"
EVENT_POOL_SHIFT_OPEN   = "pool_shift_open"
EVENT_SHIFT_CLAIMED     = "shift_claimed"
EVENT_MINIJOB_LIMIT_80  = "minijob_limit_80"
EVENT_MINIJOB_LIMIT_95  = "minijob_limit_95"
EVENT_AVAILABILITY_CHANGED = "availability_changed"
EVENT_SWAP_OFFER_OPEN        = "swap_offer_open"
EVENT_SWAP_OFFER_CREATED     = "swap_offer_created"
EVENT_SWAP_ACCEPTED          = "swap_accepted"
EVENT_SWAP_PENDING_APPROVAL  = "swap_pending_approval"
EVENT_SWAP_APPROVED          = "swap_approved"
EVENT_SWAP_DENIED            = "swap_denied"
EVENT_SWAP_CANCELLED         = "swap_cancelled"


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

        # SMTP-Config aus Tenant-Settings laden (Fallback auf ENV-Vars)
        smtp_cfg = await self._load_smtp_cfg(tid)

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

        # Alle aktiven Kanäle parallel versenden
        tasks: list[tuple[str, any]] = []
        if channels.get("telegram", False) and employee.telegram_chat_id:
            tasks.append(("telegram", self._send_telegram(employee.telegram_chat_id, message)))
        if channels.get("email", True) and employee.email:
            tasks.append(("email", self._send_email(
                to=employee.email,
                subject=subject or "VERA – Benachrichtigung",
                body=message,
                smtp_cfg=smtp_cfg,
            )))
        if channels.get("push", False):
            tasks.append(("push", self._send_push(
                employee_id=employee.id,
                title=subject or "VERA",
                body=message,
            )))

        if tasks:
            channel_names = [t[0] for t in tasks]
            results = await asyncio.gather(*[t[1] for t in tasks], return_exceptions=True)
            for channel, result in zip(channel_names, results):
                ok, err = result if not isinstance(result, Exception) else (False, str(result)[:200])
                self.db.add(NotificationLog(
                    tenant_id=tid,
                    employee_id=employee.id,
                    channel=channel,
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
            async with asyncio.timeout(10):
                async with bot:
                    await bot.send_message(chat_id=chat_id, text=message)
            return True, None
        except TimeoutError:
            return False, "Telegram-Timeout (10s)"
        except Exception as e:
            return False, str(e)[:200]

    async def _load_smtp_cfg(self, tenant_id: uuid.UUID) -> dict:
        """Lädt SMTP-Config aus Tenant.settings; fällt auf ENV-Vars zurück."""
        try:
            from sqlalchemy import select as sa_select
            from app.models.tenant import Tenant
            result = await self.db.execute(
                sa_select(Tenant).where(Tenant.id == tenant_id)
            )
            tenant = result.scalar_one_or_none()
            if tenant:
                cfg = (tenant.settings or {}).get("smtp", {})
                if cfg.get("host") and cfg.get("user") and cfg.get("password"):
                    return cfg
        except Exception:
            pass
        # ENV-Var Fallback
        return {
            "host":       settings.SMTP_HOST,
            "port":       settings.SMTP_PORT,
            "user":       settings.SMTP_USER,
            "password":   settings.SMTP_PASSWORD,
            "from_email": settings.SMTP_FROM_EMAIL,
        }

    async def _send_email(
        self, to: str, subject: str, body: str, smtp_cfg: dict | None = None
    ) -> tuple[bool, str | None]:
        cfg       = smtp_cfg or {}
        host      = cfg.get("host") or settings.SMTP_HOST
        port      = int(cfg.get("port") or settings.SMTP_PORT)
        user      = cfg.get("user") or settings.SMTP_USER
        password  = cfg.get("password") or settings.SMTP_PASSWORD
        from_addr = cfg.get("from_email") or settings.SMTP_FROM_EMAIL or user
        if not host or not user or not password:
            return False, "SMTP nicht konfiguriert"
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            def _send() -> None:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"]    = from_addr
                msg["To"]      = to
                msg.attach(MIMEText(body, "plain", "utf-8"))
                with smtplib.SMTP(host, port) as smtp:
                    smtp.ehlo()
                    smtp.starttls()
                    smtp.login(user, password)
                    smtp.sendmail(from_addr, [to], msg.as_string())

            await asyncio.wait_for(asyncio.to_thread(_send), timeout=15)
            return True, None
        except TimeoutError:
            return False, "SMTP-Timeout (15s)"
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


async def notify_pool_shift_open(
    shift: "Shift",
    db: "AsyncSession",
) -> None:
    """Benachrichtigt alle aktiven Mitarbeiter des Tenants über einen offenen Dienst."""
    from sqlalchemy import select
    from app.models.employee import Employee

    result = await db.execute(
        select(Employee).where(
            Employee.tenant_id == shift.tenant_id,
            Employee.is_active == True,
        )
    )
    employees = result.scalars().all()

    wday = _WEEKDAYS[shift.date.weekday()]
    svc  = NotificationService(db)

    for emp in employees:
        prefs  = emp.notification_prefs or {}
        events = prefs.get("events", {})
        if not events.get(EVENT_POOL_SHIFT_OPEN, True):
            continue

        msg = (
            f"Hallo {emp.first_name},\n\n"
            f"Es gibt einen offenen Dienst, der noch besetzt werden muss:\n"
            f"Datum: {wday}, {shift.date.strftime('%d.%m.%Y')}\n"
            f"Zeit:  {shift.start_time.strftime('%H:%M')} – {shift.end_time.strftime('%H:%M')} Uhr\n"
        )
        if shift.location:
            msg += f"Ort:   {shift.location}\n"
        msg += "\nMelde dich in VERA an, um den Dienst anzunehmen.\nVERA Schichtplanner"

        try:
            await svc.dispatch(
                employee=emp,
                event_type=EVENT_POOL_SHIFT_OPEN,
                message=msg,
                subject=f"Offener Dienst: {shift.date.strftime('%d.%m.%Y')}",
                tenant_id=shift.tenant_id,
            )
        except Exception:
            pass


async def notify_shift_claimed(
    shift: "Shift",
    claiming_employee: "Employee",
    db: "AsyncSession",
) -> None:
    """Benachrichtigt Admin/Manager-Mitarbeiter wenn ein Dienst angenommen wurde."""
    from sqlalchemy import select
    from app.models.employee import Employee
    from app.models.user import User

    # Alle Admin/Manager-User des Tenants holen, die ein Employee-Profil haben
    result = await db.execute(
        select(Employee).where(
            Employee.tenant_id == shift.tenant_id,
            Employee.is_active == True,
            Employee.user_id.isnot(None),
        )
    )
    candidates = result.scalars().all()

    # Filtere auf admin/manager-Rollen via User
    user_ids = [e.user_id for e in candidates if e.id != claiming_employee.id]
    if not user_ids:
        return

    user_result = await db.execute(
        select(User).where(
            User.id.in_(user_ids),
            User.role.in_(("admin", "manager")),
            User.is_active == True,
        )
    )
    admin_user_ids = {u.id for u in user_result.scalars().all()}

    wday = _WEEKDAYS[shift.date.weekday()]
    svc  = NotificationService(db)

    for emp in candidates:
        if emp.user_id not in admin_user_ids:
            continue
        msg = (
            f"Hallo {emp.first_name},\n\n"
            f"{claiming_employee.first_name} {claiming_employee.last_name} "
            f"hat folgenden offenen Dienst angenommen:\n"
            f"Datum: {wday}, {shift.date.strftime('%d.%m.%Y')}\n"
            f"Zeit:  {shift.start_time.strftime('%H:%M')} – {shift.end_time.strftime('%H:%M')} Uhr\n"
            f"\nVERA Schichtplanner"
        )
        try:
            await svc.dispatch(
                employee=emp,
                event_type=EVENT_SHIFT_ASSIGNED,
                message=msg,
                subject=f"Dienst angenommen: {shift.date.strftime('%d.%m.%Y')}",
                tenant_id=shift.tenant_id,
            )
        except Exception:
            pass


async def notify_minijob_limit(
    employee: "Employee",
    ytd_gross: float,
    annual_limit: float,
    db: "AsyncSession",
) -> None:
    """Benachrichtigt bei 80% oder 95% der Minijob-Jahresgrenze."""
    ratio = ytd_gross / annual_limit if annual_limit > 0 else 0

    if ratio >= 0.95:
        event_type = EVENT_MINIJOB_LIMIT_95
        level = "95%"
        emoji = "🔴"
    elif ratio >= 0.80:
        event_type = EVENT_MINIJOB_LIMIT_80
        level = "80%"
        emoji = "🟡"
    else:
        return

    prefs  = employee.notification_prefs or {}
    events = prefs.get("events", {})
    if not events.get(event_type, True):
        return

    msg = (
        f"Hallo {employee.first_name},\n\n"
        f"{emoji} Minijob-Warnung: {level} der Jahresgrenze erreicht\n"
        f"Aktuell:  {ytd_gross:.2f} € von {annual_limit:.2f} € ({ratio*100:.1f}%)\n"
        f"Verbleibend: {annual_limit - ytd_gross:.2f} €\n"
        f"\nBitte beachte die gesetzlichen Minijob-Grenzen.\nVERA Schichtplanner"
    )
    svc = NotificationService(db)
    try:
        await svc.dispatch(
            employee=employee,
            event_type=event_type,
            message=msg,
            subject=f"Minijob-Warnung {level}: {ytd_gross:.2f} € / {annual_limit:.2f} €",
            tenant_id=employee.tenant_id,
        )
    except Exception:
        pass


def _describe_availability_changes(old_prefs: dict | None, new_prefs: dict | None) -> list[str]:
    """Baut eine Liste menschenlesbarer Zeilen für geänderte Wochentage (Keys '0'-'6')."""
    old_prefs = old_prefs or {}
    new_prefs = new_prefs or {}
    lines: list[str] = []
    for key in sorted(set(old_prefs) | set(new_prefs), key=lambda k: int(k)):
        old_day = old_prefs.get(key, {})
        new_day = new_prefs.get(key, {})
        if old_day == new_day:
            continue
        wday = _WEEKDAYS[int(key)]
        if not new_day.get("available", True):
            lines.append(f"{wday}: nicht mehr verfügbar")
        elif not old_day.get("available", True):
            lines.append(
                f"{wday}: jetzt verfügbar ({new_day.get('from_time', '')}–{new_day.get('to_time', '')})"
            )
        else:
            lines.append(
                f"{wday}: {old_day.get('from_time', '')}–{old_day.get('to_time', '')} "
                f"→ {new_day.get('from_time', '')}–{new_day.get('to_time', '')}"
            )
    return lines


async def notify_availability_changed(
    employee: "Employee",
    old_prefs: dict | None,
    new_prefs: dict | None,
    db: "AsyncSession",
) -> None:
    """Benachrichtigt Admin/Manager wenn ein Mitarbeiter seine Verfügbarkeiten ändert."""
    from sqlalchemy import select
    from app.models.employee import Employee as EmployeeModel
    from app.models.user import User

    changes = _describe_availability_changes(old_prefs, new_prefs)
    if not changes:
        return

    result = await db.execute(
        select(EmployeeModel).where(
            EmployeeModel.tenant_id == employee.tenant_id,
            EmployeeModel.is_active == True,
            EmployeeModel.user_id.isnot(None),
            EmployeeModel.id != employee.id,
        )
    )
    candidates = result.scalars().all()
    if not candidates:
        return

    user_result = await db.execute(
        select(User).where(
            User.id.in_([e.user_id for e in candidates]),
            User.role.in_(("admin", "manager")),
            User.is_active == True,
        )
    )
    admin_user_ids = {u.id for u in user_result.scalars().all()}

    msg = (
        f"hat die Verfügbarkeiten geändert:\n\n"
        + "\n".join(f"- {line}" for line in changes)
        + "\n\nVERA Schichtplanner"
    )
    svc = NotificationService(db)
    for emp in candidates:
        if emp.user_id not in admin_user_ids:
            continue
        prefs  = emp.notification_prefs or {}
        events = prefs.get("events", {})
        if not events.get(EVENT_AVAILABILITY_CHANGED, True):
            continue
        try:
            await svc.dispatch(
                employee=emp,
                event_type=EVENT_AVAILABILITY_CHANGED,
                message=f"Hallo {emp.first_name},\n\n{employee.first_name} {employee.last_name} {msg}",
                subject=f"Verfügbarkeit geändert: {employee.first_name} {employee.last_name}",
                tenant_id=employee.tenant_id,
            )
        except Exception:
            pass


# ── Schichttausch (Dienst-Abgabe) ────────────────────────────────────────────

def _shift_line(shift: "Shift") -> str:
    wday = _WEEKDAYS[shift.date.weekday()]
    line = (
        f"Datum:  {wday}, {shift.date.strftime('%d.%m.%Y')}\n"
        f"Zeit:   {shift.start_time.strftime('%H:%M')} – {shift.end_time.strftime('%H:%M')} Uhr\n"
    )
    if shift.location:
        line += f"Ort:    {shift.location}\n"
    return line


async def _get_admin_manager_employees(tenant_id, exclude_employee_id, db) -> list["Employee"]:
    """Liefert die Employee-Profile aller aktiven Admin/Manager-User des Tenants."""
    from sqlalchemy import select
    from app.models.employee import Employee
    from app.models.user import User

    result = await db.execute(
        select(Employee).where(
            Employee.tenant_id == tenant_id,
            Employee.is_active == True,
            Employee.user_id.isnot(None),
        )
    )
    candidates = [e for e in result.scalars().all() if e.id != exclude_employee_id]
    if not candidates:
        return []
    user_result = await db.execute(
        select(User).where(
            User.id.in_([e.user_id for e in candidates]),
            User.role.in_(("admin", "manager")),
            User.is_active == True,
        )
    )
    admin_user_ids = {u.id for u in user_result.scalars().all()}
    return [e for e in candidates if e.user_id in admin_user_ids]


async def notify_swap_offer_open(
    offer: "ShiftSwapOffer", shift: "Shift", offering_employee: "Employee", db: "AsyncSession"
) -> None:
    """Benachrichtigt alle anderen aktiven Mitarbeiter über einen neu angebotenen Dienst."""
    from sqlalchemy import select
    from app.models.employee import Employee

    result = await db.execute(
        select(Employee).where(
            Employee.tenant_id == shift.tenant_id,
            Employee.is_active == True,
            Employee.id != offering_employee.id,
        )
    )
    svc = NotificationService(db)
    for emp in result.scalars().all():
        prefs  = emp.notification_prefs or {}
        events = prefs.get("events", {})
        if not events.get(EVENT_SWAP_OFFER_OPEN, True):
            continue
        msg = (
            f"Hallo {emp.first_name},\n\n"
            f"{offering_employee.first_name} {offering_employee.last_name} bietet folgenden "
            f"Dienst zur Übernahme an:\n{_shift_line(shift)}"
        )
        if offer.note:
            msg += f"Notiz:  {offer.note}\n"
        msg += "\nMelde dich in VERA an, um den Dienst zu übernehmen.\nVERA Schichtplanner"
        try:
            await svc.dispatch(
                employee=emp, event_type=EVENT_SWAP_OFFER_OPEN, message=msg,
                subject=f"Dienst zum Tausch angeboten: {shift.date.strftime('%d.%m.%Y')}",
                tenant_id=shift.tenant_id,
            )
        except Exception:
            pass


async def notify_swap_offer_created(
    offer: "ShiftSwapOffer", shift: "Shift", offering_employee: "Employee", db: "AsyncSession"
) -> None:
    """Info an Admin/Manager: ein neues Tauschangebot wurde erstellt."""
    svc = NotificationService(db)
    for emp in await _get_admin_manager_employees(shift.tenant_id, offering_employee.id, db):
        prefs  = emp.notification_prefs or {}
        events = prefs.get("events", {})
        if not events.get(EVENT_SWAP_OFFER_CREATED, True):
            continue
        msg = (
            f"Hallo {emp.first_name},\n\n"
            f"{offering_employee.first_name} {offering_employee.last_name} hat folgenden Dienst "
            f"zur Übernahme angeboten:\n{_shift_line(shift)}\nVERA Schichtplanner"
        )
        try:
            await svc.dispatch(
                employee=emp, event_type=EVENT_SWAP_OFFER_CREATED, message=msg,
                subject=f"Neues Tauschangebot von {offering_employee.first_name} {offering_employee.last_name}",
                tenant_id=shift.tenant_id,
            )
        except Exception:
            pass


async def notify_swap_accepted(
    offer: "ShiftSwapOffer", shift: "Shift", offering_employee: "Employee",
    accepting_employee: "Employee", db: "AsyncSession"
) -> None:
    """Dienst sofort wirksam übernommen: Anbieter + Admin/Manager informieren."""
    svc = NotificationService(db)

    prefs  = offering_employee.notification_prefs or {}
    events = prefs.get("events", {})
    if events.get(EVENT_SWAP_ACCEPTED, True):
        msg = (
            f"Hallo {offering_employee.first_name},\n\n"
            f"{accepting_employee.first_name} {accepting_employee.last_name} hat deinen Dienst "
            f"übernommen:\n{_shift_line(shift)}\nVERA Schichtplanner"
        )
        try:
            await svc.dispatch(
                employee=offering_employee, event_type=EVENT_SWAP_ACCEPTED, message=msg,
                subject=f"Dienst übernommen: {shift.date.strftime('%d.%m.%Y')}",
                tenant_id=shift.tenant_id,
            )
        except Exception:
            pass

    for emp in await _get_admin_manager_employees(shift.tenant_id, None, db):
        a_events = (emp.notification_prefs or {}).get("events", {})
        if not a_events.get(EVENT_SWAP_ACCEPTED, True):
            continue
        msg = (
            f"Hallo {emp.first_name},\n\n"
            f"{accepting_employee.first_name} {accepting_employee.last_name} hat den Dienst von "
            f"{offering_employee.first_name} {offering_employee.last_name} übernommen:\n"
            f"{_shift_line(shift)}\nVERA Schichtplanner"
        )
        try:
            await svc.dispatch(
                employee=emp, event_type=EVENT_SWAP_ACCEPTED, message=msg,
                subject=f"Dienst getauscht: {shift.date.strftime('%d.%m.%Y')}",
                tenant_id=shift.tenant_id,
            )
        except Exception:
            pass


async def notify_swap_pending_approval(offer: "ShiftSwapOffer", shift: "Shift", db: "AsyncSession") -> None:
    """Admin/Manager: ein Tausch wartet auf Genehmigung (bereits bestätigter Dienst)."""
    svc = NotificationService(db)
    for emp in await _get_admin_manager_employees(shift.tenant_id, None, db):
        events = (emp.notification_prefs or {}).get("events", {})
        if not events.get(EVENT_SWAP_PENDING_APPROVAL, True):
            continue
        msg = (
            f"Hallo {emp.first_name},\n\n"
            f"Ein Tauschangebot für folgenden (bereits bestätigten) Dienst wartet auf deine "
            f"Genehmigung:\n{_shift_line(shift)}\nVERA Schichtplanner"
        )
        try:
            await svc.dispatch(
                employee=emp, event_type=EVENT_SWAP_PENDING_APPROVAL, message=msg,
                subject=f"Tausch wartet auf Genehmigung: {shift.date.strftime('%d.%m.%Y')}",
                tenant_id=shift.tenant_id,
            )
        except Exception:
            pass


async def notify_swap_approved(
    offer: "ShiftSwapOffer", shift: "Shift", offering_employee: "Employee",
    accepting_employee: "Employee", db: "AsyncSession"
) -> None:
    """Admin hat den Tausch genehmigt: Anbieter + Übernehmer informieren."""
    svc = NotificationService(db)
    for emp in (offering_employee, accepting_employee):
        events = (emp.notification_prefs or {}).get("events", {})
        if not events.get(EVENT_SWAP_APPROVED, True):
            continue
        msg = (
            f"Hallo {emp.first_name},\n\n"
            f"Der Tausch für folgenden Dienst wurde genehmigt:\n{_shift_line(shift)}\nVERA Schichtplanner"
        )
        try:
            await svc.dispatch(
                employee=emp, event_type=EVENT_SWAP_APPROVED, message=msg,
                subject=f"Tausch genehmigt: {shift.date.strftime('%d.%m.%Y')}",
                tenant_id=shift.tenant_id,
            )
        except Exception:
            pass


async def notify_swap_denied(
    offer: "ShiftSwapOffer", shift: "Shift", offering_employee: "Employee",
    accepting_employee: "Employee", db: "AsyncSession"
) -> None:
    """Admin hat den Tausch abgelehnt: Anbieter + Übernehmer informieren (nicht abschaltbar)."""
    svc = NotificationService(db)
    reason = f"\nGrund: {offer.review_note}\n" if offer.review_note else ""
    for emp in (offering_employee, accepting_employee):
        if not emp:
            continue
        msg = (
            f"Hallo {emp.first_name},\n\n"
            f"Der Tausch für folgenden Dienst wurde abgelehnt:\n{_shift_line(shift)}{reason}\nVERA Schichtplanner"
        )
        try:
            await svc.dispatch(
                employee=emp, event_type=EVENT_SWAP_DENIED, message=msg,
                subject=f"Tausch abgelehnt: {shift.date.strftime('%d.%m.%Y')}",
                tenant_id=shift.tenant_id,
            )
        except Exception:
            pass


async def notify_swap_cancelled(offer: "ShiftSwapOffer", reason: str, db: "AsyncSession") -> None:
    """System-Hook (Dienst storniert/geändert/gelöscht, Abwesenheit genehmigt): Anbieter
    informieren. Nicht über Event-Prefs abschaltbar — der Anbieter muss wissen, dass
    sein Angebot hinfällig ist und der Dienst bei ihm bleibt."""
    from app.models.employee import Employee
    from app.models.shift import Shift

    offering_emp = await db.get(Employee, offer.offering_employee_id)
    if not offering_emp:
        return
    shift = await db.get(Shift, offer.shift_id)

    reason_labels = {
        "shift_cancelled": "Der Dienst wurde storniert.",
        "shift_deleted": "Der Dienst wurde gelöscht.",
        "shift_changed": "Der Dienst wurde zeitlich/örtlich geändert.",
        "absence_approved": "Für den Zeitraum wurde eine Abwesenheit genehmigt.",
    }
    label = reason_labels.get(reason, reason)

    msg = f"Hallo {offering_emp.first_name},\n\ndein Tauschangebot wurde automatisch storniert: {label}\n"
    if shift:
        msg += f"\n{_shift_line(shift)}"
    msg += "\nVERA Schichtplanner"

    svc = NotificationService(db)
    try:
        await svc.dispatch(
            employee=offering_emp, event_type=EVENT_SWAP_CANCELLED, message=msg,
            subject="Tauschangebot storniert", tenant_id=offer.tenant_id,
        )
    except Exception:
        pass
