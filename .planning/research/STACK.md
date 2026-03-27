# Technology Stack — Security Hardening, Audit Trail, PWA, Employee Self-Service

**Project:** VERA (Milestone 1: Security Hardening + Employee Self-Service)
**Researched:** 2026-03-27
**Overall confidence:** HIGH (all recommendations verified against official docs or actively maintained projects)

---

## Context

VERA already runs FastAPI 0.115 + SQLAlchemy 2.0 async + PostgreSQL 16 + Redis 7 + Next.js 14 App Router.
This milestone adds four capability areas to that existing stack. The research focuses exclusively on
*new* libraries and patterns needed — it does not re-evaluate the existing core stack.

---

## 1. JWT Token Revocation (SEC-05)

### Problem

`python-jose 3.3.0` is unmaintained (CVE-2024-33663, last release 2021). Refresh tokens are never
invalidated: a password change does not revoke a 7-day refresh token. The CONCERNS.md documents the
recommended fix — a `token_version` integer per user — but the underlying JWT library also needs
replacing.

### Recommendation: Replace python-jose with PyJWT 2.12

**Confidence: HIGH** — FastAPI's own documentation was updated to recommend PyJWT; the official
full-stack-fastapi-template PR #1203 completed this migration.

| Aspect | python-jose 3.3.0 | PyJWT 2.12.x |
|--------|-------------------|--------------|
| Maintenance | Abandoned (~2021) | Active (2.12.1 released 2026-03-13) |
| CVEs | CVE-2024-33663 (alg confusion) | None known |
| API | `jose.jwt.encode/decode` | `jwt.encode/decode` |
| Algorithm pinning | Manual | `algorithms=["HS256"]` parameter (same pattern) |
| `python` version | 3.7+ | 3.9+ |

**Migration** is minimal: the `encode`/`decode` call signatures are almost identical. PyJWT returns
a `str` directly from `encode()` (no `.decode()` needed unlike some older versions). The `JWTError`
exception class is `jwt.PyJWTError` instead of `jose.exceptions.JWTError`. Swap in `security.py`
only.

```python
# Before (python-jose)
from jose import jwt, JWTError
token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
data = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])

# After (PyJWT)
import jwt as pyjwt
from jwt import PyJWTError
token = pyjwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
data = pyjwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
```

**Do not use:** `joserfc` — less ecosystem adoption, not what FastAPI docs point to.

### Recommendation: token_version for "revoke all" + Redis jti blocklist for immediate revocation

Two complementary mechanisms are needed:

**Mechanism A — token_version (revoke-all-devices):**
- Add `token_version: int` column to `User` table (default 1, Alembic migration)
- Embed `ver: user.token_version` claim in both access and refresh tokens at issue time
- On `/auth/refresh`, validate that `token.ver == user.token_version`; reject if mismatch
- Increment `token_version` on: password change, `POST /auth/logout-all`, admin deactivation
- Cost: one extra DB read per refresh (already done to load the user)

**Mechanism B — Redis jti blocklist (immediate single-token revocation):**
- Add a UUID `jti` claim to every access token
- On `POST /auth/logout`, store `SET revoked:{jti} 1 EX {remaining_ttl_seconds}` in Redis
- In `get_current_user` dependency, after JWT decode: `await redis.exists(f"revoked:{jti}")`
- TTL equals the token's remaining lifetime so Redis auto-purges; no manual cleanup needed
- Cost: one Redis GET per authenticated request (sub-millisecond; Redis 7 already present)

**Use both:** token_version catches refresh token theft after password change (covers the 7-day
window gap); jti blocklist enables immediate access token revocation on logout. For VERA's scale
(7 users), the Redis overhead is negligible.

**Do not use:** Database-backed blocklist — slower than Redis and requires cleanup jobs.

```python
# Redis key pattern
await redis_client.set(f"revoked:{jti}", "1", ex=remaining_seconds)
exists = await redis_client.exists(f"revoked:{jti}")
```

