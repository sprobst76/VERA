"""
Compliance-Service: Automatische Validierung für alle Schichten.
Prüft Ruhezeit, Pausen und Minijob-Grenzen gemäß ArbZG.
"""
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.german_holidays import is_holiday

if TYPE_CHECKING:
    from app.models.shift import Shift
    from app.models.employee import Employee


@dataclass
class ComplianceResult:
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_ok(self) -> bool:
        return len(self.violations) == 0

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0


MINIJOB_MONTHLY_LIMIT = 556.00   # 2025
MINIJOB_ANNUAL_LIMIT  = 6672.00  # 2025
MIN_REST_HOURS        = 11
BREAK_6H_MINUTES      = 30
BREAK_9H_MINUTES      = 45


class ComplianceService:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def check_shift(self, shift: "Shift", employee: "Employee") -> ComplianceResult:
        result = ComplianceResult()

        # 1. Ruhezeit (ArbZG §5)
        await self._check_rest_period(shift, employee, result)

        # 2. Pausenpflicht (ArbZG §4)
        self._check_break(shift, result)

        # 3. Minijob-Limit
        if employee.contract_type == "minijob":
            await self._check_minijob_limit(shift, employee, result)

        # 4. Feiertag-Info
        holiday_ok, holiday_name = is_holiday(shift.date)
        if holiday_ok:
            result.warnings.append(f"Feiertag: {holiday_name}")

        return result

    async def _check_rest_period(
        self, shift: "Shift", employee: "Employee", result: ComplianceResult
    ) -> None:
        from app.models.shift import Shift

        # Letzten abgeschlossenen Dienst vor diesem finden
        prev_result = await self.db.execute(
            select(Shift)
            .where(
                and_(
                    Shift.employee_id == employee.id,
                    Shift.date < shift.date,
                    Shift.status.notin_(["cancelled", "cancelled_absence"]),
                )
            )
            .order_by(Shift.date.desc(), Shift.end_time.desc())
            .limit(1)
        )
        prev_shift = prev_result.scalar_one_or_none()

        if prev_shift:
            prev_end = datetime.combine(prev_shift.date, prev_shift.end_time)
            curr_start = datetime.combine(shift.date, shift.start_time)
            # Nachts-Dienste: end > start am gleichen Tag
            if prev_shift.end_time < prev_shift.start_time:
                prev_end += timedelta(days=1)

            rest_hours = (curr_start - prev_end).total_seconds() / 3600
            if rest_hours < MIN_REST_HOURS:
                result.violations.append(
                    f"Ruhezeit unterschritten: {rest_hours:.1f}h (min. {MIN_REST_HOURS}h)"
                )

    def _check_break(self, shift: "Shift", result: ComplianceResult) -> None:
        start = datetime.combine(shift.date, shift.start_time)
        end = datetime.combine(shift.date, shift.end_time)
        if end < start:
            end += timedelta(days=1)

        work_hours = (end - start).total_seconds() / 3600

        if work_hours > 9 and shift.break_minutes < BREAK_9H_MINUTES:
            result.violations.append(
                f"Nach 9h Arbeitszeit: mind. {BREAK_9H_MINUTES} Min Pause erforderlich"
            )
        elif work_hours > 6 and shift.break_minutes < BREAK_6H_MINUTES:
            result.violations.append(
                f"Nach 6h Arbeitszeit: mind. {BREAK_6H_MINUTES} Min Pause erforderlich"
            )

    async def _check_minijob_limit(
        self, shift: "Shift", employee: "Employee", result: ComplianceResult
    ) -> None:
        from app.models.payroll import PayrollEntry

        month_start = shift.date.replace(day=1)
        year_start = shift.date.replace(month=1, day=1)

        # Monatsgross aus bereits erfassten Payroll-Einträgen
        monthly_result = await self.db.execute(
            select(PayrollEntry).where(
                PayrollEntry.employee_id == employee.id,
                PayrollEntry.month == month_start,
            )
        )
        monthly_entry = monthly_result.scalar_one_or_none()
        if monthly_entry and monthly_entry.total_gross:
            if monthly_entry.total_gross > MINIJOB_MONTHLY_LIMIT:
                result.warnings.append(
                    f"Minijob-Monatsgrenze überschritten: {monthly_entry.total_gross:.2f}€ "
                    f"(Limit: {MINIJOB_MONTHLY_LIMIT:.2f}€)"
                )

        # Jahres-YTD
        ytd_result = await self.db.execute(
            select(func.sum(PayrollEntry.total_gross)).where(
                PayrollEntry.employee_id == employee.id,
                PayrollEntry.month >= year_start,
                PayrollEntry.month < month_start,
            )
        )
        ytd = ytd_result.scalar() or 0
        if ytd > MINIJOB_ANNUAL_LIMIT * 0.95:
            result.warnings.append(
                f"Minijob-Jahresgrenze fast erreicht: {ytd:.2f}€ von {MINIJOB_ANNUAL_LIMIT:.2f}€"
            )
        if ytd > MINIJOB_ANNUAL_LIMIT:
            result.violations.append(
                f"Minijob-Jahresgrenze überschritten: {ytd:.2f}€ (Limit: {MINIJOB_ANNUAL_LIMIT:.2f}€)"
            )
