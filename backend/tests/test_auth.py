"""
Tests für /api/v1/auth – Login, Refresh, /me, Change-Password.
"""
import hashlib
import pytest
import pytest_asyncio
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


# ── API key scope enforcement tests ──────────────────────────────────────────

@pytest_asyncio.fixture
async def make_api_key(db, tenant):
    """Factory fixture: creates an ApiKey with given scopes."""
    from app.models.audit import ApiKey
    from sqlalchemy import delete

    async def _make(scopes=None, raw_key="test-api-key-12345"):
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        # Remove existing key with same hash if any
        await db.execute(delete(ApiKey).where(ApiKey.key_hash == key_hash))
        ak = ApiKey(
            tenant_id=tenant.id,
            name="test-key",
            key_hash=key_hash,
            scopes=scopes,
            is_active=True,
        )
        db.add(ak)
        await db.commit()
        return raw_key

    return _make


@pytest.mark.asyncio
async def test_api_key_read_scope_blocks_write(client, admin_user, make_api_key):
    """Read-only API key cannot POST (D-10)."""
    raw_key = await make_api_key(scopes=["read"])
    r = await client.post("/api/v1/shifts", headers={"X-API-Key": raw_key}, json={})
    assert r.status_code == 403
    assert "Schreibberechtigung" in r.json()["detail"]


@pytest.mark.asyncio
async def test_api_key_write_scope_allows_post(client, admin_user, make_api_key):
    """Write-scoped API key can POST (D-11)."""
    raw_key = await make_api_key(scopes=["write"])
    r = await client.post("/api/v1/shifts", headers={"X-API-Key": raw_key}, json={})
    # Should not be 403 (may be 422 for missing fields)
    assert r.status_code != 403


@pytest.mark.asyncio
async def test_api_key_admin_scope_allows_all(client, admin_user, make_api_key):
    """Admin-scoped API key can POST (D-12)."""
    raw_key = await make_api_key(scopes=["admin"])
    r = await client.post("/api/v1/shifts", headers={"X-API-Key": raw_key}, json={})
    assert r.status_code != 403


@pytest.mark.asyncio
async def test_api_key_null_scopes_treated_as_admin(client, admin_user, make_api_key):
    """Null/empty scopes treated as admin for backward compat (D-14)."""
    raw_key = await make_api_key(scopes=None)
    r = await client.post("/api/v1/shifts", headers={"X-API-Key": raw_key}, json={})
    assert r.status_code != 403


@pytest.mark.asyncio
async def test_api_key_read_scope_allows_get(client, admin_user, make_api_key):
    """Read-only API key can GET (D-10)."""
    raw_key = await make_api_key(scopes=["read"])
    r = await client.get("/api/v1/shifts", headers={"X-API-Key": raw_key})
    assert r.status_code == 200