**Install:**
```bash
# Remove
pip uninstall python-jose

# Add
pip install PyJWT==2.12.1
# redis client already in requirements.txt (redis==5.2.0 with redis.asyncio)
```

---

## 2. API Key Scope Enforcement (SEC-01)

### Problem

`ApiKey.scopes` is stored but `deps.py` never checks it. A `read-only` key has full admin rights.

### Recommendation: FastAPI `Security` scopes via a require_scope dependency

**Confidence: HIGH** — This is the official FastAPI pattern from `/advanced/security/oauth2-scopes/`.

The cleanest approach uses a factory dependency — no new library needed:

```python
# In deps.py — add alongside existing get_current_user
def require_scope(*required_scopes: str):
    """
    Returns a dependency that raises 403 if the request was authenticated
    via API key and the key lacks one of the required scopes.
    JWT-authenticated requests always pass (they carry full role context).
    """
    async def _check(current_user: CurrentUser, request: Request):
        api_key_scopes = getattr(request.state, "api_key_scopes", None)
        if api_key_scopes is not None:
            for scope in required_scopes:
                if scope not in api_key_scopes:
                    raise HTTPException(status_code=403, detail=f"Scope required: {scope}")
        return current_user
    return Depends(_check)

# Usage on write endpoints
@router.post("/shifts")
async def create_shift(
    db: DB,
    current_user: Annotated[User, require_scope("write")],
    ...
):
```

During API key resolution in `get_current_user`, attach the scopes to `request.state`:
```python
request.state.api_key_scopes = api_key.scopes  # list[str] e.g. ["read"]
```

**Scopes to define:** `read`, `write`, `admin` — matches the existing `ApiKey.scopes` field.

**Do not use:** OAuth2 `SecurityScopes` — overly complex for API keys; designed for OAuth flows.

---

## 3. Pydantic v2 Strict Input Validation (SEC-03)

### Problem

Some endpoint schemas accept coercion silently (e.g., string `"123"` is accepted where `int` is
expected). The CONCERNS.md flags unrestricted user input at system boundaries.

### Recommendation: Field-level strict typing on security-sensitive schemas; model-level ConfigDict(strict=True) on write schemas

**Confidence: HIGH** — Verified against Pydantic v2 official docs.

Pydantic v2 is already in use (2.10.0). The approach:

**For write/create schemas** (shift creation, employee updates, payroll):
```python
from pydantic import BaseModel, ConfigDict, Field
from typing import Annotated
from pydantic.types import StrictStr, StrictInt

class ShiftCreate(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    employee_id: int  # strict=True prevents "123" string coercion
    date: date        # still accepts ISO string in JSON mode (Pydantic v2 relaxes strict for JSON dates)
    start_time: str = Field(pattern=r"^\d{2}:\d{2}$")  # regex validation
    end_time: str = Field(pattern=r"^\d{2}:\d{2}$")
```

Key rules:
- `extra="forbid"` on all write schemas — rejects unknown fields rather than silently ignoring
- `strict=True` at model level prevents type coercion (string → int, etc.)
- Use `Field(pattern=...)` for time strings, `Field(ge=0, le=...)` for numeric ranges
- For IDs, use `StrictInt` or `Annotated[int, Field(ge=1)]`
- **Exception:** date/datetime fields in JSON mode still accept ISO strings even in strict mode — this is intentional Pydantic v2 behavior, not a bug

**For read/response schemas:** keep lax mode (the default). Strict mode on output adds unnecessary friction and is not a security boundary.

**Do not add** `ConfigDict(strict=True)` globally to all models — it breaks existing tests that pass
string representations of numbers in test payloads.

**No new library needed** — Pydantic v2 (already installed) provides all this natively.

---

## 4. Immutable Audit Log (AUDIT-01, AUDIT-02)

### Problem

