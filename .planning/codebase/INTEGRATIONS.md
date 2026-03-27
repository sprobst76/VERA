# External Integrations

**Analysis Date:** 2026-03-27

## Authentication Mechanisms

**JWT (Primary Auth):**
- Library: `python-jose[cryptography]` 3.3.0
- Algorithm: HS256, secret from `SECRET_KEY` env var
- Token types: `access` (60 min), `refresh` (7 days), `superadmin` (8 h), `superadmin_challenge` (5 min)
- All payloads include: `sub` (user_id), `tenant_id`, `role`, `type`
- Implementation: `backend/app/core/security.py`

**Password Hashing:**
- Library: `passlib[bcrypt]` + `bcrypt 4.0.1`
- Scheme: bcrypt via `CryptContext(schemes=["bcrypt"])`
- Implementation: `backend/app/core/security.py` (`hash_password`, `verify_password`)

**API Key Authentication:**
- Header: `X-API-Key`
- Storage: SHA-256 hash stored in `api_keys` table, plaintext returned only at creation
- Format: `vera_` prefix + 32 random hex bytes (`secrets.token_hex(32)`)
- Scopes: `read`, `write`, `admin`
- Flow: `X-API-Key` → SHA-256 → lookup in DB → resolve tenant admin user as context
- Returns 403 (not 401) on invalid key to avoid JWT fallback confusion
- Implementation: `backend/app/api/deps.py` (inside `get_current_user`), CRUD in `backend/app/api/v1/api_keys.py`
- Intended clients: n8n, Zapier, external automation (noted in code comments)

**TOTP 2FA (SuperAdmin only):**
- Library: `pyotp` 2.9.0
- Flow: Password check → short-lived `superadmin_challenge` JWT → TOTP verify → `superadmin` JWT
- QR code generated with `qrcode` 8.2 for authenticator app setup
- Implementation: `backend/app/api/v1/superadmin.py`

**Frontend Auth Storage:**
- JWT tokens stored in `localStorage` (`access_token`, `refresh_token`)
- Zustand store with `persist` middleware saves `user` + `isAuthenticated` to localStorage
- Auto-refresh: axios response interceptor catches 401, POSTs to `/auth/refresh`, retries
- Implementation: `frontend/src/store/auth.ts`, `frontend/src/lib/api.ts`

## Notification Services

**Telegram Bot:**
- Library: `python-telegram-bot` 21.9
- Config: `TELEGRAM_BOT_TOKEN` env var (empty = disabled)
- Per-employee: `employee.telegram_chat_id` field
- Events: shift assigned/changed/reminder, absence approved/rejected, pool shift open, minijob limit warnings (80%, 95%)
- Quiet hours respected per employee (default 21:00–07:00 Europe/Berlin)
- Graceful degradation: skipped if token not configured
- Implementation: `backend/app/services/notification_service.py`

**SMTP Email:**
- Config: `SMTP_HOST`, `SMTP_PORT` (587), `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`
- Primary config source: `Tenant.settings["smtp"]` (set via Admin UI)
- Fallback: env vars from `backend/app/core/config.py`
- Use case: invite emails, password reset links, shift notifications
- Links use `Tenant.settings["general"]["frontend_url"]` or `FRONTEND_URL` env var fallback
- Implementation: `backend/app/services/notification_service.py`

**Web Push (VAPID):**
- Library: `pywebpush` 2.0.0
- Config: `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_CLAIMS_SUB` env vars
- Push subscription model: `backend/app/models/push_subscription.py`
- Frontend endpoint: stored via `/notifications/push` API
- Graceful degradation: skipped if VAPID keys not configured
- Implementation: `backend/app/services/notification_service.py`

## Calendar / iCal Export

**iCal Feed:**
- Library: `icalendar` 6.1.0
- Public endpoint: `GET /calendar/{ical_token}.ics` (no JWT required, token-based)
- Token stored per user: `User.ical_token` (regeneratable via `/calendar/regenerate-token`)
- Includes: shifts, absences with timezone-aware DTSTART/DTEND (Europe/Berlin), VALARM reminders
- Implementation: `backend/app/api/v1/calendar.py`

## Webhook Outbound

**Webhook System:**
- Outbound HTTP POST using `httpx` 0.28.0
- HMAC-SHA256 signature in `X-VERA-Signature` header (optional secret per webhook)
- Events: `shift.created`, `shift.updated`, `shift.cancelled`, `absence.approved`, `payroll.created`, `compliance.violation`, `care_absence.created`
- Per-tenant webhook configurations stored in DB
- Implementation: `backend/app/api/v1/webhooks.py`

## Third-Party API: Shiftjuggler Sync

