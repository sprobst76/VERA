"""
Szenarien: Eintrittsdatum (start_date) und Vertragsverlauf bearbeiten/löschen.

Testet:
  - start_date als valid_from beim ersten ContractHistory-Eintrag
  - Retroaktiver Eintrag in der Mitte der Kette (Chain-Splitting)
  - PUT /employees/{id}/contracts/{cid} – Inhalt bearbeiten
  - DELETE /employees/{id}/contracts/{cid} – Eintrag löschen + Kette reparieren
"""
import uuid
from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contract_history import ContractHistory
from app.models.employee import Employee
from tests.conftest import auth_headers


# ─── Hilfsfunktionen ──────────────────────────────────────────────────────────

async def mk_employee(client: AsyncClient, token: str, **kwargs) -> dict:
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
    assert r.status_code == 201, f"mk_employee failed: {r.text}"
    return r.json()


async def add_contract(client: AsyncClient, token: str, emp_id: str, **kwargs) -> dict:
    r = await client.post(
        f"/api/v1/employees/{emp_id}/contracts",
        json=kwargs,
        headers=auth_headers(token),
    )
    assert r.status_code == 201, f"add_contract failed: {r.text}"
    return r.json()


async def history(db: AsyncSession, emp_id: str) -> list[ContractHistory]:
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


# ─── start_date ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_start_date_wird_als_valid_from_genutzt(client, admin_token, db):
    """
    Mitarbeiter mit start_date="2024-09-01" anlegen.
    Erster ContractHistory-Eintrag soll valid_from=2024-09-01 haben.
    """
    emp = await mk_employee(
        client, admin_token,
        first_name="Eintrittsdatum",
        last_name="Test",
        contract_type="minijob",
        hourly_rate=12.00,
        start_date="2024-09-01",
    )
    eid = emp["id"]
    assert emp["start_date"] == "2024-09-01"

    h = await history(db, eid)
    assert len(h) >= 1, "Mindestens 1 ContractHistory-Eintrag erwartet"
    first = min(h, key=lambda e: e.valid_from)
    assert str(first.valid_from) == "2024-09-01", (
        f"Erster Eintrag soll valid_from=2024-09-01 haben, ist {first.valid_from}"
    )
    assert first.valid_to is None, "Erster Eintrag soll noch offen sein"
    assert float(first.hourly_rate) == 12.00


@pytest.mark.asyncio
async def test_kein_start_date_nutzt_heute(client, admin_token, db):
    """
    Mitarbeiter ohne start_date anlegen.
    Erster ContractHistory-Eintrag soll valid_from=heute haben.
    """
    today = date.today().isoformat()
    emp = await mk_employee(
        client, admin_token,
        first_name="Kein",
        last_name="Startdatum",
        contract_type="minijob",
        hourly_rate=13.50,
    )
    eid = emp["id"]
    assert emp["start_date"] is None

    h = await history(db, eid)
    assert len(h) >= 1
    first = min(h, key=lambda e: e.valid_from)
    assert str(first.valid_from) == today, (
        f"Ohne start_date soll valid_from=heute ({today}) sein, ist {first.valid_from}"
    )


@pytest.mark.asyncio
async def test_start_date_aenderbar_via_put(client, admin_token, db):
    """
    start_date über PUT /employees/{id} ändern.
    Das ContractHistory wird dabei nicht verändert.
    """
    emp = await mk_employee(
        client, admin_token,
        first_name="Start",
        last_name="Aenderbar",
        contract_type="minijob",
        hourly_rate=13.50,
        start_date="2025-01-01",
    )
    eid = emp["id"]

    h_before = await history(db, eid)

    r = await client.put(
        f"/api/v1/employees/{eid}",
        json={"start_date": "2024-08-01"},
        headers=auth_headers(admin_token),
    )
    assert r.status_code == 200
    assert r.json()["start_date"] == "2024-08-01"

    h_after = await history(db, eid)
    assert len(h_before) == len(h_after), "PUT start_date darf keine ContractHistory anlegen"


