from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


CARDS = (
    (
        "VER-021", "verification", "proof_pipeline", "A release has a machine proof state, not a prose claim",
        "A clean lint can prove syntax and selected static rules, but not installed addon behavior, visibility, pathfinding, reload cleanup or client rendering.",
        "Run one proof pipeline that records TARGET, RETRIEVAL, ROUTE, ADDON_SIGNATURE, SYNTAX and RUNTIME independently. `READY` is valid only when every required state passes. A runtime report names each required scenario and marks it PASS; absent or partial runtime keeps RELEASE_BLOCKED.",
        "Reject `STATIC_OK` as a delivery verdict, treating a JAR path as API proof, or writing 'should work' when a runtime case was not run.",
        "Keep the JSON proof report with the patch. Re-run it after a target, provider, route or lifecycle change; add every production regression as a named runtime case.",
        "dCore 0.56 executable proof gate", "high", 100, 1, "dcore_run release contract",
    ),
    (
        "PERF-013", "performance", "event_sharding", "Four-player event sessions use bounded queues, reservations and worker capacity",
        "A four-player match is not a four-player server. Sending every participant into one unbounded world/session process couples their hot paths and failure domain.",
        "Use a control plane that owns queue tickets, idempotency key, group formation and worker reservation. A worker owns several bounded sessions only when its measured CPU, entity, chunk and memory budgets permit it. Each session owns one isolated world/region namespace, participant set, deadline and idempotent cleanup. Transfer through the proxy/provider boundary after reservation succeeds; Denizen can own gameplay inside a session but does not make the proxy capacity claim true.",
        "Reject assigning players before a reservation, one global event loop for all matches, per-tick scans across every session, assuming a fixed players-per-machine number without measurement, or using fake visibility as isolation without proving every gameplay side effect is namespaced.",
        "Load-test with queue burst, partial group timeout, duplicate join, worker loss, transfer failure, session cleanup, two sessions on one worker and the configured concurrent-session ceiling. Record p95 tick time, queue age, active entities/chunks and cleanup failures per worker.",
        "Proxy/provider and server target sensitive", "high", 100, 1, "Community architecture discussion; no claim about a specific DMC deployment",
    ),
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
        db.executemany("INSERT OR REPLACE INTO cards(id,domain,kind,title,summary,guidance,reject_when,verification,version_scope,confidence,priority,token_weight,source_basis) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", CARDS)
        aliases = {
            "VER-021": ("proof pipeline", "runtime not run", "release blocked", "runtime report", "строгий runtime", "не говорить готово"),
            "PERF-013": ("event sharding", "four player event", "4 player event", "match queue", "event sessions", "ивент по 4 игрока", "очередь ивентов", "несколько каток на сервере"),
        }
        for card_id, terms in aliases.items():
            db.execute("INSERT OR REPLACE INTO card_activation_rules(card_id,min_hits) VALUES(?,1)", (card_id,))
            for term in terms:
                db.execute("INSERT OR IGNORE INTO card_terms(card_id,term) VALUES(?,?)", (card_id, term))
                db.execute("INSERT OR IGNORE INTO card_activation_terms(card_id,term) VALUES(?,?)", (card_id, term))
                db.execute("INSERT OR REPLACE INTO card_alias_terms(card_id,term,weight) VALUES(?,?,20)", (card_id, term))
        db.execute("INSERT OR REPLACE INTO card_version_scopes(card_id,scope_type,product,addon,rationale) VALUES(?,?,?,?,?)", ("VER-021", "invariant", "", "", "Proof-state semantics are version-neutral."))
        db.execute("INSERT OR REPLACE INTO card_version_scopes(card_id,scope_type,product,addon,rationale) VALUES(?,?,?,?,?)", ("PERF-013", "target_matrix", "", "", "Proxy/provider and server capacity require the selected deployment target."))
        for card_id in ("VER-021", "PERF-013"):
            db.execute("DELETE FROM route_pins WHERE card_id=?", (card_id,))
        tests = (
            ("AUTO49", "сделай строгий proof pipeline чтобы без runtime test нельзя было сказать готово", "full_audit", "verification,core", "", "VER-021", "", "Machine release gate."),
            ("AUTO50", "как сделать ивент по 4 игрока, несколько каток на сервере и не положить 200 онлайна", "new_mechanic", "performance,denizen,verification", "", "PERF-013", "", "Bounded event sharding."),
        )
        db.executemany("INSERT OR REPLACE INTO retrieval_tests VALUES(?,?,?,?,?,?,?,?)", tests)
        db.executemany(
            "INSERT OR REPLACE INTO intent_terms(intent,term,weight) VALUES(?,?,?)",
            (("full_audit", "proof pipeline", 24), ("new_mechanic", "ивент по 4 игрока", 28), ("new_mechanic", "несколько каток", 20)),
        )
        db.executemany("INSERT OR REPLACE INTO metadata(key,value) VALUES(?,?)", (("release.version", "0.56"), ("name", "dCore 0.56"), ("release.status", "active_proof_pipeline")))
        rebuild_search(db)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
