from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


CARD = (
    "VER-020", "verification", "acceptance_suite", "Release the Skill only after representative executable scenarios pass",
    "A green unit suite can miss a broken bundle, a target-routing leak or a new lint rule that only works in isolation.",
    "Keep a small deterministic acceptance suite of representative Denizen inputs: structure, selected Meta, addon boundary, target/JAR evidence, old-build isolation, cancellation scope and dog navigation ownership. Run it both from the repository and the built Skill where the tool layout is self-contained. Record static PASS separately from gameplay runtime proof.",
    "Reject checking only one happy-path file, manually eyeballing a Skill ZIP, or calling ten static fixtures a pathfinding/runtime proof.",
    "Run the scenario suite, full unit/retrieval/integrity gates, build both products, then run the profile lint. For gameplay, separately test the installed server on terrain, water, obstruction, quit/death and reload.",
    "dCore 0.55 executable acceptance contract", "high", 100, 1, "dCore release quality policy",
)


def rebuild_search(db: sqlite3.Connection) -> None:
    db.execute("DELETE FROM card_search")
    db.execute(
        """INSERT INTO card_search(id,title,summary,guidance,terms,domain,kind)
           SELECT c.id,c.title,c.summary,c.guidance,
             COALESCE((SELECT group_concat(term,' ') FROM card_terms t WHERE t.card_id=c.id),''),c.domain,c.kind
           FROM cards c"""
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    args = parser.parse_args()
    with sqlite3.connect(args.db) as db:
        db.execute(
            "INSERT OR REPLACE INTO cards(id,domain,kind,title,summary,guidance,reject_when,verification,version_scope,confidence,priority,token_weight,source_basis) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            CARD,
        )
        db.execute("INSERT OR REPLACE INTO card_activation_rules(card_id,min_hits) VALUES('VER-020',1)")
        for term in ("skill acceptance", "scenario suite", "test dcore skill", "прогон skill", "десять сценариев", "проверить dcore"):
            db.execute("INSERT OR IGNORE INTO card_terms(card_id,term) VALUES('VER-020',?)", (term,))
            db.execute("INSERT OR IGNORE INTO card_activation_terms(card_id,term) VALUES('VER-020',?)", (term,))
            db.execute("INSERT OR REPLACE INTO card_alias_terms(card_id,term,weight) VALUES('VER-020',?,20)", (term,))
        db.execute(
            "INSERT OR REPLACE INTO card_version_scopes(card_id,scope_type,product,addon,rationale) VALUES(?,?,?,?,?)",
            ("VER-020", "invariant", "", "", "Acceptance coverage is version-neutral; individual fixtures still pin their targets."),
        )
        db.executemany(
            "INSERT OR REPLACE INTO metadata(key,value) VALUES(?,?)",
            (("release.version", "0.55"), ("name", "dCore 0.55"), ("release.status", "temporarily_frozen_after_0.55")),
        )
        rebuild_search(db)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
