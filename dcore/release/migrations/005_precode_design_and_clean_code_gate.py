from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


CARDS = [
    (
        "CORE-019", "core", "design_gate",
        "Usage topology is fixed before implementation",
        "Non-trivial code starts from expected use, ownership and failure topology, not from a guessed list of containers.",
        "Before code, record expected online players and concurrent instances, trigger frequency, active versus dormant population, authoritative state owners and writers, synchronous/concurrent inputs, persistence and reload semantics, failure cleanup, installed providers and likely change axes. Convert that into explicit hot-path and code-shape budgets. Then choose the smallest architecture that satisfies the contract. Recalculate when evidence changes; do not preserve an architecture that was sized for a different workload.",
        "Reject code-first implementation, unbounded 'we may need it later' infrastructure, or a design with no stated scale, lifecycle and failure behavior.",
        "The behavior contract contains a complete design section before implementation. Compare the delivered containers, entry points, writers and hot paths with its declared budgets.",
        "Version-neutral engineering gate", "core", 100, 1,
        "Treasure rewrite expanded before expected use and event topology were fixed",
    ),
    (
        "CORE-020", "core", "clean_architecture",
        "Enterprise code without ceremonial architecture",
        "Clean enterprise Denizen code means predictable ownership, narrow entry points and stable boundaries; it does not mean more managers, registries or forwarding tasks.",
        "Keep world events as identity validation plus dispatch. Put guard clauses before mutations and keep the normal path flat. Use choose for exclusive modes and config maps only when branches differ by data. Split code at lifecycle, ownership, transaction or volatile-provider boundaries; never split a cohesive operation into one-line forwarding tasks. One orchestrator may coordinate phases, one owner performs idempotent cleanup and one adapter isolates each optional provider. Give abstractions a demonstrated second consumer, removed duplication or isolated volatility. Prefer explicit names, one state read/commit path and comments that explain invariants rather than narrating commands.",
        "Reject if/else pyramids, monolithic event handlers, duplicated writers, generic manager/factory/registry layers, magic recovery frameworks and abstraction introduced only to look enterprise.",
        "Review handler size, control nesting, branch density, event blast radius, duplicated command shapes, state writers and provider boundaries. Every extra container states the responsibility it uniquely owns.",
        "Version-neutral architecture; exact Denizen constructs are build-sensitive", "core", 100, 1,
        "Treasure dog script reached thousands of lines through branch-heavy handlers and mixed responsibilities",
    ),
    (
        "VER-009", "verification", "maintainability_gate",
        "Maintainability budgets are executable review evidence",
        "Static review must expose oversized handlers, deep nesting and branch density instead of reporting syntax-only green.",
        "Treat more than 35 commands in an event or 55 in a task/procedure as a design suggestion, and more than 60 or 90 respectively as a warning. Four nested control levels trigger review; six are a warning. Dense branch ladders require choose, data-driven variation or phase separation when semantics permit. These thresholds are not automatic proof of bad behavior: a warning may be retained only with a concrete cohesion and ownership explanation. Never silence addon syntax or valid guard clauses to make metrics green.",
        "Reject a clean-code claim based only on zero syntax errors, raw line count or renamed containers.",
        "Run dcore_lint with the exact profile/addons, inspect maintainability diagnostics, document justified warnings, then run runtime regression tests for behavior and performance.",
        "Linter revision sensitive; gameplay remains runtime evidence", "core", 100, 1,
        "Previous lint missed 319-command tasks and 126-command global handlers",
    ),
]


ALIASES = {
    "CORE-019": [
        "сначала продумай использование", "сначала рассчитай нагрузку", "сколько игроков",
        "сколько активных сессий", "usage topology", "до написания кода", "pre-code design",
        "планируемое использование",
    ],
    "CORE-020": [
        "чистый enterprise код", "чистый код", "if else каша", "if/else каша",
        "без менеджеров ради менеджеров", "не раздувай архитектуру", "guard clauses",
        "монолитный обработчик", "человеческий код",
    ],
    "VER-009": [
        "проверка чистоты кода", "размер обработчика", "глубина вложенности",
        "branch density", "слишком много if", "maintainability lint", "code shape budget",
    ],
}


