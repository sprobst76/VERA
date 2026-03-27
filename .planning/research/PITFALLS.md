# Domain Pitfalls

**Domain:** Payroll + shift planning system (live production, German labor law, PAB Arbeitgebermodell)
**Researched:** 2026-03-27
**Milestone scope:** Security hardening, audit trails, employee self-service, PWA

---

## Critical Pitfalls

Mistakes that cause rewrites, data corruption, or legal liability.

---

### Pitfall 1: Audit Log Written in the Same Transaction as the Mutating Operation

**What goes wrong:** If the audit log INSERT and the business-data mutation share a single
database transaction, a rollback of the business operation also rolls back the audit record.
You end up with gaps: the action happened, was retried, and ultimately succeeded — but the
first failed attempt is invisible.

Conversely, if you write the audit entry after `await db.commit()` and the process dies
between the commit and the audit write, you have a committed business change with no audit
record at all.

**Why it happens:** The natural instinct is to add `db.add(AuditEntry(...))` immediately
before or after the business object mutation and let both commit together. This feels atomic,
but creates the rollback-erases-audit problem.

**Consequences:** Payroll data changed with no immutable record. In a DSGVO audit, missing
change records for Gehaltsdaten are a compliance violation. Stefan cannot reconstruct who
changed an hourly rate if the operation was attempted, failed, and retried.

**Prevention:**
- Write the audit entry in the SAME transaction as the business change. Accept that a
  rollback also rolls back the audit entry — that is correct behavior (a rolled-back change
  never happened). The critical thing is that every COMMITTED business change has a committed
  audit entry.
- Use SQLAlchemy `after_commit` hook on the session (not `after_flush`) to emit any
  out-of-band notifications, because `after_flush` fires before commit and attributes may
  still be None if the object was just `db.add()`-ed.
- Never write audit entries to a separate DB connection after the main transaction commits —
  that window is where you lose records.

**Detection:** Write a test that rolls back a business transaction and verifies no audit entry
was written. Write a test that simulates a process kill after commit and verifies the audit
entry exists.

**Phase:** AUDIT-01, AUDIT-02 (Audit Trail implementation)

---

### Pitfall 2: SQLAlchemy Async Event Listeners Cannot Do Lazy I/O

**What goes wrong:** Adding `@event.listens_for(Session, "after_flush")` or attribute event
listeners that attempt to `await db.execute(...)` inside the listener body raises
`MissingGreenlet: greenlet_spawn has not been called`. SQLAlchemy async sessions prohibit
any implicit I/O from within synchronous event callbacks.

This specifically bites audit logging patterns that try to load the "before" state of an
object inside an ORM event listener.

**Why it happens:** SQLAlchemy 2.0 async is built on greenlets. Event listener callbacks are
synchronous call sites that SQLAlchemy invokes from its internal state machine. They run
outside the greenlet context expected by the async driver, so any attempt to issue a query
deadlocks or raises immediately.

**Consequences:** The audit trail implementation either crashes silently, raises a 500 on
every write, or (if the exception is swallowed) produces incomplete audit records.

**Prevention:**
- Capture the "before" snapshot BEFORE the mutation, in the async endpoint code, while you
  still have the loaded ORM object with its old values. Pass the snapshot explicitly to the
  audit write function.
- Do NOT rely on ORM event listeners for audit captures. Use explicit helper functions
  called from endpoints: `await _write_audit(db, user, entity, action, before, after)`.
- The `after_commit` hook CAN be used for fire-and-forget side effects (e.g., enqueuing a
  Celery task), but must not perform any DB I/O directly.

**Detection:** Write a test that patches `db.execute` inside an event listener body and
verifies `MissingGreenlet` is not raised.

**Phase:** AUDIT-01 (Audit Trail implementation)

---

### Pitfall 3: Shift Claim / Shift Swap Race Condition Without SELECT FOR UPDATE

