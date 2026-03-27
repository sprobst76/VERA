---
phase: 01-security-foundation-deploy-fix
plan: 03
subsystem: infra
tags: [cors, fastapi, github-actions, docker-compose, alembic, deploy]

# Dependency graph
requires: []
provides:
  - CORS middleware allows X-API-Key header for browser-based API key requests
  - Deploy script runs alembic migrations before vera-api starts (no race window)
  - Health-check loop replaces blind sleep in deploy
  - CORS test suite covering preflight for X-API-Key and Authorization headers
affects: [all phases using API key auth, all future deploy runs]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Migration-before-start: run alembic in one-shot container (run --rm) before API service starts"
    - "Deterministic readiness: pg_isready loop + API health check loop instead of sleep"

key-files:
  created:
    - backend/tests/test_cors.py
  modified:
    - backend/app/main.py
    - .github/workflows/deploy.yml

key-decisions:
  - "Health endpoint is /health (not /api/v1/health) — verified in main.py before writing deploy script"
  - "Frontend NEXT_PUBLIC_* env vars contain no secrets (only NEXT_PUBLIC_API_URL and NEXT_PUBLIC_DEMO_SLUG)"
  - "Used run --rm --no-deps vera-api for migration container so it uses same image/env but terminates after migration"

patterns-established:
  - "CORS: always include X-API-Key in allow_headers alongside Authorization"
  - "Deploy: migrations always run in one-shot container before service start"

requirements-completed: [SEC-04, INFRA-01]

# Metrics
duration: 2min
completed: 2026-03-27
---

# Phase 01 Plan 03: CORS X-API-Key Fix + Deploy Race Fix Summary

**CORS middleware extended with X-API-Key header, deploy script rewritten to run alembic in one-shot container before API starts, eliminating migration race window**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-27T13:48:48Z
- **Completed:** 2026-03-27T13:50:15Z
- **Tasks:** 2 of 2
- **Files modified:** 3

## Accomplishments
- Added `X-API-Key` to CORS `allow_headers` — browser-based API key callers no longer fail preflight
- Created `backend/tests/test_cors.py` with 2 tests covering X-API-Key and Authorization preflight (TDD: RED then GREEN)
- Rewrote deploy script: alembic now runs in one-shot container before `vera-api` starts, eliminating the window where requests could hit an un-migrated schema
- Replaced `sleep 5` with `pg_isready` loop for deterministic DB readiness and API health check loop for deterministic API readiness
- Verified frontend NEXT_PUBLIC_* vars contain no secrets (only `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_DEMO_SLUG`)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add X-API-Key to CORS allow_headers + CORS tests** - `1dc6888` (feat)
2. **Task 2: Fix deploy race — run alembic before API starts** - `e25757a` (fix)

**Plan metadata:** (docs commit follows)

_Note: Task 1 used TDD — tests written first (RED: 1 fail), then main.py fixed (GREEN: 2 pass)_

## Files Created/Modified
- `backend/app/main.py` — Added `X-API-Key` to `allow_headers` list in CORSMiddleware
- `backend/tests/test_cors.py` — New test file with 2 CORS preflight tests
- `.github/workflows/deploy.yml` — Rewritten deploy script with migration-before-start pattern and health check loops

## Decisions Made
- Health endpoint used for readiness check is `/health` (confirmed from main.py) not `/api/v1/health`
- Frontend env vars are safe: deploy.yml build-args confirmed to only pass `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_DEMO_SLUG`
- Used `run --rm --no-deps vera-api` for migration container (same image and env vars as the API service, auto-cleaned up after completion)

## Deviations from Plan

None - plan executed exactly as written. The health endpoint path (`/health` vs `/api/v1/health`) was noted in the plan as a point to verify, confirmed by reading main.py.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- CORS fix is live: browser-based API key requests will pass preflight after next deploy
- Deploy race condition eliminated: future deploys run migrations deterministically before API accepts requests
- Shiftjuggler API key scope verification (noted in STATE.md blockers) should still be confirmed before SEC-01 scope enforcement deploys in a later plan

---
*Phase: 01-security-foundation-deploy-fix*
*Completed: 2026-03-27*
