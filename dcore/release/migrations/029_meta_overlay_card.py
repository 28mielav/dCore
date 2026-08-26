from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


CARD = (
    "VER-019", "verification", "multi_version", "Historical Meta uses overlays, not duplicated snapshots",
    "Storing every unchanged API row for every build makes the knowledge base too large without adding evidence.",
    "Keep a current source as the base and retain only historical overrides, additions and tombstones. Resolve the target through the overlay before searching or linting; compaction must preserve version-difference tests.",
    "Reject compacting by dropping old rows without tombstones, resolving an old target from current API alone, or claiming a smaller database proves a route.",
    "Compare an old/new API difference before and after compaction, check foreign keys, inspect overlay/tombstone counts and confirm the historical query stays target-pinned.",
    "dCore 0.53 Meta overlay storage", "high", 100, 1, "dCore 0.53 compaction contract",
)


def rebuild_search(db: sqlite3.Connection) -> None:
    db.execute("DELETE FROM card_search")
    db.execute("""INSERT INTO card_search(id,title,summary,guidance,terms,domain,kind)
                  SELECT c.id,c.title,c.summary,c.guidance,
                    COALESCE((SELECT group_concat(term,' ') FROM card_terms t WHERE t.card_id=c.id),''),c.domain,c.kind FROM cards c""")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    args = parser.parse_args()
    with sqlite3.connect(args.db) as db:
        db.execute("INSERT OR REPLACE INTO cards(id,domain,kind,title,summary,guidance,reject_when,verification,version_scope,confidence,priority,token_weight,source_basis) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", CARD)
        db.execute("INSERT OR REPLACE INTO card_activation_rules(card_id,min_hits) VALUES('VER-019',1)")
        for term in ("meta overlay", "historical meta size", "delta compression", "сжатие meta", "дельта meta"):
            db.execute("INSERT OR IGNORE INTO card_terms(card_id,term) VALUES('VER-019',?)", (term,))
            db.execute("INSERT OR IGNORE INTO card_activation_terms(card_id,term) VALUES('VER-019',?)", (term,))
            db.execute("INSERT OR REPLACE INTO card_alias_terms(card_id,term,weight) VALUES('VER-019',?,20)", (term,))
        db.execute("INSERT OR REPLACE INTO card_version_scopes(card_id,scope_type,product,addon,rationale) VALUES(?,?,?,?,?)", ("VER-019", "target_matrix", "", "", "Overlay resolution depends on the selected historical target."))
        db.executemany("INSERT OR REPLACE INTO metadata(key,value) VALUES(?,?)", (("release.version", "0.53"), ("name", "dCore 0.53")))
        rebuild_search(db)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
