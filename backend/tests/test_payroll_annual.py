"""
Tests für GET /api/v1/payroll/annual und GET /api/v1/payroll/export.
"""
import pytest
from datetime import date, time
from decimal import Decimal

from tests.conftest import auth_headers

PAYROLL_URL = "/api/v1/payroll"


# ── Helpers ────────────────────────────────────────────────────────────────────

async def make_employee(db, tenant, first="Anna", last="Muster", contract_type="minijob"):
    from app.models.employee import Employee
    emp = Employee(
        tenant_id=tenant.id,
        first_name=first,
        last_name=last,
        contract_type=contract_type,
        hourly_rate=Decimal("12.41"),
        annual_salary_limit=Decimal("6672"),
        vacation_days=20,
        is_active=True,
    )
    db.add(emp)
    await db.commit()
    await db.refresh(emp)
    return emp


async def make_payroll_entry(db, tenant, emp, month: date, paid_hours=8.0, total_gross=100.0, status="approved"):
    from app.models.payroll import PayrollEntry
    entry = PayrollEntry(
        tenant_id=tenant.id,
        employee_id=emp.id,
        month=month,
        paid_hours=paid_hours,
        actual_hours=paid_hours,
        base_wage=total_gross,
        total_gross=total_gross,
        status=status,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


# ── GET /payroll/annual ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_annual_empty_year(client, admin_token, admin_user, tenant):
    """Kein Mitarbeiter → leere Liste."""
    resp = await client.get(
        f"{PAYROLL_URL}/annual",
        params={"year": 2025},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_annual_structure(client, admin_token, admin_user, db, tenant):
    """Mitarbeiter ohne Einträge → 12 None-Monate, Summen = 0."""
    emp = await make_employee(db, tenant)

    resp = await client.get(
        f"{PAYROLL_URL}/annual",
        params={"year": 2025},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1

    row = data[0]
    assert row["employee_id"] == str(emp.id)
    assert row["employee_name"] == "Anna Muster"
    assert row["contract_type"] == "minijob"
    # Alle 12 Monate als None
    months = row["months"]
    assert len(months) == 12
    for m in range(1, 13):
        assert months[str(m)] is None
    assert row["total_paid_hours"] == 0.0
    assert row["total_gross"] == 0.0


@pytest.mark.asyncio
async def test_annual_entry_in_correct_month(client, admin_token, admin_user, db, tenant):
    """Eintrag in März → months[3] befüllt, andere None."""
    emp = await make_employee(db, tenant)
    await make_payroll_entry(db, tenant, emp, date(2025, 3, 1), paid_hours=16.0, total_gross=198.56)

    resp = await client.get(
        f"{PAYROLL_URL}/annual",
        params={"year": 2025},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    row = resp.json()[0]
    months = row["months"]

    assert months["3"] is not None
    assert months["3"]["paid_hours"] == pytest.approx(16.0)
    assert months["3"]["total_gross"] == pytest.approx(198.56)
    assert months["3"]["status"] == "approved"

    # Alle anderen Monate None
    for m in range(1, 13):
        if m != 3:
            assert months[str(m)] is None


@pytest.mark.asyncio
async def test_annual_totals_correct(client, admin_token, admin_user, db, tenant):
    """Zwei Einträge → Jahressummen korrekt."""
    emp = await make_employee(db, tenant)
    await make_payroll_entry(db, tenant, emp, date(2025, 1, 1), paid_hours=10.0, total_gross=124.10)
    await make_payroll_entry(db, tenant, emp, date(2025, 6, 1), paid_hours=8.0, total_gross=99.28)

    resp = await client.get(
        f"{PAYROLL_URL}/annual",
        params={"year": 2025},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    row = resp.json()[0]
    assert row["total_paid_hours"] == pytest.approx(18.0)
    assert row["total_gross"] == pytest.approx(223.38)


@pytest.mark.asyncio
async def test_annual_only_own_tenant(client, admin_token, admin_user, db, tenant):
    """Einträge anderer Tenants tauchen nicht auf."""
    from app.models.tenant import Tenant
    from app.models.employee import Employee
    import uuid
    from datetime import datetime, timezone

    # Fremder Tenant + Mitarbeiter + Abrechnung
    other_tenant = Tenant(
        id=uuid.uuid4(), name="Fremdfirma", slug=f"fremdfirma-{uuid.uuid4().hex[:6]}",
        state="BY", is_active=True,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    db.add(other_tenant)
    await db.commit()

    other_emp = Employee(
        tenant_id=other_tenant.id, first_name="Fremd", last_name="User",
        contract_type="minijob", hourly_rate=Decimal("12.00"),
        annual_salary_limit=Decimal("6672"), vacation_days=20, is_active=True,
    )
    db.add(other_emp)
    await db.commit()
    await db.refresh(other_emp)
    await make_payroll_entry(db, other_tenant, other_emp, date(2025, 3, 1))

    # Eigener Tenant hat keinen Mitarbeiter → leere Liste
    resp = await client.get(
        f"{PAYROLL_URL}/annual",
        params={"year": 2025},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_annual_employee_role_forbidden(client, employee_token, employee_user, tenant):
    """Employee darf Jahresübersicht nicht abrufen."""
    resp = await client.get(
        f"{PAYROLL_URL}/annual",
        params={"year": 2025},
        headers=auth_headers(employee_token),
    )
    assert resp.status_code == 403


# ── GET /payroll/export ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_export_returns_csv(client, admin_token, admin_user, db, tenant):
    """Export liefert CSV mit korrektem Content-Type und BOM."""
    emp = await make_employee(db, tenant)
    await make_payroll_entry(db, tenant, emp, date(2025, 4, 1), paid_hours=20.0, total_gross=248.20)

    resp = await client.get(
        f"{PAYROLL_URL}/export",
        params={"year": 2025},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    # UTF-8-BOM
    assert resp.content[:3] == b"\xef\xbb\xbf"


@pytest.mark.asyncio
async def test_export_csv_header_columns(client, admin_token, admin_user, db, tenant):
    """CSV enthält Header-Zeile mit Mitarbeiter, Vertragsart und Monatsspalten."""
    await make_employee(db, tenant)

    resp = await client.get(
        f"{PAYROLL_URL}/export",
        params={"year": 2025},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    text = resp.content.decode("utf-8-sig")
    lines = text.strip().splitlines()
    header = lines[0]
    assert "Mitarbeiter" in header
    assert "Vertragsart" in header
    assert "Jan" in header
    assert "Dez" in header
    assert "Gesamt" in header


@pytest.mark.asyncio
async def test_export_csv_data_row(client, admin_token, admin_user, db, tenant):
    """CSV-Datenzeile enthält Mitarbeitername und korrekte Brutto-Summe."""
    emp = await make_employee(db, tenant, first="Klara", last="Beispiel")
    await make_payroll_entry(db, tenant, emp, date(2025, 5, 1), paid_hours=12.0, total_gross=148.92)

    resp = await client.get(
        f"{PAYROLL_URL}/export",
        params={"year": 2025},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    text = resp.content.decode("utf-8-sig")
    # Mitarbeitername muss in CSV auftauchen
    assert "Klara Beispiel" in text
    # Brutto-Wert mit Komma als Dezimaltrennzeichen (deutsches Format)
    assert "148,92" in text


@pytest.mark.asyncio
async def test_export_employee_role_forbidden(client, employee_token, employee_user, tenant):
    """Employee darf CSV-Export nicht abrufen."""
    resp = await client.get(
        f"{PAYROLL_URL}/export",
        params={"year": 2025},
        headers=auth_headers(employee_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_export_content_disposition(client, admin_token, admin_user, db, tenant):
    """Content-Disposition-Header enthält Jahres-Dateinamen."""
    await make_employee(db, tenant)

    resp = await client.get(
        f"{PAYROLL_URL}/export",
        params={"year": 2025},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    cd = resp.headers.get("content-disposition", "")
    assert "vera-abrechnung-2025.csv" in cd
