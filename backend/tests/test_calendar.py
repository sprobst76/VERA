"""
Tests für iCal-Feed / calendar.py

Da der public endpoint AsyncSessionLocal direkt verwendet (kein DI),
testen wir die _build_calendar-Hilfsfunktion als Unit-Tests
und das Routing über den Authenticated-Endpunkt (vacation-data) per Client.
"""
import uuid
from datetime import date, time, datetime, timezone
from types import SimpleNamespace

import pytest
from icalendar import Calendar

from app.api.v1.calendar import _build_calendar


def make_shift(shift_date, start="08:00", end="16:00", status="confirmed",
               employee_id=None, template_name="Tagdienst", template=None,
               shift_type_id=None):
    h_s, m_s = map(int, start.split(":"))
    h_e, m_e = map(int, end.split(":"))
    emp_id = employee_id or uuid.uuid4()
    tpl = template or SimpleNamespace(name=template_name)
    return SimpleNamespace(
        id=uuid.uuid4(),
        date=shift_date,
        start_time=time(h_s, m_s),
        end_time=time(h_e, m_e),
        break_minutes=30,
        status=status,
        employee_id=emp_id,
        template=tpl,
        shift_type_id=shift_type_id,
        location=None,
        confirmation_note=None,
        notes=None,
    )


def make_shift_type(reminder_enabled=True, reminder_minutes_before=60, name="Frühdienst"):
    st_id = uuid.uuid4()
    st = SimpleNamespace(
        id=st_id,
        name=name,
        reminder_enabled=reminder_enabled,
        reminder_minutes_before=reminder_minutes_before,
    )
    return st_id, st


def make_employee(first="Erika", last="Mustermann"):
    emp_id = uuid.uuid4()
    return emp_id, SimpleNamespace(id=emp_id, first_name=first, last_name=last)


# ── _build_calendar Unit Tests ────────────────────────────────────────────────

def test_build_calendar_returns_bytes():
    """_build_calendar liefert bytes-Daten."""
    result = _build_calendar([], {}, "Test")
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_build_calendar_valid_ical():
    """Ausgabe ist valides iCal."""
    emp_id, emp = make_employee()
    shift = make_shift(date(2025, 10, 1), employee_id=emp_id)
    result = _build_calendar([shift], {emp_id: emp}, "Test-Kalender")
    cal = Calendar.from_ical(result)
    assert cal is not None


def test_build_calendar_cal_name():
    """x-wr-calname und name enthalten den Kalender-Namen."""
    result = _build_calendar([], {}, "VERA – Stefan Müller")
    cal = Calendar.from_ical(result)
    assert "Stefan" in str(cal.get("x-wr-calname", ""))


def test_build_calendar_event_count():
    """Jede nicht-stornierte Schicht erzeugt ein VEVENT."""
    emp_id, emp = make_employee()
    shifts = [
        make_shift(date(2025, 10, 1), employee_id=emp_id, status="confirmed"),
        make_shift(date(2025, 10, 2), employee_id=emp_id, status="completed"),
        make_shift(date(2025, 10, 3), employee_id=emp_id, status="cancelled"),       # wird übersprungen
        make_shift(date(2025, 10, 4), employee_id=emp_id, status="cancelled_absence"),  # wird übersprungen
    ]
    result = _build_calendar(shifts, {emp_id: emp}, "Test")
    cal = Calendar.from_ical(result)
    events = [c for c in cal.walk() if c.name == "VEVENT"]
    assert len(events) == 2  # nur confirmed + completed


def test_build_calendar_summary_includes_template_name():
    """Event-Titel enthält den Dienstnamen."""
    emp_id, emp = make_employee("Max", "Mustermann")
    shift = make_shift(date(2025, 10, 1), employee_id=emp_id, template_name="Frühdienst")
    result = _build_calendar([shift], {emp_id: emp}, "Test")
    cal = Calendar.from_ical(result)
    events = [c for c in cal.walk() if c.name == "VEVENT"]
    summary = str(events[0].get("summary"))
    assert "Frühdienst" in summary


