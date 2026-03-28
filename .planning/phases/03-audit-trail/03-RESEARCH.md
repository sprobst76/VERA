# Phase 3: Audit Trail — Research

**Researched:** 2026-03-28
**Domain:** Immutable audit logging — FastAPI/SQLAlchemy async, PostgreSQL REVOKE, Next.js admin UI
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AUDIT-01 | `AuditLog` table gets composite indexes on `(tenant_id, entity_type, entity_id)` and `(tenant_id, created_at)` | Alembic migration with idempotent inspect-check; model already exists without these indexes |
| AUDIT-02 | `audit_service.write()` helper (explicit, no ORM event hook) called in all write endpoints: create/update/delete for Shift, Employee, PayrollEntry, ContractHistory, EmployeeAbsence | `_write_audit` already wired in shifts.py only; must extend to 4 more endpoint modules |
| AUDIT-03 | Payroll changes logged with before/after JSON — `actual_hours`, `base_wage`, `total_gross` as structured fields | PayrollEntry model has these exact fields; pattern is to capture before-snapshot before mutation |
| AUDIT-04 | Admin-UI page shows audit log filterable by entity type, user, date range; read-only, admin-only | UI-SPEC approved; backend needs `GET /api/v1/audit-log` endpoint with query params |
| AUDIT-05 | `REVOKE UPDATE, DELETE ON audit_log FROM vera` — DB-level append-only enforcement | PostgreSQL application user is `vera` (confirmed from docker-compose.yml) |
</phase_requirements>

---

## Summary

The `audit_log` table and `AuditLog` ORM model already exist in VERA (created in the initial migration, `8eefccc3f51f`). The table has no composite indexes and no REVOKE has been applied. A local `_write_audit` helper exists in `shifts.py` but has not been extracted into a shared `audit_service.py`, and no other write endpoints (employees, payroll, absences, contract history) call it.

The core design question for this phase is already answered: explicit `audit_service.write()` calls in endpoint code, never ORM event listeners. The `shifts.py` pattern proves the before-snapshot approach works: capture a dict of affected fields before mutation, apply the mutation, then `db.add(AuditLog(...))` — all before `await db.commit()`. This guarantees atomicity because the audit INSERT and the business change share the same transaction.

The main work is (1) add composite indexes via an idempotent Alembic migration, (2) extract the local helper into `backend/app/services/audit_service.py`, (3) wire the new helper into employees.py, payroll.py, and absences.py, (4) add the read endpoint for the admin UI, (5) issue a `REVOKE` via Alembic and document the SQLite test workaround, and (6) build the frontend audit-log page per the approved UI-SPEC.

**Primary recommendation:** Extract the existing `_write_audit` pattern from `shifts.py` into a single `audit_service.write()` function. Use it as the canonical call site across all write endpoints. The Alembic REVOKE migration must skip execution on SQLite (tests use SQLite in-memory; `REVOKE` is a PostgreSQL-only statement).

---

## Project Constraints (from CLAUDE.md)

- Backend: FastAPI (Python 3.12), SQLAlchemy 2.0 async, PostgreSQL 16
- Frontend: Next.js 14 App Router, TypeScript, Tailwind CSS — **no shadcn component installs**; hand-built Tailwind + Catppuccin CSS vars
- Auth dependencies: `CurrentUser`, `AdminUser`, `ManagerOrAdmin` — Annotated Depends aliases in `deps.py`
- Multi-tenancy: all queries MUST filter by `tenant_id`
- Alembic migrations MUST be idempotent (inspect-check pattern)
- `down_revision` must point to current HEAD: `j4k5l6m7n8o9`
- NO async ORM event listeners (MissingGreenlet risk)
- `db.expire_all()` (synchronous, no await) after HTTP mutations in tests
- `selectinload()` for any relationship eager-loading in async sessions
- Tests: pytest + pytest-asyncio, SQLite in-memory + StaticPool

---

## Standard Stack

### Core (all already in requirements.txt)

| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| SQLAlchemy | 2.0 async | ORM + DB operations | Already in use |
| FastAPI | current | API endpoints | Already in use |
| Alembic | current | DB migrations | Already in use |
| PostgreSQL | 16 | Production database | `REVOKE` target |
| pytest + pytest-asyncio | current | Tests | Already configured |

### Supporting

| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| date-fns | current | Timestamp formatting in frontend | Already in use (`de` locale) |
| TanStack Query | current | Data fetching + cache in frontend | Already in use |

