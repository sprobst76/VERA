---
phase: 01-security-foundation-deploy-fix
verified: 2026-03-27T14:07:57Z
status: passed
score: 5/5 must-haves verified
re_verification: false
---

# Phase 1: Security Foundation + Deploy Fix — Verification Report

**Phase Goal:** Production system deploys safely and enforces the security boundaries it advertises
**Verified:** 2026-03-27T14:07:57Z
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | python-jose CVE-2024-33663 is gone — PyJWT 2.12+ and direct bcrypt are in requirements.txt, all tests pass | VERIFIED | `requirements.txt` line 10: `PyJWT>=2.12,<3.0`; no `python-jose` or `passlib` entries; 288 tests pass |
| 2 | Deploying a schema-changing migration no longer produces 500 errors — migration runs before API container accepts traffic | VERIFIED | `deploy.yml` line 172: `run --rm --no-deps vera-api alembic upgrade head` executes before line 176: `up -d --no-deps vera-api`; `pg_isready` loop ensures DB is ready |
| 3 | A read-only API key cannot execute a write operation — POST /shifts with a read-scoped key returns 403; GET /shifts succeeds | VERIFIED | `deps.py` lines 56–63: scope enforcement with `"API-Key hat keine Schreibberechtigung"` detail; `test_api_key_read_scope_blocks_write` and `test_api_key_read_scope_allows_get` both pass |
| 4 | Logging out of all devices works — after POST /auth/logout-all, all existing refresh tokens are rejected on next use | VERIFIED | `auth.py` lines 140–144: `logout_all` endpoint increments `token_version`; `deps.py` lines 99–102: `token_ver != user.token_version` raises 401; `test_logout_all_invalidates_tokens` passes |
| 5 | CORS allows X-API-Key header — browser-based API key requests pass preflight without error | VERIFIED | `main.py` line 53: `allow_headers=["Authorization", "Content-Type", "X-API-Key"]`; `test_cors_allows_x_api_key_header` passes |

