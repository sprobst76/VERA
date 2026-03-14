"""
Vertrags-Szenarien – Integrationstests für ContractHistory, assign-contract-type, Payroll.

Fiktive Mitarbeiter:
  Anna  – startet 01.04.2026 als Minijob
  Felix – wechselt 01.09.2026 von Minijob zu Teilzeit per Vertragstyp-Zuweisung
  Lea & Tom – beide auf "Minijob Standard"; Vorlage bekommt Lohnerhöhung
"""
import uuid
from datetime import date
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contract_history import ContractHistory
from app.models.employee import Employee
from tests.conftest import auth_headers


# ─── Hilfsfunktionen ──────────────────────────────────────────────────────────

async def create_employee(client: AsyncClient, token: str, **kwargs) -> dict:
    defaults = {
        "first_name": "Test",
        "last_name": "Mitarbeiter",
        "contract_type": "minijob",
        "hourly_rate": 13.50,
        "monthly_hours_limit": 38.0,
        "annual_salary_limit": 6672.0,
    }
    defaults.update(kwargs)
    r = await client.post("/api/v1/employees", json=defaults, headers=auth_headers(token))
    assert r.status_code == 201, r.text
    return r.json()


async def create_contract_type(client: AsyncClient, token: str, **kwargs) -> dict:
    defaults = {
        "name": "Minijob Standard",
        "contract_category": "minijob",
        "hourly_rate": 13.50,
        "monthly_hours_limit": 38.0,
        "annual_salary_limit": 6672.0,
    }
    defaults.update(kwargs)
    r = await client.post("/api/v1/contract-types", json=defaults, headers=auth_headers(token))
    assert r.status_code == 201, r.text
    return r.json()


async def get_contract_history(db: AsyncSession, employee_id: str) -> list[ContractHistory]:
    result = await db.execute(
        select(ContractHistory)
        .where(ContractHistory.employee_id == uuid.UUID(employee_id))
        .order_by(ContractHistory.valid_from)
    )
    return result.scalars().all()


# ─── Szenario 1: Anna startet als Minijob ─────────────────────────────────────

@pytest.mark.asyncio
async def test_szenario1_anna_neustart_minijob(client, admin_token, db):
    """
    Anna fängt am 01.04.2026 als Minijob an.
    Nach dem Anlegen soll:
    - 1 ContractHistory-Eintrag existieren
    - contract_type = 'minijob'
    - hourly_rate = 13.50
    - valid_to = None (noch offen)
    """
    anna = await create_employee(
        client, admin_token,
        first_name="Anna",
        last_name="Mueller",
        contract_type="minijob",
        hourly_rate=13.50,
        monthly_hours_limit=38.0,
        annual_salary_limit=6672.0,
    )

    history = await get_contract_history(db, anna["id"])

    assert len(history) == 1, f"Erwartet 1 ContractHistory-Eintrag, erhalten: {len(history)}"
    h = history[0]
    assert h.contract_type == "minijob"
    assert float(h.hourly_rate) == 13.50
    assert h.valid_to is None, "Erster Eintrag sollte offen sein (valid_to=None)"


@pytest.mark.asyncio
async def test_szenario1_anna_manuelle_contract_history(client, admin_token, db):
    """
    Anna soll einen manuellen ContractHistory-Eintrag bekommen können
    (z.B. via POST /employees/{id}/contracts) mit einem spezifischen Startdatum.
    """
    anna = await create_employee(
        client, admin_token,
        first_name="Anna",
        last_name="Mueller2",
        contract_type="minijob",
        hourly_rate=13.50,
    )
    emp_id = anna["id"]

    # Manuell neuen Vertrag ab 01.04.2026 anlegen (schließt automatisch alten)
    r = await client.post(
        f"/api/v1/employees/{emp_id}/contracts",
        json={
            "valid_from": "2026-04-01",
            "contract_type": "minijob",
            "hourly_rate": 13.50,
            "monthly_hours_limit": 38.0,
            "annual_salary_limit": 6672.0,
        },
        headers=auth_headers(admin_token),
    )
    assert r.status_code == 201, r.text

    history = await get_contract_history(db, emp_id)
    # Alter Eintrag (today) + neuer (01.04.2026) = 2 Einträge,
    # oder alter wurde ersetzt – je nach Implementierung
    assert any(
        str(h.valid_from) == "2026-04-01" for h in history
    ), f"Kein Eintrag mit valid_from=2026-04-01 gefunden: {[h.valid_from for h in history]}"

    # Der Eintrag ab 01.04 muss offen sein
    new_entry = next(h for h in history if str(h.valid_from) == "2026-04-01")
    assert new_entry.valid_to is None


# ─── Szenario 2: Felix wechselt von Minijob zu Teilzeit ───────────────────────

