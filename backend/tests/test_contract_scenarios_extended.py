"""
Erweiterter Vertrags-Szenarien-Test – viele Personas, Varianten, Randfälle.

Personas:
  Clara Vogel     – Minijob → Lohnerhöhung → Kündigung
  Marc Becker     – Minijob → Vollzeit (alle Parameter wechseln)
  Sophie Kramer   – 3 aufeinanderfolgende Vertragsänderungen
  Jan Hartmann    – Vertragstyp A → Vertragstyp B mit valid_from
  Nina Schulz     – Vertragstyp-Lohnerhöhung per Gruppenupdate
  Gregor Fischer  – Retroaktive Vertragsänderung (valid_from in der Vergangenheit)
  Lena + Kai      – Geteilter Typ; Lena kündigt; Update betrifft nur Kai
  Patricia Hagen  – Manuell + Typ zuweisen + Typ-Update (kombiniert)
  Emma Braun      – Payroll mit echten Schichten und Stundenlohnwechsel
  Felix Neumann   – Mehrfach-Zuweisung: Typ entfernen, neuen Typ zuweisen
"""
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contract_history import ContractHistory
from app.models.employee import Employee
from tests.conftest import auth_headers


# ─── Hilfsfunktionen ──────────────────────────────────────────────────────────

async def mk_employee(client: AsyncClient, token: str, **kwargs) -> dict:
    """Mitarbeiter anlegen mit vernünftigen Defaults."""
    body = {
        "first_name": "Test",
        "last_name": "Person",
        "contract_type": "minijob",
        "hourly_rate": 13.50,
        "monthly_hours_limit": 38.0,
        "annual_salary_limit": 6672.0,
    }
    body.update(kwargs)
    r = await client.post("/api/v1/employees", json=body, headers=auth_headers(token))
    assert r.status_code == 201, f"create_employee failed: {r.text}"
    return r.json()


async def mk_contract_type(client: AsyncClient, token: str, **kwargs) -> dict:
    """Vertragstyp anlegen."""
    body = {
        "name": "Standard Minijob",
        "contract_category": "minijob",
        "hourly_rate": 13.50,
        "monthly_hours_limit": 38.0,
        "annual_salary_limit": 6672.0,
    }
    body.update(kwargs)
    r = await client.post("/api/v1/contract-types", json=body, headers=auth_headers(token))
    assert r.status_code == 201, f"create_contract_type failed: {r.text}"
    return r.json()


async def add_contract(client: AsyncClient, token: str, emp_id: str, **kwargs) -> dict:
    """Neuen Vertragseintrag für Mitarbeiter anlegen."""
    r = await client.post(
        f"/api/v1/employees/{emp_id}/contracts",
        json=kwargs,
        headers=auth_headers(token),
    )
    assert r.status_code == 201, f"add_contract failed: {r.text}"
    return r.json()


async def assign_type(client: AsyncClient, token: str, emp_id: str,
                      ct_id: str | None, valid_from: str | None = None) -> dict:
    """Vertragstyp einem Mitarbeiter zuweisen."""
    body: dict = {"contract_type_id": ct_id}
    if valid_from:
        body["valid_from"] = valid_from
    r = await client.post(
        f"/api/v1/employees/{emp_id}/assign-contract-type",
        json=body,
        headers=auth_headers(token),
    )
    assert r.status_code == 200, f"assign_type failed: {r.text}"
    return r.json()


async def update_type(client: AsyncClient, token: str, ct_id: str, **kwargs) -> dict:
    """Vertragstyp aktualisieren (mit optionalem apply_from für Bulk-History)."""
    r = await client.put(
        f"/api/v1/contract-types/{ct_id}",
        json=kwargs,
        headers=auth_headers(token),
    )
    assert r.status_code == 200, f"update_type failed: {r.text}"
    return r.json()


async def history(db: AsyncSession, emp_id: str) -> list[ContractHistory]:
    """ContractHistory für Mitarbeiter, sortiert nach valid_from aufsteigend."""
    result = await db.execute(
        select(ContractHistory)
        .where(ContractHistory.employee_id == uuid.UUID(emp_id))
        .order_by(ContractHistory.valid_from)
    )
    return result.scalars().all()


async def get_employee(client: AsyncClient, token: str, emp_id: str) -> dict:
    r = await client.get(f"/api/v1/employees/{emp_id}", headers=auth_headers(token))
    assert r.status_code == 200
    return r.json()


