from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


CARDS = [
    (
        "CORE-023", "core", "delivery_protocol", "One response teaches one next move",
        "A useful answer leaves the user able to perform and explain the next change.",
        "For non-trivial work, state the invariant, give one small task or fragment, ask for the result, then review it. Reveal the next fragment only after the previous boundary is understood or verified.",
        "Reject a full solution dump, a chain of fragments that reconstructs the whole file, or an answer that removes the user's need to reason.",
        "The response has a named next action, a checkable result and no unnecessary full-file artifact.",
        "Version-neutral teaching and delivery rule", "core", 100, 1, "dCore 0.31 teaching progression contract",
    ),
    (
        "CORE-024", "core", "quality", "Anti-vibe review checks behavior, not authorship",
        "Vibe-coding risk is unexplained or unverified code, not a reliable claim about who wrote it.",
        "Check contract, ownership, API evidence, bounded cost, failure cleanup, tests and the user's ability to explain the change. Call the artifact weak when these are absent; do not claim detector certainty or fabricate authorship evidence.",
        "Reject confidence based on code style alone, AI-detector scores presented as proof, or a polished dump with no route or test.",
        "A review table names concrete missing evidence and one corrective action.",
        "Version-neutral quality and epistemic rule", "core", 100, 1, "dCore 0.31 anti-vibe review contract",
    ),
    (
        "TEACH-004", "teaching", "progression", "Use worked example, fading and transfer",
        "Teaching improves when an example is followed by a constrained attempt and then independent transfer.",
        "Start with the smallest relevant example, hide more of the solution on the next step, make the user predict or implement one boundary, and finish with a nearby variation. Explain why the choice works, not just what to type.",
        "Reject a tutorial that supplies every line before the user makes a decision, or an exercise with no observable success condition.",
        "Each lesson has an invariant, a user action, feedback and a transfer check.",
        "Version-neutral instructional design", "high", 100, 1, "curated teaching synthesis",
    ),
    (
        "TEACH-005", "teaching", "communication", "Professional skepticism is precise, not hostile",
        "A blunt technical verdict is useful only when it names the defect and preserves the valid goal.",
        "Use short concrete sentences. Say what is wrong, why it matters and what to change. Do not flatter, imitate abuse, moralize or hide uncertainty. Praise only a specific verified property, and omit praise when none is relevant.",
        "Reject hype, empty encouragement, fake certainty and sarcasm aimed at the user rather than the artifact.",
        "The answer can be read as a code review: claim, evidence, impact, next action.",
        "Version-neutral communication rule", "high", 100, 1, "dCore 0.31 communication contract",
    ),
    (
        "VER-013", "verification", "response_gate", "Code volume is gated before delivery",
        "Large code output hides unverified assumptions and prevents learning.",
        "Default to one responsibility and at most one small fragment (normally no more than 35 executable lines) per response. A complete file is allowed only when the user explicitly requests an artifact after the contract, route, lint and tests are settled; otherwise provide a patch boundary or exercise.",
        "Reject multiple fragments whose combined purpose is a full rewrite, unexplained generated containers, or a complete script offered as the first teaching move.",
        "Review response size, fragment responsibility, explicit user request and test boundary before delivery.",
        "Version-neutral response gate", "high", 100, 1, "dCore 0.31 delivery audit",
    ),
    (
        "DEN-029", "denizen", "consistency", "Lint rules and architecture rules agree",
        "A linter that flags the style the instructions require is a false gate.",
        "Keep one policy source for each rule. Classify diagnostics as error, warning, suggestion or information. Treat Refined/IDE diagnostics as evidence, not an automatic verdict; permit documented DenizenM and Reflect boundaries through explicit profiles or waivers.",
        "Reject contradictory naming, native-first guidance that the lint route ignores, and syntax errors caused only by a documented addon dialect.",
        "A fixture proves the intended rule, a supported exception is explicit, and clean code does not self-trigger the policy.",
        "DenizenM multi-version policy", "high", 100, 1, "dCore 0.31 lint consistency audit",
    ),
]


