from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def migrate(db: sqlite3.Connection) -> None:
    # 022 stored tag-only ids.  Keep one canonical identity per ref channel
    # before the registry is refreshed with tags and branches.
    db.execute("DELETE FROM version_edges")
    db.execute(
        "DELETE FROM version_artifacts "
        "WHERE artifact_id NOT LIKE '%:tag:%' AND artifact_id NOT LIKE '%:branch:%'"
    )
    db.execute(
        "INSERT OR REPLACE INTO metadata(key,value) VALUES(?,?)",
        ("version.registry.channels", "tag,branch"),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    args = parser.parse_args()
    with sqlite3.connect(args.db) as db:
        migrate(db)