No systematic audit trail. The `_write_audit` helper exists in shifts but is not used in payroll,
employees, or absences. CONCERNS.md confirms payroll edits are untracked.

### Recommendation: Application-level append-only table (not triggers, not postgresql-audit)

**Confidence: HIGH** for the pattern; MEDIUM for rejecting trigger-based alternatives.

**Why application-level, not triggers:**

| Approach | Pros | Cons for VERA |
|----------|------|---------------|
| PostgreSQL triggers (`postgresql-audit` lib) | Captures all changes including migrations and direct SQL | Requires PL/pgSQL trigger per table; hard to add user context (who made the change); complex to query; `postgresql-audit` library last meaningful release 2021 |
| WAL-based (logical replication) | Zero application changes | Requires pg_logical setup, separate consumer process; massively overengineered for 7 users |
| Application-level | User context always available; queryable via SQLAlchemy; testable; matches existing `audit.py` model pattern | Misses ORM-bypassing SQL (only risk: admin direct DB access, not a concern for VERA) |

VERA already has `backend/app/models/audit.py` with a partial `audit_log` table. The right approach is
to expand this into a systematic pattern, not add a new library.

**Schema for `audit_log` table** (extend the existing model):
```python
class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_tenant_entity", "tenant_id", "entity_type", "entity_id"),
        Index("ix_audit_tenant_ts", "tenant_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)  # None = system/API key
    api_key_id: Mapped[int | None] = mapped_column(ForeignKey("api_keys.id"), nullable=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)  # "shift", "payroll", "employee"
    entity_id: Mapped[int] = mapped_column(nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)   # "create", "update", "delete"
    before: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # previous values (None for create)
    after: Mapped[dict | None] = mapped_column(JSON, nullable=True)   # new values (None for delete)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # NO updated_at — this table is append-only
```

**Append-only enforcement** — at application level, never expose an UPDATE or DELETE endpoint for
`audit_log`. Add a DB-level check: grant the application user `INSERT` only on `audit_log` (not
`UPDATE`/`DELETE`). Document this in a migration comment. Do NOT enable PostgreSQL RLS for this —
the application DB user already handles it via grant restriction.

**Helper function** (replace/extend the existing `_write_audit`):
```python
async def write_audit(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int | None,
    api_key_id: int | None,
    entity_type: str,
    entity_id: int,
    action: Literal["create", "update", "delete"],
    before: dict | None = None,
    after: dict | None = None,
) -> None:
    entry = AuditLog(
        tenant_id=tenant_id,
        user_id=user_id,
        api_key_id=api_key_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        before=before,
        after=after,
    )
    db.add(entry)
    # Do NOT commit here — caller commits as part of the main transaction
    # This ensures audit entry and data change are atomic
```

**Critical:** call `write_audit` inside the same transaction as the data change. If the data commit
fails, the audit entry rolls back too — no phantom audit entries for operations that didn't happen.

**Payroll data — no Klartextlogging:** `before`/`after` JSON for PayrollEntry must include hours,
wage, and surcharge amounts (needed for audit) but must NOT include any free-text fields or
personally identifying information beyond what's already in the DB row. No extra scrubbing needed
since `PayrollEntry` schema contains no sensitive text fields.

**Do not use:**
- `postgresql-audit` (PyPI) — last meaningful update 2021, trigger-based complexity not justified
- `sqlalchemy-postgresql-audit` — niche, low adoption, similar age concerns
- Event sourcing / WAL consumers — massively overengineered for 7-user system

---

## 5. PWA: Service Worker + Offline Caching (PWA-01 through PWA-04)

### Problem

VERA has no service worker, no web manifest, and no offline capability. Web Push via VAPID is already
implemented in the backend; the frontend only needs the service worker to receive push events.

### Recommendation: Serwist 9.x (@serwist/next + serwist)

**Confidence: HIGH** — Serwist is recommended in the official Next.js documentation for PWA offline
support. `next-pwa` (shadowwalker) has not been updated in 2+ years and is abandoned.

