---
phase: 02-payroll-correctness
plan: "03"
subsystem: backend-utils
tags: [school-holidays, seed-data, celery, cleanup]
dependency_graph:
  requires: []
  provides:
    - BW_SCHOOL_HOLIDAYS_2026_27 constant in german_holidays.py
    - is_school_holiday() auto-selects correct school year
    - seed_demo.py always targets slug="demo"
    - reminder_tasks.py without dead send_hourly_reminders
  affects:
    - backend/app/services/recurring_shift_service.py (consumes is_school_holiday)
tech_stack:
  added: []
  patterns:
    - iterate-all-lists: is_school_holiday checks both school-year lists without year-selection logic
key_files:
  created:
    - backend/tests/test_german_holidays.py
  modified:
    - backend/app/utils/german_holidays.py
    - backend/seed_demo.py
    - backend/app/tasks/reminder_tasks.py
decisions:
  - "Use iterate-all-lists approach for is_school_holiday(): simpler than year-based selection, handles Sommerferien boundary correctly"
  - "BW 2026/27 Osterferien: 30.03.2027–03.04.2027 (official km-bw.de dates, not plan estimate of 29.03–10.04)"
  - "BW 2026/27 Pfingstferien: 18.05.2027–29.05.2027 (official km-bw.de dates, not plan estimate of 25.05–05.06)"
  - "Explicit cascade deletes in seed_demo.py using only already-imported models (Shift, ShiftTemplate, ContractHistory, Employee, AuditLog, User, Tenant)"
metrics:
  duration: "~15 minutes"
  completed_date: "2026-03-28"
  tasks_completed: 2
  files_modified: 4
  files_created: 1
---

# Phase 02 Plan 03: BW 2026/27 School Holidays + Demo Tenant Hardening + Celery Cleanup Summary

BW 2026/27 school holiday constant added with official km-bw.de dates, is_school_holiday() auto-selects across both school years, seed_demo.py always targets slug="demo", and dead send_hourly_reminders task removed.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add BW_SCHOOL_HOLIDAYS_2026_27 and update is_school_holiday() | ee27070 | german_holidays.py, test_german_holidays.py |
| 2 | Harden seed_demo.py tenant slug + remove send_hourly_reminders | ef449ac | seed_demo.py, reminder_tasks.py |

## What Was Built

### Task 1: BW 2026/27 School Holidays (TDD)

Added `BW_SCHOOL_HOLIDAYS_2026_27` constant to `backend/app/utils/german_holidays.py` with dates
fetched directly from the official BW Kultusministerium website (https://km-bw.de/de/service/ferien)
on 2026-03-28.

Official dates for 2026/27:
- Herbstferien: 26.10.2026 – 30.10.2026
- Weihnachtsferien: 23.12.2026 – 09.01.2027
- Osterferien: 30.03.2027 – 03.04.2027
- Pfingstferien: 18.05.2027 – 29.05.2027
- Sommerferien: 29.07.2027 – 11.09.2027

Updated `is_school_holiday()` to iterate all lists (`[BW_SCHOOL_HOLIDAYS_2025_26, BW_SCHOOL_HOLIDAYS_2026_27]`),
making it auto-selecting without date-based year logic. No callers required changes.

Created `backend/tests/test_german_holidays.py` with 14 tests covering both school years, boundary
dates, and the gap between the two school years.

### Task 2: seed_demo.py + reminder_tasks.py

**seed_demo.py:**
- Cleanup block now searches for both `"demo"` and `"vera-demo"` slugs (handles old and new slug)
- Explicit cascade deletes added in safe order (Shift → ShiftTemplate → ContractHistory → Employee →
  AuditLog → User → Tenant) using only already-imported models
- Tenant creation changed from `slug="vera-demo"` to `slug="demo"` — now permanently hardened

**reminder_tasks.py:**
- Removed the dead `send_hourly_reminders()` stub (4 lines: comment + decorator + def + pass)
- Function was already absent from `beat_schedule` in `celery_app.py`
- 0 references remain in any Python source file under `backend/app/`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Data Correction] Official BW 2026/27 dates differ from plan estimates**
- **Found during:** Task 1 — executor fetched official dates from km-bw.de
- **Issue:** Plan provided "preliminary estimates" for Osterferien and Pfingstferien that did not match official schedule
  - Plan estimate Osterferien: 29.03.2027–10.04.2027
  - Official Osterferien: 30.03.2027–03.04.2027
  - Plan estimate Pfingstferien: 25.05.2027–05.06.2027
  - Official Pfingstferien: 18.05.2027–29.05.2027
- **Fix:** Used official km-bw.de dates; test `test_2026_27_osterferien()` uses `date(2027, 4, 2)` which is within the official range. The plan test spec `is_school_holiday(date(2027, 4, 8))` was adjusted to `date(2027, 4, 2)` since 08.04.2027 is after Osterferien end (03.04.2027).
- **Files modified:** german_holidays.py, test_german_holidays.py

## Known Stubs

None — all functionality is fully wired with official data.

## Test Results

```
323 passed, 2 warnings in 66.84s
```

All 323 backend tests pass including 14 new tests in test_german_holidays.py.

## Self-Check: PASSED

- `backend/app/utils/german_holidays.py`: FOUND
- `backend/tests/test_german_holidays.py`: FOUND
- `backend/seed_demo.py`: FOUND
- `backend/app/tasks/reminder_tasks.py`: FOUND
- Commit ee27070: FOUND
- Commit ef449ac: FOUND
