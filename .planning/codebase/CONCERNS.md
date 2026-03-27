# Codebase Concerns

**Analysis Date:** 2026-03-27

Sources: `IMPROVEMENTS.md`, `TODO.md`, `CHALLENGES.md`, `ARCHITECTURE.md` (root),
direct inspection of `backend/app/`, `frontend/src/`, `deploy/`, `.github/workflows/`.

---

## Tech Debt

**ContractHistory / Employee mirror field divergence:**
- Issue: `Employee.hourly_rate`, `contract_type`, `weekly_hours`, etc. are denormalized mirror
  fields maintained by `_sync_employee_mirror()` in `backend/app/api/v1/employees.py`. If a
  `ContractHistory` row is modified directly (e.g., via admin SQL or a migration), the mirror
  and the history can diverge silently. All compliance, payroll PDF, and reports code reads
  from the mirror field (`employee.contract_type == "minijob"`), not from the history.
- Files: `backend/app/models/employee.py`, `backend/app/api/v1/employees.py` (`_sync_employee_mirror`),
  `backend/app/services/compliance_service.py` (line 55), `backend/app/api/v1/reports.py` (lines 133, 142),
  `backend/app/services/pdf_service.py` (line 264), `backend/app/services/matching_service.py` (line 142)
- Impact: Wrong payroll calculations, compliance checks skipped for employees whose mirror
  says `contract_type != "minijob"` even though their active contract history says otherwise.
- Fix approach: Compute `contract_type` and `hourly_rate` from the current `ContractHistory`
  entry at query time, or add a DB trigger / property that keeps the mirror correct.

**`assign_contract_type` without `valid_from` creates no ContractHistory entry:**
- Issue: When `assign_contract_type` is called without `valid_from`, a `ContractTypeMembership`
  is created but no `ContractHistory` entry is created. Payroll still reads the old rate.
- Files: `backend/app/api/v1/employees.py` (assign-contract-type endpoint)
- Impact: Contract history shows old rate for new assignments; payroll incorrect until admin
  manually adds a history entry.
- Fix approach: Always create a `ContractHistory` entry when assigning a type, making
  `valid_from` mandatory or defaulting to today with an explicit history entry.

**API key scopes stored but never enforced:**
- Issue: `ApiKey.scopes` field (read/write/admin) is stored and displayed in the UI, but
  `backend/app/api/deps.py` never checks the scope when an API key is used. Any valid key
  gets full admin-user context regardless of declared scope.
- Files: `backend/app/api/v1/api_keys.py`, `backend/app/api/deps.py` (lines 33–57)
- Impact: A "read-only" API key issued to an external integration (e.g., n8n) can silently
  perform write and delete operations.
- Fix approach: Add scope checking in `get_current_user` after resolving the API key, or add
  a separate `check_api_key_scope()` dependency for write endpoints.

**Legacy `send_hourly_reminders` Celery task is a no-op:**
- Issue: The task `send_hourly_reminders` in `backend/app/tasks/reminder_tasks.py` (line 46)
  is registered with Celery Beat but its body is `pass`. The Beat schedule presumably still
  calls it.
- Files: `backend/app/tasks/reminder_tasks.py` (line 44–46)
- Impact: Wasted Celery/Redis overhead every hour; confusing if someone reads the Beat config
  expecting hourly reminders to fire.
- Fix approach: Remove from Beat schedule and delete or clearly mark as deprecated.

**Demo data mixed with production data:**
- Issue: Production DB has real employees (Melanie Britsch, Anita Erhardt, Lena Reinbold-Holz)
  alongside demo-seed data. No separation exists at the DB level.
- Files: `backend/seed_demo.py`, `TODO.md` (open item)
- Impact: Risk of sending demo notifications to real users; confusing payroll and compliance
  reports mixing demo and real entries.
- Fix approach: Re-seed demo to a separate `demo` tenant; real employees remain in the
  production tenant only.

