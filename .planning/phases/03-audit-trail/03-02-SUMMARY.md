---
phase: 03-audit-trail
plan: 02
subsystem: api
tags: [audit, fastapi, sqlalchemy, pytest, shifts, employees, payroll, absences]

# Dependency graph
requires:
  - phase: 03-audit-trail
    plan: 01
    provides: "audit_service.write() helper, AuditLog model, test scaffolds"
provides:
  - "Every write endpoint for Shift, Employee, ContractHistory, PayrollEntry, EmployeeAbsence calls audit_service.write() in-transaction"
  - "PAYROLL_AUDIT_FIELDS constant for actual_hours/base_wage/total_gross before/after snapshots"
  - "9 previously-skipped endpoint-wiring audit tests all passing green"
affects: [03-03]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "audit_service.write() called after db.flush() (to get entity.id) but before db.commit() — audit and data are atomic"
    - "Old values captured before mutation, new values captured after setattr loop — consistent diff pattern"
    - "PAYROLL_AUDIT_FIELDS tuple defines the before/after fields for payroll audit entries"
    - "calculate_payroll: old entry deleted, old values captured first, new entry flushed, then audit written"

key-files:
  created: []
  modified:
    - backend/app/api/v1/shifts.py
    - backend/app/api/v1/employees.py
    - backend/app/api/v1/payroll.py
    - backend/app/api/v1/absences.py
    - backend/tests/test_audit.py

key-decisions:
  - "Audit on delete_shift: audit row written BEFORE db.delete(shift) so entity data is still accessible for old_values"
  - "Payroll calculate_payroll: old entry deleted with flush before new entry created — old_values captured from existing before delete, new_values captured from new entry after flush"
  - "update_absence: audit write placed BEFORE the mid-function commit (not after notification block) per atomicity requirement"
  - "shifts.py: _write_audit local helper removed entirely, replaced by audit_service.write() with explicit entity_type='shift'"

patterns-established:
  - "delete endpoints: capture old_values dict before db.delete(), write audit, then delete — ensures data available for snapshot"
  - "create endpoints: db.flush() first to get UUID, then audit_service.write(), then db.commit()"
  - "update endpoints: capture old_values before setattr loop, capture new_values after, write audit before commit"

requirements-completed: [AUDIT-02, AUDIT-03]

# Metrics
duration: 25min
completed: 2026-03-28
---

# Phase 3 Plan 02: Audit Wiring Summary

**audit_service.write() wired into all five entity types (shift, employee, contract_history, payroll, absence) with PAYROLL_AUDIT_FIELDS before/after snapshots; 9 endpoint-wiring tests passing**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-03-28T11:50:00Z
- **Completed:** 2026-03-28T12:15:00Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- `shifts.py`: local `_write_audit` helper removed, replaced with `audit_service.write(entity_type="shift", ...)` at 7 call sites; create and delete endpoints wired for the first time
- `employees.py`: audit on create_employee, update_employee (with old/new diff), deactivate_employee (action="delete"), add_contract, update_contract, delete_contract
- `payroll.py`: `PAYROLL_AUDIT_FIELDS = ("actual_hours", "base_wage", "total_gross")` constant; calculate_payroll distinguishes create vs update audit by checking for existing draft; update_payroll_entry captures before/after for the three fields
- `absences.py`: audit on create_absence and update_absence (placed before mid-function commit)
- All 9 previously-skipped endpoint-wiring tests pass; full 336-test suite green

## Task Commits

1. **Task 1: Wire audit_service.write() into shifts.py (create + delete) and remove _write_audit** - `c659e91` (feat)
2. **Task 2: Wire audit into employees.py, payroll.py, absences.py and unskip all tests** - `fc1b52d` (feat)

## Files Created/Modified

- `backend/app/api/v1/shifts.py` - Removed `_write_audit` helper; added audit_service import; wired create + delete; refactored update/confirm/claim/time-correction calls
- `backend/app/api/v1/employees.py` - Added audit_service import; wired create, update, delete (deactivate), add_contract, update_contract, delete_contract
- `backend/app/api/v1/payroll.py` - Added audit_service import + PAYROLL_AUDIT_FIELDS; wired calculate_payroll, calculate_all_payroll, update_payroll_entry
- `backend/app/api/v1/absences.py` - Added audit_service import; wired create_absence + update_absence
- `backend/tests/test_audit.py` - Removed 9 skip decorators; fixed test fixtures (contract_type, tenant_id capture, correct schema field names, correct payload formats)

