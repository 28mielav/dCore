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
            """UPDATE cards SET title=?,summary=?,guidance=?,reject_when=?,verification=?,version_scope=?,confidence=?,source_basis=? WHERE id='PHYS-001'""",
            (
                "Denizen-Physics alpha has a public command surface",
                "Denizen-Physics 1.0.0-alpha.3 is publicly listed and documents rigid bodies, vehicles, terrain collision and Denizen commands. The page describes libbulletjme, not the earlier Jolt announcement.",
                "Use the published command names only as a source-backed route hypothesis: `physicsbody spawn`, `physicsvehicle spawn`, `addwheel`, `drive` and `remove`. Pin the alpha version and test the installed jar before relying on exact arguments, thread behavior, collision snapshots, display interpolation or 1.21 compatibility. Keep a vanilla fallback and do not repeat Jolt or zero-TPS claims unless a primary source confirms them.",
                "Reject guessed mechanisms, treating the alpha description as runtime proof, or silently making production code require an unstable physics plugin.",
                "Verify the exact jar on the target Paper build, query any published Denizen bridge surface, then run spawn, transform, collision, cleanup and reload fixtures.",
                "1.0.0-alpha.3; tested list includes 1.21, 26.1 and 26.2; runtime unverified",
                "medium",
                "https://www.spigotmc.org/resources/denizen-physics.137230/",
            ),
        )
        for term in ("physicsbody spawn", "physicsvehicle spawn", "libbulletjme", "denizen physics alpha", "physics addwheel", "physics drive"):
            db.execute("INSERT OR IGNORE INTO card_terms(card_id,term) VALUES(?,?)", ("PHYS-001", term))
            db.execute("INSERT OR IGNORE INTO card_activation_terms(card_id,term) VALUES(?,?)", ("PHYS-001", term))
            db.execute("INSERT OR REPLACE INTO card_alias_terms(card_id,term,weight) VALUES(?,?,?)", ("PHYS-001", term, 20))
        db.execute("INSERT OR REPLACE INTO metadata VALUES('denizen_physics_policy','public alpha surface indexed; exact jar/runtime still required; libbulletjme claim is source-backed, Jolt claim is not')")
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
