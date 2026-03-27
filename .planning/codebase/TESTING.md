# Testing Patterns

**Analysis Date:** 2026-03-27

---

## Backend Test Framework

**Runner:** pytest with pytest-asyncio
**Config:** `backend/pytest.ini`
```ini
[pytest]
asyncio_mode = auto
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
```

`asyncio_mode = auto` means no `@pytest.mark.asyncio` decorator is required on async test
functions (though many files still include it explicitly for clarity).

**Key packages:** `pytest`, `pytest-asyncio`, `httpx` (async test client), `sqlalchemy[aiosqlite]`

**Run Commands:**
```bash
cd backend
python3 -m pytest tests/ -q              # Run all 268 tests
python3 -m pytest tests/ -q -x           # Stop on first failure
python3 -m pytest tests/test_shifts.py   # Single file
python3 -m pytest tests/ -k "payroll"    # Keyword filter
```

---

## Backend Test Infrastructure (`backend/tests/conftest.py`)

### SQLite In-Memory with StaticPool

Tests use SQLite (not PostgreSQL). A fresh in-memory database is created per test
function via the `engine` fixture.

```python
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # single shared connection
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()
```

`StaticPool` ensures the test HTTP client and the `db` fixture share the same underlying
SQLite connection, so data written through one is visible to the other.

### Fixture Hierarchy

```
engine (function-scoped)
├── db (AsyncSession for direct DB access)
└── client (AsyncClient with get_db overridden)
    ├── tenant (Test GmbH, BW state)
    │   ├── admin_user  → admin_token (JWT string)
    │   └── employee_user → employee_token (JWT string)
```

All fixtures are `function`-scoped (default) — each test gets a completely fresh database.

### HTTP Client Fixture

```python
@pytest_asyncio.fixture
async def client(engine) -> AsyncClient:
    session_factory = async_sessionmaker(engine, ...)

    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c

    app.dependency_overrides.clear()
```

The `get_db` dependency is overridden so every request within a test uses the
same in-memory SQLite engine. Dependency overrides are cleared after each test.

### Auth Helper

```python
def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
```

Used in every test that requires authentication:
```python
from tests.conftest import auth_headers

resp = await client.get("/api/v1/shifts", headers=auth_headers(admin_token))
```

Tokens are created with `create_access_token(user_id, tenant_id, role)` from
`app.core.security`. No actual HTTP login call needed.

---

## Backend Test Patterns

### Standard HTTP Test

```python
@pytest.mark.asyncio
async def test_create_shift_admin(client, admin_token, admin_user, tenant):
    resp = await client.post(SHIFTS_URL, json=SHIFT_PAYLOAD, headers=auth_headers(admin_token))
    assert resp.status_code == 201
    data = resp.json()
    assert data["date"] == "2025-09-01"
    assert data["status"] == "planned"
    assert "id" in data
```

Always declare `admin_user` and `tenant` fixtures even if not directly used —
they create the DB rows that authenticate the token.

### RBAC Test Pattern

Every write endpoint has a corresponding forbidden test for lower-privileged roles:
```python
async def test_create_shift_admin(client, admin_token, admin_user, tenant):
    resp = await client.post(SHIFTS_URL, json=SHIFT_PAYLOAD, headers=auth_headers(admin_token))
    assert resp.status_code == 201

async def test_create_shift_employee_forbidden(client, employee_token, employee_user, tenant):
    resp = await client.post(SHIFTS_URL, json=SHIFT_PAYLOAD, headers=auth_headers(employee_token))
    assert resp.status_code == 403
```

### Two-Step Mutation Pattern

When testing a state that requires a prior mutation (e.g., confirming a shift before
testing edit restrictions), chain HTTP calls:
```python
# Create
create = await client.post(SHIFTS_URL, json=SHIFT_PAYLOAD, headers=auth_headers(admin_token))
shift_id = create.json()["id"]

# State change via PUT (ShiftCreate has no status field — must use separate PUT)
await client.put(f"{SHIFTS_URL}/{shift_id}", json={"status": "confirmed"}, headers=auth_headers(admin_token))

# Assert behavior on mutated state
resp = await client.put(f"{SHIFTS_URL}/{shift_id}", json={"start_time": "09:00:00"}, ...)
assert resp.status_code == 200
```

### Direct DB Inspection After HTTP Mutations

