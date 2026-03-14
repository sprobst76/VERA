"""
Reports API – Auswertungen und Berichte (MVP)

GET /reports/hours-summary       – Stunden pro Mitarbeiter und Zeitraum
GET /reports/minijob-limit-status – Minijob-Jahres-€-Status aller Minijobber
GET /reports/compliance-violations – Compliance-Verstöße im Zeitraum
GET /reports/surcharge-breakdown  – Zuschlagsaufschlüsselung nach Monat
GET /reports/absences             – Abwesenheits-Jahresbericht
GET /reports/export/csv           – CSV-Export für hours-summary
"""
import csv
import io
import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import Response
from sqlalchemy import select, func, and_

from sqlalchemy import or_

from app.api.deps import DB, CurrentUser
from app.models.employee import Employee
from app.models.shift import Shift
from app.models.payroll import PayrollEntry
from app.models.absence import EmployeeAbsence

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/hours-summary")
async def hours_summary(
    current_user: CurrentUser,
    db: DB,
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    employee_id: Optional[uuid.UUID] = Query(default=None),
):
    """
    Stunden pro Mitarbeiter im angegebenen Zeitraum (abgeschlossene + bestätigte Dienste).
    Admin: alle Mitarbeiter. Employee: nur eigene Daten.
    """
    # Mitarbeiter ermitteln
    if current_user.role == "admin":
        emp_q = select(Employee).where(
            Employee.tenant_id == current_user.tenant_id,
            Employee.is_active == True,
        )
        if employee_id:
            emp_q = emp_q.where(Employee.id == employee_id)
        emp_result = await db.execute(emp_q.order_by(Employee.last_name))
        employees = emp_result.scalars().all()
    else:
        emp_result = await db.execute(
            select(Employee).where(
                Employee.user_id == current_user.id,
                Employee.tenant_id == current_user.tenant_id,
            )
        )
        emp = emp_result.scalar_one_or_none()
        employees = [emp] if emp else []

    if not employees:
        return []

    emp_ids = [e.id for e in employees]

    # Dienste im Zeitraum – Stunden aus paid_hours in Payroll oder Shift-Zeiten
    # Wir laden Shifts und berechnen Stunden in Python (DB-agnostisch)
    shift_result = await db.execute(
        select(Shift).where(
            Shift.tenant_id == current_user.tenant_id,
            Shift.employee_id.in_(emp_ids),
            Shift.date >= from_date,
            Shift.date <= to_date,
            Shift.status.in_(["confirmed", "completed"]),
        )
    )
    all_shifts = shift_result.scalars().all()

    from datetime import datetime, timedelta
    shift_map: dict[uuid.UUID, dict] = {}
    for s in all_shifts:
        eid = s.employee_id
        if eid not in shift_map:
            shift_map[eid] = {"shift_count": 0, "gross_hours": 0.0, "net_hours": 0.0}
        start = datetime.combine(s.date, s.start_time)
        end = datetime.combine(s.date, s.end_time)
        if end <= start:
            end += timedelta(days=1)
        gross = (end - start).total_seconds() / 3600
        net = max(0.0, gross - (s.break_minutes or 0) / 60)
        shift_map[eid]["shift_count"] += 1
        shift_map[eid]["gross_hours"] = round(shift_map[eid]["gross_hours"] + gross, 2)
        shift_map[eid]["net_hours"] = round(shift_map[eid]["net_hours"] + net, 2)

    emp_map = {e.id: e for e in employees}
    return [
        {
            "employee_id":   str(eid),
            "first_name":    emp_map[eid].first_name,
            "last_name":     emp_map[eid].last_name,
            "contract_type": emp_map[eid].contract_type,
            "from":          str(from_date),
            "to":            str(to_date),
            **shift_map.get(eid, {"shift_count": 0, "gross_hours": 0.0, "net_hours": 0.0}),
        }
        for eid in emp_ids
        if eid in emp_map
    ]


