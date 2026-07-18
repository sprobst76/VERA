"""
Tests für /api/v1/notifications – Präferenzen, Logs (Sichtbarkeit), Web-Push-
Subscriptions.
"""
import uuid
from datetime import datetime, time, timezone

import pytest

from app.models.employee import Employee
from app.models.notification import NotificationLog
from app.models.push_subscription import PushSubscription
from tests.conftest import auth_headers

NOTIFICATIONS_URL = "/api/v1/notifications"


async def _link_employee(db, tenant, user, **overrides):
    emp = Employee(
        tenant_id=tenant.id,
        user_id=user.id,
        first_name="Test",
        last_name="Mitarbeiter",
        contract_type="minijob",
        hourly_rate=13.0,
        vacation_days=0,
        **overrides,
    )
    db.add(emp)
    await db.commit()
    await db.refresh(emp)
    return emp


# ── GET/PUT /notifications/preferences ───────────────────────────────────────

@pytest.mark.asyncio
async def test_get_preferences_defaults_without_employee_profile(client, employee_token, employee_user, tenant):
    resp = await client.get(f"{NOTIFICATIONS_URL}/preferences", headers=auth_headers(employee_token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["telegram_chat_id"] is None
    assert data["quiet_hours_start"] == "21:00:00"
    assert data["quiet_hours_end"] == "07:00:00"


@pytest.mark.asyncio
async def test_get_preferences_returns_own_values(client, employee_token, employee_user, tenant, db):
    await _link_employee(db, tenant, employee_user, telegram_chat_id="123456",
                          notification_prefs={"channels": {"email": True}})

    resp = await client.get(f"{NOTIFICATIONS_URL}/preferences", headers=auth_headers(employee_token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["telegram_chat_id"] == "123456"
    assert data["notification_prefs"] == {"channels": {"email": True}}


@pytest.mark.asyncio
async def test_update_preferences(client, employee_token, employee_user, tenant, db):
    await _link_employee(db, tenant, employee_user)

    resp = await client.put(f"{NOTIFICATIONS_URL}/preferences", json={
        "telegram_chat_id": "987654",
        "quiet_hours_start": "22:00:00",
        "quiet_hours_end": "06:00:00",
        "notification_prefs": {"channels": {"telegram": True}, "events": {"shift_reminder": False}},
    }, headers=auth_headers(employee_token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["telegram_chat_id"] == "987654"
    assert data["quiet_hours_start"] == "22:00:00"
    assert data["notification_prefs"]["events"]["shift_reminder"] is False


@pytest.mark.asyncio
async def test_update_preferences_without_employee_profile_404(client, employee_token, employee_user, tenant):
    resp = await client.put(f"{NOTIFICATIONS_URL}/preferences", json={"telegram_chat_id": "123"},
                             headers=auth_headers(employee_token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_preferences_rejects_unknown_field(client, employee_token, employee_user, tenant, db):
    await _link_employee(db, tenant, employee_user)
    resp = await client.put(f"{NOTIFICATIONS_URL}/preferences", json={"unknown_field": "x"},
                             headers=auth_headers(employee_token))
    assert resp.status_code == 422


# ── GET /notifications/logs ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_employee_sees_only_own_logs(client, admin_token, admin_user, employee_token, employee_user, tenant, db):
    own_emp = await _link_employee(db, tenant, employee_user)
    other_emp = Employee(tenant_id=tenant.id, first_name="Other", last_name="Person",
                          contract_type="minijob", hourly_rate=13.0, vacation_days=0)
    db.add(other_emp)
    await db.commit()
    await db.refresh(other_emp)

    db.add_all([
        NotificationLog(tenant_id=tenant.id, employee_id=own_emp.id, channel="email",
                         event_type="shift_assigned", status="sent", created_at=datetime.now(timezone.utc)),
        NotificationLog(tenant_id=tenant.id, employee_id=other_emp.id, channel="email",
                         event_type="shift_assigned", status="sent", created_at=datetime.now(timezone.utc)),
    ])
    await db.commit()

    resp = await client.get(f"{NOTIFICATIONS_URL}/logs", headers=auth_headers(employee_token))
    assert resp.status_code == 200
    logs = resp.json()
    assert len(logs) == 1
    assert logs[0]["employee_id"] == str(own_emp.id)


@pytest.mark.asyncio
async def test_admin_sees_all_logs(client, admin_token, admin_user, tenant, db):
    emp = Employee(tenant_id=tenant.id, first_name="Any", last_name="One",
                    contract_type="minijob", hourly_rate=13.0, vacation_days=0)
    db.add(emp)
    await db.commit()
    await db.refresh(emp)

    db.add(NotificationLog(tenant_id=tenant.id, employee_id=emp.id, channel="telegram",
                            event_type="shift_reminder", status="failed", created_at=datetime.now(timezone.utc)))
    await db.commit()

    resp = await client.get(f"{NOTIFICATIONS_URL}/logs", headers=auth_headers(admin_token))
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_logs_filter_by_channel_and_status(client, admin_token, admin_user, tenant, db):
    emp = Employee(tenant_id=tenant.id, first_name="Any", last_name="One",
                    contract_type="minijob", hourly_rate=13.0, vacation_days=0)
    db.add(emp)
    await db.commit()
    await db.refresh(emp)

    db.add_all([
        NotificationLog(tenant_id=tenant.id, employee_id=emp.id, channel="email",
                         event_type="shift_assigned", status="sent", created_at=datetime.now(timezone.utc)),
        NotificationLog(tenant_id=tenant.id, employee_id=emp.id, channel="telegram",
                         event_type="shift_assigned", status="failed", created_at=datetime.now(timezone.utc)),
    ])
    await db.commit()

    resp = await client.get(f"{NOTIFICATIONS_URL}/logs", params={"channel": "telegram"},
                             headers=auth_headers(admin_token))
    assert len(resp.json()) == 1
    assert resp.json()[0]["channel"] == "telegram"

    resp2 = await client.get(f"{NOTIFICATIONS_URL}/logs", params={"status": "failed"},
                              headers=auth_headers(admin_token))
    assert len(resp2.json()) == 1
    assert resp2.json()[0]["status"] == "failed"


# ── GET /notifications/vapid-key ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_vapid_key_no_auth_required(client):
    resp = await client.get(f"{NOTIFICATIONS_URL}/vapid-key")
    assert resp.status_code == 200
    assert "public_key" in resp.json()


# ── Push-Subscriptions ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_subscribe_push_activates_channel(client, employee_token, employee_user, tenant, db):
    await _link_employee(db, tenant, employee_user, notification_prefs={"channels": {"email": True}})

    resp = await client.post(f"{NOTIFICATIONS_URL}/push-subscription", json={
        "endpoint": "https://push.example.com/abc",
        "p256dh": "key1", "auth": "auth1",
    }, headers=auth_headers(employee_token))
    assert resp.status_code == 201

    prefs_resp = await client.get(f"{NOTIFICATIONS_URL}/preferences", headers=auth_headers(employee_token))
    assert prefs_resp.json()["notification_prefs"]["channels"]["push"] is True


@pytest.mark.asyncio
async def test_subscribe_push_without_employee_profile_404(client, employee_token, employee_user, tenant):
    resp = await client.post(f"{NOTIFICATIONS_URL}/push-subscription", json={
        "endpoint": "https://push.example.com/xyz", "p256dh": "key1", "auth": "auth1",
    }, headers=auth_headers(employee_token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_subscribe_push_upserts_existing_endpoint(client, employee_token, employee_user, tenant, db):
    emp = await _link_employee(db, tenant, employee_user)
    endpoint = "https://push.example.com/same"

    await client.post(f"{NOTIFICATIONS_URL}/push-subscription",
                       json={"endpoint": endpoint, "p256dh": "old", "auth": "old"},
                       headers=auth_headers(employee_token))
    await client.post(f"{NOTIFICATIONS_URL}/push-subscription",
                       json={"endpoint": endpoint, "p256dh": "new", "auth": "new"},
                       headers=auth_headers(employee_token))

    db.expire_all()
    from sqlalchemy import select
    result = await db.execute(select(PushSubscription).where(PushSubscription.endpoint == endpoint))
    subs = result.scalars().all()
    assert len(subs) == 1
    assert subs[0].p256dh == "new"


@pytest.mark.asyncio
async def test_unsubscribe_push_deactivates_channel_when_last(client, employee_token, employee_user, tenant, db):
    await _link_employee(db, tenant, employee_user)
    endpoint = "https://push.example.com/only"

    await client.post(f"{NOTIFICATIONS_URL}/push-subscription",
                       json={"endpoint": endpoint, "p256dh": "k", "auth": "a"},
                       headers=auth_headers(employee_token))

    resp = await client.request("DELETE", f"{NOTIFICATIONS_URL}/push-subscription",
                                 json={"endpoint": endpoint}, headers=auth_headers(employee_token))
    assert resp.status_code == 200

    prefs_resp = await client.get(f"{NOTIFICATIONS_URL}/preferences", headers=auth_headers(employee_token))
    assert prefs_resp.json()["notification_prefs"]["channels"]["push"] is False


@pytest.mark.asyncio
async def test_unsubscribe_push_keeps_channel_when_others_remain(client, employee_token, employee_user, tenant, db):
    await _link_employee(db, tenant, employee_user)

    await client.post(f"{NOTIFICATIONS_URL}/push-subscription",
                       json={"endpoint": "https://push.example.com/one", "p256dh": "k", "auth": "a"},
                       headers=auth_headers(employee_token))
    await client.post(f"{NOTIFICATIONS_URL}/push-subscription",
                       json={"endpoint": "https://push.example.com/two", "p256dh": "k", "auth": "a"},
                       headers=auth_headers(employee_token))

    resp = await client.request("DELETE", f"{NOTIFICATIONS_URL}/push-subscription",
                                 json={"endpoint": "https://push.example.com/one"},
                                 headers=auth_headers(employee_token))
    assert resp.status_code == 200

    prefs_resp = await client.get(f"{NOTIFICATIONS_URL}/preferences", headers=auth_headers(employee_token))
    assert prefs_resp.json()["notification_prefs"]["channels"]["push"] is True
