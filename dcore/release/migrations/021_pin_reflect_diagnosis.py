from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path("knowledge/dcore.sqlite"))
    args = parser.parse_args()
    with sqlite3.connect(args.db) as db:
        db.execute(
            "INSERT OR REPLACE INTO route_pins(intent,card_id,position) VALUES('diagnose','ADD-002',4)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