When the test must read back DB state after an HTTP call, call `db.expire_all()`
first to clear SQLAlchemy's identity cache:
```python
# CRITICAL: expire_all() is synchronous — no await
db.expire_all()
result = await db.execute(select(Shift).where(Shift.id == shift_id))
shift = result.scalar_one_or_none()
assert shift.status == "confirmed"
```

Forgetting this causes stale reads due to SQLAlchemy's identity map.

### Service Unit Tests (No HTTP)

Services are tested by instantiating them directly with a `db` fixture and passing
`SimpleNamespace` stubs instead of ORM models:
```python
from types import SimpleNamespace

def make_shift(shift_date, start, end, break_minutes=0):
    h_s, m_s = map(int, start.split(":"))
    h_e, m_e = map(int, end.split(":"))
    return SimpleNamespace(
        date=shift_date,
        start_time=time(h_s, m_s),
        end_time=time(h_e, m_e),
        break_minutes=break_minutes,
        employee_id=uuid.uuid4(),
        status="confirmed",
    )

async def test_net_hours_normal_shift(db):
    svc = PayrollService(db)
    shift = make_shift(date(2025, 9, 1), "08:00", "16:00", break_minutes=30)
    assert svc._calc_net_hours(shift) == pytest.approx(7.5)
```

### Pure Unit Tests (No DB)

`test_service.py` tests pure functions in services without fixtures at all
(synchronous test functions, no `db`, no `client`):
```python
def test_build_skip_set_vacation_period():
    profile = _Profile(periods=[_Period(date(2025, 10, 27), date(2025, 10, 31))])
    skip = build_skip_set(profile, skip_public_holidays=False, years={2025})
    assert date(2025, 10, 27) in skip
```

### Local Fixtures Per Test File

Complex tests define their own `pytest_asyncio.fixture` functions within the test file
when they need additional DB entities beyond the shared conftest:
```python
# test_shifts.py
@pytest_asyncio.fixture
async def employee_with_profile(db, employee_user, tenant):
    emp = Employee(tenant_id=tenant.id, user_id=employee_user.id, ...)
    db.add(emp)
    await db.commit()
    await db.refresh(emp)
    return emp
```

### Numeric Assertions

Floating point values use `pytest.approx()`:
```python
assert svc._calc_net_hours(shift) == pytest.approx(7.5)
assert result["amounts"].get("early", 0) == pytest.approx(1.25)
```

---

## Backend Test Coverage Breakdown (268 tests)

| File | Tests | What's Covered |
|---|---|---|
| `test_contract_scenarios_extended.py` | 16 | SCD Type 2 edge cases, mid-month changes |
| `test_recurring_shifts.py` | 19 | Regeltermine CRUD, vacation skip, preview |
| `test_payroll_service.py` | 18 | Net hours, surcharge calc §3b, monthly payroll |
| `test_holiday_profiles.py` | 17 | Ferienprofile CRUD + periods + custom days |
| `test_shifts.py` | 17 | Shift CRUD, RBAC, bulk, claim/pool |
| `test_calendar.py` | 17 | Calendar endpoint, overnight split, absences |
| `test_service.py` | 16 | `recurring_shift_service` pure functions |
| `test_contract_scenarios.py` | 9 | Basic contract history flows |
| `test_shift_types.py` | 15 | ShiftType CRUD + reminder fields |
| `test_start_date_and_edit.py` | 14 | Start date enforcement, edit after confirm |
| `test_employees.py` | 12 | Employee CRUD, RBAC (PublicOut vs Out), /me |
| `test_payroll_annual.py` | 11 | Annual payroll, YTD tracking, CSV export |
| `test_care_absences.py` | 11 | CareRecipientAbsence CRUD + shift handling |
| `test_auth.py` | 11 | Login, refresh, /me, change-password |
| `test_compliance_service.py` | 9 | §4 breaks, §5 rest period, holiday warnings |
| `test_parent_viewer.py` | 9 | parent_viewer RBAC: read-only calendar/shifts |
| `test_contract_scenarios.py` | 9 | Contract assignment, SCD Type 2 basics |
| `test_webhooks.py` | 8 | Webhook CRUD + dispatch |
| `test_reports.py` | 8 | Report endpoints + CSV |
| `test_memberships.py` | 8 | Employee membership endpoints |
| `test_absences.py` | 8 | EmployeeAbsence CRUD, approval, RBAC |
| `test_users.py` | 15 | User CRUD, invite, role management |

---

## Backend Test Gaps

