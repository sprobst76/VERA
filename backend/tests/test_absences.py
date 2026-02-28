"""
Tests für /api/v1/absences – Antrag stellen, Genehmigung, RBAC, Kaskade zu Schichten.
"""
import uuid
import pytest
from tests.conftest import auth_headers

ABSENCES_URL = "/api/v1/absences"
SHIFTS_URL = "/api/v1/shifts"


async def create_employee_record(db, tenant, user=None):
    """Hilfsfunktion: Employee-Record anlegen und optional mit User verknüpfen."""
    from app.models.employee import Employee
    emp = Employee(
        tenant_id=tenant.id,
        user_id=user.id if user else None,
        first_name="Test",
        last_name="Employee",
        contract_type="full_time",
        hourly_rate=14.0,
        annual_salary_limit=0,
        vacation_days=30,
    )
    db.add(emp)
    await db.commit()
    await db.refresh(emp)
    return emp


# ── POST /absences ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_absence_admin(client, admin_token, admin_user, db, tenant):
    """Admin kann Abwesenheit für beliebigen Mitarbeiter anlegen."""
    emp = await create_employee_record(db, tenant)

    resp = await client.post(
        ABSENCES_URL,
        json={
            "employee_id": str(emp.id),
            "type": "vacation",
            "start_date": "2025-09-01",
            "end_date": "2025-09-05",
            "days_count": 5,
        },
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "pending"
    assert data["type"] == "vacation"


@pytest.mark.asyncio
async def test_create_absence_employee_own(client, employee_token, employee_user, db, tenant):
    """Employee kann Abwesenheit für sich selbst stellen."""
    emp = await create_employee_record(db, tenant, user=employee_user)

    resp = await client.post(
        ABSENCES_URL,
        json={
            "employee_id": str(emp.id),
            "type": "vacation",
            "start_date": "2025-09-01",
            "end_date": "2025-09-03",
            "days_count": 3,
        },
        headers=auth_headers(employee_token),
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_create_absence_employee_for_other_forbidden(client, employee_token, employee_user,
                                                            db, tenant):
    """Employee kann keine Abwesenheit für andere stellen."""
    # Anderer Employee (kein user verknüpft)
    other_emp = await create_employee_record(db, tenant)
    # Eigener Employee (verknüpft, damit 403 statt 403 "kein Profil")
    own_emp = await create_employee_record(db, tenant, user=employee_user)

    resp = await client.post(
        ABSENCES_URL,
        json={
            "employee_id": str(other_emp.id),
            "type": "vacation",
            "start_date": "2025-09-01",
            "end_date": "2025-09-03",
            "days_count": 3,
        },
        headers=auth_headers(employee_token),
    )
    assert resp.status_code == 403


# ── GET /absences ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_absences_employee_sees_only_own(client, admin_token, employee_token,
                                                     admin_user, employee_user, db, tenant):
    """Employee sieht nur eigene Abwesenheiten."""
    # Eigener Mitarbeiter
    own_emp = await create_employee_record(db, tenant, user=employee_user)
    # Anderer Mitarbeiter
    other_emp = await create_employee_record(db, tenant)

    # Admin legt Abwesenheiten für beide an
    for emp_id in [own_emp.id, other_emp.id]:
        await client.post(
            ABSENCES_URL,
            json={
                "employee_id": str(emp_id),
                "type": "sick",
                "start_date": "2025-09-01",
                "end_date": "2025-09-01",
                "days_count": 1,
            },
            headers=auth_headers(admin_token),
        )

    resp = await client.get(ABSENCES_URL, headers=auth_headers(employee_token))
    assert resp.status_code == 200
    absences = resp.json()
    # Employee sieht nur seine eigene
    assert len(absences) == 1
    assert absences[0]["employee_id"] == str(own_emp.id)


@pytest.mark.asyncio
async def test_list_absences_admin_status_filter(client, admin_token, admin_user, db, tenant):
    """Admin kann nach status=pending filtern."""
    emp = await create_employee_record(db, tenant)

    # pending Antrag
    await client.post(
        ABSENCES_URL,
        json={
            "employee_id": str(emp.id),
            "type": "vacation",
            "start_date": "2025-09-01",
            "end_date": "2025-09-02",
            "days_count": 2,
        },
        headers=auth_headers(admin_token),
    )

    resp = await client.get(
        ABSENCES_URL,
        params={"status": "pending"},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    assert all(a["status"] == "pending" for a in resp.json())


# ── PUT /absences/{id} – Genehmigung ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_approve_absence(client, admin_token, admin_user, db, tenant):
    emp = await create_employee_record(db, tenant)

    create_resp = await client.post(
        ABSENCES_URL,
        json={
            "employee_id": str(emp.id),
            "type": "vacation",
            "start_date": "2025-09-01",
            "end_date": "2025-09-02",
            "days_count": 2,
        },
        headers=auth_headers(admin_token),
    )
    absence_id = create_resp.json()["id"]

    resp = await client.put(
        f"{ABSENCES_URL}/{absence_id}",
        json={"status": "approved"},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"
    assert resp.json()["approved_by"] is not None


@pytest.mark.asyncio
async def test_reject_absence(client, admin_token, admin_user, db, tenant):
    emp = await create_employee_record(db, tenant)

    create_resp = await client.post(
        ABSENCES_URL,
        json={
            "employee_id": str(emp.id),
            "type": "vacation",
            "start_date": "2025-09-05",
            "end_date": "2025-09-05",
            "days_count": 1,
        },
        headers=auth_headers(admin_token),
    )
    absence_id = create_resp.json()["id"]

    resp = await client.put(
        f"{ABSENCES_URL}/{absence_id}",
        json={"status": "rejected"},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"


@pytest.mark.asyncio
async def test_approve_absence_employee_forbidden(client, admin_token, employee_token,
                                                   admin_user, employee_user, db, tenant):
    """Employee-Rolle kann keinen Antrag genehmigen."""
    emp = await create_employee_record(db, tenant)

    create_resp = await client.post(
        ABSENCES_URL,
        json={
            "employee_id": str(emp.id),
            "type": "vacation",
            "start_date": "2025-09-08",
            "end_date": "2025-09-08",
            "days_count": 1,
        },
        headers=auth_headers(admin_token),
    )
    absence_id = create_resp.json()["id"]

    resp = await client.put(
        f"{ABSENCES_URL}/{absence_id}",
        json={"status": "approved"},
        headers=auth_headers(employee_token),
    )
    assert resp.status_code == 403
