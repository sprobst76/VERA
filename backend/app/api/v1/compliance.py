"""
Compliance API – Arbeitsrechtliche Prüfungen (ArbZG, Minijob-Limits).
"""
import uuid
from datetime import date, timedelta

from fastapi import APIRouter
from sqlalchemy import select, or_

from app.api.deps import DB, ManagerOrAdmin
from app.models.employee import Employee
from app.models.shift import Shift
from app.schemas.compliance import ComplianceViolationOut
from app.services.compliance_service import ComplianceService

router = APIRouter(prefix="/compliance", tags=["compliance"])


@router.get("/violations", response_model=list[ComplianceViolationOut])
async def list_violations(
    current_user: ManagerOrAdmin,
    db: DB,
    from_date: date | None = None,
    to_date: date | None = None,
    employee_id: uuid.UUID | None = None,
):
    """
    Gibt alle Schichten des Tenants zurück, bei denen mind. ein
    Compliance-Flag auf False gesetzt ist.
    """
    conditions = [
        Shift.tenant_id == current_user.tenant_id,
        Shift.status.notin_(["cancelled", "cancelled_absence"]),
        or_(
            Shift.rest_period_ok == False,   # noqa: E712
            Shift.break_ok == False,         # noqa: E712
            Shift.minijob_limit_ok == False, # noqa: E712
        ),
    ]
    if from_date:
        conditions.append(Shift.date >= from_date)
    if to_date:
        conditions.append(Shift.date <= to_date)
    if employee_id:
        conditions.append(Shift.employee_id == employee_id)

    result = await db.execute(
        select(Shift).where(*conditions).order_by(Shift.date.desc(), Shift.start_time)
    )
    shifts = result.scalars().all()

    # Employee-Namen nachladen (batch)
    emp_ids = {s.employee_id for s in shifts if s.employee_id}
    emp_map: dict[uuid.UUID, str] = {}
    if emp_ids:
        emp_result = await db.execute(
            select(Employee).where(Employee.id.in_(emp_ids))
        )
        for emp in emp_result.scalars().all():
            emp_map[emp.id] = f"{emp.first_name} {emp.last_name}"

    return [
        ComplianceViolationOut(
            shift_id=s.id,
            shift_date=s.date,
            start_time=s.start_time,
            end_time=s.end_time,
            employee_id=s.employee_id,
            employee_name=emp_map.get(s.employee_id, "–") if s.employee_id else "–",
            rest_period_ok=s.rest_period_ok,
            break_ok=s.break_ok,
            minijob_limit_ok=s.minijob_limit_ok,
            status=s.status,
        )
        for s in shifts
    ]


@router.post("/run", response_model=dict)
async def run_compliance_check(
    current_user: ManagerOrAdmin,
    db: DB,
    from_date: date | None = None,
    to_date: date | None = None,
):
    """
    Führt Compliance-Checks für alle nicht-stornierten Schichten im
    angegebenen Zeitraum durch (Standard: letzte 365 Tage bis heute).
    Aktualisiert rest_period_ok, break_ok, minijob_limit_ok auf den Schichten.
    """
    today = date.today()
    effective_from = from_date or (today - timedelta(days=365))
    effective_to   = to_date   or today

    shift_result = await db.execute(
        select(Shift).where(
            Shift.tenant_id == current_user.tenant_id,
            Shift.status.notin_(["cancelled", "cancelled_absence"]),
            Shift.date >= effective_from,
            Shift.date <= effective_to,
            Shift.employee_id.is_not(None),
        ).order_by(Shift.date, Shift.start_time)
    )
    shifts = shift_result.scalars().all()

    # Employees cachen
    emp_ids = {s.employee_id for s in shifts}
    emp_map: dict[uuid.UUID, Employee] = {}
    if emp_ids:
        emp_result = await db.execute(
            select(Employee).where(Employee.id.in_(emp_ids))
        )
        for emp in emp_result.scalars().all():
            emp_map[emp.id] = emp

    svc = ComplianceService(db)
    violations = 0

    for shift in shifts:
        emp = emp_map.get(shift.employee_id)
        if not emp:
            continue

        cr = await svc.check_shift(shift, emp)

        shift.rest_period_ok   = not any("Ruhezeit" in v for v in cr.violations)
        shift.break_ok         = not any("Pause"    in v for v in cr.violations)
        shift.minijob_limit_ok = not any("Minijob"  in v for v in cr.violations)

        if not (shift.rest_period_ok and shift.break_ok and shift.minijob_limit_ok):
            violations += 1

    await db.commit()

    return {"checked": len(shifts), "violations": violations}
