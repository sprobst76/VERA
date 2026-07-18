"""
Tests für /api/v1/feedback – Änderungswünsche/Bug-Meldungen (Rückkanal aus /help).
"""
import uuid

import pytest

from tests.conftest import auth_headers

FEEDBACK_URL = "/api/v1/feedback"


@pytest.mark.asyncio
async def test_create_feedback(client, employee_token, employee_user, tenant):
    resp = await client.post(FEEDBACK_URL, json={
        "category": "bug", "title": "PDF lädt nicht", "description": "Beim Klick auf Download passiert nichts.",
    }, headers=auth_headers(employee_token))
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "open"
    assert data["category"] == "bug"
    assert data["reporter_name"] == employee_user.email  # kein Employee-Profil verknüpft -> Fallback E-Mail


@pytest.mark.asyncio
async def test_create_feedback_uses_employee_name_when_linked(client, employee_token, employee_user, tenant, db):
    from app.models.employee import Employee
    emp = Employee(
        tenant_id=tenant.id, user_id=employee_user.id,
        first_name="Nina", last_name="Beispiel",
        contract_type="minijob", hourly_rate=13.0, vacation_days=0,
    )
    db.add(emp)
    await db.commit()

    resp = await client.post(FEEDBACK_URL, json={"category": "wish", "title": "Dark Mode Icon größer", "description": "..."},
                              headers=auth_headers(employee_token))
    assert resp.json()["reporter_name"] == "Nina Beispiel"


@pytest.mark.asyncio
async def test_create_feedback_invalid_category_rejected(client, employee_token, employee_user, tenant):
    resp = await client.post(FEEDBACK_URL, json={"category": "invalid", "title": "X", "description": "Y"},
                              headers=auth_headers(employee_token))
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_parent_viewer_cannot_submit_feedback(client, db, tenant):
    from app.core.security import create_access_token
    from app.models.user import User
    from datetime import datetime, timezone

    pv_user = User(tenant_id=tenant.id, email="viewer@test.de", hashed_password="x",
                   role="parent_viewer", is_active=True, created_at=datetime.now(timezone.utc))
    db.add(pv_user)
    await db.commit()
    await db.refresh(pv_user)
    token = create_access_token(pv_user.id, pv_user.tenant_id, "parent_viewer", token_version=pv_user.token_version)

    resp = await client.post(FEEDBACK_URL, json={"category": "bug", "title": "X", "description": "Y"},
                              headers=auth_headers(token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_employee_sees_only_own_feedback(client, admin_token, employee_token, employee_user, admin_user, tenant):
    await client.post(FEEDBACK_URL, json={"category": "bug", "title": "Mein Bug", "description": "..."},
                       headers=auth_headers(employee_token))
    await client.post(FEEDBACK_URL, json={"category": "bug", "title": "Admin-Meldung", "description": "..."},
                       headers=auth_headers(admin_token))

    resp = await client.get(FEEDBACK_URL, headers=auth_headers(employee_token))
    titles = [f["title"] for f in resp.json()]
    assert titles == ["Mein Bug"]


@pytest.mark.asyncio
async def test_admin_sees_all_feedback(client, admin_token, employee_token, employee_user, admin_user, tenant):
    await client.post(FEEDBACK_URL, json={"category": "bug", "title": "Mein Bug", "description": "..."},
                       headers=auth_headers(employee_token))
    await client.post(FEEDBACK_URL, json={"category": "wish", "title": "Admin-Wunsch", "description": "..."},
                       headers=auth_headers(admin_token))

    resp = await client.get(FEEDBACK_URL, headers=auth_headers(admin_token))
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_admin_updates_status_and_note(client, admin_token, employee_token, employee_user, admin_user, tenant):
    create_resp = await client.post(FEEDBACK_URL, json={"category": "bug", "title": "X", "description": "Y"},
                                     headers=auth_headers(employee_token))
    feedback_id = create_resp.json()["id"]

    resp = await client.patch(f"{FEEDBACK_URL}/{feedback_id}",
                               json={"status": "resolved", "admin_note": "Behoben in v1.2"},
                               headers=auth_headers(admin_token))
    assert resp.status_code == 200
    assert resp.json()["status"] == "resolved"
    assert resp.json()["admin_note"] == "Behoben in v1.2"


@pytest.mark.asyncio
async def test_employee_cannot_update_feedback(client, employee_token, employee_user, tenant):
    create_resp = await client.post(FEEDBACK_URL, json={"category": "bug", "title": "X", "description": "Y"},
                                     headers=auth_headers(employee_token))
    feedback_id = create_resp.json()["id"]

    resp = await client.patch(f"{FEEDBACK_URL}/{feedback_id}", json={"status": "resolved"},
                               headers=auth_headers(employee_token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_invalid_status_rejected(client, admin_token, employee_token, employee_user, admin_user, tenant):
    create_resp = await client.post(FEEDBACK_URL, json={"category": "bug", "title": "X", "description": "Y"},
                                     headers=auth_headers(employee_token))
    feedback_id = create_resp.json()["id"]

    resp = await client.patch(f"{FEEDBACK_URL}/{feedback_id}", json={"status": "nonsense"},
                               headers=auth_headers(admin_token))
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_nonexistent_feedback_404(client, admin_token, admin_user, tenant):
    resp = await client.patch(f"{FEEDBACK_URL}/{uuid.uuid4()}", json={"status": "resolved"},
                               headers=auth_headers(admin_token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_feedback_scoped_to_own_tenant(client, admin_token, admin_token_b, admin_user, admin_user_b, tenant, tenant_b):
    create_resp = await client.post(FEEDBACK_URL, json={"category": "bug", "title": "Tenant A", "description": "..."},
                                     headers=auth_headers(admin_token))
    feedback_id = create_resp.json()["id"]

    other_list = await client.get(FEEDBACK_URL, headers=auth_headers(admin_token_b))
    assert all(f["id"] != feedback_id for f in other_list.json())

    other_update = await client.patch(f"{FEEDBACK_URL}/{feedback_id}", json={"status": "resolved"},
                                       headers=auth_headers(admin_token_b))
    assert other_update.status_code == 404
