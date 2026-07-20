from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from retrieval import run_tests


def main() -> int:
    parser = argparse.ArgumentParser(description="Run dCore retrieval routing tests.")
    parser.add_argument("--db", type=Path, default=Path("knowledge/dcore.sqlite"))
    parser.add_argument("--ids", nargs="*", help="Run only these retrieval test IDs.")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    with sqlite3.connect(args.db) as db:
        total = db.execute("SELECT count(*) FROM retrieval_tests").fetchone()[0]
        failures = run_tests(db, set(args.ids) if args.ids else None)
    print(json.dumps({"total": total, "failures": failures}, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