def test_build_calendar_summary_includes_employee_name():
    """Event-Titel enthält Vorname und Nachname des Mitarbeiters."""
    emp_id, emp = make_employee("Erika", "Mustermann")
    shift = make_shift(date(2025, 10, 1), employee_id=emp_id, template_name="Spätdienst")
    result = _build_calendar([shift], {emp_id: emp}, "Test")
    cal = Calendar.from_ical(result)
    events = [c for c in cal.walk() if c.name == "VEVENT"]
    summary = str(events[0].get("summary"))
    assert "Erika" in summary
    assert "Mustermann" in summary
    assert "Spätdienst" in summary


def test_build_calendar_summary_without_employee_map():
    """Wenn kein emp_map → nur Template-Name im Titel (kein Fehler)."""
    shift = make_shift(date(2025, 10, 1), template_name="Nachtdienst")
    result = _build_calendar([shift], {}, "Test")
    cal = Calendar.from_ical(result)
    events = [c for c in cal.walk() if c.name == "VEVENT"]
    summary = str(events[0].get("summary"))
    assert "Nachtdienst" in summary


def test_build_calendar_summary_format():
    """Format: 'Dienstname – Vorname Nachname'."""
    emp_id, emp = make_employee("Anna", "Schmidt")
    shift = make_shift(date(2025, 10, 1), employee_id=emp_id, template_name="Tagdienst")
    result = _build_calendar([shift], {emp_id: emp}, "Test")
    cal = Calendar.from_ical(result)
    events = [c for c in cal.walk() if c.name == "VEVENT"]
    summary = str(events[0].get("summary"))
    assert summary == "Tagdienst – Anna Schmidt"


def test_build_calendar_midnight_crossing_shift():
    """Schicht die Mitternacht überschreitet (23:00–07:00) hat end > start."""
    emp_id, emp = make_employee()
    shift = make_shift(date(2025, 10, 1), start="23:00", end="07:00",
                       employee_id=emp_id)
    result = _build_calendar([shift], {emp_id: emp}, "Test")
    cal = Calendar.from_ical(result)
    events = [c for c in cal.walk() if c.name == "VEVENT"]
    assert len(events) == 1
    ev = events[0]
    dtstart = ev.get("dtstart").dt
    dtend = ev.get("dtend").dt
    assert dtend > dtstart


def test_build_calendar_no_template_uses_default():
    """Schicht ohne Template → 'Dienst' als Fallback-Titel."""
    emp_id, emp = make_employee("Karl", "Müller")
    shift = make_shift(date(2025, 10, 1), employee_id=emp_id)
    shift.template = None  # kein Template
    result = _build_calendar([shift], {emp_id: emp}, "Test")
    cal = Calendar.from_ical(result)
    events = [c for c in cal.walk() if c.name == "VEVENT"]
    summary = str(events[0].get("summary"))
    assert "Dienst" in summary
    assert "Karl" in summary


def test_build_calendar_multiple_employees():
    """Admin-Feed: mehrere Mitarbeiter, jeder Event hat eigenen Namen."""
    emp_id1, emp1 = make_employee("Anna", "Alpha")
    emp_id2, emp2 = make_employee("Bert", "Beta")
    emp_map = {emp_id1: emp1, emp_id2: emp2}

    shifts = [
        make_shift(date(2025, 10, 1), employee_id=emp_id1, template_name="Frühdienst"),
        make_shift(date(2025, 10, 2), employee_id=emp_id2, template_name="Spätdienst"),
    ]
    result = _build_calendar(shifts, emp_map, "Alle Dienste")
    cal = Calendar.from_ical(result)
    events = [c for c in cal.walk() if c.name == "VEVENT"]
    summaries = [str(e.get("summary")) for e in events]

    assert any("Anna" in s for s in summaries)
    assert any("Bert" in s for s in summaries)
    assert any("Frühdienst" in s for s in summaries)
    assert any("Spätdienst" in s for s in summaries)


# ── VALARM – Diensttyp-Erinnerungen im iCal ──────────────────────────────────

