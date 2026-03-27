# Feature Landscape — VERA Milestone 1

**Domain:** Workforce management / shift scheduling / payroll for small employer (PAB model)
**Researched:** 2026-03-27
**Scope:** Employee self-service, audit trail, PWA, security hardening
**Overall confidence:** HIGH (all major claims verified against official docs or multiple authoritative sources)

---

## Context: What Already Exists

VERA already has a solid foundation. Milestone 1 is additive, not foundational. Several structures are partially in place:

- `AuditLog` model exists in `backend/app/models/audit.py` with correct schema (entity_type, action, old_values, new_values, ip_address) — but nothing writes to it yet and there is no API to read it
- `EmployeeAbsence` model has a `status` field with `pending | approved | rejected` workflow — the admin approval side works; the employee-initiated request side does not
- `ApiKey` model has a `scopes: JSON` field — but `deps.py` never checks it, so any key has full access
- Web Push VAPID infrastructure exists (`push_subscription.py`, `notification_service.py`) — but service worker scope is minimal
- No `ShiftSwap` model exists anywhere; shift acknowledgment has no field in the `Shift` model

---

## 1. Employee Self-Service

### Table Stakes

Features that employees in mature scheduling tools (Deputy, When I Work, Homebase) expect. Absence without these breaks trust in the self-service claim.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| View own schedule | Baseline — every scheduling tool has this | Low | Already exists via `/calendar` and `/shifts` |
| Request absence (vacation/sick) | Standard in Deputy, Homebase, When I Work | Low-Med | Model exists; employee-initiated flow missing. Need: employee creates `pending` absence, admin gets notification |
| Receive approval/rejection notification | Without this, absence requests feel like a black hole | Low | NotificationService already handles this pattern; just needs to fire on status change |
| Update own availability preferences | Employees know their schedule better than admins | Low | Field exists on `Employee.availability_prefs`; currently admin-only write |
| Acknowledge/confirm assigned shift | Replaces informal confirmation via WhatsApp | Low | Needs new field on `Shift`: `employee_acknowledged_at` (nullable DateTime) |

### Differentiators

Features that set VERA apart from a generic scheduling tool given VERA's specific context (PAB model, 7 employees, German labor law).

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Shift swap request with compliance pre-check | Most tools let swaps happen without checking ArbZG §5 rest period — VERA can block legally invalid swaps | High | New `ShiftSwap` model needed. Pre-swap compliance check via `ComplianceService` before admin approval |
| Shift swap smart matching | Only suggest swap partners who are qualified AND available AND whose swap won't violate minijob limits | Med | Uses `Employee.qualifications`, `availability_prefs`, and `PayrollService.ytd_gross` |
| Availability change diff notification to admin | Show admin exactly what changed (was: Mon-Fri, is: Mon-Thu) rather than a generic "availability updated" | Low | Pure frontend diff; no backend change needed |
| Swap request auto-expiry | Unanswered swap requests auto-reject after 48h | Low | Celery beat task; prevents stale pending requests |

### Anti-Features

Features explicitly NOT to build for Milestone 1.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Employee-initiated time correction | Payroll integrity risk — time corrections touch billing data | Time corrections remain admin/manager only; employees acknowledge planned shifts |
| Direct shift self-assignment (open shift bidding) | With 7 employees and 1 admin, open bidding adds complexity without value | Admin assigns shifts; employees can only swap assigned shifts |
| Employee salary/payroll self-service | GDPR and PAB financial sensitivity; employees can already view their own payslip | Keep payroll read-only for `employee` role as-is |
| In-app messaging/team chat | Scope creep; Telegram notifications already fill the communication need | Continue using Telegram + email notifications |
| Early wage access | Not relevant to PAB model; Stefan pays on fixed monthly cycle | Out of scope |

### Feature Dependencies

```
ESS-02 (absence request by employee)
  → requires: notification on status change (partial: NotificationService exists)
  → enables:  AUDIT-01 (audit log entry for absence creation)

ESS-01 (shift swap request)
  → requires: ESS-04 (shift acknowledgment) — you can only swap a shift you've acknowledged
  → requires: new ShiftSwap model + API
  → requires: ComplianceService.check_rest_period() called on proposed swap
  → enables:  AUDIT-01 (audit entries for swap create/approve/reject)

ESS-03 (availability update by employee)
  → requires: RBAC change — employees can PATCH their own availability_prefs
  → enables:  notification to admin (diff view)

ESS-04 (shift acknowledgment)
  → requires: new field on Shift: employee_acknowledged_at
  → is prerequisite for: ESS-01 (shift swap)
```

