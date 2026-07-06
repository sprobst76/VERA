# ROADMAP — VERA Milestone 1
# Security, Hardening & Employee Self-Service

**Version:** 1.0
**Date:** 2026-03-27
**Milestone:** 1 — Security, Hardening & Employee Self-Service
**Granularity:** Standard (7 phases derived from natural delivery boundaries)
**Coverage:** 28/28 v1 requirements mapped

---

## Phases

- [x] **Phase 1: Security Foundation + Deploy Fix** — Fix live CVE, deploy race, API key scopes, JWT revocation
- [x] **Phase 2: Payroll Correctness** — Eliminate ContractHistory mirror divergence before audit wires up
- [x] **Phase 3: Audit Trail** — Immutable append-only audit log with admin UI
- [ ] **Phase 4: Employee Self-Service (Core)** — Absence requests, availability self-update, shift acknowledgment
- [ ] **Phase 5: PWA + Mobile** — Installable app, offline calendar, mobile UX
- [ ] **Phase 6: Shift Swap** — Multi-party swap workflow with compliance pre-check
- [ ] **Phase 7: RBAC Audit + Cleanup** — Systematic endpoint review, demo isolation, Pydantic strict mode

---

## Phase Details

### Phase 1: Security Foundation + Deploy Fix
**Goal**: Production system deploys safely and enforces the security boundaries it advertises
**Depends on**: Nothing (prerequisite for all subsequent phases)
**Requirements**: SEC-01, SEC-04, SEC-05, SEC-06, INFRA-01
**Success Criteria** (what must be TRUE):
  1. A `python-jose` CVE-2024-33663 is gone — `PyJWT 2.12+` and direct `bcrypt` are in `requirements.txt`, all tests pass
  2. Deploying a schema-changing migration no longer produces 500 errors — migration runs and succeeds before the new API container accepts traffic
  3. A read-only API key cannot execute a write operation — `POST /shifts` with a read-scoped key returns 403; `GET /shifts` succeeds
  4. Logging out of all devices works — after `POST /auth/logout-all`, all existing refresh tokens are rejected on next use
  5. CORS allows `X-API-Key` header — browser-based API key requests pass preflight without error
**Plans:** 1/3 plans executed
Plans:
- [x] 01-01-PLAN.md — PyJWT + bcrypt migration (SEC-06)
- [x] 01-02-PLAN.md — token_version JWT revocation + API key scope enforcement (SEC-05, SEC-01)
- [x] 01-03-PLAN.md — CORS X-API-Key header fix + deploy race fix (SEC-04, INFRA-01)
**Risk**: HIGH — touches auth, deploy pipeline, live API key behavior (Shiftjuggler sync must be verified with write scope before enforcement enables)

---

### Phase 2: Payroll Correctness
**Goal**: Payroll and compliance calculations read from live ContractHistory — mirror fields cannot cause silent wage errors
**Depends on**: Phase 1
**Requirements**: DEBT-01, DEBT-02, DEBT-03, DEBT-04, INFRA-02
**Success Criteria** (what must be TRUE):
  1. Payroll PDF for an employee uses the ContractHistory row valid on that date — changing the mirror field directly has no effect on the calculation
  2. Calling `assign_contract_type` without `valid_from` creates a ContractHistory entry with `valid_from=today` — no more silent payroll gaps
  3. `BW_SCHOOL_HOLIDAYS_2026_27` is populated — recurring shifts correctly skip the new school year holiday periods
  4. Legacy `send_hourly_reminders` Celery task is removed from Beat schedule — no phantom no-op task in logs
**Plans:** 3 plans
Plans:
- [x] 02-01-PLAN.md — Remove mirror field fallbacks from payroll_service + compliance_service (DEBT-01)
- [x] 02-02-PLAN.md — PDF service mirror removal + assign_contract_type valid_from fix (DEBT-01, DEBT-02)
- [x] 02-03-PLAN.md — BW school holidays 2026/27 + demo tenant hardening + dead Celery task removal (DEBT-03, DEBT-04, INFRA-02)
**Risk**: MEDIUM — payroll service refactor touches core calculation path; covered by existing payroll tests

---

### Phase 3: Audit Trail
**Goal**: Every write operation on payroll, shifts, employees, and absences leaves an immutable, queryable record
**Depends on**: Phase 2 (audit must capture correct payroll data, not stale mirror values)
**Requirements**: AUDIT-01, AUDIT-02, AUDIT-03, AUDIT-04, AUDIT-05
**Success Criteria** (what must be TRUE):
  1. Creating, editing, or deleting a Shift, Employee, PayrollEntry, ContractHistory entry, or EmployeeAbsence produces an AuditLog row in the same transaction
  2. A rolled-back mutation produces no orphan AuditLog row
  3. `UPDATE` and `DELETE` are revoked from `audit_log` for the application DB user — a direct SQL attempt returns a permission error
  4. Admin can open the Audit Log page, filter by entity type and date range, and see paginated results
  5. Payroll audit entries include before/after values for `actual_hours`, `base_wage`, and `total_gross` — no Bruttolohn in plaintext outside these structured fields
