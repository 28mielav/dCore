from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


SURFACE_CARD = (
    "PERF-009",
    "performance",
    "bounded_world_query",
    "Surface search separates height seed from bounded validation",
    "A heightmap result is a column seed, not proof that the returned top block is usable ground.",
    "Generate a fixed number of X/Z candidates in already loaded chunks. Use the native highest/heightmap lookup once per column, then descend through a small configured budget when custom terrain or canopy can occupy the top. Validate the resulting surface, foundation, replaceable headroom, biome, Y range and distance. Commit item cost/cooldown only after a candidate is returned. Never materialize a large cuboid or scan an unbounded column.",
    "Reject LocationTag.highest as final ground in forests/custom worldgen, cuboid.blocks, chunk loading during an interaction, or consuming input before search success.",
    "Test open plains, dense leaves/logs, custom tall vegetation, water, caves, min/max Y, unloaded chunks, no valid candidate and a strict worst-case counter: candidates x descent budget.",
    "Paper/DenizenM height lookup syntax is build-sensitive; architecture is version-neutral",
    "high",
    96,
    1,
    "treasure-dog runtime failure: heightmap top was canopy rather than valid ground",
)


ALIASES = {
    "MATH-016": [
        "пересечение плоскости", "скан плоской области", "тонкий портал",
        "наклонный портал", "пересёк за один тик", "лазерная калитка",
    ],
    "MATH-017": ["границы портала", "круглый портал", "локальная форма", "внутри диска"],
    "MATH-018": [
        "перенос через портал", "сохранить направление", "относительная позиция",
        "сохранить скорость", "стена потолок",
    ],
    "MATH-019": ["повторная телепортация", "зацикливание порталов", "сторона плоскости"],
    "VIS-029": ["моргание", "веки", "экран загрузки", "плавное затемнение"],
    "VIS-030": ["тряска экрана", "отдача", "покачивание камеры", "наклон камеры"],
    "MATH-009": ["курсор взглядом", "ползунок", "повёрнутая панель"],
    "VIS-023": ["привязать к камере", "третье лицо", "режим f5"],
    "VIS-025": ["маска объекта", "волна сканера", "свечение объектов"],
    "VIS-024": ["персональный sky shader", "без reload", "viewer-only control", "не пропадает при f5"],
    "VIS-027": ["shader target rebuild", "порядок shader passes", "режим графики ломает shader"],
    "PERF-009": [
        "поиск поверхности", "поиск земли", "крона дерева", "под листвой",
        "кастомная генерация", "собака не находит клад", "heightmap canopy",
        "highest valid ground", "bounded surface descent",
    ],
}