**`ContractType` badge shows blank when type deactivated:**
- Issue: Contract type list only loads `is_active=True` types. Employees with a deactivated
  type show an empty "Quelle" (source) column in their contract history view.
- Files: `backend/app/api/v1/contract_types.py`, `frontend/src/app/(dashboard)/employees/page.tsx`
- Impact: Admin has no visible trace of which contract type was used in historical entries.
- Fix approach: Pass `include_inactive=true` parameter to the contract types API when
  rendering history modals.

**`workalendar` not in requirements.txt:**
- Issue: `backend/requirements.txt` has `workalendar==17.0.0` commented out. The holiday
  detection in `backend/app/utils/german_holidays.py` uses a try/except ImportError fallback
  that computes holidays algorithmically. The production Docker image relies on the fallback.
- Files: `backend/requirements.txt` (line 22), `backend/app/utils/german_holidays.py` (line 28)
- Impact: The fallback covers BW legal holidays correctly, but doesn't include Schulferien
  from the `workalendar` library. School holiday logic uses the hardcoded list
  `BW_SCHOOL_HOLIDAYS_2025_26` which only covers 2025/26. Once the 2026/27 school year starts
  (from August 2026), recurring shift holiday exclusions will stop working.
- Fix approach: Either uncomment `workalendar` in requirements, or add 2026/27 Schulferien
  to `BW_SCHOOL_HOLIDAYS_2025_26` before summer 2026.

**Refresh tokens are never invalidated:**
- Issue: `POST /auth/change-password` updates the password hash but does not invalidate
  existing refresh tokens (7-day lifetime). An attacker who obtains a refresh token before
  a password change retains access for up to 7 days.
- Files: `backend/app/api/v1/auth.py` (line 125–131), `backend/app/core/security.py`
- Impact: Compromised account cannot be fully locked out without deactivating the user.
- Fix approach: Store a per-user `token_version` integer in the `users` table; embed it in
  refresh tokens and validate it on `/auth/refresh`. Incrementing on password change
  invalidates all existing refresh tokens.

---

## Security Concerns

**API key auth bypasses role check — grants full admin context:**
- Risk: Any valid API key resolves to the first active admin of the tenant
  (`User.role == "admin"`, `.limit(1)`), regardless of what the key was created for.
  If the tenant has multiple admins, the specific admin chosen is not deterministic.
- Files: `backend/app/api/deps.py` (lines 44–52)
- Current mitigation: Keys require SHA-256 match; expired/inactive keys are rejected.
- Recommendations: Tie API keys to a specific user or service account; enforce scope checks.

**iCal feed exposes all shift data without any rate limiting:**
- Risk: `/calendar/{token}.ics` is a public endpoint (no JWT, no auth header). The admin
  iCal feed returns every shift for the entire tenant. If the 32-byte URL-safe token is
  leaked (browser history, proxy log), all shifts become readable.
- Files: `backend/app/api/v1/calendar.py` (lines 119–203)
- Current mitigation: Token is a `secrets.token_urlsafe(32)` (256 bits of entropy); can
  be regenerated via `POST /api/v1/calendar/regenerate-token`.
- Recommendations: Add an access log for the public feed; consider a short TTL or rotation
  reminder in the UI.

**CORS allow_headers does not include `X-API-Key`:**
- Risk: The CORS config in `backend/app/main.py` (line 53) only allows
  `["Authorization", "Content-Type"]`. Browser-based integrations that send `X-API-Key`
  will be blocked by CORS preflight even though server-to-server calls work fine.
- Files: `backend/app/main.py` (lines 48–54)
- Recommendations: Add `"X-API-Key"` to `allow_headers`, or document that browser-based
  API key usage is unsupported.

**No application-level rate limiting outside Traefik:**
- Risk: Rate limiting is only applied at the Traefik layer (`/api/v1/auth/*`). If the
  backend is accessed directly (bypassing Traefik, e.g., during local dev, staging, or
  if Traefik is misconfigured), brute force on `/auth/login` is unrestricted.
