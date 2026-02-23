"""
API tests for:
  POST /api/v1/recurring-shifts/preview
  POST /api/v1/recurring-shifts
  GET  /api/v1/recurring-shifts
  POST /api/v1/recurring-shifts/{id}/update-from
  DELETE /api/v1/recurring-shifts/{id}
  GET  /api/v1/calendar/vacation-data
"""
import uuid
import pytest
from sqlalchemy import select

from tests.conftest import auth_headers
from app.models.shift import Shift
from app.models.holiday_profile import HolidayProfile, VacationPeriod

RS_BASE = "/api/v1/recurring-shifts"
HP_BASE = "/api/v1/holiday-profiles"


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _create_profile_with_summer(client, token) -> str:
    """Creates a holiday profile with Sommerferien 2025 and returns its ID."""
    r = await client.post(HP_BASE, json={"name": "Test Profil"}, headers=auth_headers(token))
    pid = r.json()["id"]
    await client.post(
        f"{HP_BASE}/{pid}/periods",
        json={"name": "Sommerferien", "start_date": "2025-07-31", "end_date": "2025-09-13"},
        headers=auth_headers(token),
    )
    return pid


def _monday_payload(valid_from="2025-09-01", valid_until="2025-09-30", profile_id=None) -> dict:
    return {
        "weekday": 0,           # Monday
        "start_time": "08:00",
        "end_time": "13:00",
        "break_minutes": 30,
        "valid_from": valid_from,
        "valid_until": valid_until,
        "holiday_profile_id": profile_id,
        "skip_public_holidays": True,
    }


