#!/usr/bin/env python3
"""Wait for Postgres, then `alembic upgrade head`. Used by compose `migrate` service."""

from __future__ import annotations

import os
import subprocess
import sys
import time

from sqlalchemy import create_engine, text


def wait_for_db(url: str, attempts: int = 30, delay_s: float = 1.0) -> None:
    for i in range(attempts):
        try:
            eng = create_engine(url, pool_pre_ping=True)
            with eng.connect() as conn:
                conn.execute(text("SELECT 1"))
            return
        except OSError as e:
            print(f"wait_for_db {i + 1}/{attempts}: {e}", flush=True)
        except Exception as e:
            print(f"wait_for_db {i + 1}/{attempts}: {e}", flush=True)
        time.sleep(delay_s)
    sys.exit("Postgres did not become ready in time")


def main() -> None:
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("DATABASE_URL is not set")
    wait_for_db(url)
    subprocess.check_call([sys.executable, "-m", "alembic", "upgrade", "head"])


if __name__ == "__main__":
    main()