| Library | Status | Next.js App Router | Workbox base | Verdict |
|---------|--------|-------------------|--------------|---------|
| next-pwa (shadowwalker) | Abandoned (~2022) | Broken | Workbox 6 | Do not use |
| @ducanh2912/next-pwa | Semi-maintained fork | Partial | Workbox 7 | Avoid |
| **Serwist** (@serwist/next) | Active, v9.x | Full support | Serwist (Workbox fork) | **Use this** |

**Install:**
```bash
npm install @serwist/next
npm install -D serwist
```

**Configuration steps:**

1. `next.config.mjs` — wrap with Serwist:
```javascript
import withSerwistInit from "@serwist/next";

const withSerwist = withSerwistInit({
  swSrc: "app/sw.ts",
  swDest: "public/sw.js",
  disable: process.env.NODE_ENV === "development",  // disable SW in dev
});

export default withSerwist({ /* existing next config */ });
```

2. `app/sw.ts` — service worker with caching strategy:
```typescript
import { defaultCache } from "@serwist/next/worker";
import type { PrecacheEntry, SerwistGlobalConfig } from "serwist";
import { Serwist } from "serwist";

declare global {
  interface ServiceWorkerGlobalScope extends SerwistGlobalConfig {
    __SW_MANIFEST: (PrecacheEntry | string)[] | undefined;
  }
}

const serwist = new Serwist({
  precacheEntries: self.__SW_MANIFEST,
  skipWaiting: true,
  clientsClaim: true,
  navigationPreload: true,
  runtimeCaching: [
    // Calendar and shifts: StaleWhileRevalidate — fast load, background refresh
    {
      matcher: /^https?:\/\/.*\/api\/v1\/(shifts|calendar)/,
      handler: "StaleWhileRevalidate",
      options: {
        cacheName: "api-shifts-calendar",
        expiration: { maxEntries: 50, maxAgeSeconds: 24 * 60 * 60 },
      },
    },
    // Auth endpoints: NetworkOnly — never cache tokens
    {
      matcher: /^https?:\/\/.*\/api\/v1\/auth/,
      handler: "NetworkOnly",
    },
    // Payroll/sensitive data: NetworkFirst — only fall back to cache on error
    {
      matcher: /^https?:\/\/.*\/api\/v1\/(payroll|employees)/,
      handler: "NetworkFirst",
      options: { cacheName: "api-sensitive", networkTimeoutSeconds: 10 },
    },
    ...defaultCache,
  ],
});

serwist.addEventListeners();
```

3. `app/manifest.ts` — Next.js built-in manifest (no separate file needed in App Router):
```typescript
import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "VERA – Schichtplanung",
    short_name: "VERA",
    description: "PAB Schichtplanung und Abrechnung",
    start_url: "/",
    display: "standalone",
    background_color: "#eff1f5",  // Catppuccin Latte base
    theme_color: "#1e66f5",       // Catppuccin Latte blue
    icons: [
      { src: "/icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
```

4. `.gitignore` additions:
```
public/sw.js
public/sw.js.map
public/workbox-*.js
public/workbox-*.js.map
```

5. `tsconfig.json` — add `"webworker"` to `lib`:
```json
{ "compilerOptions": { "lib": ["dom", "dom.iterable", "esnext", "webworker"] } }
```

**Caching strategy rationale:**
- Shifts and calendar data: `StaleWhileRevalidate` — employees on mobile need instant load
- Auth tokens: `NetworkOnly` — must never be cached
- Payroll data: `NetworkFirst` — correctness matters more than speed; fallback for offline view
- Static assets (JS, CSS, images): `CacheFirst` via `defaultCache` precaching

**Web Push integration:** Serwist service worker registers the `push` event listener. The backend
VAPID infrastructure already works. The SW simply needs to handle the `push` event in `app/sw.ts`
to display notifications even when the app is closed — no additional backend changes needed.

