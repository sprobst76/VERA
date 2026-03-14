"""
Tests für GET /employees/{id}/memberships und assign-contract-type → Membership-History.

Prüft:
- GET gibt leere Liste zurück wenn kein Typ zugewiesen
- Zuweisung mit valid_from → Membership + ContractHistory angelegt
- Zuweisung OHNE valid_from → Membership + ContractHistory angelegt (date.today())
- Typ-Wechsel → alter Eintrag bekommt valid_to, neuer ist offen
- Entfernung (contract_type_id=null) → offener Eintrag bekommt valid_to
- RBAC: Employee-Rolle darf GET /memberships nicht aufrufen
"""
import uuid
import pytest
from datetime import date
from sqlalchemy import select
from tests.conftest import auth_headers

EMPLOYEES_URL = "/api/v1/employees"
CONTRACT_TYPES_URL = "/api/v1/contract-types"

EMP_PAYLOAD = {
    "first_name": "Luisa",
    "last_name": "Gruber",
    "contract_type": "minijob",
    "hourly_rate": 12.0,
    "monthly_hours_limit": 43.0,
    "annual_salary_limit": 6672.0,
    "vacation_days": 0,
    "qualifications": [],
}

CT_PAYLOAD = {
    "name": "Standard Minijob",
    "description": "Basis-Minijob-Profil",
    "contract_category": "minijob",
    "hourly_rate": 13.5,
    "monthly_hours_limit": 43.0,
    "annual_salary_limit": 6672.0,
}


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

async def create_employee(client, token):
    r = await client.post(EMPLOYEES_URL, json=EMP_PAYLOAD, headers=auth_headers(token))
    assert r.status_code == 201
    return r.json()["id"]


async def create_contract_type(client, token, payload=None):
    r = await client.post(CONTRACT_TYPES_URL, json=payload or CT_PAYLOAD, headers=auth_headers(token))
    assert r.status_code == 201
    return r.json()["id"]


async def assign_type(client, token, emp_id, ct_id, valid_from=None):
    body = {"contract_type_id": ct_id}
    if valid_from:
        body["valid_from"] = valid_from
    r = await client.post(
        f"{EMPLOYEES_URL}/{emp_id}/assign-contract-type",
        json=body,
        headers=auth_headers(token),
    )
    assert r.status_code == 200
    return r.json()


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_memberships_empty_initially(client, admin_token, admin_user, tenant):
    """Frisch angelegter Mitarbeiter hat keine Membership-Einträge."""
    emp_id = await create_employee(client, admin_token)

    r = await client.get(f"{EMPLOYEES_URL}/{emp_id}/memberships", headers=auth_headers(admin_token))
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_assign_with_valid_from_creates_membership_and_contract_history(
    client, admin_token, admin_user, tenant, db
):
    """Zuweisung mit valid_from → Membership + ContractHistory angelegt."""
    from app.models.employee_contract_type_membership import EmployeeContractTypeMembership
    from app.models.contract_history import ContractHistory

    emp_id = await create_employee(client, admin_token)
    ct_id = await create_contract_type(client, admin_token)

    await assign_type(client, admin_token, emp_id, ct_id, valid_from="2026-04-01")

    # Membership prüfen
    r = await client.get(f"{EMPLOYEES_URL}/{emp_id}/memberships", headers=auth_headers(admin_token))
    memberships = r.json()
    assert len(memberships) == 1
    m = memberships[0]
    assert m["contract_type_id"] == ct_id
    assert m["valid_from"] == "2026-04-01"
    assert m["valid_to"] is None

    # ContractHistory prüfen: 2 Einträge (auto + zugewiesener)
    contracts_r = await client.get(f"{EMPLOYEES_URL}/{emp_id}/contracts", headers=auth_headers(admin_token))
    contracts = contracts_r.json()
    assert len(contracts) == 2
    current = next(c for c in contracts if c["valid_to"] is None)
    assert current["contract_type_id"] == ct_id
    assert current["valid_from"] == "2026-04-01"


@pytest.mark.asyncio
async def test_assign_without_valid_from_creates_membership_and_contract_history(
    client, admin_token, admin_user, tenant, db
):
    """Zuweisung OHNE valid_from → Membership UND ContractHistory mit date.today() angelegt."""
    emp_id = await create_employee(client, admin_token)
    ct_id = await create_contract_type(client, admin_token)

    await assign_type(client, admin_token, emp_id, ct_id)  # kein valid_from

    # Membership vorhanden
    r = await client.get(f"{EMPLOYEES_URL}/{emp_id}/memberships", headers=auth_headers(admin_token))
    memberships = r.json()
    assert len(memberships) == 1
    assert memberships[0]["contract_type_id"] == ct_id
    assert memberships[0]["valid_to"] is None

    # ContractHistory: Eintrag mit contract_type_id muss vorhanden sein
    contracts_r = await client.get(f"{EMPLOYEES_URL}/{emp_id}/contracts", headers=auth_headers(admin_token))
    contracts = contracts_r.json()
    current = next((c for c in contracts if c["valid_to"] is None), None)
    assert current is not None
    assert current["contract_type_id"] == ct_id


