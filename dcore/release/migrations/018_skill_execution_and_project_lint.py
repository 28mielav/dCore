from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


CARDS = (
    (
        "CORE-025", "core", "delivery", "Select teaching, diagnosis, or implementation mode from the request",
        "A progressive lesson and a production change are different contracts. Applying the lesson gate to a requested fix withholds the result; applying one-shot generation to teaching removes the learning boundary.",
        "For explain, teach, and review requests, use a bounded fragment and require reasoning. For diagnosis, identify and prove the cause without silently editing. For change, fix, build, and refactor requests, inspect the real project, implement the complete requested scope, lint it, and hand off runtime tests.",
        "Reject forcing every request into a 35-line exercise, dumping a complete project during teaching, or claiming implementation after returning only a plan.",
        "Test one teaching prompt, one read-only diagnosis, and one explicit fix request. The fix path must produce the complete in-scope edit and verification evidence.",
        "Version-neutral Codex Skill execution policy", "high", 100, 1, "dCore Skill execution contract",
    ),
    (
        "CORE-026", "core", "architecture", "Represent lifecycle phases explicitly without flattening them into branch ladders",
        "A session that mixes navigation, recovery, arrival, presentation, cleanup, and persistence in one branch-dense queue becomes an accidental state machine with hidden transitions.",
        "Name the small set of real phases and their legal transitions. Keep one session owner and one cleanup owner. Extract a task only for a cohesive transaction, lifecycle phase, reusable computation, or volatile provider boundary. Use data maps for value variation; do not create forwarding tasks to game line-count metrics.",
        "Reject long if/else ladders that encode phase, mirrored cleanup, ceremonial manager/helper containers, and splitting each branch into a one-line task.",
        "Trace every phase transition and terminal path, prove one movement/state writer per phase, and lint branch density, nesting, duplicate writes, and unreachable cleanup.",
        "Version-neutral lifecycle architecture", "high", 100, 1, "dCore clean production code contract",
    ),
    (
        "DEN-031", "denizen", "events", "Disambiguate overlapping Denizen ScriptEvents with documented switches",
        "A matcher can be syntactically plausible yet match more than one ScriptEvent. Damage matchers may overlap entity and vehicle events, producing reload warnings and ambiguous contexts.",
        "Resolve the matcher against the exact selected Meta. When entity and vehicle damage events overlap, add the documented `type:<entity matcher>` switch and keep the first executable identity guard before mutation or cancellation. Do not silence the warning by broadening the listener or changing to a console workaround.",
        "Reject accepting a multiple-ScriptEvent warning, guessing contexts from the similar event, or treating a global listener as free because it has a late guard.",
        "Lint the exact matcher, run `/ex reload`, confirm one registration without overlap, then test target and non-target entities plus cancellation side effects.",
        "Denizen/DenizenM event-Meta sensitive", "high", 100, 1, "DenizenM event Meta and observed reload warning",
    ),
    (
        "VER-014", "verification", "static_analysis", "Lint the complete project artifact, not a representative file",
        "Reference closure, duplicate containers, shared state, and cross-file event ownership cannot be validated when only one script is linted.",
        "Pass the project directory or every `.dsc` file to dcore_lint. Directory input recursively expands `.dsc` files, deduplicates explicit overlaps, and evaluates references against one closed-world script set. Use partial mode only when external owners are explicitly named.",
        "Reject claiming whole-project lint from one file, silently ignoring directory input, or using closed-world errors for known external scripts without declaring them.",
        "A nested directory fixture discovers all `.dsc` files, ignores other extensions, deduplicates overlaps, and fails when no scripts are present.",
        "dCore linter 0.31+", "high", 100, 1, "dCore executable regression tests",
    ),
)


