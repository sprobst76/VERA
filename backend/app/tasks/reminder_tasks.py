"""
Celery-Tasks für Dienst-Erinnerungen.
"""
from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.reminder_tasks.send_daily_reminders")
def send_daily_reminders():
    """Sendet Erinnerungen für Dienste am nächsten Tag."""
    import asyncio
    from datetime import date, timedelta
    asyncio.run(_send_reminders_for_date(date.today() + timedelta(days=1)))


@celery_app.task(name="app.tasks.reminder_tasks.send_hourly_reminders")
def send_hourly_reminders():
    """Sendet Erinnerungen für Dienste in den nächsten 2 Stunden."""
    import asyncio
    asyncio.run(_send_reminder_2h())


async def _send_reminders_for_date(target_date):
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.shift import Shift

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
            send_shift_reminder.delay(str(shift.id), hours_before=24)


async def _send_reminder_2h():
    from datetime import datetime, timezone, timedelta
    from sqlalchemy import select, and_
    from app.core.database import AsyncSessionLocal
    from app.models.shift import Shift

    now = datetime.now(timezone.utc)
    in_2h = now + timedelta(hours=2)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Shift).where(
                Shift.date == in_2h.date(),
                Shift.status.in_(["planned", "confirmed"]),
                Shift.employee_id.isnot(None),
            )
        )
        shifts = result.scalars().all()
        for shift in shifts:
            shift_start_hour = shift.start_time.hour
            if shift_start_hour == in_2h.hour:
                send_shift_reminder.delay(str(shift.id), hours_before=2)


@celery_app.task(name="app.tasks.reminder_tasks.send_shift_reminder")
def send_shift_reminder(shift_id: str, hours_before: int = 24):
    """Sendet eine Erinnerung für einen konkreten Dienst."""
    import asyncio
    asyncio.run(_do_send_reminder(shift_id, hours_before))


async def _do_send_reminder(shift_id: str, hours_before: int):
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
        msg = (
            f"Hallo {emp.first_name},\n\n"
            f"Erinnerung: Dein Dienst beginnt in {hours_before} Stunde(n).\n"
            f"Datum:  {wday}, {shift.date.strftime('%d.%m.%Y')}\n"
            f"Zeit:   {shift.start_time.strftime('%H:%M')} – {shift.end_time.strftime('%H:%M')} Uhr\n"
        )
        if shift.location:
            msg += f"Ort:    {shift.location}\n"
        msg += "\nVERA Schichtplanner"

        svc = NotificationService(db)
        await svc.dispatch(
            employee=emp,
            event_type=EVENT_SHIFT_REMINDER,
            message=msg,
            subject=f"Erinnerung: Dienst am {shift.date.strftime('%d.%m.%Y')} um {shift.start_time.strftime('%H:%M')} Uhr",
            tenant_id=shift.tenant_id,
        )
