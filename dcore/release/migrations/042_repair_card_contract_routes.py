from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


REPAIRS = {
    "ADD-011": "bugfix addon matrix itemsadder version",
    "VER-018": "diagnose card scope version-aware card target",
    "VER-019": "diagnose delta compression meta overlay",
    "VER-020": "diagnose scenario suite skill acceptance",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    args = parser.parse_args()
    with sqlite3.connect(args.db) as db:
        for card_id, query in REPAIRS.items():
            db.execute(
                "UPDATE retrieval_tests SET query=? WHERE id=?",
                (query, f"CARD041_{card_id}"),
            )
        db.execute(
            "INSERT OR REPLACE INTO metadata(key,value) VALUES(?,?)",
            ("release.status", "pool3_card_contract_routes_repaired"),
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
