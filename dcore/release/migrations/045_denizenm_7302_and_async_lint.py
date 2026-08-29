"""Record the 0.76 identity and exact DenizenM 7302M source artifact."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

COMMIT = "25d5164a4fbf396868345d12d0bc76a65b5548e6"
CORE_COMMIT = "5354ee62ce5158286ae1f32a915890aacc80c088"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    args = parser.parse_args()
    with sqlite3.connect(args.db) as db:
        db.execute(
            "INSERT OR REPLACE INTO version_artifacts(artifact_id,product,version,repository,tag,commit_sha,channel,source_kind,status,meta_status,runtime_status,discovered_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,COALESCE((SELECT value FROM metadata WHERE key='meta.imported_at'),'curated'))",
            ("denizenm:tag:7302m", "DenizenM", "7302M", "https://github.com/Energobro/DenizenM-Tjtoxshpilivili1", "7302M", COMMIT, "tag", "denizenm", "meta_indexed", "indexed", "unverified"),
        )
        db.executemany(
            "INSERT OR REPLACE INTO metadata(key,value) VALUES(?,?)",
            (
                ("name", "dCore 0.76"),
                ("release.version", "0.76"),
                ("denizenm.latest_tag", f"7302M@{COMMIT}"),
                ("denizenm_core.commit", CORE_COMMIT),
                ("lint.denizenm_async_boundary", "target-pinned static advisory; runtime remains separate"),
            ),
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