@router.get("/minijob-limit-status")
async def minijob_limit_status(
    current_user: CurrentUser,
    db: DB,
    year: Optional[int] = Query(default=None),
):
    """
    Jahres-€-Status aller Minijobber: YTD-Brutto vs. Jahres-Limit.
    Admin: alle. Employee: nur eigene (wenn Minijob).
    """
    target_year = year or date.today().year
    year_start = date(target_year, 1, 1)
    year_end = date(target_year, 12, 31)

    if current_user.role == "admin":
        emp_result = await db.execute(
            select(Employee).where(
                Employee.tenant_id == current_user.tenant_id,
                Employee.is_active == True,
                Employee.contract_type == "minijob",
            ).order_by(Employee.last_name)
        )
        employees = emp_result.scalars().all()
    else:
        emp_result = await db.execute(
            select(Employee).where(
                Employee.user_id == current_user.id,
                Employee.tenant_id == current_user.tenant_id,
                Employee.contract_type == "minijob",
            )
        )
        emp = emp_result.scalar_one_or_none()
        employees = [emp] if emp else []

    if not employees:
        return []

    emp_ids = [e.id for e in employees]

    # YTD aus approved/paid Abrechnungen
    ytd_result = await db.execute(
        select(
            PayrollEntry.employee_id,
            func.sum(PayrollEntry.total_gross).label("ytd_gross"),
        )
        .where(
            PayrollEntry.tenant_id == current_user.tenant_id,
            PayrollEntry.employee_id.in_(emp_ids),
            PayrollEntry.month >= year_start,
            PayrollEntry.month <= year_end,
            PayrollEntry.status.in_(["approved", "paid"]),
        )
        .group_by(PayrollEntry.employee_id)
    )
    ytd_map: dict[uuid.UUID, float] = {
        row.employee_id: float(row.ytd_gross or 0) for row in ytd_result.all()
    }

    results = []
    for emp in employees:
        limit = float(emp.annual_salary_limit or 6672)
        ytd = ytd_map.get(emp.id, 0.0)
        remaining = max(0.0, limit - ytd)
        pct = round(ytd / limit * 100, 1) if limit > 0 else 0.0
        results.append({
            "employee_id":    str(emp.id),
            "first_name":     emp.first_name,
            "last_name":      emp.last_name,
            "year":           target_year,
            "annual_limit":   limit,
            "ytd_gross":      round(ytd, 2),
            "remaining":      round(remaining, 2),
            "percent_used":   pct,
            "status":         "critical" if pct >= 90 else ("warning" if pct >= 75 else "ok"),
        })
    return results


@router.get("/compliance-violations")
async def compliance_violations_report(
    current_user: CurrentUser,
    db: DB,
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    employee_id: Optional[uuid.UUID] = Query(default=None),
):
    """
    Compliance-Verstöße im Zeitraum (aus Shift-Flags).
    Admin: alle. Employee: nur eigene.
    """
    conditions = [
        Shift.tenant_id == current_user.tenant_id,
        Shift.date >= from_date,
        Shift.date <= to_date,
        Shift.status.notin_(["cancelled", "cancelled_absence"]),
        or_(
            Shift.rest_period_ok == False,
            Shift.break_ok == False,
            Shift.minijob_limit_ok == False,
        ),
    ]

    if current_user.role != "admin":
        emp_result = await db.execute(
            select(Employee).where(
                Employee.user_id == current_user.id,
                Employee.tenant_id == current_user.tenant_id,
            )
        )
        emp = emp_result.scalar_one_or_none()
        if not emp:
            return []
        conditions.append(Shift.employee_id == emp.id)
    elif employee_id:
        conditions.append(Shift.employee_id == employee_id)

    result = await db.execute(
        select(Shift).where(*conditions).order_by(Shift.date.desc())
    )
    shifts = result.scalars().all()

    emp_ids = list({s.employee_id for s in shifts if s.employee_id})
    names: dict[uuid.UUID, str] = {}
    if emp_ids:
        emp_result = await db.execute(
            select(Employee).where(
                Employee.id.in_(emp_ids),
                Employee.tenant_id == current_user.tenant_id,
            )
        )
        for e in emp_result.scalars().all():
            names[e.id] = f"{e.first_name} {e.last_name}"

    results = []
    for s in shifts:
        violations = []
        if s.rest_period_ok is False:
            violations.append("Ruhezeit < 11h")
        if s.break_ok is False:
            violations.append("Pause unterschritten")
        if s.minijob_limit_ok is False:
            violations.append("Minijob-Limit überschritten")
        results.append({
            "shift_id":      str(s.id),
            "employee_id":   str(s.employee_id),
            "employee_name": names.get(s.employee_id, "–"),
            "date":          str(s.date),
            "start_time":    str(s.start_time),
            "end_time":      str(s.end_time),
            "violations":    violations,
            "status":        s.status,
        })
    return results