- Files: `backend/app/main.py`, `TODO.md` (open item: "Rate Limiting Application-Level")
- Current mitigation: Traefik rate limiting on auth endpoints in production.
- Recommendations: Add `slowapi` or a simple in-memory counter middleware as a fallback.

**Password policy is minimal:**
- Risk: Passwords require only 8 characters (no complexity rules). This is enforced in
  `_pw_min_length` in `backend/app/api/v1/auth.py` but not checked elsewhere.
- Files: `backend/app/api/v1/auth.py` (line 19–21)
- Recommendations: Add complexity requirements (uppercase, digit, special char) or
  integrate a configurable policy. Noted as a known gap in `IMPROVEMENTS.md` (item 14).

**`DEBUG=True` default enables SQL echo and Swagger UI:**
- Risk: Default config in `backend/app/core/config.py` has `DEBUG: bool = True`. This
  causes SQLAlchemy to log all SQL to stdout (`echo=settings.DEBUG` in database.py) and
  exposes `/docs` and `/redoc`. If DEBUG is accidentally left True in production, all
  SQL queries including payroll data would appear in container logs.
- Files: `backend/app/core/config.py` (line 7), `backend/app/core/database.py` (line 13),
  `backend/app/main.py` (lines 44–46)
- Current mitigation: `.env` on VPS explicitly sets `DEBUG=false`.
- Recommendations: Flip default to `DEBUG: bool = False`; add CI check.

---

## Performance Concerns

**iCal feed does N+1 queries per shift for template loading:**
- Problem: The employee iCal feed (`/calendar/{token}.ics`) iterates over all shifts and
  for each shift with a `template_id`, executes a separate `SELECT` to load the template.
  An admin feed with 400 shifts and 80% template coverage would issue ~320 extra queries.
- Files: `backend/app/api/v1/calendar.py` (lines 140–147, 179–186)
- Cause: Template relationship is not eager-loaded via `selectinload`.
- Improvement path: Add `.options(selectinload(Shift.template), selectinload(Shift.shift_type))`
  to the shifts query, removing the inner loop queries.

**Missing database indexes on high-traffic filter columns:**
- Problem: The `shifts` table has no explicit index on `(tenant_id, date, status)` or
  `(employee_id, date)`, which are the most common filter combinations used in calendar,
  compliance, and payroll queries. The `absence` and `payroll_entries` tables similarly
  lack composite indexes.
- Files: `backend/app/models/shift.py` (no `__table_args__` with Index),
  `backend/app/models/absence.py`, `backend/app/models/payroll.py`
- Cause: Indexes were not added during initial table creation; only `contract_history`,
  `contract_type_history`, and `employee_contract_type_memberships` have explicit indexes.
- Improvement path: Add Alembic migration to create:
  `ix_shifts_tenant_date` on `(tenant_id, date)`,
  `ix_shifts_employee_date` on `(employee_id, date)`,
  `ix_payroll_employee_month` on `(employee_id, month)`.

**Bulk contract type update loads all employees in memory:**
- Problem: `PUT /contract-types/{id}/rates` in `backend/app/api/v1/contract_types.py`
  (lines 276–321) loads all active employees for a contract type, then iterates them in
  Python, issuing one `SELECT` and one `INSERT` per employee within the loop. For a
  contract type with many employees this is an N+1 pattern with no transaction boundary
  per employee — all changes are in one `await db.commit()` at the end, but failure
  mid-loop leaves the session in a partially-modified state.
- Files: `backend/app/api/v1/contract_types.py` (lines 276–321)
- Improvement path: Use a bulk INSERT via `db.execute(insert(ContractHistory).values([...]))`.

**Calendar page loads all shifts for full period without pagination:**
- Problem: `GET /api/v1/calendar` (frontend calendar page) requests shifts for the visible
  date range from `backend/app/api/v1/shifts.py`. No server-side pagination is applied.
  As the system accumulates historical shifts (400+ already), fetching a month view is
  fine, but year views or "all shifts" admin feeds load the full dataset.
