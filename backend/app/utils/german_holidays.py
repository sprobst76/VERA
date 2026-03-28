"""
Deutsche Feiertage für Baden-Württemberg.
Verwendet workalendar für gesetzliche Feiertage + vorbelegte Schulferien BW.
"""
from datetime import date
from typing import NamedTuple


class HolidayInfo(NamedTuple):
    date: date
    name: str
    is_school_holiday: bool = False


# BW Schulferien 2025/26 (aus Spec)
BW_SCHOOL_HOLIDAYS_2025_26: list[tuple[date, date, str]] = [
    (date(2025, 10, 27), date(2025, 10, 31), "Herbstferien"),   # Mo–Fr
    (date(2025, 12, 22), date(2026, 1, 5),   "Weihnachten"),
    (date(2026, 3, 30),  date(2026, 4, 11),  "Ostern"),
    (date(2026, 5, 26),  date(2026, 6, 6),   "Pfingsten"),      # inkl. Pfingstmontag
    (date(2026, 7, 30),  date(2026, 9, 12),  "Sommer"),
]

# BW Schulferien 2026/27
# Source: BW Kultusministerium Ferienplan 2026/27
# https://km-bw.de/de/service/ferien
# Verified by executor on 2026-03-28
BW_SCHOOL_HOLIDAYS_2026_27: list[tuple[date, date, str]] = [
    (date(2026, 10, 26), date(2026, 10, 30), "Herbstferien"),
    (date(2026, 12, 23), date(2027, 1, 9),   "Weihnachten"),
    (date(2027, 3, 30),  date(2027, 4, 3),   "Ostern"),
    (date(2027, 5, 18),  date(2027, 5, 29),  "Pfingsten"),
    (date(2027, 7, 29),  date(2027, 9, 11),  "Sommer"),
]


def get_bw_holidays(year: int) -> dict[date, str]:
    """Gibt alle gesetzlichen Feiertage in BW für ein Jahr zurück."""
    try:
        from workalendar.europe import BadenWurttemberg
        cal = BadenWurttemberg()
        return {d: name for d, name in cal.holidays(year)}
    except ImportError:
        # Fallback: Hartcodierte BW-Feiertage für 2025/2026
        return _hardcoded_bw_holidays(year)


def _hardcoded_bw_holidays(year: int) -> dict[date, str]:
    """Fallback für gesetzliche Feiertage BW (wenn workalendar nicht verfügbar)."""
    from datetime import timedelta
    import math

    def easter(year: int) -> date:
        """Gauss'sche Osterformel."""
        a = year % 19
        b = year // 100
        c = year % 100
        d = b // 4
        e = b % 4
        f = (b + 8) // 25
        g = (b - f + 1) // 3
        h = (19 * a + b - d - g + 15) % 30
        i = c // 4
        k = c % 4
        l = (32 + 2 * e + 2 * i - h - k) % 7
        m = (a + 11 * h + 22 * l) // 451
        month = (h + l - 7 * m + 114) // 31
        day = ((h + l - 7 * m + 114) % 31) + 1
        return date(year, month, day)

    e = easter(year)
    holidays = {
        date(year, 1, 1):   "Neujahr",
        date(year, 1, 6):   "Heilige Drei Könige",
        e - timedelta(days=2): "Karfreitag",
        e:                  "Ostersonntag",
        e + timedelta(days=1): "Ostermontag",
        date(year, 5, 1):   "Tag der Arbeit",
        e + timedelta(days=39): "Christi Himmelfahrt",
        e + timedelta(days=49): "Pfingstsonntag",
        e + timedelta(days=50): "Pfingstmontag",
        e + timedelta(days=60): "Fronleichnam",
        date(year, 10, 3):  "Tag der Deutschen Einheit",
        date(year, 11, 1):  "Allerheiligen",
        date(year, 12, 25): "1. Weihnachtstag",
        date(year, 12, 26): "2. Weihnachtstag",
    }
    return holidays


def is_holiday(d: date, state: str = "BW") -> tuple[bool, str | None]:
    """Prüft ob ein Datum ein gesetzlicher Feiertag ist."""
    holidays = get_bw_holidays(d.year)
    name = holidays.get(d)
    return name is not None, name


def is_school_holiday(d: date) -> tuple[bool, str | None]:
    """Prueft ob ein Datum in BW-Schulferien faellt. Auto-selects correct school year."""
    for holiday_list in [BW_SCHOOL_HOLIDAYS_2025_26, BW_SCHOOL_HOLIDAYS_2026_27]:
        for start, end, name in holiday_list:
            if start <= d <= end:
                return True, name
    return False, None


def get_holiday_name(d: date, state: str = "BW") -> str | None:
    _, name = is_holiday(d, state)
    return name
