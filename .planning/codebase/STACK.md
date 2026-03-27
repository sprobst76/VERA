# Technology Stack

**Analysis Date:** 2026-03-27

## Languages

**Primary:**
- Python 3.12 - Backend API, services, migrations, tests
- TypeScript 5.7 - Frontend application

**Secondary:**
- SQL - PostgreSQL queries via SQLAlchemy ORM

## Runtime

**Backend:**
- CPython 3.12 (Docker image: `python:3.12-slim`)
- 2 uvicorn workers in production

**Frontend:**
- Node.js 22 (Docker image: `node:22-alpine`, build + runtime)
- Next.js standalone output mode in production

**Package Manager:**
- Backend: pip with `requirements.txt` + `requirements-dev.txt`
- Frontend: npm with `package-lock.json` (use `npm ci` for reproducible installs)

## Frameworks

**Backend Core:**
- FastAPI 0.115.0 - REST API framework, async, OpenAPI docs at `/docs` (DEBUG only)
- Uvicorn 0.32.0 (standard) - ASGI server
- Pydantic v2 2.10.0 (with `[email]` extra) - Request/response validation, schemas
- pydantic-settings 2.6.0 - Environment-based configuration (`app/core/config.py`)

**Frontend Core:**
- Next.js 14.2.0 - App Router, server + client components
- React 18.3.0 + React DOM - UI rendering

**Data Access:**
- SQLAlchemy 2.0.36 (asyncio) - ORM + query builder
- Alembic 1.14.0 - Database migrations
- asyncpg 0.30.0 - Async PostgreSQL driver (production)
- aiosqlite 0.20.0 - Async SQLite driver (development + tests)
- psycopg2-binary 2.9.10 - Sync PostgreSQL driver (Alembic migrations)

**Authentication:**
- python-jose 3.3.0 (cryptography) - JWT encode/decode, HS256 algorithm
- passlib 1.7.4 (bcrypt) - Password hashing context
- bcrypt 4.0.1 - bcrypt hash implementation
- pyotp 2.9.0 - TOTP 2FA (SuperAdmin login)
- qrcode 8.2 - QR code generation for TOTP setup

**Async & Background Tasks:**
- Celery 5.4.0 - Distributed task queue (worker + beat scheduler)
- redis 5.2.0 - Redis client (`redis.asyncio` used for async access)

**PDF Generation:**
- reportlab 4.2.5 - Payroll PDF creation (`backend/app/services/pdf_service.py`)

**Calendar / iCal:**
- icalendar 6.1.0 - iCal feed generation (`GET /calendar/{token}.ics`)

**HTTP Client (Backend):**
- httpx 0.28.0 - Async HTTP calls (webhook dispatch, external API calls)

**Notifications:**
- python-telegram-bot 21.9 - Telegram bot notifications
- pywebpush 2.0.0 - Web Push / VAPID notifications

**Frontend UI:**
- Tailwind CSS 3.4.0 - Utility-first CSS
- shadcn/ui (Radix UI primitives) - Component library
  - @radix-ui/react-avatar, dialog, dropdown-menu, label, select, separator, slot, tabs, toast
- lucide-react 0.468.0 - Icon library
- next-themes 0.4.4 - Dark/light mode switching
- class-variance-authority 0.7.0 + clsx 2.1.0 + tailwind-merge 2.5.0 - Class utilities

**Frontend State & Data:**
- Zustand 5.0.0 (with `persist` middleware) - Auth state store (`src/store/auth.ts`)
- @tanstack/react-query 5.62.0 - Server state, data fetching, caching
- axios 1.7.0 - HTTP client, JWT interceptors (`src/lib/api.ts`)
- react-hook-form 7.54.0 + @hookform/resolvers 3.9.0 - Form handling
- zod 3.24.0 - Form + schema validation