# ─── Retroaktiver Eintrag (Chain-Splitting) ──────────────────────────────────

@pytest.mark.asyncio
async def test_retroaktiv_in_mitte_der_kette(client, admin_token, db):
    """
    Hans startet mit start_date=01.01.2026 (Minijob, 13.00€).
    Am 01.05.2026 bekommt er 13.50€.
    Admin bemerkt nachträglich: am 01.03.2026 gab es schon 13.25€.

    Erwartete Kette nach retroaktivem Eintrag: Jan → Mär → Mai → offen
    - Jan: valid_to=2026-03-01
    - Mär: valid_from=2026-03-01, valid_to=2026-05-01
    - Mai: valid_from=2026-05-01, valid_to=None
    """
    hans = await mk_employee(
        client, admin_token,
        first_name="Hans",
        last_name="Kettensplit",
        contract_type="minijob",
        hourly_rate=13.00,
        start_date="2026-01-01",  # Initialeintrag = Jan 2026
    )
    eid = hans["id"]

    # Mai-Eintrag hinzufügen → schließt Jan
    await add_contract(client, admin_token, eid,
        valid_from="2026-05-01", contract_type="minijob",
        hourly_rate=13.50, monthly_hours_limit=38.0)

    db.expire_all()
    h_before = await history(db, eid)
    jan = next((e for e in h_before if str(e.valid_from) == "2026-01-01"), None)
    mai = next((e for e in h_before if str(e.valid_from) == "2026-05-01"), None)
    assert jan is not None, "Jan-Eintrag (via start_date) muss existieren"
    assert str(jan.valid_to) == "2026-05-01", f"Jan soll bis Mai geschlossen sein: {jan.valid_to}"
    assert mai is not None
    assert mai.valid_to is None

    # Retroaktiver Eintrag März (in der Mitte der Jan–Mai-Periode)
    r = await client.post(
        f"/api/v1/employees/{eid}/contracts",
        json={
            "valid_from": "2026-03-01",
            "contract_type": "minijob",
            "hourly_rate": 13.25,
            "monthly_hours_limit": 38.0,
            "note": "Nachkorrektur März",
        },
        headers=auth_headers(admin_token),
    )
    assert r.status_code == 201, r.text

    db.expire_all()
    h_after = await history(db, eid)

    jan_e = next((e for e in h_after if str(e.valid_from) == "2026-01-01"), None)
    mar_e = next((e for e in h_after if str(e.valid_from) == "2026-03-01"), None)
    mai_e = next((e for e in h_after if str(e.valid_from) == "2026-05-01"), None)

    assert jan_e is not None, "Jan-Eintrag muss noch existieren"
    assert mar_e is not None, "März-Eintrag muss angelegt worden sein"
    assert mai_e is not None, "Mai-Eintrag muss noch existieren"

    assert str(jan_e.valid_to) == "2026-03-01", (
        f"Jan-Eintrag soll bis März reichen, ist {jan_e.valid_to}"
    )
    assert float(mar_e.hourly_rate) == 13.25
    assert str(mar_e.valid_to) == "2026-05-01", (
        f"März-Eintrag soll bis Mai reichen, ist {mar_e.valid_to}"
    )
    assert mai_e.valid_to is None, "Mai-Eintrag soll weiterhin offen sein"
    assert float(mai_e.hourly_rate) == 13.50


