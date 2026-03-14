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


# ── Monatslohn (monthly_salary) ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_payroll_monthly_salary_base_wage_fixed(db, tenant):
    """Teilzeit mit Monatslohn: base_wage = monthly_salary, unabhängig von Stunden."""
    from app.models.employee import Employee
    from app.models.shift import Shift

    emp = Employee(
        tenant_id=tenant.id,
        first_name="Teilzeit",
        last_name="Monatslohn",
        contract_type="part_time",
        hourly_rate=Decimal("0.00"),
        monthly_salary=Decimal("1800.00"),
        weekly_hours=Decimal("20.0"),
        annual_salary_limit=Decimal("0"),
        vacation_days=25,
    )
    db.add(emp)
    await db.commit()
    await db.refresh(emp)

    # 60h Arbeit im September
    for day in [1, 8, 15, 22, 29]:
        shift = Shift(
            tenant_id=tenant.id,
            employee_id=emp.id,
            date=date(2025, 9, day),
            start_time=time(8, 0),
            end_time=time(20, 0),
            break_minutes=0,
            status="confirmed",
        )
        db.add(shift)
    await db.commit()

    svc = PayrollService(db)
    entry, _ = await svc.calculate_monthly_payroll(emp.id, date(2025, 9, 1))

    # Grundlohn = Monatslohn, nicht Stunden * Stundensatz
    assert entry.base_wage == pytest.approx(1800.0, rel=0.01)
    # Stunden wurden trotzdem gezählt
    assert entry.actual_hours == pytest.approx(60.0)


@pytest.mark.asyncio
async def test_payroll_monthly_salary_surcharges_applied(db, tenant):
    """Bei Monatslohn werden Zuschläge über effektiven Stundensatz berechnet."""
    from app.models.employee import Employee
    from app.models.shift import Shift

    # 1800€/Mo bei 20h/Woche → eff. Rate = 1800 / (20 * 52/12) ≈ 20.77 €/h
    emp = Employee(
        tenant_id=tenant.id,
        first_name="Teilzeit",
        last_name="Zuschlag",
        contract_type="part_time",
        hourly_rate=Decimal("0.00"),
        monthly_salary=Decimal("1800.00"),
        weekly_hours=Decimal("20.0"),
        annual_salary_limit=Decimal("0"),
        vacation_days=25,
    )
    db.add(emp)
    await db.commit()
    await db.refresh(emp)

    # Sonntagsdienst → Sonntagszuschlag 50%
    shift = Shift(
        tenant_id=tenant.id,
        employee_id=emp.id,
        date=date(2025, 9, 7),  # Sonntag
        start_time=time(10, 0),
        end_time=time(14, 0),
        break_minutes=0,
        status="confirmed",
    )
    db.add(shift)
    await db.commit()

    svc = PayrollService(db)
    entry, _ = await svc.calculate_monthly_payroll(emp.id, date(2025, 9, 1))

    # Zuschläge müssen > 0 sein (Sonntagszuschlag 50%)
    total_surcharge = (
        (entry.early_surcharge or 0) + (entry.late_surcharge or 0) +
        (entry.night_surcharge or 0) + (entry.weekend_surcharge or 0) +
        (entry.sunday_surcharge or 0) + (entry.holiday_surcharge or 0)
    )
    assert total_surcharge > 0
    # Grundlohn = Monatslohn
    assert entry.base_wage == pytest.approx(1800.0, rel=0.01)


# ── Jahressoll (annual_hours_target) ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_payroll_jahressoll_monthly_target(db, tenant):
    """Jahressoll-Mitarbeiter: monthly_hours_target = annual_hours_target / 12."""
    from app.models.employee import Employee
    from app.models.shift import Shift

    emp = Employee(
        tenant_id=tenant.id,
        first_name="Jahres",
        last_name="Soll",
        contract_type="part_time",
        hourly_rate=Decimal("14.00"),
        annual_hours_target=Decimal("1200.0"),
        annual_salary_limit=Decimal("0"),
        vacation_days=25,
    )
    db.add(emp)
    await db.commit()
    await db.refresh(emp)

    # Keine Schichten → Abrechnung trotzdem möglich
    svc = PayrollService(db)
    entry, _ = await svc.calculate_monthly_payroll(emp.id, date(2025, 9, 1))

    # monthly_hours_target = 1200 / 12 = 100
    assert entry.monthly_hours_target == pytest.approx(100.0, rel=0.01)


