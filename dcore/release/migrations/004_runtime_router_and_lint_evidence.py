from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


CARDS = [
    (
        "DEN-026", "denizen", "capability_resolver",
        "Resolve native DenizenM capability before fallbacks",
        "A DenizenM target must search its own preferred Meta before official-only syntax, addon APIs, Reflect or console dispatch.",
        "Extract each required capability as a clause. Query the preferred DenizenM command, tag, event, mechanism and property entries first. Record the exact matching entry and installed build. Compare official Denizen only as a compatibility baseline. If native coverage is incomplete, move to an installed addon; use Reflect only with the exact Java class, method or constructor signature behind one adapter. Never infer absence from memory and never replace an unresolved native route with a command hack.",
        "Reject official-first routing for a DenizenM target, guessed addon syntax, or Reflect before a negative native capability result.",
        "For every emitted API surface, cite a DenizenM Meta entry or mark one isolated proof boundary. Test the smallest native proof before composing gameplay.",
        "Runtime profile and build sensitive", "core", 100, 1,
        "DenizenM/Reflect failures in shader and treasure runtime transcripts",
    ),
    (
        "DEN-025", "denizen", "event_scope",
        "Event blast radius: prove ownership before cancellation",
        "A broad world matcher may observe unrelated vanilla entities and blocks; cancellation or mutation before identity proof changes global gameplay.",
        "Prefer the narrowest supported script/entity/item/inventory/location matcher. When a broad matcher is unavoidable, the first executable guards must prove a stable role, session ID or owned location. Only then may the handler cancel, damage, remove, alter physics, block water, piston or inventory behavior. Audit every determination and mutation before the guard. A guarded broad handler is still a performance suggestion because it receives unrelated traffic.",
        "Reject global slime, damage, fluid, block, inventory-close or piston cancellation based only on entity type or material.",
        "Regression-test an unrelated entity/block/inventory of the same vanilla type and prove its native behavior is unchanged.",
        "Version-neutral architecture; matcher syntax is build-sensitive", "core", 100, 1,
        "Treasure regressions: all slimes protected, water updates blocked, unrelated inventories captured",
    ),
    (
        "ADD-008", "addons", "dialect_overlay",
        "Addon dialect overlays core lint instead of becoming an IDE exception",
        "Valid Reflect or Voxizen syntax is checked against its addon Meta, not rejected as unknown core syntax and not blanket-ignored.",
        "Select the runtime profile and installed addons explicitly. Merge each addon command/tag surface into lint with provenance. A known addon token suppresses only the corresponding unknown-core diagnostic. It does not prove Java signatures, object types, side effects or runtime availability. Reflect remains one isolated, version-pinned adapter after DEN-024 proves the native gap.",
        "Reject global ignore lists for angle tags, invoke, imports or mechanisms; they hide misspellings next to valid addon syntax.",
        "Lint one valid addon sample and one misspelled neighbour. The valid line becomes informational provenance; the typo remains an error.",
        "Addon version sensitive", "high", 99, 1,
        "denizen-reflect Meta and false IDE diagnostics",
    ),
    (
        "VER-008", "verification", "evidence_ladder",
        "Lint diagnostics are layered evidence, never a runtime certificate",
        "Structural, Meta, lifecycle, shader and gameplay checks prove different things and must not collapse into one green PASS.",
        "Report diagnostics as error, warning, suggestion or information with layer and source. Errors block delivery. Warnings require proof or explanation. Suggestions are design/performance review. Information records dialect or evidence provenance. A clean static run proves only what its rules cover. Shader route, culling, F5, FPS, pathfinding, inventory races, reload and player-visible behavior require explicit runtime tests. Verdict is INCOMPLETE whenever a mandatory layer was not run.",
        "Reject `lint: []` as proof that a shader renders, an entity path is reachable, or a mechanic survives restart.",
        "Publish the exact commands and observed outputs for IDE/static, `/ex reload`, console and gameplay layers separately.",
        "Version-neutral evidence policy", "core", 100, 1,
        "Repeated false-green lint claims immediately contradicted by runtime",
    ),
    (
        "VIS-031", "visual", "render_route_proof",
        "Render-route census before shader marker or screen math",
        "Core shader filenames, vertex formats and buffers cannot be guessed from an entity class or community example.",
        "Start with the final merged pack and color one candidate route at a time using a unique harmless proof. Identify the actual draw route for the exact ItemDisplay, TextDisplay, BlockDisplay or item model. Then prove one exclusive marker with an unmarked control. Only after route and identity survive should the shader change clip-space position. Test inventory/hand/world collateral, transparency, graphics modes and pack reload. Community paths are clues, not proof for another Minecraft build.",
        "Reject implementing the real visual while route, marker identity and vertex format remain simultaneous unknowns.",
        "Proof order: route census, marker-only, transform-only, F5/FOV/culling, multi-viewer/reset, then cosmetics and gameplay.",
        "Minecraft/resource-pack version sensitive", "core", 100, 1,
        "Camera HUD shader failures across item, text and block display routes",
    ),
    (
        "VIS-032", "visual", "camera_space_composition",
        "Camera-attached display separates tracking from clip-space placement",
        "A mount or attachment may keep a draw call near the viewer, but it does not itself make a stable screen-space element.",
        "Treat the server carrier and client transform as separate owners. The smallest viewer-only carrier keeps the marked draw call alive and bounded near the player; the verified vertex route owns final clip-space placement, screen anchor, scale and perspective behavior. Declare whether F5 should remain HUD-like or follow the physical camera. Prove frustum/culling, FOV, resize, teleport, speed and first/third person. If the server cannot observe the client camera, do not promise cursor input from that camera without an explicit client-side channel.",
        "Reject per-tick world-space chasing, huge sky domes or armor stands as substitutes for a failed screen transform.",
        "Test stationary, fast movement, teleport, F5 front/back, FOV, resize, two viewers and carrier removal in the final pack.",
        "Minecraft/client render version sensitive", "high", 100, 1,
        "Camera attachment and F5 failures from shader transcripts",
    ),
    (
        "PERF-010", "performance", "navigation_owner",
        "One movement owner and progress-based bounded replanning",
        "Native pathfinding, scripted push and teleport correction must not compete for one entity during the same movement phase.",
        "Choose one movement owner per phase. For a dog search, issue a bounded native walk segment, monitor coarse progress, and replan only on timeout, insufficient progress or invalid target. Stop the previous walk before ownership changes. Separate target generation from reachability; use dry/water/slope policy as candidate validation, not a second per-tick steering system. A launch phase suspends navigation, applies one impulse, then restores only state it changed.",
        "Reject repeated push plus walk, every-tick waypoint replacement, circular corrections, or teleporting the entity back while navigation is active.",
        "Test flat terrain, mountains, water boundary, obstruction, no progress, target invalidation, quit/death/reload and simultaneous repeated input.",
        "Native navigation behavior is build-sensitive", "high", 99, 1,
        "Treasure dog circular movement, water avoidance and timeout regressions",
    ),
    (
        "CORE-018", "core", "inventory_scope",
        "GUI handlers bind to an exact inventory session",
        "Inventory title or a generic close/click event is presentation context, not authoritative ownership.",
        "Create one stable inventory/session ID and bind open, click, drag and close handlers to that exact inventory or flag matcher. The backing record owns loot/stock; the GUI is a view. On close, commit only fields the session owns and only if the same session is still active. Never write an arbitrary closing inventory snapshot into gameplay state. Clear the viewer reference idempotently and test another inventory opened during the session.",
        "Reject global player-closes-inventory handlers, title-only identity, or close-time overwrite of authoritative state.",
        "Open the target GUI, another chest, crafting and a second custom GUI; only the matching session may mutate or clean up state.",
        "Version-neutral architecture; inventory matcher syntax is build-sensitive", "core", 100, 1,
        "Treasure GUI reacted to unrelated inventory close and stale snapshots",
    ),
]


