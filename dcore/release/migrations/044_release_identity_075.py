"""Move the database release identity to the portable-skill 0.75 line."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

ROWS = (("name", "dCore 0.75"), ("release.version", "0.75"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    args = parser.parse_args()
    with sqlite3.connect(args.db) as db:
        db.executemany("INSERT OR REPLACE INTO metadata(key,value) VALUES(?,?)", ROWS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