**Plans:** 3/3 plans executed
Plans:
- [x] 03-01-PLAN.md — Audit foundation: service, schemas, migration, test scaffolds (AUDIT-01, AUDIT-05)
- [x] 03-02-PLAN.md — Wire audit_service.write() into all write endpoints (AUDIT-02, AUDIT-03)
- [x] 03-03-PLAN.md — Admin audit log API endpoint + frontend page (AUDIT-04)
**UI hint**: yes
**Risk**: MEDIUM — transaction atomicity is a known pitfall (audit INSERT must be in same db.commit() as business change); SQLAlchemy async event listeners must NOT be used

---

### Phase 4: Employee Self-Service (Core)
**Goal**: Employees can manage their own attendance data without needing to call the admin
**Depends on**: Phase 3 (all approval transitions must emit audit entries via the shared helper)
**Requirements**: ESS-01, ESS-02, ESS-03, ESS-05
**Success Criteria** (what must be TRUE):
  1. An employee can submit an absence request — it appears as `pending` in the admin view, and the admin can approve or reject it; the employee receives a notification either way
  2. An employee can update their availability preferences from their profile — the admin receives a notification showing what changed
  3. An employee can acknowledge an assigned shift — the admin sees `acknowledged_at` timestamp on the shift detail
  4. All three actions appear in the Audit Log with the acting employee's user ID
**Plans**: TBD
**UI hint**: yes
**Risk**: LOW — model and workflow infrastructure already exist; work is RBAC wire-up, new endpoints, and notification dispatch

---

### Phase 5: PWA + Mobile
**Goal**: VERA is installable on mobile devices and works offline for shift viewing
**Depends on**: Phase 1 (HTTPS and correct auth headers required for service worker registration)
**Requirements**: PWA-01, PWA-02, PWA-03, PWA-04, PWA-05, PWA-06
**Success Criteria** (what must be TRUE):
  1. Android Chrome and iOS Safari offer an "Add to Home Screen" prompt — the installed app launches full-screen with VERA branding
  2. With network disabled, an employee can view the calendar and their own shifts from the last cache fill — a visible "Offline" indicator is shown
  3. Auth and payroll endpoints are never served from cache — NetworkOnly applies to `/api/v1/auth/*` and `/api/v1/payroll/*`
  4. A push notification received when the app is closed opens the correct deep-linked page on tap (not just the app root)
  5. All interactive elements are reachable with thumb navigation on a 375px viewport — no horizontal scroll, touch targets ≥ 44px
**Plans**: TBD
**UI hint**: yes
**Risk**: LOW — frontend-only; no backend dependencies; parallelizable with Phases 2-4 if capacity allows; verify webpack (not Turbopack) before starting Serwist

---

### Phase 6: Shift Swap
**Goal**: Employees can propose and execute shift swaps through a supervised approval flow
**Depends on**: Phase 3 (audit trail), Phase 4 (ESS patterns established, shift acknowledgment live)
**Requirements**: ESS-04
**Success Criteria** (what must be TRUE):
  1. An employee can propose a swap with another employee — both the peer and the admin receive a notification
  2. The peer employee can accept or decline — if declined, the initiator is notified and the request is closed
  3. Admin can approve a peer-accepted swap only after a compliance pre-check (ArbZG §4/§5) passes for both resulting shift assignments
  4. On admin approval, both shifts atomically reassign to the new employees — two concurrent approval attempts cannot both succeed
  5. Stale swap requests auto-expire after 48 hours with notifications to both parties
**Plans**: TBD
**UI hint**: yes
**Risk**: HIGH — new model, multi-party FSM, SELECT FOR UPDATE required; notification matrix (who gets notified at each transition) must be defined at plan time before coding

---

### Phase 7: RBAC Audit + Cleanup
**Goal**: All API endpoints have verified role guards; demo data is isolated; write schemas reject extra fields
**Depends on**: Phase 1 (scope enforcement in place), Phase 2-6 (all new endpoints created)
**Requirements**: SEC-02, SEC-03
**Success Criteria** (what must be TRUE):
  1. Every route in `api/v1/` has an explicit RBAC dependency (`CurrentUser`, `ManagerOrAdmin`, `AdminUser`, or `ParentViewerOrHigher`) — a grep for routes without auth dependencies returns zero results
  2. All write-operation Pydantic schemas use `model_config = ConfigDict(extra="forbid")` — sending an unknown field to any write endpoint returns a validation error
  3. Demo data lives in a tenant with slug `demo` separate from Stefan's production tenant — payroll and compliance reports for the production tenant show no demo employee names
