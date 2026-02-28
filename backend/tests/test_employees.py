"""
Tests für /api/v1/employees – CRUD, RBAC (EmployeeOut vs EmployeePublicOut),
GET /me, ContractHistory-Endpoints.
"""
import uuid
import pytest
from tests.conftest import auth_headers

EMPLOYEES_URL = "/api/v1/employees"

EMP_PAYLOAD = {
    "first_name": "Anna",
    "last_name": "Müller",
    "contract_type": "minijob",
    "hourly_rate": 13.0,
    "monthly_hours_limit": 43.0,
    "annual_salary_limit": 6672.0,
    "vacation_days": 0,
    "qualifications": [],
}


# ── GET /employees – RBAC ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_employees_admin_sees_full_data(client, admin_token, admin_user, tenant):
    """Admin sieht EmployeeOut mit hourly_rate."""
    await client.post(EMPLOYEES_URL, json=EMP_PAYLOAD, headers=auth_headers(admin_token))

    resp = await client.get(EMPLOYEES_URL, headers=auth_headers(admin_token))
    assert resp.status_code == 200
    employees = resp.json()
    assert len(employees) >= 1
    # Admin bekommt vollständige Daten inkl. hourly_rate
    assert "hourly_rate" in employees[0]


@pytest.mark.asyncio
async def test_list_employees_employee_sees_public_data(client, admin_token, employee_token,
                                                         admin_user, employee_user, tenant):
    """Employee-Rolle bekommt EmployeePublicOut (kein hourly_rate)."""
    await client.post(EMPLOYEES_URL, json=EMP_PAYLOAD, headers=auth_headers(admin_token))

    resp = await client.get(EMPLOYEES_URL, headers=auth_headers(employee_token))
    assert resp.status_code == 200
    employees = resp.json()
    assert len(employees) >= 1
    # Public-Schema hat kein hourly_rate
    assert "hourly_rate" not in employees[0]


# ── POST /employees ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_employee_admin(client, admin_token, admin_user, tenant):
    resp = await client.post(EMPLOYEES_URL, json=EMP_PAYLOAD, headers=auth_headers(admin_token))
    assert resp.status_code == 201
    data = resp.json()
    assert data["first_name"] == "Anna"
    assert data["last_name"] == "Müller"
    assert "id" in data


@pytest.mark.asyncio
async def test_create_employee_creates_contract_history(client, admin_token, admin_user, tenant, db):
    """Beim Anlegen eines Mitarbeiters wird automatisch ein ContractHistory-Eintrag erzeugt."""
    from sqlalchemy import select
    from app.models.contract_history import ContractHistory

    resp = await client.post(EMPLOYEES_URL, json=EMP_PAYLOAD, headers=auth_headers(admin_token))
    assert resp.status_code == 201
    emp_id = resp.json()["id"]

    result = await db.execute(
        select(ContractHistory).where(ContractHistory.employee_id == uuid.UUID(emp_id))
    )
    entries = result.scalars().all()
    assert len(entries) == 1
    assert entries[0].valid_to is None  # aktueller Eintrag
    assert float(entries[0].hourly_rate) == pytest.approx(13.0)


@pytest.mark.asyncio
async def test_create_employee_employee_role_forbidden(client, employee_token, employee_user, tenant):
    resp = await client.post(EMPLOYEES_URL, json=EMP_PAYLOAD, headers=auth_headers(employee_token))
    assert resp.status_code == 403


# ── ContractHistory-Endpoints ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_contracts(client, admin_token, admin_user, tenant):
    create = await client.post(EMPLOYEES_URL, json=EMP_PAYLOAD, headers=auth_headers(admin_token))
    emp_id = create.json()["id"]

    resp = await client.get(f"{EMPLOYEES_URL}/{emp_id}/contracts", headers=auth_headers(admin_token))
    assert resp.status_code == 200
    contracts = resp.json()
    assert len(contracts) == 1
    assert contracts[0]["valid_to"] is None


@pytest.mark.asyncio
async def test_add_contract_closes_previous(client, admin_token, admin_user, tenant):
    """Neue Vertragsperiode → alter Eintrag bekommt valid_to, neuer hat valid_to=null."""
    create = await client.post(EMPLOYEES_URL, json=EMP_PAYLOAD, headers=auth_headers(admin_token))
    emp_id = create.json()["id"]

    resp = await client.post(
        f"{EMPLOYEES_URL}/{emp_id}/contracts",
        json={
            "valid_from": "2025-10-01",
            "contract_type": "part_time",
            "hourly_rate": 15.0,
            "monthly_hours_limit": None,
            "annual_salary_limit": None,
            "note": "Aufstockung",
        },
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 201

    # Alle Einträge holen
    list_resp = await client.get(
        f"{EMPLOYEES_URL}/{emp_id}/contracts",
        headers=auth_headers(admin_token),
    )
    contracts = list_resp.json()
    assert len(contracts) == 2

    current = next(c for c in contracts if c["valid_to"] is None)
    old = next(c for c in contracts if c["valid_to"] is not None)
    assert current["contract_type"] == "part_time"
    assert old["valid_to"] == "2025-10-01"


# ── GET /employees/me ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_own_employee_linked(client, admin_token, employee_token,
                                       admin_user, employee_user, db, tenant):
    """Employee mit verknüpftem Employee-Record sieht eigene Daten."""
    from app.models.employee import Employee

    emp = Employee(
        tenant_id=tenant.id,
        user_id=employee_user.id,
        first_name="Own",
        last_name="Profile",
        contract_type="minijob",
        hourly_rate=13.0,
        annual_salary_limit=6672.0,
        vacation_days=0,
    )
    db.add(emp)
    await db.commit()

    resp = await client.get(f"{EMPLOYEES_URL}/me", headers=auth_headers(employee_token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["first_name"] == "Own"
    assert "hourly_rate" in data  # Employee sieht eigene Gehaltsdaten
