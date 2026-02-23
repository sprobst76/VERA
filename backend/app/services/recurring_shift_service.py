"""
Service for generating individual Shift records from a RecurringShift definition.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shift import Shift
from app.utils.german_holidays import get_bw_holidays

if TYPE_CHECKING:
    from app.models.holiday_profile import HolidayProfile
    from app.models.recurring_shift import RecurringShift


def build_skip_set(
    profile: "HolidayProfile | None",
    skip_public_holidays: bool = True,
    years: set[int] | None = None,
) -> set[date]:
    """
    Build the set of dates to skip when generating shifts:
      - All dates inside VacationPeriods
      - All CustomHoliday dates
      - All public holidays in BW (if skip_public_holidays=True)
    """
    skip: set[date] = set()

    if profile is not None:
        # Vacation periods
        for period in profile.vacation_periods:
            d = period.start_date
            while d <= period.end_date:
                skip.add(d)
                d += timedelta(days=1)

        # Custom holidays (bewegliche Ferientage)
        for ch in profile.custom_holidays:
            skip.add(ch.date)

    # Public holidays
    if skip_public_holidays:
        for year in (years or set()):
            skip.update(get_bw_holidays(year).keys())

    return skip


async def generate_shifts(
    rs: "RecurringShift",
    from_date: date,
    until_date: date,
    profile: "HolidayProfile | None",
    db: AsyncSession,
) -> tuple[list[Shift], int]:
    """
    Generate Shift objects for every matching weekday in [from_date, until_date]
    that is not in the skip set. Returns (new_shifts, skipped_count).

    Does NOT commit – caller is responsible for db.add / db.commit.
    """
    years = set(range(from_date.year, until_date.year + 1))
    skip = build_skip_set(profile, rs.skip_public_holidays, years)

    new_shifts: list[Shift] = []
    skipped = 0
    current = from_date

    while current <= until_date:
        if current.weekday() == rs.weekday:
            if current in skip:
                skipped += 1
            else:
                shift = Shift(
                    tenant_id=rs.tenant_id,
                    employee_id=rs.employee_id,
                    template_id=rs.template_id,
                    date=current,
                    start_time=rs.start_time,
                    end_time=rs.end_time,
                    break_minutes=rs.break_minutes,
                    status="planned",
                    is_holiday=False,
                    is_weekend=current.weekday() >= 5,
                    is_sunday=current.weekday() == 6,
                    recurring_shift_id=rs.id,
                    is_override=False,
                )
                new_shifts.append(shift)
        current += timedelta(days=1)

    return new_shifts, skipped


async def delete_future_planned_shifts(
    rs_id,
    from_date: date,
    tenant_id,
    db: AsyncSession,
) -> int:
    """
    Delete all planned (non-confirmed) shifts for the given recurring_shift_id
    on or after from_date. Returns the count of deleted shifts.
    """
    result = await db.execute(
        select(Shift).where(
            and_(
                Shift.recurring_shift_id == rs_id,
                Shift.tenant_id == tenant_id,
                Shift.date >= from_date,
                Shift.status == "planned",
                Shift.is_override == False,
            )
        )
    )
    shifts = result.scalars().all()
    for s in shifts:
        await db.delete(s)
    return len(shifts)


async def preview_generate(
    weekday: int,
    from_date: date,
    until_date: date,
    profile: "HolidayProfile | None",
    skip_public_holidays: bool,
) -> dict:
    """
    Preview how many shifts would be generated without touching the DB.
    """
    years = set(range(from_date.year, until_date.year + 1))
    skip = build_skip_set(profile, skip_public_holidays, years)

    generated = 0
    skipped = 0
    skipped_dates: list[str] = []
    current = from_date

    while current <= until_date:
        if current.weekday() == weekday:
            if current in skip:
                skipped += 1
                skipped_dates.append(current.isoformat())
            else:
                generated += 1
        current += timedelta(days=1)

    return {
        "generated_count": generated,
        "skipped_count": skipped,
        "skipped_dates": skipped_dates,
    }