@pytest.mark.asyncio
async def test_retroaktiv_vor_erster_periode(client, admin_token, db):
    """
    Mitarbeiter hat einen auto-Eintrag (today).
    Retroaktiver Eintrag VOR diesem Datum (z.B. 2024-01-01).
    Da der neue Eintrag vor dem auto-Eintrag liegt, gibt es keinen
    containing-Eintrag mit valid_from <= 2024-01-01.
    Der Eintrag soll trotzdem angelegt werden (mit valid_to=None oder auto-today).
    """
    emp = await mk_employee(
        client, admin_token,
        first_name="Retroaktiv",
        last_name="VorErster",
        contract_type="minijob",
        hourly_rate=12.00,
    )
    eid = emp["id"]

    # Retroaktiver Eintrag weit in der Vergangenheit
    r = await client.post(
        f"/api/v1/employees/{eid}/contracts",
        json={
            "valid_from": "2024-01-01",
            "contract_type": "minijob",
            "hourly_rate": 11.00,
            "note": "Sehr alter Eintrag",
        },
        headers=auth_headers(admin_token),
    )
    assert r.status_code == 201, r.text

    h = await history(db, eid)
    old_e = next((e for e in h if str(e.valid_from) == "2024-01-01"), None)
    assert old_e is not None, "Retroaktiver Eintrag muss angelegt worden sein"
    assert float(old_e.hourly_rate) == 11.00


# ─── PUT /employees/{id}/contracts/{cid} ──────────────────────────────────────

