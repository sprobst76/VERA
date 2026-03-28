---
phase: 02-payroll-correctness
verified: 2026-03-28T10:17:50Z
status: passed
score: 4/4 must-haves verified
---

# Phase 2: Payroll Correctness Verification Report

**Phase Goal:** Payroll and compliance calculations read from live ContractHistory — mirror fields cannot cause silent wage errors.
**Verified:** 2026-03-28T10:17:50Z
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Payroll PDF uses the ContractHistory row valid on the shift date — changing `employee.hourly_rate` has no effect on calculation | VERIFIED | `payroll_service.py` reads exclusively from `ContractHistory` via `_get_contracts_for_month()`. Comment on line 178 states "Vertragsdaten ausschließlich aus ContractHistory lesen (keine Employee-Felder)". Test `test_payroll_uses_contract_history_not_mirror` sets `employee.hourly_rate=99€`, `ContractHistory.hourly_rate=15.50€`, asserts `base_wage=124.00€` (8h×15.50), passes. |
| 2 | Calling `assign_contract_type` without `valid_from` creates a ContractHistory entry with `valid_from=today` | VERIFIED | `employees.py` line 627: `mem_from = _date_cls.today()` when `valid_from_raw` is None. Lines 647-678 always create a CH entry with `effective_from`. Test `test_assign_contract_type_no_valid_from_creates_ch` (line 401) explicitly verifies a `valid_from=today` entry is created; passes. |
| 3 | `BW_SCHOOL_HOLIDAYS_2026_27` is populated — `is_school_holiday()` recognises 2026/27 periods and recurring shifts can skip them | VERIFIED | `german_holidays.py` lines 28-34 define `BW_SCHOOL_HOLIDAYS_2026_27` with all 5 periods (Herbst, Weihnachten, Ostern, Pfingsten, Sommer) plus source citation. `is_school_holiday()` line 100 iterates over both lists. 14 dedicated tests in `test_german_holidays.py` all pass, including 9 tests that cover 2026/27 dates. |
| 4 | Legacy `send_hourly_reminders` Celery task is absent from reminder_tasks.py and the Beat schedule | VERIFIED | `grep -rn "send_hourly_reminders"` returns no output anywhere in the backend. `celery_app.py` Beat schedule contains only 3 tasks: `send_type_reminders`, `send_daily_reminders`, `monthly-payroll`. |

**Score:** 4/4 truths verified

---

### Required Artifacts

| Artifact | Role | Status | Details |
|----------|------|--------|---------|
| `backend/app/services/payroll_service.py` | ContractHistory-only calculation | VERIFIED | `_get_contract_at()` and `_get_contracts_for_month()` query `ContractHistory`. No `employee.hourly_rate`, `employee.monthly_salary`, or other mirror field reads found anywhere in the file. |
| `backend/app/services/compliance_service.py` | No `employee.contract_type` reads | VERIFIED | `_get_contract_at()` queries `ContractHistory`. Line 67 comment "Vertragstyp aus ContractHistory lesen (nie Spiegel-Feld)". No `employee.contract_type` reference found. |
| `backend/app/services/pdf_service.py` | Requires `contract` parameter, raises ValueError without it | VERIFIED | Signature `generate_payslip_pdf(entry, employee, tenant_name, contract: ContractHistory | None = None)`. Lines 89-93 raise `ValueError` if `contract is None`. Contract data (`contract.hourly_rate`, `contract.contract_type`) used throughout the function body. |
| `backend/app/api/v1/reports.py` | ContractHistory joins, no Employee mirror reads | VERIFIED | `hours_summary` queries `ContractHistory` with date-range filter (lines 102-113). `minijob_limit_status` joins `Employee` and `ContractHistory` (lines 147-174) with comment "nicht Employee-Mirror". No `employee.hourly_rate` or `employee.contract_type` reads. |
| `backend/app/api/v1/employees.py` | `valid_from` is Optional in `ContractHistoryCreate` | VERIFIED | Line 26: `valid_from: date | None = None   # Optional: default=today (D-05)`. `add_contract` endpoint (line 380): `effective_valid_from = payload.valid_from if payload.valid_from is not None else date.today()`. |
| `backend/app/utils/german_holidays.py` | `BW_SCHOOL_HOLIDAYS_2026_27` constant with source citation | VERIFIED | Lines 24-34: constant defined with 5 periods. Lines 25-27: source citation "BW Kultusministerium Ferienplan 2026/27 — https://km-bw.de/de/service/ferien — Verified by executor on 2026-03-28". |
| `backend/app/tasks/reminder_tasks.py` | No `send_hourly_reminders` function | VERIFIED | File contains only `send_type_reminders`, `send_daily_reminders`, and `send_shift_reminder` tasks. No `send_hourly_reminders` function or reference anywhere in the file. |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `payroll.py` API (PDF endpoint) | `generate_payslip_pdf` | `ContractHistory` query + `contract=active_contract` arg | WIRED | Lines 383-398: queries `ContractHistory` with `valid_from <= entry.month`, passes result as `contract=active_contract`. HTTP 400 raised if no contract found — no silent fallback. |
| `compliance_service.py` | `ContractHistory` | `_get_contract_at()` DB query | WIRED | Lines 46-56 implement async DB lookup; result used at line 74 to check `contract.contract_type == "minijob"`. |
| `is_school_holiday()` | `BW_SCHOOL_HOLIDAYS_2026_27` | iteration in list comprehension | WIRED | Line 100 iterates `[BW_SCHOOL_HOLIDAYS_2025_26, BW_SCHOOL_HOLIDAYS_2026_27]`; both are module-level constants imported in the same file. |
| `assign_contract_type` endpoint | `ContractHistory` insert | `effective_from = mem_from` (defaults to `date.today()`) | WIRED | Lines 647-678 always insert a `ContractHistory` row. `valid_from` defaults to `date.today()` when caller omits it. |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `payroll_service.py` | `contract_periods` | `ContractHistory` DB query filtered by `employee_id` + date range | Yes — `scalars().all()` result from async query | FLOWING |
| `pdf_service.py` | `contract` parameter | Passed by caller (`payroll.py` API) from `ContractHistory` DB query | Yes — queried at PDF download time with exact month filter | FLOWING |
| `reports.py hours_summary` | `ch_map` | `ContractHistory` JOIN with date range | Yes — `scalars().all()` result | FLOWING |
| `german_holidays.py` | `BW_SCHOOL_HOLIDAYS_2026_27` | Static constant (correct by construction) | Yes — 5 holiday periods defined with real BW dates | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full test suite passes with 323 tests | `cd backend && python3 -m pytest tests/ -q` | 323 passed, 2 warnings in 66.72s | PASS |
| `test_payroll_uses_contract_history_not_mirror` asserts mirror field is ignored | `python3 -m pytest tests/test_payroll_service.py::test_payroll_uses_contract_history_not_mirror -v` | PASSED | PASS |
| 14 German holiday tests including 9 for 2026/27 | `python3 -m pytest tests/test_german_holidays.py -v` | 14 passed | PASS |
| `test_assign_contract_type_no_valid_from_creates_ch` | included in 323-test run | PASSED | PASS |
| `send_hourly_reminders` absent from entire codebase | `grep -rn "send_hourly_reminders" backend/` | no output | PASS |

