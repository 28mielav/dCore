"""Original runnable examples stored in cards with explicit target selection."""
import argparse
import json
import sqlite3
from pathlib import Path


def migrate(db):
    db.execute("CREATE TABLE IF NOT EXISTS card_code_examples(example_id TEXT PRIMARY KEY, card_id TEXT NOT NULL, title TEXT NOT NULL, targets_json TEXT NOT NULL, files_json TEXT NOT NULL, explanation TEXT NOT NULL, verification TEXT NOT NULL)")
    examples = [
        ("bounded-repeat", "PERF-002", "Finite yielding task", {},
         {"bounded_task.dsc": "bounded_task:\n  type: task\n  script:\n  - repeat 20:\n    - wait 1t\n"},
         "Twenty iterations, each yielding one tick. run bounded_task to start. Repeat/wait syntax exists in all three indexed historical Core snapshots; no recent option is used.",
         "Static source syntax checked; server scheduling and timing require runtime verification."),
        ("legacy-flag-duration", "VER-002", "Temporary flag before the Core flag rewrite", {"denizen": ["1.1.4-source-7f9353e83"]},
         {"temporary_flag.dsc": "temporary_flag:\n  type: task\n  script:\n  - flag server lesson_active:true duration:10s\n"},
         "The historical Denizen Flag command uses duration:, not expire:. Run temporary_flag; check the server flag immediately and after 10 seconds.", "Source Meta at 7f9353e83; runtime unverified."),
        ("core-flag-expire", "VER-002", "Temporary flag after the Core flag rewrite", {"denizen": ["1.2.6-b1782", "1.3.0-b1804"]},
         {"temporary_flag.dsc": "temporary_flag:\n  type: task\n  script:\n  - flag server lesson_active:true expire:10s\n"},
         "The indexed Core Flag command uses expire:. Run temporary_flag; check immediately and after 10 seconds. Do not substitute this option into the older example.", "Date-associated Core source Meta; exact binary dependency and runtime unverified."),
    ]
    visual = Path(__file__).resolve().parents[2] / "examples" / "visual"
    for lesson, card in (("outline-mask", "VIS-024"), ("outline-scene-blur", "VIS-041"), ("menu-background-blur", "VIS-027")):
        folder = visual / lesson
        files = {p.relative_to(folder).as_posix(): p.read_text(encoding="utf-8") for p in sorted(folder.rglob("*")) if p.is_file() and p.name != "README.md"}
        examples.append((lesson, card, lesson.replace("-", " "), {"minecraft": ["1.21.8"]}, files,
                         (folder / "README.md").read_text(encoding="utf-8"), "Official client source inspected; static lint only, GPU/runtime unverified."))
    for eid, card, title, targets, files, explanation, verification in examples:
        db.execute("INSERT OR REPLACE INTO card_code_examples VALUES(?,?,?,?,?,?,?)",
                   (eid, card, title, json.dumps(targets), json.dumps(files), explanation, verification))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    args = parser.parse_args()
    with sqlite3.connect(args.db) as db:
        migrate(db)