@pytest.mark.asyncio
async def test_update_contract_aendert_felder(client, admin_token, db):
    """
    Bestehenden Vertragseintrag bearbeiten via PUT.
    valid_from/valid_to bleiben unverändert, nur Inhalt ändert sich.
    """
    emp = await mk_employee(
        client, admin_token,
        first_name="Update",
        last_name="Vertrag",
        contract_type="minijob",
        hourly_rate=13.00,
    )
    eid = emp["id"]

    # Expliziten Eintrag anlegen
    c = await add_contract(client, admin_token, eid,
        valid_from="2026-01-01", contract_type="minijob",
        hourly_rate=13.00, monthly_hours_limit=38.0,
        note="Original")
    cid = c["id"]

    # Bearbeiten
    r = await client.put(
        f"/api/v1/employees/{eid}/contracts/{cid}",
        json={"hourly_rate": 13.75, "note": "Korrigiert"},
        headers=auth_headers(admin_token),
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert float(data["hourly_rate"]) == 13.75
    assert data["note"] == "Korrigiert"
    assert data["valid_from"] == "2026-01-01"  # unverändert


@pytest.mark.asyncio
async def test_update_contract_aktueller_eintrag_spiegelt_employee(client, admin_token, db):
    """
    Wird der aktuell gültige Eintrag (valid_to=None) bearbeitet,
    sollen die Employee-Spiegelfelder aktualisiert werden.
    """
    emp = await mk_employee(
        client, admin_token,
        first_name="Mirror",
        last_name="Update",
        contract_type="minijob",
        hourly_rate=13.00,
    )
    eid = emp["id"]

    # Den aktuellen Eintrag (valid_to=None) holen
    h = await history(db, eid)
    current = next(e for e in h if e.valid_to is None)
    cid = str(current.id)

    r = await client.put(
        f"/api/v1/employees/{eid}/contracts/{cid}",
        json={"hourly_rate": 14.50, "monthly_hours_limit": 45.0},
        headers=auth_headers(admin_token),
    )
    assert r.status_code == 200, r.text

    emp_data = await get_employee(client, admin_token, eid)
    assert emp_data["hourly_rate"] == 14.50, (
        f"Employee.hourly_rate soll 14.50 sein, ist {emp_data['hourly_rate']}"
    )
    assert emp_data["monthly_hours_limit"] == 45.0


@pytest.mark.asyncio
async def test_update_contract_alter_eintrag_spiegelt_nicht(client, admin_token, db):
    """
    Wird ein historischer Eintrag (valid_to != None) bearbeitet,
    sollen die Employee-Spiegelfelder NICHT verändert werden.
    """
    emp = await mk_employee(
        client, admin_token,
        first_name="History",
        last_name="NoMirror",
        contract_type="minijob",
        hourly_rate=13.00,
    )
    eid = emp["id"]

    # Zweiten Eintrag anlegen (schließt den ersten)
    await add_contract(client, admin_token, eid,
        valid_from="2026-06-01", contract_type="minijob",
        hourly_rate=14.00, monthly_hours_limit=40.0)

    h = await history(db, eid)
    old = next(e for e in h if e.valid_to is not None)
    old_id = str(old.id)

    # Alten Eintrag bearbeiten
    r = await client.put(
        f"/api/v1/employees/{eid}/contracts/{old_id}",
        json={"hourly_rate": 99.00},  # absurd hoher Wert zum Erkennen
        headers=auth_headers(admin_token),
    )
    assert r.status_code == 200, r.text

    emp_data = await get_employee(client, admin_token, eid)
    assert emp_data["hourly_rate"] != 99.00, (
        "Employee.hourly_rate darf NICHT vom alten Eintrag gespiegelt werden"
    )
    assert emp_data["hourly_rate"] == 14.00


@pytest.mark.asyncio
async def test_update_contract_falsche_id_gibt_404(client, admin_token):
    """PUT mit unbekannter contract_id → 404."""
    emp = await mk_employee(
        client, admin_token,
        first_name="Fehler",
        last_name="404",
        contract_type="minijob",
        hourly_rate=13.00,
    )
    r = await client.put(
        f"/api/v1/employees/{emp['id']}/contracts/{uuid.uuid4()}",
        json={"hourly_rate": 14.00},
        headers=auth_headers(admin_token),
    )
    assert r.status_code == 404


# ─── DELETE /employees/{id}/contracts/{cid} ──────────────────────────────────

@pytest.mark.asyncio
async def test_delete_contract_repariert_kette(client, admin_token, db):
    """
    Kette: Jan → Mär → offen.
    März-Eintrag löschen.
    Danach: Jan → offen (Jan.valid_to wird auf None gesetzt = Mär.valid_to).
    """
    emp = await mk_employee(
        client, admin_token,
        first_name="Delete",
        last_name="Kette",
        contract_type="minijob",
        hourly_rate=13.00,
    )
    eid = emp["id"]

    await add_contract(client, admin_token, eid,
        valid_from="2026-01-01", contract_type="minijob",
        hourly_rate=13.00, monthly_hours_limit=38.0)

    mar = await add_contract(client, admin_token, eid,
        valid_from="2026-03-01", contract_type="minijob",
        hourly_rate=13.50, monthly_hours_limit=38.0)
    mar_id = mar["id"]

    h_before = await history(db, eid)
    jan_e = next(e for e in h_before if str(e.valid_from) == "2026-01-01")
    assert str(jan_e.valid_to) == "2026-03-01"

    # März-Eintrag löschen
    r = await client.delete(
        f"/api/v1/employees/{eid}/contracts/{mar_id}",
        headers=auth_headers(admin_token),
    )
    assert r.status_code == 204, r.text

    db.expire_all()
    h_after = await history(db, eid)

    # März-Eintrag weg
    assert not any(str(e.valid_from) == "2026-03-01" for e in h_after), (
        "März-Eintrag soll gelöscht sein"
    )

    # Jan-Eintrag wieder offen (valid_to repariert)
    jan_e_after = next((e for e in h_after if str(e.valid_from) == "2026-01-01"), None)
    assert jan_e_after is not None
    assert jan_e_after.valid_to is None, (
        f"Jan-Eintrag soll nach Löschung wieder offen sein, ist {jan_e_after.valid_to}"
    )


@pytest.mark.asyncio
async def test_delete_contract_mittlerer_eintrag(client, admin_token, db):
    """
    Kette: Jan → Mär → Mai → offen.
    März-Eintrag löschen.
    Danach: Jan → Mai (Jan.valid_to = Mär.valid_to = Mai.valid_from).
    """
    emp = await mk_employee(
        client, admin_token,
        first_name="Delete",
        last_name="Mitte",
        contract_type="minijob",
        hourly_rate=13.00,
        start_date="2026-01-01",  # Initialeintrag = Jan 2026
    )
    eid = emp["id"]

    mar = await add_contract(client, admin_token, eid,
        valid_from="2026-03-01", contract_type="minijob", hourly_rate=13.25)
    await add_contract(client, admin_token, eid,
        valid_from="2026-05-01", contract_type="minijob", hourly_rate=13.50)
    mar_id = mar["id"]

    r = await client.delete(
        f"/api/v1/employees/{eid}/contracts/{mar_id}",
        headers=auth_headers(admin_token),
    )
    assert r.status_code == 204, r.text

    db.expire_all()
    h_after = await history(db, eid)

    assert not any(str(e.valid_from) == "2026-03-01" for e in h_after)

    jan_e = next((e for e in h_after if str(e.valid_from) == "2026-01-01"), None)
    assert jan_e is not None
    assert str(jan_e.valid_to) == "2026-05-01", (
        f"Jan.valid_to soll 2026-05-01 (ehemaliges Mär.valid_to) sein, ist {jan_e.valid_to}"
    )

    mai_e = next((e for e in h_after if str(e.valid_from) == "2026-05-01"), None)
    assert mai_e is not None
    assert mai_e.valid_to is None


@pytest.mark.asyncio
async def test_delete_contract_aktueller_eintrag_spiegelt_vorgaenger(client, admin_token, db):
    """
    Kette: Jan → Mai → offen.
    Mai-Eintrag (aktuell, valid_to=None) löschen.
    Danach: Jan → offen.
    Employee soll jetzt Werte des Jan-Eintrags spiegeln.
    """
    emp = await mk_employee(
        client, admin_token,
        first_name="Delete",
        last_name="Aktuell",
        contract_type="minijob",
        hourly_rate=13.00,
    )
    eid = emp["id"]

    await add_contract(client, admin_token, eid,
        valid_from="2026-01-01", contract_type="minijob",
        hourly_rate=13.00, monthly_hours_limit=38.0)

    mai = await add_contract(client, admin_token, eid,
        valid_from="2026-05-01", contract_type="minijob",
        hourly_rate=14.00, monthly_hours_limit=43.0)
    mai_id = mai["id"]

    # Jetzt hat Employee.hourly_rate = 14.00
    emp_data = await get_employee(client, admin_token, eid)
    assert emp_data["hourly_rate"] == 14.00

    # Aktuellen Eintrag löschen
    r = await client.delete(
        f"/api/v1/employees/{eid}/contracts/{mai_id}",
        headers=auth_headers(admin_token),
    )
    assert r.status_code == 204, r.text

    emp_data_after = await get_employee(client, admin_token, eid)
    assert emp_data_after["hourly_rate"] == 13.00, (
        f"Nach Löschung soll Employee.hourly_rate=13.00 (Vorgänger), ist {emp_data_after['hourly_rate']}"
    )
    assert emp_data_after["monthly_hours_limit"] == 38.0


@pytest.mark.asyncio
async def test_delete_contract_einziger_eintrag_gibt_fehler(client, admin_token, db):
    """
    Mitarbeiter hat nur 1 ContractHistory-Eintrag.
    Löschen soll fehlschlagen (422), da mindestens 1 Eintrag bleiben muss.
    """
    emp = await mk_employee(
        client, admin_token,
        first_name="Nur",
        last_name="Einer",
        contract_type="minijob",
        hourly_rate=13.00,
    )
    eid = emp["id"]

    h = await history(db, eid)
    assert len(h) == 1
    only_id = str(h[0].id)

    r = await client.delete(
        f"/api/v1/employees/{eid}/contracts/{only_id}",
        headers=auth_headers(admin_token),
    )
    assert r.status_code == 422, (
        f"Löschen des einzigen Eintrags soll 422 geben, war {r.status_code}: {r.text}"
    )


@pytest.mark.asyncio
async def test_delete_contract_falsche_id_gibt_404(client, admin_token):
    """DELETE mit unbekannter contract_id → 404."""
    emp = await mk_employee(
        client, admin_token,
        first_name="Fehler",
        last_name="Delete404",
        contract_type="minijob",
        hourly_rate=13.00,
    )
    r = await client.delete(
        f"/api/v1/employees/{emp['id']}/contracts/{uuid.uuid4()}",
        headers=auth_headers(admin_token),
    )
    assert r.status_code == 404