## Decisions Made

- Audit write in `delete_shift` is staged BEFORE `db.delete(shift)` — the shift object must still be accessible for capturing old_values. The audit row is staged in the same transaction, so if commit fails, both the delete and audit are rolled back.
- `calculate_payroll` distinguishes create vs update by checking `existing_old_values is not None` (which is set only when a draft was found and deleted). This produces `action="create"` on first calculation and `action="update"` on recalculation, fulfilling AUDIT-03.
- `update_absence` atomicity trap documented in plan: the audit write goes before `await db.commit()` (line ~135 in absences.py), not after the notification dispatch block at the end of the function.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test Employee fixtures missing required contract_type field**
- **Found during:** Task 2 (running tests after unskipping)
- **Issue:** All 7 Employee objects created inline in tests omitted `contract_type`, which has a `NOT NULL` constraint — caused `IntegrityError` on every fixture insert
- **Fix:** Added `contract_type="minijob"` to all 7 inline Employee fixture objects in test_audit.py
- **Files modified:** `backend/tests/test_audit.py`
- **Verification:** All Employee inserts succeed; no IntegrityError in test run
- **Committed in:** `fc1b52d` (Task 2 commit)

**2. [Rule 1 - Bug] Fixed MissingGreenlet on tenant.id access after db.expire_all()**
- **Found during:** Task 2 (running tests, second wave of failures)
- **Issue:** Tests called `db.expire_all()` then used `tenant.id` and `admin_user.id` in subsequent queries — this triggers lazy-load on expired ORM objects outside an async greenlet context, raising `MissingGreenlet`
- **Fix:** Added `tenant_id = tenant.id` (and `user_id = admin_user.id` where needed) before `db.expire_all()` in all affected tests; replaced `tenant.id` with the captured scalar in filter conditions
- **Files modified:** `backend/tests/test_audit.py`
- **Verification:** No MissingGreenlet errors; all post-expire_all queries succeed
- **Committed in:** `fc1b52d` (Task 2 commit)

**3. [Rule 1 - Bug] Fixed incorrect test payload field names and formats**
- **Found during:** Task 2 (running tests, third wave of failures — 422 Unprocessable Entity)
- **Issue 1:** `test_absence_create_produces_audit_row` used `"absence_type"` but the Pydantic schema field is `"type"`
- **Issue 2:** `test_employee_create_produces_audit_row` payload missing required `contract_type` field (EmployeeCreate requires it)
- **Issue 3:** `test_payroll_*` tests sent `{"year": 2026, "month": 3}` but `PayrollCalculateRequest.month` is a `date` field requiring ISO format `"2026-03-01"`
- **Issue 4:** `test_contract_history_create_produces_audit_row` used unknown field `"monthly_limit"` (correct field: `"monthly_hours_limit"`)
- **Fix:** Corrected all field names and value formats in test payloads
- **Files modified:** `backend/tests/test_audit.py`
- **Verification:** All 9 endpoint-wiring tests return 200/201; no 422 responses
- **Committed in:** `fc1b52d` (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (all Rule 1 — bugs in test scaffolds from Plan 01)
**Impact on plan:** All auto-fixes corrected pre-existing test scaffold issues. No scope creep. The endpoint wiring code itself worked correctly on first attempt.

## Issues Encountered

None beyond the auto-fixed test scaffold issues above.

## Known Stubs

None — this plan wires audit logging into existing endpoints. No UI-rendering data flows involved.

## Next Phase Readiness

- Plan 03 can now implement `GET /api/v1/audit-log` using the `AuditLogOut` and `AuditLogPageOut` schemas from Plan 01
- Plan 03 should unskip the 3 remaining API tests in `test_audit.py` (`test_audit_log_api_pagination`, `test_audit_log_api_filters`, `test_audit_log_api_admin_only`)
- All five entity types (shift, employee, contract_history, payroll, absence) now produce AuditLog rows atomically with their data mutations

---
*Phase: 03-audit-trail*
*Completed: 2026-03-28*
