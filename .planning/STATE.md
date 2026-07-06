---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: Completed 03-03-PLAN.md (Phase 3 complete, verified)
last_updated: "2026-07-06T05:30:00.000Z"
last_activity: 2026-07-06
progress:
  total_phases: 7
  completed_phases: 3
  total_plans: 9
  completed_plans: 9
  percent: 43
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-27)

**Core value:** Korrekte, rechtssichere Lohnabrechnung fur das PAB-Arbeitgebermodell
**Current focus:** Phase 4 — Employee Self-Service (Core), next up

## Current Position

Phase: 3 (audit-trail) — COMPLETE (2026-07-06)
Plan: 3 of 3 — done; human-verify checkpoint closed via automated Playwright
walkthrough (16 checks) after merging worktree branch `worktree-agent-a715c3c9`
(df9bd26, 455c500) to main (merge 1477409)
Status: Phase 4 ready to plan
Last activity: 2026-07-06

Progress: [████░░░░░░] 43%

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
| Phase 02-payroll-correctness P03 | 15 minutes | 2 tasks | 4 files |
| Phase 03-audit-trail P01 | 5 | 2 tasks | 4 files |
| Phase 03-audit-trail P02 | 25 | 2 tasks | 5 files |

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
- [Phase 02-payroll-correctness]: BW 2026/27 dates fetched from official km-bw.de source (Osterferien 30.03-03.04.2027, Pfingstferien 18.05-29.05.2027)
- [Phase 02-payroll-correctness]: is_school_holiday() iterates all school-year lists without year-selection logic
- [Phase 02-payroll-correctness]: seed_demo.py always uses slug=demo with explicit cascade deletes
- [Phase 03-audit-trail]: audit_service.write() stages without commit — caller owns transaction for atomicity with data changes
- [Phase 03-audit-trail]: REVOKE migration uses dialect guard — PostgreSQL-only enforcement, SQLite (dev/test) unaffected
- [Phase 03-audit-trail]: audit write on delete_shift staged before db.delete() — entity data must still be accessible for old_values capture
- [Phase 03-audit-trail]: calculate_payroll: create vs update audit distinguished by checking for existing draft before deletion (existing_old_values is not None)
- [Phase 03-audit-trail]: update_absence audit placed before mid-function db.commit() (before notification block) to maintain atomicity

### Pending Todos

None yet.

### Blockers/Concerns

- **Vacation-Entitlement-Luecke (entdeckt 2026-07-06, nach Shiftjuggler-Import)**: Mehrere
  clarasteam-Mitarbeiter (Rita Häusler, Nadja Kruschinski, Maja Juric, Bärbel Many Ndengue)
  haben weiterhin `vacation_days=0` in VERA konfiguriert. Mit echter historischer
  Urlaubsdaten aus Shiftjuggler sichtbar (Rita/Nadja: -1 Tag "remaining"). Vorbestehende
  Konfigurationsluecke, keine Folge des Imports — vor der geplanten Urlaubs-Engine-Phase
  (siehe Analyse 2026-07-06) die echten Vertrags-Urlaubsansprueche in VERA nachtragen.
  **Violeta Gjocaj bereits korrigiert (2026-07-06):** war fälschlich als Minijob angelegt
  (Stefan bestätigte: tatsächlich Teilzeit). ContractHistory korrigiert (contract_type=
  part_time, Minijob-Grenzen annual_salary_limit/monthly_hours_limit entfernt, hourly_rate
  22,10€ beibehalten), vacation_days per Fallmodell B (30÷90×25 tatsächliche AT seit
  Eintritt 2026-03-01) auf 8 Tage gesetzt — Achtung: nur ~4 Monate Datenbasis, bei mehr
  Historie neu berechnen. `Employee.contract_type_id` zeigt technisch noch auf die
  "Minijob Standard"-Vorlage (kein Editier-Feld dafür in der API) — kosmetisch, ohne
  Auswirkung auf Payroll/Compliance (die lesen contract_type/hourly_rate/Limits direkt).
- **Prod-Betrieb (entdeckt 2026-07-06)**: VERA-Prod war vom ~12. April bis 6. Juli DOWN
  (Container entfernt, Ursache unklar — restart-Policies waren gesetzt, also kein Reboot;
  vermutlich manuelles `docker compose down` oder Prune). Niemand hat es bemerkt →
  **Uptime-Monitoring/Alerting fehlt** (z. B. Healthcheck-Cron oder Uptime-Kuma).
- **Backups (entdeckt 2026-07-06)**: `backup.sh` schreibt bei totem DB-Container leere
  20-Byte-Dateien (Pipe legt Datei vor pg_dump-Fehler an) und der Retention-Prune hat
  das letzte gute Backup gelöscht. Skript härten (temp-Datei + mv nur bei Erfolg,
  Alarm bei Fehler) + Off-Site-Kopie (DSGVO Art. 32, siehe Analyse). Aktuelle Kopie:
  `~/vera-prod-backups/vera_2026-07-06_09-52.sql.gz` auf Stefans Rechner.
- **AUDIT REVOKE (Prod-Verifikation 2026-07-06)**: Migration lief korrekt (ACL ohne
  UPDATE/DELETE-Bits), aber der App-DB-User `vera` ist Postgres-**Superuser**
  (POSTGRES_USER des Images) und umgeht ACLs → Kriterium 3 aus Phase 3 greift in Prod
  faktisch nicht. Follow-up (Phase 7 / Infra): dedizierte non-superuser App-Rolle
  anlegen und DATABASE_URL umstellen.
- **Phase 1**: Shiftjuggler API key must have `write` scope set in DB before SEC-01 scope enforcement deploys — verify before Phase 1 ships
- **Phase 5**: Verify webpack (not Turbopack) active in next.config.mjs before Serwist integration starts
- **Phase 6**: Notification matrix for shift swap state transitions must be defined at plan time, not during coding

## Session Continuity

Last session: 2026-07-06
Stopped at: Phase 3 complete (03-03 checkpoint verified, worktree branch merged)
Resume file: None
