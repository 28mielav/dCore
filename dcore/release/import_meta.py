"""Import exact historical Denizen-family Meta snapshots from a local Git clone.

Each tag is a separate source.  A selected historical target can therefore
never silently receive API rows from a newer build.
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import subprocess
from pathlib import Path

from dcore.release.update import MetaSource, classify_deltas, ensure_meta_schema, import_meta_source


def source_id_for(artifact_id: str) -> str:
    return "meta_" + re.sub(r"[^a-z0-9]+", "_", artifact_id.lower()).strip("_")


def archive(repo: Path, ref: str) -> bytes:
    return subprocess.check_output(
        ["git", "-C", str(repo), "archive", "--format=zip", ref], timeout=120
    )


def import_product(
    db_path: Path, repo: Path, product: str, source_kind: str,
    channels: set[str] | None = None,
) -> dict[str, int]:
    channels = channels or {"tag"}
    with sqlite3.connect(db_path) as db:
        db.execute("PRAGMA foreign_keys=ON")
        ensure_meta_schema(db)
        artifacts = db.execute(
            "SELECT artifact_id,version,tag,commit_sha,repository,channel FROM version_artifacts "
            "WHERE product=? AND source_kind=? ORDER BY channel,version",
            (product, source_kind),
        ).fetchall()
        imported = 0
        skipped = 0
        unchanged = 0
        for artifact_id, version, tag, commit, repository, channel in artifacts:
            if channel not in channels:
                skipped += 1
                continue
            source_id = source_id_for(artifact_id)
            current = db.execute(
                "SELECT commit_sha FROM meta_sources WHERE source_id=?", (source_id,)
            ).fetchone()
            entry_count = db.execute(
                "SELECT count(*) FROM meta_entries WHERE source_id=?", (source_id,)
            ).fetchone()[0]
            if current and current[0] == commit and entry_count:
                unchanged += 1
                continue
            source = MetaSource(
                source_id, product, "historical", repo.name, tag,
                f"Historical {product} {version} source snapshot; select this exact target.",
                "local Git tag Meta", 95,
            )
            count = import_meta_source(
                db, source, commit, archive(repo, commit), artifact_id, allow_unclosed=True,
            )
            db.execute(
                "UPDATE version_artifacts SET meta_status='indexed',status='meta_indexed' WHERE artifact_id=?",
                (artifact_id,),
            )
            imported += count
        classify_deltas(db)
        db.execute(
            "INSERT OR REPLACE INTO metadata(key,value) VALUES(?,?)",
            (f"meta.multiversion.{source_kind}", f"imported_entries={imported}; non_tag_artifacts_skipped={skipped}"),
        )
        return {"artifacts": len(artifacts) - skipped, "entries": imported, "skipped": skipped, "unchanged": unchanged}


def main() -> int:
    parser = argparse.ArgumentParser(description="Import historical target-pinned Meta snapshots")
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--product", required=True)
    parser.add_argument("--source-kind", required=True)
    parser.add_argument("--channels", default="tag", help="Comma-separated registry channels, such as tag,branch")
    args = parser.parse_args()
    if not (args.repo / ".git").exists():
        parser.error("--repo must be a local Git clone with the requested tags")
    channels = {item.strip() for item in args.channels.split(",") if item.strip()}
    print(import_product(args.db, args.repo, args.product, args.source_kind, channels))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
