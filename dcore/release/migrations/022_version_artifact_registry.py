from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path("dcore/knowledge/data/dcore.sqlite"))
    args = parser.parse_args()
    with sqlite3.connect(args.db) as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS version_artifacts(
              artifact_id TEXT PRIMARY KEY, product TEXT NOT NULL, version TEXT NOT NULL,
              repository TEXT NOT NULL, tag TEXT NOT NULL, commit_sha TEXT NOT NULL,
              channel TEXT NOT NULL, source_kind TEXT NOT NULL, status TEXT NOT NULL,
              meta_status TEXT NOT NULL, runtime_status TEXT NOT NULL, discovered_at TEXT NOT NULL,
              UNIQUE(product,version,commit_sha)
            );
            CREATE INDEX IF NOT EXISTS idx_version_artifacts_product ON version_artifacts(product,version);
            CREATE TABLE IF NOT EXISTS version_edges(
              from_artifact_id TEXT NOT NULL REFERENCES version_artifacts(artifact_id) ON DELETE CASCADE,
              to_artifact_id TEXT NOT NULL REFERENCES version_artifacts(artifact_id) ON DELETE CASCADE,
              relation TEXT NOT NULL,
              PRIMARY KEY(from_artifact_id,to_artifact_id,relation)
            );
            INSERT OR REPLACE INTO metadata VALUES('version.registry','version_artifacts + version_edges');
            INSERT OR REPLACE INTO metadata VALUES('version.registry.status','catalogued source identities; Meta/runtime proof separate');
            """
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
