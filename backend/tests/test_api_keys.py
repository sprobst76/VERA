"""
Tests für /api/v1/api-keys – CRUD-Verwaltung über eine normale Admin-Session
(nicht über den X-API-Key-Auth-Pfad, der bereits in test_auth.py abgedeckt ist).
"""
import uuid

import pytest
from sqlalchemy import select

from app.models.audit import ApiKey
from tests.conftest import auth_headers

API_KEYS_URL = "/api/v1/api-keys"


@pytest.mark.asyncio
async def test_create_api_key_returns_full_key_once(client, admin_token, admin_user, tenant):
    resp = await client.post(API_KEYS_URL, json={"name": "n8n Integration", "scopes": ["write"]},
                              headers=auth_headers(admin_token))
    assert resp.status_code == 201
    data = resp.json()
    assert data["key"].startswith("vera_")
    assert data["key_prefix"] == data["key"][:12]
    assert data["scopes"] == ["write"]


@pytest.mark.asyncio
async def test_created_key_hash_never_recoverable(client, admin_token, admin_user, tenant, db):
    resp = await client.post(API_KEYS_URL, json={"name": "Test"}, headers=auth_headers(admin_token))
    raw_key = resp.json()["key"]

    result = await db.execute(select(ApiKey).where(ApiKey.tenant_id == tenant.id))
    stored = result.scalars().all()
    assert all(raw_key not in (k.key_hash or "") for k in stored)


@pytest.mark.asyncio
async def test_list_key_prefix_matches_creation_prefix(client, admin_token, admin_user, tenant):
    """Regression: der beim Anlegen gezeigte Präfix muss auch in der Liste wieder auftauchen
    (vorher wurde er aus dem Hash abgeleitet und stimmte nie überein)."""
    create_resp = await client.post(API_KEYS_URL, json={"name": "Zapier"}, headers=auth_headers(admin_token))
    created_prefix = create_resp.json()["key_prefix"]
    key_id = create_resp.json()["id"]

    list_resp = await client.get(API_KEYS_URL, headers=auth_headers(admin_token))
    entry = next(k for k in list_resp.json() if k["id"] == key_id)
    assert entry["key_prefix"] == created_prefix


@pytest.mark.asyncio
async def test_list_api_keys_excludes_raw_key(client, admin_token, admin_user, tenant):
    await client.post(API_KEYS_URL, json={"name": "Test"}, headers=auth_headers(admin_token))
    resp = await client.get(API_KEYS_URL, headers=auth_headers(admin_token))
    assert resp.status_code == 200
    assert all("key" not in entry for entry in resp.json())


@pytest.mark.asyncio
async def test_default_scope_is_read(client, admin_token, admin_user, tenant):
    resp = await client.post(API_KEYS_URL, json={"name": "Default Scope"}, headers=auth_headers(admin_token))
    assert resp.json()["scopes"] == ["read"]


@pytest.mark.asyncio
async def test_revoke_api_key(client, admin_token, admin_user, tenant):
    create_resp = await client.post(API_KEYS_URL, json={"name": "To Revoke"}, headers=auth_headers(admin_token))
    key_id = create_resp.json()["id"]

    del_resp = await client.delete(f"{API_KEYS_URL}/{key_id}", headers=auth_headers(admin_token))
    assert del_resp.status_code == 204

    list_resp = await client.get(API_KEYS_URL, headers=auth_headers(admin_token))
    assert all(k["id"] != key_id for k in list_resp.json())


@pytest.mark.asyncio
async def test_revoke_nonexistent_key_404(client, admin_token, admin_user, tenant):
    resp = await client.delete(f"{API_KEYS_URL}/{uuid.uuid4()}", headers=auth_headers(admin_token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_employee_cannot_manage_api_keys(client, employee_token, employee_user, tenant):
    resp = await client.post(API_KEYS_URL, json={"name": "Sneaky"}, headers=auth_headers(employee_token))
    assert resp.status_code == 403

    resp2 = await client.get(API_KEYS_URL, headers=auth_headers(employee_token))
    assert resp2.status_code == 403


@pytest.mark.asyncio
async def test_api_keys_scoped_to_own_tenant(client, admin_token, admin_token_b, admin_user, admin_user_b,
                                              tenant, tenant_b):
    """Ein API-Key eines anderen Tenants darf nicht sichtbar oder löschbar sein (IDOR-Schutz)."""
    create_resp = await client.post(API_KEYS_URL, json={"name": "Tenant A Key"}, headers=auth_headers(admin_token))
    key_id = create_resp.json()["id"]

    other_list = await client.get(API_KEYS_URL, headers=auth_headers(admin_token_b))
    assert all(k["id"] != key_id for k in other_list.json())

    other_delete = await client.delete(f"{API_KEYS_URL}/{key_id}", headers=auth_headers(admin_token_b))
    assert other_delete.status_code == 404
