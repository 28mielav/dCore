from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


INTENT_BY_DOMAIN = {
    "addons": "bugfix",
    "core": "full_audit",
    "denizen": "quick_question",
    "math": "refactor",
    "performance": "performance_review",
    "teaching": "teach",
    "verification": "diagnose",
    "visual": "visual_design",
}

INTENT_PREFIX = {
    "bugfix": "bugfix addon",
    "full_audit": "full audit core",
    "quick_question": "quick question denizen",
    "refactor": "refactor math",
    "performance_review": "performance review lag",
    "teach": "teach",
    "diagnose": "diagnose verification",
    "visual_design": "visual design",
}


def non_trigger(card: sqlite3.Row) -> str:
    """Write a guard, not a fake semantic claim.

    The old corpus had useful advice but left the negative boundary implicit.
    This wording is intentionally conservative: it prevents keyword-only use
    while making the card owner verify the exact trigger and declared scope.
    """
    scope = str(card["version_scope"] or "").strip()
    if any(word in scope.casefold() for word in ("version", "build", "addon", "target", "matrix")):
        return (
            "Reject when the exact target, build or addon scope is unknown or does not match "
            "this card; a related keyword is not compatibility evidence."
        )
    return (
        "Reject when the named trigger, ownership boundary or invariant is absent; "
        "do not apply this card from a loosely related keyword alone."
    )


def ensure_activation(db: sqlite3.Connection, card_id: str, terms: tuple[str, ...]) -> None:
    """Make a deliberately narrow card reachable for its own contract test."""
    db.execute(
        "INSERT OR REPLACE INTO card_activation_rules(card_id,min_hits) VALUES(?,1)",
        (card_id,),
    )
    for term in terms:
        db.execute(
            "INSERT OR IGNORE INTO card_activation_terms(card_id,term) VALUES(?,?)",
            (card_id, term),
        )
        db.execute(
            "INSERT OR REPLACE INTO card_alias_terms(card_id,term,weight) VALUES(?,?,?)",
            (card_id, term, 18),
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    args = parser.parse_args()

    with sqlite3.connect(args.db) as db:
        db.row_factory = sqlite3.Row
        cards = db.execute("SELECT * FROM cards ORDER BY id").fetchall()
        for card in cards:
            if not str(card["reject_when"] or "").strip():
                db.execute(
                    "UPDATE cards SET reject_when=? WHERE id=?",
                    (non_trigger(card), card["id"]),
                )

            has_test = db.execute(
                "SELECT 1 FROM retrieval_tests WHERE ',' || expected_cards || ',' LIKE ? LIMIT 1",
                (f"%,{card['id']},%",),
            ).fetchone()
            if has_test:
                continue

            intent = INTENT_BY_DOMAIN[card["domain"]]
            # The exact title is intentionally part of the query. This makes
            # the test exercise the real FTS/activation route, not a hidden
            # card-id shortcut.
            query = f"{INTENT_PREFIX[intent]} {card['title']}"

            # Two legacy cards had terms but no activation rule and therefore
            # could not be reached reliably when their optional domain was not
            # active. Give them one explicit, narrow activation phrase.
            if card["id"] == "ADD-005":
                ensure_activation(db, card["id"], ("external api",))
                query = "bugfix addon external api bounded transaction"
            elif card["id"] == "MATH-008":
                ensure_activation(db, card["id"], ("formula validation",))
                query = "refactor formula validation numerical effects"

            db.execute(
                "INSERT OR REPLACE INTO retrieval_tests "
                "(id,query,intent,expected_domains,forbidden_domains,expected_cards,forbidden_cards,notes) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (
                    f"CARD041_{card['id']}",
                    query,
                    intent,
                    card["domain"],
                    "",
                    card["id"],
                    "",
                    "Executable card-contract route seeded from the card title; keep green.",
                ),
            )

        db.execute("DELETE FROM card_search")
        db.execute(
            "INSERT INTO card_search(id,title,summary,guidance,terms,domain,kind) "
            "SELECT c.id,c.title,c.summary,c.guidance,"
            "COALESCE((SELECT group_concat(term,' ') FROM card_terms t WHERE t.card_id=c.id),''),"
            "c.domain,c.kind FROM cards c"
        )
        db.execute(
            "INSERT OR REPLACE INTO metadata(key,value) VALUES(?,?)",
            ("architecture_revision", "card-contracts-and-router-trace-1"),
        )
        db.execute(
            "INSERT OR REPLACE INTO metadata(key,value) VALUES(?,?)",
            ("release.status", "pool3_card_contracts"),
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
