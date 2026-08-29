from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path("dcore/knowledge/data/dcore.sqlite"))
    args = parser.parse_args()
    with sqlite3.connect(args.db) as db:
        term = "не хвали плохой код"
        db.execute("INSERT OR IGNORE INTO card_terms(card_id,term) VALUES(?,?)", ("CORE-024", term))
        db.execute("INSERT OR IGNORE INTO card_activation_terms(card_id,term) VALUES(?,?)", ("CORE-024", term))
        db.execute("INSERT OR REPLACE INTO card_alias_terms(card_id,term,weight) VALUES(?,?,20)", ("CORE-024", term))
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