No new packages are required for this phase. All required libraries are already installed.

---

## Architecture Patterns

### Recommended Project Structure (additions only)

```
backend/app/
├── services/
│   └── audit_service.py          # NEW: shared audit_service.write() helper
├── api/v1/
│   └── audit_log.py              # NEW: GET /api/v1/audit-log endpoint
└── schemas/
    └── audit_log.py              # NEW: AuditLogOut Pydantic schema

frontend/src/
└── app/(dashboard)/
    └── audit-log/
        └── page.tsx              # NEW: admin-only audit log page
```

### Pattern 1: Explicit audit_service.write() — the canonical pattern

**What:** A standalone async function that creates an `AuditLog` row and adds it to the current session — no commit. The caller commits once after both the business change and the audit write are staged.

**When to use:** Every create, update, delete on Shift, Employee, PayrollEntry, ContractHistory, EmployeeAbsence.

**Signature (derived from existing `_write_audit` in shifts.py):**

```python
# Source: derived from backend/app/api/v1/shifts.py _write_audit (lines 41-52)
async def write(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    entity_type: str,          # "shift" | "employee" | "payroll" | "absence" | "contract_history"
    entity_id: uuid.UUID,
    action: str,               # "create" | "update" | "delete"
    old_values: dict | None = None,
    new_values: dict | None = None,
) -> None:
    log = AuditLog(
        tenant_id=tenant_id,
        user_id=user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        old_values=old_values,
        new_values=new_values,
    )
    db.add(log)
    # DO NOT commit here — caller owns the transaction
```

### Pattern 2: Before-snapshot capture

**What:** Before mutating an object, read the current field values into a plain dict.

**When to use:** Any `update` or `delete` action where before-values must be captured.

**Example (from existing shifts.py lines 273-284):**

```python
# Source: backend/app/api/v1/shifts.py lines 273-284
old_values = {f: str(getattr(shift, f)) for f in payload.model_dump(exclude_unset=True)}
# ... apply mutation ...
new_values = {f: str(getattr(shift, f)) for f in payload.model_dump(exclude_unset=True)}
await audit_service.write(db, tenant_id=..., user_id=..., entity_type="shift",
                           entity_id=shift_id, action="update",
                           old_values=old_values, new_values=new_values)
await db.commit()
```

**CRITICAL:** Capture the before-snapshot BEFORE calling `setattr`. After mutation, the ORM object reflects the new values.

### Pattern 3: Payroll before/after snapshot (AUDIT-03)

The three AUDIT-03 fields (`actual_hours`, `base_wage`, `total_gross`) must be explicitly captured as `float` — not string — so the frontend diff renderer can display them numerically.

```python
# For PayrollEntry update or recalculate endpoints
PAYROLL_AUDIT_FIELDS = ("actual_hours", "base_wage", "total_gross")

# Before mutation:
old_values = {
    f: float(getattr(entry, f)) if getattr(entry, f) is not None else None
    for f in PAYROLL_AUDIT_FIELDS
}
# After mutation:
new_values = {
    f: float(getattr(entry, f)) if getattr(entry, f) is not None else None
    for f in PAYROLL_AUDIT_FIELDS
}
await audit_service.write(db, ..., entity_type="payroll", action="update",
                           old_values=old_values, new_values=new_values)
await db.commit()
```

### Pattern 4: REVOKE migration with SQLite guard

**What:** An Alembic migration that issues `REVOKE UPDATE, DELETE ON audit_log FROM vera` in production (PostgreSQL only) and skips the statement in SQLite test environments.

**SQLite guard is mandatory** — SQLite does not support `REVOKE` and test runs will fail without it.

```python
# Source: pattern established in VERA project (CLAUDE.md idempotent migration rule)
def upgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name
    if dialect == "postgresql":
        op.execute("REVOKE UPDATE, DELETE ON audit_log FROM vera")
```

**The `vera` user is the application user** — confirmed from `deploy/docker-compose.yml` line 10: `POSTGRES_USER: vera`.

### Pattern 5: Composite index migration

**What:** Adds two composite indexes to `audit_log`. The table already exists (initial migration), so we only add indexes if they don't exist (idempotent inspect-check).

