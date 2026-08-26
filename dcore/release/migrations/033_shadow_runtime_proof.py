from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


CARD = (
    "VER-022", "verification", "shadow_runtime", "Low-memory simulation proves control-plane invariants, not Minecraft behavior",
    "A queue/reservation/cleanup failure can be reproduced without booting Paper, but a simulation cannot prove Denizen execution, plugin APIs, player transfer, pathfinding or client rendering.",
    "Use a deterministic shadow plan for event-session queue, grouping, capacity, duplicate input, worker loss and cleanup. Record SIMULATION_PASS separately. Keep runtime as NOT_RUN until the actual server matrix passes; a simulation failure blocks the release immediately.",
    "Reject calling SIMULATION_PASS a server test, omitting capacity/worker-loss cases, or ignoring a failed simulation because lint is clean.",
    "Run dcore_shadow with at least capacity saturation, duplicate join, transfer failure or worker loss, then run the focused Minecraft server matrix before READY.",
    "dCore 0.57 shadow-runtime contract", "high", 100, 1, "dcore_shadow executable model",
)


def rebuild_search(db: sqlite3.Connection) -> None:
    db.execute("DELETE FROM card_search")
    db.execute("""INSERT INTO card_search(id,title,summary,guidance,terms,domain,kind)
                  SELECT c.id,c.title,c.summary,c.guidance,COALESCE((SELECT group_concat(term,' ') FROM card_terms t WHERE t.card_id=c.id),''),c.domain,c.kind FROM cards c""")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    args = parser.parse_args()
    with sqlite3.connect(args.db) as db:
        db.execute("INSERT OR REPLACE INTO cards(id,domain,kind,title,summary,guidance,reject_when,verification,version_scope,confidence,priority,token_weight,source_basis) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", CARD)
        db.execute("INSERT OR REPLACE INTO card_activation_rules(card_id,min_hits) VALUES('VER-022',1)")
        for term in ("shadow runtime", "simulation pass", "event simulation", "без запуска minecraft", "дешёвый runtime", "queue simulation"):
            db.execute("INSERT OR IGNORE INTO card_terms(card_id,term) VALUES('VER-022',?)", (term,))
            db.execute("INSERT OR IGNORE INTO card_activation_terms(card_id,term) VALUES('VER-022',?)", (term,))
            db.execute("INSERT OR REPLACE INTO card_alias_terms(card_id,term,weight) VALUES('VER-022',?,20)", (term,))
        for term in ("очереди ивента", "queue simulation"):
            db.execute("INSERT OR IGNORE INTO card_terms(card_id,term) VALUES('PERF-013',?)", (term,))
            db.execute("INSERT OR IGNORE INTO card_activation_terms(card_id,term) VALUES('PERF-013',?)", (term,))
            db.execute("INSERT OR REPLACE INTO card_alias_terms(card_id,term,weight) VALUES('PERF-013',?,20)", (term,))
        db.execute("INSERT OR REPLACE INTO card_version_scopes(card_id,scope_type,product,addon,rationale) VALUES(?,?,?,?,?)", ("VER-022", "invariant", "", "", "Simulation semantics are version-neutral."))
        db.execute("INSERT OR REPLACE INTO retrieval_tests VALUES(?,?,?,?,?,?,?,?)", ("AUTO51", "сделай дешёвый shadow runtime для очереди ивента без запуска minecraft", "new_mechanic", "verification,performance", "", "VER-022,PERF-013", "", "Simulation is not server runtime."))
        db.executemany("INSERT OR REPLACE INTO metadata(key,value) VALUES(?,?)", (("release.version", "0.57"), ("name", "dCore 0.57"), ("release.status", "active_shadow_runtime")))
        rebuild_search(db)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