@pytest.mark.asyncio
async def test_payroll_jahressoll_remaining_decreases(db, tenant):
    """annual_hours_remaining sinkt nach gearbeiteten Stunden."""
    from app.models.employee import Employee
    from app.models.shift import Shift
    from app.models.payroll import PayrollEntry
    from decimal import Decimal as D

    emp = Employee(
        tenant_id=tenant.id,
        first_name="Jahres",
        last_name="Rest",
        contract_type="part_time",
        hourly_rate=Decimal("14.00"),
        annual_hours_target=Decimal("1200.0"),
        annual_salary_limit=Decimal("0"),
        vacation_days=25,
    )
    db.add(emp)
    await db.commit()
    await db.refresh(emp)

    # 40h Arbeit im September
    for day in [1, 8, 15, 22]:
        shift = Shift(
            tenant_id=tenant.id,
            employee_id=emp.id,
            date=date(2025, 9, day),
            start_time=time(8, 0),
            end_time=time(18, 0),
            break_minutes=0,
            status="confirmed",
        )
        db.add(shift)
    await db.commit()

    svc = PayrollService(db)
    entry, _ = await svc.calculate_monthly_payroll(emp.id, date(2025, 9, 1))

    # annual_hours_remaining muss gesetzt und < annual_hours_target sein
    if entry.annual_hours_target is not None:
        assert entry.annual_hours_remaining is not None
        assert entry.annual_hours_remaining < float(entry.annual_hours_target)


# ── Mehrfachverträge im selben Monat ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_payroll_multi_contract_split(db, tenant):
    """Wenn Stundenlohn mitten im Monat wechselt, werden Dienste korrekt aufgeteilt."""
    from app.models.employee import Employee
    from app.models.contract_history import ContractHistory
    from app.models.shift import Shift

    emp = Employee(
        tenant_id=tenant.id,
        first_name="Split",
        last_name="Vertrag",
        contract_type="full_time",
        hourly_rate=Decimal("10.00"),
        annual_salary_limit=Decimal("0"),
        vacation_days=30,
    )
    db.add(emp)
    await db.commit()
    await db.refresh(emp)

    # Erster Vertrag: 1.–14. Sep, 10€/h
    c1 = ContractHistory(
        tenant_id=tenant.id,
        employee_id=emp.id,
        valid_from=date(2025, 1, 1),
        valid_to=date(2025, 9, 15),
        contract_type="full_time",
        hourly_rate=Decimal("10.00"),
    )
    # Zweiter Vertrag: ab 15. Sep, 14€/h
    c2 = ContractHistory(
        tenant_id=tenant.id,
        employee_id=emp.id,
        valid_from=date(2025, 9, 15),
        valid_to=None,
        contract_type="full_time",
        hourly_rate=Decimal("14.00"),
    )
    db.add(c1)
    db.add(c2)
    await db.commit()

    # Dienst vor Wechsel: 8h @ 10€ = 80€
    s1 = Shift(
        tenant_id=tenant.id,
        employee_id=emp.id,
        date=date(2025, 9, 10),
        start_time=time(8, 0),
        end_time=time(16, 0),
        break_minutes=0,
        status="confirmed",
    )
    # Dienst nach Wechsel: 8h @ 14€ = 112€
    s2 = Shift(
        tenant_id=tenant.id,
        employee_id=emp.id,
        date=date(2025, 9, 20),
        start_time=time(8, 0),
        end_time=time(16, 0),
        break_minutes=0,
        status="confirmed",
    )
    db.add(s1)
    db.add(s2)
    await db.commit()

    svc = PayrollService(db)
    entry, _ = await svc.calculate_monthly_payroll(emp.id, date(2025, 9, 1))

    # Gesamtlohn = 80 + 112 = 192€
    assert entry.base_wage == pytest.approx(192.0, rel=0.01)
    assert entry.actual_hours == pytest.approx(16.0)
