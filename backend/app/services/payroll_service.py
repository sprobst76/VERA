"""
PayrollService: Monatliche Lohnabrechnung mit Zuschlägen.
Zuschlagsätze gemäß §3b EStG (steuerlich begünstigt).

Unterstützt:
- Mehrere Vertragsperioden pro Monat (exakter Split bei Stundenlohnänderung mid-month)
- Jahressoll (annual_hours_target) mit anteiliger Berechnung bei unterjährigem Eintritt
- YTD-Stunden-Tracking parallel zum bestehenden YTD-Brutto-Tracking (Minijob)
"""
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta, time
from typing import TYPE_CHECKING

from sqlalchemy import func, or_, select
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

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _get_contract_at(self, employee_id: uuid.UUID, target_date: date):
        """Gibt den zum target_date gültigen Vertragseintrag zurück, oder None."""
        from app.models.contract_history import ContractHistory
        result = await self.db.execute(
            select(ContractHistory)
            .where(
                ContractHistory.employee_id == employee_id,
                ContractHistory.valid_from <= target_date,
                or_(ContractHistory.valid_to.is_(None), ContractHistory.valid_to > target_date),
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _get_contracts_for_month(
        self, employee_id: uuid.UUID, month_start: date, month_end: date
    ) -> list[tuple]:
        """
        Gibt alle Vertragsperioden zurück, die sich mit dem Monat überschneiden.
        Rückgabe: list[(contract, period_start_in_month, period_end_exclusive_in_month)]
        """
        from app.models.contract_history import ContractHistory
        result = await self.db.execute(
            select(ContractHistory)
            .where(
                ContractHistory.employee_id == employee_id,
                ContractHistory.valid_from <= month_end,
                or_(
                    ContractHistory.valid_to.is_(None),
                    ContractHistory.valid_to > month_start,
                ),
            )
            .order_by(ContractHistory.valid_from)
        )
        contracts = result.scalars().all()

        periods = []
        for c in contracts:
            ps = max(c.valid_from, month_start)
            pe = c.valid_to if c.valid_to else (month_end + timedelta(days=1))
            pe = min(pe, month_end + timedelta(days=1))
            periods.append((c, ps, pe))
        return periods

    async def _get_ytd_hours(self, employee_id: uuid.UUID, month_start: date) -> float:
        """Summiert paid_hours aus approved/paid Einträgen des laufenden Jahres (vor diesem Monat)."""
        from app.models.payroll import PayrollEntry
        year_start = month_start.replace(month=1, day=1)
        result = await self.db.execute(
            select(func.sum(PayrollEntry.paid_hours)).where(
                PayrollEntry.employee_id == employee_id,
                PayrollEntry.month >= year_start,
                PayrollEntry.month < month_start,
                PayrollEntry.status.in_(["approved", "paid"]),
            )
        )
        return float(result.scalar() or 0)

    async def _get_first_contract_date_this_year(
        self, employee_id: uuid.UUID, year: int
    ) -> date | None:
        """Frühestes valid_from eines Vertrags im gegebenen Jahr (für anteiliges Jahressoll)."""
        from app.models.contract_history import ContractHistory
        year_start = date(year, 1, 1)
        year_end = date(year, 12, 31)
        result = await self.db.execute(
            select(func.min(ContractHistory.valid_from)).where(
                ContractHistory.employee_id == employee_id,
                ContractHistory.valid_from <= year_end,
            )
        )
        first = result.scalar()
        if first is None:
            return None
        # Wenn der allererste Vertrag vor dem aktuellen Jahr liegt, gilt 1.1.
        return first if first >= year_start else None

    # ── Hauptberechnung ───────────────────────────────────────────────────────

    async def calculate_monthly_payroll(self, employee_id, month: date):
        from app.models.employee import Employee
        from app.models.payroll import PayrollEntry, HoursCarryover
        from app.models.shift import Shift
        from app.models.tenant import Tenant
        from app.api.v1.admin_settings import DEFAULT_SURCHARGE_RATES

        # Employee laden
        emp_result = await self.db.execute(select(Employee).where(Employee.id == employee_id))
        employee = emp_result.scalar_one()

        # Zuschlagsätze: Tenant-Konfiguration mit Defaults mergen
        tenant_result = await self.db.execute(select(Tenant).where(Tenant.id == employee.tenant_id))
        tenant = tenant_result.scalar_one_or_none()
        surcharge_cfg = ((tenant.settings or {}).get("surcharges", {}) if tenant else {})
        rates = {k: surcharge_cfg.get(k, v) for k, v in DEFAULT_SURCHARGE_RATES.items()}

        month_start = month.replace(day=1)
        month_end = (month.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)

        # Alle Vertragsperioden die diesen Monat berühren
        contract_periods = await self._get_contracts_for_month(employee.id, month_start, month_end)

        # Primärvertrag = der letzte im Monat (für display-rate, annual_hours_target, limits)
        primary_contract = contract_periods[-1][0] if contract_periods else None

        # Monatslohn (Teilzeit/Vollzeit): direkt als Grundlohn statt Stunden × Rate
        primary_monthly_salary = (
            float(primary_contract.monthly_salary)
            if (primary_contract and primary_contract.monthly_salary)
            else (float(employee.monthly_salary) if employee.monthly_salary else None)
        )

        # Fallback auf Employee-Felder wenn kein Vertragseintrag vorhanden
        primary_rate = (
            float(primary_contract.hourly_rate) if primary_contract
            else float(employee.hourly_rate)
        )
        monthly_limit = (
            float(primary_contract.monthly_hours_limit)
            if (primary_contract and primary_contract.monthly_hours_limit)
            else (float(employee.monthly_hours_limit) if employee.monthly_hours_limit else None)
        )
        annual_limit = (
            float(primary_contract.annual_salary_limit)
            if (primary_contract and primary_contract.annual_salary_limit)
            else float(employee.annual_salary_limit or 6672)
        )
        annual_hours_target_raw = (
            float(primary_contract.annual_hours_target)
            if (primary_contract and primary_contract.annual_hours_target)
            else (float(employee.annual_hours_target) if employee.annual_hours_target else None)
        )

        # Effektiver Stundensatz für Zuschlagsberechnung bei Monatslohn
        def _effective_surcharge_rate(monthly_sal: float, c_period=None) -> float:
            """Berechnet effektiven Stundensatz für §3b-Zuschläge bei Monatslohn."""
            wh = float(c_period.weekly_hours) if (c_period and c_period.weekly_hours) else (
                float(employee.weekly_hours) if employee.weekly_hours else None
            )
            aht = float(c_period.annual_hours_target) if (c_period and c_period.annual_hours_target) else (
                float(employee.annual_hours_target) if employee.annual_hours_target else None
            )
            if wh:
                return monthly_sal / (wh * 52 / 12)
            elif aht:
                return monthly_sal / (aht / 12)
            else:
                return monthly_sal / 160  # Fallback: 160 h / Monat

        # Hilfsfunktion: Welcher Vertrag gilt an einem bestimmten Datum?
        def _rate_for_date(d: date) -> float:
            for c, ps, pe in contract_periods:
                if ps <= d < pe:
                    # Bei Monatslohn: effektiven Stundensatz für Zuschläge berechnen
                    if c.monthly_salary:
                        return _effective_surcharge_rate(float(c.monthly_salary), c)
                    return float(c.hourly_rate)
            # Primärvertrag Fallback
            if primary_monthly_salary:
                return _effective_surcharge_rate(primary_monthly_salary, primary_contract)
            return primary_rate

        # Abgeschlossene Dienste des Monats
        shifts_result = await self.db.execute(
            select(Shift).where(
                Shift.employee_id == employee_id,
                Shift.date >= month_start,
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

        # ── Dienste berechnen ──────────────────────────────────────────────────
        total_hours = 0.0
        base_wage_sum = 0.0   # Grundlohn (ohne Zuschläge), exakt per Dienst
        total_gross = 0.0
        surcharge_hours: dict[str, float] = defaultdict(float)
        surcharge_amounts: dict[str, float] = defaultdict(float)

        # Für wage_details: Stunden und Betrag pro Vertragsperiode
        period_stats: dict[int, dict] = {}   # index → {from, to, rate, hours, amount}
        for idx, (c, ps, pe) in enumerate(contract_periods):
            period_stats[idx] = {
                "from": ps.isoformat(),
                "to": (pe - timedelta(days=1)).isoformat(),
                "rate": float(c.hourly_rate),
                "hours": 0.0,
                "amount": 0.0,
            }

        for shift in shifts:
            rate = _rate_for_date(shift.date)
            net_hours = self._calc_net_hours(shift)
            surcharges = self._calc_surcharges(shift, rate, rates)

            total_hours += net_hours
            # Bei Monatslohn: Grundlohn wird separat gesetzt (kein Stunden × Rate)
            if not primary_monthly_salary:
                base_pay = net_hours * rate
                base_wage_sum += base_pay
                total_gross += base_pay
            total_gross += sum(surcharges["amounts"].values())

            for k, v in surcharges["hours"].items():
                surcharge_hours[k] += v
            for k, v in surcharges["amounts"].items():
                surcharge_amounts[k] += v

            # Welcher Periode gehört dieser Dienst?
            for idx, (c, ps, pe) in enumerate(contract_periods):
                if ps <= shift.date < pe:
                    period_stats[idx]["hours"] += net_hours
                    if not c.monthly_salary:
                        period_stats[idx]["amount"] += net_hours * float(c.hourly_rate)
                    break

        # Monatslohn: Grundlohn fix (anteilig bei mehreren Perioden)
        if primary_monthly_salary:
            # Bei Monatslohn-Perioden: Grundlohn ist das monatliche Fixgehalt
            # Bei mehreren Perioden: anteilig nach Kalendertagen
            monthly_days = (month_end - month_start).days + 1
            base_wage_sum = 0.0
            if not contract_periods:
                # Kein ContractHistory-Eintrag → volles Monatsgehalt vom Employee-Feld
                base_wage_sum = primary_monthly_salary
                total_gross += primary_monthly_salary
            else:
                for idx, (c, ps, pe) in enumerate(contract_periods):
                    if c.monthly_salary:
                        days_in_period = (min(pe - timedelta(days=1), month_end) - ps).days + 1
                        period_base = float(c.monthly_salary) * (days_in_period / monthly_days)
                        base_wage_sum += period_base
                        total_gross += period_base
                        period_stats[idx]["amount"] = round(period_base, 2)

        paid_hours = total_hours + carryover_hours
        new_carryover = 0.0

        # Kein Stunden-Übertrag bei Monatslohn
        if monthly_limit and not primary_monthly_salary:
            new_carryover = max(0.0, paid_hours - monthly_limit)
            paid_hours = min(paid_hours, monthly_limit)

        # wage_details nur befüllen wenn > 1 Periode vorhanden
        wage_details = None
        if len(contract_periods) > 1:
            wage_details = {
                "splits": [
                    {
                        "from": s["from"],
                        "to": s["to"],
                        "rate": round(s["rate"], 2),
                        "hours": round(s["hours"], 2),
                        "amount": round(s["amount"], 2),
                    }
                    for s in period_stats.values()
                    if s["hours"] > 0
                ]
            }

        # ── YTD Brutto (Minijob-Tracking €) ───────────────────────────────────
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

        # ── Jahressoll (Stunden-Tracking) ─────────────────────────────────────
        monthly_hours_target = None
        annual_hours_remaining = None
        ytd_hours = 0.0

        if annual_hours_target_raw:
            monthly_hours_target = round(annual_hours_target_raw / 12, 1)

            # Anteiliges Soll bei unterjährigem Eintritt
            first_day_this_year = await self._get_first_contract_date_this_year(
                employee.id, month_start.year
            )
            if first_day_this_year and first_day_this_year > date(month_start.year, 1, 1):
                # Anzahl verbleibender Monate ab Eintrittsdatum (inkl. Eintrittmonat)
                remaining_months = 13 - first_day_this_year.month
                prorated_annual = annual_hours_target_raw * (remaining_months / 12)
            else:
                prorated_annual = annual_hours_target_raw

            ytd_hours = await self._get_ytd_hours(employee.id, month_start)
            annual_hours_remaining = round(prorated_annual - ytd_hours - paid_hours, 1)

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
            base_wage=round(base_wage_sum, 2),
            early_surcharge=round(surcharge_amounts.get("early", 0), 2),
            late_surcharge=round(surcharge_amounts.get("late", 0), 2),
            night_surcharge=round(surcharge_amounts.get("night", 0), 2),
            weekend_surcharge=round(surcharge_amounts.get("weekend", 0), 2),
            sunday_surcharge=round(surcharge_amounts.get("sunday", 0), 2),
            holiday_surcharge=round(surcharge_amounts.get("holiday", 0), 2),
            total_gross=round(total_gross, 2),
            ytd_gross=round(ytd_gross, 2),
            annual_limit_remaining=round(annual_limit_remaining, 2),
            ytd_hours=round(ytd_hours, 2),
            annual_hours_target=annual_hours_target_raw,
            annual_hours_remaining=annual_hours_remaining,
            monthly_hours_target=monthly_hours_target,
            wage_details=wage_details,
        )
        return entry, new_carryover

    # ── Dienst-Berechnungen ───────────────────────────────────────────────────

    def _use_actual_times(self, shift) -> bool:
        """True wenn bestätigte Ist-Zeiten für Abrechnung verwendet werden sollen."""
        return (
            getattr(shift, "time_correction_status", None) == "confirmed"
            and shift.actual_start is not None
            and shift.actual_end is not None
        )

    def _calc_net_hours(self, shift) -> float:
        if self._use_actual_times(shift):
            start = datetime.combine(shift.date, shift.actual_start)
            end = datetime.combine(shift.date, shift.actual_end)
            break_min = (
                shift.actual_break_minutes
                if shift.actual_break_minutes is not None
                else shift.break_minutes
            )
        else:
            start = datetime.combine(shift.date, shift.start_time)
            end = datetime.combine(shift.date, shift.end_time)
            break_min = shift.break_minutes
        if end < start:
            end += timedelta(days=1)
        gross_minutes = (end - start).total_seconds() / 60
        net_minutes = gross_minutes - break_min
        return max(0, net_minutes / 60)

    def _calc_surcharges(self, shift, hourly_rate: float, rates: dict | None = None) -> dict:
        """Berechnet Zuschlagsstunden und -beträge für einen Dienst."""
        if rates is None:
            rates = SURCHARGE_RATES
        hours_by_type: dict[str, float] = defaultdict(float)
        amounts_by_type: dict[str, float] = defaultdict(float)

        holiday_ok, _ = is_holiday(shift.date)
        is_sunday = shift.date.weekday() == 6
        is_saturday = shift.date.weekday() == 5

        if self._use_actual_times(shift):
            start_dt = datetime.combine(shift.date, shift.actual_start)
            end_dt = datetime.combine(shift.date, shift.actual_end)
        else:
            start_dt = datetime.combine(shift.date, shift.start_time)
            end_dt = datetime.combine(shift.date, shift.end_time)
        if end_dt < start_dt:
            end_dt += timedelta(days=1)

        net_hours = self._calc_net_hours(shift)

        if holiday_ok:
            hours_by_type["holiday"] += net_hours
            amounts_by_type["holiday"] += net_hours * hourly_rate * rates["holiday"]
        elif is_sunday:
            hours_by_type["sunday"] += net_hours
            amounts_by_type["sunday"] += net_hours * hourly_rate * rates["sunday"]
        elif is_saturday:
            hours_by_type["weekend"] += net_hours
            amounts_by_type["weekend"] += net_hours * hourly_rate * rates["weekend"]

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
                amounts_by_type["early"] += fraction * hourly_rate * rates["early"]
            if h >= 20:  # Spät (20–24)
                hours_by_type["late"] += fraction
                amounts_by_type["late"] += fraction * hourly_rate * rates["late"]
            if h >= 23 or h < 6:  # Nacht (23–06)
                hours_by_type["night"] += fraction
                amounts_by_type["night"] += fraction * hourly_rate * rates["night"]

            current = next_tick

        return {"hours": dict(hours_by_type), "amounts": dict(amounts_by_type)}
