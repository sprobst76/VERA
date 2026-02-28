"""
Tests für PayrollService – _calc_net_hours, _calc_surcharges (§3b EStG),
calculate_monthly_payroll (Integration mit SQLite-DB).
"""
import uuid
from datetime import date, time, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
import pytest_asyncio

from app.services.payroll_service import PayrollService, SURCHARGE_RATES


# ── Stub-Hilfe ────────────────────────────────────────────────────────────────

def make_shift(shift_date: date, start: str, end: str, break_minutes: int = 0, employee_id=None):
    h_s, m_s = map(int, start.split(":"))
    h_e, m_e = map(int, end.split(":"))
    return SimpleNamespace(
        date=shift_date,
        start_time=time(h_s, m_s),
        end_time=time(h_e, m_e),
        break_minutes=break_minutes,
        employee_id=employee_id or uuid.uuid4(),
        status="confirmed",
    )


# ── _calc_net_hours ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_net_hours_normal_shift(db):
    """08:00–16:00 mit 30min Pause → 7.5h."""
    svc = PayrollService(db)
    shift = make_shift(date(2025, 9, 1), "08:00", "16:00", break_minutes=30)
    assert svc._calc_net_hours(shift) == pytest.approx(7.5)


@pytest.mark.asyncio
async def test_net_hours_night_shift(db):
    """23:00–07:00 ohne Pause → 8.0h (Mitternachtsübergang)."""
    svc = PayrollService(db)
    shift = make_shift(date(2025, 9, 1), "23:00", "07:00", break_minutes=0)
    assert svc._calc_net_hours(shift) == pytest.approx(8.0)


# ── _calc_surcharges (§3b EStG) ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_surcharges_normal_day_none(db):
    """Tagschicht Mo 09:00–17:00 → keine Zuschläge."""
    svc = PayrollService(db)
    shift = make_shift(date(2025, 9, 1), "09:00", "17:00")  # Montag
    result = svc._calc_surcharges(shift, hourly_rate=14.0)
    assert result["amounts"].get("early", 0) == pytest.approx(0)
    assert result["amounts"].get("late", 0) == pytest.approx(0)
    assert result["amounts"].get("night", 0) == pytest.approx(0)
    assert result["amounts"].get("weekend", 0) == pytest.approx(0)
    assert result["amounts"].get("sunday", 0) == pytest.approx(0)


@pytest.mark.asyncio
async def test_surcharges_early_shift(db):
    """Frühschicht Mo 05:00–09:00 → 1h Frühzuschlag (05–06) + Nachtzuschlag (05–06)."""
    svc = PayrollService(db)
    shift = make_shift(date(2025, 9, 1), "05:00", "09:00")  # Montag
    result = svc._calc_surcharges(shift, hourly_rate=10.0)
    # 1 Stunde vor 06:00 → early 12.5% → 1 * 10 * 0.125 = 1.25
    assert result["amounts"].get("early", 0) == pytest.approx(1.25)
    assert result["hours"].get("early", 0) == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_surcharges_late_shift(db):
    """Spätschicht Mo 20:00–23:00 → 3h Spätzuschlag."""
    svc = PayrollService(db)
    shift = make_shift(date(2025, 9, 1), "20:00", "23:00")  # Montag
    result = svc._calc_surcharges(shift, hourly_rate=10.0)
    # 3h ab 20:00 → late 12.5% → 3 * 10 * 0.125 = 3.75
    assert result["amounts"].get("late", 0) == pytest.approx(3.75)
    assert result["hours"].get("late", 0) == pytest.approx(3.0)


@pytest.mark.asyncio
async def test_surcharges_night_shift(db):
    """Nachtschicht Mo 23:00–03:00 → Nacht- + Frühzuschlag."""
    svc = PayrollService(db)
    shift = make_shift(date(2025, 9, 1), "23:00", "03:00")  # Mo→Di
    result = svc._calc_surcharges(shift, hourly_rate=10.0)
    # 4h Nacht (23–06): 1h Spät (23:00) + 4h Nacht gesamt
    assert result["hours"].get("night", 0) == pytest.approx(4.0)
    assert result["amounts"].get("night", 0) == pytest.approx(4 * 10 * 0.25)


@pytest.mark.asyncio
async def test_surcharges_saturday(db):
    """Samstagsschicht 10:00–14:00 → 25% Wochenendzuschlag."""
    svc = PayrollService(db)
    shift = make_shift(date(2025, 9, 6), "10:00", "14:00")  # Samstag
    result = svc._calc_surcharges(shift, hourly_rate=10.0)
    # 4h * 10€ * 0.25 = 10€
    assert result["amounts"].get("weekend", 0) == pytest.approx(10.0)
    assert result["hours"].get("weekend", 0) == pytest.approx(4.0)


@pytest.mark.asyncio
async def test_surcharges_sunday(db):
    """Sonntagsschicht 10:00–14:00 → 50% Sonntagszuschlag."""
    svc = PayrollService(db)
    shift = make_shift(date(2025, 9, 7), "10:00", "14:00")  # Sonntag
    result = svc._calc_surcharges(shift, hourly_rate=10.0)
    # 4h * 10€ * 0.50 = 20€
    assert result["amounts"].get("sunday", 0) == pytest.approx(20.0)


