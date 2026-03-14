"""
Tests für /api/v1/webhooks – CRUD + Dispatch.
"""
import pytest
from tests.conftest import auth_headers

URL = "/api/v1/webhooks"
EVENTS_URL = "/api/v1/webhooks/events"


@pytest.mark.asyncio
async def test_list_webhooks_empty(client, admin_token, admin_user, tenant):
    resp = await client.get(URL, headers=auth_headers(admin_token))
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_events_list(client, admin_token, admin_user, tenant):
    resp = await client.get(EVENTS_URL, headers=auth_headers(admin_token))
    assert resp.status_code == 200
    events = resp.json()
    assert "shift.created" in events
    assert "payroll.created" in events
    assert "absence.approved" in events


@pytest.mark.asyncio
async def test_create_webhook(client, admin_token, admin_user, tenant):
    resp = await client.post(URL, json={
        "name": "Test Webhook",
        "url": "https://example.com/hook",
        "events": ["shift.created", "payroll.created"],
    }, headers=auth_headers(admin_token))
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Test Webhook"
    assert data["is_active"] is True
    assert "shift.created" in data["events"]


@pytest.mark.asyncio
async def test_create_webhook_unknown_event(client, admin_token, admin_user, tenant):
    resp = await client.post(URL, json={
        "name": "Bad",
        "url": "https://example.com/hook",
        "events": ["unknown.event"],
    }, headers=auth_headers(admin_token))
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_webhook_employee_forbidden(client, employee_token, employee_user, tenant):
    resp = await client.post(URL, json={
        "name": "X",
        "url": "https://example.com/hook",
        "events": ["shift.created"],
    }, headers=auth_headers(employee_token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_webhook(client, admin_token, admin_user, tenant):
    # Create
    create = await client.post(URL, json={
        "name": "Initial",
        "url": "https://example.com/hook",
        "events": ["shift.created"],
    }, headers=auth_headers(admin_token))
    wh_id = create.json()["id"]

    # Update
    resp = await client.put(f"{URL}/{wh_id}", json={
        "name": "Updated",
        "is_active": False,
    }, headers=auth_headers(admin_token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Updated"
    assert data["is_active"] is False


@pytest.mark.asyncio
async def test_delete_webhook(client, admin_token, admin_user, tenant):
    create = await client.post(URL, json={
        "name": "ToDelete",
        "url": "https://example.com/hook",
        "events": ["shift.created"],
    }, headers=auth_headers(admin_token))
    wh_id = create.json()["id"]

    del_resp = await client.delete(f"{URL}/{wh_id}", headers=auth_headers(admin_token))
    assert del_resp.status_code == 204

    list_resp = await client.get(URL, headers=auth_headers(admin_token))
    ids = [w["id"] for w in list_resp.json()]
    assert wh_id not in ids


@pytest.mark.asyncio
async def test_delete_webhook_not_found(client, admin_token, admin_user, tenant):
    import uuid
    resp = await client.delete(f"{URL}/{uuid.uuid4()}", headers=auth_headers(admin_token))
    assert resp.status_code == 404
