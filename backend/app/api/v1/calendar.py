"""
Calendar endpoints:

GET /calendar/{token}.ics            – public iCal feed (no JWT)
GET /api/v1/calendar/vacation-data   – vacation/holiday data for calendar display (JWT required)
POST /api/v1/calendar/regenerate-token – regenerate iCal token for current user
"""
import secrets
from datetime import datetime, timezone, timedelta, date, time as dtime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from icalendar import Calendar, Event, vText, Alarm
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.employee import Employee
from app.models.holiday_profile import HolidayProfile, VacationPeriod, CustomHoliday
from app.models.shift import Shift, ShiftTemplate
from app.models.absence import CareRecipientAbsence, EmployeeAbsence
from app.models.shift_type import ShiftType
from app.models.user import User
from app.api.deps import CurrentUser, DB
from app.utils.german_holidays import get_bw_holidays

# Public router (mounted without /api/v1 prefix in main.py)
router = APIRouter(tags=["calendar"])

# Authenticated router (mounted with /api/v1 prefix)
vacation_router = APIRouter(prefix="/calendar", tags=["calendar"])

TZ = ZoneInfo("Europe/Berlin")

STATUS_LABELS = {
    "planned":            "Geplant",
    "confirmed":          "Bestätigt",
    "completed":          "Abgeschlossen",
    "cancelled":          "Abgesagt",
    "cancelled_absence":  "Abgesagt (Abwesenheit)",
}


def _dt(d: date, t: dtime) -> datetime:
    """Combine date + time → tz-aware datetime in Europe/Berlin."""
    return datetime(d.year, d.month, d.day, t.hour, t.minute, tzinfo=TZ)


def _build_calendar(shifts: list, emp_map: dict, cal_name: str, shift_type_map: dict | None = None) -> bytes:
    cal = Calendar()
    cal.add("prodid", "-//VERA//Schichtkalender//DE")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("method", "PUBLISH")
    cal.add("x-wr-calname", vText(cal_name))
    cal.add("name", vText(cal_name))
    cal.add("x-wr-timezone", vText("Europe/Berlin"))
    cal.add("refresh-interval;value=duration", "PT1H")
    cal.add("x-published-ttl", "PT1H")

    for shift in shifts:
        if shift.status in ("cancelled", "cancelled_absence"):
            continue

        ev = Event()
        ev.add("uid", f"vera-shift-{shift.id}@vera")
        ev.add("dtstamp", datetime.now(timezone.utc))

        start_dt = _dt(shift.date, shift.start_time)
        end_dt = _dt(shift.date, shift.end_time)
        if end_dt <= start_dt:
            end_dt += timedelta(days=1)

        ev.add("dtstart", start_dt)
        ev.add("dtend", end_dt)

        template_name = shift.template.name if shift.template else "Dienst"
        emp = emp_map.get(shift.employee_id)
        if emp:
            summary = f"{template_name} – {emp.first_name} {emp.last_name}"
        else:
            summary = template_name
        ev.add("summary", vText(summary))

        if shift.location:
            ev.add("location", vText(shift.location))

        lines = []
        if emp:
            lines.append(f"Mitarbeiter: {emp.first_name} {emp.last_name}")
        lines.append(f"Status: {STATUS_LABELS.get(shift.status, shift.status)}")
        if shift.break_minutes:
            lines.append(f"Pause: {shift.break_minutes} min")
        if shift.confirmation_note:
            lines.append(f"Hinweis: {shift.confirmation_note}")
        if shift.notes:
            lines.append(f"Notiz: {shift.notes}")
        ev.add("description", vText("\n".join(lines)))

        ev.add("status", "CONFIRMED" if shift.status in ("confirmed", "completed") else "TENTATIVE")
        ev.add("last-modified", datetime.now(timezone.utc))

        # VALARM – reminder based on shift type settings
        if shift_type_map and shift.shift_type_id:
            st = shift_type_map.get(shift.shift_type_id)
            if st and st.reminder_enabled and st.reminder_minutes_before > 0:
                alarm = Alarm()
                alarm.add("action", "DISPLAY")
                alarm.add("description", vText(f"Erinnerung: {summary}"))
                alarm.add("trigger", timedelta(minutes=-st.reminder_minutes_before))
                ev.add_component(alarm)

        cal.add_component(ev)

    return cal.to_ical()


