"""Reproduce historical source Meta from immutable commits in local git clones.

Core snapshots are explicitly date-associated, not binary dependency proof.
Run: python -m dcore.release.import_history --references ../references
"""
import argparse
import json
import sqlite3
import subprocess
from pathlib import Path

from dcore.paths import DATABASE_PATH
from dcore.release.update import MetaSource, import_meta_source

SNAPSHOTS = (
    ("1.1.4-source-7f9353e83", "7f9353e83a935b1b48808e54f493c4247dd33bbf", "732068a87c80a822f89b78646ef9e46be2e89818", "1.12.2 historical source; not a numbered release build"),
    ("1.2.6-b1782", "2354775a8cfe687aa612e8216fd564f7e50c48e2", "addc82e8f8919a58dab69c39b5d15542bd7681b3", "1.16.5; Denizen source associated with CI 1782 polling log"),
    ("1.3.0-b1804", "a063ef49c9261eb30ad3304359fb93c6fdd0cb3e", "9e3ea88b6702ff12e590bb2f668b1a7db8b05f3e", "1.17.1/1.18.2/1.19.4/1.20.4; source associated with CI 1804 polling log"),
)


def import_history(db_path: Path, references: Path):
    counts = {}
    with sqlite3.connect(db_path) as db:
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("CREATE TABLE IF NOT EXISTS meta_source_dependencies(source_id TEXT, dependency_source_id TEXT, evidence TEXT NOT NULL, PRIMARY KEY(source_id,dependency_source_id))")
        for version, commit, core, compatibility in SNAPSHOTS:
            source_id = "denizen_history_" + commit[:12]
            for product, sha, clone, repo, sid, label in (
                ("Denizen", commit, "denizen-history", "Denizen", source_id, version),
                ("Denizen-Core", core, "denizencore-history", "Denizen-Core", "core_history_" + core[:12], "source-" + core[:12]),
            ):
                artifact = sid + "_artifact"
                snapshot = subprocess.check_output(["git", "-C", str(references / clone), "archive", "--format=zip", "--prefix=source/", sha])
                db.execute("INSERT OR REPLACE INTO version_artifacts VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                           (artifact, product, label, "https://github.com/DenizenScript/" + repo, "", sha,
                            "historical", "commit", "source_indexed", "indexed", "unverified", "2026-09-10"))
                source = MetaSource(sid, product, "DenizenScript", repo, sha,
                                    compatibility + "; Core is date-associated source only, exact binary dependency unverified",
                                    "official immutable Git source", 70)
                counts[sid] = import_meta_source(db, source, sha, snapshot, artifact, allow_unclosed=True)
            db.execute("INSERT OR REPLACE INTO meta_source_dependencies VALUES(?,?,?)",
                       (source_id, "core_history_" + core[:12], "date-associated source snapshot; exact binary dependency unverified"))
    return counts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--references", required=True, type=Path)
    parser.add_argument("--db", default=DATABASE_PATH, type=Path)
    args = parser.parse_args()
    print(json.dumps(import_history(args.db, args.references), indent=2))
