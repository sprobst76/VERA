# Architecture Patterns

**Project:** VERA — Milestone 1 (Security, Hardening & Employee Self-Service)
**Researched:** 2026-03-27
**Scope:** Audit logs, approval workflows, PWA service worker, JWT token revocation

---

## Existing Architecture Summary

VERA is a multi-tenant FastAPI + Next.js application with the following established constraints:

- Every DB row carries `tenant_id`; all queries filter by `current_user.tenant_id`
- Backend is fully async (SQLAlchemy 2.0 async + FastAPI)
- Auth: JWT access tokens (60 min) + refresh tokens (7 days), stored in `localStorage`
- Redis 7 is already deployed and connected via `app.core.redis.get_redis()`
- `AuditLog` model already exists in `backend/app/models/audit.py` but is sparsely populated
- `EmployeeAbsence` already has a `status` field (`pending | approved | rejected`) with `approved_by` / `approved_at` columns — the data model is partly in place

---

## Component 1: Audit Log

### Recommended Structure

The existing `AuditLog` model in `audit.py` already has the right shape:

```
id (UUID PK), tenant_id, user_id, entity_type, entity_id,
action (create|update|delete), old_values (JSON), new_values (JSON),
ip_address, created_at
```

This structure is correct. The gap is not the schema but the coverage: the table exists but most write endpoints do not call `_write_audit()`.

**Do not redesign the table.** Instead:

1. Add composite indexes (missing today):
   - `(tenant_id, created_at DESC)` — primary query pattern for the admin UI
   - `(tenant_id, entity_type, entity_id)` — per-entity history
   - `(tenant_id, user_id, created_at DESC)` — per-user activity

2. Add a `_write_audit()` helper in a shared location (`backend/app/services/audit_service.py`) so every endpoint can call it with one line. The current helper in `shifts.py` should be promoted to this shared service.

3. For payroll entries specifically: the `old_values` / `new_values` pattern must mask `hourly_rate`, `base_wage`, `total_gross` field values for logging to avoid Klartext salary data in logs. Log only the field names that changed, not the amounts. This satisfies the DATENSCHUTZ constraint in `PROJECT.md`.

**Partitioning:** Not needed. VERA has 7 employees. Monthly write volume is approximately 100-200 audit rows. Partitioning overhead is not justified. Add it only after table grows past 100K rows.

**Append-only enforcement:** PostgreSQL has no built-in append-only constraint. Enforce at the application level: no `UPDATE` or `DELETE` ever issued against `audit_log`. Grant the application DB user only `INSERT + SELECT` on this table in production (`REVOKE UPDATE, DELETE ON audit_log FROM vera_app`). This is a migration-time step.

### Component Boundaries

| What calls it | What it calls | Notes |
|---|---|---|
| All `api/v1/*.py` write endpoints | `audit_service.write_audit(db, ...)` | Fire-and-forget inside the same transaction |
| Celery tasks (payroll calculation) | `audit_service.write_audit(db, ...)` | Uses task's own `AsyncSession` |
| Admin UI `GET /api/v1/audit-log` | `audit_log` table | Filter by entity_type, user, date range |

### Data Flow

```
HTTP write request
  → route handler validates + executes mutation
  → calls audit_service.write_audit(db, entity_type, entity_id, action, old, new)
  → inserts AuditLog row in same DB transaction
  → commit — both the mutation and the log entry are atomic
```

The audit write must be in the same `db.commit()` as the mutation. If the audit write is outside the transaction, a partial commit can leave mutations without audit entries.

---

## Component 2: Approval Workflows

### State Machines

VERA needs two approval flows: `AbsenceRequest` (already partially modeled as `EmployeeAbsence`) and `ShiftSwapRequest` (does not exist yet).

**Recommended approach: Plain string status field + explicit transition endpoints.**

Do not add a state machine library (`transitions`, `python-statemachine`). For two workflows with three states each, a library adds indirection without benefit. The pattern is:

