from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path("knowledge/dcore.sqlite"))
    args = parser.parse_args()
    with sqlite3.connect(args.db) as db:
        for card_id, term in (
            ("TEACH-004", "мой первый Denizen скрипт"),
            ("TEACH-005", "что тут неплохо"),
            ("TEACH-005", "где это говно"),
        ):
            db.execute("INSERT OR IGNORE INTO card_terms(card_id,term) VALUES(?,?)", (card_id, term))
            db.execute("INSERT OR IGNORE INTO card_activation_terms(card_id,term) VALUES(?,?)", (card_id, term))
            db.execute("INSERT OR REPLACE INTO card_alias_terms(card_id,term,weight) VALUES(?,?,20)", (card_id, term))
        db.execute("DELETE FROM card_search")
        db.execute(
            """INSERT INTO card_search(id,title,summary,guidance,terms,domain,kind)
               SELECT c.id,c.title,c.summary,c.guidance,
                      COALESCE((SELECT group_concat(term,' ') FROM card_terms t WHERE t.card_id=c.id),''),
                      c.domain,c.kind FROM cards c"""
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
