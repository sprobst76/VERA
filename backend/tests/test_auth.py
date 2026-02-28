"""
Tests für /api/v1/auth – Login, Refresh, /me, Change-Password.
"""
import pytest
from tests.conftest import auth_headers


BASE = "/api/v1/auth"


# ── Login ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_login_valid(client, admin_user):
    resp = await client.post(f"{BASE}/login", json={
        "email": "admin@test.de",
        "password": "testpass123",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["access_token"]
    assert data["refresh_token"]


@pytest.mark.asyncio
async def test_login_wrong_password(client, admin_user):
    resp = await client.post(f"{BASE}/login", json={
        "email": "admin@test.de",
        "password": "wrongpassword",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_email(client, tenant):
    resp = await client.post(f"{BASE}/login", json={
        "email": "nobody@test.de",
        "password": "testpass123",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_inactive_user(client, db, admin_user):
    admin_user.is_active = False
    await db.commit()

    resp = await client.post(f"{BASE}/login", json={
        "email": "admin@test.de",
        "password": "testpass123",
    })
    assert resp.status_code == 400


# ── Refresh ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_refresh_valid(client, admin_user):
    # Erst einloggen und refresh_token holen
    login = await client.post(f"{BASE}/login", json={
        "email": "admin@test.de",
        "password": "testpass123",
    })
    refresh_token = login.json()["refresh_token"]

    resp = await client.post(f"{BASE}/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_refresh_invalid_token(client, tenant):
    resp = await client.post(f"{BASE}/refresh", json={"refresh_token": "invalid.token.here"})
    assert resp.status_code == 401


# ── /me ───────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_me_returns_user_info(client, admin_user, admin_token):
    resp = await client.get(f"{BASE}/me", headers=auth_headers(admin_token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "admin@test.de"
    assert data["role"] == "admin"
    assert "id" in data
    assert "tenant_id" in data


@pytest.mark.asyncio
async def test_me_without_token(client, tenant):
    resp = await client.get(f"{BASE}/me")
    assert resp.status_code in (401, 403)  # FastAPI liefert 403 bei fehlendem Token


# ── Change-Password ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_change_password_success(client, admin_user, admin_token):
    resp = await client.post(
        f"{BASE}/change-password",
        json={"current_password": "testpass123", "new_password": "newpass456"},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 204

    # Altes Passwort funktioniert nicht mehr
    login_old = await client.post(f"{BASE}/login", json={
        "email": "admin@test.de", "password": "testpass123",
    })
    assert login_old.status_code == 401

    # Neues Passwort funktioniert
    login_new = await client.post(f"{BASE}/login", json={
        "email": "admin@test.de", "password": "newpass456",
    })
    assert login_new.status_code == 200


@pytest.mark.asyncio
async def test_change_password_wrong_current(client, admin_user, admin_token):
    resp = await client.post(
        f"{BASE}/change-password",
        json={"current_password": "wrongpass", "new_password": "newpass456"},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_change_password_too_short(client, admin_user, admin_token):
    resp = await client.post(
        f"{BASE}/change-password",
        json={"current_password": "testpass123", "new_password": "short"},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 422
