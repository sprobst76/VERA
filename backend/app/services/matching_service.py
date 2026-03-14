"""
MatchingService – regelbasiertes Mitarbeiter-Matching für offene Dienste (MVP).

Scoring (max 90 Punkte):
+30: Keine Terminkonflikte (andere Dienste an demselben Tag + Urlaubsabwesenheit)
+25: Qualifikationen passen (wenn Dienst required_qualifications hat)
+20: Stundenkontingent verfügbar (Minijob: Jahres-€-Limit noch nicht voll)
+15: Ruhezeit eingehalten (≥11h Abstand zu benachbarten Diensten)
"""
import uuid
from datetime import date, time, timedelta, datetime, timezone
from decimal import Decimal

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Employee
from app.models.shift import Shift
from app.models.absence import EmployeeAbsence
from app.models.payroll import PayrollEntry


class MatchingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def suggest_employees(
        self,
        shift_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> list[dict]:
        """
        Gibt sortierte Kandidatenliste für einen Dienst zurück.
        Nur aktive Mitarbeiter des gleichen Tenants werden bewertet.
        """
        # Dienst laden
        shift_result = await self.db.execute(
            select(Shift).where(Shift.id == shift_id, Shift.tenant_id == tenant_id)
        )
        shift = shift_result.scalar_one_or_none()
        if not shift:
            return []

        # Aktive Mitarbeiter des Tenants
        emp_result = await self.db.execute(
            select(Employee).where(
                Employee.tenant_id == tenant_id,
                Employee.is_active == True,
            ).order_by(Employee.last_name)
        )
        employees = emp_result.scalars().all()

        # Bestehende Dienste am gleichen Tag (für Konfliktprüfung)
        day_shifts_result = await self.db.execute(
            select(Shift).where(
                Shift.tenant_id == tenant_id,
                Shift.date == shift.date,
                Shift.id != shift_id,
                Shift.status.not_in(["cancelled", "cancelled_absence"]),
            )
        )
        day_shifts = day_shifts_result.scalars().all()
        # employee_id → list of shifts on that day
        busy_employees: set[uuid.UUID] = {s.employee_id for s in day_shifts if s.employee_id}

        # Abwesenheiten am gleichen Tag
        absence_result = await self.db.execute(
            select(EmployeeAbsence).where(
                EmployeeAbsence.tenant_id == tenant_id,
                EmployeeAbsence.status == "approved",
                EmployeeAbsence.start_date <= shift.date,
                EmployeeAbsence.end_date >= shift.date,
            )
        )
        absent_employees: set[uuid.UUID] = {a.employee_id for a in absence_result.scalars().all()}

        # YTD-Brutto für Minijob-Limit-Check (aktuelles Jahr)
        year_start = shift.date.replace(month=1, day=1)
        ytd_result = await self.db.execute(
            select(
                PayrollEntry.employee_id,
                func.sum(PayrollEntry.total_gross).label("ytd_gross"),
            )
            .where(
                PayrollEntry.tenant_id == tenant_id,
                PayrollEntry.month >= year_start,
                PayrollEntry.month <= shift.date,
                PayrollEntry.status.in_(["approved", "paid"]),
            )
            .group_by(PayrollEntry.employee_id)
        )
        ytd_map: dict[uuid.UUID, float] = {
            row.employee_id: float(row.ytd_gross or 0) for row in ytd_result.all()
        }

        # Dienste ±1 Tag für Ruhezeit (11h-Regel)
        adjacent_date_start = shift.date - timedelta(days=1)
        adjacent_date_end = shift.date + timedelta(days=1)
        adj_shifts_result = await self.db.execute(
            select(Shift).where(
                Shift.tenant_id == tenant_id,
                Shift.date >= adjacent_date_start,
                Shift.date <= adjacent_date_end,
                Shift.id != shift_id,
                Shift.status.not_in(["cancelled", "cancelled_absence"]),
            )
        )
        adj_shifts = adj_shifts_result.scalars().all()
        # employee_id → list of adjacent shifts
        adj_map: dict[uuid.UUID, list] = {}
        for s in adj_shifts:
            if s.employee_id:
                adj_map.setdefault(s.employee_id, []).append(s)

        candidates = []
        for emp in employees:
            # Skip if this shift already has this employee assigned
            if shift.employee_id == emp.id:
                continue

            score = 0
            reasons = []
            blockers = []

            # ── Konfliktprüfung (+30) ─────────────────────────────────────
            has_conflict = emp.id in busy_employees or emp.id in absent_employees
            if not has_conflict:
                score += 30
                reasons.append("Kein Terminkonflikt")
            else:
                if emp.id in absent_employees:
                    blockers.append("Abwesenheit eingetragen")
                else:
                    blockers.append("Anderer Dienst an diesem Tag")

            # ── Qualifikationen (+25) ─────────────────────────────────────
            # Dienst hat keine required_qualifications-Felder in DB → immer +25
            score += 25
            reasons.append("Qualifikation ok")

            # ── Stundenkontingent (+20) ───────────────────────────────────
            if emp.contract_type == "minijob":
                annual_limit = float(emp.annual_salary_limit or 6672)
                ytd = ytd_map.get(emp.id, 0.0)
                # Geschätzter Verdienst für diesen Dienst
                shift_hours = _calc_shift_hours(shift)
                estimated_pay = shift_hours * float(emp.hourly_rate or 12)
                if ytd + estimated_pay <= annual_limit:
                    score += 20
                    reasons.append("Jahres-Limit verfügbar")
                else:
                    blockers.append(f"Jahres-Limit fast erreicht ({ytd:.0f} / {annual_limit:.0f} €)")
            else:
                score += 20
                reasons.append("Kein Stundenlimit")

            # ── Ruhezeit (+15) ────────────────────────────────────────────
            rest_ok = _check_rest_period(emp.id, shift, adj_map.get(emp.id, []))
            if rest_ok:
                score += 15
                reasons.append("Ruhezeit ≥ 11h")
            else:
                blockers.append("Ruhezeit < 11h")

            candidates.append({
                "employee_id": str(emp.id),
                "first_name": emp.first_name,
                "last_name": emp.last_name,
                "contract_type": emp.contract_type,
                "score": score,
                "reasons": reasons,
                "blockers": blockers,
            })

        # Sortieren nach Score (absteigend), dann Name
        return sorted(candidates, key=lambda x: (-x["score"], x["last_name"]))


def _calc_shift_hours(shift: Shift) -> float:
    """Berechnet Netto-Stunden eines Dienstes."""
    start = datetime.combine(shift.date, shift.start_time)
    end = datetime.combine(shift.date, shift.end_time)
    if end <= start:
        end += timedelta(days=1)
    gross = (end - start).total_seconds() / 3600
    return max(0.0, gross - (shift.break_minutes or 0) / 60)


def _check_rest_period(employee_id: uuid.UUID, shift: Shift, adjacent_shifts: list) -> bool:
    """Prüft ob min. 11h Ruhezeit vor und nach dem Dienst eingehalten wird."""
    shift_start = datetime.combine(shift.date, shift.start_time)
    shift_end = datetime.combine(shift.date, shift.end_time)
    if shift_end <= shift_start:
        shift_end += timedelta(days=1)

    for adj in adjacent_shifts:
        if adj.employee_id != employee_id:
            continue
        adj_start = datetime.combine(adj.date, adj.start_time)
        adj_end = datetime.combine(adj.date, adj.end_time)
        if adj_end <= adj_start:
            adj_end += timedelta(days=1)

        # Ruhezeit VOR dem neuen Dienst
        if adj_end <= shift_start:
            gap = (shift_start - adj_end).total_seconds() / 3600
            if gap < 11:
                return False
        # Ruhezeit NACH dem neuen Dienst
        elif adj_start >= shift_end:
            gap = (adj_start - shift_end).total_seconds() / 3600
            if gap < 11:
                return False

    return True