- Files: `backend/app/api/v1/shifts.py`, `frontend/src/app/(dashboard)/calendar/page.tsx`
- Improvement path: Enforce `limit` on the calendar endpoint or add cursor pagination for
  export/reporting queries.

---

## Reliability Concerns

**Celery task failures are silently swallowed:**
- Problem: Both `_run_type_reminders` and `_send_reminders_for_date` in
  `backend/app/tasks/reminder_tasks.py` catch all exceptions at the top level and only
  log them. If Redis is unavailable or the DB is down, the task fails silently with no
  retry or alerting.
- Files: `backend/app/tasks/reminder_tasks.py` (lines 129–130, 152–153)
- Cause: No `max_retries`, `autoretry_for`, or `on_failure` hook is configured on the tasks.
- Improvement path: Add `@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)`
  and call `self.retry(exc=e)` in the exception handler.

**`/health` endpoint does not check DB or Redis connectivity:**
- Problem: `GET /health` in `backend/app/main.py` (line 81–83) returns `{"status": "ok"}`
  unconditionally. It does not verify that the database connection pool is healthy or that
  Redis is reachable. Docker healthcheck and Traefik routing will report the container as
  healthy even if the DB is down.
- Files: `backend/app/main.py` (lines 81–83), `deploy/docker-compose.yml` (line 59)
- Improvement path: Execute `SELECT 1` against the DB in the health handler and optionally
  ping Redis; return HTTP 503 on failure.

**Notification emails silently fail on SMTP misconfiguration:**
- Problem: The `forgot_password` endpoint wraps the email send in a bare `except Exception: pass`
  (auth.py line 210). The `users.py` invite email also uses `except Exception: pass`
  (line 159). No error is logged and the user receives a success response even if email
  delivery is completely broken.
- Files: `backend/app/api/v1/auth.py` (line 210),
  `backend/app/api/v1/users.py` (line 159)
- Impact: Admins cannot know if invite/reset emails are failing without checking SMTP logs
  externally. Users wait for emails that never arrive.
- Improvement path: At minimum log the exception at ERROR level; optionally surface SMTP
  errors to the admin as a warning in the API response.

**`alembic upgrade head` failure not detected in CI/CD:**
- Problem: The deploy script in `.github/workflows/deploy.yml` (line 166) runs
  `alembic upgrade head` via `docker compose exec`, but `set -e` is only set for the
  outer SSH script — `exec` command exit codes are propagated, but any migration failure
  only becomes visible in the GitHub Actions output after the deploy has already restarted
  the API container. The new API starts before migrations run (line 162 starts the API,
  line 166 runs migrations).
- Files: `.github/workflows/deploy.yml` (lines 162–166)
- Impact: A failing migration leaves the new API running against an un-migrated schema.
  The API starts accepting traffic before the schema is consistent.
- Improvement path: Run migrations before starting the API container, or add a startup
  script inside the container that runs `alembic upgrade head` in the `lifespan` handler
  instead of `create_tables()`, exiting with non-zero if migration fails.

**`create_tables()` / Alembic race at startup:**
- Problem: `backend/app/main.py` `lifespan` calls `create_tables()` which runs
  `Base.metadata.create_all()` on every start. Alembic migrations run after. If a new
  migration tries to create a table that `create_all()` already created, Alembic raises
  `DuplicateTable`. All existing migrations use an `inspect()` check to guard against this,
  but any future migration that omits the check will cause a production outage on deploy.
- Files: `backend/app/main.py` (line 31), `backend/app/core/database.py` (line 39–43)
- Current mitigation: All existing migrations include `if "table" not in inspector.get_table_names()`.
- Risk: A contributor not aware of this constraint writes a non-idempotent migration.
  Enforcing this in code review or CI (e.g., a lint rule checking migration files) would
  reduce the risk.