```python
# Allowed transitions as a dict — simple, readable, testable
ABSENCE_TRANSITIONS = {
    "pending": ["approved", "rejected"],
    "approved": [],      # terminal
    "rejected": [],      # terminal
}

def validate_transition(current: str, target: str, transitions: dict) -> None:
    if target not in transitions.get(current, []):
        raise HTTPException(400, f"Cannot transition from {current!r} to {target!r}")
```

This approach is consistent with how `time_correction_status` is already modeled on `Shift`.

### AbsenceRequest (existing `EmployeeAbsence`)

The `EmployeeAbsence` model already has `status`, `approved_by`, `approved_at`. What is missing:

1. An employee-facing `POST /api/v1/absences` endpoint that creates with `status="pending"` and limits to own `employee_id` (today the endpoint requires ManagerOrAdmin)
2. A `PUT /api/v1/absences/{id}/approve` and `PUT /api/v1/absences/{id}/reject` endpoint (ManagerOrAdmin only) that:
   - Validates the transition
   - Sets `approved_by = current_user.id`, `approved_at = now()`
   - Triggers `NotificationService.dispatch()` to notify the employee
   - Writes to `audit_log`
3. An employee `GET /api/v1/absences/my` endpoint (scoped to own employee)

### ShiftSwapRequest (new model needed)

New table `shift_swap_requests`:

```
id (UUID PK)
tenant_id (FK tenants.id CASCADE)
requester_id (FK employees.id)        — employee requesting the swap
requester_shift_id (FK shifts.id)     — shift being offered
target_id (FK employees.id, nullable) — specific target employee, null = open offer
target_shift_id (FK shifts.id, nullable) — shift offered in return (nullable for one-way)
status (String 50)                    — pending | approved | rejected | cancelled
admin_id (FK users.id, nullable)      — who approved/rejected
resolved_at (DateTime TZ, nullable)
notes (Text, nullable)
created_at (DateTime TZ)
```

State machine: `pending → approved | rejected | cancelled`

