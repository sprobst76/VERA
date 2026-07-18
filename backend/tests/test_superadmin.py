"""
Tests für /api/v1/superadmin – Login (+2FA), Tenant-Verwaltung, SuperAdmin-
Verwaltung, und die Isolation gegenüber normalen Tenant-Tokens.
"""
import uuid
from datetime import datetime, timezone

import pyotp
import pytest
import pytest_asyncio

from app.core.security import hash_password, create_superadmin_token, create_superadmin_challenge_token
from app.models.superadmin import SuperAdmin
from tests.conftest import auth_headers

SUPERADMIN_URL = "/api/v1/superadmin"


@pytest_asyncio.fixture
async def superadmin(db) -> SuperAdmin:
    sa = SuperAdmin(
        email="root@vera-ops.de",
        hashed_password=hash_password("rootpass123"),
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db.add(sa)
    await db.commit()
    await db.refresh(sa)
    return sa


@pytest_asyncio.fixture
def superadmin_token(superadmin) -> str:
    return create_superadmin_token(superadmin.id)


@pytest_asyncio.fixture
async def superadmin_with_2fa(db) -> tuple[SuperAdmin, str]:
    """SuperAdmin mit aktivierter 2FA + das TOTP-Secret zum Codes-Generieren."""
    secret = pyotp.random_base32()
    sa = SuperAdmin(
        email="2fa@vera-ops.de",
        hashed_password=hash_password("rootpass123"),
        is_active=True,
        totp_secret=secret,
        totp_enabled=True,
        created_at=datetime.now(timezone.utc),
    )
    db.add(sa)
    await db.commit()
    await db.refresh(sa)
    return sa, secret


# ── POST /superadmin/login ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_login_success_without_2fa(client, superadmin):
    resp = await client.post(f"{SUPERADMIN_URL}/login", json={"email": "root@vera-ops.de", "password": "rootpass123"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["access_token"] is not None
    assert data["requires_2fa"] is False


@pytest.mark.asyncio
async def test_login_wrong_password(client, superadmin):
    resp = await client.post(f"{SUPERADMIN_URL}/login", json={"email": "root@vera-ops.de", "password": "wrong"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_email(client, db):
    resp = await client.post(f"{SUPERADMIN_URL}/login", json={"email": "nope@vera-ops.de", "password": "whatever1"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_inactive_account_forbidden(client, db):
    sa = SuperAdmin(email="inactive@vera-ops.de", hashed_password=hash_password("rootpass123"), is_active=False)
    db.add(sa)
    await db.commit()

    resp = await client.post(f"{SUPERADMIN_URL}/login", json={"email": "inactive@vera-ops.de", "password": "rootpass123"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_login_with_2fa_returns_challenge(client, superadmin_with_2fa):
    sa, _secret = superadmin_with_2fa
    resp = await client.post(f"{SUPERADMIN_URL}/login", json={"email": sa.email, "password": "rootpass123"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["requires_2fa"] is True
    assert data["challenge_token"] is not None
    assert data["access_token"] is None


# ── POST /superadmin/login/verify-2fa ────────────────────────────────────────

@pytest.mark.asyncio
async def test_verify_2fa_success(client, superadmin_with_2fa):
    sa, secret = superadmin_with_2fa
    challenge = create_superadmin_challenge_token(sa.id)
    code = pyotp.TOTP(secret).now()

    resp = await client.post(f"{SUPERADMIN_URL}/login/verify-2fa", json={"challenge_token": challenge, "totp_code": code})
    assert resp.status_code == 200
    assert resp.json()["access_token"] is not None


@pytest.mark.asyncio
async def test_verify_2fa_wrong_code(client, superadmin_with_2fa):
    sa, _secret = superadmin_with_2fa
    challenge = create_superadmin_challenge_token(sa.id)

    resp = await client.post(f"{SUPERADMIN_URL}/login/verify-2fa", json={"challenge_token": challenge, "totp_code": "000000"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_verify_2fa_rejects_full_access_token(client, superadmin_with_2fa):
    """Ein bereits vollwertiges Access-Token darf nicht als Challenge-Token durchgehen."""
    sa, secret = superadmin_with_2fa
    full_token = create_superadmin_token(sa.id)
    code = pyotp.TOTP(secret).now()

    resp = await client.post(f"{SUPERADMIN_URL}/login/verify-2fa", json={"challenge_token": full_token, "totp_code": code})
    assert resp.status_code == 401


# ── GET /superadmin/me + Isolation gegenüber Tenant-Tokens ───────────────────

@pytest.mark.asyncio
async def test_me_with_superadmin_token(client, superadmin, superadmin_token):
    resp = await client.get(f"{SUPERADMIN_URL}/me", headers=auth_headers(superadmin_token))
    assert resp.status_code == 200
    assert resp.json()["email"] == "root@vera-ops.de"


@pytest.mark.asyncio
async def test_tenant_admin_token_rejected_on_superadmin_routes(client, admin_token, admin_user, tenant):
    """Ein normaler Tenant-Admin-Token darf keinen Zugriff auf /superadmin/* haben."""
    resp = await client.get(f"{SUPERADMIN_URL}/me", headers=auth_headers(admin_token))
    assert resp.status_code in (401, 403)

    resp2 = await client.get(f"{SUPERADMIN_URL}/tenants", headers=auth_headers(admin_token))
    assert resp2.status_code in (401, 403)


@pytest.mark.asyncio
async def test_superadmin_token_rejected_on_tenant_routes(client, superadmin_token):
    """Umgekehrt: ein SuperAdmin-Token ist kein gültiger Tenant-User-Token."""
    resp = await client.get("/api/v1/employees/me", headers=auth_headers(superadmin_token))
    assert resp.status_code in (401, 403, 404)


@pytest.mark.asyncio
async def test_me_without_token_unauthorized(client):
    resp = await client.get(f"{SUPERADMIN_URL}/me")
    assert resp.status_code in (401, 403)


# ── 2FA-Verwaltung (authentifiziert) ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_2fa_setup_and_confirm_flow(client, superadmin, superadmin_token, db):
    setup_resp = await client.post(f"{SUPERADMIN_URL}/2fa/setup", headers=auth_headers(superadmin_token))
    assert setup_resp.status_code == 200
    setup_data = setup_resp.json()
    assert setup_data["secret"]
    assert setup_data["totp_uri"].startswith("otpauth://")
    assert "<svg" in setup_data["qr_svg"]

    code = pyotp.TOTP(setup_data["secret"]).now()
    confirm_resp = await client.post(f"{SUPERADMIN_URL}/2fa/confirm",
                                      json={"totp_code": code}, headers=auth_headers(superadmin_token))
    assert confirm_resp.status_code == 200

    superadmin_email = superadmin.email
    db.expire_all()
    login_resp = await client.post(f"{SUPERADMIN_URL}/login", json={"email": superadmin_email, "password": "rootpass123"})
    assert login_resp.json()["requires_2fa"] is True


@pytest.mark.asyncio
async def test_2fa_confirm_without_setup_fails(client, superadmin_token):
    resp = await client.post(f"{SUPERADMIN_URL}/2fa/confirm",
                              json={"totp_code": "123456"}, headers=auth_headers(superadmin_token))
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_2fa_confirm_wrong_code_fails(client, superadmin_token):
    setup_resp = await client.post(f"{SUPERADMIN_URL}/2fa/setup", headers=auth_headers(superadmin_token))
    resp = await client.post(f"{SUPERADMIN_URL}/2fa/confirm",
                              json={"totp_code": "000000"}, headers=auth_headers(superadmin_token))
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_disable_2fa_wrong_password_fails(client, superadmin_with_2fa):
    sa, secret = superadmin_with_2fa
    token = create_superadmin_token(sa.id)
    code = pyotp.TOTP(secret).now()

    resp = await client.request("DELETE", f"{SUPERADMIN_URL}/2fa",
                                 json={"password": "wrongpass", "totp_code": code}, headers=auth_headers(token))
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_disable_2fa_success(client, superadmin_with_2fa):
    sa, secret = superadmin_with_2fa
    token = create_superadmin_token(sa.id)
    code = pyotp.TOTP(secret).now()

    resp = await client.request("DELETE", f"{SUPERADMIN_URL}/2fa",
                                 json={"password": "rootpass123", "totp_code": code}, headers=auth_headers(token))
    assert resp.status_code == 200


# ── Tenant-Verwaltung ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_tenant(client, superadmin_token):
    resp = await client.post(f"{SUPERADMIN_URL}/tenants", json={
        "name": "Neuer Betrieb", "slug": "neuer-betrieb",
        "admin_email": "chef@neuer-betrieb.de", "admin_password": "supersafe1",
    }, headers=auth_headers(superadmin_token))
    assert resp.status_code == 201
    data = resp.json()
    assert data["slug"] == "neuer-betrieb"
    assert data["user_count"] == 1
    assert data["employee_count"] == 0


@pytest.mark.asyncio
async def test_create_tenant_duplicate_slug_rejected(client, superadmin_token, tenant):
    resp = await client.post(f"{SUPERADMIN_URL}/tenants", json={
        "name": "Dup", "slug": tenant.slug,
        "admin_email": "someone@example.de", "admin_password": "supersafe1",
    }, headers=auth_headers(superadmin_token))
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_create_tenant_duplicate_admin_email_rejected(client, superadmin_token, admin_user):
    resp = await client.post(f"{SUPERADMIN_URL}/tenants", json={
        "name": "Dup Email", "slug": "dup-email-tenant",
        "admin_email": admin_user.email, "admin_password": "supersafe1",
    }, headers=auth_headers(superadmin_token))
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_create_tenant_invalid_slug_rejected(client, superadmin_token):
    resp = await client.post(f"{SUPERADMIN_URL}/tenants", json={
        "name": "Invalid Slug", "slug": "Invalid Slug!",
        "admin_email": "x@example.de", "admin_password": "supersafe1",
    }, headers=auth_headers(superadmin_token))
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_tenants_includes_counts(client, superadmin_token, tenant, admin_user):
    resp = await client.get(f"{SUPERADMIN_URL}/tenants", headers=auth_headers(superadmin_token))
    assert resp.status_code == 200
    entry = next(t for t in resp.json() if t["id"] == str(tenant.id))
    assert entry["user_count"] >= 1


@pytest.mark.asyncio
async def test_deactivate_tenant_cascades_to_users(client, superadmin_token, tenant, admin_user, db):
    resp = await client.patch(f"{SUPERADMIN_URL}/tenants/{tenant.id}",
                               json={"is_active": False}, headers=auth_headers(superadmin_token))
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False

    admin_user_id = admin_user.id
    db.expire_all()
    from sqlalchemy import select
    from app.models.user import User
    result = await db.execute(select(User).where(User.id == admin_user_id))
    assert result.scalar_one().is_active is False


@pytest.mark.asyncio
async def test_update_tenant_not_found(client, superadmin_token):
    resp = await client.patch(f"{SUPERADMIN_URL}/tenants/{uuid.uuid4()}",
                               json={"name": "X"}, headers=auth_headers(superadmin_token))
    assert resp.status_code == 404


# ── SuperAdmin-Verwaltung ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_and_list_superadmins(client, superadmin_token):
    resp = await client.post(f"{SUPERADMIN_URL}/admins",
                              json={"email": "second-root@vera-ops.de", "password": "supersafe1"},
                              headers=auth_headers(superadmin_token))
    assert resp.status_code == 201

    list_resp = await client.get(f"{SUPERADMIN_URL}/admins", headers=auth_headers(superadmin_token))
    emails = [a["email"] for a in list_resp.json()]
    assert "second-root@vera-ops.de" in emails


@pytest.mark.asyncio
async def test_create_superadmin_duplicate_email_rejected(client, superadmin_token, superadmin):
    resp = await client.post(f"{SUPERADMIN_URL}/admins",
                              json={"email": superadmin.email, "password": "supersafe1"},
                              headers=auth_headers(superadmin_token))
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_create_superadmin_short_password_rejected(client, superadmin_token):
    resp = await client.post(f"{SUPERADMIN_URL}/admins",
                              json={"email": "shortpw@vera-ops.de", "password": "short"},
                              headers=auth_headers(superadmin_token))
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_cannot_deactivate_own_account(client, superadmin, superadmin_token):
    resp = await client.patch(f"{SUPERADMIN_URL}/admins/{superadmin.id}",
                               json={"is_active": False}, headers=auth_headers(superadmin_token))
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_can_deactivate_other_admin(client, superadmin_token, db):
    other = SuperAdmin(email="other-root@vera-ops.de", hashed_password=hash_password("rootpass123"), is_active=True)
    db.add(other)
    await db.commit()
    await db.refresh(other)

    resp = await client.patch(f"{SUPERADMIN_URL}/admins/{other.id}",
                               json={"is_active": False}, headers=auth_headers(superadmin_token))
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False
