"""PostgreSQL async engine and session factory."""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from config import SanicConfig

engine = create_async_engine(
    SanicConfig.ASYNC_DATABASE_URL,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)
