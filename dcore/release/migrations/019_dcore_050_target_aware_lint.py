from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


CARDS = (
    (
        "CORE-027", "core", "verification", "Seven-step implementation gate",
        "A useful Skill must turn a request into a repeatable evidence-backed execution, not a plausible answer.",
        "Inspect the project, resolve the exact target, retrieve matching evidence, design the smallest shape, implement the requested scope, run the complete verification gates, and report static facts separately from runtime proof.",
        "Reject skipping target resolution, calling lint runtime proof, teaching instead of implementing an explicit change request, or publishing a bundle with stale artifacts.",
        "Run the seven gates on a small Denizen change and confirm each result is machine-readable and blocking dependencies stop later gates.",
        "dCore 0.50 execution policy", "high", 100, 1, "dCore 0.50 release contract",
    ),
    (
        "VER-015", "verification", "multi_version", "Resolve one exact target matrix",
        "Denizen, Paper and addon facts cannot be safely combined from unrelated builds.",
        "Resolve Minecraft, Paper, Java, Denizen or DenizenM, addon versions and exact JARs before selecting syntax. Inherit unchanged facts only through an explicit version graph.",
        "Reject an unqualified 'latest' API, an addon name without a declared target when exact proof is required, or a Meta fact copied across incompatible products.",
        "Run lint with versioned addon flags and require JAR evidence; verify the report names the selected target and rejects a missing artifact.",
        "dCore target-aware lint", "high", 100, 1, "dCore 0.50 version-aware lint contract",
    ),
    (
        "ADD-010", "addons", "reflect", "Reflect shape is not Java proof",
        "Reflect syntax can be structurally valid while the class, overload, type or null behavior is wrong on the installed build.",
        "Lint the invoke dialect and addon declaration, then require exact JAR signature evidence for class, method, overload, return type and thread contract. Keep Reflect in one adapter after native capability search.",
        "Reject blanket ignoring Reflect, scattered provider calls, guessed overloads or a runtime PASS derived only from Meta.",
        "Run malformed, balanced, missing-addon and exact-JAR fixtures; then use one focused server probe for the selected signature.",
        "denizen-reflect Meta plus dCore runtime failures", "high", 100, 1, "dCore Reflect boundary",
    ),
    (
        "VER-016", "verification", "artifact", "Release only from a verified manifest",
        "A changed instruction, Skill or tool with an old manifest creates a self-contradictory release.",
        "Regenerate the manifest from the actual canonical artifacts, run integrity, foreign-key, retrieval, unit and build checks, and refuse GPT/Skill output when hashes do not match.",
        "Reject hand-edited hashes, a verified label with recorded failures, or a bundle built from generated output instead of repository source.",
        "Tamper with one artifact and confirm build rejection, then regenerate a 0.50 manifest and build both independent products.",
        "dCore build_common and verify_knowledge", "high", 100, 1, "dCore 0.50 release gate",
    ),
    (
        "CORE-028", "core", "delivery", "$dCore identity and lowercase Russian delivery",
        "A specialized Skill is easier to trigger and safer to use when its identity and delivery behavior are stable.",
        "Expose the Skill as `$dCore` in UI metadata, keep the filesystem name valid for Codex, use lowercase Russian prose outside code, and preserve normal case for API names, paths and acronyms.",
        "Reject the old generic engineer display name, uppercase AI boilerplate, emoji, or a teaching response when an explicit build/fix request requires implementation.",
        "Validate frontmatter and agents metadata, then snapshot representative response instructions and build the Skill bundle.",
        "dCore 0.50 Skill policy", "high", 100, 1, "dCore 0.50 Skill identity contract",
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
    parser.add_argument("--db", type=Path, default=Path("dcore/knowledge/data/dcore.sqlite"))
    args = parser.parse_args()
    with sqlite3.connect(args.db) as db:
        db.executemany(
            "INSERT OR REPLACE INTO cards(id,domain,kind,title,summary,guidance,reject_when,verification,version_scope,confidence,priority,token_weight,source_basis) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            CARDS,
        )
        aliases = {
            "CORE-027": ("seven gates", "implementation gate", "реализуй полностью", "сделай релиз"),
            "VER-015": ("target matrix", "multi version", "мультиверсия", "точная версия"),
            "ADD-010": ("reflect shape", "reflect signature", "reflect overload", "рефлект сигнатура"),
            "VER-016": ("verified manifest", "release gate", "manifest mismatch", "релиз skill gpt"),
            "CORE-028": ("$dCore", "lowercase russian", "маленькая буква", "название skill"),
        }
        for card_id, terms in aliases.items():
            db.execute("INSERT OR REPLACE INTO card_activation_rules(card_id,min_hits) VALUES(?,1)", (card_id,))
            for term in terms:
                db.execute("INSERT OR IGNORE INTO card_terms(card_id,term) VALUES(?,?)", (card_id, term))
                db.execute("INSERT OR IGNORE INTO card_activation_terms(card_id,term) VALUES(?,?)", (card_id, term))
                db.execute("INSERT OR REPLACE INTO card_alias_terms(card_id,term,weight) VALUES(?,?,?)", (card_id, term, 20))
        db.execute("INSERT OR REPLACE INTO metadata VALUES('release.version','0.50')")
        db.execute("INSERT OR REPLACE INTO metadata VALUES('metadata_name','dCore 0.50')")
        db.execute("INSERT OR REPLACE INTO metadata VALUES('skill.identity','$dCore')")
        db.execute("INSERT OR REPLACE INTO metadata VALUES('lint.target_aware','versioned CLI target and addon/JAR evidence')")
        db.execute("INSERT OR REPLACE INTO metadata VALUES('lint.reflect_gate','shape checked; Java signature requires exact artifact evidence')")
        rebuild_search(db)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