**What goes wrong:** Two employees simultaneously request the same open shift (or submit
swap requests targeting the same vacancy). Both read `shift.employee_id == None`, both pass
the check, both commit. PostgreSQL READ COMMITTED isolation allows this — the second commit
overwrites the first without error.

The existing codebase has this exact bug documented in `POST /shifts/{id}/claim`
(CONCERNS.md, Data Integrity section). Shift swap will introduce the same problem at a
higher level: two swap requests for the same target shift can both get approved before
either commits.

**Why it happens:** The check-then-act pattern without a row-level lock is the default
approach when translating business logic to SQL. It works in single-user systems and
low-traffic apps but fails under any concurrency.

**Consequences:** One employee's claim is silently overwritten. No error, no notification.
The losing employee believes they have the shift; the system disagrees. Payroll runs against
the wrong assignment.

**Prevention:**
- Use `.with_for_update()` on the shift SELECT inside the claim/swap approval transaction:
  `select(Shift).where(Shift.id == shift_id).with_for_update()`
- Hold the lock for the entire check-and-update operation within one transaction.
- For the shift swap approval, lock BOTH the requesting shift and the target shift rows.
- Add a DB-level unique constraint as a backstop: the current absence of a unique constraint
  on `(employee_id, date, start_time)` means even with the lock fixed, a migration bug could
  create duplicates.

**Detection:** Write a concurrent test that fires two simultaneous claim requests and verifies
only one succeeds with HTTP 200 and the other gets HTTP 409.

**Phase:** ESS-01 (Shift swap), and should also fix the existing claim endpoint before
ESS-01 ships.

---

### Pitfall 4: Refresh Token Revocation Gap After Password Change

**What goes wrong:** An attacker who steals a refresh token before a password change retains
7-day access after the account is secured. `POST /auth/change-password` updates the bcrypt
hash but does not invalidate any issued refresh tokens. This is documented in CONCERNS.md.

**Why it happens:** Stateless JWTs are by design irrevocable. The standard mitigation
(token version / jti denylist) requires either a DB lookup on every refresh or a Redis
denylist, which feels like overhead for a small app. It gets skipped in MVP implementations.

**Consequences:** Compromised account cannot be fully locked out. For a payroll app holding
real Gehaltsdaten, this is a significant risk: an attacker with a stolen refresh token can
exfiltrate salary data for up to 7 days after the user changes their password.

**Prevention:**
- Add a `token_version` integer column to the `users` table (migration required, idempotent).
- Embed `token_version` in the refresh token payload at issue time.
- On `/auth/refresh`, verify `token_version` matches the DB value. Reject mismatches with
  HTTP 401.
- Increment `token_version` on password change, logout-all-devices, and account compromise.
- This avoids a Redis denylist (no additional infrastructure) while achieving revocation.

**Detection:** Test: change password, attempt to use the old refresh token, assert HTTP 401.

**Phase:** SEC-05 (Session management hardening)

---

### Pitfall 5: API Key Scope Bypass — Read-Only Key Has Admin Rights

**What goes wrong:** The Shiftjuggler sync script and any future n8n/automation integration
uses X-API-Key auth. Currently, any valid key resolves to an admin user context regardless
of the `scopes` field (documented in CONCERNS.md and PROJECT.md as the highest-priority
security gap). A stolen read-only key can DELETE employees or modify payroll.

**Why it happens:** Scope checking was deferred when API keys were first built. The scopes
are stored and displayed correctly in UI, creating a false sense of security.

**Consequences:** External integrations with minimal-privilege intent (Shiftjuggler sync:
write shifts only) have de-facto unrestricted admin access. If the sync script environment
is compromised, an attacker has full tenant admin access via a credential that wasn't
intended to have that power.

**Prevention:**
- Add scope enforcement in `deps.py` `get_current_user` after the SHA-256 lookup:
  determine HTTP method → derive required scope → check key scopes list → 403 if insufficient.
- Scope mapping: GET → `read`, POST/PUT/PATCH/DELETE → `write`, admin endpoints → `admin`.
- Do NOT break the existing Shiftjuggler sync integration. Confirm the sync key has
  `write` scope before enforcement goes live.
