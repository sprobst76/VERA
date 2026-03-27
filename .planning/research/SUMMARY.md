# Project Research Summary

**Project:** VERA — Milestone 1: Security Hardening, Audit Trail, PWA, Employee Self-Service
**Domain:** Payroll + workforce management for small employer (PAB Arbeitgebermodell, German labor law)
**Researched:** 2026-03-27
**Confidence:** HIGH

## Executive Summary

VERA is a production payroll system with real salary data for 7 employees. Milestone 1 is additive — the core stack (FastAPI + SQLAlchemy async + PostgreSQL + Next.js App Router) is proven and not being replaced. The research confirms that all four capability areas (security hardening, audit trail, employee self-service, PWA) can be built using existing infrastructure with minimal new dependencies. The most important finding: several structures are already partially in place (`AuditLog` model exists, `EmployeeAbsence` has a status field, VAPID push infrastructure exists) — the work is completing and wiring, not starting from scratch.

Two security gaps must be treated as blockers before any other work ships: the API key scope enforcement bug (any key currently has admin rights regardless of configured scopes) and the deploy-order race condition (new API starts before migration runs, causing 500 errors during deploys). The JWT token revocation gap (7-day refresh tokens survive password changes) is a security fix that requires only a single integer column migration with no Redis overhead. The critical correctness risk is the ContractHistory mirror divergence — payroll and compliance services read from denormalized mirror fields on `Employee` rather than the live `ContractHistory` record. If the mirror diverges, payroll PDFs are silently wrong. This must be resolved before any payroll-touching feature ships.

The overall implementation risk for this milestone is low. All pitfalls have known mitigations, the patterns are well-documented, and no speculative features are in scope. The main execution discipline required is: fix the foundation before building on it.

### Most Important Findings (5 bullets)

- The API key scope enforcement bug and deploy-order race must both be fixed in Phase 1 — they are production-level risks that exist today and block safe deployment of any subsequent change.
- ContractHistory mirror divergence (DEBT-01) must be resolved before AUDIT-02 ships — auditing payroll data that is already wrong creates a false compliance paper trail.
- AUDIT-01 (audit log wiring) must precede ESS approval workflows — every state transition must emit an audit entry, and the shared helper must exist before workflows depend on it.
- PWA has zero backend dependencies and can be built in parallel with backend phases; do not let it block or be blocked by backend work.
- Shift swap (ESS-01) is the only high-complexity feature — defer it to last within the milestone; it requires a new model, multi-party workflow, race condition handling, and compliance pre-validation.

---

## Key Findings

### Recommended Stack

The existing stack needs no major additions. Only three new Python packages are required: `PyJWT==2.12.1` (replaces the abandoned `python-jose` which carries CVE-2024-33663), `python-statemachine>=2.6,<3.0` (approval workflow state validation), and `slowapi==0.1.9` (application-level rate limiting as defense-in-depth). For the frontend, `@serwist/next` + `serwist` (dev) replace the abandoned `next-pwa` package for PWA/offline support.

**Core technology changes:**

- `PyJWT 2.12.1`: replaces `python-jose 3.3.0` — active maintenance, no CVEs, near-identical API surface; `python-jose` abandoned since 2021 with CVE-2024-33663
- `bcrypt` direct: replaces `passlib[bcrypt]` wrapper — passlib is in maintenance mode; direct bcrypt is simpler and maintained
- `python-statemachine 2.6.x`: approval workflow FSM validation — cleaner than hand-coded transition dicts for guard enforcement; use 2.x not 3.x (3.x statechart features are overkill for linear flows)
- `slowapi 0.1.9`: rate limiting on auth endpoints — defense-in-depth behind existing Traefik limits
- `@serwist/next` (frontend): PWA service worker — only recommended library for Next.js App Router; `next-pwa` (shadowwalker) abandoned 2022, broken with App Router
- `token_version` int column on `User`: JWT revocation without Redis overhead — one DB column comparison per request (already loading the user row anyway)

**Do not add:** Redis jti blocklist for Milestone 1 (overkill when `token_version` suffices for "revoke all devices"), PostgreSQL RLS (application-level tenant filtering already tested across 268 tests), WAL-based audit consumers (massively overengineered for 7 users), Turbopack (Serwist requires webpack).

### Expected Features

**Must have (Milestone 1 blockers):**