async def mk_shift(client: AsyncClient, token: str, emp_id: str,
                   date_str: str, start="08:00:00", end="16:00:00",
                   break_minutes=30) -> dict:
    """Schicht anlegen und direkt als completed markieren (via PUT)."""
    r = await client.post(
        "/api/v1/shifts",
        json={
            "date": date_str,
            "start_time": start,
            "end_time": end,
            "break_minutes": break_minutes,
            "employee_id": emp_id,
        },
        headers=auth_headers(token),
    )
    assert r.status_code == 201, f"mk_shift create failed: {r.text}"
    shift_id = r.json()["id"]
    # Status auf 'completed' setzen (nur Admin möglich)
    r2 = await client.put(
        f"/api/v1/shifts/{shift_id}",
        json={"status": "completed"},
        headers=auth_headers(token),
    )
    assert r2.status_code == 200, f"mk_shift set-completed failed: {r2.text}"
    return r2.json()


# ─── Persona 1: Clara Vogel – Lohnerhöhung dann Kündigung ─────────────────────

@pytest.mark.asyncio
async def test_clara_lohnerhoehung_dann_kuendigung(client, admin_token, db):
    """
    Clara startet 01.01.2026 Minijob à 13.00 €.
    Am 01.04.2026 bekommt sie 13.50 €.
    Am 30.06.2026 wird sie deaktiviert.
    Erwartung: 2 ContractHistory-Einträge, Employee.is_active=False.
    """
    clara = await mk_employee(client, admin_token,
        first_name="Clara", last_name="Vogel",
        contract_type="minijob", hourly_rate=13.00,
        start_date="2026-01-01")  # Initialeintrag = Jan 2026
    eid = clara["id"]

    h = await history(db, eid)
    # Initialeintrag via start_date = Jan 2026
    assert any(str(e.valid_from) == "2026-01-01" for e in h), "Kein Jan-Eintrag"

    # Lohnerhöhung ab April
    await add_contract(client, admin_token, eid,
        valid_from="2026-04-01", contract_type="minijob",
        hourly_rate=13.50, monthly_hours_limit=38.0)

    db.expire_all()
    h = await history(db, eid)
    jan_entry = next(e for e in h if str(e.valid_from) == "2026-01-01")
    apr_entry = next(e for e in h if str(e.valid_from) == "2026-04-01")

    assert str(jan_entry.valid_to) == "2026-04-01", "Jan-Eintrag soll bis April gelten"
    assert float(jan_entry.hourly_rate) == 13.00
    assert apr_entry.valid_to is None, "Apr-Eintrag soll noch offen sein"
    assert float(apr_entry.hourly_rate) == 13.50

    # Kündigung: Mitarbeiter deaktivieren
    r = await client.put(f"/api/v1/employees/{eid}",
        json={"is_active": False}, headers=auth_headers(admin_token))
    assert r.status_code == 200
    emp = r.json()
    assert emp["is_active"] is False

    # ContractHistory bleibt unverändert – kein Eintrag wird durch Deaktivierung angelegt
    h_after = await history(db, eid)
    assert len(h_after) == len(h), "Deaktivierung darf keine neue ContractHistory anlegen"


# ─── Persona 2: Marc Becker – Minijob → Vollzeit ──────────────────────────────

@pytest.mark.asyncio
async def test_marc_minijob_zu_vollzeit(client, admin_token, db):
    """
    Marc startet 01.03.2026 als Minijob (13.00 €).
    Wechselt 01.09.2026 zu Vollzeit (18.00 € + Jahressoll 1800h).
    Erwartung: März-Aug Minijob geschlossen, ab Sep Vollzeit offen.
    Employee-Spiegel zeigt neue Werte.
    """
    marc = await mk_employee(client, admin_token,
        first_name="Marc", last_name="Becker",
        contract_type="minijob", hourly_rate=13.00,
        start_date="2026-03-01")  # Initialeintrag = März 2026
    eid = marc["id"]

    await add_contract(client, admin_token, eid,
        valid_from="2026-09-01", contract_type="full_time",
        hourly_rate=18.00, annual_hours_target=1800.0,
        weekly_hours=40.0)

    h = await history(db, eid)
    minijob_h = [e for e in h if e.contract_type == "minijob" and str(e.valid_from) == "2026-03-01"]
    vollzeit_h = [e for e in h if e.contract_type == "full_time"]

    assert len(minijob_h) == 1
    assert str(minijob_h[0].valid_to) == "2026-09-01", "Minijob soll bis Sep geschlossen sein"

    assert len(vollzeit_h) == 1
    assert vollzeit_h[0].valid_to is None, "Vollzeit-Eintrag soll offen sein"
    assert float(vollzeit_h[0].hourly_rate) == 18.00
    assert vollzeit_h[0].annual_hours_target is not None
    assert float(vollzeit_h[0].annual_hours_target) == 1800.0

    emp = await get_employee(client, admin_token, eid)
    assert emp["contract_type"] == "full_time"
    assert emp["hourly_rate"] == 18.00
    assert emp["annual_hours_target"] == 1800.0