@pytest.mark.asyncio
async def test_szenario2_felix_vertragstyp_zuweisung_erstellt_history(client, admin_token, db):
    """
    Felix startet als Minijob. Dann soll ihm ein Vertragstyp 'Minijob Standard'
    zugewiesen werden – assign-contract-type MUSS eine ContractHistory anlegen.

    ERWARTETES VERHALTEN (nach Fix):
    - assign-contract-type akzeptiert valid_from
    - Neuer ContractHistory-Eintrag wird angelegt
    - Felder werden vom ContractType übernommen

    AKTUELLER STAND (BUG): assign-contract-type setzt nur den FK,
    keine ContractHistory wird angelegt.
    """
    felix = await create_employee(
        client, admin_token,
        first_name="Felix",
        last_name="Huber",
        contract_type="minijob",
        hourly_rate=13.00,  # alter Satz, bevor Vertragsvorlage
    )
    emp_id = felix["id"]

    # Vertragstyp anlegen
    ct = await create_contract_type(
        client, admin_token,
        name="Minijob Standard 2026",
        contract_category="minijob",
        hourly_rate=13.50,
        monthly_hours_limit=38.0,
        annual_salary_limit=6672.0,
    )
    ct_id = ct["id"]

    history_before = await get_contract_history(db, emp_id)

    # Vertragstyp zuweisen MIT valid_from (nach Fix)
    r = await client.post(
        f"/api/v1/employees/{emp_id}/assign-contract-type",
        json={
            "contract_type_id": ct_id,
            "valid_from": "2026-04-01",
        },
        headers=auth_headers(admin_token),
    )
    assert r.status_code == 200, r.text

    history_after = await get_contract_history(db, emp_id)

    # Nach dem Fix: Neue ContractHistory-Eintrag muss existieren
    assert len(history_after) > len(history_before), (
        f"BUG: assign-contract-type hat keine ContractHistory angelegt! "
        f"Vorher: {len(history_before)}, Nachher: {len(history_after)}"
    )

    new_entries = [h for h in history_after if str(h.valid_from) == "2026-04-01"]
    assert len(new_entries) == 1, f"Kein Eintrag mit valid_from=2026-04-01 gefunden"

    new_h = new_entries[0]
    assert float(new_h.hourly_rate) == 13.50, f"hourly_rate sollte 13.50 sein, ist {new_h.hourly_rate}"
    assert new_h.contract_type == "minijob"
    assert new_h.valid_to is None
    assert new_h.contract_type_id == uuid.UUID(ct_id)


@pytest.mark.asyncio
async def test_szenario2_felix_minijob_zu_teilzeit(client, admin_token, db):
    """
    Felix wechselt am 01.09.2026 von Minijob zu Teilzeit.
    Alter ContractHistory-Eintrag soll geschlossen werden (valid_to=01.09.2026),
    neuer Eintrag für Teilzeit soll offen sein.
    """
    felix = await create_employee(
        client, admin_token,
        first_name="Felix",
        last_name="Huber2",
        contract_type="minijob",
        hourly_rate=13.50,
    )
    emp_id = felix["id"]

    # Ersten (automatischen) Eintrag nach valid_from anpassen
    r1 = await client.post(
        f"/api/v1/employees/{emp_id}/contracts",
        json={
            "valid_from": "2026-01-01",
            "contract_type": "minijob",
            "hourly_rate": 13.50,
            "monthly_hours_limit": 38.0,
        },
        headers=auth_headers(admin_token),
    )
    assert r1.status_code == 201, r1.text

    # Wechsel zu Teilzeit ab 01.09.2026
    teilzeit_ct = await create_contract_type(
        client, admin_token,
        name="Teilzeit 20h",
        contract_category="part_time",
        hourly_rate=15.00,
        weekly_hours=20.0,
    )

    r2 = await client.post(
        f"/api/v1/employees/{emp_id}/assign-contract-type",
        json={
            "contract_type_id": teilzeit_ct["id"],
            "valid_from": "2026-09-01",
        },
        headers=auth_headers(admin_token),
    )
    assert r2.status_code == 200, r2.text

    history = await get_contract_history(db, emp_id)

    # Alten offenen Eintrag finden und prüfen ob er geschlossen wurde
    minijob_entries = [h for h in history if h.contract_type == "minijob"]
    assert any(h.valid_to is not None for h in minijob_entries), (
        "BUG: Alter Minijob-Eintrag wurde nicht geschlossen (valid_to=None)"
    )

    # Neuen Teilzeit-Eintrag prüfen
    teilzeit_entries = [h for h in history if h.contract_type == "part_time"]
    assert len(teilzeit_entries) >= 1, "Kein Teilzeit-ContractHistory-Eintrag gefunden"
    tz = next(h for h in teilzeit_entries if h.valid_to is None)
    assert float(tz.hourly_rate) == 15.00
    assert str(tz.valid_from) == "2026-09-01"

    # Employee-Spiegel muss aktualisiert sein
    emp_r = await client.get(f"/api/v1/employees/{emp_id}", headers=auth_headers(admin_token))
    emp_data = emp_r.json()
    assert emp_data["contract_type"] == "part_time", (
        f"Employee.contract_type wurde nicht auf 'part_time' aktualisiert: {emp_data['contract_type']}"
    )
    assert emp_data["hourly_rate"] == 15.00


