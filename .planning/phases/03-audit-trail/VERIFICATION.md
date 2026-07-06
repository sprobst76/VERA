---
phase: 03-audit-trail
verified: 2026-07-06
status: passed
score: 5/5 success criteria verified
verified_commit: 7392ab7 (includes merge 1477409)
test_evidence:
  backend: "338 passed, 1 skipped (full suite, re-run by verifier 2026-07-06, 55s)"
  audit_suite: "16/16 passed (tests/test_audit.py, re-run by verifier 2026-07-06)"
  frontend: "61 tests pass, tsc clean (per 03-03-SUMMARY.md)"
  visual: "Playwright, 16 checks passed 2026-07-06 (03-03-SUMMARY.md)"
human_verification:
  - test: "After next production deploy: as app DB user 'vera', run UPDATE/DELETE on audit_log on the VPS Postgres"
    expected: "Both statements fail with 'permission denied for table audit_log'"
    why_human: "REVOKE is PostgreSQL-only (dialect guard); test suite runs on SQLite and cannot exercise it"
---

# Phase 3: Audit-Trail — Verification Report

**Phase Goal:** Every write operation on payroll, shifts, employees, and absences leaves an immutable, queryable record.
**Verified:** 2026-07-06 (goal-backward, code-level, tests re-run by verifier)
**Status:** passed (1 production-verification item, non-blocking)

## Success Criteria

| # | Criterion | Status | Evidence |
|---|-----------|--------|----------|
| 1 | Create/edit/delete on Shift, Employee, PayrollEntry, ContractHistory, EmployeeAbsence produces an AuditLog row in the same transaction | VERIFIED | `audit_service.write()` stages the row in the caller's session without committing (`backend/app/services/audit_service.py:22-48`). Wired at 20 call sites: `shifts.py` 7x (lines 153, 272, 327, 367, 428, 477, 506 — create/bulk/update/delete/confirm/claim/correction), `employees.py` 6x (lines 281, 332, 433, 505, 576, 772 — incl. contract_history via contracts + assign-contract-type; deactivate audited as `delete`), `payroll.py` 5x (lines 116/120, 196/202, 391 — single + bulk calculate), `absences.py` 2x (lines 83, 145 — create + update; no employee-absence DELETE endpoint exists). Endpoint-level tests pass: `test_shift_create/delete`, `test_employee_create/update`, `test_payroll_calculate`, `test_absence_create`, `test_contract_history_create` (`backend/tests/test_audit.py:147-451`). |
| 2 | Rolled-back mutation produces no orphan AuditLog row | VERIFIED | By construction: `write()` only does `db.add()`, caller owns commit (`audit_service.py:48`). Tests: `test_rollback_no_orphan_audit_row` (`test_audit.py:455-476`) and `test_audit_service_no_commit_without_caller` (`test_audit.py:88-107`) — both pass. |
| 3 | UPDATE/DELETE revoked from audit_log for app DB user (PostgreSQL-only, dialect guard) | VERIFIED (code) / PENDING (production) | Migration `k5l6m7n8o9p0` (`backend/alembic/versions/k5l6m7n8o9p0_audit_log_indexes_and_revoke.py:45-46`): `if conn.dialect.name == "postgresql": REVOKE UPDATE, DELETE ON audit_log FROM vera`. Role name matches the production DB user (`deploy/docker-compose.yml:10,52` — `postgresql+asyncpg://vera:...`). Migration is idempotent (Inspector checks), downgrade re-grants, and it is the single alembic head (verified programmatically: heads = `['k5l6m7n8o9p0']`). SQLite skip covered by `test_revoke_migration_sqlite_skip` (`test_audit.py:129-142`). **Not runtime-verifiable locally** — see human_verification. |
| 4 | Admin can open Audit Log page, filter by entity type and date range, see paginated results | VERIFIED | Backend: `GET /api/v1/audit-log` is `AdminUser`-only, tenant-scoped, supports `entity_type`/`from_date`/`to_date`/`limit`/`offset`, returns `{items, total}` (`backend/app/api/v1/audit_log.py:17-52`), registered in `main.py:79`. Tests: pagination, filters, 403 for employee token (`test_audit.py:481-539`) — pass. Frontend: `frontend/src/app/(dashboard)/audit-log/page.tsx` (468 lines, substantive): admin RBAC guard (line 108), filters wired into query params (lines 131-135), pagination (lines 156-157), TanStack Query via `auditLogApi` (`src/lib/api.ts:392-399`). Nav entry `adminOnly: true` (`(dashboard)/layout.tsx:42`). Visual verification via Playwright 2026-07-06: 16 checks passed (sidebar entry, columns, entity+date filters, pagination 56 entries/2 pages, diff expansion, employee RBAC guard — 03-03-SUMMARY.md). |
| 5 | Payroll audit entries include before/after values for actual_hours, base_wage, total_gross | VERIFIED | `PAYROLL_AUDIT_FIELDS = ("actual_hours", "base_wage", "total_gross")` (`payroll.py:25`); old values captured from existing entry before delete, new values after recalculation, written as `old_values`/`new_values` with `action="update"` (`payroll.py:100-122`, bulk: 180-206). Test `test_payroll_audit_before_after_fields` asserts all three keys present in both dicts (`test_audit.py:324-367`) — passes. Frontend renders the payroll before/after diff for exactly these fields (`audit-log/page.tsx:387-396`). |