@pytest.mark.asyncio
async def test_surcharges_holiday_bw(db):
    """Feiertagsschicht Allerheiligen (BW) → 125% Feiertagszuschlag statt Wochentag."""
    svc = PayrollService(db)
    shift = make_shift(date(2025, 11, 1), "10:00", "14:00")  # Allerheiligen (Sa in 2025)
    result = svc._calc_surcharges(shift, hourly_rate=10.0)
    # 4h * 10€ * 1.25 = 50€; kein weekend-Zuschlag (holiday überschreibt)
    assert result["amounts"].get("holiday", 0) == pytest.approx(50.0)
    assert result["amounts"].get("weekend", 0) == pytest.approx(0)


# ── calculate_monthly_payroll (Integration) ───────────────────────────────────

@pytest.mark.asyncio
async def test_payroll_no_shifts(db, tenant):
    """Keine Schichten im Monat → actual_hours=0, base_wage=0."""
    from app.models.employee import Employee

    emp = Employee(
        tenant_id=tenant.id,
        first_name="Lohn",
        last_name="Test",
        contract_type="full_time",
        hourly_rate=Decimal("14.00"),
        annual_salary_limit=Decimal("0"),
        vacation_days=30,
    )
    db.add(emp)
    await db.commit()
    await db.refresh(emp)

    svc = PayrollService(db)
    entry, carryover = await svc.calculate_monthly_payroll(emp.id, date(2025, 9, 1))
    assert entry.actual_hours == 0.0
    assert entry.base_wage == 0.0
    assert carryover == 0.0


@pytest.mark.asyncio
async def test_payroll_simple_shift(db, tenant):
    """Eine Schicht 8h → base_wage = 8 * stundenlohn."""
    from app.models.employee import Employee
    from app.models.shift import Shift

    emp = Employee(
        tenant_id=tenant.id,
        first_name="Lohn",
        last_name="Einfach",
        contract_type="full_time",
        hourly_rate=Decimal("10.00"),
        annual_salary_limit=Decimal("0"),
        vacation_days=30,
    )
    db.add(emp)
    await db.commit()
    await db.refresh(emp)

    shift = Shift(
        tenant_id=tenant.id,
        employee_id=emp.id,
        date=date(2025, 9, 1),
        start_time=time(8, 0),
        end_time=time(16, 0),
        break_minutes=0,
        status="confirmed",
    )
    db.add(shift)
    await db.commit()

    svc = PayrollService(db)
    entry, _ = await svc.calculate_monthly_payroll(emp.id, date(2025, 9, 1))
    assert entry.actual_hours == pytest.approx(8.0)
    assert entry.base_wage == pytest.approx(80.0)


@pytest.mark.asyncio
async def test_payroll_planned_shift_not_counted(db, tenant):
    """Schicht mit status='planned' zählt NICHT für Abrechnung."""
    from app.models.employee import Employee
    from app.models.shift import Shift

    emp = Employee(
        tenant_id=tenant.id,
        first_name="Lohn",
        last_name="Planned",
        contract_type="full_time",
        hourly_rate=Decimal("10.00"),
        annual_salary_limit=Decimal("0"),
        vacation_days=30,
    )
    db.add(emp)
    await db.commit()
    await db.refresh(emp)

    shift = Shift(
        tenant_id=tenant.id,
        employee_id=emp.id,
        date=date(2025, 9, 1),
        start_time=time(8, 0),
        end_time=time(16, 0),
        break_minutes=0,
        status="planned",  # <-- nicht abrechenbar
    )
    db.add(shift)
    await db.commit()

    svc = PayrollService(db)
    entry, _ = await svc.calculate_monthly_payroll(emp.id, date(2025, 9, 1))
    assert entry.actual_hours == 0.0


@pytest.mark.asyncio
async def test_payroll_minijob_cap(db, tenant):
    """Stunden über Monatslimit → carryover_hours > 0, paid_hours == limit."""
    from app.models.employee import Employee
    from app.models.shift import Shift

    emp = Employee(
        tenant_id=tenant.id,
        first_name="Mini",
        last_name="Job",
        contract_type="minijob",
        hourly_rate=Decimal("14.00"),
        monthly_hours_limit=Decimal("20.00"),
        annual_salary_limit=Decimal("6672.00"),
        vacation_days=0,
    )
    db.add(emp)
    await db.commit()
    await db.refresh(emp)

    # 3 Schichten à 8h = 24h gesamt, Limit 20h → 4h Übertrag
    for day in [1, 8, 15]:
        shift = Shift(
            tenant_id=tenant.id,
            employee_id=emp.id,
            date=date(2025, 9, day),
            start_time=time(8, 0),
            end_time=time(16, 0),
            break_minutes=0,
            status="confirmed",
        )
        db.add(shift)
    await db.commit()

    svc = PayrollService(db)
    entry, new_carryover = await svc.calculate_monthly_payroll(emp.id, date(2025, 9, 1))
    assert entry.actual_hours == pytest.approx(24.0)
    assert entry.paid_hours == pytest.approx(20.0)
    assert new_carryover == pytest.approx(4.0)
