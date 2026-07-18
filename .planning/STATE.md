---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: Phase 4 + Phase 6 delivered outside formal /gsd plan flow (direct implementation), verified + deployed 2026-07-18
last_updated: "2026-07-18T16:00:00.000Z"
last_activity: 2026-07-18
progress:
  total_phases: 7
  completed_phases: 5
  total_plans: 9
  completed_plans: 9
  percent: 71
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-27)

**Core value:** Korrekte, rechtssichere Lohnabrechnung fur das PAB-Arbeitgebermodell
**Current focus:** Phase 5 (PWA/Mobile) und Phase 7 (RBAC-Audit) sind die letzten offenen Phasen

## Current Position

Phase: 4 (Employee Self-Service) + Phase 6 (Shift Swap) — DELIVERED 2026-07-18
(nicht über den formalen /gsd:plan-phase-Flow, sondern direkt implementiert und
verifiziert nach einem Fable-5-Projektreview + priorisierter Umsetzungsliste;
siehe Memory `vera-milestone-push-pending` für die volle Erzählung).

Phase 4 (ESS): shift acknowledgment (ESS-03), availability-change notification
(ESS-02) und Minijob-Grenze-Sichtbarkeit für Mitarbeiter selbst umgesetzt.
**Lücke: ESS-05 (Audit-Log für ESS-Aktionen) nicht erfüllt** — weder
`POST /shifts/{id}/acknowledge` noch die Verfügbarkeits-Änderung in
`PUT /employees/me` schreiben einen `audit_service.write()`-Eintrag. Nachtrag
offen (siehe Pending Todos).

Phase 6 (Shift Swap): bewusst NUR als Dienst-Abgabe (giveaway) umgesetzt, kein
gerichteter 1:1-Tausch — Stefan hat das explizit abgelehnt ("Dienste sind nicht
vergleichbar"). Damit weicht die gelieferte Phase 6 vom ursprünglichen
ROADMAP.md-Success-Criteria-Text ab (der einen Peer-zu-Peer-Tausch beschreibt);
ROADMAP.md-Phase-6-Text sollte bei Gelegenheit an den tatsächlichen Scope
angepasst werden.

Zusätzlich (nicht in der ursprünglichen Roadmap): Reminder-Pipeline-Bugfix
(Celery lief seit jeher fehlerhaft in Prod), Claim-Compliance-Pre-Check,
Superadmin-/Notification-/api_keys-Testabdeckung (52 Tests) + ein API-Key-
Prefix-Bugfix, sowie ein neuer `/help`+Feedback-Bereich (nicht in ROADMAP.md
verortet, ähnlich Phase 4 aber eigenständig).

Status: Phase 5 (PWA/Mobile) und Phase 7 (RBAC-Audit + Cleanup) offen
Last activity: 2026-07-18

Progress: [███████░░░] 71% (5 von 7 Phasen inhaltlich erledigt, Zählung informell)

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
- [Phase 04-ess / 2026-07-18]: Shift acknowledgment ist idempotent (zweiter Aufruf ändert `acknowledged_at` nicht) und wird bei Zeit-/Ortsänderung durch `update_shift` zurückgesetzt
- [Phase 04-ess / 2026-07-18]: Availability-Change-Notification an Admin/Manager nutzt denselben "Diff der geänderten Wochentage"-Ansatz statt einer reinen "geändert"-Meldung
- [Phase 06-shift-swap / 2026-07-18]: Scope-Entscheidung (Stefan): NUR Dienst-Abgabe (giveaway), kein gerichteter 1:1-Tausch — Dienste sind nicht vergleichbar genug
- [Phase 06-shift-swap / 2026-07-18]: Hybrid-Genehmigung nach Ausgangsstatus: `planned`-Dienste sofort wirksam (Compliance-Vorabprüfung wie Claim), `confirmed`-Dienste brauchen Admin/Manager-Review — konsistent mit der bestehenden Regel, dass bestätigte Dienste nur Admin/Manager ändern
- [Phase 06-shift-swap / 2026-07-18]: Nebenläufigkeits-Absicherung via bedingtem `UPDATE ... WHERE status='open'` statt `SELECT FOR UPDATE` (Roadmap-Text nannte ursprünglich `.with_for_update()`) — funktioniert identisch auf SQLite (Tests) und Postgres (Prod)
- [Infra / 2026-07-18]: Celery-Tasks brauchen eine eigene `TaskSessionLocal`/`task_engine` mit `NullPool` (in `app/core/database.py`) statt der von FastAPI genutzten gepoolten `AsyncSessionLocal` — asyncpg-Connections sind an die Event-Loop gebunden, in der sie erzeugt wurden, und jeder Celery-Task startet mit `asyncio.run()` seine eigene Loop. Zusätzlich `--pool=threads` statt prefork (Fork korrumpiert die Connection zusätzlich)

### Pending Todos

- **ESS-05 nachtragen**: `POST /shifts/{id}/acknowledge` (shifts.py) und die availability_prefs-Änderung in `PUT /employees/me` (employees.py) schreiben aktuell KEINEN `audit_service.write()`-Eintrag. Roadmap-Kriterium "All three actions appear in the Audit Log" ist damit nur für den Abwesenheits-Workflow erfüllt, nicht für Shift-Acknowledgment und Availability-Update.
- **ROADMAP.md Phase 6 Success Criteria anpassen**: Text beschreibt noch einen gerichteten Peer-zu-Peer-Tausch mit Ablehnungs-Flow; tatsächlich umgesetzt (und von Stefan gewünscht) ist nur Dienst-Abgabe (giveaway) ohne Gegenstück.
- **Off-Site-Backup**: Hetzner Storage Box muss von Stefan noch bestellt werden (Hetzner Robot-Konsole, BX11); danach SSH-Key-Setup + `backup.sh`-rsync-Erweiterung.
- **Telegram-Verifikation ausstehend**: Kein Mitarbeiter hat aktuell eine `telegram_chat_id` hinterlegt — Telegram-Kanal der neuen Notification-Events (availability_changed, swap_*, feedback_submitted) ist nur über E-Mail/Push verifiziert, nicht end-to-end über Telegram.

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

Last session: 2026-07-18
Stopped at: Phase 4 + Phase 6 delivered and deployed (backend HEAD migration
`p0q1r2s3t4u5`); 448 backend tests passing; all changes verified on prod
(6/6 containers healthy) via SSH + Playwright across admin/employee roles.
Resume file: None — next open work is Phase 5 (PWA/Mobile) or Phase 7
(RBAC-Audit), plus the Pending Todos above.
