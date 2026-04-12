#!/usr/bin/env python3
"""Wait for Postgres, then `alembic upgrade head`. Used by compose `migrate` service."""

from __future__ import annotations

import os
import subprocess
import sys
import time

from sqlalchemy import create_engine, inspect, text


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


def _schema_matches_initial_bootstrap(url: str) -> bool:
    """Detect pre-existing schema without alembic_version (legacy/manual bootstrap)."""
    expected = {"sets", "symbols", "cards", "card_images", "settings"}
    eng = create_engine(url, pool_pre_ping=True)
    with eng.connect() as conn:
        insp = inspect(conn)
        if insp.has_table("alembic_version"):
            return False
        existing = set(insp.get_table_names())
    return expected.issubset(existing)


def _run_alembic(*args: str) -> None:
    cmd = [sys.executable, "-m", "alembic", *args]
    print(f"running: {' '.join(cmd)}", flush=True)
    subprocess.check_call(cmd)


def _upgrade_with_retries(max_attempts: int = 3, delay_s: float = 2.0) -> None:
    last_error: Exception | None = None
    for i in range(max_attempts):
        try:
            _run_alembic("upgrade", "head")
            return
        except Exception as e:
            last_error = e
            print(f"alembic upgrade attempt {i + 1}/{max_attempts} failed: {e}", flush=True)
            if i + 1 < max_attempts:
                time.sleep(delay_s)
    if last_error is not None:
        raise last_error


def main() -> None:
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("DATABASE_URL is not set")
    wait_for_db(url)
    if _schema_matches_initial_bootstrap(url):
        print("detected existing schema without alembic_version; stamping head", flush=True)
        _run_alembic("stamp", "head")
    _upgrade_with_retries()


if __name__ == "__main__":
    main()