# ─── Persona 3: Sophie Kramer – 3 Vertragsänderungen ─────────────────────────

@pytest.mark.asyncio
async def test_sophie_drei_vertragsaenderungen(client, admin_token, db):
    """
    Sophie: Minijob (Jan) → Teilzeit 20h (Mai) → Vollzeit 40h (Sep).
    Genau 3 ContractHistory-Einträge; Jan und Mai sind geschlossen, Sep offen.
    """
    sophie = await mk_employee(client, admin_token,
        first_name="Sophie", last_name="Kramer",
        contract_type="minijob", hourly_rate=13.00,
        start_date="2026-01-01")  # Initialeintrag = Jan 2026
    eid = sophie["id"]

    await add_contract(client, admin_token, eid,
        valid_from="2026-05-01", contract_type="part_time",
        hourly_rate=15.00, weekly_hours=20.0)

    await add_contract(client, admin_token, eid,
        valid_from="2026-09-01", contract_type="full_time",
        hourly_rate=18.00, weekly_hours=40.0, annual_hours_target=1800.0)

    h = await history(db, eid)
    relevant = [e for e in h if str(e.valid_from) in ("2026-01-01", "2026-05-01", "2026-09-01")]
    assert len(relevant) == 3

    e_jan = next(e for e in relevant if str(e.valid_from) == "2026-01-01")
    e_mai = next(e for e in relevant if str(e.valid_from) == "2026-05-01")
    e_sep = next(e for e in relevant if str(e.valid_from) == "2026-09-01")

    assert e_jan.contract_type == "minijob"
    assert str(e_jan.valid_to) == "2026-05-01"

    assert e_mai.contract_type == "part_time"
    assert float(e_mai.hourly_rate) == 15.00
    assert str(e_mai.valid_to) == "2026-09-01"

    assert e_sep.contract_type == "full_time"
    assert float(e_sep.hourly_rate) == 18.00
    assert e_sep.valid_to is None

    emp = await get_employee(client, admin_token, eid)
    assert emp["contract_type"] == "full_time"
    assert emp["hourly_rate"] == 18.00


# ─── Persona 4: Jan Hartmann – Vertragstyp A → Vertragstyp B ─────────────────

@pytest.mark.asyncio
async def test_jan_typ_zu_anderem_typ(client, admin_token, db):
    """
    Jan bekommt Vertragstyp 'Minijob A' (13.00 €) ab 01.01.2026.
    Am 01.07.2026 wechselt er zu 'Minijob B' (13.50 €).
    Beide Typen haben unterschiedliche monatliche Stundenlimits.
    Erwartung: Typ-A-Eintrag geschlossen bis Jul, Typ-B-Eintrag offen.
    """
    typ_a = await mk_contract_type(client, admin_token,
        name="Minijob A", contract_category="minijob",
        hourly_rate=13.00, monthly_hours_limit=35.0)
    typ_b = await mk_contract_type(client, admin_token,
        name="Minijob B", contract_category="minijob",
        hourly_rate=13.50, monthly_hours_limit=43.0)

    jan = await mk_employee(client, admin_token,
        first_name="Jan", last_name="Hartmann",
        contract_type="minijob", hourly_rate=13.00)
    eid = jan["id"]

    # Typ A zuweisen ab 01.01.2026
    await assign_type(client, admin_token, eid, typ_a["id"], "2026-01-01")

    h = await history(db, eid)
    a_entries = [e for e in h if e.contract_type_id == uuid.UUID(typ_a["id"])]
    assert len(a_entries) >= 1
    assert a_entries[-1].valid_to is None

    # Typ B zuweisen ab 01.07.2026
    await assign_type(client, admin_token, eid, typ_b["id"], "2026-07-01")

    db.expire_all()
    h = await history(db, eid)
    a_entries = [e for e in h if e.contract_type_id == uuid.UUID(typ_a["id"])]
    b_entries = [e for e in h if e.contract_type_id == uuid.UUID(typ_b["id"])]

    assert any(str(e.valid_to) == "2026-07-01" for e in a_entries), \
        "Typ-A-Eintrag soll bis 01.07. geschlossen sein"

    assert len(b_entries) == 1
    assert b_entries[0].valid_to is None
    assert float(b_entries[0].hourly_rate) == 13.50
    assert float(b_entries[0].monthly_hours_limit) == 43.0

    emp = await get_employee(client, admin_token, eid)
    assert emp["contract_type_id"] == typ_b["id"]
    assert emp["hourly_rate"] == 13.50


