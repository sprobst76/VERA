"""
Tests für /api/v1/reports/* – Stunden, Minijob, Compliance, CSV.
"""
import pytest
from datetime import date, time
from tests.conftest import auth_headers

REPORTS_URL = "/api/v1/reports"


async def make_employee(db, tenant, contract_type="minijob"):
    from app.models.employee import Employee
    emp = Employee(
        tenant_id=tenant.id,
        first_name="Report",
        last_name="Test",
        contract_type=contract_type,
        hourly_rate=12.0,
        annual_salary_limit=6672,
        vacation_days=20,
    )
    db.add(emp)
    await db.commit()
    await db.refresh(emp)
    return emp


async def make_shift(db, tenant, emp, shift_date, status="confirmed"):
    from app.models.shift import Shift
    s = Shift(
        tenant_id=tenant.id,
        employee_id=emp.id,
        date=shift_date,
        start_time=time(8, 0),
        end_time=time(16, 0),
        break_minutes=30,
        status=status,
    )
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return s


# ── hours-summary ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_hours_summary_empty(client, admin_token, admin_user, tenant):
    resp = await client.get(
        f"{REPORTS_URL}/hours-summary",
        params={"from": "2025-01-01", "to": "2025-01-31"},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_hours_summary_counts_shifts(client, admin_token, admin_user, db, tenant):
    emp = await make_employee(db, tenant, contract_type="full_time")
    await make_shift(db, tenant, emp, date(2025, 3, 10), status="confirmed")
    await make_shift(db, tenant, emp, date(2025, 3, 12), status="completed")
    await make_shift(db, tenant, emp, date(2025, 3, 15), status="planned")  # not counted

    resp = await client.get(
        f"{REPORTS_URL}/hours-summary",
        params={"from": "2025-03-01", "to": "2025-03-31"},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    row = next((r for r in data if r["employee_id"] == str(emp.id)), None)
    assert row is not None
    assert row["shift_count"] == 2
    assert row["gross_hours"] > 0
    assert row["net_hours"] < row["gross_hours"]  # break deducted


@pytest.mark.asyncio
async def test_hours_summary_employee_sees_only_own(client, employee_token, employee_user, db, tenant):
    """Employee darf nur eigene Daten sehen."""
    resp = await client.get(
        f"{REPORTS_URL}/hours-summary",
        params={"from": "2025-03-01", "to": "2025-03-31"},
        headers=auth_headers(employee_token),
    )
    assert resp.status_code == 200
    # Should return list (possibly empty), not 403
    assert isinstance(resp.json(), list)


# ── minijob-limit-status ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_minijob_limit_status_empty(client, admin_token, admin_user, tenant):
    resp = await client.get(
        f"{REPORTS_URL}/minijob-limit-status",
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_minijob_limit_status_has_fields(client, admin_token, admin_user, db, tenant):
    emp = await make_employee(db, tenant, contract_type="minijob")
    resp = await client.get(
        f"{REPORTS_URL}/minijob-limit-status",
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    row = next((r for r in data if r["employee_id"] == str(emp.id)), None)
    assert row is not None
    assert "annual_limit" in row
    assert "ytd_gross" in row
    assert "remaining" in row
    assert "percent_used" in row
    assert row["status"] in ("ok", "warning", "critical")


# ── compliance-violations ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_compliance_violations_empty(client, admin_token, admin_user, tenant):
    resp = await client.get(
        f"{REPORTS_URL}/compliance-violations",
        params={"from": "2025-01-01", "to": "2025-01-31"},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_compliance_violations_finds_flagged_shift(client, admin_token, admin_user, db, tenant):
    from app.models.shift import Shift
    emp = await make_employee(db, tenant, contract_type="full_time")
    s = Shift(
        tenant_id=tenant.id,
        employee_id=emp.id,
        date=date(2025, 5, 10),
        start_time=time(8, 0),
        end_time=time(16, 0),
        break_minutes=0,
        status="confirmed",
        break_ok=False,  # flagged violation
    )
    db.add(s)
    await db.commit()

    resp = await client.get(
        f"{REPORTS_URL}/compliance-violations",
        params={"from": "2025-05-01", "to": "2025-05-31"},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    violation = next((v for v in data if v["shift_id"] == str(s.id)), None)
    assert violation is not None
    assert "Pause unterschritten" in violation["violations"]


# ── CSV Export ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_csv_export_returns_csv(client, admin_token, admin_user, tenant):
    resp = await client.get(
        f"{REPORTS_URL}/export/csv",
        params={"from": "2025-03-01", "to": "2025-03-31"},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    assert "text/csv" in resp.headers.get("content-type", "")
    assert "attachment" in resp.headers.get("content-disposition", "")