- Add a `BackwardCompatibleScopeCheck` that logs a warning but does not block for a grace
  period, to allow existing integrations to catch up.

**Detection:** Test: create a read-scope-only API key, attempt a DELETE operation, assert
HTTP 403.

**Phase:** SEC-01 (API key scope enforcement — first item in security phase)

---

### Pitfall 6: ContractHistory Mirror Divergence Causes Silent Payroll Errors

**What goes wrong:** `Employee.hourly_rate`, `contract_type`, and `weekly_hours` are mirror
fields maintained by `_sync_employee_mirror()`. If a `ContractHistory` row is edited
directly (admin SQL, migration, or the `assign_contract_type`-without-`valid_from` bug),
the mirror diverges from the active history entry. Payroll, compliance, and PDF generation
all read from mirror fields — not from `ContractHistory`.

This means a Minijob employee whose mirror says `contract_type = "teilzeit"` will never
have their monthly 556€ limit checked by `ComplianceService`. Wrong surcharge base rate
silently flows into payroll PDFs.

**Why it happens:** Denormalized mirrors are a common optimization that becomes a liability
when they diverge. The sync function is only called through the API layer — direct DB
access bypasses it.

**Consequences:** Incorrect payroll PDFs delivered to employees. Minijob limit violations
undetected by compliance checks. Legal liability for the PAB employer. DEBT-01 and DEBT-02
in PROJECT.md.

**Prevention:**
- Phase DEBT-01: Derive `contract_type` and `hourly_rate` at query time from the current
  `ContractHistory` entry (where `valid_to IS NULL`) instead of reading mirror fields.
  Remove or deprecate mirror fields after migration.
- Interim: Add a DB CHECK constraint or trigger that keeps the mirror in sync. SQLAlchemy
  hybrid properties that compute from history at read time are another option.
- For `assign_contract_type`: make `valid_from` mandatory or default to today, always write
  a `ContractHistory` entry (DEBT-02).

**Warning signs:** Payroll PDF shows different rate than ContractHistory UI tab for the
same employee.

**Phase:** DEBT-01, DEBT-02 (Critical tech debt — must precede any payroll-touching features)

---

## Moderate Pitfalls

---

### Pitfall 7: PWA Service Worker Caches Stale Payroll and Shift Data

**What goes wrong:** A service worker using a Cache-First or Stale-While-Revalidate strategy
for API responses will serve a cached payroll entry or shift list to an employee even after
the admin has updated it. An employee sees "8h shift on Thursday" offline; the admin has
already moved it to Friday. Worse: a confirmed payroll PDF cached offline shows last
month's figures.

**Why it happens:** Next.js PWA libraries (next-pwa, Serwist) apply Stale-While-Revalidate
by default to most routes. Without explicit per-route cache strategy configuration, API
responses get cached with the same strategy as static assets.

**Consequences:** Employees act on stale shift data. Push notifications announce a shift
that the service worker's cache says doesn't exist. Payroll figures shown offline are wrong.

**Prevention:**
- For API routes (`/api/v1/*`): use Network-First strategy. Cache the response for offline
  fallback only, never serve stale.
- Explicit exclusion in Workbox runtime caching config:
  `{ urlPattern: /\/api\/v1\/payroll/, handler: "NetworkOnly" }` — payroll data must never
  be served from cache.
- For the calendar and shift list: Network-First with a 3-second timeout, then cache
  fallback showing a "data may be outdated" banner.
- Static app shell (JS bundles, CSS): Cache-First is correct here.
- On service worker activation, clear all API caches from the previous version.

**Warning signs:** User reports "I can see a shift that was deleted" after reconnecting.

**Phase:** PWA-02 (Offline capability implementation)

---

### Pitfall 8: Push Subscription Endpoints Become Invalid Silently