---

## Compliance Risks

**Minijob compliance check uses mirror field, not live ContractHistory:**
- Risk: `ComplianceService.check_shift()` at line 55 only runs the minijob limit check
  when `employee.contract_type == "minijob"`. If the mirror field is stale (see tech debt
  section above), employees who are actually on a minijob contract will have their limits
  silently skipped.
- Files: `backend/app/services/compliance_service.py` (line 55)
- Recommendations: Derive contract type from the active `ContractHistory` entry at check time.

**BW Schulferien hardcoded only through summer 2026:**
- Risk: `backend/app/utils/german_holidays.py` `BW_SCHOOL_HOLIDAYS_2025_26` covers through
  `2026-09-12`. Recurring shifts configured to skip school holidays will start generating
  shifts during the 2026/27 school holiday periods because `is_school_holiday()` will
  return `False` for all dates after September 2026.
- Files: `backend/app/utils/german_holidays.py` (lines 16–22),
  `backend/app/services/recurring_shift_service.py`
- Impact: Shifts generated on school holiday dates that should have been skipped;
  care recipient may unexpectedly receive care on school holidays.
- Fix approach: Add 2026/27 Schulferien before July 2026 or switch to a
  configurable per-tenant school holiday list.

**§3b EStG surcharge correctness not externally validated:**
- Risk: The entire surcharge calculation in `backend/app/services/payroll_service.py` is
  implemented in-house. The `TODO.md` explicitly notes "Zuschlagsberechnung (§3b EStG)
  von Steuerberater prüfen lassen" as an open item. No professional review has occurred.
- Files: `backend/app/services/payroll_service.py` (`SURCHARGE_RATES`, `calculate_monthly_payroll`)
- Impact: Incorrect surcharge calculations could lead to underpayment (employee liability)
  or overpayment (financial loss for PAB holder).

**No audit trail for payroll edits:**
- Risk: `PayrollEntry` status transitions (draft→approved→paid) and edits write to the
  `audit_log` table only through the `_write_audit` helper in shifts, not systematically
  in payroll endpoints. If a payroll entry is modified after approval, there is no
  immutable record of what the original calculation was.
- Files: `backend/app/api/v1/payroll.py`, `backend/app/models/audit.py`
- Recommendations: Add `_write_audit` calls to every payroll status transition and edit.

---

## Data Integrity Risks

**Shift claim endpoint has a race condition:**
- Risk: `POST /shifts/{id}/claim` in `backend/app/api/v1/shifts.py` (lines 362–382)
  reads the shift, checks `shift.employee_id is None`, then sets it. Two concurrent
  requests from different employees could both pass the check before either commits.
  PostgreSQL's default READ COMMITTED isolation means the second commit would silently
  overwrite the first.
- Files: `backend/app/api/v1/shifts.py` (lines 362–382)
- Impact: Two employees could "own" the same shift; one claim would be lost without error.
- Fix approach: Use `SELECT ... FOR UPDATE` (`.with_for_update()`) on the shift row, or
  add a unique DB constraint on `(employee_id, date, start_time)` for confirmed shifts.

**No unique constraint on `(employee_id, month)` for `PayrollEntry`:**
- Risk: `POST /payroll/calculate/{employee_id}` can create a second draft entry for the
  same employee and month if called concurrently. The endpoint checks for an existing
  entry and updates it, but without a DB-level unique constraint two concurrent calls
  can both pass the existence check before either writes.
- Files: `backend/app/api/v1/payroll.py`, `backend/app/models/payroll.py`
- Fix approach: Add a `UniqueConstraint("employee_id", "month")` to `PayrollEntry`.

**Multi-tenant isolation is application-level only:**
- Risk: All tenant isolation relies on `tenant_id` filters in application code. There is
  no database-level row security (PostgreSQL RLS). A query that accidentally omits the
  `tenant_id` filter (e.g., in a new endpoint or during a data migration) will silently
  return data across tenants.
