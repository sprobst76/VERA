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
            if abs(shift_start_hour - in_2h.hour) <= 0:
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
    from app.models.employee import Employee
    from app.models.notification import NotificationLog
    from datetime import datetime, timezone

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Shift)
            .options(selectinload(Shift.employee))
            .where(Shift.id == uuid.UUID(shift_id))
        )
        shift = result.scalar_one_or_none()
        if not shift or not shift.employee:
            return

        log = NotificationLog(
            tenant_id=shift.tenant_id,
            employee_id=shift.employee_id,
            channel="email",
            event_type="shift_reminder",
            subject=f"Erinnerung: Dienst am {shift.date} um {shift.start_time}",
            body=f"Hallo {shift.employee.first_name},\n\nErinnerung: Dein Dienst am {shift.date} beginnt um {shift.start_time} Uhr.\n\nOrt: {shift.location or 'siehe Planung'}\n\nViele Grüße\nVERA",
            status="pending",
        )
        db.add(log)
        await db.commit()
        # TODO: Tatsächlichen Versand implementieren (SendGrid/Telegram)