# ─── Persona 5: Nina Schulz – Lohnerhöhung per Gruppenupdate ──────────────────

@pytest.mark.asyncio
async def test_nina_gruppenupdate_lohnerhoehung(client, admin_token, db):
    """
    Nina ist 'Minijob Standard' zugeordnet (13.00 €).
    Der Vertragstyp bekommt eine Lohnerhöhung auf 13.80 € ab 01.06.2026.
    Ninas History: alte Einträge geschlossen, neuer Eintrag mit 13.80 € offen.
    """
    typ = await mk_contract_type(client, admin_token,
        name="Minijob Standard Nina",
        contract_category="minijob",
        hourly_rate=13.00, monthly_hours_limit=40.0)

    nina = await mk_employee(client, admin_token,
        first_name="Nina", last_name="Schulz",
        contract_type="minijob", hourly_rate=13.00)
    eid = nina["id"]

    # Typ ab 01.01.2026 zuweisen
    await assign_type(client, admin_token, eid, typ["id"], "2026-01-01")

    h_before = await history(db, eid)
    open_before = [e for e in h_before if e.valid_to is None]
    assert len(open_before) == 1
    assert float(open_before[0].hourly_rate) == 13.00

    # Lohnerhöhung per Typ-Update
    result = await update_type(client, admin_token, typ["id"],
        hourly_rate=13.80, apply_from="2026-06-01")
    assert result["updated_employees"] >= 1

    db.expire_all()
    h_after = await history(db, eid)
    new_entry = next((e for e in h_after if str(e.valid_from) == "2026-06-01"), None)
    assert new_entry is not None, "Kein neuer Eintrag ab 01.06. gefunden"
    assert float(new_entry.hourly_rate) == 13.80
    assert new_entry.valid_to is None

    # Alter Eintrag muss geschlossen sein
    old_entry = next((e for e in h_after if float(e.hourly_rate) == 13.00
                      and e.contract_type_id == uuid.UUID(typ["id"])), None)
    assert old_entry is None or old_entry.valid_to is not None, \
        "Alter 13.00€-Eintrag soll geschlossen sein"

    emp = await get_employee(client, admin_token, eid)
    assert emp["hourly_rate"] == 13.80


# ─── Persona 6: Gregor Fischer – Retroaktive Vertragsänderung ─────────────────

@pytest.mark.asyncio
async def test_gregor_retroaktiv(client, admin_token, db):
    """
    Gregor hat seit auto-heute einen Minijob-Eintrag.
    Admin stellt nachträglich fest: er hätte ab 01.01.2026 einen höheren Satz haben sollen.
    Retroaktiver Eintrag ab 01.01.2026 schließt den alten Eintrag.
    Älterer Eintrag (auto-today) bekommt valid_to=01.01.2026.
    """
    # start_date="2025-12-01" → Initialeintrag in der Vergangenheit
    # Retroaktiver Eintrag 2026-01-01 liegt NACH dem Initialeintrag → Chain-Split korrekt
    gregor = await mk_employee(client, admin_token,
        first_name="Gregor", last_name="Fischer",
        contract_type="minijob", hourly_rate=13.00,
        start_date="2025-12-01")
    eid = gregor["id"]

    h_before = await history(db, eid)
    assert len(h_before) == 1
    auto_entry = h_before[0]
    assert str(auto_entry.valid_from) == "2025-12-01"

    # Retroaktiver Eintrag: 01.01.2026 (nach start_date, aber vor "heute")
    await add_contract(client, admin_token, eid,
        valid_from="2026-01-01", contract_type="minijob",
        hourly_rate=13.70, monthly_hours_limit=38.0,
        note="Nachkorrektur: höherer Satz ab Jan 2026")

    h_after = await history(db, eid)
    jan_entry = next((e for e in h_after if str(e.valid_from) == "2026-01-01"), None)
    assert jan_entry is not None, "Retroaktiver Eintrag fehlt"
    assert float(jan_entry.hourly_rate) == 13.70
    assert jan_entry.valid_to is None, "Neuer (aktueller) Eintrag soll offen sein"
    assert jan_entry.note == "Nachkorrektur: höherer Satz ab Jan 2026"

    # Der Dezember-Eintrag muss auf 2026-01-01 geschlossen worden sein
    await db.refresh(auto_entry)
    assert str(auto_entry.valid_to) == "2026-01-01", \
        f"Dez-Eintrag soll valid_to=2026-01-01 haben, ist {auto_entry.valid_to}"