**Shiftjuggler:**
- Sync script: `backend/sync_shiftjuggler.py` (gitignored, not part of main app)
- Config file: `backend/.env.shiftjuggler` (gitignored): `SJ_BASE`, `SJ_USER`, `SJ_PASS`, `VERA_URL`, `VERA_KEY`
- Protocol: POST `/api/shift.getList`, Basic Auth, Unix timestamps, field `assignedEmployees[0]`
- Execution: `python3 sync_shiftjuggler.py --from YYYY-MM-DD --to YYYY-MM-DD [--dry-run] [--inspect]`
- Calls VERA's own REST API using `VERA_KEY` (X-API-Key)
- Status: operational, synced Jan–April 2026 (80+ shifts, 8 employees matched)

## CI/CD Pipeline

**GitHub Actions:**
- Trigger: push to `main` branch
- Workflow: `.github/workflows/deploy.yml`
- Jobs run in order: test → build → deploy

**Job: test-backend:**
- Runner: `ubuntu-latest`
- Python: 3.12 (cached via `actions/setup-python@v5`)
- Command: `python3 -m pytest tests/ -q --tb=short`
- Deps cached by `requirements.txt` + `requirements-dev.txt`

**Job: test-frontend:**
- Runner: `ubuntu-latest`
- Node.js: 24 (cached via `actions/setup-node@v5`)
- Command: `npx vitest run`
- Deps cached by `frontend/package-lock.json`

**Job: build-backend** (needs: test-backend):
- Builds Docker image from `deploy/Dockerfile.backend`
- Pushes to `ghcr.io/sprobst76/vera-backend:latest`
- GitHub Actions layer cache (`type=gha,scope=backend`)

**Job: build-frontend** (needs: test-frontend):
- Builds Docker image from `deploy/Dockerfile.frontend`
- Build args from GitHub Variables: `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_DEMO_SLUG`
- Pushes to `ghcr.io/sprobst76/vera-frontend:latest`
- GitHub Actions layer cache (`type=gha,scope=frontend`)

**Job: deploy** (needs: build-backend, build-frontend, environment: production):
- SSH via `appleboy/ssh-action@v1`
- Secrets: `SERVER_HOST`, `SERVER_USER`, `SERVER_SSH_KEY`
- Deploy path on VPS: `/srv/vera`
- Deploy sequence:
  1. `git pull --ff-only`
  2. `docker compose pull` (new images)
  3. `up -d --no-deps vera-api` (rolling restart backend first)
  4. `sleep 5`
  5. `alembic upgrade head` (exec into running container)
  6. `up -d --no-deps vera-web vera-celery-worker vera-celery-beat`
  7. `docker image prune -f`

## Data Storage

**Primary Database:**
- Production: PostgreSQL 16 via `asyncpg` (async) + `psycopg2-binary` (Alembic sync)
- Development: SQLite via `aiosqlite`
- Tests: SQLite in-memory via `aiosqlite` + `StaticPool`
- Connection env var: `DATABASE_URL`
- ORM: SQLAlchemy 2.0 async session (`backend/app/core/database.py`)

**Cache / Message Broker:**
- Redis 7 via `redis.asyncio` client
- Connection env var: `REDIS_URL`
- Client: `backend/app/core/redis.py` (lazy singleton)
- Used for: Celery broker + result backend

**File Storage:**
- PDF payroll documents: generated in-memory by reportlab, streamed as HTTP response
- No persistent file storage service (S3 etc.) detected
- Backup volume mount: `./data/backups:/app/backups` (production)

## Hosting & Infrastructure

**VPS:**
- Provider: Hetzner
- IP: `91.99.200.244`
- User: `aiplatform`
- Deploy path: `/srv/vera`

**Domain:**
- Production URL: `https://vera.lab.halbewahrheit21.de`
- TLS: Cloudflare cert resolver via Traefik

**Docker Network:**
- Internal: `vera_default` bridge network
- External: `ai-lab_ai-lab` (shared with other services on same VPS, used for Traefik routing)

## Environment Variables Summary

| Variable | Purpose | Required |
|----------|---------|----------|
| `DATABASE_URL` | DB connection string | Yes |
| `SECRET_KEY` | JWT signing key (min 32 chars) | Yes |
| `REDIS_URL` | Redis connection | Celery only |
| `REGISTRATION_SECRET` | Restricts self-registration | Prod recommended |
| `FRONTEND_URL` | Fallback for email links | Yes (prod) |
| `TELEGRAM_BOT_TOKEN` | Telegram notifications | Optional |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` / `SMTP_FROM_EMAIL` | Email | Optional |
| `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` / `VAPID_CLAIMS_SUB` | Web Push | Optional |
| `NEXT_PUBLIC_API_URL` | Backend URL baked into frontend | Yes (prod) |
| `NEXT_PUBLIC_DEMO_SLUG` | Demo tenant slug | Optional |
| `ALLOWED_ORIGINS` | CORS comma-separated origins | Yes |
| `DEBUG` | Enables Swagger UI, verbose errors | No (default true) |

**Note:** `.env` files are gitignored. Production config lives in `deploy/.env` on the VPS. SMTP and frontend URL can also be configured per-tenant via Admin UI (stored in `Tenant.settings`).

---

*Integration audit: 2026-03-27*
