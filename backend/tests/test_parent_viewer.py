"""
Tests für die parent_viewer-Rolle.

parent_viewer darf:
- GET /shifts (alle Schichten sehen, kein eigener Employee-Account nötig)
- GET /employees (EmployeePublicOut – kein Gehalt, kein Kontakt)
- GET /employees/{id} (EmployeePublicOut)

parent_viewer darf NICHT:
- POST/PUT/DELETE /shifts (Schichten anlegen/ändern/löschen)
- GET /payroll (Abrechnung)
- GET /employees/{id}/contracts (Vertragsdaten)
"""
import uuid
import pytest
from decimal import Decimal
from datetime import date, time, datetime, timezone

import pytest_asyncio
from app.core.security import create_access_token, hash_password
from app.models.user import User
from app.models.employee import Employee
from app.models.shift import Shift
from tests.conftest import auth_headers

SHIFTS_URL = "/api/v1/shifts"
EMPLOYEES_URL = "/api/v1/employees"
PAYROLL_URL = "/api/v1/payroll"


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def parent_viewer_user(db, tenant) -> User:
    u = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email="parent@test.de",
        hashed_password=hash_password("testpass123"),
        role="parent_viewer",
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


@pytest.fixture
def parent_viewer_token(parent_viewer_user) -> str:
    return create_access_token(parent_viewer_user.id, parent_viewer_user.tenant_id, "parent_viewer")


async def _make_employee(db, tenant) -> Employee:
    emp = Employee(
        tenant_id=tenant.id,
        first_name="Test",
        last_name="Mitarbeiter",
        contract_type="minijob",
        hourly_rate=Decimal("12.41"),
        annual_salary_limit=Decimal("6672"),
        vacation_days=20,
        is_active=True,
    )
    db.add(emp)
    await db.commit()
    await db.refresh(emp)
    return emp


async def _make_shift(db, tenant, employee) -> Shift:
    shift = Shift(
        tenant_id=tenant.id,
        employee_id=employee.id,
        date=date(2025, 6, 1),
        start_time=time(8, 0),
        end_time=time(14, 0),
        break_minutes=30,
        status="planned",
    )
    db.add(shift)
    await db.commit()
    await db.refresh(shift)
    return shift


# ── Shifts: Lesen ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_parent_viewer_can_list_shifts(client, db, tenant, parent_viewer_user, parent_viewer_token):
    """parent_viewer sieht alle Schichten des Tenants."""
    emp = await _make_employee(db, tenant)
    await _make_shift(db, tenant, emp)

    resp = await client.get(SHIFTS_URL, headers=auth_headers(parent_viewer_token))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1


# ── Shifts: Schreiben verboten ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_parent_viewer_cannot_create_shift(client, db, tenant, parent_viewer_token):
    """parent_viewer darf keine Schichten anlegen."""
    emp = await _make_employee(db, tenant)
    payload = {
        "employee_id": str(emp.id),
        "date": "2025-07-01",
        "start_time": "08:00",
        "end_time": "14:00",
        "break_minutes": 30,
    }
    resp = await client.post(SHIFTS_URL, json=payload, headers=auth_headers(parent_viewer_token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_parent_viewer_cannot_confirm_shift(client, db, tenant, parent_viewer_token, admin_user, admin_token):
    """parent_viewer darf Schichten nicht bestätigen."""
    emp = await _make_employee(db, tenant)
    shift = await _make_shift(db, tenant, emp)

    resp = await client.post(
        f"{SHIFTS_URL}/{shift.id}/confirm",
        headers=auth_headers(parent_viewer_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_parent_viewer_cannot_delete_shift(client, db, tenant, parent_viewer_token):
    """parent_viewer darf Schichten nicht löschen."""
    emp = await _make_employee(db, tenant)
    shift = await _make_shift(db, tenant, emp)

    resp = await client.delete(
        f"{SHIFTS_URL}/{shift.id}",
        headers=auth_headers(parent_viewer_token),
    )
    assert resp.status_code == 403


# ── Mitarbeiter: nur PublicOut ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_parent_viewer_gets_public_employee_list(client, db, tenant, parent_viewer_token):
    """parent_viewer sieht Mitarbeiter ohne Gehalts- und Kontaktdaten."""
    await _make_employee(db, tenant)

    resp = await client.get(EMPLOYEES_URL, headers=auth_headers(parent_viewer_token))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    emp = data[0]
    # PublicOut-Felder vorhanden
    assert "first_name" in emp
    assert "last_name" in emp
    # Keine sensiblen Felder
    assert "hourly_rate" not in emp
    assert "phone" not in emp


@pytest.mark.asyncio
async def test_parent_viewer_gets_public_employee_detail(client, db, tenant, parent_viewer_token):
    """parent_viewer kann einzelnen Mitarbeiter abrufen (PublicOut)."""
    emp = await _make_employee(db, tenant)

    resp = await client.get(f"{EMPLOYEES_URL}/{emp.id}", headers=auth_headers(parent_viewer_token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["first_name"] == "Test"
    assert "hourly_rate" not in data


# ── Abrechnung: verboten ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_parent_viewer_cannot_calculate_payroll(client, db, tenant, parent_viewer_token):
    """parent_viewer darf Abrechnung nicht berechnen."""
    emp = await _make_employee(db, tenant)
    resp = await client.post(
        f"{PAYROLL_URL}/calculate",
        json={"employee_id": str(emp.id), "month": "2025-06-01"},
        headers=auth_headers(parent_viewer_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_parent_viewer_cannot_access_payroll_annual(client, tenant, parent_viewer_token):
    """parent_viewer hat keinen Zugriff auf Jahresübersicht."""
    resp = await client.get(
        f"{PAYROLL_URL}/annual",
        params={"year": 2025},
        headers=auth_headers(parent_viewer_token),
    )
    assert resp.status_code == 403


# ── Verträge: verboten ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_parent_viewer_cannot_access_contracts(client, db, tenant, parent_viewer_token):
    """parent_viewer darf Vertragsdaten nicht einsehen."""
    emp = await _make_employee(db, tenant)

    resp = await client.get(
        f"{EMPLOYEES_URL}/{emp.id}/contracts",
        headers=auth_headers(parent_viewer_token),
    )
    assert resp.status_code == 403
