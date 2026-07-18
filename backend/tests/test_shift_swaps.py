"""
Tests für /api/v1/shift-swaps – Dienst-Abgabe (Schichttausch-MVP): erstellen,
annehmen (sofort wirksam vs. Genehmigungspflicht), zurückziehen, genehmigen/
ablehnen, Compliance-Block, System-Hooks bei Stornierung/Änderung/Abwesenheit.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.core.security import hash_password, create_access_token
from app.models.employee import Employee
from app.models.user import User
from app.models.shift_swap import ShiftSwapOffer
from tests.conftest import auth_headers

SWAPS_URL = "/api/v1/shift-swaps"
SHIFTS_URL = "/api/v1/shifts"
ABSENCES_URL = "/api/v1/absences"

FUTURE_DATE = (date.today() + timedelta(days=10)).isoformat()
SHIFT_PAYLOAD = {
    "date": FUTURE_DATE, "start_time": "08:00:00", "end_time": "16:00:00", "break_minutes": 30,
}


@pytest_asyncio.fixture
async def employee_with_profile(db, employee_user, tenant):
    emp = Employee(
        tenant_id=tenant.id,
        user_id=employee_user.id,
        first_name="Anbieter",
        last_name="Eins",
        contract_type="minijob",
        hourly_rate=13.0,
        qualifications=[],
        notification_prefs={},
        vacation_days=20,
        is_active=True,
    )
    db.add(emp)
    await db.commit()
    await db.refresh(emp)
    return emp


async def _make_employee_with_login(db, tenant, email: str, first_name: str):
    user = User(
        tenant_id=tenant.id,
        email=email,
        hashed_password=hash_password("testpass123"),
        role="employee",
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    emp = Employee(
        tenant_id=tenant.id,
        user_id=user.id,
        first_name=first_name,
        last_name="Test",
        contract_type="minijob",
        hourly_rate=13.0,
        qualifications=[],
        notification_prefs={},
        vacation_days=20,
        is_active=True,
    )
    db.add(emp)
    await db.commit()
    await db.refresh(emp)

    token = create_access_token(user.id, user.tenant_id, "employee", token_version=user.token_version)
    return emp, token


@pytest_asyncio.fixture
async def second_employee(db, tenant):
    """Zweiter Mitarbeiter (Übernehmer) mit eigenem Login."""
    return await _make_employee_with_login(db, tenant, "second@test.de", "Uebernehmer")


@pytest_asyncio.fixture
async def third_employee(db, tenant):
    """Dritter Mitarbeiter, für Konflikt-/Race-Tests mit zwei potenziellen Übernehmern."""
    return await _make_employee_with_login(db, tenant, "third@test.de", "Dritter")


async def _create_shift(client, admin_token, employee_id, status_override=None, **overrides):
    payload = {**SHIFT_PAYLOAD, "employee_id": str(employee_id), **overrides}
    resp = await client.post(SHIFTS_URL, json=payload, headers=auth_headers(admin_token))
    shift_id = resp.json()["id"]
    if status_override:
        await client.put(f"{SHIFTS_URL}/{shift_id}", json={"status": status_override}, headers=auth_headers(admin_token))
    return shift_id


# ── POST /shift-swaps (create) ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_offer_success(client, admin_token, employee_token, admin_user, employee_user,
                                     employee_with_profile, tenant):
    shift_id = await _create_shift(client, admin_token, employee_with_profile.id)

    resp = await client.post(SWAPS_URL, json={"shift_id": shift_id, "note": "Zahnarzttermin"},
                              headers=auth_headers(employee_token))
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "open"
    assert data["shift_id"] == shift_id
    assert data["note"] == "Zahnarzttermin"


@pytest.mark.asyncio
async def test_create_offer_not_own_shift_forbidden(client, admin_token, employee_token,
                                                     admin_user, employee_user, tenant):
    """Ein offener Dienst ohne Zuweisung gehört niemandem — kann nicht angeboten werden."""
    resp = await client.post(SHIFTS_URL, json=SHIFT_PAYLOAD, headers=auth_headers(admin_token))
    shift_id = resp.json()["id"]

    offer_resp = await client.post(SWAPS_URL, json={"shift_id": shift_id}, headers=auth_headers(employee_token))
    assert offer_resp.status_code == 403


@pytest.mark.asyncio
async def test_create_offer_duplicate_active_rejected(client, admin_token, employee_token,
                                                       admin_user, employee_user,
                                                       employee_with_profile, tenant):
    shift_id = await _create_shift(client, admin_token, employee_with_profile.id)
    first = await client.post(SWAPS_URL, json={"shift_id": shift_id}, headers=auth_headers(employee_token))
    assert first.status_code == 201

    second = await client.post(SWAPS_URL, json={"shift_id": shift_id}, headers=auth_headers(employee_token))
    assert second.status_code == 409


# ── POST /shift-swaps/{id}/accept ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_accept_planned_shift_immediate(client, admin_token, employee_token,
                                               admin_user, employee_user, employee_with_profile,
                                               second_employee, tenant):
    """Dienst im Status 'planned': Annahme wirkt sofort, ohne Admin-Genehmigung."""
    accepting_emp, accepting_token = second_employee
    shift_id = await _create_shift(client, admin_token, employee_with_profile.id)

    offer_resp = await client.post(SWAPS_URL, json={"shift_id": shift_id}, headers=auth_headers(employee_token))
    offer_id = offer_resp.json()["id"]

    accept_resp = await client.post(f"{SWAPS_URL}/{offer_id}/accept", headers=auth_headers(accepting_token))
    assert accept_resp.status_code == 200
    data = accept_resp.json()
    assert data["status"] == "completed"
    assert data["accepted_by_employee_id"] == str(accepting_emp.id)

    shift_check = await client.get(f"{SHIFTS_URL}/{shift_id}", headers=auth_headers(admin_token))
    assert shift_check.json()["employee_id"] == str(accepting_emp.id)


@pytest.mark.asyncio
async def test_accept_confirmed_shift_needs_approval(client, admin_token, employee_token,
                                                      admin_user, employee_user, employee_with_profile,
                                                      second_employee, tenant):
    """Dienst im Status 'confirmed': Annahme geht in Genehmigung, Zuweisung bleibt vorerst unverändert."""
    accepting_emp, accepting_token = second_employee
    shift_id = await _create_shift(client, admin_token, employee_with_profile.id, status_override="confirmed")

    offer_resp = await client.post(SWAPS_URL, json={"shift_id": shift_id}, headers=auth_headers(employee_token))
    offer_id = offer_resp.json()["id"]

    accept_resp = await client.post(f"{SWAPS_URL}/{offer_id}/accept", headers=auth_headers(accepting_token))
    assert accept_resp.status_code == 200
    assert accept_resp.json()["status"] == "pending_approval"

    shift_check = await client.get(f"{SHIFTS_URL}/{shift_id}", headers=auth_headers(admin_token))
    assert shift_check.json()["employee_id"] == str(employee_with_profile.id)  # noch nicht umgezogen


@pytest.mark.asyncio
async def test_accept_own_offer_forbidden(client, admin_token, employee_token,
                                           admin_user, employee_user, employee_with_profile, tenant):
    shift_id = await _create_shift(client, admin_token, employee_with_profile.id)
    offer_resp = await client.post(SWAPS_URL, json={"shift_id": shift_id}, headers=auth_headers(employee_token))
    offer_id = offer_resp.json()["id"]

    resp = await client.post(f"{SWAPS_URL}/{offer_id}/accept", headers=auth_headers(employee_token))
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_accept_already_resolved_offer_conflict(client, admin_token, employee_token,
                                                       admin_user, employee_user, employee_with_profile,
                                                       second_employee, third_employee, tenant, db):
    """Zweiter Bewerber auf ein bereits vergebenes Angebot bekommt 409."""
    accepting_emp, accepting_token = second_employee
    _, third_token = third_employee
    shift_id = await _create_shift(client, admin_token, employee_with_profile.id)
    offer_resp = await client.post(SWAPS_URL, json={"shift_id": shift_id}, headers=auth_headers(employee_token))
    offer_id = offer_resp.json()["id"]

    first = await client.post(f"{SWAPS_URL}/{offer_id}/accept", headers=auth_headers(accepting_token))
    assert first.status_code == 200

    second = await client.post(f"{SWAPS_URL}/{offer_id}/accept", headers=auth_headers(third_token))
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_accept_blocked_by_minijob_annual_limit(client, admin_token, employee_token,
                                                       admin_user, employee_user, employee_with_profile,
                                                       second_employee, db, tenant):
    accepting_emp, accepting_token = second_employee
    from app.models.contract_history import ContractHistory
    from app.models.payroll import PayrollEntry

    db.add(ContractHistory(
        tenant_id=tenant.id, employee_id=accepting_emp.id,
        valid_from=date(2025, 1, 1), valid_to=None,
        contract_type="minijob", hourly_rate=13.0,
    ))
    over_limit_month = (date.today().replace(day=1) - timedelta(days=1)).replace(day=1)  # Vormonat
    db.add(PayrollEntry(
        tenant_id=tenant.id, employee_id=accepting_emp.id, month=over_limit_month,
        actual_hours=40.0, paid_hours=40.0,
        base_wage=Decimal("7000.00"), total_gross=Decimal("7000.00"), status="approved",
    ))
    await db.commit()

    shift_id = await _create_shift(client, admin_token, employee_with_profile.id, date=FUTURE_DATE)
    offer_resp = await client.post(SWAPS_URL, json={"shift_id": shift_id}, headers=auth_headers(employee_token))
    offer_id = offer_resp.json()["id"]

    resp = await client.post(f"{SWAPS_URL}/{offer_id}/accept", headers=auth_headers(accepting_token))
    assert resp.status_code == 409
    assert "Minijob-Jahresgrenze" in resp.json()["detail"]

    # Angebot bleibt offen für andere
    offer_check = await client.get(f"{SWAPS_URL}/{offer_id}", headers=auth_headers(employee_token))
    assert offer_check.json()["status"] == "open"


# ── POST /shift-swaps/{id}/withdraw ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_withdraw_own_offer(client, admin_token, employee_token,
                                   admin_user, employee_user, employee_with_profile, tenant):
    shift_id = await _create_shift(client, admin_token, employee_with_profile.id)
    offer_resp = await client.post(SWAPS_URL, json={"shift_id": shift_id}, headers=auth_headers(employee_token))
    offer_id = offer_resp.json()["id"]

    resp = await client.post(f"{SWAPS_URL}/{offer_id}/withdraw", headers=auth_headers(employee_token))
    assert resp.status_code == 200
    assert resp.json()["status"] == "withdrawn"


@pytest.mark.asyncio
async def test_withdraw_others_offer_forbidden(client, admin_token, employee_token,
                                                admin_user, employee_user, employee_with_profile,
                                                second_employee, tenant):
    _, other_token = second_employee
    shift_id = await _create_shift(client, admin_token, employee_with_profile.id)
    offer_resp = await client.post(SWAPS_URL, json={"shift_id": shift_id}, headers=auth_headers(employee_token))
    offer_id = offer_resp.json()["id"]

    resp = await client.post(f"{SWAPS_URL}/{offer_id}/withdraw", headers=auth_headers(other_token))
    assert resp.status_code == 403


# ── POST /shift-swaps/{id}/review ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_review_approve_completes_swap(client, admin_token, employee_token,
                                              admin_user, employee_user, employee_with_profile,
                                              second_employee, tenant):
    accepting_emp, accepting_token = second_employee
    shift_id = await _create_shift(client, admin_token, employee_with_profile.id, status_override="confirmed")
    offer_resp = await client.post(SWAPS_URL, json={"shift_id": shift_id}, headers=auth_headers(employee_token))
    offer_id = offer_resp.json()["id"]
    await client.post(f"{SWAPS_URL}/{offer_id}/accept", headers=auth_headers(accepting_token))

    resp = await client.post(f"{SWAPS_URL}/{offer_id}/review", json={"approved": True},
                              headers=auth_headers(admin_token))
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"

    shift_check = await client.get(f"{SHIFTS_URL}/{shift_id}", headers=auth_headers(admin_token))
    assert shift_check.json()["employee_id"] == str(accepting_emp.id)


@pytest.mark.asyncio
async def test_review_deny_leaves_shift_unchanged(client, admin_token, employee_token,
                                                   admin_user, employee_user, employee_with_profile,
                                                   second_employee, tenant):
    accepting_emp, accepting_token = second_employee
    shift_id = await _create_shift(client, admin_token, employee_with_profile.id, status_override="confirmed")
    offer_resp = await client.post(SWAPS_URL, json={"shift_id": shift_id}, headers=auth_headers(employee_token))
    offer_id = offer_resp.json()["id"]
    await client.post(f"{SWAPS_URL}/{offer_id}/accept", headers=auth_headers(accepting_token))

    resp = await client.post(f"{SWAPS_URL}/{offer_id}/review", json={"approved": False, "note": "Zu knapp besetzt"},
                              headers=auth_headers(admin_token))
    assert resp.status_code == 200
    assert resp.json()["status"] == "denied"

    shift_check = await client.get(f"{SHIFTS_URL}/{shift_id}", headers=auth_headers(admin_token))
    assert shift_check.json()["employee_id"] == str(employee_with_profile.id)


@pytest.mark.asyncio
async def test_review_by_employee_forbidden(client, admin_token, employee_token,
                                             admin_user, employee_user, employee_with_profile,
                                             second_employee, tenant):
    _, accepting_token = second_employee
    shift_id = await _create_shift(client, admin_token, employee_with_profile.id, status_override="confirmed")
    offer_resp = await client.post(SWAPS_URL, json={"shift_id": shift_id}, headers=auth_headers(employee_token))
    offer_id = offer_resp.json()["id"]
    await client.post(f"{SWAPS_URL}/{offer_id}/accept", headers=auth_headers(accepting_token))

    resp = await client.post(f"{SWAPS_URL}/{offer_id}/review", json={"approved": True},
                              headers=auth_headers(employee_token))
    assert resp.status_code == 403


# ── Sichtbarkeit (GET /shift-swaps) ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_offers_employee_sees_own_and_open(client, admin_token, employee_token,
                                                       admin_user, employee_user, employee_with_profile,
                                                       second_employee, tenant):
    accepting_emp, accepting_token = second_employee
    shift_id = await _create_shift(client, admin_token, employee_with_profile.id)
    await client.post(SWAPS_URL, json={"shift_id": shift_id}, headers=auth_headers(employee_token))

    resp = await client.get(SWAPS_URL, headers=auth_headers(accepting_token))
    assert resp.status_code == 200
    assert len(resp.json()) == 1


# ── System-Hooks: Stornierung / Änderung / Abwesenheit ───────────────────────

@pytest.mark.asyncio
async def test_shift_cancellation_cancels_open_offer(client, admin_token, employee_token,
                                                      admin_user, employee_user, employee_with_profile, tenant):
    shift_id = await _create_shift(client, admin_token, employee_with_profile.id)
    offer_resp = await client.post(SWAPS_URL, json={"shift_id": shift_id}, headers=auth_headers(employee_token))
    offer_id = offer_resp.json()["id"]

    await client.put(f"{SHIFTS_URL}/{shift_id}", json={"status": "cancelled", "cancellation_reason": "Test"},
                      headers=auth_headers(admin_token))

    offer_check = await client.get(f"{SWAPS_URL}/{offer_id}", headers=auth_headers(employee_token))
    assert offer_check.json()["status"] == "cancelled_system"
    assert offer_check.json()["resolution_reason"] == "shift_cancelled"


@pytest.mark.asyncio
async def test_shift_time_change_cancels_open_offer(client, admin_token, employee_token,
                                                     admin_user, employee_user, employee_with_profile, tenant):
    shift_id = await _create_shift(client, admin_token, employee_with_profile.id)
    offer_resp = await client.post(SWAPS_URL, json={"shift_id": shift_id}, headers=auth_headers(employee_token))
    offer_id = offer_resp.json()["id"]

    await client.put(f"{SHIFTS_URL}/{shift_id}", json={"start_time": "09:00:00"}, headers=auth_headers(admin_token))

    offer_check = await client.get(f"{SWAPS_URL}/{offer_id}", headers=auth_headers(employee_token))
    assert offer_check.json()["status"] == "cancelled_system"
    assert offer_check.json()["resolution_reason"] == "shift_changed"


@pytest.mark.asyncio
async def test_absence_approval_cancels_open_offer(client, admin_token, employee_token,
                                                    admin_user, employee_user, employee_with_profile, tenant):
    shift_id = await _create_shift(client, admin_token, employee_with_profile.id)
    offer_resp = await client.post(SWAPS_URL, json={"shift_id": shift_id}, headers=auth_headers(employee_token))
    offer_id = offer_resp.json()["id"]

    absence_resp = await client.post(ABSENCES_URL, json={
        "employee_id": str(employee_with_profile.id),
        "type": "sick",
        "start_date": FUTURE_DATE,
        "end_date": FUTURE_DATE,
        "days_count": 1,
    }, headers=auth_headers(admin_token))
    absence_id = absence_resp.json()["id"]

    await client.put(f"{ABSENCES_URL}/{absence_id}", json={"status": "approved"}, headers=auth_headers(admin_token))

    offer_check = await client.get(f"{SWAPS_URL}/{offer_id}", headers=auth_headers(employee_token))
    assert offer_check.json()["status"] == "cancelled_system"
    assert offer_check.json()["resolution_reason"] == "absence_approved"
