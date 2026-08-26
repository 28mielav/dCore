from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


CARD = (
    "VER-023", "verification", "semantic_lint", "dCore lint uses a source-derived Denizen queue semantic core",
    "A command list is not just text: ScriptBuilder creates entries, ScriptQueue owns definitions and ordering, TagManager resolves available values, and control commands alter reachability. A lint that ignores those contracts misses errors that an editor token check cannot see.",
    "Run the source-derived DenizenCore-lite layer before Meta/API checks. It may prove only portable queue semantics: container input definitions, local definition writes, tag availability, if/else, choose/case/default, repeat, while and stop. Keep Bukkit commands, Minecraft objects, scheduling, addons and all world state as explicit platform boundaries requiring JAR or server evidence.",
    "Reject treating a text-only regex result as queue proof, treating the Python core as Bukkit runtime, or shipping its code without source commit and MIT attribution.",
    "Run semantic fixtures for declared input definitions, a read before local definition, chosen and unchosen branches, repeat restoration, bounded while and stop; then run the normal selected-target lint and real server matrix.",
    "Denizen-Core source commit 273ad9f; MIT provenance", "high", 100, 1, "source-derived portable semantic executor",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    args = parser.parse_args()
    with sqlite3.connect(args.db) as db:
        db.execute("INSERT OR REPLACE INTO cards(id,domain,kind,title,summary,guidance,reject_when,verification,version_scope,confidence,priority,token_weight,source_basis) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", CARD)
        db.execute("INSERT OR REPLACE INTO card_activation_rules(card_id,min_hits) VALUES('VER-023',1)")
        for term in ("semantic lint", "denizencore", "scriptqueue", "tagmanager", "умный линт", "движок denizen"):
            db.execute("INSERT OR IGNORE INTO card_terms(card_id,term) VALUES('VER-023',?)", (term,))
            db.execute("INSERT OR IGNORE INTO card_activation_terms(card_id,term) VALUES('VER-023',?)", (term,))
            db.execute("INSERT OR REPLACE INTO card_alias_terms(card_id,term,weight) VALUES('VER-023',?,20)", (term,))
        db.execute("INSERT OR REPLACE INTO card_version_scopes(card_id,scope_type,product,addon,rationale) VALUES(?,?,?,?,?)", ("VER-023", "invariant", "", "", "Portable queue semantics are source-pinned and independent of Minecraft adapters."))
        db.execute("INSERT OR REPLACE INTO retrieval_tests VALUES(?,?,?,?,?,?,?,?)", ("AUTO52", "сделай умный semantic lint на движке denizen scriptqueue tagmanager", "new_mechanic", "verification,denizen", "", "VER-023", "", "Source-derived core remains separate from Bukkit runtime."))
        db.executemany("INSERT OR REPLACE INTO metadata(key,value) VALUES(?,?)", (("release.version", "0.58"), ("name", "dCore 0.58"), ("release.status", "active_semantic_lint")))
        db.execute("DELETE FROM card_search")
        db.execute("INSERT INTO card_search(id,title,summary,guidance,terms,domain,kind) SELECT c.id,c.title,c.summary,c.guidance,COALESCE((SELECT group_concat(term,' ') FROM card_terms t WHERE t.card_id=c.id),''),c.domain,c.kind FROM cards c")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
