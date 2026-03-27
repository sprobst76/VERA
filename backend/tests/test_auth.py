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


# ── Token version revocation tests ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_token_version_mismatch(client, admin_user, db):
    """Token with stale ver claim is rejected (D-06)."""
    from app.core.security import create_access_token
    # Create token with ver=0
    token = create_access_token(admin_user.id, admin_user.tenant_id, "admin", token_version=0)
    # Increment user token_version in DB
    admin_user.token_version = 1
    await db.commit()
    db.expire_all()
    # Old token should be rejected
    r = await client.get(f"{BASE}/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_logout_all_returns_204(client, admin_token):
    r = await client.post(f"{BASE}/logout-all", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_logout_all_invalidates_tokens(client, admin_user, admin_token, db):
    """After logout-all, old tokens are rejected (D-07)."""
    r = await client.post(f"{BASE}/logout-all", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 204
    db.expire_all()
    # Old token should now fail
    r2 = await client.get(f"{BASE}/me", headers={"Authorization": f"Bearer {admin_token}"})
    assert r2.status_code == 401


@pytest.mark.asyncio
async def test_change_password_revokes_tokens(client, admin_user, admin_token, db):
    """Password change increments token_version, revoking sessions (D-08)."""
    r = await client.post(
        f"{BASE}/change-password",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"current_password": "testpass123", "new_password": "newpass12345"})
    assert r.status_code == 204
    db.expire_all()
    # Old token should now fail
    r2 = await client.get(f"{BASE}/me", headers={"Authorization": f"Bearer {admin_token}"})
    assert r2.status_code == 401


@pytest.mark.asyncio
async def test_missing_ver_claim_treated_as_zero(client, admin_user, db):
    """Pre-deploy tokens without ver claim work if user.token_version is 0."""
    import jwt as pyjwt
    from app.core.config import settings
    from datetime import datetime, timedelta, timezone
    # Manually create a token WITHOUT ver claim (simulates pre-deploy token)
    payload = {
        "sub": str(admin_user.id),
        "tenant_id": str(admin_user.tenant_id),
        "role": "admin",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        "type": "access",
    }
    token = pyjwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
    r = await client.get(f"{BASE}/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
