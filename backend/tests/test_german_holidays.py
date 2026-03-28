"""
Tests for BW school holiday detection (german_holidays.py).

BW 2026/27 holiday dates sourced from:
https://km-bw.de/de/service/ferien (BW Kultusministerium)
Verified on 2026-03-28. If these tests fail after a schedule correction,
update both german_holidays.py and this file with the corrected official dates.
"""
from datetime import date

import pytest

from app.utils.german_holidays import is_school_holiday


# ── 2025/26 school year ───────────────────────────────────────────────────────

def test_2025_26_osterferien_still_works():
    """Existing 2025/26 Osterferien: 30.03.2026 – 11.04.2026."""
    result, name = is_school_holiday(date(2026, 4, 5))
    assert result is True
    assert name == "Ostern"


def test_2025_26_sommerferien_start():
    """2025/26 Sommerferien begin 30.07.2026."""
    result, name = is_school_holiday(date(2026, 8, 1))
    assert result is True
    assert name == "Sommer"


# ── Gap between school years ──────────────────────────────────────────────────

def test_between_school_years_no_holiday():
    """20.09.2026 is between Sommerferien end (12.09.2026) and Herbstferien start (26.10.2026)."""
    result, name = is_school_holiday(date(2026, 9, 20))
    assert result is False
    assert name is None


# ── 2026/27 school year ───────────────────────────────────────────────────────
# Source: BW Kultusministerium https://km-bw.de/de/service/ferien
# Herbstferien 2026:         26.10.2026 – 30.10.2026
# Weihnachtsferien 2026/27:  23.12.2026 – 09.01.2027
# Osterferien 2027:          30.03.2027 – 03.04.2027
# Pfingstferien 2027:        18.05.2027 – 29.05.2027
# Sommerferien 2027:         29.07.2027 – 11.09.2027

def test_2026_27_herbstferien():
    """Herbstferien 2026: 26.10.2026 – 30.10.2026."""
    result, name = is_school_holiday(date(2026, 10, 29))
    assert result is True
    assert name == "Herbstferien"


def test_2026_27_herbstferien_first_day():
    result, name = is_school_holiday(date(2026, 10, 26))
    assert result is True
    assert name == "Herbstferien"


def test_2026_27_herbstferien_last_day():
    result, name = is_school_holiday(date(2026, 10, 30))
    assert result is True
    assert name == "Herbstferien"


def test_2026_27_weihnachten():
    """Weihnachtsferien 2026/27: 23.12.2026 – 09.01.2027."""
    result, name = is_school_holiday(date(2026, 12, 24))
    assert result is True
    assert name == "Weihnachten"


def test_2026_27_weihnachten_spans_new_year():
    """Weihnachtsferien extends into January 2027."""
    result, name = is_school_holiday(date(2027, 1, 5))
    assert result is True
    assert name == "Weihnachten"


def test_2026_27_osterferien():
    """Osterferien 2027: 30.03.2027 – 03.04.2027."""
    result, name = is_school_holiday(date(2027, 4, 2))
    assert result is True
    assert name == "Ostern"


def test_2026_27_osterferien_first_day():
    result, name = is_school_holiday(date(2027, 3, 30))
    assert result is True
    assert name == "Ostern"


def test_2026_27_pfingstferien():
    """Pfingstferien 2027: 18.05.2027 – 29.05.2027."""
    result, name = is_school_holiday(date(2027, 5, 25))
    assert result is True
    assert name == "Pfingsten"


def test_2026_27_sommerferien():
    """Sommerferien 2027: 29.07.2027 – 11.09.2027."""
    result, name = is_school_holiday(date(2027, 8, 15))
    assert result is True
    assert name == "Sommer"


def test_day_before_herbstferien_2026_is_not_holiday():
    """25.10.2026 is before Herbstferien 2026 (start: 26.10.2026)."""
    result, name = is_school_holiday(date(2026, 10, 25))
    assert result is False
    assert name is None


def test_day_after_weihnachten_2026_27_is_not_holiday():
    """10.01.2027 is after Weihnachtsferien 2026/27 (end: 09.01.2027)."""
    result, name = is_school_holiday(date(2027, 1, 10))
    assert result is False
    assert name is None