**What goes wrong:** Web Push VAPID subscriptions stored in `push_subscription` table
expire, are revoked by the user (notification permission withdrawn), or the browser
rotates the endpoint URL. The push server receives HTTP 410 (Gone) or HTTP 404 from the
push service. If the notification service does not handle these responses and delete the
stale subscription, every subsequent push attempt for that user silently fails and the
table accumulates dead entries.

**Why it happens:** The notification service sends and logs success/failure, but error
handling for specific push service HTTP error codes is often not implemented in initial
versions.

**Consequences:** Employees miss shift reminders. Admins cannot see why. The `notification_log`
shows "sent" because the HTTP POST to the push service was made, but the subscription was
dead. Celery task failure silently swallowed (existing CONCERNS.md reliability issue).

**Prevention:**
- After each push attempt, inspect the push service HTTP response code:
  - 410 Gone, 404 Not Found: delete the `push_subscription` row immediately.
  - 429 Too Many Requests: back off, retry with Celery.
  - 201 Created: log success.
- Add a `last_used_at` and `failure_count` column to `push_subscription`. After N
  consecutive failures, deactivate the subscription and notify the user via email/Telegram.
- iOS PWA push requires the app to be installed to home screen (iOS 16.4+). Document this
  for employees using iPhones.

**Detection:** Test: mock a 410 response from the push service, assert the subscription
row is deleted.

**Phase:** PWA-03 (Push notification improvement)

---

### Pitfall 9: Approval Workflow Notification Spam on Multi-Stage State Changes

**What goes wrong:** An ESS-01 shift swap request goes through states: `requested` →
`pending_admin` → `approved` / `rejected`. If a notification is sent on every state
transition, and multiple admins review the same request, Stefan (admin) receives 3-5
notifications for a single swap that takes 2 minutes to resolve. With 7 employees, a
Monday morning with 3 open swap requests generates 15+ notifications before 9am.

**Why it happens:** Notification hooks are wired to state change events, which is correct
in isolation. The problem emerges at the aggregate level — no deduplication or batching.

**Consequences:** Admin turns off notifications entirely to stop the spam. This defeats the
purpose of the notification system for actual critical alerts (Compliance violations, payroll
approvals).

**Prevention:**
- Group notifications: one notification per swap request to admin, not one per state
  change.
- Add notification cooldown / dedup: if a notification for the same `entity_type +
  entity_id` was sent in the last 5 minutes, suppress the duplicate.
- Use a single "3 requests pending your review" digest notification instead of 3 separate
  push notifications.
- Implement the `NotificationPreferences` model (already in schema) to allow granular
  per-event-type opt-out.

**Phase:** ESS-01, ESS-02 (Employee self-service approval flows)

---

### Pitfall 10: Alembic Migration Runs After API Starts (Existing Deployment Race)

**What goes wrong:** The CI/CD pipeline starts `vera-api` 5 seconds before running
`alembic upgrade head`. If the new API version requires a new column (e.g., `token_version`
on `users`), requests during those 5 seconds hit SQLAlchemy with an `UndefinedColumn`
exception. Users see 500 errors. This is documented in CONCERNS.md.

This race becomes critical for Milestone 1: SEC-05 adds `token_version` to `users`,
AUDIT-01 adds an `audit_log` table, ESS-01 adds a `shift_swap_requests` table. Every one
of these migrations, if run after the new API starts, causes 500s.

**Why it happens:** The deploy script was written for speed ("zero downtime") but the
ordering was inverted. The old API can run against the new schema safely (additive changes);
the new API cannot run against the old schema.

**Prevention:**
- Fix the deploy order BEFORE Milestone 1 starts: run migrations FIRST, then restart
  the API. The 5-second gap and the old "start then migrate" order must be corrected.
- Correct sequence: `docker compose up -d vera-api` (OLD image) → wait for health →
  `alembic upgrade head` → `docker compose up -d vera-api` (NEW image).
- OR: run a one-shot migration container before starting the API container.
- All new migrations continue to use the `inspect()` idempotency guard.

**Detection:** Deploy with the new `token_version` migration and observe no 500 errors
during the deploy window.

