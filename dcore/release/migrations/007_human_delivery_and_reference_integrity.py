from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


CARDS = [
    (
        "CORE-022", "core", "delivery_protocol", "Evidence stays backstage; delivery stays outcome-first",
        "Raw retrieval, dossiers and logs are machine evidence, not the user interface.",
        "Deliver requested files first, then one compact evidence table, unresolved boundaries and exact tests. Keep raw JSON, freshness repetition, temporary paths and tool diaries internal unless requested.",
        "Reject answers where internal evidence is larger than the useful artifact, or ordinary script work ends with dCore deployment boilerplate.",
        "The default answer contains no raw route/contract/lint JSON and no repeated blocks.",
        "Version-neutral delivery rule", "core", 100, 1, "dCore 0.30 twelve-test audit",
    ),
    (
        "DEN-027", "denizen", "container_design", "Every executable container earns its boundary",
        "Clean Denizen code uses containers for owned work, not architectural decoration.",
        "Create a task or procedure only for a transaction, lifecycle phase, reusable computation, cleanup or provider boundary. Inline or directly call one-line forwarders. Treat container budgets as ceilings, not targets.",
        "Reject manager/service/helper naming without matching ownership, no-op fixture tasks in production, and splits whose only result is another run/inject.",
        "Lint reports forwarding tasks; review call graph, owners and duplicate work.",
        "Version-neutral architecture; exact calls remain Meta-sensitive", "core", 100, 1, "dCore 0.30 code-shape audit",
    ),
    (
        "DEN-028", "denizen", "access_contract", "Permissions are product policy, not command boilerplate",
        "A generated permission changes who can use a mechanic and therefore needs an explicit requirement.",
        "Add command description, usage, permission and permission message only when the gameplay/access contract requires them. Use plain player-facing wording and test allowed/denied behavior.",
        "Reject automatic feature.use nodes, unused permissions, admin commands hidden behind unexplained policy, and marketing-style descriptions.",
        "Trace each permission to a stated access rule and runtime permission test.",
        "Permission system and server policy sensitive", "core", 100, 1, "dCore 0.30 access-policy audit",
    ),
    (
        "VER-011", "verification", "lint_interface", "Lint is a decision table, not a JSON avalanche",
        "Humans need severity, stable code, location, problem and action; automation needs JSON.",
        "Default to the compact table and totals. Hide provenance-only information unless relevant. Use JSON only for machine processing and keep static/runtime scopes visibly separate.",
        "Reject raw diagnostic arrays in normal delivery, mixed analyzer/source defects, or STATIC_OK presented as gameplay PASS.",
        "Broken and clean fixtures produce readable tables with stable counts and exit codes.",
        "Linter revision sensitive", "core", 100, 1, "dCore 0.30 lint presentation contract",
    ),
    (
        "VER-012", "verification", "verdict_semantics", "Reproduction, static validity and runtime proof are different statuses",
        "Recomputing a decision proves artifact integrity, not that its evidence is true.",
        "Name results by layer: DECISION_REPRODUCED, STATIC_OK/ERROR, RUNTIME_UNVERIFIED/PASS/FAIL. Overall PASS requires all mandatory layers; do not let a local PASS label dominate an INCOMPLETE task.",
        "Reject verify PASS as solution approval, self-authored assertions as runtime evidence, and conflicting headline/body verdicts.",
        "Tampered decisions mismatch; reproduced decisions retain their original proof boundary.",
        "Version-neutral evidence semantics", "core", 100, 1, "dCore 0.30 status audit",
    ),
    (
        "VIS-041", "visual", "reference_integrity", "A final resource pack resolves every custom program and stage",
        "Valid JSON is insufficient when a post pass references a missing program or shader stage.",
        "Resolve namespace-aware legacy and modern post programs, program JSON, vertex/fragment stages, includes, samplers and targets across the final merged pack. Missing custom-namespace dependencies are errors; target-client built-ins remain explicit warnings until version proof.",
        "Reject STATIC_OK with dangling post programs, linting only an overlay when dependencies live upstream, or dismissing unresolved links as runtime-only.",
        "A broken dangling-program fixture fails; the complete merged pack has zero unresolved custom references.",
        "Minecraft pack layout and shader schema sensitive", "high", 100, 1, "dCore 0.30 RP-lint regression test",
    ),
]


CONTRASTS = [
    (
        "CX-DEN-013", "denizen", "Ceremonial forwarding task", "forwarding_task",
        "feature_manager:\n  type: task\n  script:\n  - run feature_owner",
        "on player clicks:\n- run feature_owner",
        "The extra task owns no state, phase, cleanup or reuse.",
        "Every executable container must own a real boundary.",
        "Call graph has no one-line forwarding task.",
    ),
    (
        "CX-DEN-014", "denizen", "Work after terminal determine", "unreachable_after_terminal_command",
        "- determine cancelled\n- run treasure_dig",
        "- run treasure_dig\n- determine cancelled",
        "A non-passive determine terminates the queue before required work.",
        "Required effects precede terminal commands.",
        "Control-flow lint flags only the bad order.",
    ),
    (
        "CX-DEN-015", "denizen", "Generated permission boilerplate", "permission_boilerplate",
        "permission: feature.use # added automatically",
        "# No permission field: the requested mechanic is public",
        "The generated node silently changes the access contract.",
        "Permissions exist only for explicit access policy.",
        "Every permission maps to a requirement and allowed/denied test.",
    ),
    (
        "CX-CORE-001", "core", "Raw evidence replaces delivery", "evidence_dump",
        "Paste retrieval.json, routes.json, contract.json and every tool log after the answer.",
        "Deliver the artifact, one evidence table, unresolved proof and tests.",
        "Internal proof volume hides the result and wastes context.",
        "Evidence is retained without becoming the user interface.",
        "Default response contains no raw machine dump.",
    ),
]