### Shift Swap Workflow (Detail)

Based on research across Deputy, Homebase, When I Work, and myshyft.com:

1. **Employee A** submits swap request: "I want to swap my shift (date/time) with Employee B's shift (date/time)"
2. **System** pre-validates: qualifications match, rest periods valid for both employees after swap, neither would exceed minijob monthly limit
3. **Employee B** receives notification; accepts or declines (in-app + push)
4. If B accepts: **Admin** receives notification with a side-by-side comparison (original vs. proposed schedule for both employees)
5. Admin approves/rejects within 24h; both employees notified
6. On approval: shifts atomically reassigned (single DB transaction)

Status lifecycle: `pending_peer` → `pending_admin` → `approved | rejected | expired`

---

## 2. Audit Trail

### Table Stakes

Every HR/payroll system handling real employee data needs these. Absence makes the system unauditable and creates legal exposure under DSGVO Article 5(f) (integrity and confidentiality).

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Immutable write log: who changed what, when | Without this, there is no accountability for payroll errors | Med | `AuditLog` model already exists; needs write-path wiring and a DB-level trigger or REVOKE to prevent UPDATE/DELETE |
| Before/after values captured | "Something changed" is not enough — need what it was and what it became | Low | `old_values` / `new_values` JSON columns already in the model |
| Admin UI: filterable audit log view | Admins need to investigate incidents without DB access | Med | New page in `(dashboard)/settings/` or a dedicated `/audit` route; filter by entity_type, user, date range |
| Payroll-specific audit entries | Wage data changes are the highest-stakes writes in the system | Low | Same mechanism; just tag `entity_type = "payroll_entry"` or `"contract_history"` |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Payroll audit trail with redacted display | Show "hourly_rate changed from [REDACTED] to [REDACTED]" for non-admin viewers, full values for admin | Low | Frontend display logic only; raw values already in JSON |
| Audit entries for ESS actions | "Employee X requested swap", "Admin Y approved swap" — full paper trail for labor disputes | Low | Natural byproduct if audit writes are wired into ESS API endpoints |
| IP address capture | Relevant if unauthorized access is suspected | Low | Field already in model; just need to wire `request.client.host` in API endpoints |

### Anti-Features

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Streaming/real-time audit dashboard | Overkill for 7 employees | Polling-based page load with TanStack Query is sufficient |
| External log shipping (Datadog, ELK) | Infrastructure overhead not justified at this scale | Postgres table with REVOKE UPDATE/DELETE is sufficient for immutability |
| Audit log for read operations (SELECT audit) | Extreme noise; no compliance requirement for reads at this scale | Only log write operations (create/update/delete) |
| Cryptographic hash chain | WORM integrity guarantee is overkill; PostgreSQL REVOKE is sufficient | DB-level permission restriction on `audit_log` table |

### Audit Log: What to Write

Every write endpoint should emit one `AuditLog` row. Minimum fields required:

```
entity_type:  "shift" | "payroll_entry" | "employee" | "contract_history" |
              "employee_absence" | "shift_swap" | "api_key" | "user"
entity_id:    UUID of the affected record
action:       "create" | "update" | "delete" | "approve" | "reject"
old_values:   JSONB snapshot before (None for create)
new_values:   JSONB snapshot after (None for delete)
user_id:      UUID of acting user (or None for API key operations — store key name)
ip_address:   request.client.host
created_at:   UTC timestamp (already default)
```

Immutability mechanism: REVOKE UPDATE, DELETE ON audit_log FROM application DB user. This is simpler than triggers and sufficient for the threat model (accidental or malicious admin tampering, not DB-level root compromise).

### Feature Dependencies

