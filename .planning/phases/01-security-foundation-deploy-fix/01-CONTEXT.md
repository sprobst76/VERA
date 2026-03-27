# Phase 1: Security Foundation + Deploy Fix — Context

**Gathered:** 2026-03-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Fix live security issues in the production auth and deploy pipeline. No new user-facing features. Deliverables: (1) python-jose CVE eliminated, (2) deploy race fixed, (3) API key scopes enforced, (4) JWT revocation via token_version, (5) CORS allows X-API-Key for browser callers, (6) VPS .env hygiene verified.

</domain>

<decisions>
## Implementation Decisions

### JWT Library Migration (SEC-06)
- **D-01:** Replace `python-jose` with `PyJWT 2.12+` in `backend/app/core/security.py`. Remove `python-jose` from `requirements.txt`.
- **D-02:** Replace `passlib.context.CryptContext` with direct `bcrypt` calls (`bcrypt.hashpw` / `bcrypt.checkpw`). Verify hash format compatibility with existing hashes before removing passlib (bcrypt hashes from passlib's CryptContext are standard `$2b$` format — same as direct bcrypt, but add one explicit test).
- **D-03:** Token payload structure is UNCHANGED — `sub`, `tenant_id`, `role`, `exp`, `type` claims remain identical. No JTI claim added (not needed for token_version approach).

### JWT Revocation — token_version (SEC-05)
- **D-04:** Add `token_version: int` column (default=0, non-null) to `User` model via Alembic migration.
- **D-05:** Access tokens include a `ver` claim set to the user's `token_version` at issue time.
- **D-06:** `get_current_user` in `deps.py` checks `payload["ver"] == user.token_version` after loading the user. Mismatch → 401.
- **D-07:** `POST /auth/logout-all` increments `token_version`, invalidating ALL sessions including the current one. The caller must re-authenticate.
- **D-08:** `change_password` endpoint automatically increments `token_version` — password change is a security event that revokes all existing sessions.
- **D-09:** Single-device logout (`POST /auth/logout`) is NOT implemented in this phase — token_version covers all cases; per-token JTI blocklist deferred.

### API Key Scope Enforcement (SEC-01)
- **D-10:** `ApiKey.scopes` (existing field, currently ignored) is now enforced in `get_current_user`. Scopes are stored as a list/string: `"read"`, `"write"`, `"admin"`.
- **D-11:** Write operations (POST/PUT/PATCH/DELETE) called with a read-only key return HTTP 403.
- **D-12:** Implementation approach: after resolving the API key and loading the admin user, attach the scope to the request context. Add a new FastAPI dependency `WriteApiKeyOrJwt` / or check HTTP method in `get_current_user` after key resolution.
- **D-13:** The Shiftjuggler sync script uses a key that creates/updates shifts → assign **write** scope (not admin). Admin scope is reserved for keys that need user management or settings changes. Claude to verify the exact scopes needed by reading the sync script before implementing.
- **D-14:** Existing keys with no scopes set are treated as `"admin"` during a one-time migration, then admin must review and downgrade. (Backward-compatible, prevents breaking existing integrations.)

### Deploy Race Fix (INFRA-01)
- **D-15:** Fix in `deploy.yml`: run `alembic upgrade head` BEFORE `docker compose up -d vera-api`. Concretely: bring vera-api up with `--no-deps`, wait for DB healthcheck, run migrations, then bring up the full stack. Or simpler: run alembic in a one-shot exec against the already-running DB container before starting vera-api. Claude decides exact approach — constraint is zero-downtime and no window where API accepts requests with un-migrated schema.
- **D-16:** The `sleep 5` in the current deploy script is replaced by a proper health check wait.

### CORS & Secrets Audit (SEC-04)
- **D-17:** CORS `allow_headers` must include `"X-API-Key"` — browser-based callers use this header directly (confirmed in-use).
- **D-18:** Secrets audit focus: VPS `deploy/.env` — verify file permissions (600 or 640), not world-readable, not committed to git. Check `.gitignore` covers it.
- **D-19:** Frontend bundle check: verify no `NEXT_PUBLIC_*` variable exposes secrets (API keys, SECRET_KEY, DB URL). `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_DEMO_SLUG` are the only public vars — these are safe (URLs, not secrets).

### Claude's Discretion
- Exact approach for deploy race fix (one-shot migration container vs script ordering) — implement the most reliable zero-downtime solution.
- passlib hash format compatibility test — write a small test to verify existing hashes verify with direct bcrypt before removing passlib from requirements.
- Whether to use a FastAPI `Security()` dependency or inline method-check for scope enforcement — pick whichever is cleaner given existing deps.py patterns.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Auth / Security
- `backend/app/core/security.py` — JWT encode/decode, bcrypt wrappers (to be replaced)
- `backend/app/api/deps.py` — `get_current_user`, `ApiKey` lookup, all role dependencies
- `backend/app/api/v1/auth.py` — Login, refresh, change-password endpoints (logout-all to be added here)
- `backend/app/models/user.py` — User model (token_version column to be added)
- `backend/app/models/audit.py` — ApiKey model with scopes field

### Deploy Pipeline
- `.github/workflows/deploy.yml` — Current deploy script with the `sleep 5` race
- `deploy/docker-compose.yml` — Service definitions, healthchecks, depends_on conditions

### Requirements
- `.planning/REQUIREMENTS.md` — SEC-01, SEC-04, SEC-05, SEC-06, INFRA-01 success criteria

### Dependencies
- `backend/requirements.txt` — python-jose and passlib to be replaced with PyJWT + bcrypt

No external specs — requirements fully captured in decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `deps.py` → `get_current_user`: single function to modify for both scope enforcement (D-10–D-12) and token_version check (D-06). All auth changes funnel through here.
- `auth.py` → `change_password` endpoint: add `token_version` increment here (D-08).
- `User` model: add `token_version` column; existing Alembic migration pattern (idempotent inspect-check) applies.

### Established Patterns
- Alembic migrations must use `inspect(conn)` for idempotent column adds — `create_tables()` runs before `alembic upgrade head` in lifespan.
- FastAPI dependencies: all auth is via `Annotated` type aliases in `deps.py`. Add any new scope dependency here.
- Error responses: HTTP 403 for auth/permission failures (existing pattern in `get_current_active_admin`).

### Integration Points
- `backend/app/main.py`: CORS middleware `allow_headers` needs `"X-API-Key"` added.
- `deploy.yml` SSH script: migration ordering change is self-contained in the `script:` block.
- `requirements.txt`: `python-jose` → `PyJWT>=2.12`, `passlib[bcrypt]` → `bcrypt`.

</code_context>

<specifics>
## Specifics

- Shiftjuggler sync key should have **write** scope (creates/updates shifts). Claude to verify by reading `backend/sync_shiftjuggler.py` before assigning scope.
- "Logout-all" must revoke the session that called it — user must re-authenticate immediately.
- Changing password automatically revokes all sessions — this is a hard requirement, not optional.
- CORS priority: X-API-Key header in allow_headers is confirmed needed (browser callers exist).
- VPS .env audit is the primary secrets concern — frontend bundle vars are already safe.

</specifics>