@router.get("/calendar/{token}.ics", include_in_schema=True)
async def get_ical_feed(token: str):
    """
    Public iCal feed. Token identifies either an employee or an admin user.
    No authentication header required.
    """
    async with AsyncSessionLocal() as db:

        emp_result = await db.execute(
            select(Employee).where(Employee.ical_token == token)
        )
        employee = emp_result.scalar_one_or_none()

        if employee:
            shifts_result = await db.execute(
                select(Shift).where(
                    Shift.employee_id == employee.id,
                    Shift.tenant_id == employee.tenant_id,
                ).order_by(Shift.date)
            )
            shifts = shifts_result.scalars().all()

            for shift in shifts:
                if shift.template_id:
                    tpl_result = await db.execute(
                        select(ShiftTemplate).where(ShiftTemplate.id == shift.template_id)
                    )
                    shift.template = tpl_result.scalar_one_or_none()
                else:
                    shift.template = None

            st_result = await db.execute(
                select(ShiftType).where(ShiftType.tenant_id == employee.tenant_id)
            )
            shift_type_map = {st.id: st for st in st_result.scalars().all()}

            cal_name = f"VERA – {employee.first_name} {employee.last_name}"
            ical_bytes = _build_calendar(shifts, {employee.id: employee}, cal_name, shift_type_map)

            return Response(
                content=ical_bytes,
                media_type="text/calendar; charset=utf-8",
                headers={
                    "Content-Disposition": f'attachment; filename="vera-{employee.first_name.lower()}.ics"',
                    "Cache-Control": "no-cache",
                },
            )

        user_result = await db.execute(
            select(User).where(User.ical_token == token)
        )
        user = user_result.scalar_one_or_none()

        if user and user.role in ("admin", "manager") and user.is_active:
            shifts_result = await db.execute(
                select(Shift).where(
                    Shift.tenant_id == user.tenant_id,
                ).order_by(Shift.date)
            )
            shifts = shifts_result.scalars().all()

            for shift in shifts:
                if shift.template_id:
                    tpl_result = await db.execute(
                        select(ShiftTemplate).where(ShiftTemplate.id == shift.template_id)
                    )
                    shift.template = tpl_result.scalar_one_or_none()
                else:
                    shift.template = None

            emps_result = await db.execute(
                select(Employee).where(Employee.tenant_id == user.tenant_id)
            )
            emp_map = {e.id: e for e in emps_result.scalars().all()}

            st_result = await db.execute(
                select(ShiftType).where(ShiftType.tenant_id == user.tenant_id)
            )
            shift_type_map = {st.id: st for st in st_result.scalars().all()}

            cal_name = "VERA – Alle Dienste"
            ical_bytes = _build_calendar(shifts, emp_map, cal_name, shift_type_map)

            return Response(
                content=ical_bytes,
                media_type="text/calendar; charset=utf-8",
                headers={
                    "Content-Disposition": 'attachment; filename="vera-alle-dienste.ics"',
                    "Cache-Control": "no-cache",
                },
            )

    raise HTTPException(status_code=404, detail="Kalender nicht gefunden")


# ── Token management ─────────────────────────────────────────────────────────

@vacation_router.post("/regenerate-token")
async def regenerate_ical_token(current_user: CurrentUser, db: DB):
    """Regenerate the iCal token for the current user (and linked employee if any)."""
    new_token = secrets.token_urlsafe(32)
    current_user.ical_token = new_token

    # Also regenerate linked employee token if exists
    emp_result = await db.execute(
        select(Employee).where(Employee.user_id == current_user.id)
    )
    employee = emp_result.scalar_one_or_none()
    if employee:
        employee.ical_token = secrets.token_urlsafe(32)

    await db.commit()
    return {
        "ical_token": new_token,
        "employee_ical_token": employee.ical_token if employee else None,
    }


@vacation_router.get("/ical-links")
async def get_ical_links(current_user: CurrentUser, db: DB):
    """
    Return iCal feed URLs for the current user.
    Admin/Manager: own URL (all shifts) + all employee URLs.
    Employee: own URL only.
    """
    base_url = "https://vera.lab.halbewahrheit21.de"

    result = {"own_url": f"{base_url}/calendar/{current_user.ical_token}.ics"}

    if current_user.role in ("admin", "manager"):
        emps_result = await db.execute(
            select(Employee).where(
                Employee.tenant_id == current_user.tenant_id,
                Employee.is_active == True,
                Employee.ical_token.isnot(None),
            ).order_by(Employee.first_name, Employee.last_name)
        )
        employees = emps_result.scalars().all()
        result["employee_links"] = [
            {
                "id": str(e.id),
                "name": f"{e.first_name} {e.last_name}",
                "url": f"{base_url}/calendar/{e.ical_token}.ics",
            }
            for e in employees
        ]
    else:
        # Employee: own employee ical_token (for personal feed)
        emp_result = await db.execute(
            select(Employee).where(Employee.user_id == current_user.id)
        )
        emp = emp_result.scalar_one_or_none()
        if emp and emp.ical_token:
            result["own_url"] = f"{base_url}/calendar/{emp.ical_token}.ics"

    return result