- Files: All `backend/app/api/v1/*.py` and `backend/app/services/*.py`
- Current mitigation: Pattern is consistently applied and tested; code review is the guard.
- Recommendations: Consider adding PostgreSQL RLS as a defense-in-depth layer, especially
  before adding more tenants.

---

## Frontend Concerns

**Monolithic page files — difficult to maintain and test:**
- Problem: Several dashboard pages are extremely large single-file components:
  - `frontend/src/app/(dashboard)/employees/page.tsx` — 2,625 lines (contains EmployeeModal,
    ContractHistoryModal, EmployeeCard, EmployeeDetailView, membership logic)
  - `frontend/src/app/(dashboard)/settings/page.tsx` — 2,800 lines (4 tabs all inline)
  - `frontend/src/app/(dashboard)/payroll/page.tsx` — 1,351 lines
  - `frontend/src/app/(dashboard)/shifts/page.tsx` — 1,221 lines
- Impact: Testing individual modals requires rendering the entire page; refactoring is
  high-risk; any PR touching these files is hard to review.
- Fix approach: Extract components per `IMPROVEMENTS.md` item 4 into
  `frontend/src/components/employees/`, `frontend/src/components/payroll/`, etc.

**No Next.js error boundaries or `error.tsx` files:**
- Problem: No `error.tsx` or `global-error.tsx` files exist under `frontend/src/app/`.
  Unhandled React render errors in any dashboard page will crash the entire layout without
  a recovery UI.
- Files: `frontend/src/app/(dashboard)/` — no `error.tsx` found
- Impact: A runtime error in one page (e.g., malformed API response) shows a blank screen
  with no way to navigate away.
- Fix approach: Add `error.tsx` to `frontend/src/app/(dashboard)/` and `frontend/src/app/`.

**No `loading.tsx` files for suspense boundaries:**
- Problem: No `loading.tsx` files exist in the dashboard routes. All data fetching is
  done with TanStack Query `isLoading` checks in-component. Route transitions do not show
  a skeleton or spinner at the layout level.
- Files: `frontend/src/app/(dashboard)/` — no `loading.tsx` found

**Several `useQuery` calls have no `isError` handling:**
- Problem: Multiple queries in `reports/page.tsx` (lines 611–634) and `layout.tsx` (line 52)
  use `useQuery` with a default empty array fallback but no `isError` check. Silent API
  failures (e.g., 500 from backend) show an empty list with no user-visible feedback.
- Files: `frontend/src/app/(dashboard)/reports/page.tsx`,
  `frontend/src/app/(dashboard)/layout.tsx`

---

## Test Coverage Gaps

**`GET /employees/{id}/memberships`, `PUT/DELETE /employees/{id}/contracts` not tested:**
- What's not tested: The membership history endpoints and individual contract edit/delete endpoints.
- Files: `backend/tests/test_employees.py`, `backend/app/api/v1/employees.py`
  (assign-contract-type, PUT/DELETE /contracts)
- Risk: Contract chain repair logic on delete could silently corrupt SCD Type 2 history.
- Priority: High (payroll depends on correct contract chain)

**Celery tasks have no automated tests:**
- What's not tested: `send_type_reminders`, `send_daily_reminders`, `send_shift_reminder`
  in `backend/app/tasks/reminder_tasks.py` have no test coverage.
- Files: `backend/app/tasks/reminder_tasks.py`, `backend/app/tasks/payroll_tasks.py`
- Risk: Notification failures or silent Celery Beat misconfigurations go undetected until
  users report missing reminders.
- Priority: Medium

**Webhook dispatch not tested end-to-end:**
- What's not tested: Webhook signature verification (`hmac.new(...)` in `backend/app/api/v1/webhooks.py`
  line 185) and the HTTP dispatch to external URLs have no integration tests.
