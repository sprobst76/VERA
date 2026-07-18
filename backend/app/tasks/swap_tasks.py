"""
Celery-Task: abgelaufene Schichttausch-Angebote (Dienst-Abgabe) markieren.
"""
import logging

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.swap_tasks.expire_swap_offers")
def expire_swap_offers():
    """Läuft alle 15 Minuten: setzt Angebote mit abgelaufener Frist auf 'expired'."""
    import asyncio
    asyncio.run(_expire_swap_offers())


async def _expire_swap_offers():
    from datetime import datetime, timezone
    from sqlalchemy import select
    from app.core.database import TaskSessionLocal
    from app.models.shift_swap import ShiftSwapOffer
    from app.services.notification_service import notify_swap_cancelled

    try:
        now = datetime.now(timezone.utc)
        async with TaskSessionLocal() as db:
            result = await db.execute(
                select(ShiftSwapOffer).where(
                    ShiftSwapOffer.status == "open",
                    ShiftSwapOffer.expires_at <= now,
                )
            )
            offers = result.scalars().all()
            for offer in offers:
                offer.status = "expired"
            await db.commit()

            for offer in offers:
                await notify_swap_expired(offer, db)
    except Exception as e:
        logger.error("Ablauf-Prüfung für Tauschangebote fehlgeschlagen: %s", e, exc_info=True)


async def notify_swap_expired(offer, db) -> None:
    """Anbieter informieren: niemand hat übernommen, Dienst bleibt bei ihm."""
    from app.models.employee import Employee
    from app.models.shift import Shift
    from app.services.notification_service import NotificationService

    offering_emp = await db.get(Employee, offer.offering_employee_id)
    if not offering_emp:
        return
    shift = await db.get(Shift, offer.shift_id)

    msg = (
        f"Hallo {offering_emp.first_name},\n\n"
        f"Niemand hat deinen angebotenen Dienst übernommen — die Frist ist abgelaufen. "
        f"Der Dienst bleibt bei dir.\n"
    )
    if shift:
        weekdays = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
        wday = weekdays[shift.date.weekday()]
        msg += (
            f"\nDatum:  {wday}, {shift.date.strftime('%d.%m.%Y')}\n"
            f"Zeit:   {shift.start_time.strftime('%H:%M')} – {shift.end_time.strftime('%H:%M')} Uhr\n"
        )
    msg += "\nVERA Schichtplanner"

    svc = NotificationService(db)
    try:
        await svc.dispatch(
            employee=offering_emp, event_type="swap_expired", message=msg,
            subject="Tauschangebot abgelaufen", tenant_id=offer.tenant_id,
        )
    except Exception:
        pass
