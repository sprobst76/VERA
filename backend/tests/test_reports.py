"""
Tests für /api/v1/reports/* – Stunden, Minijob, Compliance, CSV.
"""
import pytest
from datetime import date, time
from tests.conftest import auth_headers

REPORTS_URL = "/api/v1/reports"


async def make_employee(db, tenant, contract_type="minijob"):
    from app.models.employee import Employee
    from app.models.contract_history import ContractHistory

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
    await db.flush()

    # ContractHistory-Eintrag anlegen (D-01: Reports lesen aus CH, nicht Employee-Mirror)
    ch = ContractHistory(
        tenant_id=tenant.id,
        employee_id=emp.id,
        valid_from=date(2025, 1, 1),
        valid_to=None,
        contract_type=contract_type,
        hourly_rate=12.0,
        annual_salary_limit=6672,
    )
    db.add(ch)
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


# ── ContractHistory-Reads in reports (D-01 / D-02) ────────────────────────────

async def make_employee_with_ch(db, tenant, employee_contract_type, ch_contract_type,
                                 employee_annual_limit=None, ch_annual_limit=6672.0,
                                 hourly_rate=13.0):
    """
    Erzeugt einen Mitarbeiter mit einem CH-Eintrag, wobei Employee.contract_type und
    ContractHistory.contract_type bewusst unterschiedlich gesetzt werden können.
    """
    from app.models.employee import Employee
    from app.models.contract_history import ContractHistory
    from datetime import date

    emp = Employee(
        tenant_id=tenant.id,
        first_name="CH",
        last_name="Test",
        contract_type=employee_contract_type,
        hourly_rate=hourly_rate,
        annual_salary_limit=employee_annual_limit,
        vacation_days=0,
        is_active=True,
    )
    db.add(emp)
    await db.flush()

    ch = ContractHistory(
        tenant_id=tenant.id,
        employee_id=emp.id,
        valid_from=date(2025, 1, 1),
        valid_to=None,
        contract_type=ch_contract_type,
        hourly_rate=hourly_rate,
        annual_salary_limit=ch_annual_limit,
    )
    db.add(ch)
    await db.commit()
    await db.refresh(emp)
    return emp, ch


@pytest.mark.asyncio
async def test_minijob_limit_reads_contract_history_not_mirror(client, admin_token, admin_user, db, tenant):
    """
    minijob-limit-status soll Mitarbeiter mit CH.contract_type='minijob' finden,
    auch wenn Employee.contract_type='part_time' (Mirror-Feld wird ignoriert).
    """
    emp, ch = await make_employee_with_ch(
        db, tenant,
        employee_contract_type="part_time",  # Mirror: NICHT minijob
        ch_contract_type="minijob",           # CH: minijob → SOLL im Report erscheinen
        ch_annual_limit=6672.0,
    )

    resp = await client.get(
        f"{REPORTS_URL}/minijob-limit-status",
        params={"year": 2026},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    found = next((r for r in data if r["employee_id"] == str(emp.id)), None)
    assert found is not None, (
        f"Employee {emp.id} with CH.contract_type='minijob' must appear in minijob-limit-status, "
        f"even though Employee.contract_type='part_time'. Got: {[r['employee_id'] for r in data]}"
    )


@pytest.mark.asyncio
async def test_minijob_limit_excludes_employee_mirror_only(client, admin_token, admin_user, db, tenant):
    """
    Mitarbeiter mit Employee.contract_type='minijob' aber CH.contract_type='part_time'
    soll NICHT im minijob-limit-status erscheinen.
    """
    emp, ch = await make_employee_with_ch(
        db, tenant,
        employee_contract_type="minijob",    # Mirror: minijob (aber CH sagt part_time)
        ch_contract_type="part_time",         # CH: part_time → soll NICHT erscheinen
        ch_annual_limit=None,
    )

    resp = await client.get(
        f"{REPORTS_URL}/minijob-limit-status",
        params={"year": 2026},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    found = next((r for r in data if r["employee_id"] == str(emp.id)), None)
    assert found is None, (
        f"Employee {emp.id} with CH.contract_type='part_time' must NOT appear in minijob-limit-status, "
        f"even though Employee.contract_type='minijob'."
    )


@pytest.mark.asyncio
async def test_minijob_limit_uses_ch_annual_salary_limit(client, admin_token, admin_user, db, tenant):
    """
    minijob-limit-status nutzt annual_salary_limit aus ContractHistory,
    nicht aus Employee.annual_salary_limit (Mirror-Feld).
    """
    emp, ch = await make_employee_with_ch(
        db, tenant,
        employee_contract_type="minijob",
        ch_contract_type="minijob",
        employee_annual_limit=9999.0,  # Mirror: 9999 (falsch / veraltet)
        ch_annual_limit=6672.0,         # CH: 6672 (korrekt)
    )

    resp = await client.get(
        f"{REPORTS_URL}/minijob-limit-status",
        params={"year": 2026},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    found = next((r for r in data if r["employee_id"] == str(emp.id)), None)
    assert found is not None
    assert found["annual_limit"] == pytest.approx(6672.0), (
        f"annual_limit should be from ContractHistory (6672), got {found['annual_limit']}"
    )


@pytest.mark.asyncio
async def test_hours_summary_reads_contract_type_from_ch(client, admin_token, admin_user, db, tenant):
    """
    hours-summary liefert contract_type aus ContractHistory, nicht aus Employee.contract_type.
    Employee.contract_type='full_time', CH.contract_type='minijob' → Report soll 'minijob' zeigen.
    """
    from datetime import time
    from app.models.shift import Shift

    emp, ch = await make_employee_with_ch(
        db, tenant,
        employee_contract_type="full_time",  # Mirror: full_time (veraltet)
        ch_contract_type="minijob",           # CH: minijob (aktuell)
    )
    # Schicht anlegen damit der Mitarbeiter im Report auftaucht
    s = Shift(
        tenant_id=tenant.id,
        employee_id=emp.id,
        date=date(2025, 6, 10),
        start_time=time(8, 0),
        end_time=time(16, 0),
        break_minutes=30,
        status="confirmed",
    )
    db.add(s)
    await db.commit()

    resp = await client.get(
        f"{REPORTS_URL}/hours-summary",
        params={"from": "2025-06-01", "to": "2025-06-30"},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    row = next((r for r in data if r["employee_id"] == str(emp.id)), None)
    assert row is not None
    assert row["contract_type"] == "minijob", (
        f"contract_type should be 'minijob' (from ContractHistory), got '{row['contract_type']}'"
    )
