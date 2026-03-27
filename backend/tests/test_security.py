"""
Unit tests for backend/app/core/security.py

These tests verify:
- Password hashing and verification with bcrypt
- Passlib compatibility (hash format interoperability)
- JWT access token creation and decoding
- Token tampering and expiry detection
"""
import uuid
from datetime import timedelta

import pytest

from app.core.security import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_passlib_bcrypt_compat():
    """A passlib-generated bcrypt hash must verify with bcrypt.checkpw.

    This test validates format compatibility between passlib (the old dependency)
    and direct bcrypt calls (the new approach), confirming that existing
    production hashes created with passlib remain valid after migration.
    """
    from passlib.context import CryptContext
    import bcrypt

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    password = "testpassword123"
    passlib_hash = pwd_context.hash(password)

    # Passlib bcrypt hashes always start with $2b$ (bcrypt format)
    assert passlib_hash.startswith("$2b$"), (
        f"Expected passlib hash to start with '$2b$', got: {passlib_hash[:6]}"
    )

    # Direct bcrypt must be able to verify a passlib-generated hash
    assert bcrypt.checkpw(
        password.encode("utf-8"),
        passlib_hash.encode("utf-8"),
    ), "bcrypt.checkpw failed to verify a passlib-generated hash"


def test_hash_password_returns_bcrypt_string():
    """hash_password should return a $2b$ bcrypt hash string."""
    result = hash_password("test")
    assert isinstance(result, str), "hash_password should return a str"
    assert result.startswith("$2b$"), (
        f"Expected hash to start with '$2b$', got: {result[:6]}"
    )


def test_verify_password_correct():
    """verify_password returns True when the plain password matches the hash."""
    plain = "my_secure_password"
    hashed = hash_password(plain)
    assert verify_password(plain, hashed) is True


def test_verify_password_wrong():
    """verify_password returns False when the plain password does not match."""
    hashed = hash_password("correct_password")
    assert verify_password("wrong_password", hashed) is False


def test_create_access_token_has_expected_claims():
    """create_access_token produces a JWT with sub, tenant_id, role, exp, type='access'."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    role = "admin"

    token = create_access_token(user_id, tenant_id, role)
    payload = decode_token(token)

    assert payload["sub"] == str(user_id), f"Expected sub={user_id}, got {payload.get('sub')}"
    assert payload["tenant_id"] == str(tenant_id), (
        f"Expected tenant_id={tenant_id}, got {payload.get('tenant_id')}"
    )
    assert payload["role"] == role, f"Expected role={role}, got {payload.get('role')}"
    assert payload["type"] == "access", f"Expected type='access', got {payload.get('type')}"
    assert "exp" in payload, "Access token must contain an 'exp' claim"


def test_decode_token_valid():
    """decode_token returns the correct payload dict for a valid token."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()

    token = create_access_token(str(user_id), str(tenant_id), "employee")
    payload = decode_token(token)

    assert payload["sub"] == str(user_id)
    assert payload["tenant_id"] == str(tenant_id)
    assert payload["role"] == "employee"
    assert payload["type"] == "access"


def test_decode_tampered_token():
    """decode_token raises ValueError when the token signature has been tampered with."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()

    token = create_access_token(str(user_id), str(tenant_id), "admin")
    tampered_token = token + "x"

    with pytest.raises(ValueError, match="Invalid token"):
        decode_token(tampered_token)


def test_decode_expired_token():
    """decode_token raises ValueError for a token whose exp is in the past."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()

    # Create a token that expired 1 second ago
    expired_token = create_access_token(
        str(user_id),
        str(tenant_id),
        "admin",
        expires_delta=timedelta(seconds=-1),
    )

    with pytest.raises(ValueError, match="Invalid token"):
        decode_token(expired_token)
