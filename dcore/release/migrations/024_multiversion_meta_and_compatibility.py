from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


CARDS = (
    (
        "VER-017", "verification", "multi_version", "Historical Meta is target-pinned",
        "A command valid in a current build is not evidence for an older Denizen or DenizenM build.",
        "Store one Meta source snapshot per indexed artifact. Resolve the requested build first and query only its snapshot; an absent snapshot is an explicit proof gap, never permission to use current Meta.",
        "Reject fallback from an old version to current Meta, a version label without source identity, or one shared API list claimed to cover every build.",
        "Query one tag with historical Meta, query a catalogued-but-unindexed artifact, and confirm the second result reports a proof gap.",
        "dCore 0.51 multiversion Meta", "high", 100, 1, "dCore 0.51 target-pinned Meta contract",
    ),
    (
        "ADD-011", "addons", "compatibility", "Addon compatibility is a version matrix",
        "An addon name alone cannot establish support across Minecraft, Paper and its own release line.",
        "Record addon release family, Minecraft/Paper bounds, provider constraints, evidence URL and confidence. Emit advice only when the declared target matches a rule; otherwise require the exact JAR and a focused probe.",
        "Reject guessed ranges such as 'ItemsAdder v3 probably works on 1.20.6', carrying resource-pack output across a Minecraft shader transition, or treating a user report as universal support.",
        "Check one matched rule, one mismatched Minecraft version and one unknown addon release; each must produce a distinct result.",
        "dCore 0.51 compatibility matrix", "high", 100, 1, "dCore 0.51 addon matrix contract",
    ),
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
    parser.add_argument("--db", type=Path, required=True)
    args = parser.parse_args()
    with sqlite3.connect(args.db) as db:
        db.execute("ALTER TABLE meta_sources ADD COLUMN artifact_id TEXT") if "artifact_id" not in {row[1] for row in db.execute("PRAGMA table_info(meta_sources)")} else None
        db.execute("CREATE INDEX IF NOT EXISTS idx_meta_sources_artifact ON meta_sources(artifact_id)")
        db.execute(
            """CREATE TABLE IF NOT EXISTS compatibility_rules(
              rule_id TEXT PRIMARY KEY, subject TEXT NOT NULL, release_family TEXT NOT NULL,
              minecraft_min TEXT, minecraft_max TEXT, paper_min TEXT, paper_max TEXT,
              provider TEXT, status TEXT NOT NULL, confidence TEXT NOT NULL,
              evidence_url TEXT NOT NULL, notes TEXT NOT NULL, updated_at TEXT NOT NULL)"""
        )
        db.execute("CREATE INDEX IF NOT EXISTS idx_compatibility_rules_subject ON compatibility_rules(subject,release_family)")
        db.executemany(
            "INSERT OR REPLACE INTO cards(id,domain,kind,title,summary,guidance,reject_when,verification,version_scope,confidence,priority,token_weight,source_basis) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            CARDS,
        )
        for card_id, terms in {
            "VER-017": ("historical meta", "target pinned meta", "старый denizen", "старая версия denizenm"),
            "ADD-011": ("addon matrix", "itemsadder version", "совместимость itemsadder", "версия аддона"),
        }.items():
            db.execute("INSERT OR REPLACE INTO card_activation_rules(card_id,min_hits) VALUES(?,1)", (card_id,))
            for term in terms:
                db.execute("INSERT OR IGNORE INTO card_terms(card_id,term) VALUES(?,?)", (card_id, term))
                db.execute("INSERT OR IGNORE INTO card_activation_terms(card_id,term) VALUES(?,?)", (card_id, term))
                db.execute("INSERT OR REPLACE INTO card_alias_terms(card_id,term,weight) VALUES(?,?,?)", (card_id, term, 20))
        db.executemany(
            "INSERT OR REPLACE INTO metadata(key,value) VALUES(?,?)",
            (("release.version", "0.51"), ("name", "dCore 0.51"),
             ("meta.multiversion", "historical snapshots are selected by version artifact"),
             ("compatibility.matrix", "addon release + Minecraft/Paper bounds + evidence")),
        )
        rebuild_search(db)


if __name__ == "__main__":
    main()
