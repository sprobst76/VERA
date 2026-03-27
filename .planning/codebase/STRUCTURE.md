# Codebase Structure

**Analysis Date:** 2026-03-27

## Directory Layout

```
VERA/
├── backend/                        # FastAPI application
│   ├── app/
│   │   ├── main.py                 # App factory, router registration, lifespan
│   │   ├── core/                   # Infra: config, DB, security, Redis
│   │   ├── models/                 # SQLAlchemy ORM models
│   │   ├── schemas/                # Pydantic v2 request/response schemas
│   │   ├── api/
│   │   │   └── v1/                 # All REST endpoints + deps.py
│   │   ├── services/               # Business logic services
│   │   ├── tasks/                  # Celery app + scheduled tasks
│   │   └── utils/                  # Stateless helpers (holiday logic)
│   ├── alembic/
│   │   ├── versions/               # Migration files (committed, idempotent)
│   │   └── env.py                  # Alembic async env setup
│   ├── tests/
│   │   ├── conftest.py             # Fixtures: engine, db, client, tenant, users
│   │   └── test_*.py               # 268 tests (SQLite in-memory)
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── pytest.ini                  # asyncio_mode=auto
│   └── seed_demo.py                # Demo data seeder
├── frontend/                       # Next.js 14 App Router
│   └── src/
│       ├── app/
│       │   ├── (auth)/             # Public auth pages (no sidebar)
│       │   │   ├── login/
│       │   │   ├── register/
│       │   │   ├── accept-invite/
│       │   │   ├── forgot-password/
│       │   │   └── reset-password/
│       │   ├── (dashboard)/        # Protected pages with sidebar layout
│       │   │   ├── layout.tsx      # Auth guard, sidebar nav, route guard for parent_viewer
│       │   │   ├── page.tsx        # Dashboard/overview
│       │   │   ├── calendar/       # react-big-calendar with overnight split
│       │   │   ├── shifts/         # Shift list + Regeltermine (recurring) tab
│       │   │   ├── employees/      # Employee list + detail view + modals
│       │   │   ├── absences/       # Absence management + approval
│       │   │   ├── account/        # Own profile / Mein Profil
│       │   │   ├── payroll/        # Payroll calculation + PDF download
│       │   │   ├── compliance/     # ArbZG violation list
│       │   │   ├── notifications/  # Notification log + preferences
│       │   │   ├── reports/        # Hours, minijob status, surcharge reports
│       │   │   └── settings/       # 4-tab settings: Planung|Abrechnung|Profil|System
│       │   └── admin/              # SuperAdmin panel (separate auth)
│       │       ├── login/          # 2-step: password → TOTP
│       │       ├── tenants/        # Tenant CRUD
│       │       ├── admins/         # SuperAdmin management
│       │       └── account/        # SuperAdmin profile
│       ├── components/
│       │   ├── calendar/           # Calendar event components
│       │   ├── employees/          # Employee detail components
│       │   ├── payroll/            # Payroll table/card components
│       │   ├── shifts/             # Shift-specific components
│       │   ├── shared/             # Cross-feature shared components
│       │   │   ├── ThemeToggle.tsx
│       │   │   ├── AvailabilityGrid.tsx
│       │   │   ├── CreateShiftModal.tsx
│       │   │   ├── DemoBar.tsx
│       │   │   ├── PushManager.tsx
│       │   │   └── TimeInput.tsx
│       │   └── ui/                 # shadcn/ui primitives (button, dialog, etc.)
│       ├── hooks/
│       │   └── useSwipe.ts         # Touch swipe hook (mobile calendar nav)
│       ├── lib/
│       │   ├── api.ts              # Axios client + all API call functions
│       │   └── utils.ts            # cn() class merger, misc helpers
│       ├── store/
│       │   ├── auth.ts             # Zustand: user auth state + login/logout
│       │   └── superadmin.ts       # Zustand: superadmin auth state
│       └── test/ + __tests__/      # Vitest test files (excluded from tsconfig)
├── deploy/                         # Production Docker Compose config
│   ├── docker-compose.yml          # 6 services: api, web, db, redis, celery, beat
│   ├── Dockerfile.backend
│   ├── Dockerfile.frontend
│   ├── backup.sh
│   ├── restore.sh
│   └── deploy.sh
├── traefik/                        # Traefik reverse proxy config
├── data/                           # Local log storage (gitignored in deploy/)
│   └── logs/
├── migration/                      # One-off data migration scripts
├── .github/
│   └── workflows/
│       └── deploy.yml              # CI/CD: test → build → push GHCR → SSH deploy
├── docker-compose.yml              # Local dev compose (hot-reload, local volumes)
├── CLAUDE.md                       # Project conventions for Claude Code
├── TODO.md
├── CHANGELOG.md
└── start-backend.sh / start-frontend.sh  # Quick dev start scripts
```

---

## Directory Purposes