```
AUDIT-01 (write-path wiring)
  → requires: helper function audit_log_write(db, user, entity_type, entity_id, action, old, new, ip)
  → called by: all write endpoints in shifts.py, employees.py, payroll.py, absences.py, etc.

AUDIT-02 (payroll audit)
  → requires: AUDIT-01
  → special: salary fields (hourly_rate, base_wage) should be flagged sensitive in display

AUDIT-03 (admin UI)
  → requires: AUDIT-01 (data to display)
  → requires: new GET /api/v1/audit endpoint (AdminUser only, paginated, filterable)
```

---

## 3. PWA / Mobile

### Table Stakes

For a workforce management tool used by 7 employees on mobile, these are minimum viable:

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Installable to home screen | Without this, it's "just a website" — employees won't engage regularly | Low | Requires `app/manifest.ts` + HTTPS. Next.js App Router has native `MetadataRoute.Manifest` support (verified: nextjs.org/docs, 2026-03-25) |
| PWA icons (192x192, 512x512) | Required for installation prompt on Android/Chrome | Low | Generate from logo with realfavicongenerator.net; place in `public/` |
| Push notification via service worker | Allows notifications even when tab is closed | Low-Med | Service worker already registered (PushManager); needs to handle `push` and `notificationclick` events in sw.js |
| Offline calendar view (read-only) | Employees check schedule when commuting (spotty signal) | Med | Cache-first strategy for `/calendar` route + last-fetched shift data in service worker cache |
| Touch-friendly UI | Mandatory for mobile-first workforce tool | Low-Med | Larger tap targets (min 44x44px), bottom-sheet modals for forms, no hover-only interactions |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Offline shift acknowledgment queue | Employee can acknowledge a shift offline; syncs when back online via Background Sync API | High | Requires Background Sync API (`sync` event in service worker); complex to test reliably |
| "Add to Home Screen" hint banner | iOS doesn't show native install prompt; custom inline hint improves install rate | Low | Detect `navigator.standalone` and show hint for iOS; hide after user dismisses (localStorage flag) |
| Push notification click → deep link | Tap on "Shift swap approved" notification opens the relevant shift directly | Low | Set `data.url` in push payload; handle in `notificationclick` in sw.js |