# ─── Personas 7a+7b: Lena + Kai – Geteilter Typ, Lena kündigt ────────────────

@pytest.mark.asyncio
async def test_lena_kai_geteilter_typ_lena_kuendigt(client, admin_token, db):
    """
    Lena und Kai sind beide auf 'Minijob Shared' (13.00 €).
    Lena wird deaktiviert (is_active=False).
    Typ-Update auf 13.50 € ab 01.05.2026 darf nur Kai betreffen (active_only=True).
    Lenas ContractHistory bleibt unverändert.
    """
    typ = await mk_contract_type(client, admin_token,
        name="Minijob Shared",
        contract_category="minijob",
        hourly_rate=13.00, monthly_hours_limit=40.0)

    lena = await mk_employee(client, admin_token,
        first_name="Lena", last_name="Weber",
        contract_type="minijob", hourly_rate=13.00)
    kai = await mk_employee(client, admin_token,
        first_name="Kai", last_name="Meier",
        contract_type="minijob", hourly_rate=13.00)

    # Beide dem Typ zuweisen (ohne valid_from = nur FK, kein History-Eintrag)
    await assign_type(client, admin_token, lena["id"], typ["id"])
    await assign_type(client, admin_token, kai["id"], typ["id"])

    # Lena kündigt
    await client.put(f"/api/v1/employees/{lena['id']}",
        json={"is_active": False}, headers=auth_headers(admin_token))

    lena_h_before = await history(db, lena["id"])

    # Typ-Update: nur aktive Mitarbeiter bekommen neuen History-Eintrag
    result = await update_type(client, admin_token, typ["id"],
        hourly_rate=13.50, apply_from="2026-05-01")

    # Nur Kai ist aktiv → 1 Mitarbeiter aktualisiert
    assert result["updated_employees"] == 1, \
        f"Nur 1 aktiver MA (Kai) soll aktualisiert werden, war: {result['updated_employees']}"

    # Lenas History bleibt unverändert
    lena_h_after = await history(db, lena["id"])
    assert len(lena_h_before) == len(lena_h_after), \
        "Lenas ContractHistory darf sich nicht ändern (inaktiv)"

    # Kai bekommt neuen Eintrag
    kai_h = await history(db, kai["id"])
    kai_new = [e for e in kai_h if str(e.valid_from) == "2026-05-01"]
    assert len(kai_new) == 1
    assert float(kai_new[0].hourly_rate) == 13.50


# ─── Persona 8: Patricia Hagen – Manuell + Typ + Update ──────────────────────

@pytest.mark.asyncio
async def test_patricia_manuell_dann_typ_dann_update(client, admin_token, db):
    """
    Patricia hatte erst einen manuellen Vertrag.
    Dann wird ihr ein Vertragstyp zugewiesen (mit valid_from → neuer History-Eintrag).
    Dann wird der Typ aktualisiert (Lohnerhöhung).
    Erwartung: korrekte Kette von History-Einträgen.
    """
    typ = await mk_contract_type(client, admin_token,
        name="Minijob Patricia",
        contract_category="minijob",
        hourly_rate=13.20, monthly_hours_limit=38.0)

    patricia = await mk_employee(client, admin_token,
        first_name="Patricia", last_name="Hagen",
        contract_type="minijob", hourly_rate=12.80,
        start_date="2026-01-01")  # Initialeintrag = Jan 2026
    eid = patricia["id"]

    # Typ zuweisen ab 01.04.2026 (schließt Jan-Eintrag, legt Apr-Eintrag an)
    await assign_type(client, admin_token, eid, typ["id"], "2026-04-01")

    h = await history(db, eid)
    jan_h = next((e for e in h if str(e.valid_from) == "2026-01-01"), None)
    apr_h = next((e for e in h if str(e.valid_from) == "2026-04-01"), None)

    assert jan_h is not None
    assert str(jan_h.valid_to) == "2026-04-01"
    assert apr_h is not None
    assert float(apr_h.hourly_rate) == 13.20
    assert apr_h.contract_type_id == uuid.UUID(typ["id"])
    assert apr_h.valid_to is None

    # Lohnerhöhung per Typ-Update
    result = await update_type(client, admin_token, typ["id"],
        hourly_rate=13.80, apply_from="2026-07-01")
    assert result["updated_employees"] >= 1

    db.expire_all()
    h_final = await history(db, eid)
    jul_h = next((e for e in h_final if str(e.valid_from) == "2026-07-01"), None)
    assert jul_h is not None, "Kein Juli-Eintrag nach Typ-Update"
    assert float(jul_h.hourly_rate) == 13.80
    assert jul_h.valid_to is None

    # Apr-Eintrag muss geschlossen sein
    apr_h_after = next((e for e in h_final if str(e.valid_from) == "2026-04-01"), None)
    assert apr_h_after is not None
    assert str(apr_h_after.valid_to) == "2026-07-01"

    # Vollständige Kette: Jan → Apr → Jul
    emp = await get_employee(client, admin_token, eid)
    assert emp["hourly_rate"] == 13.80