**Not tested / limited coverage:**
- `notification_service.py` — Telegram/Email/Push send paths (external, no mock)
- `pdf_service.py` — PDF generation (reportlab output)
- Superadmin endpoints (basic coverage only)
- API key middleware edge cases (expiry, last_used_at update)
- `admin_settings.py` SMTP test endpoint (calls external SMTP)
- Celery task scheduling (no Celery test infrastructure)
- Error paths in `recurring_shift_service.py` for edge-case overlap resolution

---

## Frontend Test Framework

**Runner:** Vitest
**Config:** `frontend/vitest.config.ts`
```typescript
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
  },
  resolve: {
    alias: { "@": resolve(__dirname, "./src") },
  },
});
```

**Run Commands:**
```bash
cd frontend
npx vitest run              # Run all 61 tests (non-interactive)
npx vitest                  # Watch mode
npx vitest run --reporter=verbose  # With test names
```

### Global Setup (`frontend/src/test/setup.ts`)

Mocks run before every test file:
- `next/navigation` → mocked `useRouter`, `usePathname`, `useSearchParams`
- `next-themes` → mocked `useTheme`
- Suppresses React `Warning:` console.error noise

---

## Frontend Test Patterns

### API Client Tests (axios mock)

Used for tests in `frontend/src/__tests__/`. Axios is mocked at module level using
`vi.hoisted()` to ensure mock functions are available before imports:

```typescript
const { mockGet, mockPost, mockDel } = vi.hoisted(() => ({
  mockGet:  vi.fn().mockResolvedValue({ data: [] }),
  mockPost: vi.fn().mockResolvedValue({ data: {} }),
  mockDel:  vi.fn().mockResolvedValue({ data: {} }),
}));

vi.mock("axios", () => ({
  default: {
    create: () => ({
      get: mockGet, post: mockPost, delete: mockDel,
      interceptors: { request: { use: vi.fn() }, response: { use: vi.fn() } },
    }),
  },
}));

import { careAbsencesApi } from "@/lib/api";

beforeEach(() => { vi.clearAllMocks(); });

it("list() calls GET /care-absences", async () => {
  await careAbsencesApi.list();
  expect(mockGet).toHaveBeenCalledWith("/care-absences");
});
```

This pattern verifies that API client methods call the correct HTTP method and endpoint.
Does not test backend behavior.

### Pure Utility Tests

Tests in `frontend/src/test/` and `__tests__/recurring-shift-utils.test.ts` test
pure TypeScript utility functions with no mocking needed:
```typescript
import { buildSkipSet } from "@/lib/recurringEventUtils";

describe("buildSkipSet", () => {
  it("enthält alle Ferientage", () => {
    const skip = buildSkipSet(VACATION_DATA, false);
    expect(skip.has("2026-04-06")).toBe(true);
    expect(skip.has("2026-04-12")).toBe(false);
  });
});
```

---

## Frontend Test Coverage Breakdown (61 tests)

| File | Tests | What's Covered |
|---|---|---|
| `recurringEventUtils.test.ts` | 15 | `buildSkipSet`, `buildRecurringEventsForShift`, `buildAllRecurringEvents` |
| `recurring-shift-utils.test.ts` | 21 | Weekday mapping, date range utils, vacation period logic |
| `api-schuljahrdienste.test.ts` | 18 | `recurringShiftsApi` + `holidayProfilesApi` HTTP methods |
| `api-care-absences.test.ts` | 7 | `careAbsencesApi`, `employeesApi.vacationBalances` HTTP methods |

---

## Frontend Test Gaps

**Not tested:**
- React components (no component rendering tests / no React Testing Library)
- Auth flow (login redirect, token refresh logic)
- TanStack Query hooks and cache invalidation
- Calendar event rendering (react-big-calendar integration)
- Form validation in modals
- Zustand store (`useAuthStore`)
- All dashboard pages (Shifts, Employees, Payroll, etc.)

The frontend test suite is focused entirely on utility functions and API client
method signatures. UI behavior, component rendering, and user interaction are untested.

---

## tsconfig Requirement

`frontend/src/__tests__` and `frontend/src/test` must be listed in `tsconfig.json`
under `exclude`. Omitting this causes the Next.js build to fail with
`"Cannot find name 'vi'"` because TypeScript tries to compile test files:

```json
{
  "exclude": ["node_modules", "src/__tests__", "src/test"]
}
```

---

*Testing analysis: 2026-03-27*