### Anti-Features

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Full offline mode (write operations offline) | Complex sync conflict resolution; payroll must not have duplicate writes | Read-only offline cache is sufficient; writes require connectivity |
| Native iOS/Android app | Already in Out of Scope in PROJECT.md; PWA is sufficient for 7 users | PWA with manifest |
| Custom `beforeinstallprompt` install button | Not supported on Safari iOS (the primary mobile platform for employees) — official Next.js docs explicitly advise against this | Use iOS hint banner instead; let Chrome/Android handle its own prompt |
| Service worker for auth routes | Auth flows (login, reset-password) must not be served stale | Exclude `/(auth)/**` from service worker cache scope |
| Workbox/next-pwa package | `@ducanh2912/next-pwa` / `next-pwa` package has known App Router compatibility issues (shadowwalker/next-pwa issue #424); requires webpack override | Use native `public/sw.js` + Next.js `app/manifest.ts` per official docs |

### PWA Technical Requirements (verified from nextjs.org/docs, 2026-03-25)

Minimum for installability on Chrome/Android (HIGH confidence):
1. `app/manifest.ts` with `display: "standalone"`, `start_url`, `icons` (192 + 512)
2. HTTPS (already satisfied via Traefik)
3. `public/sw.js` registered at scope `/` with `updateViaCache: 'none'`

For iOS push notifications (iOS 16.4+ required, must be installed to home screen first):
- The existing VAPID keys and `push_subscription.py` model are already correct
- Add `push` event listener and `notificationclick` handler to `sw.js`

Offline caching strategy for VERA:
- **Cache-first:** static assets (JS, CSS, icons) — these change only on deploy
- **Network-first with 5min cache fallback:** `/api/v1/calendar`, `/api/v1/shifts` — real-time preferred, stale acceptable
- **Network-only (no cache):** `/api/v1/auth/*`, `/api/v1/payroll/*` — must never serve stale

### Feature Dependencies

```
PWA-01 (installable)
  → requires: app/manifest.ts, PWA icons in public/
  → enables:  iOS push notifications (requires installed standalone mode)

PWA-02 (offline calendar)
  → requires: PWA-01 (service worker must be registered)
  → requires: network-first caching for /api/v1/calendar and /api/v1/shifts
  → does NOT require: Background Sync API

PWA-03 (improved push)
  → requires: PWA-01 (sw.js must exist)
  → extends existing: push_subscription.py, VAPID keys, notification_service.py
  → adds: push + notificationclick handlers in sw.js, deep link payloads

PWA-04 (mobile UX)
  → independent of PWA-01/02/03 — pure CSS/component work
  → should be done before or alongside PWA-01 (no point installing an unusable app)
```

---

## 4. Security Hardening

### Table Stakes

These are not optional given that VERA holds real salary data for real people on a public VPS.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| API key scope enforcement | Currently any key has admin rights — this is the most critical bug | Med | `ApiKey.scopes` exists in DB; `deps.py` needs a `require_scope(scope)` dependency that reads the resolved API key's scopes |
| Consistent RBAC on all endpoints | Systematic audit of every endpoint for missing `AdminUser`/`ManagerOrAdmin` dependency | Low-Med | Grep all routes; especially check GET endpoints that may expose salary data |
| Pydantic strict mode on all input schemas | Prevents unexpected field injection, untyped fields becoming null | Low | Add `model_config = ConfigDict(strict=True)` to write schemas; audit for `Optional` fields that should be required |
| JWT token revocation (logout-all-devices) | Refresh tokens live 7 days; compromised refresh token = week-long access | Med | Redis blocklist for refresh token JTI; on logout-all, insert all active refresh tokens for user into blocklist |
| Token rotation on every refresh | Prevents refresh token replay attacks | Low | Already partially designed — ensure old refresh token is invalidated when a new one is issued |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| API key scope enforcement with read/write/admin tiers | Shiftjuggler sync only needs read access; tighten it to `read` scope | Low | Define: `read` = GET only, `write` = GET + POST/PUT/PATCH, `admin` = full including payroll/settings |
| Secrets audit: no salary data in logs | DSGVO Article 5(f); currently unclear if `old_values`/`new_values` in AuditLog would log salary in plaintext | Low | Redact known sensitive fields (hourly_rate, base_wage, total_gross) before writing to audit log |
| CORS hardening | ALLOWED_ORIGINS is a comma-separated env var — verify production value is not `*` | Low | Audit deploy/.env on VPS; add test that CORS rejects non-listed origins |

### Anti-Features

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Full OAuth2 server (authorization code flow) | Engineering overhead for 7 internal users | JWT + refresh token rotation with Redis blocklist is sufficient |
| Biometric auth / WebAuthn | Nice-to-have but no demand signal; admin already has TOTP | Out of scope for Milestone 1 |
| IP allowlisting for API keys | Stefan's home IP may change; Shiftjuggler runs from cloud | Scope enforcement is sufficient without IP restriction |
| Re-implementation of auth from scratch | Bcrypt + JWT is correct; the gaps are configuration, not architecture | Fix the specific gaps (scope enforcement, token rotation) |

### Feature Dependencies

```
SEC-01 (API key scope enforcement)
  → requires: new Depends function require_scope("read"|"write"|"admin") in deps.py
  → requires: Shiftjuggler sync key must be updated to scopes=["read"] in DB

SEC-02 (consistent RBAC)
  → requires: systematic grep of all route files for missing auth dependencies
  → no new models needed

SEC-05 (JWT revocation)
  → requires: Redis (already deployed as vera-redis)
  → requires: new endpoint POST /auth/logout-all
  → requires: JTI claim added to JWT payload (currently missing — check security.py)
  → the refresh token check in get_current_user must look up Redis blocklist
```

---

## MVP Recommendation for Milestone 1

Prioritize in this order based on risk/value:

**Must ship (Milestone 1 core):**
1. SEC-01: API key scope enforcement — security hole, no workaround
2. AUDIT-01 + AUDIT-02: Audit log wiring — model exists, just needs write-path; payroll data changes must be traceable
3. ESS-02 + ESS-03 + ESS-04: Absence request, availability update, shift acknowledge — these three are independent and low-complexity
4. PWA-01 + PWA-03: Installable + improved push — manifest is 1 file; service worker push handler is ~20 lines

**Second priority (still Milestone 1, can be later phases within milestone):**
5. SEC-02: RBAC audit — medium effort, no model changes
6. AUDIT-03: Admin UI for audit log — requires AUDIT-01 to be done first
7. PWA-02: Offline calendar — requires PWA-01, adds meaningful value
8. PWA-04: Mobile UX polish — polish pass, no new features

**Defer to Milestone 2:**
9. ESS-01: Shift swap — highest complexity, requires new model + multi-step workflow + compliance integration; tackle after simpler ESS features are stable
10. SEC-05: JWT revocation — correct approach is Redis blocklist; design carefully to avoid breaking token refresh for all users simultaneously

---

## Complexity Reference

| ID | Feature | Complexity | Key reason |
|----|---------|------------|------------|
| ESS-01 | Shift swap | High | New model, multi-party workflow, compliance pre-check |
| ESS-02 | Absence request by employee | Low | Model and workflow exist; RBAC change + notification wire-up |
| ESS-03 | Availability self-update | Low | One PATCH endpoint + RBAC change + notification |
| ESS-04 | Shift acknowledgment | Low | One nullable DateTime column on Shift + PATCH endpoint |
| AUDIT-01 | Audit log wiring | Medium | Touches every write endpoint; needs helper function pattern |
| AUDIT-02 | Payroll audit specifics | Low | Same mechanism; add redaction for sensitive fields |
| AUDIT-03 | Admin audit UI | Medium | New page + filter/pagination UI |
| PWA-01 | Installable manifest | Low | One file: app/manifest.ts + icons |
| PWA-02 | Offline calendar | Medium | Service worker cache strategy; test edge cases |
| PWA-03 | Push via service worker | Low | sw.js push + notificationclick handlers |
| PWA-04 | Mobile UX | Low-Med | CSS + component work; no backend |
| SEC-01 | API key scope enforcement | Medium | New Depends function + update all scoped endpoints |
| SEC-02 | RBAC audit all endpoints | Low-Med | Systematic review + fixes; no new models |
| SEC-03 | Pydantic strict input validation | Low | Config change + audit of schemas |
| SEC-04 | Secrets audit | Low | Env var audit + bundle inspection |
| SEC-05 | JWT revocation (Redis blocklist) | Medium | Redis integration + JTI in tokens + logout-all endpoint |

---

## Sources

- [Homebase: What is employee self-service?](https://www.joinhomebase.com/glossary/employee-self-service) — feature list, HIGH confidence
- [Homebase vs. Deputy 2025 comparison](https://connecteam.com/homebase-vs-deputy/) — feature comparison, MEDIUM confidence
- [Deputy shift swap documentation](https://www.joinhomebase.com/employee-scheduling/shift-swapping) — swap workflow, MEDIUM confidence
- [myshyft.com: Shift swap request workflows](https://www.myshyft.com/blog/shift-swap-request-workflows/) — approval UX best practices, MEDIUM confidence
- [PeopleStrong: HRMS Audit Log](https://www.peoplestrong.com/blog/hrms-audit-log/) — audit log fields, MEDIUM confidence
- [PostgreSQL audit log schema (Medium / sehban.alam)](https://medium.com/@sehban.alam/lets-build-production-ready-audit-logs-in-postgresql-7125481713d8) — schema design, MEDIUM confidence
- [4Spot Consulting: HR audit trail security practices](https://4spotconsulting.com/fortifying-your-hr-data-8-essential-practices-for-securing-audit-trails/) — immutability, MEDIUM confidence
- [Next.js official docs: PWA guide](https://nextjs.org/docs/app/guides/progressive-web-apps) — App Router PWA, version 16.2.1, lastUpdated 2026-03-25, HIGH confidence
- [Fishtank: Native-Like Offline Experience in Next.js PWAs](https://www.getfishtank.com/insights/building-native-like-offline-experience-in-nextjs-pwas) — Workbox caching strategies, MEDIUM confidence
- [shadowwalker/next-pwa GitHub issue #424](https://github.com/shadowwalker/next-pwa/issues/424) — App Router incompatibility, HIGH confidence
- [WorkOS: API granular permissions with OAuth scopes](https://workos.com/blog/api-granular-permissions-with-oauth-scopes) — scope design patterns, MEDIUM confidence
- [Auth0: Refresh tokens security](https://auth0.com/blog/refresh-tokens-what-are-they-and-when-to-use-them/) — token rotation, HIGH confidence