ALIASES = {
    "DEN-026": ["нативная поддержка DenizenM", "нативн* поддерж* DenizenM", "сначала DenizenM Meta", "native DenizenM", "не делай костыль", "capability proof"],
    "DEN-025": ["глобальный обработчик", "все слизни", "ломается вода", "широкое событие", "broad slime event", "blast radius", "отмена до проверки"],
    "ADD-008": ["Reflect", "Reflect lint", "denizen-reflect", "invoke не ошибка", "addon dialect", "IDE считает Reflect ошибкой"],
    "VER-008": ["lint пустой но не работает", "ложный PASS", "ошибки предупреждения предложения", "static не runtime", "lint и runtime", "уровни проверки"],
    "VIS-031": ["route census", "render route", "какой шейдер рисует", "шейдер не срабатывает", "block.vsh", "vertex format"],
    "VIS-032": ["прикрепить display к камере", "прикреплённ* к экран*", "item display в экран", "не работает в F5", "screen space display", "clip space HUD"],
    "PERF-010": ["собака ходит кругами", "ходит кругами", "ломается pathfinding", "walk конфликтует с push", "walk и push", "пес не идет", "repath", "navigation owner"],
    "CORE-018": ["закрыл другой инвентарь", "друг* инвентар*", "любой инвентарь", "GUI session", "inventory close срабатывает", "общий сундук"],
}


