"""
Celery-Tasks für automatische Lohnabrechnungen.
"""
from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.payroll_tasks.create_monthly_payrolls")
def create_monthly_payrolls():
    """Erstellt Lohnabrechnungen für den Vormonat für alle aktiven Mitarbeiter."""
    import asyncio
    asyncio.run(_create_payrolls())


async def _create_payrolls():
    from datetime import date
    from dateutil.relativedelta import relativedelta
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.employee import Employee
    from app.models.payroll import PayrollEntry
    from app.services.payroll_service import PayrollService

    last_month = date.today().replace(day=1) - __import__('datetime').timedelta(days=1)
    month = last_month.replace(day=1)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Employee).where(Employee.is_active == True)
        )
        employees = result.scalars().all()

        payroll_svc = PayrollService(db)
        for employee in employees:
            # Nur erstellen wenn noch kein Eintrag vorhanden
            existing = await db.execute(
                select(PayrollEntry).where(
                    PayrollEntry.employee_id == employee.id,
                    PayrollEntry.month == month,
                )
            )
            if existing.scalar_one_or_none():
                continue

            try:
                entry, new_carryover = await payroll_svc.calculate_monthly_payroll(employee.id, month)
                db.add(entry)

                # Übertrag für Folgemonat anlegen wenn nötig
                if abs(new_carryover) > 0.01:
                    from app.models.payroll import HoursCarryover
                    next_month = (month.replace(day=28) + __import__('datetime').timedelta(days=4)).replace(day=1)
                    carryover = HoursCarryover(
                        tenant_id=employee.tenant_id,
                        employee_id=employee.id,
                        from_month=month,
                        to_month=next_month,
                        hours=round(new_carryover, 2),
                        reason="Automatischer Übertrag",
                    )
                    db.add(carryover)

            except Exception as e:
                import logging
                logging.getLogger(__name__).error(
                    f"Payroll error for employee {employee.id}: {e}"
                )

        await db.commit()