**Plans**: TBD
**Risk**: LOW — systematic review pass; no new models or workflows

---

## Progress Table

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Security Foundation + Deploy Fix | 3/3 | Complete | 2026-03-27 |
| 2. Payroll Correctness | 3/3 | Complete | 2026-03-28 |
| 3. Audit Trail | 1/3 | In Progress|  |
| 4. Employee Self-Service (Core) | 0/TBD | Not started | - |
| 5. PWA + Mobile | 0/TBD | Not started | - |
| 6. Shift Swap | 0/TBD | Not started | - |
| 7. RBAC Audit + Cleanup | 0/TBD | Not started | - |

---

## Coverage Map

| Req-ID | Phase | Category |
|--------|-------|----------|
| SEC-01 | Phase 1 | API key scope enforcement |
| SEC-04 | Phase 1 | Secrets audit: CORS + X-API-Key header |
| SEC-05 | Phase 1 | JWT revocation via token_version |
| SEC-06 | Phase 1 | PyJWT replaces python-jose (CVE) |
| INFRA-01 | Phase 1 | Deploy race fix |
| DEBT-01 | Phase 2 | ContractHistory mirror divergence |
| DEBT-02 | Phase 2 | assign_contract_type always creates history |
| DEBT-03 | Phase 2 | Schulferien 2026/27 |
| DEBT-04 | Phase 2 | Demo tenant separation |
| INFRA-02 | Phase 2 | Remove legacy send_hourly_reminders task |
| AUDIT-01 | Phase 3 | AuditLog composite indexes |
| AUDIT-02 | Phase 3 | audit_service.write() wired to all write endpoints |
| AUDIT-03 | Phase 3 | Payroll changes logged with before/after JSON |
| AUDIT-04 | Phase 3 | Admin UI: audit log page |
| AUDIT-05 | Phase 3 | PostgreSQL REVOKE on audit_log table |
| ESS-01 | Phase 4 | Absence request workflow |
| ESS-02 | Phase 4 | Employee availability self-update |
| ESS-03 | Phase 4 | Shift acknowledgment |
| ESS-05 | Phase 4 | ESS actions in audit log |
| PWA-01 | Phase 5 | Web App Manifest |
| PWA-02 | Phase 5 | Service Worker via Serwist |
| PWA-03 | Phase 5 | Caching strategy per route |
| PWA-04 | Phase 5 | Offline fallback |
| PWA-05 | Phase 5 | Push deep links |
| PWA-06 | Phase 5 | Mobile UX: touch targets + swipe |
| ESS-04 | Phase 6 | Shift swap workflow |
| SEC-02 | Phase 7 | Systematic RBAC endpoint audit |
| SEC-03 | Phase 7 | Pydantic strict mode on write schemas |

**Total mapped: 28/28 — no orphaned requirements**

---

## Key Ordering Constraints

1. **Phase 1 is a hard prerequisite for all other phases** — the deploy race means any schema migration can produce 500 errors until INFRA-01 ships; the API key scope bug means all subsequent security guarantees are false until SEC-01 ships
2. **Phase 2 before Phase 3** — auditing data from stale mirror fields creates a false compliance paper trail; payroll must read from live ContractHistory before audit captures it
3. **Phase 3 before Phase 4** — every ESS approval state transition must emit an audit entry; `audit_service.write()` must exist and be tested before workflows depend on it
4. **Phase 4 before Phase 6** — shift acknowledgment (ESS-03) is a direct prerequisite for shift swap (ESS-04); ESS patterns proven in Phase 4 reduce Phase 6 risk
5. **Phase 5 is parallelizable** — entirely frontend-only; can run concurrently with Phases 2-4 if capacity allows; do not let it block or be blocked by backend work
6. **Phase 7 last** — RBAC audit must cover all new endpoints created in Phases 1-6; cleanup is most effective after all features are built

---

## Critical Pitfalls (from research)

- **Audit tx atomicity**: AuditLog INSERT must be inside the same `db.commit()` as the business change — never in a separate commit
- **No async event listeners for audit**: `await db.execute()` inside SQLAlchemy ORM event listeners raises `MissingGreenlet`; capture before-snapshot in endpoint code
- **Shiftjuggler sync key**: Before SEC-01 deploys, verify the Shiftjuggler API key has `write` scope in the DB — consider a grace-period warning mode for the first deploy
- **Shift swap race condition**: Both swap shifts must be locked with `.with_for_update()` — fixes existing `/shifts/{id}/claim` race as a prerequisite to ESS-04
- **Serwist requires webpack**: Verify `next.config.mjs` is NOT using Turbopack before starting Phase 5
- **Notification matrix for shift swap**: Define exact who-gets-notified at each state transition before Phase 6 coding begins

---

*Roadmap created: 2026-03-27*
*Next: `/gsd:execute-phase 3`*
