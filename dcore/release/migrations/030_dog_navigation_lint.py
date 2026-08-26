from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


CARDS = (
    (
        "DOG-001", "denizen", "state_machine", "Dog search has explicit session phases and one cleanup owner",
        "A treasure dog mixes target selection, pathfinding, discovery, rewards and recovery unless its session phases are explicit.",
        "Model one session as acquire -> choose_target -> navigate -> inspect -> resolve -> cleanup. The session record owns phase, target, deadline and the navigation entity reference. Candidate generation validates ground, water and slope before navigation; it does not steer every tick. Every terminal path reaches idempotent cleanup.",
        "Reject a branch ladder that silently encodes phase, a target stored independently on player and wolf, or cleanup that only runs after success.",
        "Trace success, no candidate, no progress, invalid target, player quit, wolf death and reload. Prove one session owner and that cleanup can run twice without creating a second reward or orphan navigation.",
        "DenizenM native navigation is target/build sensitive", "high", 100, 1, "dCore treasure-dog architecture contract",
    ),
    (
        "PERF-012", "performance", "dog_navigation", "Dog pathfinding has one movement owner and a bounded replan trigger",
        "Native walk, scripted push, teleport correction and per-tick waypoint replacement compete for the same wolf velocity and target state.",
        "During navigate, native walk is the only movement owner. Before a launch, push or teleport correction, stop walk and transition phase. Replan only after a deadline, measured lack of progress or target invalidation; never from on tick or every movement event. Keep the current target and last-progress sample in the session record.",
        "Reject active walk plus push/teleport, a second walk before stop, and walk started by an on-tick dog handler.",
        "Run dcore_lint for the exact target, then test flat ground, custom terrain, water boundary, obstruction, no progress, player quit, entity death and reload. A static pass is not pathfinding proof.",
        "DenizenM native navigation is target/build sensitive", "high", 100, 1, "dCore 0.54 dog navigation static gate",
    ),
)


CONTRAST = (
    "CX-DEN-019", "denizen", "Competing dog movement owners", "dog_navigation_owner_conflict",
    "- walk <[wolf]> <[target]>\n- push <[wolf]> origin:<[wolf].location> destination:<[target]> speed:1",
    "- walk <[wolf]> <[target]>\n- walk <[wolf]> stop\n- push <[wolf]> origin:<[wolf].location> destination:<[target]> speed:1",
    "Push changes velocity while native navigation remains active, producing circular or unstable movement.",
    "Exactly one movement controller owns the dog in each phase.",
    "Lint reports no owner conflict; runtime covers obstacle, water, no-progress and recovery transitions.",
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
        db.executemany(
            "INSERT OR REPLACE INTO cards(id,domain,kind,title,summary,guidance,reject_when,verification,version_scope,confidence,priority,token_weight,source_basis) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            CARDS,
        )
        aliases = {
            "DOG-001": ("treasure dog", "dog state machine", "собака ищет клад", "собака", "собаку", "волк", "wolf session", "cleanup dog"),
            "PERF-012": ("dog pathfinding", "walk push", "walk teleport", "dog walks in circles", "repath dog", "собака ходит кругами", "собаку", "ходит кругами", "walk конфликтует с push", "pathfinding", "pathfinding собак"),
        }
        for card_id, terms in aliases.items():
            db.execute("INSERT OR REPLACE INTO card_activation_rules(card_id,min_hits) VALUES(?,1)", (card_id,))
            for term in terms:
                db.execute("INSERT OR IGNORE INTO card_terms(card_id,term) VALUES(?,?)", (card_id, term))
                db.execute("INSERT OR IGNORE INTO card_activation_terms(card_id,term) VALUES(?,?)", (card_id, term))
                db.execute("INSERT OR REPLACE INTO card_alias_terms(card_id,term,weight) VALUES(?,?,20)", (card_id, term))
            db.execute(
                "INSERT OR REPLACE INTO card_version_scopes(card_id,scope_type,product,addon,rationale) VALUES(?,?,?,?,?)",
                (card_id, "target_matrix", "DenizenM", "", "Native navigation behavior must be resolved against the selected build."),
            )

        db.execute(
            "INSERT OR REPLACE INTO contrast_examples(id,domain,title,diagnostic_code,bad_snippet,good_snippet,bad_reason,invariant,verification) VALUES(?,?,?,?,?,?,?,?,?)",
            CONTRAST,
        )
        for term in ("walk push", "dog pathfinding", "собака ходит кругами", "navigation owner"):
            db.execute("INSERT OR REPLACE INTO contrast_terms VALUES(?,?,1)", ("CX-DEN-019", term))

        for card_id in ("DOG-001", "PERF-012"):
            db.execute("DELETE FROM route_pins WHERE card_id=?", (card_id,))
        for position, (intent, card_id) in enumerate((("bugfix", "PERF-012"), ("performance_review", "PERF-012")), 76):
            db.execute("INSERT OR REPLACE INTO route_pins(intent,card_id,position) VALUES(?,?,?)", (intent, card_id, position))

        tests = (
            ("AUTO47", "перепиши собаку для поиска клада как нормальную машину состояний с cleanup", "refactor", "denizen,performance,verification", "", "DOG-001,PERF-012", "", "Dog lifecycle and native-navigation ownership."),
            ("AUTO48", "у собаки pathfinding: walk конфликтует с push и она ходит кругами, найди причину", "diagnose", "denizen,performance", "", "PERF-012", "", "Competing movement owner."),
        )
        db.executemany("INSERT OR REPLACE INTO retrieval_tests VALUES(?,?,?,?,?,?,?,?)", tests)
        for intent, term, weight in (("refactor", "машину состояний", 16), ("diagnose", "ходит кругами", 18), ("performance_review", "dog pathfinding", 20)):
            db.execute("INSERT OR REPLACE INTO intent_terms(intent,term,weight) VALUES(?,?,?)", (intent, term, weight))

        db.executemany(
            "INSERT OR REPLACE INTO metadata(key,value) VALUES(?,?)",
            (("release.version", "0.54"), ("name", "dCore 0.54"), ("lint.dog_navigation", "exclusive movement owner; no hot-event repath")),
        )
        rebuild_search(db)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
