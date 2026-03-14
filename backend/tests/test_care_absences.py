"""
Tests für /api/v1/care-absences – Abwesenheit betreute Person.

Testet:
- Anlegen (Admin only)
- Automatische Schicht-Stornierung bei shift_handling=cancelled_unpaid
- Schichten bleiben erhalten bei carry_over / paid_anyway
- Löschen (Admin only)
- Listing (Admin + Employee)
- Tenant-Isolation
"""
import uuid
import pytest
from datetime import date, time
from tests.conftest import auth_headers

CARE_URL = "/api/v1/care-absences"
SHIFTS_URL = "/api/v1/shifts"


async def make_employee(db, tenant, user=None):
    from app.models.employee import Employee
    emp = Employee(
        tenant_id=tenant.id,
        user_id=user.id if user else None,
        first_name="Care",
        last_name="Test",
        contract_type="minijob",
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
        break_minutes=0,
        status=status,
    )
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return s


# ── GET /care-absences ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_care_absences_empty(client, admin_token, admin_user, tenant):
    """Leere Liste wenn keine Abwesenheiten vorhanden."""
    resp = await client.get(CARE_URL, headers=auth_headers(admin_token))
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_care_absences_employee_allowed(client, employee_token, employee_user, tenant):
    """Auch Employees dürfen die Liste abrufen."""
    resp = await client.get(CARE_URL, headers=auth_headers(employee_token))
    assert resp.status_code == 200


# ── POST /care-absences ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_care_absence_admin(client, admin_token, admin_user, tenant):
    """Admin kann Abwesenheit anlegen."""
    resp = await client.post(
        CARE_URL,
        json={
            "type": "vacation",
            "start_date": "2025-07-01",
            "end_date": "2025-07-14",
            "description": "Sommerurlaub",
            "shift_handling": "cancelled_unpaid",
            "notify_employees": False,
        },
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["type"] == "vacation"
    assert data["shift_handling"] == "cancelled_unpaid"
    assert data["start_date"] == "2025-07-01"
    assert data["end_date"] == "2025-07-14"


@pytest.mark.asyncio
async def test_create_care_absence_employee_forbidden(client, employee_token, employee_user, tenant):
    """Employee-Rolle kann keine Care Absence anlegen."""
    resp = await client.post(
        CARE_URL,
        json={
            "type": "sick",
            "start_date": "2025-07-01",
            "end_date": "2025-07-03",
            "shift_handling": "cancelled_unpaid",
        },
        headers=auth_headers(employee_token),
    )
    assert resp.status_code == 403


# ── Shift-Stornierung bei cancelled_unpaid ────────────────────────────────────

@pytest.mark.asyncio
async def test_care_absence_cancels_shifts(client, admin_token, admin_user, db, tenant):
    """Bei shift_handling=cancelled_unpaid werden Dienste im Zeitraum storniert."""
    emp = await make_employee(db, tenant)

    # Dienst innerhalb des Zeitraums
    s_inside = await make_shift(db, tenant, emp, date(2025, 8, 5), status="confirmed")
    # Dienst ausserhalb
    s_outside = await make_shift(db, tenant, emp, date(2025, 8, 20), status="confirmed")

    resp = await client.post(
        CARE_URL,
        json={
            "type": "hospital",
            "start_date": "2025-08-01",
            "end_date": "2025-08-10",
            "shift_handling": "cancelled_unpaid",
            "notify_employees": False,
        },
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 201

    # Dienst im Zeitraum muss storniert sein
    await db.refresh(s_inside)
    assert s_inside.status == "cancelled_absence"

    # Dienst ausserhalb bleibt unverändert
    await db.refresh(s_outside)
    assert s_outside.status == "confirmed"


@pytest.mark.asyncio
async def test_care_absence_carry_over_keeps_shifts(client, admin_token, admin_user, db, tenant):
    """Bei shift_handling=carry_over bleiben Dienste erhalten."""
    emp = await make_employee(db, tenant)
    s = await make_shift(db, tenant, emp, date(2025, 8, 5), status="confirmed")

    await client.post(
        CARE_URL,
        json={
            "type": "rehab",
            "start_date": "2025-08-01",
            "end_date": "2025-08-10",
            "shift_handling": "carry_over",
            "notify_employees": False,
        },
        headers=auth_headers(admin_token),
    )

    await db.refresh(s)
    assert s.status == "confirmed"


@pytest.mark.asyncio
async def test_care_absence_paid_anyway_keeps_shifts(client, admin_token, admin_user, db, tenant):
    """Bei shift_handling=paid_anyway bleiben Dienste erhalten."""
    emp = await make_employee(db, tenant)
    s = await make_shift(db, tenant, emp, date(2025, 8, 5), status="confirmed")

    await client.post(
        CARE_URL,
        json={
            "type": "vacation",
            "start_date": "2025-08-01",
            "end_date": "2025-08-10",
            "shift_handling": "paid_anyway",
            "notify_employees": False,
        },
        headers=auth_headers(admin_token),
    )

    await db.refresh(s)
    assert s.status == "confirmed"


@pytest.mark.asyncio
async def test_care_absence_already_cancelled_not_affected(client, admin_token, admin_user, db, tenant):
    """Bereits stornierte Dienste werden nicht doppelt angefasst."""
    emp = await make_employee(db, tenant)
    s = await make_shift(db, tenant, emp, date(2025, 8, 5), status="cancelled")

    await client.post(
        CARE_URL,
        json={
            "type": "sick",
            "start_date": "2025-08-01",
            "end_date": "2025-08-10",
            "shift_handling": "cancelled_unpaid",
            "notify_employees": False,
        },
        headers=auth_headers(admin_token),
    )

    await db.refresh(s)
    # Bleibt "cancelled", nicht "cancelled_absence"
    assert s.status == "cancelled"


# ── DELETE /care-absences/{id} ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_care_absence(client, admin_token, admin_user, tenant):
    """Admin kann Abwesenheit löschen."""
    create_resp = await client.post(
        CARE_URL,
        json={
            "type": "other",
            "start_date": "2025-09-01",
            "end_date": "2025-09-05",
            "shift_handling": "carry_over",
            "notify_employees": False,
        },
        headers=auth_headers(admin_token),
    )
    assert create_resp.status_code == 201
    absence_id = create_resp.json()["id"]

    del_resp = await client.delete(
        f"{CARE_URL}/{absence_id}",
        headers=auth_headers(admin_token),
    )
    assert del_resp.status_code == 204

    # Nicht mehr in der Liste
    list_resp = await client.get(CARE_URL, headers=auth_headers(admin_token))
    ids = [a["id"] for a in list_resp.json()]
    assert absence_id not in ids


@pytest.mark.asyncio
async def test_delete_care_absence_not_found(client, admin_token, admin_user, tenant):
    """404 wenn Abwesenheit nicht existiert."""
    resp = await client.delete(
        f"{CARE_URL}/{uuid.uuid4()}",
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_care_absence_employee_forbidden(client, admin_token, employee_token,
                                                       admin_user, employee_user, tenant):
    """Employee-Rolle darf nicht löschen."""
    create_resp = await client.post(
        CARE_URL,
        json={
            "type": "vacation",
            "start_date": "2025-09-10",
            "end_date": "2025-09-12",
            "shift_handling": "carry_over",
            "notify_employees": False,
        },
        headers=auth_headers(admin_token),
    )
    absence_id = create_resp.json()["id"]

    resp = await client.delete(
        f"{CARE_URL}/{absence_id}",
        headers=auth_headers(employee_token),
    )
    assert resp.status_code == 403