TESTS = [
    ("GVP01", "Игрок за один тик пересекает тонкий наклонный портал: нужен точный скан плоской области, а не кубоид", "visual_design", "math", "", "MATH-016,MATH-017", "VIS-013", "Portal crossing is geometry."),
    ("GVP02", "Лазерная калитка под углом должна один раз сработать, когда игрок пересечёт её плоскость", "visual_design", "math", "", "MATH-016,MATH-019", "", "Transfer without portal vocabulary."),
    ("GVP03", "Круглый энергетический щит должен ловить быстрый projectile только внутри видимого диска", "visual_design", "math", "", "MATH-016,MATH-017", "", "Swept segment plus local circular bounds."),
    ("GVP04", "Пара порталов на стене и потолке сохраняет смещение справа, взгляд и скорость игрока", "visual_design", "math", "", "MATH-018", "", "Paired-frame transform."),
    ("GVP05", "Повёрнутая display панель: курсор взглядом двигает slider по локальной вертикали", "visual_design", "math,visual", "", "MATH-009,VIS-009", "", "Reusable ray-plane input."),
    ("GVP06", "Сделай моргание веками через shader только одному игроку", "visual_design", "visual", "", "VIS-029", "", "Temporal fullscreen mask."),
    ("GVP07", "Нужен полноценный экран загрузки с прерыванием и безопасным reset, не actionbar-картинка", "visual_design", "visual", "", "VIS-029", "", "Loading reuses transition primitive."),
    ("GVP08", "После взрыва экран кратко ведёт в сторону, дрожит и полностью затухает", "visual_design", "visual", "", "VIS-030", "", "Bounded screen impulse."),
    ("GVP09", "HUD item_display должен быть привязан к виду и работать в F5 и от первого лица", "visual_design", "visual", "", "VIS-023", "", "Explicit view source."),
    ("GVP10", "Портал показывает сохранённый color depth снимок другой точки и перепроецирует его", "visual_design", "visual", "", "VIS-013", "MATH-016", "Rendering is distinct from crossing."),
    ("DCF01", "Собака не создаёт клад в кастомном лесу: LocationTag.highest попадает в крону, нужен ограниченный поиск земли", "diagnose", "denizen,performance", "", "PERF-009", "", "Custom-world surface regression."),
    ("DCF02", "Нужен плавно включаемый персональный sky shader без reload, который не пропадает при F5, speed и teleport", "visual_design", "visual", "", "VIS-022,VIS-024", "", "Carrier proof before implementation."),
    ("DCF03", "Хочу через Reflect вызвать new Vector3f и сразу выдать production код без проверки сигнатуры", "new_mechanic", "addons,verification", "", "ADD-002", "", "Reflect must remain a proof boundary."),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path("knowledge/dcore.sqlite"))
    args = parser.parse_args()
    with sqlite3.connect(args.db) as db:
        db.execute("PRAGMA foreign_keys=ON")

        # Remove replacement characters and characteristic UTF-8-as-CP1251 garbage.
        mojibake_markers = set("�їЃ‚љњќћЎўЌЊ")
        for table in ("card_terms", "card_activation_terms", "card_alias_terms"):
            for card_id, term in db.execute(f"SELECT card_id,term FROM {table}").fetchall():
                if any(character in mojibake_markers for character in term):
                    db.execute(f"DELETE FROM {table} WHERE card_id=? AND term=?", (card_id, term))
        for domain, term in db.execute("SELECT domain,term FROM domain_terms").fetchall():
            if any(character in mojibake_markers for character in term):
                db.execute("DELETE FROM domain_terms WHERE domain=? AND term=?", (domain, term))

        db.execute(
            "INSERT OR REPLACE INTO cards(id,domain,kind,title,summary,guidance,reject_when,verification,version_scope,confidence,priority,token_weight,source_basis) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            SURFACE_CARD,
        )
        db.execute(
            "UPDATE cards SET guidance=? WHERE id='VIS-022'",
            (
                "Proof order: final-pack shader compile; one marker texture; one carrier; one viewer; expected material; unmarked fallback; transform/interpolation; multiple viewers; lifecycle/reset; only then cosmetics or gameplay. Stop at the first failed layer. Do not hide a failed carrier behind Denizen follow loops, mounts, Reflect or recovery tasks. Parameter proofs also verify encode/decode monotonicity, sample coordinates and stale-target clearing. Without a compiled final render-graph merge, label the result a proof, not a complete pack.",
            ),
        )
        db.execute(
            "UPDATE cards SET guidance=?,reject_when=?,verification=? WHERE id='VIS-024'",
            (
                "A viewer-only glowing carrier may encode controls into entity_outline only after the final client pipeline proves that the sample survives frustum/culling, F5, fast movement, teleport and graphics-mode target rebuilds. Keep the carrier as presentation input, never gameplay truth. Own show/hide, color reservation, stale-buffer clearing and cleanup in one session. If a stable camera-independent sample cannot be proven, reject this carrier instead of adding a server chase loop.",
                "Reject when ordinary glow colors must remain untouched, the pipeline lacks a stable outline target, the sample disappears outside the view/frustum, or a simpler already-loaded fullscreen route exists.",
                "Verify off/on, two values, ordinary glowing entities, F5, fast flight, teleport, resize, graphics modes, one frame after removal and final-pack merge before adding the real effect.",
            ),
        )

        for card_id, terms in ALIASES.items():
            for term in terms:
                db.execute("INSERT OR IGNORE INTO card_terms(card_id,term) VALUES(?,?)", (card_id, term))
                db.execute("INSERT OR IGNORE INTO card_activation_terms(card_id,term) VALUES(?,?)", (card_id, term))
                weight = 12 if card_id in ("VIS-024", "VIS-027") else 8
                db.execute("INSERT OR REPLACE INTO card_alias_terms(card_id,term,weight) VALUES(?,?,?)", (card_id, term, weight))
            db.execute("INSERT OR REPLACE INTO card_activation_rules(card_id,min_hits) VALUES(?,1)", (card_id,))

        for term in ("поиск поверхности", "крона", "листва", "кастомная генерация", "heightmap", "highest"):
            db.execute("INSERT OR IGNORE INTO domain_terms(domain,term) VALUES('performance',?)", (term,))

        for test in TESTS:
            db.execute(
                "INSERT OR REPLACE INTO retrieval_tests(id,query,intent,expected_domains,forbidden_domains,expected_cards,forbidden_cards,notes) VALUES(?,?,?,?,?,?,?,?)",
                test,
            )

        db.execute("DELETE FROM card_search")
        db.execute("INSERT INTO card_search(id,title,summary,guidance) SELECT id,title,summary,guidance FROM cards")
        db.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('name','dCore 0.26')")
        db.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('architecture_revision','runtime-proof-and-unicode-routing-2')")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
