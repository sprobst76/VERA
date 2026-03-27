# Architecture

**Analysis Date:** 2026-03-27

## Pattern Overview

**Overall:** Multi-tenant SaaS with layered REST API backend and SPA frontend

**Key Characteristics:**
- Every resource in the database is scoped to a `tenant_id`; no cross-tenant query is ever valid
- Backend is fully async (SQLAlchemy 2.0 async + FastAPI)
- Frontend is a Next.js App Router SPA — all protected pages live under the `(dashboard)` route group
- Celery handles scheduled tasks (reminders, monthly payroll) backed by Redis
- A separate SuperAdmin plane operates outside tenant context with its own JWT type and TOTP 2FA

---

## Layers

### Backend

**API Layer:**
- Purpose: Accept HTTP requests, validate input, enforce auth/RBAC, return responses
- Location: `backend/app/api/v1/`
- Contains: One file per domain (e.g. `shifts.py`, `payroll.py`, `employees.py`)
- Depends on: Service layer, models, schemas, `deps.py`
- Used by: Frontend (`api.ts`), external clients via API key

**Service Layer:**
- Purpose: Business logic that spans multiple models or requires domain rules
- Location: `backend/app/services/`
- Contains: `payroll_service.py`, `compliance_service.py`, `notification_service.py`, `pdf_service.py`, `recurring_shift_service.py`, `matching_service.py`
- Depends on: Models, `AsyncSession`, utility functions
- Used by: API layer and Celery tasks

**Model Layer:**
- Purpose: SQLAlchemy ORM definitions; single source of truth for table schema
- Location: `backend/app/models/`
- Contains: One file per entity (see Data Models section below)
- Depends on: `Base` from `database.py`
- Used by: Service layer, API layer

**Schema Layer:**
- Purpose: Pydantic v2 models for request validation and response serialization
- Location: `backend/app/schemas/`
- Contains: `employee.py`, `shift.py`, `payroll.py`, `absence.py`, `auth.py`, etc.
- Depends on: Nothing (pure Pydantic)
- Used by: API layer (`response_model=`, function parameter types)

**Core Layer:**
- Purpose: Infrastructure configuration and shared utilities
- Location: `backend/app/core/`
- Contains: `config.py` (Pydantic Settings), `database.py` (engine + session factory), `security.py` (JWT + bcrypt), `redis.py`
- Depends on: Environment variables / `.env`
- Used by: All other layers

**Tasks Layer:**
- Purpose: Asynchronous scheduled jobs
- Location: `backend/app/tasks/`
- Contains: `celery_app.py`, `reminder_tasks.py`, `payroll_tasks.py`
- Depends on: Service layer, `AsyncSession` (created fresh per task)
- Schedule: Every 5 min (type reminders), 08:00 daily (daily reminders), 1st of month 07:00 (payroll)

**Utils Layer:**
- Purpose: Stateless helpers
- Location: `backend/app/utils/`
- Contains: `german_holidays.py` — BW public holiday calculation (Gauss Easter formula + hardcoded fallback)

### Frontend

**Page Layer:**
- Purpose: Route-level components that own data fetching and page composition
- Location: `frontend/src/app/(dashboard)/` and `frontend/src/app/(auth)/`
- Contains: One directory per feature, each with `page.tsx`
- Depends on: `api.ts`, `useAuthStore`, TanStack Query, feature components

**Component Layer:**
- Purpose: Reusable UI components scoped to a domain or shared
- Location: `frontend/src/components/`
- Subdirectories: `calendar/`, `employees/`, `payroll/`, `shifts/`, `shared/`, `ui/`
- Key shared components: `ThemeToggle`, `AvailabilityGrid`, `CreateShiftModal`, `DemoBar`, `PushManager`
- `ui/` contains shadcn/ui primitives

**API Client Layer:**
- Purpose: All HTTP calls, token lifecycle, automatic token refresh
- Location: `frontend/src/lib/api.ts`
- Pattern: Axios instance `api` + named export objects per domain (`shiftsApi`, `employeesApi`, `payrollApi`, etc.)

**State Layer:**
- Purpose: Client-side auth state and SuperAdmin auth state
- Location: `frontend/src/store/`
- Contains: `auth.ts` (Zustand + persist middleware), `superadmin.ts`
- Tokens stored in `localStorage` (`access_token`, `refresh_token`)

---

## Data Flow

**Authenticated API Request:**