TESTS = [
    (
        "AUTO11", "Перепиши собак чистым enterprise кодом: сначала продумай планируемое использование, не делай if else кашу и глобальные слушатели",
        "refactor", "core,verification", "", "CORE-019,CORE-020,VER-009,DEN-025", "", "Clean architecture and blast radius.",
    ),
    (
        "AUTO12", "Сделай production файл для 100 игроков и 20 активных сессий, сначала рассчитай нагрузку и lifecycle",
        "full_file", "core", "", "CORE-019,CORE-020", "", "Scale before code.",
    ),
    (
        "AUTO13", "Рефактор без manager factory registry ради вида: нужны guard clauses, один owner и человеческий код",
        "refactor", "core", "", "CORE-020", "", "Enterprise without ceremony.",
    ),
    (
        "AUTO14", "Полный аудит чистоты: найди слишком большие handlers, глубокую вложенность и branch density",
        "full_audit", "verification", "", "VER-009", "", "Maintainability evidence.",
    ),
    (
        "AUTO15", "Новая механика: до написания кода определи сколько активных сессий, hot path, concurrency, reload и cleanup",
        "new_mechanic", "core", "", "CORE-019", "", "Pre-code design dossier.",
    ),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path("dcore/knowledge/data/dcore.sqlite"))
    args = parser.parse_args()
    with sqlite3.connect(args.db) as db:
        db.execute("PRAGMA foreign_keys=ON")
        for card in CARDS:
            db.execute(
                "INSERT OR REPLACE INTO cards(id,domain,kind,title,summary,guidance,reject_when,verification,version_scope,confidence,priority,token_weight,source_basis) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                card,
            )

        db.execute(
            "UPDATE cards SET guidance=?, reject_when=?, verification=? WHERE id='CORE-003'",
            (
                "Before containers, budget expected players and concurrent instances, trigger frequency, persistent facts, long-lived queues, active updates, event handlers, mutation writers, external calls and failure paths. Include a code-shape budget. The budget is a warning boundary, not a target to fill.",
                "Reject a route that has no usage assumptions or exceeds the simplest complete behavior without explaining every extra owner.",
                "Compare the final artifact and lint metrics with the pre-code budget; explain every material delta.",
            ),
        )
        db.execute(
            "UPDATE cards SET guidance=?, reject_when=?, verification=? WHERE id='CORE-007'",
            (
                "Before presenting code, flatten ownership guards, inspect handler size and nesting, remove repeated command shapes, tag chains, guards, writers, constant branches and forwarding tasks. Use choose for exclusive modes and data maps for value-only variation. Compress only identical semantics.",
                "Do not emit a branch-heavy first draft and promise cleanup later; do not hide the same complexity behind ceremonial abstractions.",
                "Run the maintainability lint gate and re-read each retained warning against the declared ownership and code-shape budget.",
            ),
        )

        for card_id, terms in ALIASES.items():
            db.execute("INSERT OR REPLACE INTO card_activation_rules(card_id,min_hits) VALUES(?,1)", (card_id,))
            for term in terms:
                db.execute("INSERT OR IGNORE INTO card_terms(card_id,term) VALUES(?,?)", (card_id, term))
                db.execute("INSERT OR IGNORE INTO card_activation_terms(card_id,term) VALUES(?,?)", (card_id, term))
                db.execute("INSERT OR REPLACE INTO card_alias_terms(card_id,term,weight) VALUES(?,?,14)", (card_id, term))
        for term in ("глобальные слушатели", "глобальн* слушател*"):
            db.execute("INSERT OR IGNORE INTO card_terms(card_id,term) VALUES('DEN-025',?)", (term,))
            db.execute("INSERT OR IGNORE INTO card_activation_terms(card_id,term) VALUES('DEN-025',?)", (term,))
            db.execute("INSERT OR REPLACE INTO card_alias_terms(card_id,term,weight) VALUES('DEN-025',?,14)", (term,))

        for intent, term, weight in (
            ("refactor", "перепиши", 10),
            ("full_file", "production файл", 12),
            ("new_mechanic", "новая механика", 12),
        ):
            db.execute("INSERT OR REPLACE INTO intent_terms(intent,term,weight) VALUES(?,?,?)", (intent, term, weight))

        for term in (
            "чистый код", "enterprise код", "if else каша", "usage topology",
            "guard clauses", "планируемое использование", "code shape budget",
        ):
            db.execute("INSERT OR IGNORE INTO domain_terms(domain,term) VALUES('core',?)", (term,))
        for term in ("maintainability lint", "размер обработчика", "глубина вложенности", "branch density"):
            db.execute("INSERT OR IGNORE INTO domain_terms(domain,term) VALUES('verification',?)", (term,))

        design_intents = ("bugfix", "refactor", "new_mechanic", "visual_design", "full_file")
        for intent in design_intents:
            db.execute("INSERT OR REPLACE INTO route_pins(intent,card_id,position) VALUES(?,?,81)", (intent, "CORE-020"))
        for intent in ("refactor", "full_audit", "full_file", "performance_review"):
            db.execute("INSERT OR REPLACE INTO route_pins(intent,card_id,position) VALUES(?,?,82)", (intent, "VER-009"))

        links = [
            ("CORE-019", "CORE-003", "supports_budget", 0),
            ("CORE-019", "CORE-002", "supports_owner", 0),
            ("CORE-020", "CORE-019", "requires_design", 1),
            ("CORE-020", "CORE-007", "supports_clean_output", 0),
            ("VER-009", "CORE-020", "requires_architecture", 1),
            ("VER-009", "VER-008", "supports_evidence_ladder", 0),
        ]
        for link in links:
            db.execute("INSERT OR REPLACE INTO card_links(from_id,to_id,relation,mandatory) VALUES(?,?,?,?)", link)

        for test in TESTS:
            db.execute(
                "INSERT OR REPLACE INTO retrieval_tests(id,query,intent,expected_domains,forbidden_domains,expected_cards,forbidden_cards,notes) VALUES(?,?,?,?,?,?,?,?)",
                test,
            )

        db.execute("DELETE FROM card_search")
        db.execute(
            """INSERT INTO card_search(id,title,summary,guidance,terms,domain,kind)
               SELECT c.id,c.title,c.summary,c.guidance,
                      COALESCE((SELECT group_concat(term,' ') FROM card_terms t WHERE t.card_id=c.id),''),
                      c.domain,c.kind
               FROM cards c"""
        )
        db.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('name','dCore 0.28')")
        db.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('architecture_revision','precode-design-and-maintainability-gate-4')")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