```python
# Source: pattern from VERA CLAUDE.md idempotent migration rules
def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    existing_indexes = {idx["name"] for idx in inspector.get_indexes("audit_log")}
    if "ix_audit_log_tenant_entity" not in existing_indexes:
        op.create_index(
            "ix_audit_log_tenant_entity",
            "audit_log",
            ["tenant_id", "entity_type", "entity_id"],
        )
    if "ix_audit_log_tenant_created" not in existing_indexes:
        op.create_index(
            "ix_audit_log_tenant_created",
            "audit_log",
            ["tenant_id", "created_at"],
        )
```

### Pattern 6: Read endpoint for admin UI

**What:** `GET /api/v1/audit-log` with query parameters for entity_type, date range (from/to), and pagination (limit/offset). Admin-only (`AdminUser` dependency).

```python
@router.get("", response_model=AuditLogPageOut)
async def list_audit_log(
    current_user: AdminUser,
    db: DB,
    entity_type: str | None = Query(None),
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
):
    # All queries MUST filter by tenant_id (CLAUDE.md multi-tenancy rule)
    conditions = [AuditLog.tenant_id == current_user.tenant_id]
    if entity_type:
        conditions.append(AuditLog.entity_type == entity_type)
    if from_date:
        conditions.append(AuditLog.created_at >= from_date)
    if to_date:
        # Include the full to_date day — add 1 day for exclusive upper bound
        conditions.append(AuditLog.created_at < to_date + timedelta(days=1))
    ...
```

**Response shape must include `total` count** for pagination bar (`{from}-{to} von {total}` in UI-SPEC).

### Anti-Patterns to Avoid

- **ORM event listeners for audit**: `@event.listens_for(Session, "after_flush")` — calling `await db.execute()` inside an event listener raises `MissingGreenlet`. Confirmed in ROADMAP.md critical pitfalls and CLAUDE.md.
- **Audit INSERT in a separate commit**: If `await db.commit()` is called for the business change and then again for the audit INSERT, a rollback of the business commit leaves an orphan audit row (violates AUDIT-02 success criterion 2).
- **Lazy-loading in the audit read endpoint**: If the response schema includes a relationship (e.g., User name from `user_id`), use `selectinload()` or a JOIN — never rely on lazy load in async sessions.
- **Using `inspect(conn)` for index existence**: SQLAlchemy's `get_indexes()` on SQLite may return an empty list for indexes not in the initial schema. For the test environment, both index names will simply not exist and `create_index` will run — this is safe because SQLite accepts `CREATE INDEX`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead |
|---------|-------------|-------------|
| Transaction atomicity | Custom two-phase commit logic | Stage `db.add(AuditLog(...))` before `await db.commit()` — SQLAlchemy handles atomicity |
| DB-level append-only | Application-layer delete guard | PostgreSQL `REVOKE UPDATE, DELETE ON audit_log FROM vera` |
| Pagination count | Manual COUNT query | `select(func.count()).where(...)` in the same endpoint |
| Frontend date formatting | Custom date formatter | `date-fns` `format()` with `de` locale — already in use across compliance/payroll pages |
| Action badge colors | Hardcoded style strings | CSS var `--ctp-green/blue/red` with `/ 0.12` alpha — same pattern as FlagBadge in compliance/page.tsx |

---

## Endpoint Coverage Audit

The following write endpoints currently have NO audit coverage. Each requires `audit_service.write()` calls:

### employees.py (no audit calls present)
| Endpoint | Action | entity_type | Before-snapshot needed? |
|----------|--------|-------------|------------------------|
| `POST /employees` | create | `employee` | No (no before-state) |
| `PUT /employees/{id}` | update | `employee` | Yes — `updates` dict fields |
| `DELETE /employees/{id}` (if exists) | delete | `employee` | Yes — full employee snapshot |
| `POST /employees/{id}/contracts` | create | `contract_history` | No |

### payroll.py (no audit calls present)
| Endpoint | Action | entity_type | Before-snapshot needed? |
|----------|--------|-------------|------------------------|
| `POST /payroll/calculate` | create | `payroll` | No (new entry) — but if replacing draft, capture old `actual_hours`/`base_wage`/`total_gross` |
| `PUT /payroll/{id}` | update | `payroll` | Yes — AUDIT-03: `actual_hours`, `base_wage`, `total_gross` |

### absences.py (no audit calls present)
| Endpoint | Action | entity_type | Before-snapshot needed? |
|----------|--------|-------------|------------------------|
| `POST /absences` | create | `absence` | No |
| `PUT /absences/{id}` | update | `absence` | Yes — `status` change is key field |
| `DELETE /absences/{id}` (if exists) | delete | `absence` | Yes |