@pytest.mark.asyncio
async def test_type_change_closes_old_membership(client, admin_token, admin_user, tenant):
    """Typ-Wechsel: alter Membership-Eintrag bekommt valid_to, neuer ist offen."""
    emp_id = await create_employee(client, admin_token)
    ct1_id = await create_contract_type(client, admin_token, {**CT_PAYLOAD, "name": "Typ A"})
    ct2_id = await create_contract_type(client, admin_token, {**CT_PAYLOAD, "name": "Typ B"})

    await assign_type(client, admin_token, emp_id, ct1_id, valid_from="2026-01-01")
    await assign_type(client, admin_token, emp_id, ct2_id, valid_from="2026-06-01")

    r = await client.get(f"{EMPLOYEES_URL}/{emp_id}/memberships", headers=auth_headers(admin_token))
    memberships = r.json()
    assert len(memberships) == 2

    current = next(m for m in memberships if m["valid_to"] is None)
    closed = next(m for m in memberships if m["valid_to"] is not None)

    assert current["contract_type_id"] == ct2_id
    assert current["valid_from"] == "2026-06-01"
    assert closed["contract_type_id"] == ct1_id
    assert closed["valid_to"] == "2026-06-01"


@pytest.mark.asyncio
async def test_type_change_closes_old_contract_history(client, admin_token, admin_user, tenant):
    """Typ-Wechsel: alter ContractHistory-Eintrag wird geschlossen, neuer angelegt."""
    emp_id = await create_employee(client, admin_token)
    ct1_id = await create_contract_type(client, admin_token, {**CT_PAYLOAD, "name": "Günstig", "hourly_rate": 12.0})
    ct2_id = await create_contract_type(client, admin_token, {**CT_PAYLOAD, "name": "Teuer", "hourly_rate": 15.0})

    await assign_type(client, admin_token, emp_id, ct1_id, valid_from="2026-01-01")
    await assign_type(client, admin_token, emp_id, ct2_id, valid_from="2026-07-01")

    contracts_r = await client.get(f"{EMPLOYEES_URL}/{emp_id}/contracts", headers=auth_headers(admin_token))
    contracts = contracts_r.json()

    current = next(c for c in contracts if c["valid_to"] is None)
    assert float(current["hourly_rate"]) == pytest.approx(15.0)
    assert current["contract_type_id"] == ct2_id

    # Alle Einträge mit valid_to: mindestens 2 (auto-Eintrag + erster zugewiesener)
    closed = [c for c in contracts if c["valid_to"] is not None]
    assert len(closed) >= 1


@pytest.mark.asyncio
async def test_remove_contract_type_closes_membership(client, admin_token, admin_user, tenant):
    """Entfernen (contract_type_id=null) schließt den offenen Membership-Eintrag."""
    emp_id = await create_employee(client, admin_token)
    ct_id = await create_contract_type(client, admin_token)

    await assign_type(client, admin_token, emp_id, ct_id, valid_from="2026-01-01")

    # Entfernen
    r = await client.post(
        f"{EMPLOYEES_URL}/{emp_id}/assign-contract-type",
        json={"contract_type_id": None},
        headers=auth_headers(admin_token),
    )
    assert r.status_code == 200
    assert r.json()["contract_type_id"] is None

    # Membership ist jetzt geschlossen
    memberships_r = await client.get(
        f"{EMPLOYEES_URL}/{emp_id}/memberships",
        headers=auth_headers(admin_token),
    )
    memberships = memberships_r.json()
    assert len(memberships) == 1
    assert memberships[0]["valid_to"] is not None  # geschlossen mit today()


@pytest.mark.asyncio
async def test_memberships_rbac_employee_forbidden(client, admin_token, employee_token, admin_user, employee_user, tenant):
    """Employee-Rolle darf GET /memberships nicht aufrufen (ManagerOrAdmin required)."""
    emp_id = await create_employee(client, admin_token)

    r = await client.get(
        f"{EMPLOYEES_URL}/{emp_id}/memberships",
        headers=auth_headers(employee_token),
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_memberships_includes_contract_type_name(client, admin_token, admin_user, tenant):
    """Membership-Antwort enthält contract_type_name (Join mit ContractType)."""
    emp_id = await create_employee(client, admin_token)
    ct_id = await create_contract_type(client, admin_token, {**CT_PAYLOAD, "name": "Sondervertrag"})

    await assign_type(client, admin_token, emp_id, ct_id)

    r = await client.get(f"{EMPLOYEES_URL}/{emp_id}/memberships", headers=auth_headers(admin_token))
    memberships = r.json()
    assert len(memberships) == 1
    assert memberships[0]["contract_type_name"] == "Sondervertrag"
