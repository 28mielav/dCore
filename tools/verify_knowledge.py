from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from retrieval import run_tests


def table_exists(db: sqlite3.Connection, name: str) -> bool:
    return db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--artifact", action="append", type=Path, default=[])
    args = parser.parse_args()

    failures: list[str] = []
    with sqlite3.connect(args.db) as db:
        integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_keys = len(db.execute("PRAGMA foreign_key_check").fetchall())
        if integrity != "ok":
            failures.append(f"integrity_check={integrity}")
        if foreign_keys:
            failures.append(f"foreign_key_errors={foreign_keys}")

        required = {
            "cards": 100,
            "meta_entries": 4500,
            "ide_diagnostics": 40,
            "retrieval_tests": 1,
        }
        counts: dict[str, int] = {}
        for table, minimum in required.items():
            if not table_exists(db, table):
                failures.append(f"missing_table={table}")
                counts[table] = 0
                continue
            counts[table] = db.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
            if counts[table] < minimum:
                failures.append(f"{table}={counts[table]}<{minimum}")

        sources = []
        if table_exists(db, "meta_sources"):
            columns = {row[1] for row in db.execute("PRAGMA table_info(meta_sources)")}
            wanted = [name for name in ("product", "commit_sha", "source_id") if name in columns]
            if wanted:
                sources = [dict(zip(wanted, row)) for row in db.execute(
                    f"SELECT {','.join(wanted)} FROM meta_sources ORDER BY product"
                )]

        retrieval_failures = run_tests(db) if table_exists(db, "retrieval_tests") else []
        if retrieval_failures:
            failures.append(f"retrieval_failures={len(retrieval_failures)}")

    digest = hashlib.sha256(args.db.read_bytes()).hexdigest()
    artifacts = {
        args.db.name: {"sha256": digest, "size": args.db.stat().st_size}
    }
    for path in args.artifact:
        if not path.is_file():
            failures.append(f"missing_artifact={path.name}")
            continue
        artifacts[path.name] = {
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "size": path.stat().st_size,
        }
    bundle_material = "\n".join(
        f"{name}:{data['sha256']}:{data['size']}"
        for name, data in sorted(artifacts.items())
    ).encode("utf-8")
    manifest = {
        "name": "dCore",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "verified" if not failures else "failed",
        "sha256": digest,
        "size": args.db.stat().st_size,
        "bundle_sha256": hashlib.sha256(bundle_material).hexdigest(),
        "artifacts": artifacts,
        "counts": counts,
        "sources": sources,
        "validation": {
            "integrity_check": integrity,
            "foreign_key_errors": foreign_keys,
            "retrieval_failures": retrieval_failures,
            "failures": failures,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
