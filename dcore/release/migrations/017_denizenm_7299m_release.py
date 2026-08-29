from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


CARD = (
    "DEN-030", "denizen", "release", "DenizenM 7299M release boundary",
    "Denizen 1.3.3 b7299M was released on 2026-07-30 at commit 478d877. The release notes list performance and Paper-component fixes, but they are not a full Meta snapshot.",
    "For a 7299M server, pin the jar and record the build before choosing version-sensitive syntax. The release notes specifically mention the `on player join` determine/context.message fix with Paper components, stricter async teleport entity checks, `showfake` performance, head-component support in `.optimize_json`, stricter schematic material validation and ParticleBuilder optimization in `playeffect`. Prefer these native paths only after exact Meta or runtime verification. Keep the old source snapshot marked as the last indexed Meta until the 7299M source is re-ingested.",
    "Reject claiming that every 7299M API change is known from the release notes, silently mixing 7290M and 7299M behavior, or calling a release-notes card runtime proof.",
    "Verify the installed 7299M jar, refresh the fork Meta from tag/commit 478d877 when the source fetch is available, then run `/ex reload`, event, teleport, showfake, JSON, schematic and playeffect fixtures.",
    "Denizen 1.3.3 b7299M; Paper 1.21+ target; Meta re-ingest pending",
    "high", 100, 1, "https://github.com/Energobro/DenizenM-Tjtoxshpilivili1/releases/tag/7299M",
)


ALIASES = (
    "7299M", "b7299M", "DenizenM 7299M", "Denizen 1.3.3 b7299M",
    "on player join context.message", "async teleport entity check",
    "showfake performance", "optimize_json head", "schematic material validation",
    "playeffect ParticleBuilder",
)


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
        db.execute(
            "INSERT OR REPLACE INTO cards(id,domain,kind,title,summary,guidance,reject_when,verification,version_scope,confidence,priority,token_weight,source_basis) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            CARD,
        )
        db.execute("INSERT OR REPLACE INTO card_activation_rules(card_id,min_hits) VALUES(?,1)", (CARD[0],))
        for term in ALIASES:
            db.execute("INSERT OR IGNORE INTO card_terms(card_id,term) VALUES(?,?)", (CARD[0], term))
            db.execute("INSERT OR IGNORE INTO card_activation_terms(card_id,term) VALUES(?,?)", (CARD[0], term))
            db.execute("INSERT OR REPLACE INTO card_alias_terms(card_id,term,weight) VALUES(?,?,?)", (CARD[0], term, 20))
        db.execute(
            "INSERT OR REPLACE INTO contrast_examples(id,domain,title,diagnostic_code,bad_snippet,good_snippet,bad_reason,invariant,verification) VALUES(?,?,?,?,?,?,?,?,?)",
            (
                "CX-DEN-017", "denizen", "Release notes versus complete Meta", "release_notes_overclaim",
                "7299M says it fixed teleport, so use every new tag without checking the build.",
                "Pin 7299M, refresh exact Meta when available, and runtime-test the changed boundary. Until then, call the release notes evidence, not syntax proof.",
                "A release summary names behavior changes but does not enumerate all commands, tags, contexts or fork deviations.",
                "Version-sensitive syntax needs exact source/build or runtime evidence.",
                "The answer labels Meta re-ingest pending and lists a fixture for each changed feature.",
            ),
        )
        for term in ("7299M", "release notes", "meta re-ingest", "version boundary", "b7299"):
            db.execute("INSERT OR REPLACE INTO contrast_terms VALUES(?,?,1)", ("CX-DEN-017", term))
        db.execute(
            "INSERT OR REPLACE INTO retrieval_tests VALUES(?,?,?,?,?,?,?,?)",
            (
                "AUTO42", "DenizenM 7299M release notes: what changed and what still needs exact Meta or runtime proof", "new_mechanic", "denizen,verification,core", "", "DEN-030", "", "Release notes are not a full Meta snapshot.",
            ),
        )
        db.execute("INSERT OR REPLACE INTO metadata VALUES('denizenm.target_version','1.3.3-b7299M')")
        db.execute("INSERT OR REPLACE INTO metadata VALUES('denizenm.release_commit','478d877')")
        db.execute("INSERT OR REPLACE INTO metadata VALUES('denizenm.release_date','2026-07-30')")
        db.execute("INSERT OR REPLACE INTO metadata VALUES('denizenm.release_notes_status','indexed; exact 7299M Meta re-ingest pending due source fetch rate limit')")
        rebuild_search(db)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