---

### Requirements Coverage

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|----------|
| D-01 | Payroll reads from ContractHistory, not Employee mirror fields | SATISFIED | `payroll_service._get_contracts_for_month()` queries only `ContractHistory`; test `test_payroll_uses_contract_history_not_mirror` passes |
| D-02 | `assign_contract_type` without `valid_from` creates CH entry with `valid_from=today` | SATISFIED | `employees.py` line 380 defaults to `date.today()`; test `test_assign_contract_type_no_valid_from_creates_ch` passes |
| D-03 | PDF service requires explicit ContractHistory — no silent mirror fallback | SATISFIED | `ValueError` raised at line 89-93 of `pdf_service.py` when `contract is None` |
| D-04 | `BW_SCHOOL_HOLIDAYS_2026_27` populated with source citation | SATISFIED | `german_holidays.py` lines 28-34 with citation lines 25-27 |
| D-05 | Beat schedule has no phantom `send_hourly_reminders` task | SATISFIED | `celery_app.py` beat_schedule has 3 entries, none named `send_hourly_reminders`; function does not exist in `reminder_tasks.py` |

---

### Anti-Patterns Found

None detected. Specific checks run:

- No `employee.hourly_rate` / `employee.contract_type` / `employee.monthly_salary` reads in `payroll_service.py`, `compliance_service.py`, `pdf_service.py`, or `reports.py`
- No `TODO`/`FIXME`/`PLACEHOLDER` in the key files
- No `return null` / `return []` stub patterns in service or API code
- `send_hourly_reminders` not present anywhere in the backend

---

### Human Verification Required

None. All success criteria could be verified programmatically:

1. Mirror-field isolation is proven by the dedicated test that sets `employee.hourly_rate=99€` and asserts `base_wage=124€` (ContractHistory rate).
2. `valid_from` defaulting is proven by `test_assign_contract_type_no_valid_from_creates_ch`.
3. Holiday data is proven by 14 passing unit tests.
4. Beat schedule absence is verified by direct code inspection and grep.

---

### Summary

Phase 2 goal is fully achieved. All four success criteria are implemented, wired, and covered by the test suite:

- **ContractHistory isolation**: `payroll_service.py` and `compliance_service.py` query only `ContractHistory`; `pdf_service.py` enforces the contract parameter with a hard `ValueError`; the entire mirror-field bypass path has been eliminated.
- **No silent `valid_from` gap**: `assign_contract_type` always creates a `ContractHistory` entry, defaulting to `date.today()` when the caller omits `valid_from`.
- **2026/27 school holidays**: `BW_SCHOOL_HOLIDAYS_2026_27` is defined, sourced, and exercised by 9 dedicated tests; `is_school_holiday()` iterates both school-year lists.
- **No phantom Celery task**: `send_hourly_reminders` has been removed from both `reminder_tasks.py` and the Beat schedule.

The test count increased from 268 (Phase 1 baseline) to 323, confirming 55 new tests were added to cover Phase 2 behaviour.

---

_Verified: 2026-03-28T10:17:50Z_
_Verifier: Claude (gsd-verifier)_
