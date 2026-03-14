"""
Einmaliges Bereinigungsskript:
Löscht alle 'planned' Regeltermin-Schichten, die in Ferienzeiten oder an
gesetzlichen Feiertagen liegen. Bestätigte und manuell erstellte Schichten
bleiben unberührt.
"""
import asyncio
from datetime import date, timedelta

from sqlalchemy import select, delete, and_
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal
from app.models.shift import Shift
from app.models.holiday_profile import HolidayProfile
from app.utils.german_holidays import get_bw_holidays


async def build_skip_dates(db) -> set[date]:
    """Sammelt alle Ferien- und Feiertagsdaten aus allen aktiven Profilen."""
    result = await db.execute(
        select(HolidayProfile)
        .options(
            selectinload(HolidayProfile.vacation_periods),
            selectinload(HolidayProfile.custom_holidays),
        )
        .where(HolidayProfile.is_active == True)
    )
    profiles = result.scalars().all()

    skip: set[date] = set()

    for profile in profiles:
        for period in profile.vacation_periods:
            d = period.start_date
            while d <= period.end_date:
                skip.add(d)
                d += timedelta(days=1)
        for ch in profile.custom_holidays:
            skip.add(ch.date)

    # BW gesetzliche Feiertage für relevante Jahre
    for year in (2025, 2026, 2027):
        skip.update(get_bw_holidays(year).keys())

    return skip


async def main():
    async with AsyncSessionLocal() as db:
        skip_dates = await build_skip_dates(db)
        print(f"Gefundene Sperrdaten: {len(skip_dates)} Tage")

        # Alle betroffenen planned Regeltermin-Schichten finden
        result = await db.execute(
            select(Shift).where(
                and_(
                    Shift.status == "planned",
                    Shift.recurring_shift_id.isnot(None),
                )
            ).order_by(Shift.date)
        )
        shifts = result.scalars().all()

        to_delete = [s for s in shifts if s.date in skip_dates]

        if not to_delete:
            print("Keine betroffenen Schichten gefunden – alles sauber!")
            return

        print(f"\nFolgende {len(to_delete)} Schichten werden gelöscht:")
        for s in to_delete:
            _, holiday_name = (False, None)
            from app.utils.german_holidays import is_holiday
            is_hol, hol_name = is_holiday(s.date)
            reason = hol_name if is_hol else "Ferienzeit"
            print(f"  {s.date}  {s.start_time}–{s.end_time}  employee_id={s.employee_id}  Grund: {reason}")

        confirm = input(f"\n{len(to_delete)} Schichten löschen? (ja/nein): ").strip().lower()
        if confirm != "ja":
            print("Abgebrochen.")
            return

        ids_to_delete = [s.id for s in to_delete]
        await db.execute(
            delete(Shift).where(Shift.id.in_(ids_to_delete))
        )
        await db.commit()
        print(f"\n✓ {len(to_delete)} Schichten gelöscht.")


if __name__ == "__main__":
    asyncio.run(main())