**Score:** 5/5 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/core/security.py` | JWT encode/decode via PyJWT, password hash/verify via direct bcrypt | VERIFIED | `import jwt` (line 6), `import bcrypt` (line 5), `bcrypt.hashpw`/`bcrypt.checkpw`, `jwt.PyJWTError` in except, `"ver": token_version` in payload |
| `backend/requirements.txt` | Updated dependencies without python-jose or passlib | VERIFIED | `PyJWT>=2.12,<3.0` present; `bcrypt==4.0.1` present; no python-jose or passlib |
| `backend/tests/test_security.py` | Unit tests for security.py functions | VERIFIED | 8 tests including `test_passlib_bcrypt_compat`, `test_decode_tampered_token`, `test_create_access_token_has_expected_claims`; all pass |
| `backend/app/models/user.py` | User model with token_version column | VERIFIED | Line 20: `token_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)` |
| `backend/app/api/deps.py` | get_current_user with token_version check and scope enforcement | VERIFIED | `token_ver = payload.get("ver", 0)`, `request.method.upper() in ("POST", "PUT", "PATCH", "DELETE")`, `"API-Key hat keine Schreibberechtigung"` |
| `backend/app/api/v1/auth.py` | logout-all endpoint and change-password token revocation | VERIFIED | `@router.post("/logout-all")` at line 140; `token_version += 1` in both logout-all and change-password |
| `backend/alembic/versions/j4k5l6m7n8o9_add_token_version.py` | Idempotent migration adding token_version column | VERIFIED | Uses `Inspector.from_engine`, `down_revision = "i3j4k5l6m7n8"`, `server_default="0"` |
| `backend/app/main.py` | CORS middleware with X-API-Key in allow_headers | VERIFIED | Line 53: `allow_headers=["Authorization", "Content-Type", "X-API-Key"]` |
| `.github/workflows/deploy.yml` | Fixed deploy script with migration-before-start pattern | VERIFIED | `pg_isready` loop, `run --rm --no-deps vera-api alembic upgrade head` before `up -d --no-deps vera-api`, no `sleep 5` |
| `backend/tests/test_cors.py` | CORS header verification test | VERIFIED | `test_cors_allows_x_api_key_header` and `test_cors_allows_authorization_header` both pass |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `security.py` | `jwt (PyJWT)` | `import jwt; jwt.encode / jwt.decode` | WIRED | `import jwt` line 6; `jwt.encode(...)` and `jwt.decode(...)` in use; `jwt.PyJWTError` in except |
| `security.py` | `bcrypt` | `import bcrypt; bcrypt.hashpw / bcrypt.checkpw` | WIRED | `import bcrypt` line 5; `bcrypt.hashpw(...)` and `bcrypt.checkpw(...)` used in hash_password and verify_password |
| `security.py` | `deps.py` | `ver claim in access token; deps checks ver against user.token_version` | WIRED | `"ver": token_version` in create_access_token payload; `token_ver = payload.get("ver", 0)` and `token_ver != user.token_version` in deps.py |
| `auth.py` | `user.token_version` | `logout-all and change-password increment token_version` | WIRED | `current_user.token_version += 1` present in both endpoints |
| `deps.py` | `fastapi.Request` | `request.method checked for API key scope enforcement` | WIRED | `request: Request` first parameter; `request.method.upper() in ("POST", "PUT", "PATCH", "DELETE")` |
| `deploy.yml` | `alembic upgrade head` | `docker compose run --rm before docker compose up vera-api` | WIRED | Line 172 (`run --rm` migration) precedes line 176 (`up -d vera-api`); explicit `set -e` ensures failure stops deploy |
| `main.py` | `CORS middleware` | `allow_headers list includes X-API-Key` | WIRED | `allow_headers=["Authorization", "Content-Type", "X-API-Key"]` |

---

### Data-Flow Trace (Level 4)

Not applicable — this phase produces auth/security enforcement logic, not data-rendering components. All critical behaviors verified via test execution.

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Security tests (bcrypt, JWT, tamper detection) | `pytest tests/test_security.py tests/test_cors.py -q` | 10 passed | PASS |
| Token revocation and scope enforcement | `pytest tests/test_auth.py -k "logout_all or token_version or api_key or change_password_revokes or missing_ver" -q` | 10 passed | PASS |
| Full test suite regression check | `pytest tests/ -q` | 288 passed, 0 failed | PASS |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| SEC-06 | 01-01-PLAN.md | `python-jose` replaced by PyJWT 2.12+ (CVE-2024-33663 eliminated) | SATISFIED | `PyJWT>=2.12,<3.0` in requirements.txt; `import jwt` in security.py; no python-jose |
| SEC-05 | 01-02-PLAN.md | JWT revocation via `token_version` — logout-all and password change invalidate all sessions | SATISFIED | `token_version` on User model; `ver` claim in JWT; check in deps.py; logout-all endpoint; test_logout_all_invalidates_tokens passes |
| SEC-01 | 01-02-PLAN.md | API key scopes enforced — read-only key blocked from write operations | SATISFIED | Scope check in deps.py lines 56–63; test_api_key_read_scope_blocks_write passes (403); test_api_key_read_scope_allows_get passes (200) |
| SEC-04 | 01-03-PLAN.md | CORS allows X-API-Key header; no secrets in frontend NEXT_PUBLIC vars | SATISFIED | `X-API-Key` in `allow_headers`; deploy.yml only passes `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_DEMO_SLUG` as build-args |
| INFRA-01 | 01-03-PLAN.md | Deploy order fixed — alembic runs before API starts, no sleep 5 race | SATISFIED | Migration `run --rm` on line 172 before API `up -d` on line 176; `pg_isready` loop replaces sleep; `sleep 5` absent from file |

No orphaned requirements found — all 5 requirement IDs declared in plans and confirmed satisfied.

---

### Anti-Patterns Found

No blockers or warnings found. Scan of modified files:

- `backend/app/core/security.py` — clean implementation, no TODOs, no stubs
- `backend/app/api/deps.py` — scope enforcement has no bypass paths; null scopes intentionally treated as admin (D-14 backward compat, documented in comment)
- `backend/app/api/v1/auth.py` — logout-all and change-password both increment token_version before commit
- `backend/alembic/versions/j4k5l6m7n8o9_add_token_version.py` — idempotent inspect check present
- `.github/workflows/deploy.yml` — `set -e` ensures failure halts deploy; no sleep race

---

### Human Verification Required

None. All success criteria are programmatically verifiable and confirmed by passing tests.

---

## Gaps Summary

No gaps. All 5 observable truths verified, all artifacts substantive and wired, all 5 requirements satisfied, 288 tests pass.

---

_Verified: 2026-03-27T14:07:57Z_
_Verifier: Claude (gsd-verifier)_