# ── Preview ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_preview_basic(client, admin_token):
    """September 2025 has 5 Mondays."""
    resp = await client.post(RS_BASE + "/preview", json=_monday_payload(), headers=auth_headers(admin_token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["generated_count"] == 5
    assert data["skipped_count"] == 0


@pytest.mark.asyncio
async def test_preview_with_vacation(client, admin_token):
    """Mondays inside vacation are counted as skipped."""
    pid = await _create_profile_with_summer(client, admin_token)
    # Sommerferien: 31.7–13.9 covers first 2 Mondays of September (1.9, 8.9)
    resp = await client.post(
        RS_BASE + "/preview",
        json=_monday_payload(profile_id=pid),
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    # 1.9 and 8.9 are in Sommerferien (ends 13.9) → 2 skipped, 3 generated
    assert data["skipped_count"] == 2
    assert data["generated_count"] == 3


@pytest.mark.asyncio
async def test_preview_requires_auth(client):
    resp = await client.post(RS_BASE + "/preview", json=_monday_payload())
    assert resp.status_code == 403


# ── Create ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_generates_shifts(client, admin_token, db):
    resp = await client.post(RS_BASE, json=_monday_payload(), headers=auth_headers(admin_token))
    assert resp.status_code == 201
    data = resp.json()
    assert data["generated_count"] == 5
    assert data["skipped_count"] == 0
    assert "id" in data["recurring_shift"]

    # Verify individual Shift rows exist in DB
    rs_id = uuid.UUID(data["recurring_shift"]["id"])
    result = await db.execute(select(Shift).where(Shift.recurring_shift_id == rs_id))
    shifts = result.scalars().all()
    assert len(shifts) == 5
    # All shifts are planned, not override
    assert all(s.status == "planned" for s in shifts)
    assert all(s.is_override is False for s in shifts)


@pytest.mark.asyncio
async def test_create_with_profile_skips_vacation(client, admin_token, db):
    pid = await _create_profile_with_summer(client, admin_token)
    resp = await client.post(
        RS_BASE,
        json=_monday_payload(profile_id=pid),
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["skipped_count"] == 2
    assert data["generated_count"] == 3

    rs_id = uuid.UUID(data["recurring_shift"]["id"])
    result = await db.execute(select(Shift).where(Shift.recurring_shift_id == rs_id))
    assert len(result.scalars().all()) == 3


@pytest.mark.asyncio
async def test_create_shift_times_are_correct(client, admin_token, db):
    resp = await client.post(
        RS_BASE,
        json={**_monday_payload(), "start_time": "09:00", "end_time": "14:30", "break_minutes": 45},
        headers=auth_headers(admin_token),
    )
    rs_id = uuid.UUID(resp.json()["recurring_shift"]["id"])
    result = await db.execute(select(Shift).where(Shift.recurring_shift_id == rs_id))
    shift = result.scalars().first()
    assert str(shift.start_time)[:5] == "09:00"
    assert str(shift.end_time)[:5] == "14:30"
    assert shift.break_minutes == 45


@pytest.mark.asyncio
async def test_create_requires_manager_or_admin(client, employee_token):
    resp = await client.post(RS_BASE, json=_monday_payload(), headers=auth_headers(employee_token))
    assert resp.status_code == 403


# ── List ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_recurring_shifts(client, admin_token):
    await client.post(RS_BASE, json=_monday_payload(), headers=auth_headers(admin_token))
    await client.post(RS_BASE, json={**_monday_payload(), "weekday": 2}, headers=auth_headers(admin_token))  # Wed
    resp = await client.get(RS_BASE, headers=auth_headers(admin_token))
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_list_includes_weekday_name(client, admin_token):
    await client.post(RS_BASE, json=_monday_payload(), headers=auth_headers(admin_token))
    resp = await client.get(RS_BASE, headers=auth_headers(admin_token))
    assert resp.json()[0]["weekday_name"] == "Montag"


# ── Update from Date ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_from_preserves_confirmed_shifts(client, admin_token, db):
    """Confirmed shifts are NOT deleted when update-from is called."""
    resp = await client.post(RS_BASE, json=_monday_payload(), headers=auth_headers(admin_token))
    rs_id = resp.json()["recurring_shift"]["id"]

    # Manually confirm the first shift (1.9.2025)
    result = await db.execute(
        select(Shift)
        .where(Shift.recurring_shift_id == uuid.UUID(rs_id))
        .order_by(Shift.date)
    )
    shifts = result.scalars().all()
    first_shift = shifts[0]
    first_shift.status = "confirmed"
    await db.commit()

    # Update from 2.9.2025 – should not touch the confirmed 1.9.2025
    resp2 = await client.post(
        f"{RS_BASE}/{rs_id}/update-from",
        json={"from_date": "2025-09-08", "start_time": "09:00", "end_time": "14:00"},
        headers=auth_headers(admin_token),
    )
    assert resp2.status_code == 200

    # Confirmed shift still exists
    check = await db.execute(
        select(Shift).where(Shift.id == first_shift.id)
    )
    confirmed = check.scalar_one_or_none()
    assert confirmed is not None
    assert confirmed.status == "confirmed"


@pytest.mark.asyncio
async def test_update_from_deletes_future_planned(client, admin_token, db):
    """Planned future shifts are deleted and regenerated by update-from."""
    resp = await client.post(RS_BASE, json=_monday_payload(), headers=auth_headers(admin_token))
    rs_id = resp.json()["recurring_shift"]["id"]

    # Before: 5 planned shifts
    result = await db.execute(
        select(Shift).where(Shift.recurring_shift_id == uuid.UUID(rs_id))
    )
    assert len(result.scalars().all()) == 5

    # Update-from 2nd Monday (8.9), regenerating from there
    resp2 = await client.post(
        f"{RS_BASE}/{rs_id}/update-from",
        json={"from_date": "2025-09-08"},
        headers=auth_headers(admin_token),
    )
    assert resp2.status_code == 200
    # 4 Mondays from 8.9 to 29.9 (8, 15, 22, 29) regenerated
    assert resp2.json()["generated_count"] == 4

    result2 = await db.execute(
        select(Shift).where(Shift.recurring_shift_id == uuid.UUID(rs_id))
    )
    # 1.9 (kept: was before from_date) + 4 new = 5 total
    assert len(result2.scalars().all()) == 5


# ── Delete ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_soft_deletes_and_removes_future_planned(client, admin_token, db):
    resp = await client.post(RS_BASE, json=_monday_payload(), headers=auth_headers(admin_token))
    rs_id = resp.json()["recurring_shift"]["id"]

    del_resp = await client.delete(f"{RS_BASE}/{rs_id}", headers=auth_headers(admin_token))
    assert del_resp.status_code == 204

    # RecurringShift is soft-deleted (is_active=False), not gone from DB
    from app.models.recurring_shift import RecurringShift
    result = await db.execute(
        select(RecurringShift).where(RecurringShift.id == uuid.UUID(rs_id))
    )
    rs = result.scalar_one_or_none()
    assert rs is not None
    assert rs.is_active is False

    # All planned shifts are removed
    shifts_result = await db.execute(
        select(Shift).where(Shift.recurring_shift_id == uuid.UUID(rs_id))
    )
    assert len(shifts_result.scalars().all()) == 0


@pytest.mark.asyncio
async def test_delete_preserves_confirmed_shifts(client, admin_token, db):
    resp = await client.post(RS_BASE, json=_monday_payload(), headers=auth_headers(admin_token))
    rs_id = resp.json()["recurring_shift"]["id"]

    # Confirm the first shift
    result = await db.execute(
        select(Shift).where(Shift.recurring_shift_id == uuid.UUID(rs_id)).order_by(Shift.date)
    )
    first = result.scalars().first()
    first.status = "confirmed"
    await db.commit()

    await client.delete(f"{RS_BASE}/{rs_id}", headers=auth_headers(admin_token))

    # Confirmed shift remains
    check = await db.execute(select(Shift).where(Shift.id == first.id))
    assert check.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_deleted_rs_not_in_list(client, admin_token):
    resp = await client.post(RS_BASE, json=_monday_payload(), headers=auth_headers(admin_token))
    rs_id = resp.json()["recurring_shift"]["id"]
    await client.delete(f"{RS_BASE}/{rs_id}", headers=auth_headers(admin_token))

    list_resp = await client.get(RS_BASE, headers=auth_headers(admin_token))
    ids = [rs["id"] for rs in list_resp.json()]
    assert rs_id not in ids


# ── Calendar vacation-data ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_vacation_data_no_profile(client, admin_token):
    """Without an active profile, endpoint returns empty lists + public holidays."""
    resp = await client.get(
        "/api/v1/calendar/vacation-data",
        params={"from": "2025-09-01", "to": "2025-09-30"},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["vacation_periods"] == []
    assert data["custom_holidays"] == []
    # September has no BW public holidays → empty
    assert data["public_holidays"] == []


@pytest.mark.asyncio
async def test_vacation_data_with_active_profile(client, admin_token):
    """Vacation periods from the active profile are returned."""
    r = await client.post(
        HP_BASE,
        json={"name": "Test", "is_active": True, "preset_bw": True},
        headers=auth_headers(admin_token),
    )
    assert r.status_code == 201

    resp = await client.get(
        "/api/v1/calendar/vacation-data",
        params={"from": "2025-10-01", "to": "2025-11-30"},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    names = [vp["name"] for vp in data["vacation_periods"]]
    assert "Herbstferien" in names


@pytest.mark.asyncio
async def test_vacation_data_includes_public_holidays_in_january(client, admin_token):
    """January 2026 contains Neujahr and Heilige Drei Könige."""
    resp = await client.get(
        "/api/v1/calendar/vacation-data",
        params={"from": "2026-01-01", "to": "2026-01-31"},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    holiday_names = [ph["name"] for ph in resp.json()["public_holidays"]]
    assert "Neujahr" in holiday_names
    assert "Heilige Drei Könige" in holiday_names


@pytest.mark.asyncio
async def test_vacation_data_requires_auth(client):
    resp = await client.get(
        "/api/v1/calendar/vacation-data",
        params={"from": "2025-09-01", "to": "2025-09-30"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_vacation_data_custom_holidays_included(client, admin_token):
    """Custom holidays from active profile appear in response."""
    r = await client.post(HP_BASE, json={"name": "P", "is_active": True}, headers=auth_headers(admin_token))
    pid = r.json()["id"]
    await client.post(
        f"{HP_BASE}/{pid}/custom-days",
        json={"name": "Konferenztag", "date": "2025-10-15"},
        headers=auth_headers(admin_token),
    )
    resp = await client.get(
        "/api/v1/calendar/vacation-data",
        params={"from": "2025-10-01", "to": "2025-10-31"},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    custom = resp.json()["custom_holidays"]
    assert any(ch["name"] == "Konferenztag" for ch in custom)
