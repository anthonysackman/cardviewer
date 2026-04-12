"""Config for the Sanic application"""

import os


class SanicConfig:
    # Sync URL — used by Alembic migrations only
    DATABASE_URL: str = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg2://postgres:postgres@postgres:5432/postgres",
    )

    # Async URL — used by the API at runtime
    ASYNC_DATABASE_URL: str = os.environ.get(
        "ASYNC_DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@postgres:5432/postgres",
    )

    REDIS_MAIN_URL: str = os.environ.get(
        "REDIS_URL",
        "redis://redis:6379/0",
    )