---
phase: 02-payroll-correctness
plan: "01"
subsystem: backend-services
tags: [payroll, compliance, contract-history, debt-reduction, DEBT-01]
requirements: [DEBT-01]

dependency_graph:
  requires:
    - backend/app/models/contract_history.py (ContractHistory SCD Type 2 model)
    - backend/app/models/payroll.py (PayrollEntry.notes field for soft-fail)
  provides:
    - payroll_service.py exclusively reads from ContractHistory (no mirror fields)
    - compliance_service.py reads contract_type from ContractHistory at shift.date
    - structured soft-fail warnings when no ContractHistory row exists
  affects:
    - backend/app/api/v1/payroll.py (calls calculate_monthly_payroll)
    - backend/app/api/v1/shifts.py (calls check_shift via compliance_service)

tech_stack:
  added: []
  patterns:
    - SCD Type 2 ContractHistory lookup (_get_contract_at with valid_from/valid_to range)
    - Soft-fail with structured JSON warning in PayrollEntry.notes
    - Early-return pattern for missing-contract case (avoid cascading None checks)

key_files:
  modified:
    - backend/app/services/payroll_service.py
    - backend/app/services/compliance_service.py
    - backend/tests/test_payroll_service.py
    - backend/tests/test_compliance_service.py

decisions:
  - id: D-01
    summary: "Soft-fail for missing ContractHistory in payroll_service: return PayrollEntry with total_gross=0 and warning in notes JSON, not an exception"
    rationale: "Upstream callers (API layer) must handle all employees even if data is incomplete. Silent error (exception) would break month-end batch runs."
  - id: D-02
    summary: "Existing tests updated to create ContractHistory rows — no Employee mirror field reliance in test setup"
    rationale: "Tests that relied on Employee.hourly_rate being read were passing for wrong reasons. Correcting test setup makes intent explicit and catches regressions."
  - id: D-03
    summary: "compliance_service uses getattr fallback for employee.first_name in warning message"
    rationale: "Existing tests pass SimpleNamespace stubs without first_name/last_name. Rather than breaking backward compat, graceful fallback to employee.id."

metrics:
  duration_minutes: 63
  completed_date: "2026-03-28"
  tasks_completed: 2
  files_modified: 4
---

# Phase 02 Plan 01: Remove Mirror Field Fallbacks from Payroll + Compliance Services Summary

**One-liner:** Eliminate all Employee mirror field reads from payroll_service and compliance_service, replacing with ContractHistory SCD Type 2 lookups and structured soft-fail warnings.

## What Was Done

### Task 1: payroll_service.py — Mirror Field Removal + Soft-Fail

Removed six mirror field fallback patterns from `calculate_monthly_payroll()`:

| Removed | Replacement |
|---------|-------------|
| `else float(employee.monthly_salary)` | `else None` |
| `else float(employee.hourly_rate)` | `else 0.0` (caught by soft-fail above) |
| `else float(employee.monthly_hours_limit)` | `else None` |
| `else float(employee.annual_salary_limit or 6672)` | `else 6672.0` (constant default) |
| `else float(employee.annual_hours_target)` | `else None` |
| `float(employee.weekly_hours)` fallback in `_effective_surcharge_rate` | `else None` |
| `float(employee.annual_hours_target)` fallback in `_effective_surcharge_rate` | `else None` |

Added early-return soft-fail: when `contract_periods` is empty, returns a `PayrollEntry` with `total_gross=0, actual_hours=0, base_wage=0` and a warning stored in `notes` as JSON:
```json
{"missing_contract_warnings": ["Kein gueltiger Vertrag fuer ... im Zeitraum ..."]}
```

Removed dead code: the `if not contract_periods` branch inside the `if primary_monthly_salary` block (now unreachable because empty contract_periods returns early).

Updated 7 existing integration tests to create `ContractHistory` rows (previously they relied on Employee mirror fields being read, which masked test intent).

### Task 2: compliance_service.py — Mirror Field Removal + _get_contract_at

Added `_get_contract_at()` helper method with identical SCD Type 2 query pattern:

```python
async def _get_contract_at(self, employee_id: uuid.UUID, target_date: date):
    from app.models.contract_history import ContractHistory
    result = await self.db.execute(
        select(ContractHistory).where(
            ContractHistory.employee_id == employee_id,
            ContractHistory.valid_from <= target_date,
            or_(ContractHistory.valid_to.is_(None), ContractHistory.valid_to > target_date),
        ).limit(1)
    )
    return result.scalar_one_or_none()
```

Replaced `employee.contract_type == "minijob"` check in `check_shift()` with ContractHistory lookup at `shift.date`. Added soft-fail warning when no contract exists.

Added `import uuid` and `or_` import at module level.

## Test Results

```
tests/test_payroll_service.py: 21 passed (9 original + 3 new + 7 updated)
tests/test_compliance_service.py: 11 passed (9 original + 2 new)
Full suite: 293 passed
```

## Verification

```bash
# Zero mirror field reads
grep -n "employee\.(hourly_rate|contract_type|monthly_salary|weekly_hours|annual_hours_target|annual_salary_limit|monthly_hours_limit)" \
  app/services/payroll_service.py app/services/compliance_service.py
# → (empty — PASS)

# Soft-fail warnings present in both services
grep -n "Kein gueltiger Vertrag" app/services/payroll_service.py app/services/compliance_service.py
# payroll_service.py:152: ...
# compliance_service.py:72: ...
```

## Commits

| Hash | Message |
|------|---------|
| `739b45b` | test(02-01): add failing tests for payroll ContractHistory-only reads (DEBT-01) |
| `b90cc15` | feat(02-01): remove mirror field fallbacks from payroll_service + add soft-fail (DEBT-01) |
| `0ebe527` | test(02-01): add failing tests for compliance ContractHistory reads (DEBT-01) |
| `4c7f2d3` | feat(02-01): remove mirror field read from compliance_service + add _get_contract_at (DEBT-01) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] Update existing tests to create ContractHistory rows**
- **Found during:** Task 1 GREEN phase
- **Issue:** 7 existing payroll tests created Employee with mirror fields (hourly_rate, monthly_salary, etc.) but no ContractHistory. After removing fallbacks they triggered the soft-fail path, returning zero gross instead of testing the actual calculation logic.
- **Fix:** Added `ContractHistory` rows to each affected test with the same values the Employee mirror fields had, making the tests exercise the real calculation path.
- **Files modified:** `backend/tests/test_payroll_service.py`
- **Commit:** `b90cc15`

**2. [Rule 1 - Bug] Use getattr for employee name in compliance_service warning**
- **Found during:** Task 2 GREEN phase
- **Issue:** Existing tests pass `SimpleNamespace(id=emp_id, contract_type="full_time")` without `first_name`/`last_name`. New soft-fail warning accessed `employee.first_name` directly → `AttributeError`.
- **Fix:** Changed to `getattr(employee, 'first_name', '')` with fallback to `employee.id`.
- **Files modified:** `backend/app/services/compliance_service.py`
- **Commit:** `4c7f2d3`

## Known Stubs

None — all calculations now read live data from ContractHistory.

## Self-Check: PASSED
