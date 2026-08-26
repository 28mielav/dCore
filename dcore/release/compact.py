"""Convert full historical Meta snapshots into base + override + tombstone overlays."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from dcore.knowledge.meta_resolution import entry_key


BASE_SOURCES = {"DenizenM": "denizenm_public_master", "Denizen": "denizen_official_dev"}


def search_tables(db: sqlite3.Connection) -> list[str]:
    return [
        row[0]
        for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND sql LIKE '%USING fts5%' ORDER BY name"
        )
    ]


def optimize_search(db: sqlite3.Connection) -> None:
    """Merge FTS5 segments so deleted rows stop occupying pages.

    A plain ``DELETE FROM <fts table>`` only writes tombstones. Rebuilding an
    index without this step grew meta_search to 80 MB over a 4 MB corpus.
    """
    for table in search_tables(db):
        db.execute(f"INSERT INTO {table}({table}) VALUES('optimize')")


def rebuild_search(db: sqlite3.Connection) -> None:
    db.execute("DELETE FROM meta_search")
    db.execute(
        """INSERT INTO meta_search
           SELECT e.entry_id,e.category,e.name,e.object_type,e.syntax,e.summary,e.description,
                  COALESCE(group_concat(f.field_name || ': ' || f.value, char(10)), '')
           FROM meta_entries e LEFT JOIN meta_fields f ON f.entry_id=e.entry_id
           GROUP BY e.entry_id,e.category,e.name,e.object_type,e.syntax,e.summary,e.description"""
    )
    optimize_search(db)


def compact(db_path: Path, force: bool = False) -> dict[str, int]:
    """Reduce freshly imported full snapshots to overlays against their base source.

    Only valid directly after ``import_multiversion_meta``. A source already
    stored as an overlay has had its identical entries deleted, so recomputing
    ``base - history`` would invent a tombstone for every shared API and make
    historical resolution deny APIs that the build really has. Such sources are
    skipped unless ``force`` is set.
    """
    with sqlite3.connect(db_path) as db:
        db.execute("PRAGMA foreign_keys=ON")
        db.row_factory = sqlite3.Row
        sources = db.execute(
            "SELECT source_id,product FROM meta_sources WHERE artifact_id IS NOT NULL ORDER BY source_id"
        ).fetchall()
        already_overlay = {
            row[0]
            for row in db.execute(
                "SELECT source_id FROM meta_delta_sources WHERE storage_mode='overlay'"
            )
        }
        removed = tombstones = compacted = skipped = 0
        for source in sources:
            base_id = BASE_SOURCES.get(source["product"])
            if not base_id:
                continue
            if source["source_id"] in already_overlay and not force:
                skipped += 1
                continue
            base_rows = db.execute(
                "SELECT entry_id,category,name,object_type,raw_fields_json FROM meta_entries WHERE source_id=?", (base_id,)
            ).fetchall()
            history_rows = db.execute(
                "SELECT entry_id,category,name,object_type,raw_fields_json FROM meta_entries WHERE source_id=?", (source["source_id"],)
            ).fetchall()
            base = {entry_key(row): row for row in base_rows}
            history = {entry_key(row): row for row in history_rows}
            db.execute("DELETE FROM meta_version_tombstones WHERE source_id=?", (source["source_id"],))
            for key in base.keys() - history.keys():
                db.execute(
                    "INSERT INTO meta_version_tombstones(source_id,category,name,object_type) VALUES(?,?,?,?)",
                    (source["source_id"], *key),
                )
                tombstones += 1
            duplicate_ids = [
                row["entry_id"] for key, row in history.items()
                if key in base and row["raw_fields_json"] == base[key]["raw_fields_json"]
            ]
            if duplicate_ids:
                marks = ",".join("?" for _ in duplicate_ids)
                db.execute(f"DELETE FROM meta_entries WHERE entry_id IN ({marks})", duplicate_ids)
                removed += len(duplicate_ids)
            db.execute(
                "INSERT OR REPLACE INTO meta_delta_sources(source_id,base_source_id,storage_mode) VALUES(?,?,?)",
                (source["source_id"], base_id, "overlay"),
            )
            compacted += 1
        if compacted:
            rebuild_search(db)
        else:
            optimize_search(db)
        db.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES(?,?)", ("meta.multiversion.storage", "base+override+tombstone overlays"))
        db.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES(?,?)", ("meta.multiversion.compaction", f"sources={compacted}; removed_identical_entries={removed}; tombstones={tombstones}"))
    return {
        "sources": compacted,
        "skipped_already_overlay": skipped,
        "removed_identical_entries": removed,
        "tombstones": tombstones,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compact historical Meta snapshots into overlays")
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--vacuum", action="store_true")
    parser.add_argument(
        "--optimize-only",
        action="store_true",
        help="Merge FTS segments and leave overlay storage untouched",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Recompute overlays for sources already stored as overlays",
    )
    args = parser.parse_args()
    if args.optimize_only:
        with sqlite3.connect(args.db) as db:
            optimize_search(db)
    else:
        print(compact(args.db, force=args.force))
    if args.vacuum:
        sqlite3.connect(args.db).execute("VACUUM")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
