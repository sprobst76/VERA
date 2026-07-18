from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.core.config import settings

# SQLite benötigt check_same_thread=False
connect_args = {}
if "sqlite" in settings.DATABASE_URL:
    connect_args = {"check_same_thread": False}

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    connect_args=connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Separate NullPool-Engine für Celery-Tasks: jeder Task-Aufruf startet mit
# asyncio.run() eine eigene, frische Event-Loop, aber asyncpg-Connections sind
# an die Loop gebunden, in der sie erzeugt wurden. Eine aus dem normalen Pool
# wiederverwendete Connection einer anderen Loop wirft "attached to a
# different loop". NullPool öffnet pro Checkout eine neue Connection und
# schließt sie danach sofort wieder - kein Wiederverwenden über Loop-Grenzen.
task_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    connect_args=connect_args,
    poolclass=NullPool,
)

TaskSessionLocal = async_sessionmaker(
    task_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_tables():
    """Erstellt alle Tabellen (für lokale Entwicklung ohne Alembic)."""
    import app.models  # noqa – alle Models importieren
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
