---
phase: 01-security-foundation-deploy-fix
plan: 02
subsystem: auth
tags: [jwt, token-version, revocation, api-keys, scope-enforcement, security]

# Dependency graph
requires:
  - 01-01 (PyJWT + bcrypt foundation)
provides:
  - JWT revocation via token_version column on User
  - POST /auth/logout-all endpoint (invalidates all sessions)
  - change-password increments token_version (revokes all sessions)
  - API key scope enforcement (read/write/admin)
affects:
  - all auth flows (tokens now include 'ver' claim)
  - API key integrations (read-only keys blocked from write operations)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "token_version int column on User; ver claim in JWT payload; mismatch = 401"
    - "API key scope enforcement via request.method in get_current_user"
    - "null/empty API key scopes treated as admin (D-14 backward compat)"

key-files:
  created:
    - backend/alembic/versions/j4k5l6m7n8o9_add_token_version.py
  modified:
    - backend/app/models/user.py
    - backend/app/core/security.py
    - backend/app/api/deps.py
    - backend/app/api/v1/auth.py
    - backend/tests/conftest.py
    - backend/tests/test_auth.py

key-decisions:
  - "token_version default=0 with server_default='0' ensures backward compat with existing sessions (D-04)"
  - "Missing 'ver' claim in JWT treated as 0 — pre-deploy tokens still work for users with token_version=0 (D-06)"
  - "null/empty API key scopes treated as admin scope (D-14 — Shiftjuggler key has no scopes set)"
  - "Request parameter added to get_current_user — FastAPI injects automatically, no existing callers affected"

# Metrics
duration: 5min
completed: 2026-03-27
---

# Phase 01 Plan 02: JWT Revocation + API Key Scope Enforcement Summary

**JWT revocation via token_version column (logout-all + change-password) and API key scope enforcement (read/write/admin) with 288 tests passing**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-27T13:56:26Z
- **Completed:** 2026-03-27T14:01:00Z
- **Tasks:** 3
- **Files modified:** 6 files (user.py, security.py, deps.py, auth.py, conftest.py, test_auth.py) + 1 created (migration)

## Accomplishments

- Added `token_version: int` column to User model with idempotent Alembic migration (down_revision: i3j4k5l6m7n8)
- Updated `create_access_token` and `create_refresh_token` to include `ver` claim matching user.token_version
- Implemented `token_ver` check in `get_current_user` — missing ver treated as 0 for pre-deploy compat (D-06)
- Added `POST /auth/logout-all` endpoint — increments token_version, invalidates all sessions (D-07)
- Updated `change-password` endpoint to increment token_version on password change (D-08)
- Updated `refresh_token` endpoint to validate token_version on refresh tokens
- Implemented API key scope enforcement in `get_current_user` — read-only keys return 403 on write methods (D-10)
- null/empty scopes treated as admin for Shiftjuggler backward compatibility (D-14)
- 12 new tests (5 token revocation + 5 API key scope + fixture) — 288 total pass

## Task Commits

1. **Task 1: token_version model + migration + ver claim in JWTs** - `0c78746` (feat)
2. **Task 2 RED: failing tests for token_version revocation** - `12e623d` (test)
3. **Task 2 GREEN: token_version check, logout-all, change-password revocation** - `4154076` (feat)
4. **Task 3 RED: failing tests for API key scope enforcement** - `47b246e` (test)
5. **Task 3 GREEN: API key scope enforcement in get_current_user** - `e538812` (feat)

## Files Created/Modified

- `backend/alembic/versions/j4k5l6m7n8o9_add_token_version.py` - Idempotent migration adding token_version column with Inspector pattern
- `backend/app/models/user.py` - Added `token_version: Mapped[int]` with `server_default="0"`
- `backend/app/core/security.py` - Added `token_version: int = 0` param and `"ver": token_version` to access/refresh token payloads
- `backend/app/api/deps.py` - Added `request: Request` param, token_ver check after user load, API key scope enforcement
- `backend/app/api/v1/auth.py` - Updated login/refresh/accept-invite to pass token_version; added logout-all endpoint; change-password increments token_version
- `backend/tests/conftest.py` - Updated admin_token/employee_token fixtures to pass token_version
- `backend/tests/test_auth.py` - 12 new tests: token_version_mismatch, logout_all_returns_204, logout_all_invalidates_tokens, change_password_revokes_tokens, missing_ver_claim_treated_as_zero, make_api_key fixture, 5 API key scope tests

## Decisions Made

- token_version default=0 with server_default='0' ensures backward compat (existing DB users get version 0, new tokens get ver=0 claim, check passes)
- Missing 'ver' claim in JWT (pre-deploy tokens) treated as 0 — users with token_version=0 are unaffected post-deploy
- null/empty API key scopes treated as admin scope — Shiftjuggler sync script uses key with no scopes set (D-14)
- Request parameter is first in get_current_user signature — FastAPI injects it automatically, no existing endpoint code changes needed

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Functionality] Added admin_user dependency to API key scope tests**

- **Found during:** Task 3 RED phase
- **Issue:** API key auth path finds the admin user of the tenant to return as context — tests without admin_user fixture had no user to find, causing 403 for all keys including GET
- **Fix:** Added `admin_user` parameter to all 5 API key scope test functions
- **Files modified:** backend/tests/test_auth.py
- **Commit:** 47b246e (squashed into RED test commit)

## Known Stubs

None — all functionality is fully implemented and wired.

## Self-Check

## Self-Check: PASSED

- `backend/alembic/versions/j4k5l6m7n8o9_add_token_version.py` — FOUND
- `backend/app/models/user.py` contains `token_version` — FOUND
- `backend/app/core/security.py` contains `ver` claim — FOUND
- `backend/app/api/deps.py` contains `token_ver` check and `request.method` — FOUND
- `backend/app/api/v1/auth.py` contains `logout-all` endpoint — FOUND
- Commits 0c78746, 12e623d, 4154076, 47b246e, e538812 — all exist
- 288 tests pass (0 failures)
