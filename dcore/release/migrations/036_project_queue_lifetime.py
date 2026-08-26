from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


CARD = (
    "DEN-033", "denizen", "queue_lifetime", "Analyze project-wide queue flow, shared inject scope and wait boundaries",
    "A project split across DSC files still has one call graph. Run creates a child queue, inject prepends entries to the current queue and shares definitions/delays, while wait changes queue timing rather than proving scheduler/runtime behavior.",
    "Build one local program from all linted DSC files before semantic traversal. Follow local run targets across files and reject cycles. Execute inject in the caller queue, preserve shared definitions, reject inject cycles and mark unresolved paths as an explicit boundary. Record static wait durations; dynamic duration needs a fixture or runtime proof. Foreach supports bounded ListTag and MapTag fixtures with scoped key/value/index restoration.",
    "Reject validating each file as an isolated program, treating inject as run, leaking injected definitions incorrectly, or calling a static wait proof a real scheduler test.",
    "Test cross-file run cycle, inject scope/stop/cycle, static and dynamic wait, and MapTag foreach key/value scope, then run the actual server lifecycle matrix.",
    "Denizen-Core InjectCommand and WaitCommand source semantics", "high", 100, 1, "source-derived project queue model",
)


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--db", type=Path, required=True); args = parser.parse_args()
    with sqlite3.connect(args.db) as db:
        db.execute("INSERT OR REPLACE INTO cards(id,domain,kind,title,summary,guidance,reject_when,verification,version_scope,confidence,priority,token_weight,source_basis) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", CARD)
        db.execute("INSERT OR REPLACE INTO card_activation_rules(card_id,min_hits) VALUES('DEN-033',1)")
        for term in ("project queue graph", "inject scope", "wait queue", "cross file run", "межфайловый run", "inject denizen"):
            db.execute("INSERT OR IGNORE INTO card_terms(card_id,term) VALUES('DEN-033',?)", (term,)); db.execute("INSERT OR IGNORE INTO card_activation_terms(card_id,term) VALUES('DEN-033',?)", (term,)); db.execute("INSERT OR REPLACE INTO card_alias_terms(card_id,term,weight) VALUES('DEN-033',?,20)", (term,))
        db.execute("INSERT OR REPLACE INTO card_version_scopes(card_id,scope_type,product,addon,rationale) VALUES(?,?,?,?,?)", ("DEN-033", "invariant", "", "", "Project queue topology is portable Denizen-Core semantics."))
        db.execute("INSERT OR REPLACE INTO retrieval_tests VALUES(?,?,?,?,?,?,?,?)", ("AUTO54", "проверь межфайловый run inject wait очередь denizen", "new_mechanic", "denizen,verification", "", "DEN-033", "", "Static queue topology is not server scheduler proof."))
        db.executemany("INSERT OR REPLACE INTO metadata(key,value) VALUES(?,?)", (("release.version", "0.60"), ("name", "dCore 0.60"), ("release.status", "active_project_queue_lifetime")))
        db.execute("DELETE FROM card_search"); db.execute("INSERT INTO card_search(id,title,summary,guidance,terms,domain,kind) SELECT c.id,c.title,c.summary,c.guidance,COALESCE((SELECT group_concat(term,' ') FROM card_terms t WHERE t.card_id=c.id),''),c.domain,c.kind FROM cards c")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
