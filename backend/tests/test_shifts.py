"""
Tests für /api/v1/shifts und /api/v1/shift-templates – CRUD, RBAC, Bulk, Claim/Pool.
"""
import uuid
import pytest
import pytest_asyncio
from datetime import datetime, timezone
from tests.conftest import auth_headers
from app.models.employee import Employee

SHIFTS_URL = "/api/v1/shifts"
TEMPLATES_URL = "/api/v1/shift-templates"

TEMPLATE_PAYLOAD = {
    "name": "Tagschicht",
    "weekdays": [0, 1, 2, 3, 4],  # Mo–Fr
    "start_time": "08:00:00",
    "end_time": "16:00:00",
    "break_minutes": 30,
    "color": "#1E3A5F",
}

SHIFT_PAYLOAD = {
    "date": "2025-09-01",
    "start_time": "08:00:00",
    "end_time": "16:00:00",
    "break_minutes": 30,
}


# ── Helper: Shift-Template anlegen ────────────────────────────────────────────

async def create_template(client, token):
    resp = await client.post(TEMPLATES_URL, json=TEMPLATE_PAYLOAD, headers=auth_headers(token))
    assert resp.status_code == 201
    return resp.json()


# ── POST /shifts ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_shift_admin(client, admin_token, admin_user, tenant):
    resp = await client.post(SHIFTS_URL, json=SHIFT_PAYLOAD, headers=auth_headers(admin_token))
    assert resp.status_code == 201
    data = resp.json()
    assert data["date"] == "2025-09-01"
    assert data["status"] == "planned"
    assert "id" in data


