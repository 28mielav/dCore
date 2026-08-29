from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


CARDS = [
    (
        "ADD-009", "addons", "provider", "Megizen is a ModelEngine-Denizen adapter",
        "Megizen is a third-party bridge between Denizen and ModelEngine, not a DenizenM core API.",
        "Treat Megizen as one provider boundary. Confirm the installed commit, ModelEngine R4 build and exact docs before using a tag, command, mechanism or event. Keep a vanilla or native ModelEngine fallback outside the adapter; do not scatter guessed Megizen calls through gameplay code.",
        "Reject invented Megizen syntax, treating the GitHub README as proof of every runtime signature, or making the whole mechanic depend on an unverified addon.",
        "Verify the exact jar/build in a minimal runtime fixture, then lint the adapter and test spawn, animation, viewer scope and cleanup.",
        "Paper 1.21+; exact addon build required", "high", 95, 1, "https://github.com/0tickpulse/Megizen; https://0tickpulse.github.io/megizen-docs/",
    ),
    (
        "PHYS-001", "physics", "preview", "Denizen-Physics is preview-only until its API is published",
        "The supplied announcement describes a Jolt Physics integration with rigid bodies, joints and raycasts, but no indexed source, jar, wiki or Meta is available yet.",
        "Use the announcement only to compare architecture routes: rigid-body state, display pivot, bounded raycast and one physics owner. Mark every command or mechanism INCOMPLETE until an exact repository commit, jar, Paper matrix and runtime Meta are available. Do not promise 60 Hz, zero TPS cost or benchmark claims from marketing text.",
        "Reject guessed Denizen-Physics commands, copied Jolt signatures, performance guarantees and production code that silently requires a not-yet-released plugin.",
        "Require the official source/download, exact build, documented Denizen bridge and a runtime fixture before moving this card from preview to verified.",
        "Paper 1.21+ announcement only; review_pending", "medium", 80, 1, "user-supplied Denizen-Physics announcement; no verified source indexed",
    ),
]


ALIASES = {
    "ADD-009": ["megizen", "megizen docs", "modelengine denizen", "denizen modelengine bridge", "megizen animation"],
    "PHYS-001": ["denizen physics", "jolt physics", "rigidbody denizen", "physics plugin", "physics preview", "denizen-physics"],
}


CONTRASTS = [
    (
        "CX-ADD-003", "addons", "Megizen adapter versus invented bridge", "addon_api_guess",
        "Use megizen_spawn_model and megizen_animation; it probably works on every build.",
        "Megizen is a separate provider. Pin the installed build, query its exact docs/runtime surface, and keep one adapter with a fallback.",
        "A plausible command name is not an API contract and makes failures look like gameplay bugs.",
        "Native or addon routes must be version-bounded and isolated.",
        "The adapter has an exact source/build witness and a runtime fixture.",
    ),
    (
        "CX-PHYS-001", "physics", "Physics preview claim versus verified API", "physics_preview_claim",
        "Denizen-Physics runs at 60 Hz with zero TPS impact, so write the vehicle script now.",
        "The announcement is a route hypothesis. Without a jar, source and Meta, define the rigid-body contract only and mark implementation INCOMPLETE.",
        "Marketing claims do not prove a plugin build, thread safety, bridge syntax or server behavior.",
        "Unverified provider features cannot become hidden production dependencies.",
        "A source commit, exact jar and runtime test move the route out of preview.",
    ),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path("dcore/knowledge/data/dcore.sqlite"))
    args = parser.parse_args()
    with sqlite3.connect(args.db) as db:
        db.execute("PRAGMA foreign_keys=ON")
        db.execute(
            "INSERT OR IGNORE INTO domains(key,purpose,load_when,do_not_load_when,default_limit) VALUES(?,?,?,?,?)",
            ("physics", "Preview physics providers, rigid bodies, joints and collision routes.", "User names a physics plugin, rigid body, joint, raycast or simulation.", "Do not preload for ordinary Denizen events.", 4),
        )
        for card in CARDS:
            db.execute(
                "INSERT OR REPLACE INTO cards(id,domain,kind,title,summary,guidance,reject_when,verification,version_scope,confidence,priority,token_weight,source_basis) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                card,
            )
        for card_id, terms in ALIASES.items():
            db.execute("INSERT OR REPLACE INTO card_activation_rules(card_id,min_hits) VALUES(?,1)", (card_id,))
            for term in terms:
                db.execute("INSERT OR IGNORE INTO card_terms(card_id,term) VALUES(?,?)", (card_id, term))
                db.execute("INSERT OR IGNORE INTO card_activation_terms(card_id,term) VALUES(?,?)", (card_id, term))
                db.execute("INSERT OR REPLACE INTO card_alias_terms(card_id,term,weight) VALUES(?,?,?)", (card_id, term, 20))
        for item in CONTRASTS:
            db.execute(
                "INSERT OR REPLACE INTO contrast_examples(id,domain,title,diagnostic_code,bad_snippet,good_snippet,bad_reason,invariant,verification) VALUES(?,?,?,?,?,?,?,?,?)",
                item,
            )
            for term in set((item[2] + " " + item[3] + " " + item[6]).lower().replace("_", " ").split()):
                if len(term) >= 4:
                    db.execute("INSERT OR REPLACE INTO contrast_terms VALUES(?,?,1)", (item[0], term))
        db.execute("INSERT OR REPLACE INTO metadata VALUES('megizen_policy','third-party adapter; exact build and runtime API required; no guessed calls')")
        db.execute("INSERT OR REPLACE INTO metadata VALUES('denizen_physics_policy','preview only; supplied announcement is not source or Meta; no performance claims')")
        db.execute("INSERT OR REPLACE INTO metadata VALUES('tone_policy','direct lowercase human Russian; no emoji; rare bounded playful jab only after catastrophic code failure; explain defect and next step')")
        db.execute(
            """UPDATE cards SET guidance=?, reject_when=?, verification=? WHERE id='TEACH-005'""",
            (
                "Use mostly lowercase natural Russian chat with short sentences. If a first attempt has a real merit, name it once, then attack the code precisely: what is broken, why it matters and the next test. A rare playful personal jab is allowed only for an obvious catastrophe, one short phrase, never identity-based; it cannot replace the technical explanation.",
                "Reject empty praise, emoji, constant profanity, childish jokes, AI catchphrases, harassment and insults that replace a defect, reason or fix.",
                "The response contains a warranted merit or no praise, a precise defect, impact, next action and no emoji.",
            ),
        )
        tests = [
            ("AUTO40", "Megizen ModelEngine Denizen animation: verify the addon boundary and do not invent the command", "new_mechanic", "addons,visual,denizen", "", "ADD-009", "", "Addon route must be version-bounded."),
            ("AUTO41", "Denizen-Physics Jolt rigidbody plugin has no wiki or jar yet: compare a preview route without claiming an API", "new_mechanic", "physics,verification", "", "PHYS-001", "", "Preview source is not runtime proof."),
        ]
        for test in tests:
            db.execute("INSERT OR REPLACE INTO retrieval_tests VALUES(?,?,?,?,?,?,?,?)", test)
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