### shifts.py (already partially wired)
| Endpoint | Action | Covered? | Gap |
|----------|--------|----------|-----|
| `PUT /shifts/{id}` | update | YES | None |
| `POST /shifts/{id}/confirm` | confirm | YES | None |
| `POST /shifts/{id}/claim` | claim | YES | None |
| `POST /shifts/{id}/time-correction` | submit | YES | None |
| `PUT /shifts/{id}/time-correction` | review | YES | None |
| `POST /shifts` | create | **NO** | Missing create audit |
| `DELETE /shifts/{id}` | delete | **NO** | Missing delete audit |

---

## Common Pitfalls

### Pitfall 1: Separate commit for audit INSERT

**What goes wrong:** Developer calls `await db.commit()` for the business change, then `db.add(audit_log); await db.commit()`. If the first commit succeeds and the process crashes before the second, the audit row is missing. Worse — if the business logic is rolled back via exception, the audit row is orphaned.

**Why it happens:** Feels natural to "write the audit separately."

**How to avoid:** Always call `db.add(audit_log)` before `await db.commit()` — the single commit captures both changes atomically. The existing `_write_audit` helper in `shifts.py` demonstrates this correctly.

**Warning signs:** Any `await db.commit()` that appears between the business mutation and the `_write_audit` call.

### Pitfall 2: ORM event listener for audit

**What goes wrong:** `@event.listens_for(Session, "after_flush")` with `await db.execute(...)` inside raises `MissingGreenlet` exception at runtime.

**Why it happens:** SQLAlchemy sync event hooks cannot await coroutines. The async session's event context does not permit async IO.

**How to avoid:** Use explicit `audit_service.write()` calls in endpoint code. Already decided in CONTEXT.md / ROADMAP.md.

**Warning signs:** Any import of `sqlalchemy.event` in audit-related code.

### Pitfall 3: REVOKE fails on SQLite in tests

**What goes wrong:** Alembic migration containing `REVOKE UPDATE, DELETE ON audit_log FROM vera` runs during tests (which use SQLite in-memory). SQLite raises `OperationalError: near "REVOKE": syntax error`.

**Why it happens:** REVOKE is a PostgreSQL SQL command; SQLite has no user/permission model.

**How to avoid:** Guard the REVOKE with `if conn.dialect.name == "postgresql":` in the migration's `upgrade()` function.

**Warning signs:** `OperationalError: near "REVOKE"` in test output.

### Pitfall 4: Before-snapshot captured after mutation

**What goes wrong:** `old_values` dict is populated from the ORM object after `setattr()` calls — it reflects the new values, so before/after are identical.

**Why it happens:** Snapshot code placed after mutation loop.

**How to avoid:** Always capture `old_values` BEFORE the `setattr()` or model update loop. The `shifts.py` pattern (lines 273-284) is the reference.

**Warning signs:** `old_values` and `new_values` are identical in the audit log.

### Pitfall 5: Missing `total` count in audit-log API response

**What goes wrong:** Frontend PaginationBar displays `{from}-{to} von {total}` — if the endpoint only returns rows without a total count, the pagination cannot render the summary.

**Why it happens:** Endpoint returns `list[AuditLogOut]` without a wrapper object containing `total`.

**How to avoid:** Return a `{ items: [...], total: N }` envelope. Define `AuditLogPageOut` schema with `items: list[AuditLogOut]` and `total: int`.

### Pitfall 6: payroll.py `calculate` replaces existing draft — audit must capture the deleted draft's values

**What goes wrong:** `POST /payroll/calculate` deletes any existing draft entry (`await db.delete(existing); await db.flush()`) before creating a new one. The before-values of the old draft are lost if not captured before deletion.

**Why it happens:** The delete-then-recreate pattern doesn't naturally expose a before/after comparison.

