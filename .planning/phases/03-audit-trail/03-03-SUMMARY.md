---
phase: 03-audit-trail
plan: 03
subsystem: api+frontend
tags: [audit, fastapi, nextjs, typescript, pagination, filters, diff]

# Dependency graph
requires:
  - phase: 03-audit-trail
    plan: 01
    provides: "AuditLog model, AuditLogOut/AuditLogPageOut schemas, audit_service.write()"
  - phase: 03-audit-trail
    plan: 02
    provides: "All write endpoints wired with audit_service.write()"
provides:
  - "GET /api/v1/audit-log — admin-only paginated endpoint with entity_type and date range filters"
  - "frontend/src/app/(dashboard)/audit-log/page.tsx — admin-only audit log page"
  - "auditLogApi.list() in frontend/src/lib/api.ts"
  - "Audit-Log nav entry in layout.tsx (adminOnly: true)"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pagination via limit/offset query params; total returned in AuditLogPageOut.total"
    - "Date range filter: from_date >= and to_date < (to_date + 1 day) for inclusive end"
    - "Frontend: TanStack Query with queryKey including all filter state for automatic refetch"
    - "Expand/collapse diff row — accordion (one open at a time) via expandedRow state"
    - "DiffLine component renders field-level before/after for payroll; generic diff for other entity types"

key-files:
  created:
    - backend/app/api/v1/audit_log.py
    - frontend/src/app/(dashboard)/audit-log/page.tsx
  modified:
    - backend/app/main.py
    - backend/tests/test_audit.py
    - frontend/src/lib/api.ts
    - frontend/src/app/(dashboard)/layout.tsx

key-decisions:
  - "Expand button shown for any row with old_values or new_values (not just action=update) — ensures create/delete rows with data can also be inspected"
  - "Payroll diff uses fixed PAYROLL_AUDIT_FIELDS list (actual_hours, base_wage, total_gross); other entities render all changed keys generically"
  - "User lookup via separate /users query; fallback to truncated user_id if not found in map"

requirements-completed: [AUDIT-04]

# Metrics
duration: 20min
completed: 2026-03-28
---

# Phase 3 Plan 03: Audit Log Read Endpoint + Frontend Page Summary

**GET /api/v1/audit-log endpoint with entity_type/date filtering and pagination; admin-only frontend page with action badges, expandable diff rows, and Catppuccin styling**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-03-28T11:58:00Z
- **Completed:** 2026-03-28T12:03:53Z
- **Tasks completed:** 3 of 3 (Task 3 verified 2026-07-06 via automated Playwright walkthrough)
- **Files modified:** 6

## Accomplishments

- `backend/app/api/v1/audit_log.py`: `GET /api/v1/audit-log` endpoint with AdminUser dependency, tenant_id filter, optional entity_type + date range filters, limit/offset pagination, returns `AuditLogPageOut`
- `backend/app/main.py`: `audit_log_router` registered at `/api/v1` prefix
- `backend/tests/test_audit.py`: All 3 remaining `@pytest.mark.skip` decorators removed; `test_audit_log_api_pagination`, `test_audit_log_api_filters`, `test_audit_log_api_admin_only` now pass
- Full backend suite: **339 tests pass**, 0 failures
- `frontend/src/lib/api.ts`: `auditLogApi.list()` added after last export
- `frontend/src/app/(dashboard)/layout.tsx`: `ClipboardList` imported; Audit-Log nav entry added before Settings (`adminOnly: true`, `parentViewerVisible: false`)
- `frontend/src/app/(dashboard)/audit-log/page.tsx`: Full page implementation — entity type select, date range inputs, reset button, results count, paginated table with alternating tint + action badges, expandable diff rows (payroll: DiffLine per PAYROLL_AUDIT_FIELDS; generic: all changed keys), pagination bar, loading/empty/error states, admin access guard
- Frontend tests: **61 tests pass**, TypeScript: **0 errors**

## Task Commits

1. **Task 1: Create GET /api/v1/audit-log endpoint** — `df9bd26`
2. **Task 2: Build frontend audit-log page** — `455c500`

## Files Created/Modified

- `backend/app/api/v1/audit_log.py` — New: admin-only paginated audit log endpoint
- `backend/app/main.py` — Added audit_log_router import + include_router
- `backend/tests/test_audit.py` — Removed 3 skip decorators
- `frontend/src/lib/api.ts` — Added auditLogApi export
- `frontend/src/app/(dashboard)/layout.tsx` — Added ClipboardList + Audit-Log nav entry
- `frontend/src/app/(dashboard)/audit-log/page.tsx` — New: complete audit log page

## Decisions Made

- Expand button shown for any row with `old_values !== null || new_values !== null`, not just `action === "update"`. This ensures rows produced by delete operations (which capture old_values before deletion) can also show their snapshot.
- For non-payroll `update` rows, the diff renders all keys from `{...old_values, ...new_values}` generically. This provides useful output for employee/absence/shift updates without requiring a per-entity-type field whitelist.
- Users are looked up via a separate `/users` query (cached by TanStack Query). Fallback to `user_id.slice(0, 8) + "..."` ensures the table always displays something useful even if the user was deleted.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## Known Stubs

None — all data flows from the API are wired. The `auditLogApi.list()` call fetches real rows from the `audit_log` table populated by Plan 02 endpoint wiring.

## Task 3: Visual Verification — COMPLETED 2026-07-06

The worktree branch `worktree-agent-a715c3c9` (commits df9bd26, 455c500) was merged
to main (merge commit 1477409). Verification ran against the merged state with a
fresh demo seed (SQLite), backend on :31367, frontend dev on :31368, via Playwright
(chromium, 16 automated checks — all passed):

- Audit-Log nav entry (ClipboardList) appears in sidebar for admin ✓
- Page loads with heading + subtitle; columns Zeitpunkt/Benutzer/Aktion/Entität/Details ✓
- Shift create produced an "angelegt" row; 55 updates produced "geändert" rows ✓
- Entity filter "Dienst" narrows results ✓
- Date range Von/Bis narrows results (future date → empty state) ✓
- Pagination: 56 entries, page 2 shows remaining 6, Zurück returns to page 1 ✓
- Diff expansion renders before/after (notes old→new, strikethrough/green) ✓
- Employee login: no Audit-Log nav entry; direct /audit-log shows admin guard ✓

Follow-up fixes made during verification (committed to main):
- `7392ab7` — restored German umlauts in audit-log page UI strings
- `855d975` — fixed 3 date-dependent contract tests + passlib compat guard
  (pre-existing failures unrelated to this phase; would have blocked CI)

Note: timestamps render as UTC in local SQLite dev (naive ISO serialization);
under production Postgres (timezone=True) Pydantic emits +00:00 and the browser
converts correctly.

## Self-Check: PASSED

- FOUND: backend/app/api/v1/audit_log.py
- FOUND: frontend/src/app/(dashboard)/audit-log/page.tsx
- FOUND: commit df9bd26 (Task 1)
- FOUND: commit 455c500 (Task 2)

---
*Phase: 03-audit-trail*
*Completed (auto tasks): 2026-03-28*