def test_build_calendar_valarm_added_when_reminder_enabled():
    """VALARM-Komponente erscheint im Event wenn Diensttyp reminder_enabled=True."""
    emp_id, emp = make_employee()
    st_id, st = make_shift_type(reminder_enabled=True, reminder_minutes_before=60)
    shift = make_shift(date(2025, 10, 1), employee_id=emp_id, shift_type_id=st_id)

    result = _build_calendar([shift], {emp_id: emp}, "Test", shift_type_map={st_id: st})
    cal = Calendar.from_ical(result)
    events = [c for c in cal.walk() if c.name == "VEVENT"]
    assert len(events) == 1

    alarms = [c for c in events[0].walk() if c.name == "VALARM"]
    assert len(alarms) == 1


def test_build_calendar_valarm_trigger_offset():
    """VALARM trigger entspricht -reminder_minutes_before."""
    from datetime import timedelta
    emp_id, emp = make_employee()
    st_id, st = make_shift_type(reminder_enabled=True, reminder_minutes_before=90)
    shift = make_shift(date(2025, 10, 1), employee_id=emp_id, shift_type_id=st_id)

    result = _build_calendar([shift], {emp_id: emp}, "Test", shift_type_map={st_id: st})
    cal = Calendar.from_ical(result)
    events = [c for c in cal.walk() if c.name == "VEVENT"]
    alarms = [c for c in events[0].walk() if c.name == "VALARM"]
    trigger = alarms[0].get("trigger").dt
    assert trigger == timedelta(minutes=-90)


def test_build_calendar_no_valarm_when_reminder_disabled():
    """Kein VALARM wenn reminder_enabled=False."""
    emp_id, emp = make_employee()
    st_id, st = make_shift_type(reminder_enabled=False, reminder_minutes_before=60)
    shift = make_shift(date(2025, 10, 1), employee_id=emp_id, shift_type_id=st_id)

    result = _build_calendar([shift], {emp_id: emp}, "Test", shift_type_map={st_id: st})
    cal = Calendar.from_ical(result)
    events = [c for c in cal.walk() if c.name == "VEVENT"]
    alarms = [c for c in events[0].walk() if c.name == "VALARM"]
    assert len(alarms) == 0


def test_build_calendar_no_valarm_without_shift_type_map():
    """Kein VALARM wenn kein shift_type_map übergeben wird."""
    emp_id, emp = make_employee()
    shift = make_shift(date(2025, 10, 1), employee_id=emp_id)

    result = _build_calendar([shift], {emp_id: emp}, "Test")
    cal = Calendar.from_ical(result)
    events = [c for c in cal.walk() if c.name == "VEVENT"]
    alarms = [c for c in events[0].walk() if c.name == "VALARM"]
    assert len(alarms) == 0


def test_build_calendar_no_valarm_when_shift_type_not_in_map():
    """Kein VALARM wenn shift_type_id nicht im Map."""
    emp_id, emp = make_employee()
    st_id, _ = make_shift_type()
    shift = make_shift(date(2025, 10, 1), employee_id=emp_id, shift_type_id=st_id)

    # Leere Map – Typ nicht enthalten
    result = _build_calendar([shift], {emp_id: emp}, "Test", shift_type_map={})
    cal = Calendar.from_ical(result)
    events = [c for c in cal.walk() if c.name == "VEVENT"]
    alarms = [c for c in events[0].walk() if c.name == "VALARM"]
    assert len(alarms) == 0


def test_build_calendar_only_events_with_type_get_alarm():
    """Nur Events mit Diensttyp + reminder_enabled bekommen VALARM."""
    emp_id, emp = make_employee()
    st_id, st = make_shift_type(reminder_enabled=True, reminder_minutes_before=30)

    shift_with_type = make_shift(date(2025, 10, 1), employee_id=emp_id, shift_type_id=st_id)
    shift_without_type = make_shift(date(2025, 10, 2), employee_id=emp_id)  # kein shift_type_id

    result = _build_calendar(
        [shift_with_type, shift_without_type],
        {emp_id: emp}, "Test",
        shift_type_map={st_id: st},
    )
    cal = Calendar.from_ical(result)
    events = [c for c in cal.walk() if c.name == "VEVENT"]
    assert len(events) == 2

    alarm_counts = [len([c for c in ev.walk() if c.name == "VALARM"]) for ev in events]
    assert sum(alarm_counts) == 1  # Nur ein Event hat VALARM