@router.get("/surcharge-breakdown")
async def surcharge_breakdown(
    current_user: CurrentUser,
    db: DB,
    month: date = Query(..., description="Erster Tag des Monats (YYYY-MM-01)"),
    employee_id: Optional[uuid.UUID] = Query(default=None),
):
    """
    Zuschlagsaufschlüsselung für einen Monat aus den Lohnabrechnungen.
    """
    if current_user.role == "admin":
        q = select(PayrollEntry).where(
            PayrollEntry.tenant_id == current_user.tenant_id,
            PayrollEntry.month == month,
        )
        if employee_id:
            q = q.where(PayrollEntry.employee_id == employee_id)
    else:
        emp_result = await db.execute(
            select(Employee).where(
                Employee.user_id == current_user.id,
                Employee.tenant_id == current_user.tenant_id,
            )
        )
        emp = emp_result.scalar_one_or_none()
        if not emp:
            return []
        q = select(PayrollEntry).where(
            PayrollEntry.tenant_id == current_user.tenant_id,
            PayrollEntry.employee_id == emp.id,
            PayrollEntry.month == month,
        )

    result = await db.execute(q)
    entries = result.scalars().all()

    emp_ids = [e.employee_id for e in entries]
    names: dict[uuid.UUID, str] = {}
    if emp_ids:
        emp_r = await db.execute(
            select(Employee).where(Employee.id.in_(emp_ids), Employee.tenant_id == current_user.tenant_id)
        )
        for e in emp_r.scalars().all():
            names[e.id] = f"{e.first_name} {e.last_name}"

    return [
        {
            "employee_id":          str(e.employee_id),
            "employee_name":        names.get(e.employee_id, "–"),
            "month":                str(e.month),
            "base_wage":            float(e.base_wage or 0),
            "early_surcharge":      float(e.early_surcharge or 0),
            "late_surcharge":       float(e.late_surcharge or 0),
            "night_surcharge":      float(e.night_surcharge or 0),
            "sunday_surcharge":     float(e.sunday_surcharge or 0),
            "holiday_surcharge":    float(e.holiday_surcharge or 0),
            "total_surcharges":     sum(float(x or 0) for x in [
                e.early_surcharge, e.late_surcharge, e.night_surcharge,
                e.sunday_surcharge, e.holiday_surcharge
            ]),
            "total_gross":          float(e.total_gross or 0),
            "paid_hours":           float(e.paid_hours or 0),
            "status":               e.status,
        }
        for e in entries
    ]


@router.get("/export/csv")
async def export_csv(
    current_user: CurrentUser,
    db: DB,
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    employee_id: Optional[uuid.UUID] = Query(default=None),
):
    """
    CSV-Export der Stunden-Zusammenfassung.
    """
    # Daten via hours_summary laden
    summary = await hours_summary(
        current_user=current_user,
        db=db,
        from_date=from_date,
        to_date=to_date,
        employee_id=employee_id,
    )

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=[
        "employee_id", "first_name", "last_name", "contract_type",
        "from", "to", "shift_count", "gross_hours", "net_hours",
    ])
    writer.writeheader()
    writer.writerows(summary)

    filename = f"vera_stunden_{from_date}_{to_date}.csv"
    return Response(
        content=output.getvalue().encode("utf-8-sig"),  # BOM für Excel
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/absences")
async def absences_report(
    current_user: CurrentUser,
    db: DB,
    year: int = Query(default=None, description="Jahr (z.B. 2026); Standard: aktuelles Jahr"),
):
    """
    Abwesenheits-Jahresbericht: Alle Abwesenheiten eines Jahres mit Tagen-Summe pro Typ.
    Mitarbeiter sehen nur ihre eigenen Abwesenheiten.
    """
    from datetime import datetime
    if year is None:
        year = datetime.now().year

    year_start = date(year, 1, 1)
    year_end   = date(year, 12, 31)

    query = (
        select(EmployeeAbsence, Employee)
        .join(Employee, Employee.id == EmployeeAbsence.employee_id)
        .where(
            Employee.tenant_id == current_user.tenant_id,
            EmployeeAbsence.start_date <= year_end,
            EmployeeAbsence.end_date >= year_start,
        )
    )

    if current_user.role == "employee":
        emp_result = await db.execute(
            select(Employee.id).where(Employee.user_id == current_user.id)
        )
        own_id = emp_result.scalar_one_or_none()
        if own_id is None:
            return []
        query = query.where(EmployeeAbsence.employee_id == own_id)

    query = query.order_by(EmployeeAbsence.start_date)
    result = await db.execute(query)
    rows = result.fetchall()

    items = []
    for absence, emp in rows:
        # Clamp auf das Jahr
        eff_start = max(absence.start_date, year_start)
        eff_end   = min(absence.end_date,   year_end)
        days = (eff_end - eff_start).days + 1
        items.append({
            "id":             str(absence.id),
            "employee_id":    str(emp.id),
            "first_name":     emp.first_name,
            "last_name":      emp.last_name,
            "absence_type":   absence.absence_type,
            "start_date":     str(absence.start_date),
            "end_date":       str(absence.end_date),
            "days_in_year":   days,
            "status":         absence.status,
            "reason":         absence.reason or "",
        })

    return items
