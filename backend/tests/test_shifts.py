"""
Tests für /api/v1/shifts und /api/v1/shift-templates – CRUD, RBAC, Bulk.
"""
import uuid
import pytest
from tests.conftest import auth_headers

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
