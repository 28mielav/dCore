from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


INTENTS = (
    ("diagnose", "диагностика", 24),
    ("diagnose", "проверь этот код", 18),
    ("teach", "обучи меня", 24),
    ("teach", "через пример мою попытку", 18),
    ("quick_question", "отвечай профессионально", 18),
    ("quick_question", "сделай ответ компактным", 18),
)

TERMS = {
    "CORE-018": ["identity-инвентаря"],
    "CORE-022": ["без JSON кухни", "таблица проверки и следующий шаг"],
    "CORE-023": ["объясни владельца состояния и дай один небольшой фрагмент", "через пример мою попытку"],
    "VER-010": ["конкретные риски и тесты"],
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path("dcore/knowledge/data/dcore.sqlite"))
    args = parser.parse_args()
    with sqlite3.connect(args.db) as db:
        for intent, term, weight in INTENTS:
            db.execute("INSERT OR REPLACE INTO intent_terms(intent,term,weight) VALUES(?,?,?)", (intent, term, weight))
        for card_id, terms in TERMS.items():
            for term in terms:
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