# ── Vacation/Holiday data for calendar display ────────────────────────────────

@vacation_router.get("/vacation-data")
async def get_vacation_data(
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    current_user: CurrentUser = None,
    db: DB = None,
):
    """
    Returns vacation periods, custom holidays, and public holidays
    for the active holiday profile of the current tenant.
    Used by the calendar page to render background events.
    """
    hp_result = await db.execute(
        select(HolidayProfile).where(
            HolidayProfile.tenant_id == current_user.tenant_id,
            HolidayProfile.is_active == True,
        )
    )
    profile = hp_result.scalar_one_or_none()

    vacation_periods = []
    custom_holidays = []

    if profile:
        vp_result = await db.execute(
            select(VacationPeriod).where(
                VacationPeriod.profile_id == profile.id,
                VacationPeriod.end_date >= from_date,
                VacationPeriod.start_date <= to_date,
            ).order_by(VacationPeriod.start_date)
        )
        for vp in vp_result.scalars().all():
            vacation_periods.append({
                "id": str(vp.id),
                "name": vp.name,
                "start_date": vp.start_date.isoformat(),
                "end_date": vp.end_date.isoformat(),
                "color": vp.color,
            })

        ch_result = await db.execute(
            select(CustomHoliday).where(
                CustomHoliday.profile_id == profile.id,
                CustomHoliday.date >= from_date,
                CustomHoliday.date <= to_date,
            ).order_by(CustomHoliday.date)
        )
        for ch in ch_result.scalars().all():
            custom_holidays.append({
                "id": str(ch.id),
                "date": ch.date.isoformat(),
                "name": ch.name,
                "color": ch.color,
            })

    public_holidays = []
    for year in range(from_date.year, to_date.year + 1):
        for d, name in get_bw_holidays(year).items():
            if from_date <= d <= to_date:
                public_holidays.append({
                    "date": d.isoformat(),
                    "name": name,
                })

    # Care recipient absences
    care_result = await db.execute(
        select(CareRecipientAbsence).where(
            CareRecipientAbsence.tenant_id == current_user.tenant_id,
            CareRecipientAbsence.end_date >= from_date,
            CareRecipientAbsence.start_date <= to_date,
        ).order_by(CareRecipientAbsence.start_date)
    )
    care_absences = []
    type_labels = {
        "vacation": "Urlaub (betreute Person)",
        "rehab": "Reha",
        "hospital": "Krankenhausaufenthalt",
        "sick": "Krank",
        "other": "Abwesenheit",
    }
    for ca in care_result.scalars().all():
        label = type_labels.get(ca.type, ca.type)
        if ca.description:
            label = f"{label}: {ca.description}"
        care_absences.append({
            "id": str(ca.id),
            "type": ca.type,
            "label": label,
            "start_date": ca.start_date.isoformat(),
            "end_date": ca.end_date.isoformat(),
            "shift_handling": ca.shift_handling,
        })

    # Employee absences (approved only)
    # RBAC: Employee sees only own absences; Admin/Manager see all
    emp_absence_filter = [
        EmployeeAbsence.tenant_id == current_user.tenant_id,
        EmployeeAbsence.status == "approved",
        EmployeeAbsence.end_date >= from_date,
        EmployeeAbsence.start_date <= to_date,
    ]
    if current_user.role == "employee":
        emp_result = await db.execute(
            select(Employee).where(Employee.user_id == current_user.id)
        )
        linked_emp = emp_result.scalar_one_or_none()
        if linked_emp:
            emp_absence_filter.append(EmployeeAbsence.employee_id == linked_emp.id)
        else:
            emp_absence_filter.append(EmployeeAbsence.employee_id == None)  # noqa: E711

    ea_result = await db.execute(
        select(EmployeeAbsence, Employee).join(
            Employee, Employee.id == EmployeeAbsence.employee_id
        ).where(*emp_absence_filter).order_by(EmployeeAbsence.start_date)
    )
    employee_absences = []
    for ea, emp in ea_result.all():
        employee_absences.append({
            "id": str(ea.id),
            "employee_id": str(ea.employee_id),
            "employee_name": f"{emp.first_name} {emp.last_name}",
            "type": ea.type,
            "start_date": ea.start_date.isoformat(),
            "end_date": ea.end_date.isoformat(),
            "days_count": float(ea.days_count) if ea.days_count is not None else None,
        })

    return {
        "vacation_periods": vacation_periods,
        "custom_holidays": custom_holidays,
        "public_holidays": public_holidays,
        "care_absences": care_absences,
        "employee_absences": employee_absences,
    }
