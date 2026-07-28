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
            "cards": 149,
            "meta_entries": 4500,
            "ide_diagnostics": 40,
            "retrieval_tests": 128,
            "visual_sources": 5,
            "contrast_examples": 28,
            "route_patterns": 10,
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

        if table_exists(db, "retrieval_tests"):
            auto_tests = db.execute(
                "SELECT count(*) FROM retrieval_tests WHERE id LIKE 'AUTO%'"
            ).fetchone()[0]
            if auto_tests < 27:
                failures.append(f"auto_intent_tests={auto_tests}<27")
        if table_exists(db, "cards"):
            required_cards = {
                "CORE-019", "CORE-020", "CORE-021", "VER-009", "VER-010",
                "DEN-025", "DEN-026", "VER-008", "VIS-033", "VIS-034",
                "VIS-035", "VIS-036", "VIS-037", "VIS-038", "VIS-039",
                "VIS-040", "PERF-011",
                "CORE-022", "DEN-027", "DEN-028", "VER-011", "VER-012", "VIS-041",
                "CORE-023", "CORE-024", "TEACH-004", "TEACH-005", "VER-013", "DEN-029",
            }
            present_cards = {
                row[0] for row in db.execute(
                    f"SELECT id FROM cards WHERE id IN ({','.join('?' for _ in required_cards)})",
                    tuple(sorted(required_cards)),
                )
            }
            missing_cards = sorted(required_cards - present_cards)
            if missing_cards:
                failures.append(f"missing_policy_cards={','.join(missing_cards)}")
        if table_exists(db, "card_search"):
            empty_search_fields = db.execute(
                "SELECT count(*) FROM card_search WHERE terms='' OR domain='' OR kind=''"
            ).fetchone()[0]
            if empty_search_fields:
                failures.append(f"card_search_empty_fields={empty_search_fields}")
        if table_exists(db, "card_links"):
            link_columns = {row[1] for row in db.execute("PRAGMA table_info(card_links)")}
            if "mandatory" not in link_columns:
                failures.append("card_links_missing_mandatory")
            elif db.execute("SELECT count(*) FROM card_links WHERE mandatory=1").fetchone()[0] < 20:
                failures.append("mandatory_card_links<20")

        visual_sources = []
        if table_exists(db, "visual_sources"):
            wanted_sources = {
                "jnngl_vanilla_shaders", "midorikuma_variables_viewer",
                "cloudwolf_shader_selector_v2", "halbfettkaese_common_shaders",
                "psdps_mc_charcoal",
            }
            visual_sources = [
                {
                    "source_id": row[0], "repository": row[1],
                    "indexed_commit_sha": row[2], "latest_seen_sha": row[3],
                    "license": row[4], "license_status": row[5],
                    "ingest_policy": row[6], "review_status": row[7],
                }
                for row in db.execute(
                    """SELECT source_id,repository,indexed_commit_sha,latest_seen_sha,
                              license,license_status,ingest_policy,review_status
                       FROM visual_sources ORDER BY source_id"""
                )
            ]
            present = {item["source_id"] for item in visual_sources}
            if wanted_sources - present:
                failures.append(f"missing_visual_sources={','.join(sorted(wanted_sources - present))}")
            unsafe = [
                item["source_id"] for item in visual_sources
                if item["license_status"] == "missing"
                and item["ingest_policy"] != "reference_only_no_code_redistribution"
            ]
            if unsafe:
                failures.append(f"unsafe_unlicensed_ingest={','.join(unsafe)}")

        metadata_name = db.execute(
            "SELECT value FROM metadata WHERE key='name'"
        ).fetchone() if table_exists(db, "metadata") else None
        if not metadata_name or metadata_name[0] != "dCore 0.31":
            failures.append("metadata_name!=dCore 0.31")

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
        if path.name == "DCORE_INSTRUCTIONS.txt" and len(path.read_bytes()) > 8000:
            failures.append(f"instructions_too_large={len(path.read_bytes())}>8000")
        if path.name == "lint_contract.example.json":
            try:
                contract = json.loads(path.read_text(encoding="utf-8"))
                required_design = {
                    "expected_scale", "entry_points", "state_owners", "hot_path_budget",
                    "concurrency", "persistence_reload", "failure_cleanup", "change_axes",
                    "code_shape_budget", "route_decision",
                }
                design = contract.get("design") if isinstance(contract, dict) else None
                missing_design = sorted(
                    required_design - set(design) if isinstance(design, dict) else required_design
                )
                if missing_design:
                    failures.append(f"contract_design_missing={','.join(missing_design)}")
            except (OSError, UnicodeError, json.JSONDecodeError) as error:
                failures.append(f"contract_invalid={error}")
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
        "version": "0.31",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "verified" if not failures else "failed",
        "sha256": digest,
        "size": args.db.stat().st_size,
        "bundle_sha256": hashlib.sha256(bundle_material).hexdigest(),
        "artifacts": artifacts,
        "counts": counts,
        "sources": sources,
        "visual_sources": visual_sources,
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