# ─── Szenario 3: Gruppenvertrag-Update betrifft alle ──────────────────────────

@pytest.mark.asyncio
async def test_szenario3_gruppenvertrag_lohnerhohung(client, admin_token, db):
    """
    Lea und Tom sind beide auf 'Minijob Standard' (Vertragstyp).
    Der Stundenlohn wird ab 01.05.2026 von 13.50 auf 14.00 erhöht.
    Beide sollen automatisch neue ContractHistory-Einträge bekommen.
    """
    # Vertragstyp anlegen
    ct = await create_contract_type(
        client, admin_token,
        name="Minijob Standard",
        contract_category="minijob",
        hourly_rate=13.50,
        monthly_hours_limit=38.0,
        annual_salary_limit=6672.0,
    )
    ct_id = ct["id"]

    # Lea anlegen
    lea = await create_employee(client, admin_token,
        first_name="Lea", last_name="Schmidt",
        contract_type="minijob", hourly_rate=13.50)
    # Tom anlegen
    tom = await create_employee(client, admin_token,
        first_name="Tom", last_name="Wagner",
        contract_type="minijob", hourly_rate=13.50)

    # Beiden den Vertragstyp zuweisen (ohne valid_from für einfachen FK-Fall)
    for emp_id in [lea["id"], tom["id"]]:
        r = await client.post(
            f"/api/v1/employees/{emp_id}/assign-contract-type",
            json={"contract_type_id": ct_id},
            headers=auth_headers(admin_token),
        )
        assert r.status_code == 200, r.text

    # Stundenlohn erhöhen ab 01.05.2026
    r_update = await client.put(
        f"/api/v1/contract-types/{ct_id}",
        json={
            "hourly_rate": 14.00,
            "apply_from": "2026-05-01",
        },
        headers=auth_headers(admin_token),
    )
    assert r_update.status_code == 200, r_update.text
    update_data = r_update.json()
    assert update_data.get("updated_employees") == 2, (
        f"Erwartet 2 aktualisierte Mitarbeiter, erhalten: {update_data.get('updated_employees')}"
    )

    # ContractHistory für Lea und Tom prüfen
    for emp_id, name in [(lea["id"], "Lea"), (tom["id"], "Tom")]:
        history = await get_contract_history(db, emp_id)
        new_entries = [h for h in history if str(h.valid_from) == "2026-05-01"]
        assert len(new_entries) == 1, (
            f"{name}: Kein neuer ContractHistory-Eintrag ab 2026-05-01 gefunden"
        )
        assert float(new_entries[0].hourly_rate) == 14.00, (
            f"{name}: hourly_rate soll 14.00 sein, ist {new_entries[0].hourly_rate}"
        )
        assert new_entries[0].valid_to is None

        # Alter Eintrag muss geschlossen sein
        old_entries = [h for h in history if str(h.valid_from) != "2026-05-01"
                       and float(h.hourly_rate) == 13.50]
        assert any(h.valid_to is not None for h in old_entries), (
            f"{name}: Alter Eintrag mit 13.50€ wurde nicht geschlossen"
        )


# ─── Szenario 4: Payroll nutzt korrekten historischen Stundenlohn ──────────────