- SEC-01: API key scope enforcement — security hole; any key currently has admin rights
- DEBT-01: ContractHistory mirror fix — must precede any payroll audit
- Deploy order fix — must precede any schema-changing migration
- AUDIT-01 + AUDIT-02: Audit log wiring — `AuditLog` model exists but nothing writes to it; payroll changes must be traceable (DSGVO)
- ESS-02: Employee-initiated absence request — model and workflow exist; only RBAC + notification wire-up needed
- ESS-03: Employee availability self-update — one PATCH endpoint + RBAC change
- ESS-04: Shift acknowledgment — one nullable DateTime column on `Shift` + PATCH endpoint
- PWA-01: Installable manifest — one file (`app/manifest.ts`) + icons
- PWA-03: Push via service worker — `push` + `notificationclick` handlers in `sw.js`
- DEBT-04: Schulferien 2026/27 — expires September 2026, only 5 months away

**Should have (complete the milestone):**

- SEC-02: RBAC audit — systematic grep of all routes for missing auth dependencies
- SEC-05: JWT revocation — `token_version` migration + `POST /auth/logout-all` endpoint
- AUDIT-03: Admin audit UI — paginated, filterable; depends on AUDIT-01
- PWA-02: Offline calendar — network-first caching; depends on PWA-01
- PWA-04: Mobile UX polish — CSS/component work, no backend
- DEBT-02: `assign_contract_type` always creates a ContractHistory entry

**Defer to Milestone 2:**

- ESS-01: Shift swap — new model, multi-party workflow, compliance pre-check, race condition handling; build after simpler ESS features are stable
- SEC-03: Pydantic strict mode — low urgency; audit schemas before applying globally

**Explicit anti-features (do not build):**

- Employee-initiated time corrections — payroll integrity risk
- Open shift bidding — no value for 7-user system
- In-app messaging — Telegram notifications fill this need
- Full offline write operations — sync conflict complexity not justified

### Architecture Approach

All four capability areas plug into VERA's existing architecture without structural changes. The audit log uses the existing `AuditLog` model with an explicit helper function (`audit_service.write_audit()`) called directly from endpoint code — not ORM event listeners (SQLAlchemy 2.0 async prohibits I/O in synchronous event callbacks, which would raise `MissingGreenlet`). Approval workflows expand the existing endpoint surface without new model concepts except `ShiftSwapRequest`, which requires a separate table because it spans two shifts and two employees. JWT revocation uses a `token_version` int column — cheaper and simpler than a Redis jti blocklist for "revoke all devices" semantics. The PWA service worker is built with Serwist using webpack (not Turbopack) and adds push/notificationclick handlers to complete the existing VAPID push flow that is already fully wired on the backend.

**Major components and changes:**

1. `backend/app/services/audit_service.py` (new) — shared `write_audit()` helper called by all write endpoints; replaces the per-file `_write_audit` in `shifts.py`
2. `backend/app/models/user.py` — add `token_version: int = 1` column + Alembic migration
3. `backend/app/api/v1/absences.py` — add employee-facing `POST /absences` + `PUT /absences/{id}/approve` / `reject` (model already correct)
4. `backend/app/models/shift_swap_request.py` (new) — `ShiftSwapRequest` table with status FSM
5. `backend/app/api/deps.py` — add `require_scope()` factory dependency; attach `api_key_scopes` to `request.state` during key resolution
6. `frontend/app/sw.ts` + `frontend/app/manifest.ts` (new) — Serwist-managed service worker + Web App Manifest
7. Deploy script / CI workflow — fix order: migration before new API image start

**Recommended build order:**

```
1. Deploy fix + SEC-01 + SEC-05  — security foundation, no deps, unblocks everything
2. DEBT-01 + DEBT-02 + DEBT-04  — payroll correctness, must precede AUDIT-02
3. AUDIT-01 + AUDIT-02          — audit wiring, needed by ESS approval workflows
4. ESS-02 + ESS-03 + ESS-04     — simple ESS, depend on audit being wired
5. AUDIT-03 + SEC-02            — cleanup + audit UI, parallel with ESS
6. PWA-01 through PWA-04        — frontend-only, parallelizable with phases 2-4
7. ESS-01                       — shift swap, last; most complex, requires prior ESS stable
```

### Critical Pitfalls

1. **Audit log outside the mutation transaction** — if the `AuditLog` INSERT is not in the same `db.commit()` as the business change, a process kill between commit and audit write leaves committed mutations with no audit record. Write audit entries inside the same transaction; rollbacks correctly roll back audit entries too.

