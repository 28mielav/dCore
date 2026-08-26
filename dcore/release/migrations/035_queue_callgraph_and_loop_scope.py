from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


CARD = (
    "DEN-032", "denizen", "queue_semantics", "Lint queue calls and loop scope as Denizen queues, not loose text",
    "`run` creates a separate queue with positional or named definitions; `foreach` temporarily owns value/key/loop_index; non-passive `determine` terminates the queue. Ignoring this creates false reachability, missing-input and recursion bugs that token lint cannot see.",
    "Trace local run targets, map positional def values to the target declaration order, preserve named def values, report missing targets/inputs and reject local recursion. During a statically known foreach, scope and restore value/key/loop_index, honor foreach next/stop locally, and treat determine as terminal unless passively. Keep cross-file bodies, Bukkit state, MapTag iteration and scheduling as explicit analysis/runtime boundaries.",
    "Reject treating a supplied definition as global, leaking foreach value after the loop, continuing after terminal determine, or allowing a recursive run cycle because the text parses.",
    "Test named and positional run definitions, cross-file known target, missing target/input, direct recursion, foreach next/stop/scope restoration, terminal and passive determine, then execute the relevant server fixture.",
    "Denizen-Core RunCommand, ForeachCommand and DetermineCommand source semantics", "high", 100, 1, "source-derived queue call graph",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    args = parser.parse_args()
    with sqlite3.connect(args.db) as db:
        db.execute("INSERT OR REPLACE INTO cards(id,domain,kind,title,summary,guidance,reject_when,verification,version_scope,confidence,priority,token_weight,source_basis) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", CARD)
        db.execute("INSERT OR REPLACE INTO card_activation_rules(card_id,min_hits) VALUES('DEN-032',1)")
        for term in ("queue call graph", "run definitions", "foreach scope", "determine queue", "рекурсия run", "очередь denizen"):
            db.execute("INSERT OR IGNORE INTO card_terms(card_id,term) VALUES('DEN-032',?)", (term,))
            db.execute("INSERT OR IGNORE INTO card_activation_terms(card_id,term) VALUES('DEN-032',?)", (term,))
            db.execute("INSERT OR REPLACE INTO card_alias_terms(card_id,term,weight) VALUES('DEN-032',?,20)", (term,))
        db.execute("INSERT OR REPLACE INTO card_version_scopes(card_id,scope_type,product,addon,rationale) VALUES(?,?,?,?,?)", ("DEN-032", "invariant", "", "", "Queue scope is portable Denizen-Core semantics."))
        db.execute("INSERT OR REPLACE INTO retrieval_tests VALUES(?,?,?,?,?,?,?,?)", ("AUTO53", "проверь run definitions foreach scope determine recursion в denizen", "new_mechanic", "denizen,verification", "", "DEN-032", "", "Queue semantics require runtime only for platform-bound objects."))
        db.executemany("INSERT OR REPLACE INTO metadata(key,value) VALUES(?,?)", (("release.version", "0.59"), ("name", "dCore 0.59"), ("release.status", "active_queue_callgraph")))
        db.execute("DELETE FROM card_search")
        db.execute("INSERT INTO card_search(id,title,summary,guidance,terms,domain,kind) SELECT c.id,c.title,c.summary,c.guidance,COALESCE((SELECT group_concat(term,' ') FROM card_terms t WHERE t.card_id=c.id),''),c.domain,c.kind FROM cards c")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
