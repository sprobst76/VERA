---
phase: 01-security-foundation-deploy-fix
plan: 01
subsystem: auth
tags: [jwt, bcrypt, pyjwt, security, cve, python-jose, passlib]

# Dependency graph
requires: []
provides:
  - PyJWT-based JWT encode/decode in security.py (no python-jose)
  - Direct bcrypt password hashing/verification (no passlib)
  - Unit test suite for security module with passlib compatibility proof
affects:
  - 01-02 (token_version revocation builds on this security foundation)
  - all phases using auth (JWT decode is unchanged in payload structure)

# Tech tracking
tech-stack:
  added:
    - PyJWT>=2.12,<3.0 (replaces python-jose[cryptography]==3.3.0)
  patterns:
    - Direct bcrypt calls: bcrypt.hashpw/checkpw with explicit encode/decode
    - PyJWT exception: jwt.PyJWTError (replaces JWTError from jose)
    - Token payload structure unchanged: sub, tenant_id, role, exp, type

key-files:
  created:
    - backend/tests/test_security.py
  modified:
    - backend/app/core/security.py
    - backend/requirements.txt

key-decisions:
  - "PyJWT replaces python-jose (CVE-2024-33663 eliminated); same jwt.encode/jwt.decode API"
  - "Direct bcrypt replaces passlib; passlib hash format ($2b$) is compatible with bcrypt.checkpw"
  - "Token payload structure unchanged (sub, tenant_id, role, exp, type) per D-03 — existing tokens remain valid"

patterns-established:
  - "Password hashing: bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')"
  - "Password verify: bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))"
  - "JWT error handling: except jwt.PyJWTError as e: raise ValueError(f'Invalid token: {e}')"

requirements-completed: [SEC-06]

# Metrics
duration: 4min
completed: 2026-03-27
---

# Phase 01 Plan 01: CVE Elimination — python-jose + passlib to PyJWT + bcrypt Summary

**Eliminated CVE-2024-33663 by replacing python-jose with PyJWT 2.12 and removing passlib in favor of direct bcrypt calls, with all 276 backend tests passing**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-27T13:48:41Z
- **Completed:** 2026-03-27T13:52:43Z
- **Tasks:** 2
- **Files modified:** 3 (security.py, requirements.txt, new test_security.py)

## Accomplishments

- Removed python-jose (CVE-2024-33663) and replaced with PyJWT 2.12 — same jwt.encode/jwt.decode API, only exception class changed
- Removed passlib (abandoned dependency) and replaced with direct bcrypt calls — hash format ($2b$) is fully compatible with existing production hashes
- Created 8-test unit test suite for security module including passlib compatibility proof test

## Task Commits

1. **Task 1: Create test_security.py with unit tests for security module + passlib compat test** - `756c0c3` (test)
2. **Task 2: Migrate security.py from python-jose/passlib to PyJWT/bcrypt and update requirements.txt** - `1c79485` (feat)

## Files Created/Modified

- `backend/tests/test_security.py` - 8 unit tests: passlib compat, hash_password, verify_password, create_access_token claims, decode_token valid/tampered/expired
- `backend/app/core/security.py` - Replaced jose/passlib imports with PyJWT/bcrypt; identical function signatures and token payload structure
- `backend/requirements.txt` - python-jose removed, passlib removed, PyJWT>=2.12,<3.0 added, bcrypt==4.0.1 kept as direct dependency

## Decisions Made

- PyJWT chosen as drop-in replacement for python-jose — identical jwt.encode/jwt.decode call signatures, only exception class differs (jwt.PyJWTError vs JWTError)
- Passlib hash format ($2b$) is a standard bcrypt hash; existing production hashes are directly verifiable by bcrypt.checkpw — no migration needed
- Token payload structure intentionally unchanged (D-03): sub, tenant_id, role, exp, type — existing issued tokens remain valid post-deployment

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Worktree had no virtual environment — created fresh venv and installed requirements (prerequisite for test execution, not a code issue)

## Known Stubs

None — security module is fully functional, no placeholders.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Security foundation complete: PyJWT + bcrypt are the canonical auth primitives for all subsequent plans
- Plan 01-02 (token_version JWT revocation) can build directly on this foundation
- All 276 backend tests pass, CI will pass on push

---
*Phase: 01-security-foundation-deploy-fix*
*Completed: 2026-03-27*
