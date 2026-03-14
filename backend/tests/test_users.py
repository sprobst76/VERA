"""
Tests für /api/v1/users – Admin-only User-Management (CRUD, RBAC).
"""
import pytest
from tests.conftest import auth_headers

URL = "/api/v1/users"

CREATE_PAYLOAD = {
    "email": "new@test.de",
    "password": "sicher1234",
    "role": "employee",
}


# ── GET /users ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_users_admin(client, admin_token, admin_user, tenant):
    resp = await client.get(URL, headers=auth_headers(admin_token))
    assert resp.status_code == 200
    data = resp.json()
    # Mindestens der Admin selbst
    assert any(u["email"] == "admin@test.de" for u in data)


@pytest.mark.asyncio
async def test_list_users_employee_forbidden(client, employee_token, employee_user, tenant):
    resp = await client.get(URL, headers=auth_headers(employee_token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_users_requires_auth(client):
    resp = await client.get(URL)
    assert resp.status_code in (401, 403)


# ── POST /users ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_user_admin(client, admin_token, admin_user, tenant):
    resp = await client.post(URL, json=CREATE_PAYLOAD, headers=auth_headers(admin_token))
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "new@test.de"
    assert data["role"] == "employee"
    assert data["is_active"] is True
    assert "id" in data
    # Kein Passwort-Hash im Response
    assert "password" not in data
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_create_user_employee_forbidden(client, employee_token, employee_user, tenant):
    resp = await client.post(URL, json=CREATE_PAYLOAD, headers=auth_headers(employee_token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_user_duplicate_email(client, admin_token, admin_user, tenant):
    await client.post(URL, json=CREATE_PAYLOAD, headers=auth_headers(admin_token))
    resp = await client.post(URL, json=CREATE_PAYLOAD, headers=auth_headers(admin_token))
    assert resp.status_code in (400, 409)


@pytest.mark.asyncio
async def test_create_user_manager_role(client, admin_token, admin_user, tenant):
    payload = {**CREATE_PAYLOAD, "email": "mgr@test.de", "role": "manager"}
    resp = await client.post(URL, json=payload, headers=auth_headers(admin_token))
    assert resp.status_code == 201
    assert resp.json()["role"] == "manager"


@pytest.mark.asyncio
async def test_create_user_missing_email(client, admin_token, admin_user, tenant):
    resp = await client.post(URL, json={"password": "abc123"},
                             headers=auth_headers(admin_token))
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_user_appears_in_list(client, admin_token, admin_user, tenant):
    await client.post(URL, json=CREATE_PAYLOAD, headers=auth_headers(admin_token))
    resp = await client.get(URL, headers=auth_headers(admin_token))
    emails = [u["email"] for u in resp.json()]
    assert "new@test.de" in emails


# ── PUT /users/{id} ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_user_role(client, admin_token, admin_user, tenant):
    create_resp = await client.post(URL, json=CREATE_PAYLOAD, headers=auth_headers(admin_token))
    user_id = create_resp.json()["id"]

    resp = await client.put(f"{URL}/{user_id}", json={"role": "manager"},
                            headers=auth_headers(admin_token))
    assert resp.status_code == 200
    assert resp.json()["role"] == "manager"


@pytest.mark.asyncio
async def test_deactivate_user(client, admin_token, admin_user, tenant):
    create_resp = await client.post(URL, json=CREATE_PAYLOAD, headers=auth_headers(admin_token))
    user_id = create_resp.json()["id"]

    resp = await client.put(f"{URL}/{user_id}", json={"is_active": False},
                            headers=auth_headers(admin_token))
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_update_user_password(client, admin_token, admin_user, tenant):
    """Passwort-Reset durch Admin – kein 422."""
    create_resp = await client.post(URL, json=CREATE_PAYLOAD, headers=auth_headers(admin_token))
    user_id = create_resp.json()["id"]

    resp = await client.put(f"{URL}/{user_id}", json={"password": "neuesPasswort99"},
                            headers=auth_headers(admin_token))
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_update_user_employee_forbidden(client, admin_token, employee_token,
                                              admin_user, employee_user, tenant):
    create_resp = await client.post(URL, json=CREATE_PAYLOAD, headers=auth_headers(admin_token))
    user_id = create_resp.json()["id"]

    resp = await client.put(f"{URL}/{user_id}", json={"role": "admin"},
                            headers=auth_headers(employee_token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_user_not_found(client, admin_token, admin_user, tenant):
    import uuid
    resp = await client.put(f"{URL}/{uuid.uuid4()}", json={"role": "employee"},
                            headers=auth_headers(admin_token))
    assert resp.status_code == 404


# ── Tenant-Isolation ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_users_only_own_tenant(client, admin_token, admin_user, tenant, db):
    """Admin sieht nur User des eigenen Mandanten."""
    import uuid
    from datetime import datetime, timezone
    from app.models.tenant import Tenant
    from app.models.user import User
    from app.core.security import hash_password, create_access_token

    # Zweiter Tenant + User
    other_tenant = Tenant(id=uuid.uuid4(), name="Other", slug=f"other-{uuid.uuid4().hex[:6]}",
                          state="BW", is_active=True,
                          created_at=datetime.now(timezone.utc),
                          updated_at=datetime.now(timezone.utc))
    db.add(other_tenant)
    await db.commit()

    other_user = User(id=uuid.uuid4(), tenant_id=other_tenant.id,
                      email="other@other.de",
                      hashed_password=hash_password("x"),
                      role="admin", is_active=True,
                      created_at=datetime.now(timezone.utc))
    db.add(other_user)
    await db.commit()

    resp = await client.get(URL, headers=auth_headers(admin_token))
    emails = [u["email"] for u in resp.json()]
    assert "other@other.de" not in emails