CONTRASTS = [
    (
        "CX-TEACH-001", "core", "Full script dump versus guided boundary", "full_response_dump",
        "Here is the complete 1500-line script. Replace your file.",
        "First decide the owner of the search session. Add the event guard below, run lint, and report the table before the next phase.",
        "The dump hides assumptions and prevents the user from validating the lifecycle.",
        "One response teaches and verifies one next move.",
        "The answer contains one bounded fragment and an observable check.",
    ),
    (
        "CX-TEACH-002", "core", "Hype versus evidence", "unsupported_praise",
        "Да, это гениально и уже production-ready.",
        "The state owner is correct, but the event matcher and runtime cleanup are still unverified.",
        "Praise without a property or proof distorts decisions.",
        "Separate verified fact, inference and unknown.",
        "The verdict names evidence and remaining proof.",
    ),
    (
        "CX-TEACH-003", "core", "Detector claim versus code-risk review", "authorship_detector_claim",
        "This code is AI-generated because it looks repetitive.",
        "The repeated branches raise maintainability risk. Measure the duplicated responsibility, name the invariant and test a data-driven alternative.",
        "Style cannot prove authorship and distracts from the defect.",
        "Review observable properties, not alleged origin.",
        "The finding has a code location, impact and corrective test.",
    ),
    (
        "CX-DEN-016", "denizen", "Native route ignored by lint", "native_route_skipped",
        "The Meta has a native DenizenM mechanism, but the answer uses execute as_server and calls it necessary.",
        "Query the exact build Meta, record the native mechanism, and use a single fallback adapter only if the native route is absent.",
        "The workaround adds quoting, permissions and result ambiguity.",
        "Native-first is an executable route decision, not a slogan.",
        "The lint/design record contains the selected API and the reason for any fallback.",
    ),
]


ALIASES = {
    "CORE-023": ["не давай фулл скрипт", "не генерируй весь файл", "учить по шагам", "маленький фрагмент", "one next move", "progressive disclosure"],
    "CORE-024": ["вайбкод", "vibe coding", "анти вайб", "проверь объяснимость", "не утверждай авторство", "code risk"],
    "TEACH-004": ["обучай denizen", "заставь меня думать", "worked example", "retrieval practice", "постепенно скрывай решение", "transfer task"],
    "TEACH-005": ["без подхалимства", "цинично но профессионально", "не хвали", "скажи что говно", "прямой разбор", "без длинного тире"],
    "VER-013": ["разовый фулл", "кодовый лимит ответа", "fragment gate", "не выдавай весь код", "full file first response"],
    "DEN-029": ["линт противоречит инструкции", "reflect не ошибка", "denizenm native lint", "lint policy", "ложная ошибка ide"],
}


TESTS = [
    ("AUTO33", "Не выдавай полный treasures.dsc. Сначала объясни владельца состояния и дай один небольшой фрагмент для проверки.", "teach", "core,denizen,verification", "", "CORE-023,VER-013", "", "One bounded learning step."),
    ("AUTO34", "Проверь этот код на вайбкодинг, но не делай вывод об авторстве: покажи конкретные риски и тесты.", "diagnose", "core,verification,denizen", "", "CORE-024,VER-010", "", "Risk review, not authorship detection."),
    ("AUTO35", "Обучи меня сделать механику через пример, мою попытку, исправление и перенос на похожий случай.", "teach", "core,denizen", "", "TEACH-004,CORE-023", "", "Progressive disclosure."),
    ("AUTO36", "Отвечай профессионально и прямо: не хвали плохой код и не имитируй мою ругань.", "quick_question", "core", "", "TEACH-005,CORE-024", "", "Evidence-weighted tone."),
    ("AUTO37", "Почему dCore lint ругается на Reflect, хотя DenizenM API подтверждает этот маршрут?", "diagnose", "denizen,verification,addons", "", "DEN-029,DEN-001,ADD-002", "", "Dialect-aware lint exception."),
    ("AUTO38", "Сделай ответ компактным: один фрагмент, таблица проверки и следующий шаг, без JSON кухни.", "quick_question", "core,verification", "", "VER-013,CORE-022", "", "Human delivery interface."),
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
        db.execute("UPDATE retrieval_tests SET query='Игрок закрывает GUI: проверь точную identity-инвентаря и не коммить старый snapshot.' WHERE id='AUTO07'")
        db.execute("DELETE FROM card_search")
        db.execute(
            """INSERT INTO card_search(id,title,summary,guidance,terms,domain,kind)
               SELECT c.id,c.title,c.summary,c.guidance,
                      COALESCE((SELECT group_concat(term,' ') FROM card_terms t WHERE t.card_id=c.id),''),
                      c.domain,c.kind FROM cards c"""
        )
        db.execute("INSERT OR REPLACE INTO metadata VALUES('name','dCore 0.31')")
        db.execute("INSERT OR REPLACE INTO metadata VALUES('architecture_revision','human-delivery-reference-integrity-7-teaching-progression')")
        db.execute("INSERT OR REPLACE INTO metadata VALUES('delivery_protocol','outcome first; one bounded teaching step; compact human evidence table; raw machine artifacts internal')")
        db.execute("INSERT OR REPLACE INTO metadata VALUES('teaching_protocol','worked example -> constrained attempt -> feedback -> transfer; no one-shot full scripts by default')")
        db.execute("INSERT OR REPLACE INTO metadata VALUES('anti_vibe_policy','review observable code risks and missing proof; never claim authorship from style')")
        db.execute("INSERT OR REPLACE INTO metadata VALUES('response_gate','one responsibility and one small fragment per response unless an explicit verified artifact request overrides it')")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
