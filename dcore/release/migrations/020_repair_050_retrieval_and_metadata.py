from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def rebuild_search(db: sqlite3.Connection) -> None:
    db.execute("DELETE FROM card_search")
    db.execute(
        """INSERT INTO card_search(id,title,summary,guidance,terms,domain,kind)
           SELECT c.id,c.title,c.summary,c.guidance,
                  COALESCE((SELECT group_concat(term,' ') FROM card_terms t WHERE t.card_id=c.id),''),
                  c.domain,c.kind FROM cards c"""
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path("dcore/knowledge/data/dcore.sqlite"))
    args = parser.parse_args()
    with sqlite3.connect(args.db) as db:
        db.execute("INSERT OR REPLACE INTO metadata VALUES('name','dCore 0.50')")
        db.execute("DELETE FROM metadata WHERE key='metadata_name'")
        db.execute("UPDATE cards SET priority=20, token_weight=2 WHERE id='CORE-028'")
        for term in ("API", "API confirms", "signature proof", "Reflect API"):
            db.execute("INSERT OR IGNORE INTO card_terms(card_id,term) VALUES('ADD-002',?)", (term,))
            db.execute("INSERT OR IGNORE INTO card_activation_terms(card_id,term) VALUES('ADD-002',?)", (term,))
            db.execute("INSERT OR REPLACE INTO card_alias_terms(card_id,term,weight) VALUES('ADD-002',?,?)", (term, 28))
        rebuild_search(db)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