CONTRASTS = (
    (
        "CX-DEN-018", "denizen", "Ambiguous damage matcher", "ambiguous_event_matcher",
        "on entity_flagged:treasure_role damaged:",
        "on entity_flagged:treasure_role damaged type:slime:",
        "The first matcher overlaps entity and vehicle damage ScriptEvents on the indexed DenizenM Meta.",
        "An event has one intended ScriptEvent contract and documented context set.",
        "Lint reports no overlap and `/ex reload` registers the intended handler once.",
    ),
    (
        "CX-CORE-018", "core", "Line-count refactor without responsibility", "flattened_state_machine",
        "One queue owns tracking, path recovery, teleport policy, discovery, particles, rewards and every cleanup branch.",
        "One session coordinates explicit phases; cohesive calculations and provider boundaries are separate; one cleanup releases acquired resources.",
        "A smaller file can still contain a branch-dense accidental state machine and multiple competing writers.",
        "Container boundaries follow ownership and phase, not arbitrary line limits.",
        "Phase transition tests and lint show bounded branches, one writer and one cleanup path.",
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
        terms = {
            "CORE-025": ("implement the fix", "fix this project", "полностью почини", "внеси изменения", "build mode", "teaching mode"),
            "CORE-026": ("state machine", "if else ladder", "branch ladder", "машина состояний", "лестница if", "чистая архитектура"),
            "DEN-031": ("matched to multiple scriptevents", "multiple scriptevents", "entity damaged", "vehicle damaged", "type:slime", "неоднозначное событие"),
            "VER-014": ("lint directory", "lint project", "whole project lint", "проверить весь проект", "каталог dsc", "closed world"),
        }
        for card_id, aliases in terms.items():
            db.execute("INSERT OR REPLACE INTO card_activation_rules(card_id,min_hits) VALUES(?,1)", (card_id,))
            for term in aliases:
                db.execute("INSERT OR IGNORE INTO card_terms(card_id,term) VALUES(?,?)", (card_id, term))
                db.execute("INSERT OR IGNORE INTO card_activation_terms(card_id,term) VALUES(?,?)", (card_id, term))
                db.execute("INSERT OR REPLACE INTO card_alias_terms(card_id,term,weight) VALUES(?,?,?)", (card_id, term, 18))
        db.executemany(
            "INSERT OR REPLACE INTO contrast_examples(id,domain,title,diagnostic_code,bad_snippet,good_snippet,bad_reason,invariant,verification) VALUES(?,?,?,?,?,?,?,?,?)",
            CONTRASTS,
        )
        for contrast_id, aliases in {
            "CX-DEN-018": ("damaged", "multiple scriptevents", "type:slime"),
            "CX-CORE-018": ("if else ladder", "state machine", "branch dense"),
        }.items():
            for term in aliases:
                db.execute("INSERT OR REPLACE INTO contrast_terms VALUES(?,?,1)", (contrast_id, term))
        for card_id in ("CORE-025", "CORE-026", "DEN-031", "VER-014"):
            db.execute("DELETE FROM route_pins WHERE card_id=?", (card_id,))
        pins = {
            "CORE-025": ("full_file",),
            "CORE-026": ("refactor",),
            "VER-014": ("full_audit", "full_file"),
        }
        for card_id, intents in pins.items():
            for position, intent in enumerate(intents, 70):
                db.execute("INSERT OR REPLACE INTO route_pins(intent,card_id,position) VALUES(?,?,?)", (intent, card_id, position))
        tests = (
            ("AUTO43", "Полностью почини проект и внеси изменения, не оставляй мне только учебный фрагмент", "bugfix", "core,denizen,verification", "", "CORE-025", "", "Implementation mode must complete the requested edit."),
            ("AUTO44", "Перепиши branch-dense очередь собак как чистую машину состояний без manager и helper мусора", "refactor", "core,verification", "", "CORE-026", "", "Lifecycle phases instead of an if ladder."),
            ("AUTO45", "reload пишет matched to multiple ScriptEvents для entity_flagged damaged, найди точную причину", "diagnose", "denizen,verification", "", "DEN-031", "", "Damage event overlap."),
            ("AUTO46", "Проведи lint всего каталога scripts рекурсивно и проверь cross-file references", "full_audit", "verification,denizen,core", "", "VER-014", "", "Project directory lint."),
        )
        db.executemany("INSERT OR REPLACE INTO retrieval_tests VALUES(?,?,?,?,?,?,?,?)", tests)
        for intent, term, weight in (
            ("diagnose", "matched to multiple scriptevents", 30),
            ("diagnose", "точную причину", 12),
            ("full_audit", "всего каталога", 30),
            ("full_audit", "cross-file", 20),
        ):
            db.execute("INSERT OR REPLACE INTO intent_terms(intent,term,weight) VALUES(?,?,?)", (intent, term, weight))
        db.execute("INSERT OR REPLACE INTO metadata VALUES('skill.execution_policy','request-selected teach, diagnose, or complete implementation')")
        db.execute("INSERT OR REPLACE INTO metadata VALUES('lint.project_directory','recursive .dsc expansion with deduplication')")
        rebuild_search(db)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
