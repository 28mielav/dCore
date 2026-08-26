from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    args = parser.parse_args()
    with sqlite3.connect(args.db) as db:
        db.execute(
            """CREATE TABLE IF NOT EXISTS meta_delta_sources(
              source_id TEXT PRIMARY KEY REFERENCES meta_sources(source_id) ON DELETE CASCADE,
              base_source_id TEXT NOT NULL REFERENCES meta_sources(source_id),
              storage_mode TEXT NOT NULL CHECK(storage_mode IN ('overlay')) )"""
        )
        db.execute(
            """CREATE TABLE IF NOT EXISTS meta_version_tombstones(
              source_id TEXT NOT NULL REFERENCES meta_sources(source_id) ON DELETE CASCADE,
              category TEXT NOT NULL,name TEXT NOT NULL,object_type TEXT NOT NULL,
              PRIMARY KEY(source_id,category,name,object_type))"""
        )
        db.execute("CREATE INDEX IF NOT EXISTS idx_meta_tombstones_source ON meta_version_tombstones(source_id)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
