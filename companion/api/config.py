"""Config for the Sanic application"""

import os


def _default_database_url() -> str:
    return os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg2://postgres:postgres@localhost:5432/postgres",
    )


class SanicConfig:
    REDIS_MAIN_URL = "redis://localhost:6379/0"
    DATABASE_URL = _default_database_url()