# Phase 1: Security Foundation + Deploy Fix — Research

**Researched:** 2026-03-27
**Domain:** Python JWT/auth libraries, FastAPI auth middleware, Docker Compose deploy ordering, CORS configuration
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**JWT Library Migration (SEC-06)**
- D-01: Replace `python-jose` with `PyJWT 2.12+` in `backend/app/core/security.py`. Remove `python-jose` from `requirements.txt`.
- D-02: Replace `passlib.context.CryptContext` with direct `bcrypt` calls (`bcrypt.hashpw` / `bcrypt.checkpw`). Verify hash format compatibility with existing hashes before removing passlib (bcrypt hashes from passlib's CryptContext are standard `$2b$` format — same as direct bcrypt, but add one explicit test).
- D-03: Token payload structure is UNCHANGED — `sub`, `tenant_id`, `role`, `exp`, `type` claims remain identical. No JTI claim added (not needed for token_version approach).

**JWT Revocation — token_version (SEC-05)**
- D-04: Add `token_version: int` column (default=0, non-null) to `User` model via Alembic migration.
- D-05: Access tokens include a `ver` claim set to the user's `token_version` at issue time.
- D-06: `get_current_user` in `deps.py` checks `payload["ver"] == user.token_version` after loading the user. Mismatch → 401.
- D-07: `POST /auth/logout-all` increments `token_version`, invalidating ALL sessions including the current one. The caller must re-authenticate.
- D-08: `change_password` endpoint automatically increments `token_version` — password change is a security event that revokes all existing sessions.
- D-09: Single-device logout (`POST /auth/logout`) is NOT implemented in this phase — token_version covers all cases; per-token JTI blocklist deferred.

**API Key Scope Enforcement (SEC-01)**
- D-10: `ApiKey.scopes` (existing field, currently ignored) is now enforced in `get_current_user`. Scopes are stored as a list/string: `"read"`, `"write"`, `"admin"`.
- D-11: Write operations (POST/PUT/PATCH/DELETE) called with a read-only key return HTTP 403.
- D-12: Implementation approach: after resolving the API key and loading the admin user, attach the scope to the request context. Add a new FastAPI dependency `WriteApiKeyOrJwt` / or check HTTP method in `get_current_user` after key resolution.
- D-13: The Shiftjuggler sync script uses a key that creates/updates shifts → assign **write** scope. Admin scope is reserved for keys that need user management or settings changes.
- D-14: Existing keys with no scopes set are treated as `"admin"` during a one-time migration, then admin must review and downgrade. (Backward-compatible, prevents breaking existing integrations.)

**Deploy Race Fix (INFRA-01)**
- D-15: Fix in `deploy.yml`: run `alembic upgrade head` BEFORE `docker compose up -d vera-api`. Zero-downtime approach: bring vera-api up with `--no-deps`, wait for DB healthcheck, run migrations, then bring up the full stack.
- D-16: The `sleep 5` in the current deploy script is replaced by a proper health check wait.

**CORS & Secrets Audit (SEC-04)**
- D-17: CORS `allow_headers` must include `"X-API-Key"`.
- D-18: Secrets audit focus: VPS `deploy/.env` — verify file permissions (600 or 640).
- D-19: Frontend bundle check: verify no `NEXT_PUBLIC_*` variable exposes secrets. `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_DEMO_SLUG` are the only public vars — already safe.

### Claude's Discretion
- Exact approach for deploy race fix (one-shot migration container vs script ordering).
- passlib hash format compatibility test — write a small test to verify existing hashes verify with direct bcrypt before removing passlib from requirements.
- Whether to use a FastAPI `Security()` dependency or inline method-check for scope enforcement — pick whichever is cleaner given existing deps.py patterns.

### Deferred Ideas (OUT OF SCOPE)
- Per-device logout (JTI blocklist in Redis) — deferred to v2.
- Single-device logout (`POST /auth/logout`) — not in this phase.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SEC-01 | API key scopes enforced — read-only key cannot execute write operations | ApiKey.scopes column already exists as JSON; needs enforcement in get_current_user after key resolution |
| SEC-04 | Secrets audit: CORS config reviewed, no secrets in frontend bundles, .env handling | CORS allow_headers missing "X-API-Key"; frontend vars confirmed safe (NEXT_PUBLIC_API_URL, NEXT_PUBLIC_DEMO_SLUG only) |
| SEC-05 | JWT revocation via token_version on User model | User model has no token_version column; needs Alembic migration + ver claim in access tokens + check in deps.py |
| SEC-06 | python-jose replaced by PyJWT 2.12+ (CVE-2024-33663) | python-jose==3.3.0 in requirements.txt; PyJWT 2.12.1 available on PyPI; bcrypt 5.0.0 available |
| INFRA-01 | Deploy order fixed — alembic runs before API accepts requests | Current deploy.yml starts vera-api then sleeps 5s then migrates; healthcheck on vera-api is already defined |
</phase_requirements>

---

## Summary

Phase 1 is a pure security and infrastructure hardening phase with no user-facing features. All five requirements are backend-only changes. The codebase is well-structured for the changes: auth flows through a single `get_current_user` function in `deps.py`, making scope enforcement and token_version checking additive changes there. The security.py module is a thin wrapper over python-jose (8 functions), making the PyJWT migration a direct API swap.

The deploy race is the most operationally risky change. The current script starts `vera-api` (which calls `create_tables()` via lifespan), then sleeps 5s, then runs `alembic upgrade head`. This is inherently racy: if the API starts accepting requests before migrations complete, callers hit a schema that is partially migrated. The fix requires running `alembic upgrade head` in a one-shot `docker compose run` or `exec` command before `docker compose up` for vera-api.

The passlib-to-bcrypt migration is sensitive because production has existing hashed passwords. The passlib `CryptContext(schemes=["bcrypt"])` produces standard `$2b$` bcrypt hashes — identical format to `bcrypt.hashpw()`. However, a one-line compatibility test should be written and run before deploying the removal.

**Primary recommendation:** Implement in order: (1) PyJWT + bcrypt migration (isolated change, easiest to test), (2) token_version column + logout-all endpoint, (3) API key scope enforcement, (4) CORS header fix, (5) deploy race fix. Each change is independent and can be separately verified.

---

## Standard Stack

### Core Libraries

| Library | Current | Target | Purpose | Why |
|---------|---------|--------|---------|-----|
| `PyJWT` | not installed | `2.12.1` | JWT encode/decode | Replaces python-jose; CVE-free, actively maintained |
| `bcrypt` | `4.0.1` (in requirements.txt) | `4.0.1` (keep or upgrade to 5.0.0) | Password hashing | Already a transitive dep of passlib; making it direct |
| `python-jose[cryptography]` | `3.3.0` | **REMOVE** | JWT (CVE-2024-33663) | Abandoned upstream, CVE in HS256 |
| `passlib[bcrypt]` | `1.7.4` | **REMOVE** | Password hashing wrapper | Unnecessary wrapper once bcrypt is direct |

**bcrypt version note:** Current `requirements.txt` pins `bcrypt==4.0.1`. Latest is `5.0.0`. Either version works. Upgrading to `5.0.0` is a safe improvement but is optional — keep `4.0.1` to minimize change surface in this phase.

### PyJWT API Differences from python-jose

python-jose and PyJWT have near-identical signatures with two important differences:

**Encoding:**
```python
# python-jose (current):
from jose import jwt
jwt.encode(payload, key, algorithm="HS256")  # returns str

# PyJWT:
import jwt
jwt.encode(payload, key, algorithm="HS256")  # returns str (PyJWT 2.x)
```

**Decoding:**
```python
# python-jose (current):
jwt.decode(token, key, algorithms=["HS256"])
# raises jose.JWTError on failure

# PyJWT:
jwt.decode(token, key, algorithms=["HS256"])
# raises jwt.PyJWTError (or subclasses: jwt.ExpiredSignatureError, jwt.InvalidTokenError)
# options={"verify_exp": True} is the default — no change needed
```

The exception class changes: `JWTError` (jose) → `jwt.PyJWTError` (PyJWT). The `decode_token()` function in `security.py` catches `JWTError` and re-raises as `ValueError`. Only the import and exception type change — the re-raise as `ValueError` pattern stays the same.

### bcrypt Direct API

```python
# passlib (current):
from passlib.context import CryptContext
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
pwd_context.hash(password)           # returns "$2b$12$..." string
pwd_context.verify(plain, hashed)    # returns bool

# Direct bcrypt:
import bcrypt
bcrypt.hashpw(password.encode(), bcrypt.gensalt())   # returns bytes
bcrypt.checkpw(password.encode(), hashed.encode())   # returns bool
```

**Critical:** `bcrypt.hashpw()` returns `bytes`, not `str`. Must decode to string for DB storage: `bcrypt.hashpw(...).decode("utf-8")`. `bcrypt.checkpw()` accepts both `bytes` and `str` for the stored hash in bcrypt>=4.0.0.

**Hash format compatibility (HIGH confidence):** passlib's `CryptContext(schemes=["bcrypt"])` generates standard `$2b$12$...` format bcrypt hashes. These are byte-for-byte identical to what `bcrypt.hashpw()` produces. `bcrypt.checkpw()` will verify them correctly. A small explicit test is still required per D-02.

**Installation:**
```bash
pip install "PyJWT>=2.12"
# bcrypt is already in requirements.txt — no install needed
```

---

## Architecture Patterns

### Current State: What Changes and What Doesn't

**`backend/app/core/security.py` — full rewrite of imports only:**
- 2 import lines change (`jose` → `jwt`, `passlib` removed)
- 4 functions change body: `hash_password`, `verify_password`, `create_access_token`, `decode_token`
- `create_access_token` gains a `token_version: int` parameter and adds `"ver": token_version` to payload
- Exception handler in `decode_token`: `JWTError` → `jwt.PyJWTError`

**`backend/app/api/deps.py` — additive changes only:**
- API key path: after loading `user`, check `ak.scopes` against `request.method`
- JWT path: after loading `user`, check `payload.get("ver") == user.token_version`
- Scope check requires access to the HTTP request object — `Request` must be added as a dependency parameter

**`backend/app/models/user.py` — one column added:**
- `token_version: Mapped[int]` with `default=0`, `nullable=False`, `server_default="0"`

**`backend/app/api/v1/auth.py` — two additions:**
- `change_password`: add `user.token_version += 1` before `db.commit()`
- New `POST /auth/logout-all` endpoint: load current user, `user.token_version += 1`, `db.commit()`, return 204

**`backend/app/main.py` — one line change:**
- `allow_headers=["Authorization", "Content-Type", "X-API-Key"]`

**`.github/workflows/deploy.yml` — script reordering:**
- Replace `sleep 5` + `exec alembic` pattern with a health-check-gated migration run

### Scope Enforcement Pattern

The cleanest approach given existing `deps.py` patterns is an inline method check inside `get_current_user` for the API key path. This avoids a new dependency type while keeping all auth logic in one place.

The `get_current_user` function needs the HTTP `Request` object to check the method. FastAPI injects it directly:

```python
# Add to get_current_user signature:
from fastapi import Request

async def get_current_user(
    request: Request,
    credentials: ...,
    db: ...,
    x_api_key: ...,
) -> User:
```

After loading the API key's user, before returning:

```python
if x_api_key:
    # ... existing key lookup ...
    if user:
        # Scope enforcement
        scopes = ak.scopes or ["admin"]  # D-14: no scopes = admin (backward compat)
        if isinstance(scopes, str):
            scopes = [scopes]
        method = request.method.upper()
        is_write = method in ("POST", "PUT", "PATCH", "DELETE")
        if is_write and "write" not in scopes and "admin" not in scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="API-Key hat keine Schreibberechtigung",
            )
        ak.last_used_at = datetime.now(timezone.utc)
        await db.commit()
        return user
```

**Scope hierarchy (D-10, D-11):** `admin` > `write` > `read`. An admin-scoped key can do everything. A write-scoped key can POST/PUT/PATCH/DELETE. A read-scoped key can only GET/HEAD/OPTIONS.

### token_version Check Pattern

In the JWT path of `get_current_user`, after loading the user from DB:

```python
# After: user = result.scalar_one_or_none()
if user is None or not user.is_active:
    raise credentials_exception

# token_version check (D-06):
token_ver = payload.get("ver")
if token_ver is None or token_ver != user.token_version:
    raise credentials_exception
```

**Important:** The `ver` claim check uses `is None` guard because existing tokens issued before this deploy will not have the `ver` claim. Strategy: treat missing `ver` as version 0. Since all users start at `token_version=0`, tokens without `ver` still work until someone calls logout-all or change-password. This avoids a forced re-login for all users on deploy.

Alternatively: treat missing `ver` as a mismatch (force re-login on deploy). Decision for planner — recommend the graceful approach (treat missing as 0) since this is a production system with active sessions.

### Deploy Race Fix

**Current (broken):**
```bash
docker compose up -d --no-deps vera-api   # API starts, create_tables() runs
sleep 5                                    # arbitrary wait
docker compose exec -T vera-api alembic upgrade head  # races with API startup
```

**Problem:** `vera-api` lifespan calls `create_tables()` (SQLAlchemy `metadata.create_all()`) at startup. Then `alembic upgrade head` runs. If a migration creates a table that `create_all()` already created, the migration fails with `DuplicateTable` (PostgreSQL) or silently succeeds (idempotent check).

But the deeper problem is: if `alembic upgrade head` is needed for a column that an endpoint uses, and a request arrives in the 5-second window before migration completes, the endpoint gets a DB error.

**Fix approach — one-shot run before API starts:**
```bash
# 1. Pull images (already there)
docker compose -p vera -f deploy/docker-compose.yml pull

# 2. Ensure DB is up and healthy (it's already running from previous deploy)
docker compose -p vera -f deploy/docker-compose.yml up -d --no-deps vera-db
# Wait for DB health
until docker compose -p vera -f deploy/docker-compose.yml exec -T vera-db pg_isready -U vera -d vera; do
  sleep 2
done

# 3. Run migrations in a one-shot container (no API server started yet)
docker compose -p vera -f deploy/docker-compose.yml run --rm --no-deps vera-api alembic upgrade head

# 4. Now start the API (create_tables runs, but all tables already exist)
docker compose -p vera -f deploy/docker-compose.yml up -d --no-deps vera-api

# 5. Start remaining services
docker compose -p vera -f deploy/docker-compose.yml up -d --no-deps vera-web vera-celery-worker vera-celery-beat
```

**Why `run --rm` not `exec`:** `exec` requires a running container. `run --rm` starts a fresh container, runs the command, exits, and removes the container. This is the correct pattern for one-shot migration jobs.

**Why `--no-deps`:** Avoids starting the entire stack just to run migrations. The DB is already running.

**Health check wait:** `docker compose up -d --no-deps vera-db` followed by a `pg_isready` loop is more reliable than `sleep 5`. The vera-db healthcheck is already configured (`interval: 10s, retries: 5`). An alternative is `docker compose wait vera-db` (available in Compose v2.27+) or polling `pg_isready`.

### Alembic Migration: token_version Column

The new migration for `token_version` must follow the idempotent inspect pattern (required by CLAUDE.md):

```python
revision = 'j4k5l6m7n8o9'  # new, follows i3j4k5l6m7n8
down_revision = 'i3j4k5l6m7n8'

def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    cols = [c["name"] for c in inspector.get_columns("users")]
    if "token_version" not in cols:
        op.add_column("users", sa.Column(
            "token_version", sa.Integer(),
            nullable=False,
            server_default="0",
        ))
```

**`server_default="0"` is required** (not `default=0`) for existing rows in PostgreSQL. Without `server_default`, adding a `NOT NULL` column to a non-empty table fails.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JWT encode/decode | Custom HMAC signing | `PyJWT` | Algorithm edge cases, expiry handling, clock skew |
| Password hashing | Custom bcrypt wrapper | Direct `bcrypt.hashpw/checkpw` | One-way KDF correctness, salt generation |
| Docker health wait | `sleep N` | `pg_isready` loop or `docker compose wait` | Sleep is inherently racy; health check is deterministic |
| Scope hierarchy | Custom RBAC engine | Inline `if "write" not in scopes` check | Overkill for 3 scope levels |

---

## Common Pitfalls

### Pitfall 1: bcrypt hashpw() Returns bytes, Not str
**What goes wrong:** `bcrypt.hashpw(pw.encode(), bcrypt.gensalt())` returns `b"$2b$12$..."`. Storing bytes directly in the `hashed_password` column (String(255)) causes SQLAlchemy type errors or stores the string `"b'$2b$...'"`.
**Why it happens:** Unlike passlib which returns a string, the raw bcrypt library returns bytes.
**How to avoid:** Always call `.decode("utf-8")` on the return value of `hashpw()`.
**Warning signs:** `hashed_password` values in DB starting with `b'`.

### Pitfall 2: checkpw() Argument Encoding
**What goes wrong:** `bcrypt.checkpw(plain_password, hashed_password)` — if `hashed_password` is a Python `str` (from DB), bcrypt<4.0 raises `TypeError`. bcrypt>=4.0 accepts str.
**Why it happens:** bcrypt C library expects bytes.
**How to avoid:** Always encode: `bcrypt.checkpw(plain.encode(), stored_hash.encode())`. This is safe regardless of bcrypt version.

### Pitfall 3: PyJWT decode() Requires algorithms List
**What goes wrong:** `jwt.decode(token, key, algorithms="HS256")` — passing a string instead of list raises `DecodeError`.
**Why it happens:** PyJWT enforces `algorithms` as a list to prevent algorithm confusion attacks.
**How to avoid:** Always pass `algorithms=["HS256"]` (list).

### Pitfall 4: token_version Missing ver Claim Breaks All Sessions on Deploy
**What goes wrong:** If `get_current_user` requires `ver` claim and existing tokens don't have it, ALL logged-in users get 401 immediately after deploy.
**Why it happens:** Tokens issued before the `ver` claim was added will never have it.
**How to avoid:** In the `ver` check, treat `payload.get("ver", 0)` as version 0. Since all users start at `token_version=0`, this is equivalent to "no revocation has happened" — valid for pre-existing tokens.

### Pitfall 5: server_default Missing on NOT NULL Column Add
**What goes wrong:** `alembic upgrade head` fails with `null value in column "token_version" violates not-null constraint` on production DB (which has existing rows).
**Why it happens:** PostgreSQL cannot add a NOT NULL column without a default to a non-empty table.
**How to avoid:** Always specify `server_default="0"` (string, not int) in `op.add_column()` for PostgreSQL. The `server_default` is a SQL expression string.

### Pitfall 6: docker compose run Creates a New Container Name
**What goes wrong:** `docker compose run --rm vera-api alembic upgrade head` creates a new container (e.g., `vera-vera-api-run-1`) that may conflict with network/volume settings if not using `--no-deps` correctly.
**Why it happens:** `run` creates a one-off container, not the named service container.
**How to avoid:** Use `--rm` to auto-remove. Ensure `--no-deps` prevents starting dependent services. The migration container shares the same image and env_file as the service.

### Pitfall 7: conftest.py admin_token Fixture Won't Include ver Claim
**What goes wrong:** After adding `ver` to `create_access_token()`, the `admin_token` fixture in `conftest.py` calls `create_access_token(admin_user.id, admin_user.tenant_id, "admin")` without `token_version`. If `token_version` is required, all existing tests that use `admin_token` break.
**Why it happens:** The fixture doesn't pass `token_version`.
**How to avoid:** Update `create_access_token()` signature with `token_version: int = 0` as default. Update the fixture to pass `admin_user.token_version` (which will be `0`). Both must be updated atomically.

---

## Code Examples

### PyJWT Encode/Decode (Verified Pattern)

```python
# Source: PyJWT 2.x official docs / PyPI package
import jwt  # PyJWT, not python-jose

# Encode
token = jwt.encode(
    {"sub": "user-id", "exp": expire, "type": "access"},
    settings.SECRET_KEY,
    algorithm="HS256",  # string (not list) for encode
)
# Returns str in PyJWT 2.x

# Decode
try:
    payload = jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=["HS256"],  # list required
    )
except jwt.PyJWTError as e:
    raise ValueError(f"Invalid token: {e}")
```

### Direct bcrypt Hash/Verify

```python
import bcrypt

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )
```

### Passlib Compatibility Test (Required per D-02)

```python
def test_passlib_hash_compatible_with_direct_bcrypt():
    """Verify existing passlib hashes verify with direct bcrypt."""
    from passlib.context import CryptContext
    import bcrypt
    ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
    passlib_hash = ctx.hash("testpassword")
    # Must start with $2b$ (standard bcrypt)
    assert passlib_hash.startswith("$2b$")
    # Direct bcrypt must verify it
    assert bcrypt.checkpw("testpassword".encode(), passlib_hash.encode())
```

This test can be run once before removing passlib from requirements.txt, then the test itself is removed.

### Scope Enforcement in get_current_user (API Key Path)

```python
from fastapi import Request

async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> User:
    if x_api_key:
        # ... key hash lookup, expiry check (unchanged) ...
        if ak and not expired:
            scopes = ak.scopes or ["admin"]  # D-14: missing scopes = admin
            if isinstance(scopes, str):
                scopes = [scopes]
            is_write_method = request.method.upper() in ("POST", "PUT", "PATCH", "DELETE")
            if is_write_method and "write" not in scopes and "admin" not in scopes:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="API-Key hat keine Schreibberechtigung",
                )
            user_result = await db.execute(...)
            user = user_result.scalar_one_or_none()
            if user:
                ak.last_used_at = datetime.now(timezone.utc)
                await db.commit()
                return user
        raise HTTPException(status_code=403, detail="Ungültiger oder abgelaufener API-Key")
```

---

## Runtime State Inventory

> Included because this phase adds a new `token_version` column and introduces scope enforcement on API keys — both affect existing runtime state.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `api_keys` table rows — existing keys have `scopes` column set (default is `["read"]` per model). But any keys created before the default was set may have NULL. | Data migration: set `scopes = '["admin"]'` for any rows where `scopes IS NULL` or `scopes = '[]'` (D-14 backward-compat rule). One-time SQL in migration. |
| Stored data | `users` table rows — no `token_version` column yet. Will be added with `server_default=0`. | Alembic migration with inspect-check + server_default. Existing sessions continue working (treat missing `ver` claim as 0). |
| Live service config | Shiftjuggler sync key in production: currently has `scopes = ["read"]` (default). After scope enforcement deploys, this key will be blocked from `POST /shifts` with 403. | **CRITICAL: Before deploying SEC-01, update the Shiftjuggler key's scopes to `["write"]` in the production DB.** Can be done via Admin UI (Settings → API Keys) or direct SQL: `UPDATE api_keys SET scopes = '["write"]' WHERE name ILIKE '%shiftjuggler%'`. |
| OS-registered state | None — no OS-level service registration affected | None |
| Secrets/env vars | `python-jose` and `passlib` removal: these are dep-only changes. No env vars reference them. | Remove from requirements.txt only. |
| Build artifacts | Docker image will be rebuilt with new requirements.txt. Old `vera-backend:latest` will be replaced by CI/CD. | `docker image prune -f` (already in deploy script) |

**Nothing found in category:** OS-registered state, secrets/env vars — verified by code review.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| python-jose | PyJWT 2.x | python-jose abandoned ~2024, CVE-2024-33663 reported 2024 | Drop-in API swap required |
| passlib CryptContext | Direct bcrypt | bcrypt 4.0+ is stable direct API | Return type difference (bytes vs str) |
| sleep in deploy | Health-check loop | Docker Compose 2.27+ supports `docker compose wait` | Deterministic readiness |

**Deprecated/outdated:**
- `python-jose[cryptography]==3.3.0`: CVE-2024-33663 allows signature bypass under specific conditions. Library is unmaintained. No fix available upstream.
- `passlib==1.7.4`: Last release 2020. No security issues, but adds dependency weight for a thin wrapper over bcrypt.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | Backend tests | Check in CI | 3.12 (CI: setup-python) | — |
| PyJWT | SEC-06 migration | Not in venv (PyJWT 2.7.0 system, not in backend deps) | 2.12.1 on PyPI | — |
| bcrypt | SEC-06 migration | Yes — already in requirements.txt | 4.0.1 installed | — |
| pg_isready (PostgreSQL client) | INFRA-01 deploy fix | Available on VPS (PostgreSQL 16 installed) | 16.x | `nc -z vera-db 5432` as fallback |
| docker compose run | INFRA-01 deploy fix | Available on VPS (Compose v2) | v2.x | `docker exec` on started container |

**Missing dependencies with no fallback:** None.

**Note:** `PyJWT` is not currently installed in the backend `.venv` (confirmed: only `python-jose` is installed). It will be installed when `requirements.txt` is updated and `pip install` runs.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 7.x + pytest-asyncio (asyncio_mode=auto in pytest.ini) |
| Config file | `backend/pytest.ini` |
| Quick run command | `cd backend && python3 -m pytest tests/test_auth.py -q` |
| Full suite command | `cd backend && python3 -m pytest tests/ -q` |

### Existing Auth Tests (test_auth.py — 9 tests)

Current coverage:
- `test_login_valid` — login returns access + refresh tokens
- `test_login_wrong_password` — 401
- `test_login_unknown_email` — 401
- `test_login_inactive_user` — 400
- `test_refresh_valid` — refresh returns new token pair
- `test_refresh_invalid_token` — 401
- `test_me_returns_user_info` — returns email, role, id, tenant_id
- `test_me_without_token` — 401/403
- `test_change_password_success` — 204, old PW fails, new PW works
- `test_change_password_wrong_current` — 400
- `test_change_password_too_short` — 422

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | New Test Needed |
|--------|----------|-----------|-------------------|-----------------|
| SEC-06 | passlib hash verified by direct bcrypt | unit | `pytest tests/test_auth.py::test_passlib_bcrypt_compat -x` | Yes — `test_passlib_bcrypt_compat` |
| SEC-06 | login still works after PyJWT migration | integration | `pytest tests/test_auth.py::test_login_valid -x` | No — existing test covers it |
| SEC-06 | token decode rejects tampered token | unit | `pytest tests/test_security.py::test_decode_tampered_token -x` | Yes — `test_security.py` (new file) |
| SEC-05 | access token includes `ver` claim | unit | `pytest tests/test_security.py::test_access_token_has_ver_claim -x` | Yes |
| SEC-05 | `ver` mismatch → 401 on protected endpoint | integration | `pytest tests/test_auth.py::test_token_version_mismatch -x` | Yes |
| SEC-05 | `POST /auth/logout-all` → increments token_version → old token rejected | integration | `pytest tests/test_auth.py::test_logout_all_invalidates_tokens -x` | Yes |
| SEC-05 | `change_password` → increments token_version → old token rejected | integration | `pytest tests/test_auth.py::test_change_password_revokes_tokens -x` | Yes |
| SEC-01 | read-only API key → POST returns 403 | integration | `pytest tests/test_auth.py::test_api_key_read_scope_blocks_write -x` | Yes |
| SEC-01 | write-scoped API key → POST returns 201 | integration | `pytest tests/test_auth.py::test_api_key_write_scope_allows_write -x` | Yes |
| SEC-01 | admin-scoped API key → all methods allowed | integration | `pytest tests/test_auth.py::test_api_key_admin_scope_allows_all -x` | Yes |
| SEC-01 | null/empty scopes → treated as admin (D-14) | integration | `pytest tests/test_auth.py::test_api_key_null_scopes_treated_as_admin -x` | Yes |
| SEC-04 | CORS preflight includes X-API-Key in allowed headers | unit | `pytest tests/test_cors.py::test_cors_allows_x_api_key_header -x` | Yes — `test_cors.py` (new file) |
| INFRA-01 | N/A — deploy script change, not testable in unit tests | manual | Manual deploy verification on VPS | Document as manual check |

### conftest.py Updates Required

The `admin_token` and `employee_token` fixtures call `create_access_token()` without `token_version`. After adding `token_version: int = 0` as a default parameter, the fixtures work without change. However, tests for token_version revocation need a way to create tokens with a specific `ver`. The fixture should be updated to pass `admin_user.token_version` explicitly.

### Wave 0 Gaps (Tests That Must Be Created)

- [ ] `tests/test_security.py` — unit tests for security.py functions (token claims, decode, bcrypt compat)
- [ ] `tests/test_cors.py` — CORS header verification
- [ ] `tests/test_auth.py` additions: logout-all, token_version mismatch, API key scope tests
- [ ] `tests/conftest.py` update: `admin_token` fixture passes `token_version=admin_user.token_version`

### Sampling Rate

- **Per task commit:** `cd backend && python3 -m pytest tests/test_auth.py tests/test_security.py -q`
- **Per wave merge:** `cd backend && python3 -m pytest tests/ -q`
- **Phase gate:** Full suite green (268 existing + new tests) before `/gsd:verify-work`

---

## Open Questions

1. **Missing `ver` in pre-existing tokens: reject or treat as version 0?**
   - What we know: All users start at `token_version=0`; tokens issued before deploy have no `ver` claim.
   - What's unclear: Whether forcing all users to re-login on deploy is acceptable.
   - Recommendation: Treat `payload.get("ver", 0)` as version 0 — graceful. Production has active sessions.

2. **Shiftjuggler key scope update: when relative to code deploy?**
   - What we know: Scope enforcement deploys with SEC-01; existing key has `scopes=["read"]` (default).
   - What's unclear: Whether the Admin UI allows scope editing before code deploy.
   - Recommendation: The migration (Wave 0 or Wave 1) should include a SQL statement to set the Shiftjuggler key to `["write"]` scope. This must run before SEC-01 code goes live. Document as a pre-deploy checklist item.

3. **`docker compose run` vs `docker compose exec` for migration in deploy.yml**
   - What we know: `exec` requires running container; `run` starts fresh container.
   - Recommendation: Use `docker compose run --rm --no-deps vera-api alembic upgrade head`. This is standard practice for migration-before-start patterns. The `run` container shares the same env_file and image.

---

## Sources

### Primary (HIGH confidence)
- Direct code inspection of `backend/app/core/security.py`, `backend/app/api/deps.py`, `backend/app/api/v1/auth.py`, `backend/app/models/user.py`, `backend/app/models/audit.py`
- `backend/requirements.txt` — confirmed python-jose 3.3.0 and passlib 1.7.4 present
- `backend/tests/test_auth.py` — confirmed existing test coverage
- `backend/tests/conftest.py` — confirmed fixture structure
- `.github/workflows/deploy.yml` — confirmed `sleep 5` race and `exec alembic` pattern
- `deploy/docker-compose.yml` — confirmed vera-db healthcheck, vera-api healthcheck, service dependencies
- `backend/sync_shiftjuggler.py` — confirmed uses `vera_get` (GET) and `vera_post` (POST /shifts) with `X-API-Key` header → requires `write` scope (D-13 confirmed)
- `pip index versions PyJWT` — confirmed 2.12.1 is latest
- `pip index versions bcrypt` — confirmed 5.0.0 is latest (4.0.1 in requirements.txt)
- Alembic HEAD confirmed via `ScriptDirectory.get_heads()` → `i3j4k5l6m7n8`

### Secondary (MEDIUM confidence)
- PyJWT 2.x API: encode returns str (not bytes), decode requires `algorithms` as list — verified from package documentation patterns and version history

### Tertiary (LOW confidence)
- None — all critical claims verified from source code or PyPI registry

---

## Metadata

**Confidence breakdown:**
- Standard stack (PyJWT, bcrypt): HIGH — confirmed from PyPI, code inspection
- Architecture patterns: HIGH — derived from direct source code reading
- Deploy fix approach: HIGH — derived from docker-compose.yml + deploy.yml source
- Pitfalls: HIGH — derived from library API differences (bcrypt bytes vs str, PyJWT algorithms list)
- Test gaps: HIGH — derived from test_auth.py source reading

**Research date:** 2026-03-27
**Valid until:** 2026-04-27 (stable libraries; deploy patterns stable)

## Project Constraints (from CLAUDE.md)

These directives from CLAUDE.md are binding for all planning and implementation:

1. **Alembic migrations MUST use `inspect(conn)` for idempotent column/table adds** — `create_tables()` runs on every API startup before `alembic upgrade head` in lifespan. All migration `upgrade()` functions must check before adding.
2. **`down_revision` must point to real HEAD** — current HEAD is `i3j4k5l6m7n8`. New migration for `token_version` must use `down_revision = 'i3j4k5l6m7n8'`.
3. **Multi-tenancy**: all DB queries must filter by `tenant_id`. The `token_version` check in `get_current_user` loads the user by `user_id` (already tenant-scoped via User.tenant_id FK).
4. **Auth dependencies**: use `Annotated` type aliases in `deps.py`. New `Request` parameter in `get_current_user` is a standard FastAPI dependency, not a breaking change.
5. **`db.expire_all()` (synchronous, not `await`) after HTTP mutations in tests** — critical for token_version tests that modify the user and then check with a fresh request.
6. **`tsconfig.json` must exclude `src/__tests__` and `src/test`** — frontend constraint, not relevant to this phase (backend-only changes).
7. **Docker Compose project name is `vera`** — all compose commands must use `-p vera -f deploy/docker-compose.yml`.
