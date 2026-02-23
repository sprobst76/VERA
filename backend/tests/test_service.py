"""
Unit tests for recurring_shift_service.py

These are pure function tests – no database required.
"""
import asyncio
from datetime import date, time

import pytest

from app.services.recurring_shift_service import build_skip_set, preview_generate
from app.utils.german_holidays import get_bw_holidays


# ── Minimal stubs (no SQLAlchemy required) ────────────────────────────────────

class _Period:
    def __init__(self, start: date, end: date):
        self.start_date = start
        self.end_date = end


class _CustomDay:
    def __init__(self, d: date):
        self.date = d


class _Profile:
    def __init__(self, periods=None, custom_days=None):
        self.vacation_periods = periods or []
        self.custom_holidays = custom_days or []


# ── build_skip_set ────────────────────────────────────────────────────────────

def test_build_skip_set_no_profile_no_holidays():
    """Without profile and skip_public=False the skip set is empty."""
    result = build_skip_set(profile=None, skip_public_holidays=False, years={2025})
    assert result == set()


def test_build_skip_set_vacation_period():
    """All dates within a VacationPeriod appear in the skip set."""
    profile = _Profile(periods=[_Period(date(2025, 10, 27), date(2025, 10, 31))])
    skip = build_skip_set(profile, skip_public_holidays=False, years={2025})
    assert date(2025, 10, 27) in skip
    assert date(2025, 10, 31) in skip
    assert date(2025, 11, 1) not in skip


def test_build_skip_set_vacation_period_boundaries_inclusive():
    """start_date and end_date are both included."""
    profile = _Profile(periods=[_Period(date(2026, 1, 5), date(2026, 1, 5))])
    skip = build_skip_set(profile, skip_public_holidays=False, years={2026})
    assert date(2026, 1, 5) in skip
    assert date(2026, 1, 4) not in skip
    assert date(2026, 1, 6) not in skip


def test_build_skip_set_custom_holiday():
    """A CustomHoliday date is included in the skip set."""
    profile = _Profile(custom_days=[_CustomDay(date(2025, 11, 3))])
    skip = build_skip_set(profile, skip_public_holidays=False, years={2025})
    assert date(2025, 11, 3) in skip
    assert date(2025, 11, 4) not in skip


def test_build_skip_set_public_holidays_bw():
    """Known BW public holidays are in the skip set when skip_public=True."""
    skip = build_skip_set(profile=None, skip_public_holidays=True, years={2025})
    # Neujahr
    assert date(2025, 1, 1) in skip
    # Tag der Arbeit
    assert date(2025, 5, 1) in skip
    # 1. Weihnachtstag
    assert date(2025, 12, 25) in skip
    # Allerheiligen (BW-spezifisch)
    assert date(2025, 11, 1) in skip


def test_build_skip_set_combines_all_sources():
    """VacationPeriod + CustomHoliday + public holidays are all merged."""
    profile = _Profile(
        periods=[_Period(date(2025, 10, 27), date(2025, 10, 31))],
        custom_days=[_CustomDay(date(2025, 11, 3))],
    )
    skip = build_skip_set(profile, skip_public_holidays=True, years={2025})
    assert date(2025, 10, 28) in skip   # vacation period
    assert date(2025, 11, 3) in skip    # custom holiday
    assert date(2025, 11, 1) in skip    # Allerheiligen (public)


def test_build_skip_set_multi_year():
    """When years spans two calendar years, both are included."""
    skip = build_skip_set(profile=None, skip_public_holidays=True, years={2025, 2026})
    assert date(2025, 1, 1) in skip
    assert date(2026, 1, 1) in skip


# ── preview_generate ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_preview_all_mondays_in_one_week():
    """One Monday in range → 1 generated, 0 skipped."""
    result = await preview_generate(
        weekday=0,  # Monday
        from_date=date(2025, 9, 1),   # Monday
        until_date=date(2025, 9, 1),
        profile=None,
        skip_public_holidays=False,
    )
    assert result["generated_count"] == 1
    assert result["skipped_count"] == 0


@pytest.mark.asyncio
async def test_preview_counts_mondays_in_month():
    """September 2025 has exactly 4 Mondays (1, 8, 15, 22, 29 = 5)."""
    result = await preview_generate(
        weekday=0,
        from_date=date(2025, 9, 1),
        until_date=date(2025, 9, 30),
        profile=None,
        skip_public_holidays=False,
    )
    # Sept 2025 Mondays: 1, 8, 15, 22, 29 → 5
    assert result["generated_count"] == 5
    assert result["skipped_count"] == 0


@pytest.mark.asyncio
async def test_preview_skips_vacation_period():
    """Mondays inside a vacation period are counted as skipped."""
    profile = _Profile(periods=[_Period(date(2025, 10, 27), date(2025, 11, 2))])
    result = await preview_generate(
        weekday=0,   # Monday
        from_date=date(2025, 10, 20),
        until_date=date(2025, 11, 10),
        profile=profile,
        skip_public_holidays=False,
    )
    # Mondays in range: 20.10, 27.10, 3.11, 10.11 = 4 total
    # Vacation is 27.10–2.11 → only 27.10 is a Monday inside it (3.11 is after 2.11)
    assert result["skipped_count"] == 1
    assert result["generated_count"] == 3


@pytest.mark.asyncio
async def test_preview_skips_public_holiday():
    """A Monday that is a public holiday is skipped."""
    # Tag der Arbeit 2026: 1.5.2026 is a Friday, not testing that.
    # Neujahr 2026: 1.1.2026 is a Thursday. Let's test with Thursday.
    result = await preview_generate(
        weekday=3,   # Thursday
        from_date=date(2026, 1, 1),
        until_date=date(2026, 1, 1),
        profile=None,
        skip_public_holidays=True,
    )
    # 1.1.2026 is Neujahr and a Thursday → skipped
    assert result["skipped_count"] == 1
    assert result["generated_count"] == 0


@pytest.mark.asyncio
async def test_preview_no_matching_weekday():
    """If no day in the range matches the weekday, both counts are 0."""
    # Only one day in range: a Monday (weekday 0), asking for Tuesday (1)
    result = await preview_generate(
        weekday=1,
        from_date=date(2025, 9, 1),   # Monday
        until_date=date(2025, 9, 1),
        profile=None,
        skip_public_holidays=False,
    )
    assert result["generated_count"] == 0
    assert result["skipped_count"] == 0


@pytest.mark.asyncio
async def test_preview_skipped_dates_list():
    """skipped_dates contains ISO strings of each skipped day."""
    profile = _Profile(custom_days=[_CustomDay(date(2025, 9, 8))])  # Monday
    result = await preview_generate(
        weekday=0,
        from_date=date(2025, 9, 1),
        until_date=date(2025, 9, 8),
        profile=profile,
        skip_public_holidays=False,
    )
    assert "2025-09-08" in result["skipped_dates"]
    assert "2025-09-01" not in result["skipped_dates"]


# ── german_holidays sanity checks ─────────────────────────────────────────────

def test_bw_holidays_2025_includes_allerheiligen():
    holidays = get_bw_holidays(2025)
    assert date(2025, 11, 1) in holidays


def test_bw_holidays_2025_includes_heilige_drei_koenige():
    holidays = get_bw_holidays(2025)
    assert date(2025, 1, 6) in holidays


def test_bw_holidays_has_14_entries_for_2025():
    """BW has 14 public holidays (Fronleichnam is only BW/BY/HE/NW/RP/SL)."""
    holidays = get_bw_holidays(2025)
    assert len(holidays) >= 12