1. Frontend calls e.g. `shiftsApi.list()` from `api.ts`
2. Axios request interceptor reads `access_token` from `localStorage` and adds `Authorization: Bearer <token>` header
3. FastAPI router receives request; `CurrentUser` dependency in `deps.py` decodes JWT, loads `User` from DB
4. Route handler queries DB with `tenant_id == current_user.tenant_id` filter
5. Result serialized through Pydantic `response_model` schema; JSON returned
6. If response is 401, Axios response interceptor calls `/auth/refresh`, updates tokens, and retries original request once; on refresh failure redirects to `/login`

**Token Refresh:**
```
401 response → POST /auth/refresh {refresh_token}
             → new access_token + refresh_token stored in localStorage
             → original request retried with new access_token
```

**Payroll Calculation:**
1. Admin POSTs to `/api/v1/payroll/calculate` with `{employee_id, month}`
2. `PayrollService.calculate_month()` loads all completed shifts for that month
3. For each shift: looks up `ContractHistory` record valid on that date (SCD Type 2)
4. Calculates base wage + §3b surcharges per time-of-day/day-of-week/holiday rules
5. Writes `PayrollEntry` to DB; returns response with itemized breakdown

**Recurring Shift Generation:**
1. `RecurringShift` defines a weekly pattern (weekday + time range + validity window)
2. `RecurringShiftService.generate_shifts()` materializes concrete `Shift` rows for each date in the window
3. School/public holiday skipping via `HolidayProfile` and `german_holidays.py`
4. Generated `Shift` rows link back to `recurring_shift_id` for traceability

**Notification Dispatch:**
1. API endpoints call `NotificationService.dispatch(employee, event_type, message)`
2. Service checks `employee.notification_prefs` for enabled channels
3. Checks quiet hours (default 21:00–07:00 Europe/Berlin) — suppresses if active
4. Sends via: SMTP email, Telegram Bot API, Web Push (VAPID)
5. Writes `NotificationLog` entry with status (`sent` | `failed`)

**State Management:**
- Server state: TanStack Query (caching, background refresh, stale-while-revalidate)
- Auth state: Zustand with `persist` middleware (survives page reload via `localStorage`)
- No global client-side store for domain data — all fetched per page/component via `useQuery`

---

## Auth Flow

**Regular User (tenant-scoped):**

1. `POST /api/v1/auth/login` → verifies bcrypt hash, returns `{access_token, refresh_token}`
2. Access token payload: `{sub: user_id, tenant_id, role, type: "access", exp: +60min}`
3. Refresh token payload: `{sub: user_id, tenant_id, type: "refresh", exp: +7days}`
4. `POST /api/v1/auth/refresh` → issues new token pair (sliding window)
5. `useAuthStore.login()` stores tokens in `localStorage`; Zustand `persist` stores `{user, isAuthenticated}` under key `"vera-auth"`

**Self-registration is disabled.** `POST /auth/register` returns HTTP 410. New users are created by SuperAdmin (tenant creation) or invited via `POST /users/{id}/invite` → token email link → `POST /auth/accept-invite`.

**Password Reset:**
1. `POST /auth/forgot-password` → generates `reset_token` on `User`, sends email link
2. `GET /auth/check-reset/{token}` → validates expiry (1 hour)
3. `POST /auth/reset-password` → sets new password, clears token

**API Key Auth (machine-to-machine):**
- `X-API-Key` header → SHA-256 hash → lookup in `api_keys` table
- On match: loads the tenant's admin user as request context
- Implemented in `backend/app/api/v1/deps.py` within `get_current_user`

**SuperAdmin (cross-tenant):**
- Separate `super_admins` table; no `tenant_id`
- Two-step login: password check → short-lived `superadmin_challenge` token (5min) → TOTP verification → `superadmin` token (8h)
- SuperAdmin frontend at `/admin/*` uses `useSuperAdminStore` (separate Zustand store)
- Backend dependency `SuperAdminUser` in `deps.py` validates `type: "superadmin"` JWT claim

---

## Role-Based Access Control

**Roles (ascending privilege):**

| Role | Access |
|------|--------|
| `parent_viewer` | Read-only: `/calendar`, `/shifts` only. Route-guarded in `(dashboard)/layout.tsx` |
| `employee` | Own profile, own shifts, own absences, payroll read |
| `manager` | Employee-level + shift management, absence approval |
| `admin` | Full access including employees list, reports, settings |
| `superadmin` | Cross-tenant admin panel at `/admin/*` |

