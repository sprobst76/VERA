"""
Tests für /api/v1/shift-types – CRUD, RBAC, Soft-Delete, Tenant-Isolation.
"""
import pytest
from tests.conftest import auth_headers

URL = "/api/v1/shift-types"

PAYLOAD = {
    "name": "Frühdienst",
    "color": "#FF5733",
    "description": "Morgens früh",
    "reminder_enabled": True,
    "reminder_minutes_before": 60,
}


# ── Helper ────────────────────────────────────────────────────────────────────

async def create_shift_type(client, token, payload=None):
    resp = await client.post(URL, json=payload or PAYLOAD, headers=auth_headers(token))
    assert resp.status_code == 201
    return resp.json()


# ── GET /shift-types ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_shift_types_empty(client, admin_token, admin_user, tenant):
    resp = await client.get(URL, headers=auth_headers(admin_token))
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_shift_types_employee_allowed(client, employee_token, employee_user, tenant):
    """Mitarbeiter darf Diensttypen lesen."""
    resp = await client.get(URL, headers=auth_headers(employee_token))
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_shift_types_requires_auth(client):
    resp = await client.get(URL)
    assert resp.status_code in (401, 403)


# ── POST /shift-types ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_shift_type_admin(client, admin_token, admin_user, tenant):
    resp = await client.post(URL, json=PAYLOAD, headers=auth_headers(admin_token))
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Frühdienst"
    assert data["color"] == "#FF5733"
    assert data["reminder_enabled"] is True
    assert data["reminder_minutes_before"] == 60
    assert data["is_active"] is True
    assert "id" in data


@pytest.mark.asyncio
async def test_create_shift_type_employee_forbidden(client, employee_token, employee_user, tenant):
    resp = await client.post(URL, json=PAYLOAD, headers=auth_headers(employee_token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_shift_type_missing_name(client, admin_token, admin_user, tenant):
    resp = await client.post(URL, json={"color": "#123456", "reminder_enabled": False,
                                        "reminder_minutes_before": 60},
                             headers=auth_headers(admin_token))
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_shift_type_reminder_disabled(client, admin_token, admin_user, tenant):
    payload = {**PAYLOAD, "reminder_enabled": False, "name": "Spätdienst"}
    st = await create_shift_type(client, admin_token, payload)
    assert st["reminder_enabled"] is False


@pytest.mark.asyncio
async def test_create_shift_type_appears_in_list(client, admin_token, admin_user, tenant):
    await create_shift_type(client, admin_token)
    resp = await client.get(URL, headers=auth_headers(admin_token))
    assert resp.status_code == 200
    names = [st["name"] for st in resp.json()]
    assert "Frühdienst" in names


# ── PUT /shift-types/{id} ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_shift_type(client, admin_token, admin_user, tenant):
    st = await create_shift_type(client, admin_token)
    resp = await client.put(f"{URL}/{st['id']}", json={"name": "Nachtdienst", "color": "#000000"},
                            headers=auth_headers(admin_token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Nachtdienst"
    assert data["color"] == "#000000"
    # Unveränderte Felder bleiben
    assert data["reminder_enabled"] == st["reminder_enabled"]


@pytest.mark.asyncio
async def test_update_shift_type_employee_forbidden(client, admin_token, employee_token,
                                                    admin_user, employee_user, tenant):
    st = await create_shift_type(client, admin_token)
    resp = await client.put(f"{URL}/{st['id']}", json={"name": "X"},
                            headers=auth_headers(employee_token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_shift_type_not_found(client, admin_token, admin_user, tenant):
    import uuid
    resp = await client.put(f"{URL}/{uuid.uuid4()}", json={"name": "X"},
                            headers=auth_headers(admin_token))
    assert resp.status_code == 404


# ── DELETE /shift-types/{id} (Soft-Delete) ────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_shift_type_soft(client, admin_token, admin_user, tenant):
    """Löschen setzt is_active=False; der Typ erscheint nicht mehr in der Liste."""
    st = await create_shift_type(client, admin_token)
    resp = await client.delete(f"{URL}/{st['id']}", headers=auth_headers(admin_token))
    assert resp.status_code == 204

    # Nicht mehr in der Liste
    list_resp = await client.get(URL, headers=auth_headers(admin_token))
    ids = [s["id"] for s in list_resp.json()]
    assert st["id"] not in ids


@pytest.mark.asyncio
async def test_delete_shift_type_employee_forbidden(client, admin_token, employee_token,
                                                    admin_user, employee_user, tenant):
    st = await create_shift_type(client, admin_token)
    resp = await client.delete(f"{URL}/{st['id']}", headers=auth_headers(employee_token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_shift_type_not_found(client, admin_token, admin_user, tenant):
    import uuid
    resp = await client.delete(f"{URL}/{uuid.uuid4()}", headers=auth_headers(admin_token))
    assert resp.status_code == 404


# ── Sortierung & Rückgabe ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_shift_types_sorted_by_name(client, admin_token, admin_user, tenant):
    """Liste ist alphabetisch nach Name sortiert."""
    for name in ["Zulu", "Alpha", "Mike"]:
        await create_shift_type(client, admin_token, {**PAYLOAD, "name": name})

    resp = await client.get(URL, headers=auth_headers(admin_token))
    names = [st["name"] for st in resp.json()]
    assert names == sorted(names)