# ─── Persona 9: Emma Braun – Payroll mit echten Schichten ─────────────────────

@pytest.mark.asyncio
async def test_emma_payroll_mit_schichten(client, admin_token, db):
    """
    Emma hat im März 2026 Schichten à 8h mit 13.00 €/h.
    Ab 01.04.2026 steigt ihr Satz auf 14.00 €.
    Im April hat sie ebenfalls Schichten.
    Payroll März = Stunden × 13.00 (Basis, ohne Zuschlag).
    Payroll April = Stunden × 14.00 (Basis, ohne Zuschlag).
    """
    emma = await mk_employee(client, admin_token,
        first_name="Emma", last_name="Braun",
        contract_type="minijob", hourly_rate=13.00,
        monthly_hours_limit=50.0,
        start_date="2026-03-01")  # Initialeintrag = März 2026
    eid = emma["id"]

    await add_contract(client, admin_token, eid,
        valid_from="2026-04-01", contract_type="minijob",
        hourly_rate=14.00, monthly_hours_limit=50.0)

    # Schichten im März: 2 × 8h (abzgl. 30min Pause = 7.5h netto)
    for day in ["2026-03-10", "2026-03-17"]:
        await mk_shift(client, admin_token, eid, day,
            start="08:00:00", end="16:00:00", break_minutes=30)

    # Schichten im April: 2 × 8h
    for day in ["2026-04-07", "2026-04-14"]:
        await mk_shift(client, admin_token, eid, day,
            start="08:00:00", end="16:00:00", break_minutes=30)

    # Payroll März
    r_mar = await client.post("/api/v1/payroll/calculate",
        json={"employee_id": eid, "month": "2026-03-01"},
        headers=auth_headers(admin_token))
    assert r_mar.status_code == 200, r_mar.text
    pay_mar = r_mar.json()
    # actual_hours: 2 Schichten × 7.5h (8h − 30min Pause)
    assert pay_mar["actual_hours"] == pytest.approx(15.0, abs=0.1)
    # base_wage = 15h × 13.00 = 195.00 €
    assert pay_mar["base_wage"] == pytest.approx(195.00, abs=1.0)

    # Payroll April
    r_apr = await client.post("/api/v1/payroll/calculate",
        json={"employee_id": eid, "month": "2026-04-01"},
        headers=auth_headers(admin_token))
    assert r_apr.status_code == 200, r_apr.text
    pay_apr = r_apr.json()
    assert pay_apr["actual_hours"] == pytest.approx(15.0, abs=0.1)
    # base_wage = 15h × 14.00 = 210.00 €
    assert pay_apr["base_wage"] == pytest.approx(210.00, abs=1.0)

    # Sicherstellung: Märzlohn < Aprillohn (wegen höherem Satz)
    assert pay_mar["base_wage"] < pay_apr["base_wage"], \
        "März-Lohn soll kleiner als April-Lohn sein (niedrigerer Stundensatz)"


# ─── Persona 10: Felix Neumann – Typ entfernen, neuen zuweisen ────────────────