@pytest.mark.asyncio
async def test_create_shift_employee_forbidden(client, employee_token, employee_user, tenant):
    resp = await client.post(SHIFTS_URL, json=SHIFT_PAYLOAD, headers=auth_headers(employee_token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_shift_missing_fields(client, admin_token, admin_user, tenant):
    resp = await client.post(SHIFTS_URL, json={"date": "2025-09-01"}, headers=auth_headers(admin_token))
    assert resp.status_code == 422


# ── GET /shifts ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_shifts_admin_sees_all(client, admin_token, admin_user, tenant):
    # Zwei Schichten anlegen
    for day in ["01", "02"]:
        payload = {**SHIFT_PAYLOAD, "date": f"2025-09-{day}"}
        await client.post(SHIFTS_URL, json=payload, headers=auth_headers(admin_token))

    resp = await client.get(SHIFTS_URL, headers=auth_headers(admin_token))
    assert resp.status_code == 200
    assert len(resp.json()) >= 2


@pytest.mark.asyncio
async def test_list_shifts_employee_sees_only_own(client, admin_token, employee_token,
                                                   admin_user, employee_user, db, tenant):
    """Employee sieht nur eigene Schichten (und hat keinen verknüpften Employee-Datensatz → leere Liste)."""
    # Admin legt Schicht ohne employee_id an
    await client.post(SHIFTS_URL, json=SHIFT_PAYLOAD, headers=auth_headers(admin_token))

    # Employee hat kein Employee-Profil → leere Liste
    resp = await client.get(SHIFTS_URL, headers=auth_headers(employee_token))
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_shifts_date_filter(client, admin_token, admin_user, tenant):
    """from_date/to_date-Filter begrenzt die Ergebnisse."""
    for day in ["01", "15"]:
        payload = {**SHIFT_PAYLOAD, "date": f"2025-09-{day}"}
        await client.post(SHIFTS_URL, json=payload, headers=auth_headers(admin_token))

    resp = await client.get(
        SHIFTS_URL,
        params={"from_date": "2025-09-01", "to_date": "2025-09-05"},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    dates = [s["date"] for s in resp.json()]
    assert "2025-09-01" in dates
    assert "2025-09-15" not in dates


# ── PUT /shifts/{id} ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_shift_status_to_confirmed(client, admin_token, admin_user, tenant):
    create = await client.post(SHIFTS_URL, json=SHIFT_PAYLOAD, headers=auth_headers(admin_token))
    shift_id = create.json()["id"]

    resp = await client.put(
        f"{SHIFTS_URL}/{shift_id}",
        json={"status": "confirmed"},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "confirmed"


@pytest.mark.asyncio
async def test_update_shift_employee_forbidden(client, admin_token, employee_token,
                                                admin_user, employee_user, tenant):
    create = await client.post(SHIFTS_URL, json=SHIFT_PAYLOAD, headers=auth_headers(admin_token))
    shift_id = create.json()["id"]

    resp = await client.put(
        f"{SHIFTS_URL}/{shift_id}",
        json={"status": "confirmed"},
        headers=auth_headers(employee_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_edit_confirmed_shift_times(client, admin_token, admin_user, tenant):
    """Admin darf Zeiten eines bereits bestätigten Dienstes korrigieren."""
    create = await client.post(SHIFTS_URL, json=SHIFT_PAYLOAD, headers=auth_headers(admin_token))
    shift_id = create.json()["id"]
    # Dienst bestätigen
    await client.put(f"{SHIFTS_URL}/{shift_id}", json={"status": "confirmed"}, headers=auth_headers(admin_token))

    resp = await client.put(
        f"{SHIFTS_URL}/{shift_id}",
        json={"start_time": "09:00:00", "end_time": "17:00:00", "actual_start": "09:05:00", "actual_end": "17:10:00"},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["start_time"] == "09:00:00"
    assert data["end_time"] == "17:00:00"
    assert data["actual_start"] == "09:05:00"
    assert data["actual_end"] == "17:10:00"
    assert data["status"] == "confirmed"  # Status bleibt bestätigt


@pytest.mark.asyncio
async def test_employee_cannot_edit_confirmed_shift(client, admin_token, employee_token,
                                                     admin_user, employee_user, tenant):
    """Mitarbeiter darf bestätigte Dienste nicht bearbeiten (403)."""
    create = await client.post(SHIFTS_URL, json=SHIFT_PAYLOAD, headers=auth_headers(admin_token))
    shift_id = create.json()["id"]
    # Dienst bestätigen (als Admin)
    await client.put(f"{SHIFTS_URL}/{shift_id}", json={"status": "confirmed"}, headers=auth_headers(admin_token))

    resp = await client.put(
        f"{SHIFTS_URL}/{shift_id}",
        json={"notes": "Versuch"},
        headers=auth_headers(employee_token),
    )
    assert resp.status_code == 403


# ── DELETE /shifts/{id} ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_shift_admin(client, admin_token, admin_user, tenant):
    create = await client.post(SHIFTS_URL, json=SHIFT_PAYLOAD, headers=auth_headers(admin_token))
    shift_id = create.json()["id"]

    resp = await client.delete(f"{SHIFTS_URL}/{shift_id}", headers=auth_headers(admin_token))
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_shift_employee_forbidden(client, admin_token, employee_token,
                                                admin_user, employee_user, tenant):
    create = await client.post(SHIFTS_URL, json=SHIFT_PAYLOAD, headers=auth_headers(admin_token))
    shift_id = create.json()["id"]

    resp = await client.delete(f"{SHIFTS_URL}/{shift_id}", headers=auth_headers(employee_token))
    assert resp.status_code == 403


# ── POST /shifts/bulk ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bulk_shift_creation(client, admin_token, admin_user, tenant):
    """Template Mo–Fr, 2 Wochen → 10 Schichten."""
    tpl = await create_template(client, admin_token)

    resp = await client.post(
        f"{SHIFTS_URL}/bulk",
        json={
            "template_id": tpl["id"],
            "from_date": "2025-09-01",  # Montag
            "to_date": "2025-09-12",    # Freitag der 2. Woche
        },
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 201
    shifts = resp.json()
    assert len(shifts) == 10  # 5 Mo–Fr × 2 Wochen
    assert all(s["status"] == "planned" for s in shifts)


# ── POST /shifts/{id}/claim ───────────────────────────────────────────────────

@pytest_asyncio.fixture
async def employee_with_profile(db, employee_user, tenant):
    """Erstellt ein Employee-Profil, verknüpft mit employee_user."""
    emp = Employee(
        tenant_id=tenant.id,
        user_id=employee_user.id,
        first_name="Test",
        last_name="Mitarbeiter",
        contract_type="minijob",
        hourly_rate=13.0,
        qualifications=[],
        notification_prefs={},
        vacation_days=20,
        vacation_carryover=0,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db.add(emp)
    await db.commit()
    await db.refresh(emp)
    return emp


@pytest.mark.asyncio
async def test_claim_open_shift(client, admin_token, employee_token,
                                 admin_user, employee_user, employee_with_profile, tenant):
    """Mitarbeiter nimmt offene Schicht (ohne employee_id) erfolgreich an."""
    create = await client.post(SHIFTS_URL, json=SHIFT_PAYLOAD, headers=auth_headers(admin_token))
    assert create.status_code == 201
    shift_id = create.json()["id"]
    assert create.json()["employee_id"] is None

    resp = await client.post(f"{SHIFTS_URL}/{shift_id}/claim", headers=auth_headers(employee_token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["employee_id"] == str(employee_with_profile.id)


@pytest.mark.asyncio
async def test_claim_already_taken_shift(client, admin_token, employee_token,
                                          admin_user, employee_user, employee_with_profile, tenant):
    """Schicht mit employee_id kann nicht ge-claimed werden → 409."""
    payload = {**SHIFT_PAYLOAD, "employee_id": str(employee_with_profile.id)}
    create = await client.post(SHIFTS_URL, json=payload, headers=auth_headers(admin_token))
    shift_id = create.json()["id"]

    resp = await client.post(f"{SHIFTS_URL}/{shift_id}/claim", headers=auth_headers(employee_token))
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_claim_shift_admin_forbidden(client, admin_token, admin_user, tenant):
    """Admin darf keine Schichten claimen (nur Mitarbeiter)."""
    create = await client.post(SHIFTS_URL, json=SHIFT_PAYLOAD, headers=auth_headers(admin_token))
    shift_id = create.json()["id"]

    resp = await client.post(f"{SHIFTS_URL}/{shift_id}/claim", headers=auth_headers(admin_token))
    assert resp.status_code == 403


# ── Claim-Compliance-Pre-Check (Minijob-Grenze / Ruhezeit) ──────────────────────

@pytest.mark.asyncio
async def test_claim_blocked_over_minijob_annual_limit(client, admin_token, employee_token,
                                                        admin_user, employee_user,
                                                        employee_with_profile, db, tenant):
    """Claim wird blockiert, wenn der Mitarbeiter die Minijob-Jahresgrenze bereits gerissen hat."""
    from datetime import date
    from decimal import Decimal
    from app.models.contract_history import ContractHistory
    from app.models.payroll import PayrollEntry

    db.add(ContractHistory(
        tenant_id=tenant.id,
        employee_id=employee_with_profile.id,
        valid_from=date(2025, 1, 1),
        valid_to=None,
        contract_type="minijob",
        hourly_rate=13.0,
    ))
    db.add(PayrollEntry(
        tenant_id=tenant.id,
        employee_id=employee_with_profile.id,
        month=date(2025, 6, 1),
        actual_hours=40.0,
        paid_hours=40.0,
        base_wage=Decimal("7000.00"),
        total_gross=Decimal("7000.00"),  # bereits über der 6.672€-Jahresgrenze
        status="approved",
    ))
    await db.commit()

    payload = {**SHIFT_PAYLOAD, "date": "2025-09-01"}
    create = await client.post(SHIFTS_URL, json=payload, headers=auth_headers(admin_token))
    shift_id = create.json()["id"]

    resp = await client.post(f"{SHIFTS_URL}/{shift_id}/claim", headers=auth_headers(employee_token))
    assert resp.status_code == 409
    assert "Minijob-Jahresgrenze" in resp.json()["detail"]

    check = await client.get(f"{SHIFTS_URL}/{shift_id}", headers=auth_headers(admin_token))
    assert check.json()["employee_id"] is None


@pytest.mark.asyncio
async def test_claim_blocked_by_rest_period_violation(client, admin_token, employee_token,
                                                        admin_user, employee_user,
                                                        employee_with_profile, tenant):
    """Claim wird blockiert, wenn er die 11h-Ruhezeit zum vorherigen Dienst unterschreiten würde."""
    # Vorheriger, bereits zugewiesener Dienst bis 22:00
    prev_payload = {
        "date": "2025-09-01", "start_time": "14:00:00", "end_time": "22:00:00",
        "break_minutes": 30, "employee_id": str(employee_with_profile.id),
    }
    await client.post(SHIFTS_URL, json=prev_payload, headers=auth_headers(admin_token))

    # Offener Dienst am Folgetag ab 06:00 → nur 8h Ruhezeit
    open_payload = {"date": "2025-09-02", "start_time": "06:00:00", "end_time": "14:00:00", "break_minutes": 30}
    create = await client.post(SHIFTS_URL, json=open_payload, headers=auth_headers(admin_token))
    shift_id = create.json()["id"]

    resp = await client.post(f"{SHIFTS_URL}/{shift_id}/claim", headers=auth_headers(employee_token))
    assert resp.status_code == 409
    assert "Ruhezeit" in resp.json()["detail"]


# ── POST /shifts/{id}/acknowledge ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_acknowledge_own_shift(client, admin_token, employee_token,
                                      admin_user, employee_user, employee_with_profile, tenant):
    """Mitarbeiter quittiert den eigenen zugewiesenen Dienst."""
    payload = {**SHIFT_PAYLOAD, "employee_id": str(employee_with_profile.id)}
    create = await client.post(SHIFTS_URL, json=payload, headers=auth_headers(admin_token))
    shift_id = create.json()["id"]
    assert create.json()["acknowledged_at"] is None

    resp = await client.post(f"{SHIFTS_URL}/{shift_id}/acknowledge", headers=auth_headers(employee_token))
    assert resp.status_code == 200
    assert resp.json()["acknowledged_at"] is not None


@pytest.mark.asyncio
async def test_acknowledge_is_idempotent(client, admin_token, employee_token,
                                          admin_user, employee_user, employee_with_profile, tenant):
    """Zweimaliges Quittieren überschreibt den Zeitstempel nicht."""
    payload = {**SHIFT_PAYLOAD, "employee_id": str(employee_with_profile.id)}
    create = await client.post(SHIFTS_URL, json=payload, headers=auth_headers(admin_token))
    shift_id = create.json()["id"]

    first = await client.post(f"{SHIFTS_URL}/{shift_id}/acknowledge", headers=auth_headers(employee_token))
    second = await client.post(f"{SHIFTS_URL}/{shift_id}/acknowledge", headers=auth_headers(employee_token))
    assert first.json()["acknowledged_at"] == second.json()["acknowledged_at"]


@pytest.mark.asyncio
async def test_acknowledge_other_employees_shift_forbidden(client, admin_token, employee_token,
                                                            admin_user, employee_user,
                                                            employee_with_profile, db, tenant):
    """Mitarbeiter darf fremden Dienst nicht quittieren."""
    other_emp = Employee(
        tenant_id=tenant.id,
        first_name="Andere",
        last_name="Person",
        contract_type="minijob",
        hourly_rate=13.0,
        vacation_days=0,
        is_active=True,
    )
    db.add(other_emp)
    await db.commit()
    await db.refresh(other_emp)

    payload = {**SHIFT_PAYLOAD, "employee_id": str(other_emp.id)}
    create = await client.post(SHIFTS_URL, json=payload, headers=auth_headers(admin_token))
    shift_id = create.json()["id"]

    resp = await client.post(f"{SHIFTS_URL}/{shift_id}/acknowledge", headers=auth_headers(employee_token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_acknowledge_unassigned_shift_forbidden(client, admin_token, employee_token,
                                                        admin_user, employee_user,
                                                        employee_with_profile, tenant):
    """Ein noch offener (nicht zugewiesener) Dienst kann nicht quittiert werden."""
    create = await client.post(SHIFTS_URL, json=SHIFT_PAYLOAD, headers=auth_headers(admin_token))
    shift_id = create.json()["id"]

    resp = await client.post(f"{SHIFTS_URL}/{shift_id}/acknowledge", headers=auth_headers(employee_token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_acknowledge_admin_forbidden(client, admin_token, admin_user, employee_with_profile, tenant):
    """Admin/Manager quittieren nicht (das ist eine Mitarbeiter-Handlung)."""
    payload = {**SHIFT_PAYLOAD, "employee_id": str(employee_with_profile.id)}
    create = await client.post(SHIFTS_URL, json=payload, headers=auth_headers(admin_token))
    shift_id = create.json()["id"]

    resp = await client.post(f"{SHIFTS_URL}/{shift_id}/acknowledge", headers=auth_headers(admin_token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_shift_time_change_resets_acknowledgement(client, admin_token, employee_token,
                                                          admin_user, employee_user,
                                                          employee_with_profile, tenant):
    """Ändert der Admin Zeit/Ort eines quittierten Dienstes, wird die Quittierung zurückgesetzt."""
    payload = {**SHIFT_PAYLOAD, "employee_id": str(employee_with_profile.id)}
    create = await client.post(SHIFTS_URL, json=payload, headers=auth_headers(admin_token))
    shift_id = create.json()["id"]

    ack = await client.post(f"{SHIFTS_URL}/{shift_id}/acknowledge", headers=auth_headers(employee_token))
    assert ack.json()["acknowledged_at"] is not None

    update = await client.put(
        f"{SHIFTS_URL}/{shift_id}",
        json={"start_time": "09:00:00"},
        headers=auth_headers(admin_token),
    )
    assert update.status_code == 200
    assert update.json()["acknowledged_at"] is None


@pytest.mark.asyncio
async def test_employee_sees_open_shifts_in_list(client, admin_token, employee_token,
                                                   admin_user, employee_user,
                                                   employee_with_profile, tenant):
    """Mitarbeiter sieht eigene Schichten + offene Schichten im Pool."""
    # Offene Schicht (kein employee_id)
    open_shift = await client.post(SHIFTS_URL, json=SHIFT_PAYLOAD, headers=auth_headers(admin_token))
    open_id = open_shift.json()["id"]

    # Eigene Schicht (mit employee_id)
    own_payload = {**SHIFT_PAYLOAD, "date": "2025-09-02", "employee_id": str(employee_with_profile.id)}
    own_shift = await client.post(SHIFTS_URL, json=own_payload, headers=auth_headers(admin_token))
    own_id = own_shift.json()["id"]

    # Andere Mitarbeiter-Schicht (anderer employee_id) → darf nicht sichtbar sein
    other_emp_id = str(uuid.uuid4())
    other_payload = {**SHIFT_PAYLOAD, "date": "2025-09-03"}
    await client.post(SHIFTS_URL, json={**other_payload}, headers=auth_headers(admin_token))

    resp = await client.get(SHIFTS_URL, headers=auth_headers(employee_token))
    assert resp.status_code == 200
    ids = [s["id"] for s in resp.json()]
    assert open_id in ids    # offene Schicht sichtbar
    assert own_id in ids     # eigene Schicht sichtbar