**Phase:** Must be fixed in Phase 1 before any schema-changing features land.

---

### Pitfall 11: DSGVO / GDPR Constraint on Audit Log Retention

**What goes wrong:** An audit log that records WHO accessed WHAT payroll data at WHAT time
is itself personal data under DSGVO. Under German law (§26 BDSG + DSGVO Article 5(1)(e)),
personal data may only be retained as long as necessary for the purpose. An audit log that
retains every access to every salary figure indefinitely creates a secondary DSGVO liability.

**Why it happens:** Audit logs are written to document accountability (a legitimate purpose)
but retention periods are rarely defined at implementation time.

**Consequences:** DSGVO audit by Datenschutzbehörde flags the system. Mitarbeiter exercise
their right of access (Art. 15 DSGVO) and receive a full history of who viewed their
payroll data — potentially exposing admin access patterns.

**Prevention:**
- Define retention policy at build time: 2 years for payroll-related audit entries
  (matching German commercial record retention minimums for wage records: §257 HGB).
- Add a `retained_until` column or a periodic Celery task that deletes audit entries older
  than the policy window.
- Do NOT log the actual payroll values in the audit entry body — log the fact that a
  calculation was run and by whom, not the resulting Bruttolohn in plaintext. Reference the
  `PayrollEntry.id` instead.
- For delete operations: log `before_snapshot` without PII where possible, or with a
  separate permission gate on the audit viewer endpoint.

**Phase:** AUDIT-01, AUDIT-02 (Audit Trail — design retention at the same time as the
log schema)

---

### Pitfall 12: §3b EStG Surcharge Calculation — The 50 Euro Stundensatz Cap

**What goes wrong:** §3b EStG grants tax-free status to night/Sunday/holiday allowances
only when calculated against a base wage capped at 50 EUR/hour (since 2004). If an
employee's actual hourly rate exceeds 50 EUR, the tax-free portion of the allowance is
still calculated against 50 EUR, not the actual rate.

VERA's current `payroll_service.py` applies percentage rates to the actual `hourly_rate`
without capping at 50 EUR. For Stefan's Minijob employees (typically 12-15 EUR/hr), this
is currently harmless. However, if a Teilzeitkraft's rate rises above 50 EUR (unlikely but
legally possible), the calculation produces an incorrect tax-free amount — overstating the
tax-free portion.

Additionally: the §3b EStG "Nacht" period is 23:00–06:00 (25% rate), but there is also an
enhanced rate for the core night period (00:00–04:00). VERA currently uses one flat 25%
night rate. The BMF Lohnsteuerhandbuch specifies a 40% rate for 00:00–04:00 on working
nights. Whether VERA should implement the enhanced rate depends on Steuerberater guidance
(PROJECT.md: "Zuschlagsberechnung von Steuerberater prüfen lassen").

**Why it happens:** Edge cases that don't affect current employees are not tested. The
50 EUR cap is a 2004 change that only matters for higher-wage workers; Minijob employees
are always under the cap.

**Prevention:**
- Apply the 50 EUR cap: `effective_base = min(employee.hourly_rate, 50.0)` before
  calculating surcharge amounts.
- Add a test with an employee at exactly 50 EUR/hr and at 60 EUR/hr to verify capping.
- Flag the 40% enhanced night rate as a "TODO: Steuerberater confirm" comment in code —
  do not implement silently.

**Phase:** DEBT-01 payroll service hardening (or as a standalone fix before AUDIT-02)

---

### Pitfall 13: Minijob Annual Limit — The "Two-Month Exception" Not Tracked

**What goes wrong:** The 556 EUR/month Minijob limit has a statutory exception: the limit
may be exceeded in up to two calendar months per year, provided those months do not exceed
2x the limit (1,112 EUR). VERA's compliance check fires a warning on any month exceeding
556 EUR, which produces false positives during the valid two-month exception.

More critically: VERA does not track how many exception months have been used in the
current calendar year. If two months are already used, the third overrun is an actual
violation — but the compliance check treats it identically to the first overrun.