**Backend dependencies in `backend/app/api/v1/deps.py`:**
- `CurrentUser` — any active authenticated user (JWT or API key)
- `ManagerOrAdmin` — role must be `manager` or `admin`
- `AdminUser` — role must be `admin`
- `SuperAdminUser` — JWT type must be `superadmin`
- `ParentViewerOrHigher` — any role including `parent_viewer`
- `DB` — `AsyncSession` from `get_db()`

All are `Annotated[..., Depends(...)]` type aliases for use directly as function parameters.

---

## Multi-Tenancy

**Isolation mechanism:** Every table that holds business data has a `tenant_id UUID` column with a `ForeignKey("tenants.id", ondelete="CASCADE")`. All queries in the API layer include `WHERE tenant_id = current_user.tenant_id`.

**Tenant structure:**
- `Tenant.slug` — unique short identifier (used in some URLs)
- `Tenant.state` — Bundesland (default `"BW"`) — affects holiday calculation
- `Tenant.settings` — JSON column for mutable config:
  - `settings["smtp"]` — SMTP configuration
  - `settings["surcharges"]` — §3b surcharge rates (overrides defaults)
  - `settings["general"]["frontend_url"]` — used in invite/reset email links

**SuperAdmin** creates tenants; tenant admin manages users within their tenant.

---

## Key Data Models

All models inherit from `Base` (SQLAlchemy `DeclarativeBase`) in `backend/app/core/database.py`. All PKs are `UUID` (auto-generated with `uuid.uuid4`).

**`Tenant`** (`backend/app/models/tenant.py`)
- Root of all tenant-scoped data
- `settings: JSON` — mutable runtime config (SMTP, surcharges, frontend URL)
- Cascade deletes to `User`, `Employee`

**`User`** (`backend/app/models/user.py`)
- Login identity; has `role`, `tenant_id`, `hashed_password` (bcrypt)
- `ical_token` — unique secret for iCal feed URL (no auth required)
- `invite_token` / `reset_token` — time-limited one-use strings

**`Employee`** (`backend/app/models/employee.py`)
- Personnel record; optionally linked to a `User` via `user_id`
- `contract_type: str` — `minijob | part_time | full_time` (current snapshot)
- `availability_prefs: JSON` — weekly availability by weekday (`{"0": {"available": true, "from_time": "08:00", ...}}`)
- `qualifications: JSON` — list of skill tags
- `notification_prefs: JSON`, `telegram_chat_id`, `quiet_hours_start/end`

**`ContractHistory`** (`backend/app/models/contract_history.py`)
- SCD Type 2: time-versioned contract records per employee
- `valid_from: Date`, `valid_to: Date | None` (NULL = currently active)
- Snapshots all wage fields; `PayrollService` uses this to find the correct rate on any given date
- `assign-contract-type` endpoint handles open/close transitions automatically

**`ContractType`** (`backend/app/models/contract_type.py`)
- Group contract template; employees can be assigned to one via `EmployeeContractTypeMembership`
- Changes propagate via `ContractTypeHistory` and generate `ContractHistory` entries for all members

**`Shift`** (`backend/app/models/shift.py`)
- Core work record: `date`, `start_time`, `end_time`, `break_minutes`
- `status`: `planned | confirmed | completed | cancelled | cancelled_absence`
- `actual_start/end` — time-correction workflow fields
- `time_correction_status`: `none | pending | approved | rejected`
- Compliance flags auto-computed: `is_holiday`, `is_weekend`, `is_sunday`, `rest_period_ok`, `break_ok`, `minijob_limit_ok`
- Optional links: `template_id`, `recurring_shift_id`, `shift_type_id`
- `duration_hours` property handles overnight shifts (end < start → +1 day)

**`ShiftTemplate`** (`backend/app/models/shift.py`)
- Reusable shift pattern with `weekdays: JSON`, time, color
- Used by bulk shift creation and recurring shifts

**`RecurringShift`** (`backend/app/models/recurring_shift.py`)
- Defines a weekly recurring pattern with `valid_from / valid_until` window
- Links to `HolidayProfile` for school-holiday-aware skipping
- `RecurringShiftService` generates concrete `Shift` rows from this definition

**`ShiftType`** (`backend/app/models/shift_type.py`)
- Named categorization for shifts (e.g. "Frühdienst") with color and reminder config
- `reminder_enabled`, `reminder_minutes_before` — used by Celery `reminder_tasks.py`