- Files: `backend/app/api/v1/webhooks.py`
- Risk: Misconfigured HMAC or network errors in dispatch are not caught until production.
- Priority: Low

**Frontend: only `recurringEventUtils` has unit tests:**
- What's not tested: No frontend unit tests exist for API client functions in
  `frontend/src/lib/api.ts`, auth store in `frontend/src/store/auth.ts`, or any
  component rendering logic outside of the recurring event utilities.
- Files: `frontend/src/__tests__/`
- Priority: Low (covered indirectly by backend integration tests)

---

## Deployment Risks

**Rolling restart: API starts before migrations run:**
- Risk: The deploy sequence in `.github/workflows/deploy.yml` (lines 162–166) starts
  `vera-api` first (`up -d --no-deps vera-api`), waits 5 seconds, then runs
  `alembic upgrade head`. During those 5 seconds (and longer if migration takes time),
  the new code runs against the old schema. If a new API version requires a new column,
  requests during this window will return 500 errors.
- Files: `.github/workflows/deploy.yml` (lines 161–166)
- Fix approach: Run migrations before starting the new API container, using a
  one-off migration container or an entrypoint script.

**No migration success check exits the deploy pipeline:**
- Risk: If `alembic upgrade head` fails (e.g., DuplicateTable from a non-idempotent
  migration), the exit code propagates through `set -e` and the SSH step fails. However,
  the API is already running on the new (possibly incompatible) image. The pipeline marks
  the deploy as failed but the service is in a broken state requiring manual intervention.
- Files: `.github/workflows/deploy.yml`

**Single-VPS, no rollback automation:**
- Risk: There is no automated rollback mechanism. A failed deploy requires manual SSH
  access to pull the previous image tag and restart services. GHCR images are all tagged
  `latest`, so the previous version is not directly pullable without a prior SHA.
- Files: `deploy/docker-compose.yml` (uses `ghcr.io/.../vera-backend:latest`)
- Fix approach: Add a `previous` or SHA-tagged image alongside `latest` in the CI pipeline,
  and document rollback steps in `DEPLOY.md`.

**Restore script tested only in documentation, not in CI:**
- Risk: `deploy/restore.sh` exists and is documented, but the `TODO.md` notes "produktiver
  Test mit echtem Backup noch ausstehend". The restore procedure has never been tested
  end-to-end against a real production backup.
- Files: `deploy/restore.sh`

---

## Dependency Risks

**`python-jose 3.3.0` — known CVE for algorithm confusion:**
- Risk: `python-jose==3.3.0` has a known vulnerability (CVE-2024-33663) where the `alg`
  header in JWT tokens can be manipulated if not explicitly constrained. VERA's
  `decode_token()` passes `algorithms=[settings.ALGORITHM]` which mitigates the standard
  algorithm confusion attack, but the library is unmaintained and `joserfc` or `PyJWT`
  are preferred alternatives.
- Files: `backend/requirements.txt` (line 10), `backend/app/core/security.py`
- Migration plan: Replace with `PyJWT>=2.8.0`; API is similar.

**`passlib 1.7.4` is in maintenance mode:**
- Risk: `passlib` is no longer actively maintained. The `bcrypt` backend works via the
  separately pinned `bcrypt==4.0.1` package, but passlib's compatibility shim with newer
  bcrypt versions has had known warnings in past versions.
- Files: `backend/requirements.txt` (lines 11–12)
- Migration plan: Use `bcrypt` directly for hashing, or switch to `argon2-cffi`.

**Frontend dependencies use `^` semver ranges (all of them):**
- Risk: All `frontend/package.json` dependencies use `^` (caret) ranges. `npm ci` uses
  `package-lock.json` in CI, providing determinism there, but local `npm install` can
  silently install different minor versions. `next: 14.2.0` is pinned exactly, which is
  correct for the framework, but all Radix UI, TanStack, and Recharts packages float on
  minor updates.
- Files: `frontend/package.json`

---

*Concerns audit: 2026-03-27*