**`backend/app/core/`:**
- Purpose: Application infrastructure wiring — nothing domain-specific lives here
- Key files:
  - `config.py`: `Settings` class (Pydantic BaseSettings); reads `.env`; exported as singleton `settings`
  - `database.py`: `engine`, `AsyncSessionLocal`, `Base`, `get_db()`, `create_tables()`
  - `security.py`: `hash_password()`, `verify_password()`, `create_access_token()`, `create_refresh_token()`, `decode_token()`, superadmin token variants
  - `redis.py`: Optional Redis client; gracefully handles missing Redis

**`backend/app/models/`:**
- Purpose: Single source of truth for database schema
- `__init__.py`: Imports all models so `create_tables()` / Alembic sees them
- Key files: `tenant.py`, `user.py`, `employee.py`, `shift.py`, `payroll.py`, `absence.py`, `contract_history.py`, `contract_type.py`, `audit.py`, `notification.py`, `recurring_shift.py`, `shift_type.py`, `holiday_profile.py`, `superadmin.py`

**`backend/app/api/v1/`:**
- Purpose: HTTP boundary — one file per domain, each exports a `router`
- `deps.py`: All FastAPI dependency functions and type aliases (`CurrentUser`, `AdminUser`, `ManagerOrAdmin`, `SuperAdminUser`, `ParentViewerOrHigher`, `DB`)
- All routers registered in `main.py` under prefix `/api/v1`
- Exception: `calendar_router` registered without prefix (iCal public feeds)

**`backend/app/services/`:**
- Purpose: Domain business logic callable from both API routes and Celery tasks
- All services take `AsyncSession` in `__init__`
- `payroll_service.py`: Monthly wage calculation with SCD contract history and §3b surcharges
- `compliance_service.py`: ArbZG rest period, break, and minijob limit checks
- `notification_service.py`: Multi-channel dispatch (email, Telegram, Web Push) with quiet hours
- `pdf_service.py`: reportlab-based payroll PDF generation
- `recurring_shift_service.py`: Materializes `Shift` rows from `RecurringShift` patterns
- `matching_service.py`: Employee matching/suggestions for open shifts

**`backend/app/tasks/`:**
- Purpose: Celery task definitions and beat schedule
- `celery_app.py`: Celery instance + beat schedule (3 schedules, Europe/Berlin tz)
- `reminder_tasks.py`: Shift reminders (type-based every 5min, daily at 08:00)
- `payroll_tasks.py`: Monthly automatic payroll creation (1st of month 07:00)

**`backend/alembic/versions/`:**
- Purpose: Database migration history — all files are committed
- All migrations must be idempotent (use `inspect(conn)` to check for existing tables/columns)
- Current HEAD: `i3j4k5l6m7n8` (add_employee_contract_type_memberships)

**`backend/tests/`:**
- `conftest.py`: Fixtures using `StaticPool` SQLite for test isolation
- Available fixtures: `engine`, `db`, `client`, `tenant`, `admin_user`, `employee_user`, `admin_token`, `employee_token`
- Rule: call `db.expire_all()` (not `await`) after HTTP mutations before direct DB queries

**`frontend/src/app/(auth)/`:**
- Purpose: Public pages that render without the sidebar layout
- Uses Next.js route group `(auth)` — not part of URL path
- Pages: `login`, `register` (disabled in prod), `accept-invite`, `forgot-password`, `reset-password`

**`frontend/src/app/(dashboard)/`:**
- Purpose: All authenticated pages sharing the sidebar layout
- `layout.tsx`: Auth guard (`useEffect` checks `localStorage` for token), `parent_viewer` route guard, sidebar nav with RBAC visibility
- Each subdirectory is a protected route

**`frontend/src/app/admin/`:**
- Purpose: SuperAdmin panel — completely separate from `(dashboard)`, uses `useSuperAdminStore`
- Two-step login (password + TOTP) at `admin/login`
- No shared layout with regular dashboard

**`frontend/src/lib/api.ts`:**
- Purpose: All API interaction — the only file that imports axios
- Structure: One named export object per domain: `authApi`, `employeesApi`, `shiftsApi`, `templatesApi`, `absencesApi`, `careAbsencesApi`, `usersApi`, `payrollApi`, `holidayProfilesApi`, `recurringShiftsApi`, `notificationsApi`, `contractsApi`, `complianceApi`, `adminSettingsApi`, `calendarDataApi`, `apiKeysApi`, `reportsApi`, `webhooksApi`, `shiftTypesApi`, `contractTypesApi`
- Token refresh interceptor handles 401 → refresh → retry automatically

**`frontend/src/store/`:**
- `auth.ts`: `useAuthStore` — persisted Zustand store; state: `{user, isAuthenticated, isLoading}`; actions: `login()`, `logout()`, `fetchMe()`
- `superadmin.ts`: Separate SuperAdmin auth state; `getSuperAdminApi()` returns SuperAdmin-auth-flavored API client

**`frontend/src/components/ui/`:**
- shadcn/ui components (button, dialog, card, toast, table, etc.)
- Do not edit these directly — regenerate via shadcn CLI if needed

---

## Key Files to Know