**Why it happens:** The two-month exception rule is not widely known and is not in the
current compliance service.

**Consequences:** Stefan (admin) either ignores all 556 EUR warnings (because some are
false positives) and misses real violations, or calls his Steuerberater every time a
warning fires. Legal risk: inadvertent reclassification of Minijob to Midijob with
retroactive social security contributions.

**Prevention:**
- Track `exception_months_used` per employee per calendar year in the compliance check.
- Month 1 and 2 of overrun (≤1,112 EUR): WARNING with "exception month N/2 used" message.
- Month 3 of overrun: ERROR — "annual exception limit exceeded, reclassification risk".
- Persist the exception month count in `PayrollEntry` or as a derived query on approved
  entries.

**Phase:** SEC-02/DEBT area — Compliance service correctness review

---

## Minor Pitfalls

---

### Pitfall 14: python-jose CVE and Deprecated Passlib

**What goes wrong:** `python-jose==3.3.0` has CVE-2024-33663 (algorithm confusion). VERA
already mitigates this by passing `algorithms=[settings.ALGORITHM]` in `decode_token()`,
but the library is unmaintained. Any future CVE will not be patched upstream.

`passlib 1.7.4` is also in maintenance mode. The bcrypt shim has had compatibility warnings
with newer bcrypt versions.

**Prevention:**
- Migrate to `PyJWT>=2.8.0` (MEDIUM confidence: API is similar, migration is low-risk).
- Use `bcrypt` directly for password hashing instead of through passlib.
- Do this in the security hardening phase, not as an urgent hotfix (the existing mitigation
  is adequate for now).

**Phase:** SEC-04 (Secrets and dependency audit)

---

### Pitfall 15: BW Schulferien Hardcoded Only Through Summer 2026

**What goes wrong:** `BW_SCHOOL_HOLIDAYS_2025_26` expires in September 2026. After that,
`is_school_holiday()` returns False for all dates. Recurring shifts configured to skip
school holidays will generate unintended shifts during the 2026/27 school holidays.

**Prevention:**
- Add 2026/27 BW Schulferien to the hardcoded list before July 2026 (calendar year 2026
  school holiday release is typically in spring).
- OR make school holidays a tenant-configurable list in the Admin UI (longer-term fix).
- Add a CI check or a Celery periodic task that alerts when the most recent school holiday
  end date is within 60 days.

**Phase:** DEBT-04 (should be resolved in Milestone 1 since it expires within 5 months)

---

### Pitfall 16: CORS Missing X-API-Key Header

**What goes wrong:** VERA's CORS config only allows `Authorization` and `Content-Type`
headers. Any browser-based tool (e.g., a custom admin panel, n8n browser automation) that
sends `X-API-Key` will be blocked by CORS preflight, even though server-to-server calls
work fine. The developer spends time debugging a "works in Postman, fails in browser"
issue.

**Prevention:**
- Add `"X-API-Key"` to `allow_headers` in `backend/app/main.py` CORS configuration.
- Document whether browser-based API key usage is supported or intentionally blocked.

**Phase:** SEC-04 (CORS hardening)

---

### Pitfall 17: Service Worker Installation Breaks Auth Interceptor

**What goes wrong:** The TanStack Query axios client in `lib/api.ts` has a response
interceptor that handles 401 errors by attempting a token refresh and retrying. Once a
service worker is active, some requests may be served from cache before reaching the axios
interceptor. A cached response with a 401 payload will not trigger the refresh interceptor,
leaving the user stuck on a stale error state.

**Why it happens:** The service worker intercepts network requests at a lower level than
the axios interceptor. If the cache layer returns a synthetic or stale 401, the interceptor
never fires.

**Prevention:**
- All auth-related routes (`/api/v1/auth/*`, `/api/v1/users/me`) must be excluded from
  service worker caching entirely — `NetworkOnly` handler.
- Test the auth refresh flow with the service worker active and verify the interceptor
  still fires on a real 401.

