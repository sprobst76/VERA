"""
PayrollService: Monatliche Lohnabrechnung mit Zuschlägen.
Zuschlagsätze gemäß §3b EStG (steuerlich begünstigt).
"""
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta, time
from typing import TYPE_CHECKING

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.german_holidays import is_holiday

if TYPE_CHECKING:
    from app.models.employee import Employee
    from app.models.shift import Shift
    from app.models.contract_history import ContractHistory


SURCHARGE_RATES = {
    "early":   0.125,  # 12.5% vor 06:00
    "late":    0.125,  # 12.5% nach 20:00
    "night":   0.25,   # 25%   23:00–06:00
    "weekend": 0.25,   # 25%   Samstag
    "sunday":  0.50,   # 50%   Sonntag
    "holiday": 1.25,   # 125%  Feiertag
}


class PayrollService:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_contract_at(self, employee_id: uuid.UUID, month_start: date):
        """Gibt den zum Monatsersten gültigen Vertragseintrag zurück, oder None."""
        from app.models.contract_history import ContractHistory
        result = await self.db.execute(
            select(ContractHistory)
            .where(
                ContractHistory.employee_id == employee_id,
                ContractHistory.valid_from <= month_start,
                or_(ContractHistory.valid_to.is_(None), ContractHistory.valid_to > month_start),
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def calculate_monthly_payroll(
        self, employee_id, month: date
    ):
        from app.models.employee import Employee
        from app.models.payroll import PayrollEntry, HoursCarryover
        from app.models.shift import Shift

        # Employee laden
        emp_result = await self.db.execute(select(Employee).where(Employee.id == employee_id))
        employee = emp_result.scalar_one()

        # Historischen Vertrag für diesen Monat ermitteln (Fallback: aktuelle Employee-Felder)
        month_start = month.replace(day=1)
        contract = await self._get_contract_at(employee.id, month_start)
        hourly_rate = float(contract.hourly_rate) if contract else float(employee.hourly_rate)
        monthly_limit = float(contract.monthly_hours_limit) if (contract and contract.monthly_hours_limit) else (float(employee.monthly_hours_limit) if employee.monthly_hours_limit else None)
        annual_limit = float(contract.annual_salary_limit) if (contract and contract.annual_salary_limit) else float(employee.annual_salary_limit or 6672)

        # Abgeschlossene Dienste des Monats
        month_end = (month.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        shifts_result = await self.db.execute(
            select(Shift).where(
                Shift.employee_id == employee_id,
                Shift.date >= month,
                Shift.date <= month_end,
                Shift.status.in_(["completed", "confirmed"]),
            )
        )
        shifts = shifts_result.scalars().all()

        # Übertrag aus Vormonat
        carryover_result = await self.db.execute(
            select(HoursCarryover).where(
                HoursCarryover.employee_id == employee_id,
                HoursCarryover.to_month == month,
            ).order_by(HoursCarryover.created_at.desc()).limit(1)
        )
        carryover_entry = carryover_result.scalar_one_or_none()
        carryover_hours = float(carryover_entry.hours) if carryover_entry else 0.0

        total_hours = 0.0
        total_gross = 0.0
        surcharge_hours: dict[str, float] = defaultdict(float)
        surcharge_amounts: dict[str, float] = defaultdict(float)

        for shift in shifts:
            net_hours = self._calc_net_hours(shift)
            base_pay = net_hours * hourly_rate
            surcharges = self._calc_surcharges(shift, hourly_rate)

            total_hours += net_hours
            total_gross += base_pay + sum(surcharges["amounts"].values())

            for k, v in surcharges["hours"].items():
                surcharge_hours[k] += v
            for k, v in surcharges["amounts"].items():
                surcharge_amounts[k] += v

        paid_hours = total_hours + carryover_hours
        new_carryover = 0.0

        if monthly_limit:
            new_carryover = paid_hours - monthly_limit
            paid_hours = min(paid_hours, monthly_limit)

        # YTD berechnen
        year_start = month.replace(month=1, day=1)
        ytd_result = await self.db.execute(
            select(PayrollEntry).where(
                PayrollEntry.employee_id == employee_id,
                PayrollEntry.month >= year_start,
                PayrollEntry.month < month,
                PayrollEntry.status.in_(["approved", "paid"]),
            )
        )
        prev_entries = ytd_result.scalars().all()
        ytd_gross = sum(float(e.total_gross or 0) for e in prev_entries)
        ytd_gross += total_gross
        annual_limit_remaining = annual_limit - ytd_gross

        entry = PayrollEntry(
            tenant_id=employee.tenant_id,
            employee_id=employee_id,
            month=month,
            planned_hours=monthly_limit,
            actual_hours=round(total_hours, 2),
            carryover_hours=round(carryover_hours, 2),
            paid_hours=round(paid_hours, 2),
            early_hours=round(surcharge_hours.get("early", 0), 2),
            late_hours=round(surcharge_hours.get("late", 0), 2),
            night_hours=round(surcharge_hours.get("night", 0), 2),
            weekend_hours=round(surcharge_hours.get("weekend", 0), 2),
            sunday_hours=round(surcharge_hours.get("sunday", 0), 2),
            holiday_hours=round(surcharge_hours.get("holiday", 0), 2),
            base_wage=round(paid_hours * hourly_rate, 2),
            early_surcharge=round(surcharge_amounts.get("early", 0), 2),
            late_surcharge=round(surcharge_amounts.get("late", 0), 2),
            night_surcharge=round(surcharge_amounts.get("night", 0), 2),
            weekend_surcharge=round(surcharge_amounts.get("weekend", 0), 2),
            sunday_surcharge=round(surcharge_amounts.get("sunday", 0), 2),
            holiday_surcharge=round(surcharge_amounts.get("holiday", 0), 2),
            total_gross=round(total_gross, 2),
            ytd_gross=round(ytd_gross, 2),
            annual_limit_remaining=round(annual_limit_remaining, 2),
        )
        return entry, new_carryover

    def _calc_net_hours(self, shift) -> float:
        start = datetime.combine(shift.date, shift.start_time)
        end = datetime.combine(shift.date, shift.end_time)
        if end < start:
            end += timedelta(days=1)
        gross_minutes = (end - start).total_seconds() / 60
        net_minutes = gross_minutes - shift.break_minutes
        return max(0, net_minutes / 60)

    def _calc_surcharges(self, shift, hourly_rate: float) -> dict:
        """Berechnet Zuschlagsstunden und -beträge für einen Dienst."""
        hours_by_type: dict[str, float] = defaultdict(float)
        amounts_by_type: dict[str, float] = defaultdict(float)

        holiday_ok, _ = is_holiday(shift.date)
        is_sunday = shift.date.weekday() == 6
        is_saturday = shift.date.weekday() == 5

        start_dt = datetime.combine(shift.date, shift.start_time)
        end_dt = datetime.combine(shift.date, shift.end_time)
        if end_dt < start_dt:
            end_dt += timedelta(days=1)

        net_hours = self._calc_net_hours(shift)

        if holiday_ok:
            hours_by_type["holiday"] += net_hours
            amounts_by_type["holiday"] += net_hours * hourly_rate * SURCHARGE_RATES["holiday"]
        elif is_sunday:
            hours_by_type["sunday"] += net_hours
            amounts_by_type["sunday"] += net_hours * hourly_rate * SURCHARGE_RATES["sunday"]
        elif is_saturday:
            hours_by_type["weekend"] += net_hours
            amounts_by_type["weekend"] += net_hours * hourly_rate * SURCHARGE_RATES["weekend"]

        # Zeit-Zuschläge (unabhängig vom Wochentag)
        current = start_dt
        while current < end_dt:
            next_tick = current + timedelta(hours=1)
            if next_tick > end_dt:
                next_tick = end_dt
            h = current.hour
            fraction = (next_tick - current).total_seconds() / 3600

            if h < 6:  # Früh (00–06)
                hours_by_type["early"] += fraction
                amounts_by_type["early"] += fraction * hourly_rate * SURCHARGE_RATES["early"]
            if h >= 20:  # Spät (20–24)
                hours_by_type["late"] += fraction
                amounts_by_type["late"] += fraction * hourly_rate * SURCHARGE_RATES["late"]
            if h >= 23 or h < 6:  # Nacht (23–06)
                hours_by_type["night"] += fraction
                amounts_by_type["night"] += fraction * hourly_rate * SURCHARGE_RATES["night"]

            current = next_tick

        return {"hours": dict(hours_by_type), "amounts": dict(amounts_by_type)}
