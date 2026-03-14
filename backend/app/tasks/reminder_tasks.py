"""
Celery-Tasks für Dienst-Erinnerungen.

Logik:
- Jede 5 Minuten: shift-type-basierte Erinnerungen (shift_type.reminder_minutes_before)
  → Redis-Key verhindert Doppelversand
- Täglich 08:00: allgemeine 24h-Vorwarnung für ALLE Dienste mit Mitarbeiter
  (unabhängig vom Diensttyp, nur wenn Event-Pref "shift_reminder" aktiviert)
"""
import logging

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

# Redis-Key Präfix für gesendete Typ-Erinnerungen (TTL 48h)
REDIS_PREFIX = "vera:reminder:type:"
REDIS_TTL    = 48 * 3600  # 48 Stunden


# ── Beat-Tasks ────────────────────────────────────────────────────────────────

@celery_app.task(name="app.tasks.reminder_tasks.send_type_reminders")
def send_type_reminders():
    """
    Läuft alle 5 Minuten.
    Schickt Erinnerungen für Dienste deren Diensttyp reminder_enabled=True hat
    und die im Fenster [now, now + reminder_minutes_before] beginnen.
    Deduplizierung via Redis (ein Dienst bekommt seine Typ-Erinnerung nur einmal).
    """
    import asyncio
    asyncio.run(_run_type_reminders())


@celery_app.task(name="app.tasks.reminder_tasks.send_daily_reminders")
def send_daily_reminders():
    """Täglich 08:00: generelle 24h-Erinnerung für alle Dienste morgen."""
    import asyncio
    from datetime import date, timedelta
    asyncio.run(_send_reminders_for_date(date.today() + timedelta(days=1), hours_before=24))


# Legacy: stündlich (wird von daily + 5-min-task abgedeckt, bleibt für Kompatibilität)
@celery_app.task(name="app.tasks.reminder_tasks.send_hourly_reminders")
def send_hourly_reminders():
    pass  # ersetzt durch send_type_reminders


# ── Kern-Logik: Diensttyp-basierte Erinnerungen ───────────────────────────────

async def _run_type_reminders():
    from datetime import datetime, timezone, timedelta, date as date_type
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.core.database import AsyncSessionLocal
    from app.models.shift import Shift
    from app.models.shift_type import ShiftType
    from app.core.redis import get_redis

    now = datetime.now(timezone.utc)

    try:
        async with AsyncSessionLocal() as db:
            # Lade alle aktiven Diensttypen mit Erinnerung
            st_result = await db.execute(
                select(ShiftType).where(
                    ShiftType.reminder_enabled == True,
                    ShiftType.is_active == True,
                )
            )
            shift_types = {st.id: st for st in st_result.scalars().all()}

            if not shift_types:
                return

            # Suche Dienste der nächsten 24h mit einem dieser Typen
            tomorrow = (now + timedelta(hours=24)).date()
            result = await db.execute(
                select(Shift)
                .options(selectinload(Shift.employee))
                .where(
                    Shift.date <= tomorrow,
                    Shift.date >= now.date(),
                    Shift.shift_type_id.in_(shift_types.keys()),
                    Shift.status.in_(["planned", "confirmed"]),
                    Shift.employee_id.isnot(None),
                )
            )
            shifts = result.scalars().all()

        redis = await get_redis()

        for shift in shifts:
            st = shift_types.get(shift.shift_type_id)
            if not st or not shift.employee:
                continue

            redis_key = f"{REDIS_PREFIX}{shift.id}"

            # Bereits gesendet?
            if await redis.exists(redis_key):
                continue

            # Dienstbeginn in Berlin-Zeit berechnen
            from zoneinfo import ZoneInfo
            from datetime import datetime as dt
            berlin = ZoneInfo("Europe/Berlin")
            shift_start = dt(
                shift.date.year, shift.date.month, shift.date.day,
                shift.start_time.hour, shift.start_time.minute,
                tzinfo=berlin,
            )
            shift_start_utc = shift_start.astimezone(timezone.utc)

            # Erinnerungsfenster: [start - minutes_before, start - minutes_before + 5min]
            remind_at = shift_start_utc - timedelta(minutes=st.reminder_minutes_before)
            remind_until = remind_at + timedelta(minutes=5)

            if remind_at <= now <= remind_until:
                # Erinnerung schicken
                send_shift_reminder.delay(
                    str(shift.id),
                    hours_before=round(st.reminder_minutes_before / 60, 1),
                    shift_type_name=st.name,
                )
                # Deduplizierungs-Key setzen
                await redis.setex(redis_key, REDIS_TTL, "sent")

    except Exception as e:
        logger.error("Typ-Erinnerungen fehlgeschlagen: %s", e, exc_info=True)