## Goal-Backward Trace

- **Truth "record exists per mutation":** wiring verified at all 20 call sites (not just service existence); endpoint-level tests exercise the real HTTP paths and query the DB afterward — no stub pattern found.
- **Truth "same transaction / no orphans":** service deliberately does not commit; rollback tests prove atomicity.
- **Truth "immutable":** DB-level REVOKE (PostgreSQL); no UPDATE/DELETE route on audit_log exists in the API (read-only `GET` router).
- **Truth "queryable":** composite indexes `(tenant_id, entity_type, entity_id)` and `(tenant_id, created_at)` created idempotently in migration; admin API + UI page consume them.
- **Data flow (Level 4):** UI page → `auditLogApi.list` → `GET /audit-log` → real `select(AuditLog)` with tenant filter → rendered rows with diff expansion. No hardcoded/static data.

## Test Evidence (re-run by verifier, not taken from SUMMARY)

- `tests/test_audit.py`: **16 passed** (2026-07-06)
- Full backend suite: **338 passed, 1 skipped** (2026-07-06, 55s)
- Frontend: 61 tests pass, `tsc` clean (03-03-SUMMARY.md)
- Merge commit `1477409` confirmed ancestor of HEAD (`7392ab7`)

## Gaps / Risks

No blocking gaps. Notable items:

1. **Production verification pending (criterion 3):** The REVOKE only runs on PostgreSQL; the test suite (SQLite) can only verify the dialect guard. **TODO after next deploy:** on the VPS, connect as `vera` and confirm `UPDATE audit_log SET action='x'` and `DELETE FROM audit_log` both fail with permission denied, and that `alembic upgrade head` applied `k5l6m7n8o9p0`.
2. **Owner-can-re-grant (info):** The `vera` role owns the table (created via `create_tables()`), so it can re-`GRANT` itself UPDATE/DELETE. The REVOKE is effective defense-in-depth against application bugs, not tamper-proofing against a compromised DB account. Acceptable for the phase goal as scoped.
3. **CareRecipientAbsence not audited (info):** `delete_care_absence` (`absences.py:225`) writes no audit row. Out of scope — success criterion names `EmployeeAbsence` only, which has no delete endpoint.
4. **Employee hard-delete does not exist (info):** deactivation is audited as `action="delete"` (`employees.py:772`) — consistent with the soft-delete model.

---

_Verified: 2026-07-06_
_Verifier: Claude (gsd-verifier), goal-backward method_