2. **SQLAlchemy async event listeners cannot do I/O** — `await db.execute()` inside `after_flush` or similar ORM event listeners raises `MissingGreenlet`. Capture the "before" snapshot in endpoint code before the mutation and pass it explicitly to `write_audit()`. Never use event listeners for audit captures.

3. **Shift claim/swap race condition without SELECT FOR UPDATE** — two simultaneous requests can both read `shift.employee_id == None`, both pass the check, both commit. PostgreSQL READ COMMITTED isolation allows this silent overwrite. Fix the existing claim endpoint race before ESS-01 ships; use `.with_for_update()` on shift row selects within claim/swap transactions.

4. **API key scope enforcement breaks Shiftjuggler sync** — when SEC-01 ships, the existing Shiftjuggler API key must have `write` scope assigned in the DB before enforcement is enabled. Verify key scopes before the code deploys. Consider a grace-period warning mode (log but don't block) for the first deploy.

5. **Deploy order: new API starts before migration runs** — the current deploy script starts `vera-api` before running `alembic upgrade head`. With `token_version`, audit log indexes, and `shift_swap_requests` all landing in Milestone 1, each migration will cause 500 errors during the deploy window. Fix the deploy order (migrate first, then restart API) before any schema-changing migration lands — this is a prerequisite for the entire milestone.

---

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Security Foundation + Deploy Fix

**Rationale:** Two issues make every subsequent deploy dangerous. The deploy order race (API starts before migration) means any schema change can cause a 500-error window. The API key scope bug means all automation has de-facto admin rights. Fix these first so the rest of the milestone ships safely.

**Delivers:** Safe deployment pipeline; API key scopes enforced; JWT token revocation via `token_version`; CVE-2024-33663 resolved (PyJWT replaces python-jose); passlib replaced with direct bcrypt; CORS hardened with `X-API-Key` header

**Addresses:** SEC-01, SEC-04, SEC-05, Pitfall 4 (refresh token gap), Pitfall 5 (scope bypass), Pitfall 10 (deploy order race)

**Avoids:** Deploying security fixes on a broken deploy pipeline

**Research flag:** Standard patterns — PyJWT migration is near-identical API surface. `token_version` is established best practice. No additional research needed.

---

### Phase 2: Payroll Correctness (Tech Debt)

**Rationale:** Auditing incorrect payroll data (Phase 3) is worse than not auditing at all — it creates a false compliance paper trail. DEBT-01 must resolve the ContractHistory mirror before audit wiring captures payroll state.

**Delivers:** Payroll and compliance read from live `ContractHistory` (WHERE valid_to IS NULL) instead of mirror fields; `assign_contract_type` always creates a history entry; §3b surcharge capped at 50 EUR/hr base; Schulferien 2026/27 added

**Addresses:** DEBT-01, DEBT-02, DEBT-04, Pitfall 6 (mirror divergence), Pitfall 12 (§3b cap)

**Avoids:** AUDIT-02 capturing wrong payroll figures in the before/after snapshots

**Research flag:** No additional research needed — these are known fixes with clear implementation paths. The §3b 40% enhanced night rate (00:00–04:00) should be flagged as a comment in code pending Steuerberater confirmation; do not implement silently.

---

### Phase 3: Audit Trail

**Rationale:** AUDIT-01 is the dependency for every ESS approval workflow — each state transition must emit an audit log entry. The shared `audit_service.write_audit()` helper must exist and be tested before workflows rely on it.

**Delivers:** Immutable audit log for all write operations; `audit_service.py` shared helper; composite DB indexes; DSGVO-compliant 2-year retention policy with Celery cleanup task; admin UI for audit log review (paginated, filterable)

**Addresses:** AUDIT-01, AUDIT-02, AUDIT-03, Pitfall 1 (tx atomicity), Pitfall 2 (async event listeners), Pitfall 11 (DSGVO retention)

**Avoids:** Phantom audit entries for rolled-back operations; missing audit entries for committed operations

**Research flag:** Standard patterns — application-level audit log with SQLAlchemy is well-documented. DSGVO retention mechanics are clear (2 years per §257 HGB). Payroll audit entries must reference `PayrollEntry.id`, not log Bruttolohn values in plaintext.

---

### Phase 4: Employee Self-Service (Simple)

**Rationale:** ESS-02, ESS-03, ESS-04 are individually low-complexity and can ship together. ESS-04 (shift acknowledgment) is a prerequisite for ESS-01 (shift swap), so shipping these three features first unblocks Phase 7 without the risk of a complex feature.

**Delivers:** Employees can request absences (admin approval flow); employees can update their own availability (admin notified with diff); employees can acknowledge assigned shifts

**Addresses:** ESS-02, ESS-03, ESS-04

**Avoids:** Pitfall 9 (notification spam) — implement notification dedup/cooldown before wiring approval notifications

**Research flag:** Standard patterns — follows existing RBAC + notification architecture. Decision needed at phase planning: use `python-statemachine 2.6` or inline transition dict for absence status transitions. Both are valid; pick one and apply it consistently.

---

### Phase 5: PWA

**Rationale:** Entirely frontend-side with no backend dependencies. Can be developed in parallel with Phases 2-4. Sequenced here for clarity; PWA-01 (manifest) is a one-file change that could ship at any point.

**Delivers:** App installable to home screen (Android Chrome + iOS with hint banner); offline calendar/shift view with "data may be outdated" indicator; push notifications work when app is closed; mobile-optimized touch targets

**Addresses:** PWA-01, PWA-02, PWA-03, PWA-04, Pitfall 7 (stale offline data), Pitfall 8 (dead push subscriptions), Pitfall 17 (auth interceptor bypass)

**Avoids:** Serving stale payroll data offline (NetworkOnly for `/api/v1/payroll/*` and `/api/v1/auth/*`); auth interceptor bypassed by service worker cache

**Research flag:** Verify webpack (not Turbopack) is active in `next.config.mjs` before starting — Serwist requires webpack and will silently fail with Turbopack. iOS Background Sync support is LOW confidence; verify MDN compatibility at implementation time and default to graceful degradation.

---

### Phase 6: Shift Swap (ESS-01)

**Rationale:** Highest-complexity feature. Deferred to last because it requires a new model, multi-party workflow, compliance pre-validation, and race condition handling. Building on proven ESS patterns (Phase 4) and wired audit trail (Phase 3) reduces risk significantly.

**Delivers:** Employees can request shift swaps; peer acceptance step; admin approval with compliance pre-check; atomic shift reassignment; auto-expiry of stale requests after 48h; existing claim endpoint race condition fixed

**Addresses:** ESS-01, Pitfall 3 (race condition — also fixes the existing `/shifts/{id}/claim` race as a prerequisite)

**Avoids:** Simultaneous swap approvals overwriting each other (SELECT FOR UPDATE on both shift rows)

**Research flag:** The multi-party status machine (`pending_peer → pending_admin`) has nuance in the notification flow when peer declines vs. when admin rejects. Define the exact notification matrix (who gets notified at each transition) at planning time before coding.

---

### Phase 7: RBAC Audit + Cleanup

**Rationale:** Independent of all other phases. RBAC audit (SEC-02) is a grep-and-fix pass that has no dependencies and does not block anything. DEBT-03, DEBT-05, and SEC-03 are similar cleanups.

**Delivers:** All endpoints verified for correct RBAC dependencies; demo data isolated to `demo` tenant; legacy `send_hourly_reminders` Celery task removed; Pydantic strict mode applied to write schemas

**Addresses:** SEC-02, SEC-03, DEBT-03, DEBT-05

**Research flag:** No research needed. SEC-02 is a systematic review pass.

---

### Phase Ordering Rationale

- **Security foundation first (Phase 1):** The deploy order race means any subsequent migration can cause production 500s. The API key scope bug means every feature that ships assumes security guarantees that don't exist.
- **Payroll correctness before audit (Phase 2 before Phase 3):** Auditing wrong data creates a false compliance trail, which is worse than no audit at all.
- **Audit before ESS approvals (Phase 3 before Phase 4):** Every approval transition must emit an audit entry; the shared helper must exist and be tested before workflows depend on it.
- **Simple ESS before shift swap (Phase 4 before Phase 6):** ESS-04 (shift acknowledgment) is a direct prerequisite for ESS-01. Patterns proven in Phase 4 reduce Phase 6 risk.
- **PWA parallelizable (Phase 5):** Frontend-only work; can proceed in parallel with Phase 2-4 backend work if capacity allows. Do not block or be blocked.

### Research Flags

Needs attention during planning:
- **Phase 4/6:** Choose `python-statemachine 2.6` vs. inline transition dict before coding — use one approach consistently across both absence requests and shift swap
- **Phase 5:** Verify webpack (not Turbopack) before starting Serwist integration; check iOS Background Sync MDN compatibility at implementation time
- **Phase 6:** Define the full notification matrix for shift swap state transitions before coding

Standard patterns (no additional research needed):
- **Phase 1:** PyJWT migration, `token_version` pattern, `require_scope()` dependency factory
- **Phase 2:** ContractHistory query refactor, §3b cap fix
- **Phase 3:** Application-level audit log, SQLAlchemy async patterns, DSGVO retention
- **Phase 7:** RBAC grep-and-fix pass

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | PyJWT and Serwist verified against official FastAPI and Next.js docs; token_version approach verified against established JWT best practices |
| Features | HIGH | Feature analysis grounded in direct VERA codebase inspection (CONCERNS.md); no speculative features — all gaps are confirmed present |
| Architecture | HIGH | Build order derives from verifiable code dependencies in the existing codebase; patterns consistent with SQLAlchemy async official documentation |
| Pitfalls | HIGH | Top pitfalls sourced from direct codebase inspection (CONCERNS.md) plus official SQLAlchemy async docs and official German statutory sources (§3b EStG, §257 HGB) |

**Overall confidence:** HIGH

### Gaps to Address

- **python-statemachine vs. inline transition dict:** ARCHITECTURE.md recommends inline dicts; STACK.md recommends the library. Both work; the team should decide at Phase 4 planning and apply it consistently. Recommendation: use the library for guard enforcement, but only if the team is comfortable adding a dependency; inline dicts are sufficient for two simple linear flows.

- **§3b EStG 40% enhanced night rate (00:00–04:00):** PROJECT.md explicitly defers this to Steuerberater review. Do not implement silently. Add a `# TODO: Steuerberater confirm enhanced night rate 40% per BMF Lohnsteuerhandbuch` comment in `payroll_service.py` during Phase 2.

- **iOS Background Sync support:** Research flagged LOW confidence on current iOS support status. At Phase 5 implementation, check MDN compatibility table for the current iOS version. Graceful degradation ("you are offline, try again") is the correct fallback — no backend implications.

- **Minijob two-month exception tracking (Pitfall 13):** Not in Milestone 1 scope but is a known correctness gap — the compliance service fires false-positive warnings for the valid statutory 2-month exception. Add to Milestone 2 backlog.

- **Push subscription `last_used_at` / `failure_count` columns:** Recommended by Pitfall 8 but not in any current Milestone 1 scope item. Should be included in Phase 5 planning to properly handle dead VAPID subscription cleanup.

---

## Sources

### Primary (HIGH confidence)

- `/home/spro/development/VERA/.planning/codebase/CONCERNS.md` — direct codebase audit, 2026-03-27
- Next.js official PWA docs: https://nextjs.org/docs/app/guides/progressive-web-apps (updated 2026-03-25)
- Serwist getting started: https://serwist.pages.dev/docs/next/getting-started
- PyJWT PyPI: https://pypi.org/project/PyJWT/ (v2.12.1, released 2026-03-13)
- FastAPI full-stack template JWT migration PR: https://github.com/fastapi/full-stack-fastapi-template/pull/1203
- FastAPI OAuth2 scopes: https://fastapi.tiangolo.com/advanced/security/oauth2-scopes/
- Pydantic v2 strict mode: https://docs.pydantic.dev/latest/concepts/strict_mode/
- German §3b EStG: https://www.gesetze-im-internet.de/estg/__3b.html
- SQLAlchemy async event listener constraints: https://github.com/sqlalchemy/sqlalchemy/discussions/7152 and https://github.com/sqlalchemy/sqlalchemy/discussions/8913
- MDN Web Push API: https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Tutorials/js13kGames/Re-engageable_Notifications_Push

### Secondary (MEDIUM confidence)

- python-statemachine docs: https://python-statemachine.readthedocs.io/
- slowapi GitHub: https://github.com/laurentS/slowapi
- JWT revocation strategies: https://www.michal-drozd.com/en/blog/jwt-revocation-strategies/
- PostgreSQL audit log schema: https://medium.com/@sehban.alam/lets-build-production-ready-audit-logs-in-postgresql-7125481713d8
- Minijob two-month exception: https://zmi.de/en/lexikon/mini-job/
- DSGVO data retention (German law perspective): https://www.taylorwessing.com/en/global-data-hub/2024
- Deputy / Homebase feature comparisons: https://connecteam.com/homebase-vs-deputy/
- Shift swap workflow best practices: https://www.myshyft.com/blog/shift-swap-request-workflows/

### Tertiary (LOW confidence)

- iOS Background Sync API current support — verify at MDN at Phase 5 implementation time
- §3b 40% enhanced night rate applicability — requires Steuerberater confirmation for VERA's specific context

---
*Research completed: 2026-03-27*
*Ready for roadmap: yes*
