from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    args = parser.parse_args()
    with sqlite3.connect(args.db) as db:
        db.execute("DELETE FROM meta_fields WHERE entry_id NOT IN (SELECT entry_id FROM meta_entries)")
        db.execute("DELETE FROM meta_deltas WHERE entry_id NOT IN (SELECT entry_id FROM meta_entries)")
        db.execute("DELETE FROM meta_deltas WHERE baseline_entry_id IS NOT NULL AND baseline_entry_id NOT IN (SELECT entry_id FROM meta_entries)")
        db.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES(?,?)", ("meta.foreign_keys", "historical imports enable SQLite foreign_keys; 026 removed prior orphan fields"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
