# Coding Conventions

**Analysis Date:** 2026-03-27

---

## Python – General

**Type Hints:**
- All function parameters and return types are fully annotated.
- `uuid.UUID` used everywhere (not `str`) for IDs in service/model layer.
- `Optional[X]` written as `X | None` (Python 3.10+ union style).
- `TYPE_CHECKING` guard used for circular imports in services (e.g. `payroll_service.py`).

**Async/Await:**
- All DB operations are `async/await` via SQLAlchemy 2.0 `AsyncSession`.
- Service constructors take `db: AsyncSession` and store it as `self.db`.
- `await db.execute(select(...))` → `.scalar_one_or_none()` or `.scalars().all()`.
- `await db.commit()` followed by `await db.refresh(obj)` after every write.
- `db.expire_all()` (synchronous, no `await`) used only in tests after HTTP mutations.

**Logging:**
```python
import logging
logger = logging.getLogger(__name__)
```
Module-level logger, no custom handler setup — uses default FastAPI logging.

---

## Backend – API Layer (`backend/app/api/v1/`)

**Router Definition:**
```python
router = APIRouter(tags=["shifts"])
```
Each module defines its own `router`. All routers registered in `backend/app/main.py`
with prefix `"/api/v1"`.

**Dependency Injection:**
All auth and DB dependencies come from `backend/app/api/deps.py` as `Annotated` type aliases:

```python
CurrentUser    # any authenticated user (role: admin | manager | employee | parent_viewer)
AdminUser      # role == "admin" only
ManagerOrAdmin # role in ("admin", "manager")
ParentViewerOrHigher # role in ("admin", "manager", "parent_viewer")
SuperAdminUser # SuperAdmin (separate JWT type "superadmin")
DB             # Annotated[AsyncSession, Depends(get_db)]
```

Use directly as parameter types, no `Depends()` call at use site:
```python
@router.get("/something")
async def get_something(current_user: CurrentUser, db: DB):
    ...
```

**Response Models:**
Every endpoint has an explicit `response_model=`:
```python
@router.get("", response_model=list[ShiftOut])
@router.post("", response_model=ShiftOut, status_code=status.HTTP_201_CREATED)
@router.put("/{id}", response_model=ShiftOut)
@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
```

**HTTP Status Codes:**
- `200` – successful GET/PUT
- `201` – successful POST (create)
- `204` – successful DELETE (no body)
- `400` – bad request / business rule violation (e.g. wrong password, inactive user)
- `401` – unauthenticated (invalid/missing JWT)
- `403` – forbidden (wrong role, invalid API key)
- `404` – not found
- `409` – conflict (e.g. claiming an already-taken shift)
- `422` – validation error (Pydantic schema failure)

**Error Handling:**
```python
raise HTTPException(status_code=404, detail="Template not found")
raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
```
No custom exception classes — always `HTTPException` with explicit `status_code` and `detail` string.

**Payload Updates:**
```python
for field, value in payload.model_dump(exclude_unset=True).items():
    setattr(obj, field, value)
await db.commit()
await db.refresh(obj)
```
Always `exclude_unset=True` on partial updates so None values from optional fields don't overwrite existing data.

---

## Backend – Database Layer (`backend/app/models/`)

**ORM Style:**
SQLAlchemy 2.0 `Mapped` / `mapped_column` with full type annotations:
```python
class Employee(Base):
    __tablename__ = "employees"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
```

**Tenant Filtering:**
Every query MUST filter by `tenant_id`. Pattern:
```python
result = await db.execute(
    select(Employee).where(
        Employee.tenant_id == current_user.tenant_id,
        Employee.id == employee_id,
    )
)
```
Never omit the `tenant_id` filter — it is the multi-tenancy boundary.

**Relationships:**
Declare relationships in models but always use `selectinload()` in queries when
you need related objects. Never access relationship attributes directly on async sessions
(triggers lazy-load / `MissingGreenlet` error):
```python
# WRONG – lazy-load in async:
profile.vacation_periods = [...]

# CORRECT:
select(HolidayProfile).options(selectinload(HolidayProfile.vacation_periods))
```

