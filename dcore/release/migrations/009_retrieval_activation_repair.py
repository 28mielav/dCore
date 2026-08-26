from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


TERMS = {
    "CORE-023": ["не выдавай полный", "не выдавай полный treasures", "один небольшой фрагмент", "объясни владельца"],
    "CORE-024": ["вайбкодинг", "вайб кодинг", "не делай вывод об авторстве", "конкретные риски"],
    "TEACH-004": ["обучи меня сделать", "через пример", "мою попытку", "перенос на похожий"],
    "TEACH-005": ["профессионально и прямо", "не хвали плохой код", "не имитируй мою ругань"],
    "VER-013": ["один фрагмент", "компактным", "без json кухни", "не выдавай полный"],
    "DEN-029": ["ругается на reflect", "denizenm api", "ложная ошибка ide"],
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path("knowledge/dcore.sqlite"))
    args = parser.parse_args()
    with sqlite3.connect(args.db) as db:
        for card_id, terms in TERMS.items():
            for term in terms:
                db.execute("INSERT OR IGNORE INTO card_terms(card_id,term) VALUES(?,?)", (card_id, term))
                db.execute("INSERT OR IGNORE INTO card_activation_terms(card_id,term) VALUES(?,?)", (card_id, term))
                db.execute("INSERT OR REPLACE INTO card_alias_terms(card_id,term,weight) VALUES(?,?,20)", (card_id, term))
        db.execute("UPDATE retrieval_tests SET query='Диагностика: игрок закрывает GUI. Проверь точную identity-инвентаря и не коммить старый snapshot.' WHERE id='AUTO07'")
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