| File | Purpose |
|------|---------|
| `backend/app/main.py` | FastAPI app factory, all router `include_router` calls, lifespan |
| `backend/app/core/config.py` | All env var definitions and defaults |
| `backend/app/core/database.py` | Engine, session factory, `get_db`, `create_tables` |
| `backend/app/api/v1/deps.py` | All auth dependencies and role guards |
| `backend/app/models/__init__.py` | Imports all models; required for Alembic and `create_tables` |
| `backend/app/services/payroll_service.py` | Wage calculation with surcharges |
| `backend/app/utils/german_holidays.py` | BW public holiday determination |
| `backend/alembic/versions/` | All migration files |
| `backend/tests/conftest.py` | Test fixtures |
| `frontend/src/lib/api.ts` | All API call functions; token interceptors |
| `frontend/src/store/auth.ts` | Auth state + JWT storage |
| `frontend/src/app/(dashboard)/layout.tsx` | Sidebar, auth guard, `parent_viewer` route guard |
| `deploy/docker-compose.yml` | Production 6-service stack |
| `.github/workflows/deploy.yml` | Full CI/CD pipeline |

---

## Config Files

| File | Purpose |
|------|---------|
| `backend/.env` | Local env (gitignored); required vars: `DATABASE_URL`, `SECRET_KEY` |
| `backend/pytest.ini` | `asyncio_mode = auto` for async tests |
| `backend/requirements.txt` | Production dependencies |
| `backend/requirements-dev.txt` | Test/dev extras (pytest, httpx, etc.) |
| `frontend/.env.local` | Local frontend env (gitignored); `NEXT_PUBLIC_API_URL` |
| `frontend/tsconfig.json` | Must exclude `src/__tests__` and `src/test` to avoid `vi` name error in Next.js build |
| `frontend/tailwind.config.ts` | Catppuccin theme tokens (`ctp.*` palette) |
| `docker-compose.yml` | Local dev stack (Postgres + Redis + backend + frontend with hot-reload) |
| `deploy/docker-compose.yml` | Production stack with Traefik labels and memory limits |
| `deploy/.env` | Production secrets on VPS — **never committed** |

---

## Naming Conventions

**Backend files:**
- One file per domain, lowercase with underscores: `payroll_service.py`, `contract_history.py`
- API routers: `{domain}.py` in `api/v1/`; models: `{entity}.py` in `models/`

**Frontend files:**
- Pages: `page.tsx` inside feature directory
- Components: `PascalCase.tsx`
- Stores: `camelCase.ts`
- Hooks: `useCamelCase.ts`

---

## Where to Add New Code

**New API endpoint:**
1. Add function(s) to existing file in `backend/app/api/v1/{domain}.py` or create new file
2. If new file: import and `include_router` in `backend/app/main.py`
3. Add Pydantic schemas to `backend/app/schemas/{domain}.py` or inline in endpoint file
4. If new DB fields: create Alembic migration in `backend/alembic/versions/` with idempotent inspect-check
5. Add corresponding function to appropriate export object in `frontend/src/lib/api.ts`

**New dashboard page:**
1. Create `frontend/src/app/(dashboard)/{feature}/page.tsx` with `"use client"` directive
2. Add nav entry in `navItems` array in `frontend/src/app/(dashboard)/layout.tsx`
3. Use `useQuery` from TanStack Query for data fetching; call functions from `api.ts`

**New model:**
1. Create `backend/app/models/{name}.py` extending `Base`
2. Import in `backend/app/models/__init__.py`
3. Write idempotent Alembic migration
4. Create Pydantic schema in `backend/app/schemas/`

**New service:**
1. Create `backend/app/services/{name}_service.py`
2. Class takes `AsyncSession` in `__init__`
3. Import and instantiate in relevant API endpoint(s) or Celery task(s)

**New shared component:**
1. Create `frontend/src/components/shared/{ComponentName}.tsx`
2. Import directly where needed (no barrel file required)

**New Celery task:**
1. Add task function to `backend/app/tasks/reminder_tasks.py` or `payroll_tasks.py`
2. If scheduled: add to `beat_schedule` in `backend/app/tasks/celery_app.py`

---

## What Is Gitignored vs Committed

**Gitignored:**
- `backend/.env`, `backend/*.db` (SQLite dev database)
- `backend/.venv/`, `**/__pycache__/`
- `frontend/.env.local`, `frontend/node_modules/`, `frontend/.next/`
- `deploy/.env` (production secrets — only exists on VPS)
- `deploy/data/` (Postgres data volume on VPS)
- `backend/media/` (uploaded files)
- `backend/sync_shiftjuggler.py`, `backend/.env.shiftjuggler` (operational scripts)

**Committed:**
- All Alembic migration files in `backend/alembic/versions/`
- `deploy/docker-compose.yml` and Dockerfiles
- `deploy/backup.sh`, `deploy/restore.sh`, `deploy/deploy.sh`
- `.github/workflows/deploy.yml`
- `CLAUDE.md`, `TODO.md`, `CHANGELOG.md`
- `backend/seed_demo.py`

---

*Structure analysis: 2026-03-27*
