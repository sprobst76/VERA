"""
API tests for /api/v1/holiday-profiles

Tests CRUD operations for HolidayProfile, VacationPeriod, and CustomHoliday.
"""
import pytest

from tests.conftest import auth_headers


BASE = "/api/v1/holiday-profiles"


# ── Create Profile ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_profile_basic(client, admin_token):
    resp = await client.post(BASE, json={"name": "BW 2025/26", "state": "BW"}, headers=auth_headers(admin_token))
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "BW 2025/26"
    assert data["state"] == "BW"
    assert data["is_active"] is False
    assert "id" in data


@pytest.mark.asyncio
async def test_create_profile_with_bw_preset(client, admin_token):
    resp = await client.post(
        BASE,
        json={"name": "BW Preset", "state": "BW", "preset_bw": True},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 201
    data = resp.json()
    # BW preset fills 5 vacation periods
    assert len(data["vacation_periods"]) == 5
    names = [vp["name"] for vp in data["vacation_periods"]]
    assert "Herbstferien" in names
    assert "Sommer" in names


@pytest.mark.asyncio
async def test_create_profile_active_flag(client, admin_token):
    resp = await client.post(
        BASE,
        json={"name": "Aktiv", "state": "BW", "is_active": True},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 201
    assert resp.json()["is_active"] is True


@pytest.mark.asyncio
async def test_only_one_profile_active_at_a_time(client, admin_token):
    """Activating a new profile deactivates the previously active one."""
    r1 = await client.post(BASE, json={"name": "Profil A", "is_active": True}, headers=auth_headers(admin_token))
    assert r1.json()["is_active"] is True
    profile_a_id = r1.json()["id"]

    r2 = await client.post(BASE, json={"name": "Profil B", "is_active": True}, headers=auth_headers(admin_token))
    assert r2.json()["is_active"] is True

    # Profile A should now be inactive
    r_a = await client.get(f"{BASE}/{profile_a_id}", headers=auth_headers(admin_token))
    assert r_a.json()["is_active"] is False


@pytest.mark.asyncio
async def test_create_profile_requires_manager_or_admin(client, employee_token):
    resp = await client.post(BASE, json={"name": "X"}, headers=auth_headers(employee_token))
    assert resp.status_code == 403


# ── List Profiles ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_profiles_empty(client, admin_token):
    resp = await client.get(BASE, headers=auth_headers(admin_token))
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_profiles_returns_created(client, admin_token):
    await client.post(BASE, json={"name": "P1"}, headers=auth_headers(admin_token))
    await client.post(BASE, json={"name": "P2"}, headers=auth_headers(admin_token))
    resp = await client.get(BASE, headers=auth_headers(admin_token))
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_list_profiles_includes_counts(client, admin_token):
    r = await client.post(BASE, json={"name": "P", "preset_bw": True}, headers=auth_headers(admin_token))
    profile_id = r.json()["id"]
    resp = await client.get(BASE, headers=auth_headers(admin_token))
    profile = next(p for p in resp.json() if p["id"] == profile_id)
    assert profile["vacation_period_count"] == 5
    assert profile["custom_holiday_count"] == 0


# ── Get Profile Detail ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_profile_detail(client, admin_token):
    r = await client.post(BASE, json={"name": "Detail Test", "preset_bw": True}, headers=auth_headers(admin_token))
    pid = r.json()["id"]
    resp = await client.get(f"{BASE}/{pid}", headers=auth_headers(admin_token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Detail Test"
    assert len(data["vacation_periods"]) == 5
    assert len(data["custom_holidays"]) == 0


@pytest.mark.asyncio
async def test_get_profile_not_found(client, admin_token):
    import uuid
    resp = await client.get(f"{BASE}/{uuid.uuid4()}", headers=auth_headers(admin_token))
    assert resp.status_code == 404


# ── Update Profile ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_profile_name(client, admin_token):
    r = await client.post(BASE, json={"name": "Alt"}, headers=auth_headers(admin_token))
    pid = r.json()["id"]
    resp = await client.put(f"{BASE}/{pid}", json={"name": "Neu"}, headers=auth_headers(admin_token))
    assert resp.status_code == 200
    assert resp.json()["name"] == "Neu"


# ── Delete Profile ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_profile(client, admin_token):
    r = await client.post(BASE, json={"name": "Del"}, headers=auth_headers(admin_token))
    pid = r.json()["id"]
    resp = await client.delete(f"{BASE}/{pid}", headers=auth_headers(admin_token))
    assert resp.status_code == 204
    # Verify gone
    resp2 = await client.get(f"{BASE}/{pid}", headers=auth_headers(admin_token))
    assert resp2.status_code == 404


# ── Vacation Periods ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_add_vacation_period(client, admin_token):
    r = await client.post(BASE, json={"name": "P"}, headers=auth_headers(admin_token))
    pid = r.json()["id"]
    resp = await client.post(
        f"{BASE}/{pid}/periods",
        json={"name": "Sommerferien", "start_date": "2025-07-31", "end_date": "2025-09-13", "color": "#a6e3a1"},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Sommerferien"
    assert data["start_date"] == "2025-07-31"
    assert data["end_date"] == "2025-09-13"


@pytest.mark.asyncio
async def test_delete_vacation_period(client, admin_token):
    r = await client.post(BASE, json={"name": "P"}, headers=auth_headers(admin_token))
    pid = r.json()["id"]
    rp = await client.post(
        f"{BASE}/{pid}/periods",
        json={"name": "Ferien", "start_date": "2025-07-01", "end_date": "2025-07-31"},
        headers=auth_headers(admin_token),
    )
    vpid = rp.json()["id"]
    resp = await client.delete(f"{BASE}/{pid}/periods/{vpid}", headers=auth_headers(admin_token))
    assert resp.status_code == 204
    # Verify removed from detail
    detail = await client.get(f"{BASE}/{pid}", headers=auth_headers(admin_token))
    assert len(detail.json()["vacation_periods"]) == 0


# ── Custom Holidays ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_add_custom_holiday(client, admin_token):
    r = await client.post(BASE, json={"name": "P"}, headers=auth_headers(admin_token))
    pid = r.json()["id"]
    resp = await client.post(
        f"{BASE}/{pid}/custom-days",
        json={"name": "Konferenztag", "date": "2025-10-03", "color": "#fab387"},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Konferenztag"
    assert data["date"] == "2025-10-03"


@pytest.mark.asyncio
async def test_delete_custom_holiday(client, admin_token):
    r = await client.post(BASE, json={"name": "P"}, headers=auth_headers(admin_token))
    pid = r.json()["id"]
    rc = await client.post(
        f"{BASE}/{pid}/custom-days",
        json={"name": "Konferenztag", "date": "2025-10-03"},
        headers=auth_headers(admin_token),
    )
    chid = rc.json()["id"]
    resp = await client.delete(f"{BASE}/{pid}/custom-days/{chid}", headers=auth_headers(admin_token))
    assert resp.status_code == 204


# ── Isolation: different tenants ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_profile_not_visible_to_other_tenant(client, admin_token, db):
    """Profile created by tenant A is not visible to tenant B."""
    import uuid
    from datetime import datetime, timezone
    from app.models.tenant import Tenant
    from app.models.user import User
    from app.core.security import hash_password, create_access_token

    # Create second tenant + admin
    t2 = Tenant(id=uuid.uuid4(), name="Tenant B", slug=f"tenant-b-{uuid.uuid4().hex[:6]}", is_active=True,
                created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))
    u2 = User(id=uuid.uuid4(), tenant_id=t2.id, email="admin2@test.de",
              hashed_password=hash_password("x"), role="admin", is_active=True,
              created_at=datetime.now(timezone.utc))
    db.add(t2); db.add(u2)
    await db.commit()
    token2 = create_access_token(u2.id, t2.id, "admin")

    # Tenant A creates a profile
    await client.post(BASE, json={"name": "Tenant A Profil"}, headers=auth_headers(admin_token))

    # Tenant B sees no profiles
    resp = await client.get(BASE, headers=auth_headers(token2))
    assert resp.json() == []