INTENT_TERMS = {
    "bugfix": [("почини", 8), ("исправь", 8), ("фикс", 6), ("не работает", 5)],
    "diagnose": [("почему", 7), ("найди причину", 8), ("ошибка в консоли", 6)],
    "full_audit": [("полный аудит", 10), ("проанализируй всё", 9), ("аудит проекта", 9)],
    "refactor": [("рефактор", 9), ("перепиши архитектуру", 9), ("оптимизируй код", 6)],
    "full_file": [("полный файл", 9), ("production файл", 8)],
    "visual_design": [("шейдер", 5), ("shader", 5), ("item_display", 4), ("resource pack", 4)],
    "performance_review": [("нагрузка", 7), ("лаги", 7), ("hot path", 6)],
    "teach": [("объясни", 7), ("научи", 8)],
    "quick_question": [("синтаксис", 6), ("какой тег", 6)],
}


TESTS = [
    ("AUTO01", "Почини: глобальный обработчик сделал так, что всех слизней нельзя бить и вода не обновляется", "bugfix", "denizen,verification", "", "DEN-025,VER-008", "", "Blast radius regression."),
    ("AUTO02", "Сделай item_display прикреплённый к экрану, чтобы не дёргался и работал в F5 через shader", "visual_design", "visual", "", "VIS-031,VIS-032", "", "Camera composition requires route proof."),
    ("AUTO03", "Проведи полный аудит проекта: роутер, lint, Meta и runtime доказательства", "full_audit", "denizen,verification", "", "DEN-026,VER-008", "", "Actual auto intent."),
    ("AUTO04", "Рефактор GUI: закрытие любого другого инвентаря сейчас портит содержимое клада", "refactor", "core", "", "CORE-018", "", "Inventory scope."),
    ("AUTO05", "Почини собаку: она ходит кругами, боится воды и walk конфликтует с push", "bugfix", "performance", "", "PERF-010", "", "Movement ownership."),
    ("AUTO06", "Новая механика вызывает API через Reflect, но сначала проверь нативную поддержку DenizenM", "new_mechanic", "addons,denizen", "", "ADD-008,DEN-026", "", "Native-first addon boundary."),
    ("AUTO07", "Почему inventory close срабатывает, когда я закрываю вообще другой сундук?", "diagnose", "core", "", "CORE-018", "", "Diagnose exact GUI identity."),
    ("AUTO08", "Шейдер компилируется, но BlockDisplay не меняется: сначала нужен render route census", "visual_design", "visual", "", "VIS-031", "", "Compiled is not reachable."),
    ("AUTO09", "Дай полный файл и не называй его готовым, пока lint и runtime проверки не пройдены", "full_file", "verification", "", "VER-008", "", "Full file evidence gate."),
    ("AUTO10", "Проверь нагрузку: broad slime event и глобальный tick loop работают для всех игроков", "performance_review", "denizen,performance", "", "DEN-025", "", "Performance plus blast radius."),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path("dcore/knowledge/data/dcore.sqlite"))
    args = parser.parse_args()
    with sqlite3.connect(args.db) as db:
        db.execute("PRAGMA foreign_keys=ON")
        columns = {row[1] for row in db.execute("PRAGMA table_info(card_links)")}
        if "mandatory" not in columns:
            db.execute("ALTER TABLE card_links ADD COLUMN mandatory INTEGER NOT NULL DEFAULT 0 CHECK(mandatory IN (0,1))")
        db.execute("UPDATE card_links SET mandatory=1 WHERE relation='requires' OR relation LIKE 'requires_%'")

        for card in CARDS:
            db.execute(
                "INSERT OR REPLACE INTO cards(id,domain,kind,title,summary,guidance,reject_when,verification,version_scope,confidence,priority,token_weight,source_basis) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                card,
            )
        db.execute(
            "UPDATE cards SET guidance=? WHERE id='ADD-001'",
            ("Select precedence from the requested runtime. For DenizenM: preferred DenizenM Meta first, official Denizen only as baseline comparison, then installed addon Meta, then an exact-signature Reflect adapter. Never infer native absence from memory and never dispatch a console command merely because official syntax was easier to recall.",),
        )
        db.execute(
            "UPDATE cards SET guidance=? WHERE id='DEN-016'",
            ("Before any console or plugin command dispatch, resolve the same capability in preferred DenizenM commands, tags, mechanisms, properties and events. Use native execution when it preserves the required semantics. A dispatch fallback must document the missing native capability, permission/quoting boundary and exact installed provider.",),
        )

        for card_id, terms in ALIASES.items():
            db.execute("INSERT OR REPLACE INTO card_activation_rules(card_id,min_hits) VALUES(?,1)", (card_id,))
            for term in terms:
                db.execute("INSERT OR IGNORE INTO card_terms(card_id,term) VALUES(?,?)", (card_id, term))
                db.execute("INSERT OR IGNORE INTO card_activation_terms(card_id,term) VALUES(?,?)", (card_id, term))
                db.execute("INSERT OR REPLACE INTO card_alias_terms(card_id,term,weight) VALUES(?,?,12)", (card_id, term))
        for intent, terms in INTENT_TERMS.items():
            for term, weight in terms:
                db.execute("INSERT OR REPLACE INTO intent_terms(intent,term,weight) VALUES(?,?,?)", (intent, term, weight))

        for intent in ("diagnose", "bugfix", "refactor", "new_mechanic", "visual_design", "full_audit", "full_file"):
            db.execute("INSERT OR REPLACE INTO route_pins(intent,card_id,position) VALUES(?,?,90)", (intent, "DEN-026"))
            db.execute("INSERT OR REPLACE INTO route_pins(intent,card_id,position) VALUES(?,?,91)", (intent, "VER-008"))

        for domain, terms in {
            "denizen": ["DenizenM Meta", "глобальный обработчик", "широкое событие", "все слизни"],
            "verification": ["lint", "runtime", "ложный PASS", "предупреждения"],
            "visual": ["render route", "route census", "clip space", "прикрепить display к камере"],
            "addons": ["denizen-reflect", "Reflect", "invoke"],
            "performance": ["собака ходит кругами", "pathfinding", "repath", "navigation owner"],
            "core": ["inventory close", "другой инвентарь", "GUI session"],
        }.items():
            for term in terms:
                db.execute("INSERT OR IGNORE INTO domain_terms(domain,term) VALUES(?,?)", (domain, term))

        links = [
            ("ADD-008", "DEN-026", "requires", 1),
            ("VIS-032", "VIS-031", "requires_render_graph", 1),
            ("VIS-031", "VIS-022", "requires", 1),
            ("DEN-025", "VER-008", "requires", 1),
            ("CORE-018", "DEN-025", "requires_lifecycle", 1),
            ("PERF-010", "DEN-026", "requires", 1),
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
        db.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('name','dCore 0.27')")
        db.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('architecture_revision','native-first-router-and-layered-lint-3')")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