@pytest.mark.asyncio
async def test_felix_typ_entfernen_neu_zuweisen(client, admin_token, db):
    """
    Felix bekommt Typ A zugewiesen (mit valid_from → History-Eintrag).
    Typ wird entfernt (contract_type_id=null) – nur FK-Entkopplung, kein neuer History-Eintrag.
    Dann wird Typ B zugewiesen (mit valid_from → neuer History-Eintrag).
    Erwartung: 2 Einträge mit Typ-ID, Typ A geschlossen, Typ B offen.
    """
    typ_a = await mk_contract_type(client, admin_token,
        name="Felix Typ A", contract_category="minijob",
        hourly_rate=13.00, monthly_hours_limit=38.0)
    typ_b = await mk_contract_type(client, admin_token,
        name="Felix Typ B", contract_category="part_time",
        hourly_rate=16.00, weekly_hours=25.0)

    felix = await mk_employee(client, admin_token,
        first_name="Felix", last_name="Neumann",
        contract_type="minijob", hourly_rate=13.00)
    eid = felix["id"]

    # Typ A zuweisen ab 01.02.2026
    await assign_type(client, admin_token, eid, typ_a["id"], "2026-02-01")
    h = await history(db, eid)
    assert any(e.contract_type_id == uuid.UUID(typ_a["id"]) for e in h)

    # Typ entfernen (nur FK) – kein new History Entry
    h_before_count = len(await history(db, eid))
    emp = await assign_type(client, admin_token, eid, None)
    assert emp["contract_type_id"] is None
    h_after_remove = await history(db, eid)
    assert len(h_after_remove) == h_before_count, "Entfernen des Typs darf keine History anlegen"

    # Typ B zuweisen ab 01.06.2026 → History-Eintrag
    await assign_type(client, admin_token, eid, typ_b["id"], "2026-06-01")

    db.expire_all()
    h_final = await history(db, eid)
    typ_a_entries = [e for e in h_final if e.contract_type_id == uuid.UUID(typ_a["id"])]
    typ_b_entries = [e for e in h_final if e.contract_type_id == uuid.UUID(typ_b["id"])]

    # Typ A Eintrag soll geschlossen sein
    assert all(e.valid_to is not None for e in typ_a_entries), \
        "Alle Typ-A-Einträge sollen geschlossen sein"

    assert len(typ_b_entries) == 1
    assert typ_b_entries[0].valid_to is None
    assert float(typ_b_entries[0].hourly_rate) == 16.00
    assert str(typ_b_entries[0].valid_from) == "2026-06-01"


# ─── Randfälle ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rand_gleiches_datum_zweimal(client, admin_token, db):
    """
    Zwei manuelle Einträge mit demselben valid_from: zweiter Eintrag schließt den ersten.
    Ergebnis: immer genau ein offener Eintrag.
    """
    emp = await mk_employee(client, admin_token,
        first_name="Rand", last_name="Gleich",
        contract_type="minijob", hourly_rate=13.00,
        start_date="2026-05-01")  # Initialeintrag = Mai 2026
    eid = emp["id"]

    # Zweiter Eintrag mit gleichem Datum (Duplikat) → 422
    r_dup = await client.post(
        f"/api/v1/employees/{eid}/contracts",
        json={"valid_from": "2026-05-01", "contract_type": "minijob",
              "hourly_rate": 13.25, "note": "Korrektur"},
        headers=auth_headers(admin_token),
    )
    assert r_dup.status_code == 422, (
        f"Doppelter valid_from soll 422 geben, war {r_dup.status_code}: {r_dup.text}"
    )

    # Nur 1 Eintrag soll existieren (der aus start_date)
    h = await history(db, eid)
    open_entries = [e for e in h if e.valid_to is None]
    assert len(open_entries) == 1, f"Genau 1 offener Eintrag erwartet, {len(open_entries)} gefunden"
    assert float(open_entries[0].hourly_rate) == 13.00  # Original, nicht Duplikat


@pytest.mark.asyncio
async def test_rand_kein_valid_from_bei_typ_zuweisung(client, admin_token, admin_user, tenant):
    """
    Vertragstyp ohne valid_from: effective_from = date.today().
    Da der initiale ContractHistory-Eintrag ebenfalls valid_from=heute hat,
    wird in-place aktualisiert (kein neuer Eintrag, kein Zero-Length-Eintrag).
    """
    typ = await mk_contract_type(client, admin_token,
        name="Typ ohne Datum", contract_category="minijob",
        hourly_rate=13.00)

    emp = await mk_employee(client, admin_token,
        first_name="Ohne", last_name="Datum",
        contract_type="minijob", hourly_rate=13.00)
    eid = emp["id"]

    r_before = await client.get(f"/api/v1/employees/{eid}/contracts", headers=auth_headers(admin_token))
    count_before = len(r_before.json())

    await assign_type(client, admin_token, eid, typ["id"])  # kein valid_from

    r_after = await client.get(f"/api/v1/employees/{eid}/contracts", headers=auth_headers(admin_token))
    contracts = r_after.json()

    # In-place-Update: Anzahl bleibt gleich, kein Zero-Length-Eintrag
    assert len(contracts) == count_before, \
        "Gleiches Datum → In-place-Update, kein neuer Eintrag"

    open_entries = [c for c in contracts if c["valid_to"] is None]
    assert len(open_entries) == 1
    assert open_entries[0]["contract_type_id"] == typ["id"]

    emp_data = await get_employee(client, admin_token, eid)
    assert emp_data["contract_type_id"] == typ["id"]


