from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


CARD = (
    "VER-024", "verification", "queue_report", "Queue lifetime findings require a path report, not a bare loop error",
    "A bounded list, an event-driven wait loop and an actually unbounded loop can look identical to a naive semantic executor. The diagnostic must retain the root file/container, queue path, waits seen and the exact proof boundary.",
    "Report semantic execution limits with a call/inject path, static waits, root container and last trace entries. Classify static bounded execution, dynamic/event-driven execution and true recursive/unbounded execution separately. A limit is a proof failure for the current fixture, not an automatic claim that the production server is broken.",
    "Reject a naked line-only loop error, calling a semantic budget exhaustion a confirmed server lag, or suppressing it because a wait command exists without proving its exit condition.",
    "Run the real project report; verify gravity-gun and smiler fixtures are classified as dynamic/event-driven or unverified, while a literal while true and recursive run remain blocking.",
    "dCore semantic execution evidence and Denizen-Core queue lifecycle boundary", "high", 100, 1, "queue lifetime proof report",
)


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--db", type=Path, required=True); args = parser.parse_args()
    with sqlite3.connect(args.db) as db:
        db.execute("INSERT OR REPLACE INTO cards(id,domain,kind,title,summary,guidance,reject_when,verification,version_scope,confidence,priority,token_weight,source_basis) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", CARD)
        db.execute("INSERT OR REPLACE INTO card_activation_rules(card_id,min_hits) VALUES('VER-024',1)")
        for term in ("queue lifetime report", "semantic execution limit", "loop proof report", "отчёт очереди", "почему цикл", "gravity gun loop"):
            db.execute("INSERT OR IGNORE INTO card_terms(card_id,term) VALUES('VER-024',?)", (term,)); db.execute("INSERT OR IGNORE INTO card_activation_terms(card_id,term) VALUES('VER-024',?)", (term,)); db.execute("INSERT OR REPLACE INTO card_alias_terms(card_id,term,weight) VALUES('VER-024',?,20)", (term,))
        db.execute("INSERT OR REPLACE INTO card_version_scopes(card_id,scope_type,product,addon,rationale) VALUES(?,?,?,?,?)", ("VER-024", "invariant", "", "", "Proof classification is portable; runtime result remains target-specific."))
        db.execute("INSERT OR REPLACE INTO retrieval_tests VALUES(?,?,?,?,?,?,?,?)", ("AUTO55", "покажи почему semantic execution limit в gravity gun и smiler", "new_mechanic", "verification,denizen", "", "VER-024", "", "A limit requires path/lifetime classification, not an automatic runtime claim."))
        db.executemany("INSERT OR REPLACE INTO metadata(key,value) VALUES(?,?)", (("release.version", "0.61"), ("name", "dCore 0.61"), ("release.status", "active_queue_proof_report")))
        db.execute("DELETE FROM card_search"); db.execute("INSERT INTO card_search(id,title,summary,guidance,terms,domain,kind) SELECT c.id,c.title,c.summary,c.guidance,COALESCE((SELECT group_concat(term,' ') FROM card_terms t WHERE t.card_id=c.id),''),c.domain,c.kind FROM cards c")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