**`EmployeeAbsence`** (`backend/app/models/absence.py`)
- Types: `vacation | sick | school_holiday | other`
- Status workflow: `pending → approved | rejected`
- Approved absences appear in calendar as all-day events

**`CareRecipientAbsence`** (`backend/app/models/absence.py`)
- Absence of the care recipient (the PAB holder's care needs stop)
- `shift_handling`: `cancelled_unpaid | carry_over | paid_anyway`

**`PayrollEntry`** (`backend/app/models/payroll.py`)
- Monthly payroll record per employee
- Stores both hours and wages broken down by surcharge category
- `status`: `draft | approved | paid`
- `ytd_gross` — year-to-date gross for minijob limit tracking
- `wage_details: JSON` — split detail when multiple contract periods in one month

**`HoursCarryover`** (`backend/app/models/payroll.py`)
- Explicit carry-over record when hours overflow monthly limit

**`HolidayProfile`** + `VacationPeriod` + `CustomHoliday` (`backend/app/models/holiday_profile.py`)
- Per-tenant school vacation calendars (BW preset + custom)
- Used by `RecurringShift` to skip school holidays

**`ApiKey`** (`backend/app/models/audit.py`)
- `key_hash: str` — SHA-256 of the raw key (never stored plaintext)
- `scopes: JSON`, optional `expires_at`

**`Webhook`** (`backend/app/models/audit.py`)
- Outbound webhook endpoints with event subscriptions and optional HMAC secret

**`NotificationLog`** (`backend/app/models/notification.py`)
- Append-only log of all notification attempts with `status` and `error`

**`ComplianceCheck`** / **`AuditLog`** (`backend/app/models/audit.py`)
- `ComplianceCheck` — results of ArbZG validation runs per shift
- `AuditLog` — general entity change log with `old_values` / `new_values` JSON

**`SuperAdmin`** (`backend/app/models/superadmin.py`)
- Separate table, no `tenant_id`; `totp_secret` + `totp_enabled` for 2FA

---

## Async Patterns

**Database:**
- `create_async_engine` + `async_sessionmaker` from SQLAlchemy 2.0
- `get_db()` yields `AsyncSession` via `AsyncSessionLocal`
- All queries use `await db.execute(select(...))` pattern
- Relationships must be loaded eagerly with `selectinload()` — lazy loading raises `MissingGreenlet` in async context
- `expire_on_commit=False` on the session factory prevents expired-object issues after commits

**Celery Tasks:**
- Celery itself is synchronous; tasks create a fresh `asyncio` event loop to run async DB operations
- Beat schedule defined in `backend/app/tasks/celery_app.py`: timezone `Europe/Berlin`
- Three beat tasks: type-based reminders (every 5min), daily reminders (08:00), monthly payroll (1st 07:00)

**FastAPI Lifespan:**
- `create_tables()` runs at startup (for local SQLite dev without Alembic)
- Redis connection closed at shutdown

---

## Error Handling

**Strategy:** HTTPException raised in API layer; services raise `ValueError` or `HTTPException` directly

**Patterns:**
- 404: `scalar_one_or_none()` check → `raise HTTPException(status_code=404)`
- 403: `AdminUser` / `ManagerOrAdmin` dependency auto-raises 403 if role insufficient
- 401: JWT decode failure in `get_current_user` → 401; API key mismatch → 403
- Notification failures are silently swallowed (best-effort delivery)
- Password reset / invite emails: failures caught and ignored, always return 200 to prevent enumeration

---

## Cross-Cutting Concerns

**CORS:** Configured in `main.py` via `CORSMiddleware`; allowed origins from `settings.ALLOWED_ORIGINS` (comma-separated env var)

**Rate Limiting:** Traefik middleware in `deploy/docker-compose.yml`:
- `/api/v1/auth/login`: 10 req/min average, burst 3
- `/api/v1/superadmin/login`: 5 req/min average, burst 2

**Security Headers:** Traefik sets HSTS, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`

**Swagger UI:** Only enabled when `DEBUG=true`; disabled in production (`docs_url=None`)

**German Holiday Logic:** `backend/app/utils/german_holidays.py` — uses `workalendar` library when available, falls back to hardcoded Gauss Easter calculation for BW public holidays

**iCal Feed:** Public endpoint `GET /calendar/ical/{ical_token}` — no auth, token is a 32-byte URL-safe secret stored on both `User` and `Employee`

---

*Architecture analysis: 2026-03-27*
