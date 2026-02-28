"""
Tests für ComplianceService – §4 Pausen, §5 Ruhezeit, Feiertags-Warning.
_check_break und check_shift (Feiertag) laufen ohne DB.
_check_rest_period braucht DB (sucht Vorschichten).
"""
import uuid
from datetime import date, time, datetime, timezone
from types import SimpleNamespace

import pytest
import pytest_asyncio

from app.services.compliance_service import ComplianceService
from tests.conftest import auth_headers


# ── Stub-Helfer ───────────────────────────────────────────────────────────────

def make_shift(
    shift_date: date,
    start: str,
    end: str,
    break_minutes: int = 0,
    employee_id=None,
    status: str = "planned",
):
    h_s, m_s = map(int, start.split(":"))
    h_e, m_e = map(int, end.split(":"))
    return SimpleNamespace(
        id=uuid.uuid4(),
        date=shift_date,
        start_time=time(h_s, m_s),
        end_time=time(h_e, m_e),
        break_minutes=break_minutes,
        employee_id=employee_id or uuid.uuid4(),
        status=status,
    )


def make_employee(contract_type: str = "full_time"):
    return SimpleNamespace(
        id=uuid.uuid4(),
        contract_type=contract_type,
    )


# ── §4 Pausenpflicht (_check_break) ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_break_under_6h_no_pause_required(db):
    """5h Schicht ohne Pause → kein Verstoß."""
    svc = ComplianceService(db)
    shift = make_shift(date(2025, 9, 1), "08:00", "13:00", break_minutes=0)
    from app.services.compliance_service import ComplianceResult
    result = ComplianceResult()
    svc._check_break(shift, result)
    assert result.is_ok


@pytest.mark.asyncio
async def test_break_over_6h_with_30min_ok(db):
    """6.5h Schicht mit 30min Pause → kein Verstoß."""
    svc = ComplianceService(db)
    shift = make_shift(date(2025, 9, 1), "08:00", "14:30", break_minutes=30)
    from app.services.compliance_service import ComplianceResult
    result = ComplianceResult()
    svc._check_break(shift, result)
    assert result.is_ok


@pytest.mark.asyncio
async def test_break_over_6h_with_20min_violation(db):
    """6.5h Schicht mit nur 20min Pause → §4-Verstoß."""
    svc = ComplianceService(db)
    shift = make_shift(date(2025, 9, 1), "08:00", "14:30", break_minutes=20)
    from app.services.compliance_service import ComplianceResult
    result = ComplianceResult()
    svc._check_break(shift, result)
    assert not result.is_ok
    assert any("6h" in v for v in result.violations)


@pytest.mark.asyncio
async def test_break_over_9h_with_45min_ok(db):
    """9.5h Schicht mit 45min Pause → kein Verstoß."""
    svc = ComplianceService(db)
    shift = make_shift(date(2025, 9, 1), "07:00", "16:30", break_minutes=45)
    from app.services.compliance_service import ComplianceResult
    result = ComplianceResult()
    svc._check_break(shift, result)
    assert result.is_ok


@pytest.mark.asyncio
async def test_break_over_9h_with_30min_violation(db):
    """9.5h Schicht mit nur 30min Pause → §4-Verstoß (mind. 45min erforderlich)."""
    svc = ComplianceService(db)
    shift = make_shift(date(2025, 9, 1), "07:00", "16:30", break_minutes=30)
    from app.services.compliance_service import ComplianceResult
    result = ComplianceResult()
    svc._check_break(shift, result)
    assert not result.is_ok
    assert any("9h" in v for v in result.violations)


# ── §5 Ruhezeit (_check_rest_period) ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_rest_first_shift_no_violation(client, db, admin_token, tenant, admin_user):
    """Erste Schicht des Mitarbeiters (kein Vorgänger) → kein Verstoß."""
    from app.models.employee import Employee
    from app.core.security import hash_password

    emp = Employee(
        tenant_id=tenant.id,
        first_name="Test",
        last_name="User",
        contract_type="full_time",
        hourly_rate=14.0,
        annual_salary_limit=0,
        vacation_days=30,
    )
    db.add(emp)
    await db.commit()
    await db.refresh(emp)

    shift = make_shift(date(2025, 9, 1), "08:00", "16:00", employee_id=emp.id)
    employee = SimpleNamespace(id=emp.id, contract_type="full_time")

    svc = ComplianceService(db)
    result = await svc.check_shift(shift, employee)
    # Keine Ruhezeit-Verletzung (kein Vorgänger)
    assert not any("Ruhezeit" in v for v in result.violations)


@pytest.mark.asyncio
async def test_rest_14h_gap_ok(client, db, admin_token, tenant, admin_user):
    """Vorschicht endet 20:00, neue Schicht 10:00 nächsten Tag → 14h Pause → OK."""
    from app.models.employee import Employee
    from app.models.shift import Shift

    emp = Employee(
        tenant_id=tenant.id,
        first_name="Rest",
        last_name="Test",
        contract_type="full_time",
        hourly_rate=14.0,
        annual_salary_limit=0,
        vacation_days=30,
    )
    db.add(emp)
    await db.commit()
    await db.refresh(emp)

    # Vorgänger-Schicht
    prev = Shift(
        tenant_id=tenant.id,
        employee_id=emp.id,
        date=date(2025, 9, 1),
        start_time=time(12, 0),
        end_time=time(20, 0),
        break_minutes=0,
        status="confirmed",
    )
    db.add(prev)
    await db.commit()

    current_shift = make_shift(date(2025, 9, 2), "10:00", "18:00", employee_id=emp.id)
    employee = SimpleNamespace(id=emp.id, contract_type="full_time")

    svc = ComplianceService(db)
    result = await svc.check_shift(current_shift, employee)
    assert not any("Ruhezeit" in v for v in result.violations)


@pytest.mark.asyncio
async def test_rest_10h_gap_violation(client, db, admin_token, tenant, admin_user):
    """Vorschicht endet 23:00, neue Schicht 09:00 nächsten Tag → 10h Pause → Verstoß."""
    from app.models.employee import Employee
    from app.models.shift import Shift

    emp = Employee(
        tenant_id=tenant.id,
        first_name="Rest",
        last_name="Violation",
        contract_type="full_time",
        hourly_rate=14.0,
        annual_salary_limit=0,
        vacation_days=30,
    )
    db.add(emp)
    await db.commit()
    await db.refresh(emp)

    prev = Shift(
        tenant_id=tenant.id,
        employee_id=emp.id,
        date=date(2025, 9, 1),
        start_time=time(15, 0),
        end_time=time(23, 0),
        break_minutes=0,
        status="confirmed",
    )
    db.add(prev)
    await db.commit()

    current_shift = make_shift(date(2025, 9, 2), "09:00", "17:00", employee_id=emp.id)
    employee = SimpleNamespace(id=emp.id, contract_type="full_time")

    svc = ComplianceService(db)
    result = await svc.check_shift(current_shift, employee)
    assert not result.is_ok
    assert any("Ruhezeit" in v for v in result.violations)


# ── Feiertags-Warning ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_holiday_warning(db):
    """Schicht am BW-Feiertag (Allerheiligen 1.11.) → Warning."""
    svc = ComplianceService(db)
    emp_id = uuid.uuid4()
    shift = make_shift(date(2025, 11, 1), "08:00", "14:00",
                       break_minutes=0, employee_id=emp_id)
    employee = SimpleNamespace(id=emp_id, contract_type="full_time")

    result = await svc.check_shift(shift, employee)
    assert result.has_warnings
    assert any("Feiertag" in w for w in result.warnings)