**JSON Columns:**
Used for flexible fields: `availability_prefs`, `qualifications`, `notification_prefs`,
`emergency_contact`, `Tenant.settings`. Type hint: `Mapped[dict]` or `Mapped[list]`.

**Timestamps:**
```python
created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
)
```
Always `timezone=True` and `datetime.now(timezone.utc)` — never naive datetimes.

---

## Backend – Pydantic Schemas (`backend/app/schemas/`)

**Structure per resource:**
- `XxxCreate` – input for POST (required fields, no `id`/`tenant_id`)
- `XxxUpdate` – input for PUT (all fields `Optional`, `exclude_unset=True` on update)
- `XxxOut` – response schema with `model_config = {"from_attributes": True}`

**from_attributes:**
All `Out` schemas have:
```python
model_config = {"from_attributes": True}
```
This enables ORM-to-Pydantic serialization.

**RBAC via separate schemas:**
`EmployeePublicOut` (name + qualifications only) vs `EmployeeOut` (full data incl. salary).
Endpoint returns different schema based on caller role.

**Optional fields:**
```python
email: EmailStr | None = None
weekly_hours: float | None = None
```
Uses Python union syntax, not `Optional[...]`.

---

## Backend – Migrations (`backend/alembic/versions/`)

**Idempotency rule:** Migrations MUST use `inspect()` checks because `lifespan()` in
`main.py` calls `create_tables()` (SQLAlchemy `metadata.create_all()`) before Alembic runs.

```python
from sqlalchemy.engine.reflection import Inspector

def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)

    # For new tables:
    if "my_table" not in inspector.get_table_names():
        op.create_table("my_table", ...)

    # For new columns:
    cols = [c["name"] for c in inspector.get_columns("existing_table")]
    if "new_column" not in cols:
        op.add_column("existing_table", sa.Column("new_column", ...))
```

**`down_revision`:** Always point to the actual HEAD from
`alembic heads` output before creating a new revision — never copy from an old file.

**ContractHistory (SCD Type 2):**
- `valid_to = None` → currently active record
- Close old record (`valid_to = today`), create new one for changes
- `assign-contract-type` endpoint handles this automatically when `valid_from` is provided

---

## Frontend – Component Structure

**"use client" placement:**
All dashboard pages and any component using hooks, browser APIs, or event handlers
gets `"use client"` as the first line. Layout files (`layout.tsx`) also use `"use client"`
when they contain hooks (e.g. `(dashboard)/layout.tsx`).

**Page files:**
- Located at `frontend/src/app/(dashboard)/[feature]/page.tsx`
- Always `"use client"`
- Import from `@/lib/api` for data fetching
- Use TanStack Query (`useQuery`, `useMutation`) for all server state

**Component naming:**
- PascalCase for React components: `ConfirmModal`, `CreateShiftModal`, `ThemeToggle`
- camelCase for utility functions and hooks: `auth_headers`, `useSwipe`, `useAuthStore`
- Shared components in `frontend/src/components/shared/`

**Inline style constants:**
Named constant objects for repeated styles:
```typescript
const inputCls = "w-full px-3 py-2 rounded-lg border border-border bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring";
const labelCls = "block text-xs font-medium text-muted-foreground mb-1";
```

---

## Frontend – Data Fetching

**All API calls go through `frontend/src/lib/api.ts`.**
Never use `fetch()` directly. Use the exported `api` axios instance or the grouped
API objects.

**Grouped API objects pattern:**
```typescript
export const employeesApi = {
  list: (activeOnly = true) =>
    api.get("/employees", { params: { active_only: activeOnly } }),
  me: () => api.get("/employees/me"),
  get: (id: string) => api.get(`/employees/${id}`),
  create: (data: Record<string, unknown>) => api.post("/employees", data),
  update: (id: string, data: Record<string, unknown>) =>
    api.put(`/employees/${id}`, data),
};
```