# ── Kern-Logik: tägliche generelle Erinnerungen ───────────────────────────────

async def _send_reminders_for_date(target_date, hours_before: int = 24):
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.shift import Shift

    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Shift).where(
                    Shift.date == target_date,
                    Shift.status.in_(["planned", "confirmed"]),
                    Shift.employee_id.isnot(None),
                )
            )
            shifts = result.scalars().all()
            for shift in shifts:
                send_shift_reminder.delay(str(shift.id), hours_before=hours_before)
    except Exception as e:
        logger.error("Tageserinnerungen fehlgeschlagen für %s: %s", target_date, e, exc_info=True)


# ── Shared Task: Erinnerungsnachricht bauen & versenden ───────────────────────

@celery_app.task(name="app.tasks.reminder_tasks.send_shift_reminder")
def send_shift_reminder(shift_id: str, hours_before: float = 24, shift_type_name: str | None = None):
    """Sendet eine Erinnerung für einen konkreten Dienst."""
    import asyncio
    asyncio.run(_do_send_reminder(shift_id, hours_before, shift_type_name))


async def _do_send_reminder(shift_id: str, hours_before: float, shift_type_name: str | None):
    import uuid
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.core.database import AsyncSessionLocal
    from app.models.shift import Shift
    from app.services.notification_service import NotificationService, EVENT_SHIFT_REMINDER

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Shift)
            .options(selectinload(Shift.employee))
            .where(Shift.id == uuid.UUID(shift_id))
        )
        shift = result.scalar_one_or_none()
        if not shift or not shift.employee:
            return

        emp = shift.employee
        weekdays = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
        wday = weekdays[shift.date.weekday()]

        # Zeitangabe
        if hours_before < 1:
            time_label = f"{int(hours_before * 60)} Minuten"
        elif hours_before == int(hours_before):
            time_label = f"{int(hours_before)} Stunde(n)"
        else:
            time_label = f"{hours_before:.1f} Stunden"

        type_line = f"Typ:    {shift_type_name}\n" if shift_type_name else ""

        msg = (
            f"Hallo {emp.first_name},\n\n"
            f"Erinnerung: Dein Dienst beginnt in {time_label}.\n"
            f"Datum:  {wday}, {shift.date.strftime('%d.%m.%Y')}\n"
            f"Zeit:   {shift.start_time.strftime('%H:%M')} – {shift.end_time.strftime('%H:%M')} Uhr\n"
            f"{type_line}"
        )
        if shift.location:
            msg += f"Ort:    {shift.location}\n"
        msg += "\nVERA Schichtplanner"

        subject = (
            f"{'[' + shift_type_name + '] ' if shift_type_name else ''}"
            f"Erinnerung: Dienst am {shift.date.strftime('%d.%m.%Y')} "
            f"um {shift.start_time.strftime('%H:%M')} Uhr"
        )

        svc = NotificationService(db)
        await svc.dispatch(
            employee=emp,
            event_type=EVENT_SHIFT_REMINDER,
            message=msg,
            subject=subject,
            tenant_id=shift.tenant_id,
        )