**How to avoid:** If `existing` is not None, capture `old_values` from `existing` before `await db.delete(existing)`. Write an `update` audit entry using those old values and the new entry's computed values after `await db.commit()`.

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| ORM event hooks for audit | Explicit helper calls in endpoint code | Required — async events cannot await DB operations |
| Single `action` field for shift | Fine-grained actions: `update`, `confirm`, `claim`, `time_correction_submit`, `time_correction_review` | More searchable; frontend filters on `create`/`update`/`delete` so `confirm`/`claim` map to `update` action label |
| No DB-level write protection | PostgreSQL REVOKE | True append-only guarantee even against compromised application code |

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | `backend/pytest.ini` (asyncio_mode=auto) |
| Quick run command | `cd backend && python3 -m pytest tests/test_audit.py -q` |
| Full suite command | `cd backend && python3 -m pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AUDIT-01 | Composite indexes exist on audit_log | integration | `pytest tests/test_audit.py::test_audit_log_indexes -x` | ❌ Wave 0 |
| AUDIT-02 | Shift create/update/delete produce AuditLog row in same tx | integration | `pytest tests/test_audit.py::test_shift_mutations_produce_audit_rows -x` | ❌ Wave 0 |
| AUDIT-02 | Employee create/update produce AuditLog row | integration | `pytest tests/test_audit.py::test_employee_mutations_produce_audit_rows -x` | ❌ Wave 0 |
| AUDIT-02 | Absence create/update produces AuditLog row | integration | `pytest tests/test_audit.py::test_absence_mutations_produce_audit_rows -x` | ❌ Wave 0 |
| AUDIT-02 | PayrollEntry produce AuditLog row | integration | `pytest tests/test_audit.py::test_payroll_mutations_produce_audit_rows -x` | ❌ Wave 0 |
| AUDIT-02 | Rolled-back mutation produces no orphan row | integration | `pytest tests/test_audit.py::test_rollback_no_orphan_audit_row -x` | ❌ Wave 0 |
| AUDIT-03 | Payroll audit entries include actual_hours, base_wage, total_gross | integration | `pytest tests/test_audit.py::test_payroll_audit_before_after_fields -x` | ❌ Wave 0 |
| AUDIT-04 | GET /api/v1/audit-log returns paginated results with total | integration | `pytest tests/test_audit.py::test_audit_log_api_pagination -x` | ❌ Wave 0 |
| AUDIT-04 | Filter by entity_type and date range works | integration | `pytest tests/test_audit.py::test_audit_log_api_filters -x` | ❌ Wave 0 |
| AUDIT-05 | REVOKE migration skips on SQLite | unit | `pytest tests/test_audit.py::test_revoke_migration_sqlite_skip -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `cd backend && python3 -m pytest tests/test_audit.py -q`
- **Per wave merge:** `cd backend && python3 -m pytest tests/ -q`
- **Phase gate:** Full suite green (`268+ tests pass`) before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `backend/tests/test_audit.py` — all AUDIT-01 through AUDIT-05 tests
- [ ] `backend/app/services/audit_service.py` — extracted service module
- [ ] `backend/app/api/v1/audit_log.py` — read endpoint
- [ ] `backend/app/schemas/audit_log.py` — `AuditLogOut` + `AuditLogPageOut` Pydantic schemas
- [ ] Alembic migration for composite indexes + REVOKE (new revision after `j4k5l6m7n8o9`)
- [ ] `frontend/src/app/(dashboard)/audit-log/page.tsx` — admin UI page

---

## Environment Availability

Step 2.6: SKIPPED (no external dependencies beyond existing project stack; all tools confirmed already in use).

---

## Code Examples

### audit_service.py — full module skeleton

```python
# backend/app/services/audit_service.py
import uuid
from app.models.audit import AuditLog
from sqlalchemy.ext.asyncio import AsyncSession


async def write(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
    action: str,
    old_values: dict | None = None,
    new_values: dict | None = None,
) -> None:
    """
    Stage an AuditLog INSERT into the current transaction.
    Caller MUST call db.commit() after this to persist both the business
    change and the audit row atomically.
    DO NOT commit inside this function.
    """
    log = AuditLog(
        tenant_id=tenant_id,
        user_id=user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        old_values=old_values,
        new_values=new_values,
    )
    db.add(log)
```

### AuditLogPageOut schema

```python
# backend/app/schemas/audit_log.py
import uuid
from datetime import datetime
from pydantic import BaseModel


class AuditLogOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID | None
    user_id: uuid.UUID | None
    entity_type: str
    entity_id: uuid.UUID | None
    action: str
    old_values: dict | None
    new_values: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogPageOut(BaseModel):
    items: list[AuditLogOut]
    total: int
```

### Idempotent index migration skeleton