---

## 6. Approval Workflow State Machine (ESS-01, ESS-02, ESS-04)

### Problem

Shift swap requests and absence requests need a state machine:
`pending → approved / rejected / cancelled`. The shift claim endpoint already has a race condition
(CONCERNS.md) that must be fixed alongside this.

### Recommendation: python-statemachine 2.6 (not 3.0) for explicit state modeling; application-level enum for DB persistence

**Confidence: MEDIUM** — python-statemachine is well-maintained but the integration pattern with
SQLAlchemy async is not officially documented; relies on established community patterns.

**Why a library over hand-coded enums:**
- State transition validation (can't go from `rejected` → `approved` without going through `pending`)
- Guard conditions (can't approve your own request)
- On-transition hooks (send notification, update related shift)
- Self-documenting: the state machine class IS the spec

**Version choice: 2.6 not 3.0**

python-statemachine 3.0 introduces statecharts (parallel states, SCXML compliance) which is
over-engineered for a simple linear approval flow. Stay on 2.6 until 3.x has more production
adoption. The StateMachine class from 2.x is preserved in 3.x with backward compatibility.

```bash
pip install "python-statemachine>=2.6,<3.0"
```

**Pattern: state machine for validation, SQLAlchemy enum for persistence**

Do not store state machine instances in the DB. Instead:
1. Define an `ApprovalStatus` enum in the model (`pending/approved/rejected/cancelled`)
2. Load the current status from DB into a transient state machine instance
3. Run the transition (raises `InvalidDefinition` if transition is invalid)
4. Persist the new status back to DB

```python
from statemachine import StateMachine, State

class AbsenceRequestFSM(StateMachine):
    pending   = State(initial=True)
    approved  = State(final=True)
    rejected  = State(final=True)
    cancelled = State(final=True)

    approve   = pending.to(approved)
    reject    = pending.to(rejected)
    cancel    = pending.to(cancelled) | approved.to(cancelled)  # can cancel approved too

    def on_enter_approved(self):
        # called synchronously — schedule async notification via Celery
        pass

# In the FastAPI endpoint:
async def approve_absence(absence_id: int, current_user: AdminUser, db: DB):
    absence = await db.get(EmployeeAbsence, absence_id)
    if not absence or absence.tenant_id != current_user.tenant_id:
        raise HTTPException(404)

    fsm = AbsenceRequestFSM(current_state=absence.status)
    try:
        fsm.approve()
    except InvalidDefinition as e:
        raise HTTPException(422, detail=str(e))

    absence.status = fsm.current_state.id  # "approved"
    absence.approved_by = current_user.id
    absence.approved_at = datetime.utcnow()
    await write_audit(db, ..., action="update", before={"status": "pending"}, after={"status": "approved"})
    await db.commit()
    # dispatch Celery notification task
```

**Shift swap request model** (new table `shift_swap_requests`):
```
id, tenant_id, requester_id, shift_id, target_employee_id (optional),
status (pending/approved/rejected/cancelled),
admin_id (who decided), admin_note, created_at, decided_at
```

**Race condition fix for shift claim (CONCERNS.md):** Use `SELECT ... FOR UPDATE` to lock the row
before the employee assignment check:
```python
result = await db.execute(
    select(Shift).where(Shift.id == shift_id).with_for_update()
)
```

**Alternative considered: `transitions` library (pytransitions)**
- More stars on GitHub but API is more complex for simple linear flows
- `python-statemachine` is cleaner for FastAPI async patterns
- Rejected in favor of `python-statemachine`

---

## 7. Application-Level Rate Limiting (Security Defense-in-Depth)

### Problem

Rate limiting exists only at Traefik. Direct backend access (dev, CI, staging, Traefik bypass)
has no protection.

### Recommendation: slowapi 0.1.x with Redis backend

**Confidence: MEDIUM** — slowapi is the most widely adopted FastAPI rate limiting library but has
moderate maintenance activity.

```bash
pip install slowapi
```

Apply only to auth endpoints (mirrors Traefik limits) as a fallback, not to every route:
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, storage_uri=settings.REDIS_URL)

@router.post("/auth/login")
@limiter.limit("10/minute")
async def login(request: Request, ...):
    ...
```

This is a defense-in-depth measure — it does not replace Traefik rate limiting.

---

## 8. Dependency Updates Required

**Confidence: HIGH** — based on official CVE reports and FastAPI project migration.

| Package | Current | Target | Reason |
|---------|---------|--------|--------|
| `python-jose` | 3.3.0 | **Remove** | CVE-2024-33663; abandoned |
| `PyJWT` | not installed | **2.12.1** | Replaces python-jose |
| `passlib` | 1.7.4 | **Remove** | Maintenance mode; use bcrypt directly |
| `bcrypt` | 4.0.1 | **4.2.x** | Compatibility fixes with passlib removal |

**passlib removal:** Use `bcrypt` directly for password hashing. The passlib API wraps bcrypt with
a compatibility shim; direct bcrypt usage is simpler and maintained:
```python
import bcrypt

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())
```

---

## Complete Additions to requirements.txt

```text
# Replaces python-jose
PyJWT==2.12.1

