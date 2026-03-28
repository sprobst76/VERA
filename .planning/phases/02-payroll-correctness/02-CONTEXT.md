# Phase 2: Payroll Correctness — Context

**Gathered:** 2026-03-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Fix silent wage errors by making all calculation paths read from ContractHistory instead of Employee mirror fields. Plus three cleanup tasks: BW school holidays 2026/27, demo tenant hardening, dead Celery task removal.

No new user-facing features. Backend-only correctness and cleanup.

</domain>

<decisions>
## Implementation Decisions

### Mirror Field Fallback Strategy (DEBT-01)

- **D-01:** When a calculation service finds no ContractHistory row for an employee, use **soft-fail**: skip that employee and return a structured warning. Never raise an unhandled exception, never silently fall back to mirror fields.
- **D-02:** Soft-fail applies uniformly across **all four services**: `payroll_service.py`, `compliance_service.py`, `pdf_service.py`, `reports.py`. Consistent behavior — no service is stricter or more lenient than another.
- **D-03:** The 5 SJ-synced employees (Violeta, Maja, Rita, Nadja, Bärbel) with `hourly_rate=0` and no ContractHistory will be handled **manually by Stefan** before deploy — no automatic migration or placeholder CH entries. The soft-fail behavior means they simply appear as "Kein gültiger Vertrag" in payroll output until their data is entered via the UI.
- **D-04:** Mirror fields on `Employee` (`hourly_rate`, `contract_type`, etc.) remain in the schema for now — they are still synced by `_sync_employee_mirror()` and serve as display-only denormalized cache. The change is that **calculation code must not read them**. Removal of mirror fields is deferred.

### assign_contract_type + create_employee (DEBT-02)

- **D-05:** **Both** the `assign-contract-type` endpoint AND the `create_employee` endpoint must guarantee a ContractHistory entry exists after they run.
  - `assign-contract-type` without `valid_from` → use `date.today()` as default (was already `ContractHistoryCreate` schema requiring `valid_from` — make it optional with today as default).
  - `create_employee` without `start_date` → the existing ContractHistory creation in line 265–270 of `employees.py` already has `valid_from=payload.start_date or date.today()`. Verify this path is correct and covered by a test.
- **D-06:** After this fix, every Employee in the system should have at least one ContractHistory row. The payroll soft-fail (D-01) handles any edge cases.

### Demo Tenant Separation (DEBT-04)

- **D-07:** `seed_demo.py` must always create/use a tenant with `slug="demo"` — it must **never write into any other tenant**. If a tenant with that slug already exists, re-use it (clear + reseed). If not, create fresh.
- **D-08:** No data cleanup needed on the VPS — `seed_demo.py` has not been run in production. This is a preventive hardening, not a bug fix.
- **D-09:** No ENV guard required (Stefan's call was to fix seed_demo.py's tenant targeting, not add deployment guards).

### BW School Holidays 2026/27 (DEBT-03)

- **D-10:** Add `BW_SCHOOL_HOLIDAYS_2026_27` constant to `backend/app/utils/german_holidays.py`. The `is_school_holiday()` function should use the 2026/27 list after 2026-09-12 (when the 2025/26 Sommerferien end). Claude determines exact BW 2026/27 dates from official BW Kultusministerium schedule.
- **D-11:** The `is_school_holiday()` function should auto-select the correct year's list based on the date being checked — no caller changes needed.

### Dead Celery Task Cleanup (INFRA-02)

- **D-12:** `send_hourly_reminders` is already a no-op (`pass`) and is already **not** in the current `beat_schedule` in `celery_app.py`. The cleanup is: remove the function definition from `reminder_tasks.py` and verify no other code references it.
- **D-13:** No Celery Beat DB schedule to clean up — VERA uses code-defined beat schedule, not DB-stored schedules.

### Claude's Discretion

- Exact soft-fail return format (warning dict, None, or raised custom exception caught by caller) — choose whatever integrates cleanest with the existing `PayrollResult` / `ComplianceResult` dataclass patterns.
- Whether to add a `has_valid_contract(employee_id, date)` helper or do inline checks — pick the cleaner pattern.
- BW 2026/27 exact holiday dates — look up official schedule.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Payroll / Calculation Services
- `backend/app/services/payroll_service.py` — current mirror-field fallbacks to remove
- `backend/app/services/compliance_service.py` — reads `employee.contract_type` directly (line 55)
- `backend/app/services/pdf_service.py` — reads `employee.contract_type`, `employee.hourly_rate` (lines 120, 154, 264)
- `backend/app/api/v1/payroll.py` — report endpoint reads mirror fields

### Models / Contracts
- `backend/app/models/employee.py` — mirror fields: `contract_type` (line 24), `hourly_rate` (line 25)
- `backend/app/models/contract_history.py` — SCD Type 2 structure, `valid_from`/`valid_to`
- `backend/app/api/v1/employees.py` — `assign-contract-type` endpoint, `create_employee`, `_sync_employee_mirror()`

### Holidays
- `backend/app/utils/german_holidays.py` — `BW_SCHOOL_HOLIDAYS_2025_26`, `is_school_holiday()` function

### Celery
- `backend/app/tasks/celery_app.py` — current beat_schedule (send_hourly_reminders already absent)
- `backend/app/tasks/reminder_tasks.py` — dead `send_hourly_reminders` function definition

### Demo
- `backend/seed_demo.py` — tenant creation logic to harden

### Requirements
- `.planning/REQUIREMENTS.md` — DEBT-01, DEBT-02, DEBT-03, DEBT-04, INFRA-02 acceptance criteria

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Patterns
- `PayrollResult` / `ComplianceResult` dataclasses: existing return types — soft-fail can add a `missing_contract_warnings: list[str]` field.
- Alembic migration pattern: idempotent `inspect(conn)` check (already established in Phase 1).
- `ContractHistory` SCD Type 2: `valid_to=None` = current. Query pattern in `payroll_service._get_contracts_for_month()` is the reference implementation.

### Key Observation: payroll_service Already Partially Correct
`payroll_service.py` already queries ContractHistory correctly. The problem is the `else float(employee.hourly_rate)` fallbacks when no CH row is found. Removing those fallbacks + adding soft-fail warnings is the core of DEBT-01 for this service.

### assign_contract_type Schema Fix
`ContractHistoryCreate` in `employees.py` line 25 has `valid_from: date` as required. Making it `Optional[date] = None` with `valid_from = payload.valid_from or date.today()` is the fix.

</code_context>

<specifics>
## Specifics

- Soft-fail warning format should include employee name/ID and the period that had no contract, so Stefan can identify which employees need data entry.
- BW Schulferien 2026/27: Claude must look up the official schedule — do not guess dates.
- The `send_hourly_reminders` cleanup is minor — remove dead code, add a test that the beat schedule doesn't reference it.

</specifics>
