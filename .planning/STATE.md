---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: Completed 02-payroll-correctness/02-02-PLAN.md
last_updated: "2026-03-28T10:07:20.955Z"
last_activity: 2026-03-28
progress:
  total_phases: 7
  completed_phases: 1
  total_plans: 6
  completed_plans: 5
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-27)

**Core value:** Korrekte, rechtssichere Lohnabrechnung fur das PAB-Arbeitgebermodell
**Current focus:** Phase 01 — security-foundation-deploy-fix

## Current Position

Phase: 02 (payroll-correctness) — EXECUTING
Plan: 2 of 3 (all 3 plans running in parallel)
Status: Ready to execute
Last activity: 2026-03-28

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**

- Total plans completed: 0
- Average duration: — min
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**

- Last 5 plans: —
- Trend: —

*Updated after each plan completion*
| Phase 01-security-foundation-deploy-fix P03 | 2 | 2 tasks | 3 files |
| Phase 01-security-foundation-deploy-fix P01 | 4 | 2 tasks | 3 files |
| Phase 01-security-foundation-deploy-fix P02 | 5 | 3 tasks | 7 files |
| Phase 02-payroll-correctness P01 | 63 | 2 tasks | 4 files |
| Phase 02-payroll-correctness P02 | 35 | 3 tasks | 6 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Pre-Phase 1: PyJWT replaces python-jose (CVE-2024-33663); direct bcrypt replaces passlib
- Pre-Phase 1: token_version int column for JWT revocation (no Redis jti blocklist needed)
- Pre-Phase 3: Audit log uses explicit audit_service.write() calls, not ORM event listeners (MissingGreenlet)
- Pre-Phase 4/6: Decide python-statemachine 2.6 vs inline transition dict at Phase 4 plan time — apply consistently
- [Phase 01-security-foundation-deploy-fix]: Health endpoint for deploy readiness check is /health (not /api/v1/health)
- [Phase 01-security-foundation-deploy-fix]: Deploy: alembic runs in one-shot container (run --rm --no-deps) before API service starts
- [Phase 01-security-foundation-deploy-fix]: PyJWT replaces python-jose (CVE-2024-33663 eliminated); passlib removed, direct bcrypt in use; token payload structure unchanged
- [Phase 01-security-foundation-deploy-fix]: token_version default=0 with server_default='0' ensures backward compat with existing sessions (D-04)
- [Phase 01-security-foundation-deploy-fix]: Missing 'ver' claim in JWT treated as 0 — pre-deploy tokens still work for users with token_version=0 (D-06)
- [Phase 01-security-foundation-deploy-fix]: null/empty API key scopes treated as admin for Shiftjuggler backward compatibility (D-14)
- [Phase 02-payroll-correctness]: payroll_service soft-fail for missing ContractHistory: return PayrollEntry total_gross=0 with JSON warning in notes field
- [Phase 02-payroll-correctness]: compliance_service uses _get_contract_at helper to read contract_type from ContractHistory at shift.date
- [Phase 02-payroll-correctness]: generate_payslip_pdf requires explicit ContractHistory parameter (raises ValueError if None) — no mirror fallback per D-01
- [Phase 02-payroll-correctness]: reports.py minijob filtering via ContractHistory JOIN replaces Employee.contract_type DB filter
- [Phase 02-payroll-correctness]: ContractHistoryCreate.valid_from Optional with date.today() default — endpoint resolves effective_valid_from before DB write

### Pending Todos

None yet.

### Blockers/Concerns

- **Phase 1**: Shiftjuggler API key must have `write` scope set in DB before SEC-01 scope enforcement deploys — verify before Phase 1 ships
- **Phase 5**: Verify webpack (not Turbopack) active in next.config.mjs before Serwist integration starts
- **Phase 6**: Notification matrix for shift swap state transitions must be defined at plan time, not during coding

## Session Continuity

Last session: 2026-03-28T10:07:20.952Z
Stopped at: Completed 02-payroll-correctness/02-02-PLAN.md
Resume file: None
