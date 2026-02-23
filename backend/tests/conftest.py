"""
Shared pytest fixtures for VERA backend tests.

Uses SQLite in-memory with StaticPool so all sessions share one connection,
meaning data written in one session is visible to others (important for HTTP client tests).
"""
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool

import app.models  # noqa – registers all SQLAlchemy models with Base.metadata
from app.core.database import Base, get_db
from app.core.security import hash_password, create_access_token
from app.main import app
from app.models.tenant import Tenant
from app.models.user import User

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


# ── Shared engine (function-scoped: fresh DB per test) ───────────────────────

@pytest_asyncio.fixture
async def engine():
    """Creates a fresh in-memory SQLite engine per test with a shared connection pool."""
    eng = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,          # single shared connection → all sessions see same data
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield eng

    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture
async def db(engine) -> AsyncSession:
    """Async DB session for direct data inspection inside tests."""
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session


# ── HTTP client fixture ───────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def client(engine) -> AsyncClient:
    """
    FastAPI test client with get_db overridden to use the test engine.
    Each request gets its own session (proper handling) but shares the same
    underlying connection via StaticPool.
    """
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

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


# ── Tenant + User fixtures ────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def tenant(db) -> Tenant:
    t = Tenant(
        id=uuid.uuid4(),
        name="Test GmbH",
        slug=f"test-{uuid.uuid4().hex[:8]}",
        state="BW",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return t


@pytest_asyncio.fixture
async def admin_user(db, tenant) -> User:
    u = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email="admin@test.de",
        hashed_password=hash_password("testpass123"),
        role="admin",
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


@pytest_asyncio.fixture
async def employee_user(db, tenant) -> User:
    u = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email="employee@test.de",
        hashed_password=hash_password("testpass123"),
        role="employee",
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


@pytest_asyncio.fixture
def admin_token(admin_user) -> str:
    return create_access_token(admin_user.id, admin_user.tenant_id, "admin")


@pytest_asyncio.fixture
def employee_token(employee_user) -> str:
    return create_access_token(employee_user.id, employee_user.tenant_id, "employee")


# ── Helper ────────────────────────────────────────────────────────────────────

def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
