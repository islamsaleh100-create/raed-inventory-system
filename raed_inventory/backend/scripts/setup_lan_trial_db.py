#!/usr/bin/env python3
"""
Prepare fresh LAN trial database (raed_lan_trial) — official seeds only, no simulation.

Usage (from backend/):
  python scripts/setup_lan_trial_db.py [--skip-create-db] [--skip-item-import]

Requires LAN trial database and credential settings from the process environment.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND.parent.parent
os.chdir(BACKEND)
sys.path.insert(0, str(BACKEND))

EXPECTED_HEAD = "c1d2e3f4a5b6"
REQUIRED_ENVIRONMENT_VARIABLES = (
    "LAN_TRIAL_DATABASE_URL",
    "LAN_TRIAL_ADMIN_PASSWORD",
    "LAN_TRIAL_USER_PASSWORD",
)


def require_environment() -> dict[str, str]:
    missing = [name for name in REQUIRED_ENVIRONMENT_VARIABLES if not os.environ.get(name)]
    if missing:
        raise SystemExit(f"Missing required environment variable: {missing[0]}")
    return {name: os.environ[name] for name in REQUIRED_ENVIRONMENT_VARIABLES}


def redact_output(text: str, env: dict[str, str]) -> str:
    redacted = text
    for name in ("DATABASE_URL", "ADMIN_PASSWORD", "PHASE2_DEMO_PASSWORD"):
        value = env.get(name)
        if value:
            redacted = redacted.replace(value, "<REDACTED>")
    return redacted


def run(cmd: list[str], *, env: dict | None = None) -> subprocess.CompletedProcess:
    print(f"\n>> {' '.join(cmd)}")
    merged = {**os.environ, **(env or {})}
    proc = subprocess.run(cmd, cwd=str(BACKEND), env=merged, text=True, capture_output=True)
    if proc.stdout:
        print(redact_output(proc.stdout.rstrip(), merged))
    if proc.returncode != 0:
        print(redact_output(proc.stderr.rstrip(), merged), file=sys.stderr)
        raise SystemExit(proc.returncode)
    return proc


def create_database(database_url: str) -> None:
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
    from urllib.parse import urlparse

    parsed = urlparse(database_url.replace("+psycopg2", ""))
    database_name = parsed.path.lstrip("/")
    if parsed.scheme != "postgresql" or not all(
        (parsed.hostname, parsed.username, parsed.password, database_name)
    ):
        raise SystemExit("Invalid required environment variable: LAN_TRIAL_DATABASE_URL")
    # psycopg2 needs plain postgresql://
    conn = psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port or 5432,
        user=parsed.username,
        password=parsed.password,
        dbname="postgres",
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (database_name,))
    if cur.fetchone():
        print(f"Database {database_name} already exists")
    else:
        cur.execute(f'CREATE DATABASE "{database_name}"')
        print(f"Created database {database_name}")
    cur.close()
    conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Setup LAN trial database")
    parser.add_argument("--skip-create-db", action="store_true")
    parser.add_argument("--skip-item-import", action="store_true")
    args = parser.parse_args()

    required = require_environment()
    database_url = required["LAN_TRIAL_DATABASE_URL"]
    admin_password = required["LAN_TRIAL_ADMIN_PASSWORD"]
    user_password = required["LAN_TRIAL_USER_PASSWORD"]
    env = {
        "DATABASE_URL": database_url,
        "ADMIN_PASSWORD": admin_password,
        "RATE_LIMIT_ENABLED": "false",
    }

    if not args.skip_create_db:
        create_database(database_url)

    run(["alembic", "upgrade", "head"], env=env)
    current = run(["alembic", "current"], env=env)
    if EXPECTED_HEAD not in (current.stdout or ""):
        print(f"WARNING: expected alembic head {EXPECTED_HEAD}", file=sys.stderr)

    run([sys.executable, "seed_supply_chain_demo.py"], env=env)
    run([sys.executable, "seed_official_branches.py"], env=env)
    run([sys.executable, "backfill_official_kitchens.py"], env=env)
    run([sys.executable, "seed_area_managers.py"], env=env)

    run(
        [sys.executable, "seed_phase2_official_users.py"],
        env={**env, "PHASE2_DEMO_PASSWORD": user_password},
    )
    run([sys.executable, "seed_internal_auditor.py"], env=env)

    if not args.skip_item_import:
        workbook = REPO_ROOT / "classified_supply_items.xlsx"
        if workbook.exists():
            run([sys.executable, "import_classified_supply_items.py"], env=env)
        else:
            print(f"SKIP item import — workbook not found: {workbook}")

    print("\nLAN trial DB setup complete.")
    print("DATABASE_URL configured through LAN_TRIAL_DATABASE_URL.")


if __name__ == "__main__":
    main()