```python
# backend/alembic/versions/k5l6m7n8o9p0_audit_log_indexes_and_revoke.py
revision = "k5l6m7n8o9p0"
down_revision = "j4k5l6m7n8o9"

def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    existing = {idx["name"] for idx in inspector.get_indexes("audit_log")}

    if "ix_audit_log_tenant_entity" not in existing:
        op.create_index("ix_audit_log_tenant_entity", "audit_log",
                        ["tenant_id", "entity_type", "entity_id"])
    if "ix_audit_log_tenant_created" not in existing:
        op.create_index("ix_audit_log_tenant_created", "audit_log",
                        ["tenant_id", "created_at"])

    # REVOKE: PostgreSQL only — SQLite used in tests has no permission model
    if conn.dialect.name == "postgresql":
        op.execute("REVOKE UPDATE, DELETE ON audit_log FROM vera")
```

### Frontend api.ts addition

```typescript
// Add to frontend/src/lib/api.ts
export const auditLogApi = {
  list: (params: {
    entity_type?: string;
    from_date?: string;
    to_date?: string;
    limit?: number;
    offset?: number;
  }) => api.get("/audit-log", { params }),
};
```

---

## Open Questions

1. **`confirm` / `claim` / `time_correction_*` actions — should they be mapped to `"update"` in the audit log or kept as distinct action strings?**
   - What we know: the UI-SPEC shows only `create`/`update`/`delete` as badge options (German: `angelegt`/`geändert`/`gelöscht`)
   - What's unclear: whether these fine-grained shift actions should be stored verbatim (richer audit data) or normalized to `"update"` (simpler UI filtering)
   - Recommendation: Store verbatim (`"confirm"`, `"claim"`, etc.) in `audit_log.action` — map to the German badge label `"geändert"` in the frontend display layer. This preserves full detail without changing the backend schema.

2. **Should the `GET /api/v1/audit-log` endpoint join User for display name?**
   - What we know: UI-SPEC shows a "Benutzer" column with user display name or email
   - What's unclear: whether to join User in the query or return raw `user_id` and resolve in frontend
   - Recommendation: Return `user_id` only in `AuditLogOut`; have the frontend maintain a `usersApi.list()` lookup table. This keeps the audit endpoint simple and avoids a `selectinload(User)` that adds query complexity.

3. **Does `REVOKE` cover the Celery worker user?**
   - What we know: All services connect as `vera` (confirmed from docker-compose.yml — same DATABASE_URL)
   - What's unclear: nothing — Celery worker uses the same `vera` credentials, so the REVOKE applies to all application services. This is the desired behavior.
   - Recommendation: Proceed with single REVOKE against `vera`. Document in plan that superadmin access (postgres superuser on VPS) can still modify audit rows for break-glass recovery.

---

## Sources

### Primary (HIGH confidence)

- `backend/app/models/audit.py` — AuditLog ORM model (no indexes, table already exists)
- `backend/app/api/v1/shifts.py` lines 41-52, 273-284, 337-345 — proven `_write_audit` pattern
- `backend/alembic/versions/8eefccc3f51f_initial.py` lines 121-135 — audit_log table DDL (no indexes)
- `backend/alembic/versions/j4k5l6m7n8o9_add_token_version.py` — idempotent inspect-check pattern
- `deploy/docker-compose.yml` line 10 — `POSTGRES_USER: vera` (application DB user for REVOKE)
- `.planning/phases/03-audit-trail/03-UI-SPEC.md` — approved UI contract
- `CLAUDE.md` — project conventions, multi-tenancy rules, SQLAlchemy async pitfalls
- `ROADMAP.md` lines 203-204 — audit tx atomicity and no-event-listener decisions

### Secondary (MEDIUM confidence)

- PostgreSQL 16 docs on REVOKE: `REVOKE privilege ON table FROM role` syntax confirmed standard
- SQLAlchemy 2.0 async docs: `db.add()` stages INSERT in current transaction; `db.commit()` flushes atomically

### Tertiary (LOW confidence)

None — all findings are grounded in the project codebase and official documentation.

---

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — all libraries already in use, no new dependencies
- Architecture patterns: HIGH — derived directly from existing codebase patterns
- AuditLog model state: HIGH — verified by reading the ORM model and initial migration
- REVOKE target user: HIGH — confirmed `vera` from docker-compose.yml
- Composite index naming: HIGH — standard SQLAlchemy `create_index` pattern
- Pitfalls: HIGH — derived from existing code bugs and ROADMAP.md explicit warnings

**Research date:** 2026-03-28
**Valid until:** 2026-06-01 (stable domain; no fast-moving dependencies)
