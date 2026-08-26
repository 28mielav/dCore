from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


CARD = (
    "VER-025", "verification", "fixture_policy", "Fixtures lower uncertainty only on explicit queue paths",
    "Static semantic execution cannot know an event's next input, external list, or terminal condition. A fixture is evidence input, not a global suppression switch.",
    "Keep diagnostic severity, priority and confidence bucket separate. Treat context/list/duration gaps as input or platform boundaries; treat dynamic wait limits as P1 warnings; accept them as information only when a fixture names the exact source:line path. Keep structural recursion, unknown target and invalid terminal commands blocking.",
    "Reject a fixture that globally disables a rule, a warning that hides its confidence bucket, or an information row that silently claims runtime proof.",
    "Run dcore_lint with and without a fixture for one known lifetime path and verify only that exact finding changes severity; unrelated paths remain unchanged.",
    "dCore queue report policy", "high", 100, 1, "explicit fixture confidence policy",
)


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--db", type=Path, required=True); args = parser.parse_args()
    with sqlite3.connect(args.db) as db:
        db.execute("INSERT OR REPLACE INTO cards(id,domain,kind,title,summary,guidance,reject_when,verification,version_scope,confidence,priority,token_weight,source_basis) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", CARD)
        db.execute("INSERT OR REPLACE INTO card_activation_rules(card_id,min_hits) VALUES('VER-025',1)")
        for term in ("queue fixture", "diagnostic priority", "confidence bucket", "fixture only this path", "приоритет ошибки", "fixture не скрывает"):
            db.execute("INSERT OR IGNORE INTO card_terms(card_id,term) VALUES('VER-025',?)", (term,)); db.execute("INSERT OR IGNORE INTO card_activation_terms(card_id,term) VALUES('VER-025',?)", (term,)); db.execute("INSERT OR REPLACE INTO card_alias_terms(card_id,term,weight) VALUES('VER-025',?,20)", (term,))
        db.execute("INSERT OR REPLACE INTO card_version_scopes(card_id,scope_type,product,addon,rationale) VALUES(?,?,?,?,?)", ("VER-025", "invariant", "", "", "Fixture policy is dCore lint confidence policy."))
        db.execute("INSERT OR REPLACE INTO retrieval_tests VALUES(?,?,?,?,?,?,?,?)", ("AUTO56", "добавь fixture приоритет confidence bucket чтобы lint не ошибался по хуйнe", "new_mechanic", "verification,denizen", "", "VER-025", "", "Fixtures are explicit per-path evidence, not suppressions."))
        db.executemany("INSERT OR REPLACE INTO metadata(key,value) VALUES(?,?)", (("release.version", "0.62"), ("name", "dCore 0.62"), ("release.status", "active_fixture_confidence_policy")))
        db.execute("DELETE FROM card_search"); db.execute("INSERT INTO card_search(id,title,summary,guidance,terms,domain,kind) SELECT c.id,c.title,c.summary,c.guidance,COALESCE((SELECT group_concat(term,' ') FROM card_terms t WHERE t.card_id=c.id),''),c.domain,c.kind FROM cards c")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