On `approved`:
1. Swap the `employee_id` fields on both `Shift` rows (or just the requester's shift if one-way)
2. Write two `AuditLog` entries (one per shifted Shift)
3. Notify both employees via `NotificationService`
4. Mark both shifts as needing re-confirmation (`status = "planned"`)

Race condition: use `SELECT ... FOR UPDATE` on both shift rows before executing the swap, consistent with the existing shift claim endpoint analysis in `CONCERNS.md`.

### RBAC Integration

The existing dependency pattern in `deps.py` handles this cleanly:

- `CurrentUser` — employee creates own absence request, views own swap requests
- `ManagerOrAdmin` — approves/rejects absence and swap requests
- Tenant isolation — all queries filter by `tenant_id == current_user.tenant_id`

No new dependency types are needed. The existing RBAC layer is sufficient.

### Component Boundaries

| Component | Inputs | Outputs |
|---|---|---|
| `POST /absences` (employee) | Employee JWT, absence dates/type | `EmployeeAbsence{status=pending}`, `NotificationLog` (to admin) |
| `PUT /absences/{id}/approve` | ManagerOrAdmin JWT | Updated `EmployeeAbsence{status=approved}`, `AuditLog`, `NotificationLog` (to employee) |
| `POST /shift-swap-requests` | Employee JWT, shift IDs | `ShiftSwapRequest{status=pending}`, `NotificationLog` (to admin) |
| `PUT /shift-swap-requests/{id}/approve` | ManagerOrAdmin JWT | Updated shifts + `ShiftSwapRequest`, `AuditLog` x2, `NotificationLog` x2 |

### Data Flow

```
Employee: POST /absences {type, start_date, end_date}
  → deps: CurrentUser (must have linked employee record)
  → create EmployeeAbsence(status="pending", employee_id=current_user.employee_id)
  → notify admins via NotificationService
  → write AuditLog(action="create")
  → return EmployeeAbsenceOut

Admin: PUT /absences/{id}/approve
  → deps: ManagerOrAdmin
  → load EmployeeAbsence (filter tenant_id)
  → validate_transition("pending", "approved")
  → set approved_by, approved_at
  → notify employee via NotificationService
  → write AuditLog(action="update", old={status:pending}, new={status:approved})
  → commit
```

---

## Component 3: PWA Service Worker

### Next.js App Router Constraints (HIGH confidence — official docs verified 2026-03-25)

1. **Service worker file must be in `public/sw.js`** — Next.js App Router does not generate or manage service workers automatically. The file is served as a static asset.

2. **Registration is manual** — add `navigator.serviceWorker.register('/sw.js', { scope: '/', updateViaCache: 'none' })` in a `useEffect` inside a client component. The official Next.js PWA guide (updated 2026-03-25) shows this exact pattern.

3. **Webpack is required for Serwist** — the `@serwist/next` plugin (the currently recommended library for offline caching) explicitly requires webpack, not Turbopack. VERA's `next.config` must not use `experimental.turbopack` if Serwist is used.

4. **App Router SSR + service worker scope**: Server components run on the server; the service worker only intercepts fetch calls from the client. There is no conflict, but server-rendered HTML is not pre-cached by the service worker unless explicitly added to the precache manifest.

5. **Push notifications**: VERA already has `PushManager` component, `push_subscription` table, and VAPID keys. The service worker `push` event listener is the missing piece — this belongs in `public/sw.js`.

### Recommended Implementation

**Use Serwist** (`@serwist/next`) for cache management. Reason: it is the library referenced in official Next.js docs for offline support, it wraps Workbox with better defaults, and it handles precache manifest injection automatically on build.

Do NOT use the abandoned `next-pwa` package (last significant update 2021, does not reliably support App Router).

Do NOT hand-write a caching service worker from scratch — Workbox/Serwist's runtime caching handles cache versioning and stale-while-revalidate logic correctly.

**Cache strategy per resource type:**

| Resource | Strategy | Why |
|---|---|---|
| Next.js static assets (`/_next/static/*`) | CacheFirst (precached by Serwist) | Immutable, content-hashed filenames |
| API `GET /calendar` (shift data) | NetworkFirst, fallback to cache | Must be fresh when online; readable offline |
| API `GET /shifts/my` (employee view) | StaleWhileRevalidate | Acceptable to see slightly stale data |
| API `POST/PUT/DELETE` mutations | No caching — queue via BackgroundSync | Mutations need online confirmation |
| `/` dashboard page | NetworkFirst | |

**Background sync for offline mutations:** When an employee is offline and tries to confirm a shift or submit an absence request, the request goes into a BackgroundSync queue (IndexedDB-backed). Serwist provides `BackgroundSyncPlugin` for this. On reconnect, the service worker replays the queued requests automatically.

**Limits:**
- Background sync is not supported on iOS Safari as of early 2026 (LOW confidence on current iOS version support — verify at implementation time). For iOS, gracefully degrade to "you are offline, try again" messaging.
- The service worker cannot intercept Next.js Server Actions directly (they are POST requests to the same origin; cache is possible but complex). Avoid routing Server Actions through the service worker cache.

### Component Boundaries

| Component | Location | Communicates With |
|---|---|---|
| `app/manifest.ts` | Next.js App Router | Browser install prompt |
| `public/sw.js` (via Serwist build) | Static asset | Browser fetch events, PushManager |
| `PushManager` component (exists) | `src/components/shared/PushManager.tsx` | Registers SW, subscribes to push, calls `/api/v1/notifications/push/subscribe` |
| Backend `push_subscription` table (exists) | `backend/app/models/push_subscription.py` | Stores VAPID subscriptions per user |

The push notification flow already works end-to-end. The service worker just needs the `push` event listener added.

### Data Flow

```
Install:
  Browser loads page → PushManager useEffect → navigator.serviceWorker.register('/sw.js')
  → SW installs, Serwist precaches static assets
  → User consents to push → pushManager.subscribe() → POST /push/subscribe → DB

Offline read:
  Employee opens calendar offline
  → fetch /api/v1/calendar intercepted by SW
  → SW returns cached response from NetworkFirst cache
  → TanStack Query renders stale data with staleness indicator

Push notification (existing flow + SW listener):
  Backend sends VAPID push → SW receives 'push' event
  → SW calls self.registration.showNotification(...)
  → User taps notification → SW 'notificationclick' → clients.openWindow(url)
```

---

## Component 4: Redis-Based JWT Token Revocation

### Recommended Approach: Token Version on User Row

**HIGH confidence** — this approach is the established best practice for "revoke all devices" scenarios.

Add an integer `token_version` column to the `User` model:

```python
token_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
```

Embed `token_version` in both access and refresh token payloads:

```python
payload = {
    "sub": str(user_id),
    "tenant_id": str(tenant_id),
    "role": role,
    "ver": user.token_version,   # new field
    "exp": expire,
    "type": "access",
}
```

On validation in `get_current_user` (in `deps.py`), after decoding the JWT, load the user from DB and compare `payload["ver"] == user.token_version`. If they differ, return 401.

On `POST /auth/logout-all` or `POST /auth/change-password`: increment `user.token_version` by 1. All existing tokens immediately become invalid on their next use.

**Why this over a Redis blocklist:**

A Redis blocklist stores the `jti` (token ID) of every revoked token and checks it on every request. This requires:
1. Adding a `jti` UUID to every token (currently not present in VERA's tokens)
2. A Redis lookup on every authenticated request
3. Redis persistence configured correctly (otherwise revocations are lost on restart)
4. TTL management to expire blocklist entries after the token's `exp`

The `token_version` approach requires only one DB column read per request — which is already happening (the user row is loaded in `get_current_user` to check `is_active`). The marginal cost is one integer comparison.

The `token_version` approach does not support revoking a single session (only all sessions for a user). For VERA's use case (7 users, logout-all-devices, password change invalidation), this is exactly the right scope.

### Redis Blocklist: When to Use It Instead

Use a Redis blocklist only if VERA later needs per-device logout (logout from one device without logging out all devices). This would require a `jti` per token and per-token revocation storage. For Milestone 1, this is over-engineering.

### Implementation Boundary

| Component | Change |
|---|---|
| `User` model | Add `token_version: int = 1` |
| `security.py` | `create_access_token` + `create_refresh_token` embed `ver` field |
| `deps.py` `get_current_user` | After loading user, assert `payload.get("ver") == user.token_version` |
| `auth.py` `POST /auth/change-password` | Increment `user.token_version` after password update |
| New `POST /auth/logout-all` endpoint | Increment `user.token_version`, return 200 |

**Migration:** `ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 1` — safe, non-breaking, no data migration needed.

**Backward compatibility:** Existing tokens without `ver` field will have `payload.get("ver")` return `None`. Compare against `user.token_version` (which starts at 1). Since `None != 1`, all existing tokens become invalid on the first deploy after this change. This is acceptable and desirable — forces re-login on deploy.

### Data Flow

```
Normal request:
  JWT decoded → payload["ver"] loaded
  → User row fetched (already done for role check)
  → payload["ver"] == user.token_version → proceed
  → payload["ver"] != user.token_version → 401 Unauthorized

Logout-all / password change:
  POST /auth/change-password or POST /auth/logout-all
  → user.token_version += 1
  → db.commit()
  → all existing tokens for this user become invalid on next use
  → return 200, client clears localStorage tokens
```

---

## Suggested Build Order

Dependencies between the four components determine sequencing:

```
1. Token Revocation (SEC-05)
   ← No dependencies on other Milestone 1 components
   ← Unblocks: more secure session context for everything that follows
   ← Risk: forces re-login on deploy (acceptable, communicate to Stefan)

2. Audit Log Coverage (AUDIT-01, AUDIT-02)
   ← Depends on: token revocation complete (so audit log captures authenticated user correctly)
   ← Blocks: AUDIT-03 (admin UI needs data to display)
   ← Adds: audit_service.py shared helper, DB indexes

3. Approval Workflows (ESS-01, ESS-02)
   ← Depends on: audit log service (every approval writes to audit log)
   ← AbsenceRequest: existing model, add endpoints only
   ← ShiftSwapRequest: new model + Alembic migration + endpoints
   ← Notification triggers fire from existing NotificationService

4. PWA / Service Worker (PWA-01 through PWA-04)
   ← No backend dependencies
   ← Can be parallelized with audit log if frontend and backend work separately
   ← Serwist setup affects next.config.ts + CI build time
   ← Push notification listener in sw.js completes existing push flow
```

**Phase sequencing rationale:**

Token revocation first because it is the security foundation — any audit log entry needs a trustworthy `user_id`, and approval workflows need a session that can be immediately invalidated after password change. Approval workflows depend on audit coverage because every transition must be logged. Service worker is frontend-only and can be developed in parallel with backend work.

---

## Cross-Cutting Architecture Notes

### Audit Log Is Not a Notification Trigger

Do not route notifications through the audit log. The existing `NotificationService.dispatch()` is the correct trigger point. The audit log is a compliance/forensics record; notifications are a real-time UX concern. Keep them separate.

### Approval Workflow vs Direct Edit

The `EmployeeAbsence` status field already encodes the workflow. Do not add a separate `AbsenceRequest` table — it would duplicate the existing model. Instead, expand the existing model's endpoint surface (employee-facing create + manager approve/reject).

For `ShiftSwapRequest`, a separate table is correct because a swap involves two shifts and two employees — it cannot be modeled on either shift row alone.

### Service Worker and TanStack Query Coexistence

TanStack Query's in-memory cache and the service worker's HTTP cache serve different purposes and must not fight each other. Configure Serwist's NetworkFirst caching for API routes so the service worker does not serve stale data when TanStack Query expects fresh data from the network. NetworkFirst means: try network, if offline use cache. This is compatible with TanStack Query's `staleTime` settings.

### No PostgreSQL RLS for Milestone 1

`CONCERNS.md` raises adding PostgreSQL Row Level Security as defense-in-depth. This is architecturally sound but out of scope for Milestone 1 — it requires significant schema changes and thorough testing. Continue relying on application-level `tenant_id` filtering, which is comprehensive and consistently applied across 268 tests.

---

## Sources

- Next.js official PWA docs: https://nextjs.org/docs/app/guides/progressive-web-apps (updated 2026-03-25, HIGH confidence)
- Serwist Next.js getting started: https://serwist.pages.dev/docs/next/getting-started (HIGH confidence)
- PostgreSQL audit log patterns: https://medium.com/@sehban.alam/lets-build-production-ready-audit-logs-in-postgresql-7125481713d8 (MEDIUM confidence — community article, patterns verified against VERA's existing schema)
- JWT revocation strategies: https://supertokens.com/blog/revoking-access-with-a-jwt-blacklist (MEDIUM confidence), https://zuniweb.com/blog/jwt-database-patterns-revocation-blacklists-and-persistence-in-mysql-postgresql-mongodb-and-redis/ (MEDIUM confidence)
- FastAPI + SQLAlchemy 2.0 async patterns: existing VERA codebase (HIGH confidence — primary source)
- VERA codebase analysis: `backend/app/models/audit.py`, `backend/app/models/absence.py`, `backend/app/core/security.py`, `backend/app/core/redis.py`, `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/CONCERNS.md`
