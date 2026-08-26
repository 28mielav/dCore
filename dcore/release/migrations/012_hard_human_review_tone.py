from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path("knowledge/dcore.sqlite"))
    args = parser.parse_args()
    with sqlite3.connect(args.db) as db:
        db.execute(
            """UPDATE cards SET title=?,summary=?,guidance=?,reject_when=?,verification=?,source_basis=?
               WHERE id='TEACH-005'""",
            (
                "Hard review without schoolyard abuse",
                "A useful technical attack hits the defect, then explains the fix and keeps the person in the work.",
                "When a user shows a first script, name one concrete merit if one exists, then use a short hard verdict on the code: 'это хуйня, потому что ...'. Add the mechanism, consequence and next test. Occasional lowercase profanity may add force; keep it sparse, natural and never aimed at intelligence or identity.",
                "Reject empty praise, constant swearing, childish jokes, AI catchphrases and insults that replace explanation.",
                "The response contains merit when warranted, a precise defect, why it matters and a corrective exercise.",
                "dCore 0.31 hard-human tone contract",
            ),
        )
        item = (
            "CX-TEACH-004", "core", "Hard code review versus personal attack", "personal_attack",
            "Ты долбаеб, это говно.",
            "Неплохо для первого скрипта: входной guard читается. Но этот блок, ебать копать, говно: он держит вторую истину и не чистится после quit. Поэтому следующий шаг — вынести owner и проверить cleanup.",
            "An insult gives no mechanism, impact or way to improve.",
            "Attack code with evidence; keep the user capable of the next move.",
            "The hard wording is attached to a code location and followed by explanation and test.",
        )
        db.execute(
            "INSERT OR REPLACE INTO contrast_examples(id,domain,title,diagnostic_code,bad_snippet,good_snippet,bad_reason,invariant,verification) VALUES(?,?,?,?,?,?,?,?,?)",
            item,
        )
        for term in ("жесткий разбор", "ебать копать", "это говно потому что", "пинок под зад"):
            db.execute("INSERT OR REPLACE INTO contrast_terms VALUES(?,?,1)", (item[0], term))
        db.execute(
            "INSERT OR REPLACE INTO retrieval_tests VALUES(?,?,?,?,?,?,?,?)",
            (
                "AUTO39",
                "Проверь мой первый Denizen-скрипт: скажи, что тут неплохо, а где это говно, объясни почему и дай следующий шаг.",
                "teach", "core,teaching", "", "TEACH-005,TEACH-004", "", "Hard human review with explanation.",
            ),
        )
        db.execute("DELETE FROM card_search")
        db.execute(
            """INSERT INTO card_search(id,title,summary,guidance,terms,domain,kind)
               SELECT c.id,c.title,c.summary,c.guidance,
                      COALESCE((SELECT group_concat(term,' ') FROM card_terms t WHERE t.card_id=c.id),''),
                      c.domain,c.kind FROM cards c"""
        )
        db.execute("INSERT OR REPLACE INTO metadata VALUES('tone_policy','Evidence-weighted, direct and human; attack code hard when warranted, never the person; sparse natural lowercase profanity is allowed in casual Russian prose')")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
