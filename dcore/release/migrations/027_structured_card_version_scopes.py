from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


CARD = (
    "VER-018", "verification", "multi_version", "Card advice must be executable against a target",
    "Free-text version notes cannot stop an incompatible recommendation from reaching a user.",
    "Every card has one structured scope: invariant, Minecraft target, Denizen target, addon target or target matrix. Retrieval returns applicability separately from card text and defers advice whose required target is absent.",
    "Reject a card that only says 'version-sensitive' without machine-readable requirements, or advice presented as applicable when its target fields are missing.",
    "Retrieve a visual card with and without Minecraft, a Denizen card with and without a pinned build, and an addon card with and without addon@version.",
    "dCore 0.52 structured card scopes", "high", 100, 1, "dCore 0.52 routing contract",
)


def scope_for(domain: str, kind: str, title: str, version_scope: str) -> tuple[str, str, str, str]:
    text = " ".join((domain, kind, title, version_scope)).casefold()
    if "version-neutral" in text or version_scope.casefold() == "all builds":
        return ("invariant", "", "", "Architecture or algorithm rule is independent of a specific build.")
    if domain == "visual":
        return ("minecraft_target", "Minecraft", "", "Shader/resource-pack advice needs an exact client target.")
    if domain == "addons":
        addon = "reflect" if "reflect" in text else ("voxizen" if "voxizen" in text else "")
        return ("addon_target", "", addon, "Addon advice needs addon@version and Minecraft/Paper compatibility evidence.")
    if domain == "denizen":
        return ("denizen_target", "Denizen", "", "Syntax/API advice needs a pinned Denizen or DenizenM build.")
    if kind == "multi_version" or domain == "verification":
        return ("target_matrix", "", "", "Advice resolves against the declared target matrix before use.")
    return ("invariant", "", "", "General engineering rule remains applicable across supported builds.")


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
        db.execute(
            """CREATE TABLE IF NOT EXISTS card_version_scopes(
              card_id TEXT PRIMARY KEY REFERENCES cards(id) ON DELETE CASCADE,
              scope_type TEXT NOT NULL CHECK(scope_type IN ('invariant','minecraft_target','denizen_target','addon_target','target_matrix')),
              product TEXT NOT NULL DEFAULT '', addon TEXT NOT NULL DEFAULT '',
              rationale TEXT NOT NULL)"""
        )
        db.execute("INSERT OR REPLACE INTO cards(id,domain,kind,title,summary,guidance,reject_when,verification,version_scope,confidence,priority,token_weight,source_basis) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", CARD)
        db.execute("INSERT OR REPLACE INTO card_activation_rules(card_id,min_hits) VALUES('VER-018',1)")
        for term in ("card scope", "version-aware card", "карточки версии", "мультиверсионные советы"):
            db.execute("INSERT OR IGNORE INTO card_terms(card_id,term) VALUES('VER-018',?)", (term,))
            db.execute("INSERT OR IGNORE INTO card_activation_terms(card_id,term) VALUES('VER-018',?)", (term,))
            db.execute("INSERT OR REPLACE INTO card_alias_terms(card_id,term,weight) VALUES('VER-018',?,20)", (term,))
        db.execute("DELETE FROM card_version_scopes")
        for card_id, domain, kind, title, version_scope in db.execute(
            "SELECT id,domain,kind,title,version_scope FROM cards ORDER BY id"
        ):
            db.execute(
                "INSERT INTO card_version_scopes(card_id,scope_type,product,addon,rationale) VALUES(?,?,?,?,?)",
                (card_id, *scope_for(domain, kind, title, version_scope)),
            )
        db.executemany(
            "INSERT OR REPLACE INTO metadata(key,value) VALUES(?,?)",
            (("release.version", "0.52"), ("name", "dCore 0.52"),
             ("cards.version_scopes", "all cards have one structured executable scope")),
        )
        rebuild_search(db)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