**TanStack Query pattern:**
```typescript
const { data, isLoading } = useQuery({
  queryKey: ["employees"],
  queryFn: () => employeesApi.list().then(r => r.data),
});

const mutation = useMutation({
  mutationFn: (data) => shiftsApi.create(data),
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ["shifts"] }),
});
```

**Auth token storage:** `localStorage` (`access_token`, `refresh_token`).
Token attached via request interceptor. Auto-refresh on 401 via response interceptor.

**Auth state:** Zustand store at `frontend/src/store/auth.ts` (`useAuthStore`).

---

## Frontend – Theme System

**Catppuccin Latte (light) + Mocha (dark).**
CSS custom properties defined in `globals.css`. All color tokens prefixed `--ctp-`.

**Color usage:**
```tsx
// Catppuccin semantic colors:
style={{ color: "rgb(var(--ctp-blue))" }}
style={{ backgroundColor: "rgb(var(--ctp-blue) / 0.12)" }}  // with alpha
style={{ color: "rgb(var(--ctp-green))" }}
style={{ color: "rgb(var(--ctp-red))" }}
style={{ color: "rgb(var(--ctp-overlay1))" }}

// Semantic Tailwind tokens (prefer these for structural elements):
className="bg-card text-foreground border-border bg-muted bg-background"
className="text-muted-foreground"
```

**Status colors:** Defined as `Record<string, React.CSSProperties>` constants within
each page component — do not hardcode inline per-instance.

**Icons:** `lucide-react` for all icons. Import only what is needed per file.

---

## Frontend – Navigation

**Adding a new page:**
1. Create `frontend/src/app/(dashboard)/[feature]/page.tsx` with `"use client"`
2. Add nav entry to `navItems` in `frontend/src/app/(dashboard)/layout.tsx`:
   ```typescript
   { href: "/feature", label: "Label", icon: IconName, adminOnly: false, parentViewerVisible: false }
   ```
3. Add API methods to `frontend/src/lib/api.ts`

**Route guards:** Handled in `(dashboard)/layout.tsx` via `useAuthStore` + `useRouter`.
Parent viewer routes filtered by `parentViewerVisible` flag.

---

## Import Patterns

**Backend:**
```python
# Standard library first
import uuid
from datetime import date, datetime, timezone

# Third-party
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

# Internal – models
from app.models.employee import Employee
from app.models.shift import Shift

# Internal – schemas, services, deps
from app.api.deps import DB, AdminUser, CurrentUser
from app.schemas.shift import ShiftCreate, ShiftOut
```

**Frontend:**
```typescript
// React/framework first
import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

// Internal API + stores
import { shiftsApi, employeesApi } from "@/lib/api";
import { useAuthStore } from "@/store/auth";

// Utilities
import { format, parseISO } from "date-fns";
import { de } from "date-fns/locale";

// Icons
import { Plus, Trash2, Check } from "lucide-react";

// Components
import { CreateShiftModal } from "@/components/shared/CreateShiftModal";
```

**Path alias:** `@/` maps to `frontend/src/` in both `tsconfig.json` and `vitest.config.ts`.

---

## File Naming

| Context | Convention | Example |
|---|---|---|
| Backend API modules | snake_case | `shift_types.py`, `admin_settings.py` |
| Backend model files | snake_case, singular | `employee.py`, `contract_history.py` |
| Frontend pages | `page.tsx` inside feature dir | `shifts/page.tsx` |
| Frontend components | PascalCase `.tsx` | `CreateShiftModal.tsx` |
| Frontend utility libs | camelCase `.ts` | `recurringEventUtils.ts` |
| Test files (backend) | `test_` prefix | `test_shifts.py` |
| Test files (frontend) | `.test.ts` suffix | `api-care-absences.test.ts` |

---

*Convention analysis: 2026-03-27*
