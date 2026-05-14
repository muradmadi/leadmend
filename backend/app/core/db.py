"""Configures the SQLAlchemy async engine and session factory.

Provides the global database engine and a dependency function to inject
sessions into FastAPI endpoints. It also contains the initialization logic
for creating tables and necessary PostgreSQL extensions on application startup.
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    """The declarative base class for all SQLAlchemy ORM models."""

    pass


engine = create_async_engine(settings.DATABASE_URL, echo=True)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db():
    """Provide a transactional asynchronous database session.

    Yields:
        AsyncSession: An active SQLAlchemy async session.

    Example:
        >>> @app.get("/items")
        ... async def get_items(db: AsyncSession = Depends(get_db)):
        ...     pass

    """
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    """Initialize the database schema and required extensions.

    Ensures that pg_trgm is available for fuzzy matching, and creates all
    ORM tables if they do not already exist. It connects via a synchronous
    runner to apply the metadata.

    Example:
        >>> await init_db()

    """
    async with engine.begin() as conn:
        from sqlalchemy import text

        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        await conn.run_sync(Base.metadata.create_all)