**Frontend UI Components:**
- react-big-calendar 1.15.0 - Calendar view (`src/app/(dashboard)/calendar/`)
- recharts 2.14.0 - Charts in reports page
- react-hot-toast 2.4.0 - Toast notifications
- date-fns 4.1.0 - Date formatting and manipulation
- react-qr-code 2.0.18 - QR code display (TOTP setup)

## Testing

**Backend:**
- pytest 8.3.0 - Test runner
- pytest-asyncio 0.24.0 - Async test support (`asyncio_mode = auto` in `pytest.ini`)
- anyio 4.7.0 - Async testing utilities
- httpx 0.28.0 - `AsyncClient` for API testing
- aiosqlite 0.20.0 - In-memory SQLite for tests (StaticPool, single connection)
- Config: `backend/pytest.ini`
- Test count: 268 tests in `backend/tests/`

**Frontend:**
- vitest 2.1.0 - Test runner
- @testing-library/react 16.3.2 - React component testing
- @testing-library/user-event 14.6.1 - User interaction simulation
- jsdom 28.1.0 - Browser environment simulation
- @vitejs/plugin-react 4.3.0 - React plugin for Vite/Vitest
- Config: `frontend/vitest.config.ts`
- Test count: 61 tests in `frontend/src/__tests__/`

## Infrastructure

**Containers:**
- Docker (multi-stage builds for frontend: builder + runner)
- Docker Compose (dev: `docker-compose.yml`, prod: `deploy/docker-compose.yml`)
- Compose project name: `vera`

**Production Services:**
- `vera-api` - FastAPI backend (port 8000 internal)
- `vera-web` - Next.js frontend (port 3000 internal)
- `vera-db` - PostgreSQL 16 Alpine
- `vera-redis` - Redis 7 Alpine
- `vera-celery-worker` - Celery worker (concurrency=2)
- `vera-celery-beat` - Celery beat scheduler

**Dev Services:**
- `db` - PostgreSQL 15 Alpine (port 5432)
- `redis` - Redis 7 Alpine (port 6379)
- `backend` - FastAPI with hot reload (port 31367)
- `celery` + `celery-beat` - background tasks
- `frontend` - Next.js dev server (port 31368)

**Reverse Proxy:**
- Traefik - TLS termination, rate limiting, security headers
- TLS via Cloudflare cert resolver
- Rate limits: `/api/v1/auth/login` → 10 req/min burst 3; `/api/v1/superadmin/login` → 5 req/min burst 2

**Database:**
- PostgreSQL 16 Alpine (production) / PostgreSQL 15 Alpine (dev) / SQLite in-memory (tests)
- Tuned: `shared_buffers=32MB`, `work_mem=4MB`, `max_connections=25`, `mem_limit=256m`

**Cache / Message Broker:**
- Redis 7 Alpine - Celery broker + backend, async client via `redis.asyncio`

**Container Registry:**
- GitHub Container Registry (GHCR): `ghcr.io/sprobst76/vera-backend:latest` and `ghcr.io/sprobst76/vera-frontend:latest`

## Configuration

**Backend Environment:**
- Loaded via `pydantic-settings` from `.env` file (`backend/app/core/config.py`)
- Dev default: `DATABASE_URL=sqlite+aiosqlite:///./vera.db`
- Prod: `DATABASE_URL=postgresql+asyncpg://vera:...@vera-db:5432/vera`

**Frontend Environment:**
- `NEXT_PUBLIC_API_URL` - Backend URL, baked into Next.js build at compile time
- `NEXT_PUBLIC_DEMO_SLUG` - Demo tenant slug for demo bar
- Config: `frontend/next.config.mjs`

**Tenant-Level Config:**
- Stored in `Tenant.settings` JSON column (SMTP, surcharge rates, frontend_url)
- Managed via Admin UI at Settings → System tab

## Ports (Development)

| Service | Port |
|---------|------|
| Backend API | 31367 |
| Frontend | 31368 |
| PostgreSQL | 5432 |
| Redis | 6379 |

---

*Stack analysis: 2026-03-27*