ALIASES = {
    "CORE-022": ["меньше кухни", "не показывай json", "сырых json", "короткий ответ", "raw evidence", "tool diary"],
    "DEN-027": ["лишние таски", "лишних task", "много контейнеров", "forwarding task", "manager service", "чистый код"],
    "DEN-028": ["лишний permission", "permission boilerplate", "не добавляй права", "описание команды"],
    "VER-011": ["lint таблицей", "lint нормальной таблицей", "таблица ошибок", "чек линт", "human lint table"],
    "VER-012": ["verify pass", "decision reproduced", "статус проверки", "runtime unverified"],
    "VIS-041": ["missing shader program", "shader program", "legacy post pass", "post pass program", "dangling shader", "сломанный resource pack", "не хватает glsl"],
}


TESTS = [
    ("AUTO28", "Почини маленький Denizen bug без лишних task и без сырых JSON отчётов", "bugfix", "denizen,verification,core", "", "DEN-027,CORE-022", "", "Proportional clean delivery."),
    ("AUTO29", "Сделай публичную команду и не добавляй permission boilerplate без требования", "new_mechanic", "denizen,core", "", "DEN-028", "", "Access policy."),
    ("AUTO30", "Покажи результат dcore lint нормальной таблицей severity code location problem fix", "diagnose", "verification", "", "VER-011", "", "Human lint interface."),
    ("AUTO31", "Не называй dcore_design verify PASS runtime доказательством", "diagnose", "verification,core", "", "VER-012", "", "Layered verdict semantics."),
    ("AUTO32", "Проверь resource pack: legacy post pass ссылается на отсутствующую shader program", "diagnose", "visual,verification", "", "VIS-041", "", "Reference closure."),
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
        for card_id, terms in ALIASES.items():
            db.execute("INSERT OR REPLACE INTO card_activation_rules(card_id,min_hits) VALUES(?,1)", (card_id,))
            for term in terms:
                db.execute("INSERT OR IGNORE INTO card_terms(card_id,term) VALUES(?,?)", (card_id, term))
                db.execute("INSERT OR IGNORE INTO card_activation_terms(card_id,term) VALUES(?,?)", (card_id, term))
                db.execute("INSERT OR REPLACE INTO card_alias_terms(card_id,term,weight) VALUES(?,?,14)", (card_id, term))
        for item in CONTRASTS:
            db.execute(
                "INSERT OR REPLACE INTO contrast_examples(id,domain,title,diagnostic_code,bad_snippet,good_snippet,bad_reason,invariant,verification) VALUES(?,?,?,?,?,?,?,?,?)",
                item,
            )
            terms = set((item[2] + " " + item[3] + " " + item[6]).lower().replace("_", " ").split())
            for term in terms:
                if len(term) >= 4:
                    db.execute("INSERT OR REPLACE INTO contrast_terms VALUES(?,?,1)", (item[0], term))
        for test in TESTS:
            db.execute("INSERT OR REPLACE INTO retrieval_tests VALUES(?,?,?,?,?,?,?,?)", test)
        for intent, term in (
            ("diagnose", "lint нормальной таблицей"),
            ("diagnose", "verify pass"),
            ("diagnose", "legacy post pass"),
        ):
            db.execute("INSERT OR REPLACE INTO intent_terms(intent,term,weight) VALUES(?,?,30)", (intent, term))
        for link in (
            ("CORE-022", "VER-011", "uses_human_evidence_table", 0),
            ("DEN-027", "CORE-020", "supports_clean_architecture", 0),
            ("DEN-028", "DEN-027", "requires_purposeful_boundary", 0),
            ("VER-012", "CORE-021", "clarifies_decision_status", 0),
            ("VIS-041", "VIS-038", "extends_reference_checks", 1),
        ):
            db.execute("INSERT OR REPLACE INTO card_links VALUES(?,?,?,?)", link)
        db.execute("DELETE FROM card_search")
        db.execute(
            """INSERT INTO card_search(id,title,summary,guidance,terms,domain,kind)
               SELECT c.id,c.title,c.summary,c.guidance,
                      COALESCE((SELECT group_concat(term,' ') FROM card_terms t WHERE t.card_id=c.id),''),
                      c.domain,c.kind FROM cards c"""
        )
        db.execute("INSERT OR REPLACE INTO metadata VALUES('name','dCore 0.30')")
        db.execute("INSERT OR REPLACE INTO metadata VALUES('architecture_revision','human-delivery-reference-integrity-6')")
        db.execute("INSERT OR REPLACE INTO metadata VALUES('delivery_protocol','outcome first; compact evidence table; raw machine artifacts internal')")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