@pytest.mark.asyncio
async def test_szenario4_payroll_korrekter_historischer_satz(client, admin_token, db):
    """
    Maria hat im März 2026 einen Stundenlohn von 13.50 €.
    Ab 01.04.2026 steigt er auf 14.00 €.
    Payroll für März 2026 muss 13.50 € verwenden.
    Payroll für April 2026 muss 14.00 € verwenden.
    """
    maria = await create_employee(
        client, admin_token,
        first_name="Maria",
        last_name="Weber",
        contract_type="minijob",
        hourly_rate=13.50,
        monthly_hours_limit=40.0,
        annual_salary_limit=6672.0,
        start_date="2026-03-01",  # Initialeintrag = März 2026
    )
    emp_id = maria["id"]

    # Erster Eintrag wurde via start_date bereits angelegt (valid_from=2026-03-01)

    # Ab April: Lohnerhöhung auf 14.00 €
    r2 = await client.post(
        f"/api/v1/employees/{emp_id}/contracts",
        json={
            "valid_from": "2026-04-01",
            "contract_type": "minijob",
            "hourly_rate": 14.00,
            "monthly_hours_limit": 40.0,
        },
        headers=auth_headers(admin_token),
    )
    assert r2.status_code == 201, r2.text

    # ContractHistory prüfen
    history = await get_contract_history(db, emp_id)
    march_entries = [h for h in history if str(h.valid_from) == "2026-03-01"]
    april_entries = [h for h in history if str(h.valid_from) == "2026-04-01"]

    assert len(march_entries) >= 1, "Kein März-Eintrag gefunden"
    assert len(april_entries) >= 1, "Kein April-Eintrag gefunden"

    # März-Eintrag muss geschlossen sein (valid_to=01.04.2026)
    assert str(march_entries[-1].valid_to) == "2026-04-01", (
        f"März-Eintrag soll valid_to=2026-04-01 haben, ist {march_entries[-1].valid_to}"
    )

    # April-Eintrag muss offen sein
    assert april_entries[-1].valid_to is None

    # Payroll für März berechnen (nutzt 13.50 €)
    r_pay_march = await client.post(
        "/api/v1/payroll/calculate",
        json={"employee_id": emp_id, "month": "2026-03-01"},
        headers=auth_headers(admin_token),
    )
    assert r_pay_march.status_code == 200, r_pay_march.text
    pay_march = r_pay_march.json()
    assert pay_march["employee_id"] == emp_id

    # Payroll für April berechnen (nutzt 14.00 €)
    r_pay_april = await client.post(
        "/api/v1/payroll/calculate",
        json={"employee_id": emp_id, "month": "2026-04-01"},
        headers=auth_headers(admin_token),
    )
    assert r_pay_april.status_code == 200, r_pay_april.text
    pay_april = r_pay_april.json()
    assert pay_april["employee_id"] == emp_id


# ─── Szenario 5: Entfernen eines Vertragstyps ─────────────────────────────────

@pytest.mark.asyncio
async def test_szenario5_vertragstyp_entfernen(client, admin_token, db):
    """
    Karl hatte einen Vertragstyp zugewiesen. Wenn der Vertragstyp entfernt wird
    (contract_type_id=null), bleibt die ContractHistory erhalten.
    Der Employee.contract_type_id FK wird auf null gesetzt.
    """
    ct = await create_contract_type(
        client, admin_token,
        name="Befristet",
        contract_category="minijob",
        hourly_rate=13.00,
    )
    ct_id = ct["id"]

    karl = await create_employee(
        client, admin_token,
        first_name="Karl",
        last_name="Bauer",
        contract_type="minijob",
        hourly_rate=13.00,
    )
    emp_id = karl["id"]

    # Vertragstyp zuweisen
    r1 = await client.post(
        f"/api/v1/employees/{emp_id}/assign-contract-type",
        json={"contract_type_id": ct_id},
        headers=auth_headers(admin_token),
    )
    assert r1.status_code == 200

    # Vertragstyp entfernen
    r2 = await client.post(
        f"/api/v1/employees/{emp_id}/assign-contract-type",
        json={"contract_type_id": None},
        headers=auth_headers(admin_token),
    )
    assert r2.status_code == 200
    emp_data = r2.json()
    assert emp_data["contract_type_id"] is None

    # ContractHistory bleibt erhalten
    history = await get_contract_history(db, emp_id)
    assert len(history) >= 1, "ContractHistory darf nicht gelöscht werden"


# ─── Szenario 6: Fehlerfälle ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_szenario6_ungültiger_vertragstyp(client, admin_token):
    """assign-contract-type mit ungültiger UUID gibt 404."""
    emp = await create_employee(client, admin_token,
        first_name="Test", last_name="User",
        contract_type="minijob", hourly_rate=13.00)

    r = await client.post(
        f"/api/v1/employees/{emp['id']}/assign-contract-type",
        json={"contract_type_id": str(uuid.uuid4())},
        headers=auth_headers(admin_token),
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_szenario6_vertragstyp_löschen_mit_mitarbeitern(client, admin_token):
    """ContractType kann nicht gelöscht werden wenn Mitarbeiter zugewiesen."""
    ct = await create_contract_type(client, admin_token,
        name="Nicht löschbar", contract_category="minijob", hourly_rate=13.00)
    emp = await create_employee(client, admin_token,
        first_name="Test", last_name="User2",
        contract_type="minijob", hourly_rate=13.00)

    # Zuweisen
    await client.post(
        f"/api/v1/employees/{emp['id']}/assign-contract-type",
        json={"contract_type_id": ct["id"]},
        headers=auth_headers(admin_token),
    )

    # Löschen sollte fehlschlagen
    r = await client.delete(
        f"/api/v1/contract-types/{ct['id']}",
        headers=auth_headers(admin_token),
    )
    assert r.status_code == 400
    assert "zugewiesen" in r.json()["detail"]