@pytest.mark.asyncio
async def test_rand_typ_update_ohne_apply_from_kein_history(client, admin_token, db):
    """
    Typ-Update ohne apply_from: nur Typ-Metadaten ändern sich,
    keine neuen ContractHistory-Einträge für Mitarbeiter.
    """
    typ = await mk_contract_type(client, admin_token,
        name="Typ kein apply_from", contract_category="minijob",
        hourly_rate=13.00)

    emp = await mk_employee(client, admin_token,
        first_name="Kein", last_name="ApplyFrom",
        contract_type="minijob", hourly_rate=13.00)
    eid = emp["id"]
    await assign_type(client, admin_token, eid, typ["id"])

    h_before = await history(db, eid)

    # Nur den Namen ändern – kein Lohnfeld, kein apply_from
    r = await client.put(f"/api/v1/contract-types/{typ['id']}",
        json={"name": "Umbenannt"},
        headers=auth_headers(admin_token))
    assert r.status_code == 200
    assert r.json()["updated_employees"] == 0

    h_after = await history(db, eid)
    assert len(h_before) == len(h_after), \
        "Name-Update ohne Lohnänderung darf keine History anlegen"


@pytest.mark.asyncio
async def test_rand_payroll_ohne_schichten(client, admin_token, db):
    """
    Mitarbeiter ohne Schichten: Payroll berechnet 0 Stunden, 0 Lohn.
    Kein Fehler, nur leerer Eintrag.
    """
    emp = await mk_employee(client, admin_token,
        first_name="Leere", last_name="Abrechnung",
        contract_type="minijob", hourly_rate=13.50)
    eid = emp["id"]

    r = await client.post("/api/v1/payroll/calculate",
        json={"employee_id": eid, "month": "2026-04-01"},
        headers=auth_headers(admin_token))
    assert r.status_code == 200
    p = r.json()
    assert p["actual_hours"] == 0.0
    assert p["total_gross"] == 0.0


@pytest.mark.asyncio
async def test_rand_mehrere_mitarbeiter_gleichzeitig_update(client, admin_token, db):
    """
    5 Mitarbeiter auf demselben Typ. Alle bekommen gleichzeitig neue Konditionen.
    updated_employees muss 5 sein.
    """
    typ = await mk_contract_type(client, admin_token,
        name="Gruppentyp 5x", contract_category="minijob",
        hourly_rate=12.50)

    emp_ids = []
    for i in range(5):
        emp = await mk_employee(client, admin_token,
            first_name=f"Person{i}", last_name="Gruppe",
            contract_type="minijob", hourly_rate=12.50)
        await assign_type(client, admin_token, emp["id"], typ["id"])
        emp_ids.append(emp["id"])

    result = await update_type(client, admin_token, typ["id"],
        hourly_rate=13.00, apply_from="2026-06-01")
    assert result["updated_employees"] == 5

    for eid in emp_ids:
        h = await history(db, eid)
        new = [e for e in h if str(e.valid_from) == "2026-06-01"]
        assert len(new) == 1, f"Mitarbeiter {eid} hat keinen neuen Eintrag"
        assert float(new[0].hourly_rate) == 13.00


@pytest.mark.asyncio
async def test_rand_vertragsverlauf_api_liefert_korrekte_reihenfolge(client, admin_token, db):
    """
    GET /employees/{id}/contracts gibt Einträge zurück (neueste zuerst laut API).
    Mit 3 Einträgen: Sep > Mai > Jan.
    """
    emp = await mk_employee(client, admin_token,
        first_name="Reihen", last_name="Folge",
        contract_type="minijob", hourly_rate=13.00)
    eid = emp["id"]

    for valid_from, rate in [("2026-01-01", 13.00), ("2026-05-01", 13.25), ("2026-09-01", 13.50)]:
        await add_contract(client, admin_token, eid,
            valid_from=valid_from, contract_type="minijob", hourly_rate=rate)

    r = await client.get(f"/api/v1/employees/{eid}/contracts",
        headers=auth_headers(admin_token))
    assert r.status_code == 200
    contracts = r.json()

    # API liefert neueste zuerst
    dates = [c["valid_from"] for c in contracts if c["valid_from"] in
             ("2026-01-01", "2026-05-01", "2026-09-01")]
    assert dates == ["2026-09-01", "2026-05-01", "2026-01-01"], \
        f"Falsche Reihenfolge: {dates}"

    # Sep-Eintrag ist offen
    sep = next(c for c in contracts if c["valid_from"] == "2026-09-01")
    assert sep["valid_to"] is None
    assert float(sep["hourly_rate"]) == pytest.approx(13.50)