**Phase:** PWA-01 (Service worker installation)

---

## Phase-Specific Warnings

| Phase / Feature | Likely Pitfall | Mitigation Priority |
|---|---|---|
| AUDIT-01 (Audit log table) | Write in same tx as mutation; async event listener MissingGreenlet | Design before code: explicit helper function pattern |
| AUDIT-02 (Payroll audit) | DSGVO: logging Bruttolohn in plaintext | Log entity reference, not value |
| SEC-01 (API key scopes) | Breaks Shiftjuggler sync if wrong scope assigned | Verify existing key scopes before enforcement |
| SEC-05 (Token revocation) | 7-day refresh token window after password change | `token_version` migration must be idempotent |
| ESS-01 (Shift swap) | Race condition on simultaneous swap approvals | SELECT FOR UPDATE on shift rows |
| ESS-02 (Absence request) | Notification spam on multi-admin tenant | Dedup cooldown before wiring notifications |
| DEBT-01 (Contract mirror) | Payroll reads mirror, not live history | Must fix before any payroll-touching feature |
| DEBT-02 (assign_contract_type) | No ContractHistory entry on assign | Make valid_from mandatory or default to today |
| DEBT-04 (Schulferien 2026/27) | Expires September 2026 — 5 months away | Fix in Milestone 1, not later |
| PWA-01 (Service worker install) | Auth interceptor bypassed by SW cache | NetworkOnly for all /api/v1/auth/* routes |
| PWA-02 (Offline caching) | Stale payroll/shift data served offline | NetworkOnly for /api/v1/payroll, NetworkFirst for shifts |
| PWA-03 (Push notifications) | Dead VAPID endpoints silently accumulate | Handle 410 Gone → delete subscription |
| Deploy order (all schema changes) | New API starts before migration runs | Fix deploy order FIRST, before Milestone 1 |

---

## Sources

- `/home/spro/development/VERA/.planning/codebase/CONCERNS.md` (codebase audit 2026-03-27) — HIGH confidence, direct inspection
- `/home/spro/development/VERA/.planning/PROJECT.md` — HIGH confidence, project requirements
- SQLAlchemy 2.1 documentation: ORM Events with asyncio — [Discussion #7152](https://github.com/sqlalchemy/sqlalchemy/discussions/7152), [Discussion #8913](https://github.com/sqlalchemy/sqlalchemy/discussions/8913) — HIGH confidence
- German §3b EStG text: [gesetze-im-internet.de](https://www.gesetze-im-internet.de/estg/__3b.html), [sevdesk.de Lohnsteuerhandbuch](https://sevdesk.de/ratgeber/buchhaltung-finanzen/lohnbuchhaltung/lohnsteuer/steuerfreie-zuschlaege/) — HIGH confidence (official source)
- Minijob 2025 limits and two-month exception: [zmi.de](https://zmi.de/en/lexikon/mini-job/), [meinbavaria.de](https://www.meinbavaria.de/new-rules-mini-jobs-germany-what-changes/) — HIGH confidence
- JWT revocation patterns: [python-jose CVE](https://github.com/IndominusByte/fastapi-jwt-auth/issues/65) — MEDIUM confidence (cross-referenced with CONCERNS.md)
- PWA cache strategy guidance: [MDN Web Docs](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Caching), [Workbox docs](https://web.dev/learn/pwa/workbox) — HIGH confidence (official sources)
- Web Push 410 handling: [MDN Push API](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Tutorials/js13kGames/Re-engageable_Notifications_Push) — HIGH confidence
- DSGVO retention: [Taylor Wessing German data law guide](https://www.taylorwessing.com/en/global-data-hub/2024/uk-gdpr---what-you-really-need-to-know/top-ten-needtoknows-for-handling-employee-data-a-german-law-perspective) — MEDIUM confidence
- next-pwa App Router limitations: [Vercel discussion #82498](https://github.com/vercel/next.js/discussions/82498) — MEDIUM confidence (community source)
