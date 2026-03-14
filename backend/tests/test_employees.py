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


# ── GET /employees/vacation-balances ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_vacation_balances_admin_sees_all(client, admin_token, admin_user, db, tenant):
    """Admin sieht Urlaubskonten aller aktiven Mitarbeiter."""
    from app.models.employee import Employee
    for i in range(3):
        emp = Employee(
            tenant_id=tenant.id,
            first_name=f"Emp{i}",
            last_name="Test",
            contract_type="minijob",
            hourly_rate=12.0,
            annual_salary_limit=6672,
            vacation_days=20,
            is_active=True,
        )
        db.add(emp)
    await db.commit()

    resp = await client.get(
        f"{EMPLOYEES_URL}/vacation-balances",
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3
    for b in data:
        assert "employee_id" in b
        assert "entitlement" in b
        assert "taken" in b
        assert "remaining" in b
        assert b["remaining"] == b["entitlement"] - b["taken"]


@pytest.mark.asyncio
async def test_vacation_balances_employee_sees_own(client, admin_token, employee_token,
                                                    admin_user, employee_user, db, tenant):
    """Employee sieht nur eigenes Urlaubskonto."""
    from app.models.employee import Employee

    # Eigener Mitarbeiter
    own_emp = Employee(
        tenant_id=tenant.id,
        user_id=employee_user.id,
        first_name="Own",
        last_name="Employee",
        contract_type="minijob",
        hourly_rate=12.0,
        annual_salary_limit=6672,
        vacation_days=15,
        is_active=True,
    )
    db.add(own_emp)
    # Anderer Mitarbeiter
    other_emp = Employee(
        tenant_id=tenant.id,
        first_name="Other",
        last_name="Employee",
        contract_type="minijob",
        hourly_rate=12.0,
        annual_salary_limit=6672,
        vacation_days=20,
        is_active=True,
    )
    db.add(other_emp)
    await db.commit()

    resp = await client.get(
        f"{EMPLOYEES_URL}/vacation-balances",
        headers=auth_headers(employee_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    # Employee sieht nur eigenes Konto
    assert len(data) == 1
    assert data[0]["employee_id"] == str(own_emp.id)
    assert data[0]["entitlement"] == 15


@pytest.mark.asyncio
async def test_vacation_balances_taken_counted(client, admin_token, admin_user, db, tenant):
    """Genommene Urlaubstage werden korrekt abgezogen."""
    from app.models.employee import Employee
    from app.models.absence import EmployeeAbsence
    from datetime import date

    emp = Employee(
        tenant_id=tenant.id,
        first_name="Urlaub",
        last_name="Nehmer",
        contract_type="part_time",
        hourly_rate=14.0,
        annual_salary_limit=0,
        vacation_days=25,
        is_active=True,
    )
    db.add(emp)
    await db.flush()

    # Genehmigter Urlaub im aktuellen Jahr
    absence = EmployeeAbsence(
        tenant_id=tenant.id,
        employee_id=emp.id,
        type="vacation",
        status="approved",
        start_date=date.today().replace(month=1, day=2),
        end_date=date.today().replace(month=1, day=6),
        days_count=5,
    )
    db.add(absence)
    await db.commit()

    resp = await client.get(
        f"{EMPLOYEES_URL}/vacation-balances",
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    balances = {b["employee_id"]: b for b in resp.json()}
    b = balances[str(emp.id)]
    assert b["taken"] == 5.0
    assert b["remaining"] == 20.0  # 25 - 5


@pytest.mark.asyncio
async def test_vacation_balances_year_filter(client, admin_token, admin_user, db, tenant):
    """year-Parameter filtert auf das gewählte Kalenderjahr."""
    from app.models.employee import Employee
    from app.models.absence import EmployeeAbsence
    from datetime import date

    emp = Employee(
        tenant_id=tenant.id,
        first_name="Jahr",
        last_name="Filter",
        contract_type="minijob",
        hourly_rate=12.0,
        annual_salary_limit=6672,
        vacation_days=10,
        is_active=True,
    )
    db.add(emp)
    await db.flush()

    # Urlaub in 2024
    a2024 = EmployeeAbsence(
        tenant_id=tenant.id,
        employee_id=emp.id,
        type="vacation",
        status="approved",
        start_date=date(2024, 6, 1),
        end_date=date(2024, 6, 3),
        days_count=3,
    )
    db.add(a2024)
    await db.commit()

    # Abfrage für 2024 → 3 Tage genommen
    resp = await client.get(
        f"{EMPLOYEES_URL}/vacation-balances",
        params={"year": 2024},
        headers=auth_headers(admin_token),
    )
    balances = {b["employee_id"]: b for b in resp.json()}
    assert balances[str(emp.id)]["taken"] == 3.0

    # Abfrage für 2025 → 0 Tage genommen
    resp2 = await client.get(
        f"{EMPLOYEES_URL}/vacation-balances",
        params={"year": 2025},
        headers=auth_headers(admin_token),
    )
    balances2 = {b["employee_id"]: b for b in resp2.json()}
    assert balances2[str(emp.id)]["taken"] == 0.0
