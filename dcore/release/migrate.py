from __future__ import annotations

import argparse
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from dcore.release.compact import optimize_search


def mark(db: sqlite3.Connection, name: str) -> None:
    db.execute(
        "INSERT OR IGNORE INTO schema_migrations(name,applied_at) VALUES(?,?)",
        (name, datetime.now(timezone.utc).isoformat()),
    )


def bootstrap_existing(db: sqlite3.Connection) -> None:
    """Record curated migrations already present in pre-registry databases."""
    has_generalized = db.execute("SELECT 1 FROM cards WHERE id='MATH-016'").fetchone()
    revision = db.execute(
        "SELECT value FROM metadata WHERE key='architecture_revision'"
    ).fetchone()
    if has_generalized:
        mark(db, "001_generalized_visual_primitives.py")
    if revision and revision[0] == "runtime-proof-and-unicode-routing-2":
        mark(db, "002_repair_russian_routing_and_proof_gates.py")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument(
        "--directory", type=Path, default=Path(__file__).with_name("migrations")
    )
    args = parser.parse_args()

    with sqlite3.connect(args.db) as db:
        existed = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
        ).fetchone()
        db.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations("
            "name TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        if not existed:
            bootstrap_existing(db)

    for migration in sorted(args.directory.glob("[0-9][0-9][0-9]_*.py")):
        with sqlite3.connect(args.db) as db:
            applied = db.execute(
                "SELECT 1 FROM schema_migrations WHERE name=?", (migration.name,)
            ).fetchone()
        if applied:
            continue
        subprocess.run(
            [sys.executable, str(migration), "--db", str(args.db)], check=True
        )
        with sqlite3.connect(args.db) as db:
            mark(db, migration.name)

    with sqlite3.connect(args.db) as db:
        optimize_search(db)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