# Approval workflow state machine
python-statemachine>=2.6,<3.0

# Rate limiting (defense-in-depth)
slowapi==0.1.9

# Serwist is frontend-only (npm), no Python package needed
```

```text
# Remove from requirements.txt
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
```

```bash
# Frontend — add to package.json
npm install @serwist/next
npm install -D serwist
```

---

## What NOT to Use

| Category | Reject | Reason |
|----------|--------|--------|
| JWT library | `python-jose` | CVE-2024-33663, abandoned |
| JWT library | `joserfc` | Lower ecosystem adoption vs PyJWT |
| Audit log | `postgresql-audit` | Last meaningful release 2021, trigger complexity |
| Audit log | WAL/logical replication | Vastly overengineered for 7 users |
| PWA | `next-pwa` (shadowwalker) | Abandoned 2022, broken with App Router |
| PWA | `@ducanh2912/next-pwa` | Semi-maintained fork, less complete than Serwist |
| State machine | hand-coded enum transitions | No guard enforcement, easy to introduce illegal transitions |
| State machine | `python-statemachine>=3.0` | Statechart features (parallel states, SCXML) are overkill |
| State machine | `transitions` (pytransitions) | More complex API for no added benefit on linear flows |
| Rate limiting | Custom Redis middleware | Re-inventing slowapi; maintenance burden |
| PostgreSQL RLS | For tenant isolation | Application-level is sufficient and already tested; RLS adds operational complexity without benefit at VERA's scale |

---

## Sources

- PyJWT PyPI: https://pypi.org/project/PyJWT/ (version 2.12.1, 2026-03-13)
- FastAPI docs migration PR: https://github.com/fastapi/full-stack-fastapi-template/pull/1203
- FastAPI JWT discussion: https://github.com/fastapi/fastapi/discussions/11345
- Pydantic v2 strict mode: https://docs.pydantic.dev/latest/concepts/strict_mode/
- FastAPI OAuth2 scopes: https://fastapi.tiangolo.com/advanced/security/oauth2-scopes/
- Serwist getting started: https://serwist.pages.dev/docs/next/getting-started
- Next.js PWA guide: https://nextjs.org/docs/app/guides/progressive-web-apps
- python-statemachine: https://python-statemachine.readthedocs.io/
- slowapi: https://github.com/laurentS/slowapi
- JWT revocation strategies: https://www.michal-drozd.com/en/blog/jwt-revocation-strategies/
- PostgreSQL audit logging: https://oneuptime.com/blog/post/2026-01-21-postgresql-audit-logging/view
