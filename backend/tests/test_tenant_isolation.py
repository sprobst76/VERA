"""
IDOR-/Tenant-Isolationstests.

Deckt die in der Projektanalyse (2026-07-06) als HOCH eingestufte Lücke ab:
"Tenant-Isolation ist kaum getestet" — echte cross-tenant-Zugriffstests
existierten nur an 3 Stellen (holiday_profiles, payroll_annual, users).

Muster: Tenant A legt eine Ressource an, Tenant B (eigener Admin, siehe
conftest.tenant_b/admin_token_b) versucht per ID darauf zuzugreifen/sie zu
ändern/zu löschen — muss durchgängig 404 liefern (Ressource "existiert nicht"
aus Sicht des fremden Tenants, kein 403 das die Existenz verraten würde).
"""
from datetime import date
from decimal import Decimal

import pytest

from tests.conftest import auth_headers

EMPLOYEES_URL = "/api/v1/employees"
SHIFTS_URL = "/api/v1/shifts"
PAYROLL_URL = "/api/v1/payroll"
REPORTS_URL = "/api/v1/reports"
SUPERADMIN_URL = "/api/v1/superadmin"

EMP_PAYLOAD = {
    "first_name": "Anna",
    "last_name": "Isoliert",
    "contract_type": "minijob",
    "hourly_rate": 13.0,
}


# ── Employees ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_employee_get_cross_tenant_404(client, admin_token, admin_token_b):
    r = await client.post(EMPLOYEES_URL, json=EMP_PAYLOAD, headers=auth_headers(admin_token))
    assert r.status_code == 201
    emp_id = r.json()["id"]

    r2 = await client.get(f"{EMPLOYEES_URL}/{emp_id}", headers=auth_headers(admin_token_b))
    assert r2.status_code == 404


@pytest.mark.asyncio
async def test_employee_update_cross_tenant_404(client, admin_token, admin_token_b):
    r = await client.post(EMPLOYEES_URL, json=EMP_PAYLOAD, headers=auth_headers(admin_token))
    emp_id = r.json()["id"]

    r2 = await client.put(
        f"{EMPLOYEES_URL}/{emp_id}", json={"first_name": "Uebernommen"},
        headers=auth_headers(admin_token_b),
    )
    assert r2.status_code == 404


@pytest.mark.asyncio
async def test_employee_delete_cross_tenant_404(client, admin_token, admin_token_b):
    r = await client.post(EMPLOYEES_URL, json=EMP_PAYLOAD, headers=auth_headers(admin_token))
    emp_id = r.json()["id"]

    r2 = await client.delete(f"{EMPLOYEES_URL}/{emp_id}", headers=auth_headers(admin_token_b))
    assert r2.status_code == 404


# ── Shifts ─────────────────────────────────────────────────────────────────

async def _mk_shift(client, token, date_str):
    r = await client.post(EMPLOYEES_URL, json=EMP_PAYLOAD, headers=auth_headers(token))
    assert r.status_code == 201
    emp_id = r.json()["id"]
    r2 = await client.post(
        SHIFTS_URL,
        json={"employee_id": emp_id, "date": date_str, "start_time": "08:00", "end_time": "16:00"},
        headers=auth_headers(token),
    )
    assert r2.status_code == 201
    return r2.json()["id"]


@pytest.mark.asyncio
async def test_shift_get_cross_tenant_404(client, admin_token, admin_token_b):
    shift_id = await _mk_shift(client, admin_token, "2026-08-10")
    r = await client.get(f"{SHIFTS_URL}/{shift_id}", headers=auth_headers(admin_token_b))
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_shift_update_cross_tenant_404(client, admin_token, admin_token_b):
    shift_id = await _mk_shift(client, admin_token, "2026-08-11")
    r = await client.put(
        f"{SHIFTS_URL}/{shift_id}", json={"notes": "Uebernommen"}, headers=auth_headers(admin_token_b)
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_shift_delete_cross_tenant_404(client, admin_token, admin_token_b):
    shift_id = await _mk_shift(client, admin_token, "2026-08-12")
    r = await client.delete(f"{SHIFTS_URL}/{shift_id}", headers=auth_headers(admin_token_b))
    assert r.status_code == 404


# ── Payroll ────────────────────────────────────────────────────────────────

async def _mk_payroll_entry(db, tenant):
    from app.models.employee import Employee
    from app.models.payroll import PayrollEntry

    emp = Employee(
        tenant_id=tenant.id, first_name="Payroll", last_name="Isoliert",
        contract_type="minijob", hourly_rate=Decimal("13.00"), is_active=True,
    )
    db.add(emp)
    await db.commit()
    await db.refresh(emp)

    entry = PayrollEntry(
        tenant_id=tenant.id, employee_id=emp.id, month=date(2026, 6, 1),
        paid_hours=10.0, actual_hours=10.0, base_wage=130.0, total_gross=130.0,
        status="approved",
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


@pytest.mark.asyncio
async def test_payroll_get_cross_tenant_404(client, admin_token_b, tenant, db):
    entry = await _mk_payroll_entry(db, tenant)
    r = await client.get(f"{PAYROLL_URL}/{entry.id}", headers=auth_headers(admin_token_b))
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_payroll_update_cross_tenant_404(client, admin_token_b, tenant, db):
    entry = await _mk_payroll_entry(db, tenant)
    r = await client.put(
        f"{PAYROLL_URL}/{entry.id}", json={"status": "paid"}, headers=auth_headers(admin_token_b)
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_payroll_pdf_cross_tenant_404(client, admin_token_b, tenant, db):
    entry = await _mk_payroll_entry(db, tenant)
    r = await client.get(f"{PAYROLL_URL}/{entry.id}/pdf", headers=auth_headers(admin_token_b))
    assert r.status_code == 404


# ── Reports ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reports_hours_summary_cross_tenant_employee_id_yields_nothing(
    client, admin_token, admin_token_b,
):
    """employee_id-Filter eines fremden Tenants darf keine Daten liefern, statt
    versehentlich die Stunden des fremden Mitarbeiters preiszugeben."""
    r = await client.post(EMPLOYEES_URL, json=EMP_PAYLOAD, headers=auth_headers(admin_token))
    emp_id = r.json()["id"]

    r2 = await client.get(
        REPORTS_URL + "/hours-summary",
        params={"from": "2026-01-01", "to": "2026-12-31", "employee_id": emp_id},
        headers=auth_headers(admin_token_b),
    )
    assert r2.status_code == 200
    assert r2.json() == []


# ── Superadmin: Privilege Escalation ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_superadmin_tenants_rejects_regular_admin_token(client, admin_token):
    """Ein normales Tenant-Admin-JWT (type=access) darf niemals als
    SuperAdmin-Berechtigung durchgehen — sonst sähe jeder Tenant-Admin alle
    anderen Tenants."""
    r = await client.get(f"{SUPERADMIN_URL}/tenants", headers=auth_headers(admin_token))
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_superadmin_admins_rejects_regular_admin_token(client, admin_token):
    r = await client.get(f"{SUPERADMIN_URL}/admins", headers=auth_headers(admin_token))
    assert r.status_code == 403
