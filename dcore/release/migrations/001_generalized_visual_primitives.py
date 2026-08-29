from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


CARDS = [
    (
        "MATH-016", "math", "geometry", "Oriented plane queries share one local-space primitive",
        "Thin portals, laser gates, panels and trigger surfaces use the same bounded plane query; only the input ray or motion segment changes.",
        "Represent the plane by center C, unit normal n and orthonormal right/up axes. For a segment P0->P1 compute signed distances d0=dot(P0-C,n), d1=dot(P1-C,n). A directional crossing requires the configured sign transition and a non-degenerate denominator. Solve t=d0/(d0-d1), require t in [0,1], then H=P0+(P1-P0)t. A view query instead solves the equivalent ray-plane equation and requires t>=0. Convert H-C to local x/y before applying shape bounds. Use a cheap chunk/region candidate lookup as broad phase and this exact query as narrow phase.",
        "Reject axis-specific X/Y/Z branches, a one-block-thick cuboid presented as a thin rotated surface, nearest-entity distance as crossing proof, or a polygon entity scan without exact segment-plane intersection.",
        "Test both crossing directions, parallel and coplanar motion, high-speed tunneling, edge hits, an angled plane, start/end on the epsilon slab, and the same primitive as portal, laser gate and panel input.",
        "version-neutral math; exact Denizen vector syntax is build-sensitive", "high", 97, 2,
        "generalized from portal-plane scan, ray-plane UI and swept collision requirements",
    ),
    (
        "MATH-017", "math", "geometry", "Local shape bounds are independent of world orientation",
        "Intersection with an infinite plane and membership in its finite shape are separate operations.",
        "After converting the hit to plane-local x/y, choose a declared shape test: rectangle abs(x)<=halfWidth and abs(y)<=halfHeight; circle x*x+y*y<=r*r; ellipse (x/a)^2+(y/b)^2<=1; convex polygon by consistent edge half-spaces. Keep render geometry, interaction bounds and gameplay shape explicit because they may differ. Rotation affects only the basis conversion, never the local shape formula.",
        "Reject world-axis bounds for rotated geometry, a fat cuboid used to approximate a plane, or collision against every decorative display piece.",
        "Test center, every edge and corner, just-inside/outside epsilon cases, multiple rotations and scales, and mismatched visual/proxy sizes.",
        "version-neutral math", "high", 94, 2,
        "general local-space geometry primitive",
    ),
    (
        "MATH-018", "math", "transform", "Paired frames transform position, direction and velocity",
        "Portals, linked cameras and oriented transitions map components between two coordinate frames instead of adding world-coordinate offsets.",
        "For entry basis (rightA,upA,normalA), project point offset, gaze and velocity into local components with dot products. Apply the declared handedness or portal flip in local space, then reconstruct through (rightB,upB,normalB) at the exit. Transform position, look direction and velocity with the same convention. Normalize directions, preserve magnitudes where intended, and offset the result slightly to the valid exit side.",
        "Reject raw destination-minus-source translation, yaw-only rotation for arbitrary planes, or transforming position while leaving gaze and velocity in the old frame.",
        "Test entry from right/left/top/bottom, floor and ceiling portals, nonparallel frames, preserved speed, handedness, and round-trip A->B->A within tolerance.",
        "version-neutral math; teleport/velocity APIs are build-sensitive", "high", 96, 2,
        "generalized paired-coordinate-frame mapping",
    ),
    (
        "MATH-019", "math", "state", "Crossing detection needs side history, hysteresis and rearm",
        "A mathematically correct plane hit still repeats when an actor remains on the boundary or immediately intersects the paired exit.",
        "Store only the short-lived facts required by the crossing owner: previous sample, armed side, token and optional paired destination. Use an epsilon slab around the plane, require a directional sign transition, fire once, disarm, place the actor beyond the exit epsilon, and rearm only after it clearly leaves the slab on an allowed side. Prefer state tied to the active actor/portal session; do not poll dormant portals.",
        "Reject a fixed timer as the only anti-loop rule, repeated teleport while distance is below a threshold, or persistent per-portal tick queues.",
        "Test standing on the plane, walking back and forth, spawning inside the slab, high speed, paired portals facing each other, lag spikes, cancellation and cleanup.",
        "version-neutral state model", "high", 93, 2,
        "general crossing lifecycle primitive",
    ),
    (
        "VIS-029", "visual", "postprocess", "Temporal fullscreen masks compose transitions",
        "Blinking, fades, loading screens and damage flashes are parameterized fullscreen transitions, not four unrelated shader systems.",
        "Define a per-viewer transition session with phase, normalized progress, curve, mask geometry, color/content source and reset. The shader derives coverage from progress: opposing eyelid masks for a blink, uniform coverage for fade, and a branded layer or captured frame for loading. Server updates transition parameters only at meaningful state changes; the client renders frames. Absence of the control carrier must decode to a neutral effect.",
        "Reject a giant actionbar image described as a fullscreen shader, per-frame server entity churn, or a shader with no neutral reset and interrupted-transition cleanup.",
        "Test open/close curves, aspect ratios, FOV, GUI scale independence, interruption halfway, teleport/load completion, two viewers, death/world change/quit/reload and missing control input.",
        "Minecraft 1.21.11 render-pipeline sensitive", "high", 94, 2,
        "generalized fullscreen transition architecture",
    ),
    (
        "VIS-030", "visual", "postprocess", "Screen transforms consume bounded impulses",
        "Shake, recoil, camera roll and shock distortion share an impulse envelope and differ in the transform they drive.",
        "Represent each impulse by start time, duration, amplitude, frequency/seed, envelope and channels such as translation, rotation, radial distortion or chromatic offset. Sum a bounded number of active impulses, clamp the result, decay to zero and feed one per-viewer control protocol. Keep visual camera displacement separate from authoritative player look unless gameplay intentionally changes it. Select core, post or camera-control route from the required screen-space operation.",
        "Reject random teleporting of the player as cosmetic shake, one queue/entity per oscillation sample, unlimited impulse accumulation, or a permanent nonzero shader state after cleanup.",
        "Test single and overlapping impulses, exact decay to zero, low/high FPS, F5 modes, two viewers, world change, death, quit, reload and an unmarked render path.",
        "Minecraft and camera-control API sensitive", "high", 93, 2,
        "generalized camera and screen impulse architecture",
    ),
]

TERMS = {
    "MATH-016": ["oriented plane", "segment plane intersection", "signed distance", "plane crossing", "thin trigger", "пересечение плоскости", "скан плоской области", "тонкий портал", "наклонный портал"],
    "MATH-017": ["local shape bounds", "point in shape", "circle bounds", "polygon bounds", "границы портала", "круглый портал", "локальная форма"],
    "MATH-018": ["paired frames", "portal transform", "preserve view", "preserve velocity", "перенос через портал", "сохранить направление", "относительная позиция"],
    "MATH-019": ["crossing hysteresis", "portal rearm", "reentry guard", "повторная телепортация", "зацикливание порталов", "сторона плоскости"],
    "VIS-029": ["fullscreen transition", "blink shader", "eyelid mask", "loading screen", "fade shader", "моргание", "веки", "экран загрузки"],
    "VIS-030": ["screen impulse", "screen shake", "camera shake", "recoil", "camera roll", "shock distortion", "тряска экрана", "отдача", "покачивание камеры"],
}

ALIASES = {key: [(term, 7 if index < 4 else 6) for index, term in enumerate(values)] for key, values in TERMS.items()}

TESTS = [
    ("GVP01", "Игрок за один тик пересекает тонкий наклонный портал: нужен точный скан плоской области, а не кубоид", "visual_design", "math", "", "MATH-016,MATH-017", "VIS-013", "Portal crossing is geometry, not captured-scene rendering."),
    ("GVP02", "Лазерная калитка под углом должна один раз сработать, когда игрок пересечет ее плоскость", "visual_design", "math", "", "MATH-016,MATH-019", "", "Transfer test: no portal vocabulary required."),
    ("GVP03", "Круглый энергетический щит должен ловить быстрый projectile только внутри видимого диска", "visual_design", "math", "", "MATH-016,MATH-017", "", "Transfer to swept projectile and circular bounds."),
    ("GVP04", "Пара порталов на стене и потолке сохраняет смещение справа, взгляд и скорость игрока", "visual_design", "math", "", "MATH-018", "", "Paired-frame transform."),
    ("GVP05", "Повернутая display панель: курсор взглядом двигает slider по локальной вертикали", "visual_design", "math,visual", "", "MATH-009,VIS-009", "", "Ray-plane input remains reusable."),
    ("GVP06", "Сделай моргание веками через shader только одному игроку", "visual_design", "visual", "", "VIS-029", "", "Temporal mask application."),
    ("GVP07", "Нужен полноценный экран загрузки с прерыванием и безопасным reset, не actionbar-картинка", "visual_design", "visual", "", "VIS-029", "", "Loading reuses transition primitive."),
    ("GVP08", "После взрыва экран кратко ведет в сторону, дрожит и полностью затухает", "visual_design", "visual", "", "VIS-030", "", "Semantic transfer without literal shake keyword."),
    ("GVP09", "HUD item_display должен быть привязан к виду и работать в F5 и от первого лица", "visual_design", "visual", "", "VIS-023", "", "View-relative projection, not one menu recipe."),
    ("GVP10", "Портал показывает сохраненный color depth снимок другой точки и перепроецирует его", "visual_design", "visual", "", "VIS-013", "MATH-016", "Rendering request must remain distinct from crossing detection."),
]


def add_terms(db: sqlite3.Connection, table: str, card_id: str, values: list[str]) -> None:
    for value in values:
        db.execute(f"INSERT OR IGNORE INTO {table}(card_id,term) VALUES(?,?)", (card_id, value))


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
        # Generalize existing cards instead of teaching one mechanism per named demo.
        db.execute("UPDATE cards SET title=?,summary=?,guidance=?,reject_when=?,verification=? WHERE id='MATH-009'", (
            "Ray-plane queries map a view ray into local space",
            "Gaze cursors, sliders and world-space panels use one ray-plane intersection followed by local-coordinate bounds.",
            "Represent the surface with center, right, up and normal. Solve t=dot(center-origin,normal)/dot(direction,normal); reject a near-zero denominator or t<0. Convert hit-center with dot products onto right/up, apply the declared local shape bounds, then quantize application values once. The same primitive serves cursor menus, sliders, buttons and aim-selected surfaces.",
            "Reject guessed points at equal distance, world-space Y slider math, or a separate coordinate recipe for every rotated widget.",
            "Test horizontal, vertical and arbitrarily rotated surfaces, parallel rays, behind-camera hits, shape edges, FOV/view-source changes and release cleanup.",
        ))
        db.execute("UPDATE cards SET title=?,summary=?,guidance=? WHERE id='VIS-023'", (
            "View-relative interfaces require an explicit projection source",
            "HUDs, reticles and cursor menus must declare whether they follow the server eye, the actual client camera or clip space; F5 is a compatibility case, not a separate architecture.",
            "Choose a projection source and route. Camera-space route owns a camera/mount transaction and viewer-only displays. Shader route marks only intended carriers and maps vertices into clip/screen space while preserving vanilla draws. Define anchor, depth, aspect/FOV policy, view-mode limitations, visibility, input-ray source and reset. Do not claim exact third-person-camera input when the server cannot observe that camera transform.",
        ))
        db.execute("UPDATE cards SET title=?,summary=? WHERE id='VIS-025'", (
            "Selective masks feed bounded screen-space processing",
            "Bloom, outlines, highlights, scanner waves and local distortion share mask selection, bounded processing and composite.",
        ))
        for card_id, values in TERMS.items():
            add_terms(db, "card_terms", card_id, values)
            add_terms(db, "card_activation_terms", card_id, values)
            db.execute("INSERT OR REPLACE INTO card_activation_rules(card_id,min_hits) VALUES(?,1)", (card_id,))
            for term, weight in ALIASES[card_id]:
                db.execute("INSERT OR REPLACE INTO card_alias_terms(card_id,term,weight) VALUES(?,?,?)", (card_id, term, weight))
        targeted = {
            "MATH-016": ["пересека* тонк*", "скан плоск*", "лазерн* калитк*", "быстр* projectile"],
            "MATH-017": ["тонк* наклонн*", "кругл* энергетич*", "внутри видим* диск*"],
            "MATH-018": ["сохраня* смещен*", "сохраня* взгляд*", "стен* потолк*"],
            "MATH-019": ["один раз сработ*", "повторн* пересеч*"],
            "VIS-030": ["ведет в сторону", "дрожит", "полностью затухает"],
        }
        for card_id, values in targeted.items():
            for term in values:
                db.execute("INSERT OR IGNORE INTO card_activation_terms(card_id,term) VALUES(?,?)", (card_id, term))
                db.execute("INSERT OR REPLACE INTO card_alias_terms(card_id,term,weight) VALUES(?,?,8)", (card_id, term))
        extras = {
            "MATH-009": ["gaze cursor", "ray plane", "cursor menu", "slider", "курсор взглядом", "ползунок"],
            "VIS-023": ["view relative", "screen attached", "clip space", "f5", "third person hud", "привязать к камере", "третье лицо"],
            "VIS-025": ["scanner wave", "selective mask", "outline", "bloom", "highlight", "маска объекта"],
        }
        for card_id, values in extras.items():
            add_terms(db, "card_terms", card_id, values)
            for term in values:
                db.execute("INSERT OR REPLACE INTO card_alias_terms(card_id,term,weight) VALUES(?,?,?)", (card_id, term, 6))
                db.execute("INSERT OR IGNORE INTO card_activation_terms(card_id,term) VALUES(?,?)", (card_id, term))
        for term in [
            "plane", "geometry", "ray", "local coordinates", "transform",
            "плоскост*", "плоск*", "геометр*", "локальн*", "пересеч*", "щит*",
            "калитк*", "направлен*", "скорост*",
        ]:
            db.execute("INSERT OR IGNORE INTO domain_terms(domain,term) VALUES('math',?)", (term,))
        # Stabilize a pre-existing regression: repeated expensive tag evaluation must
        # route to the cache/reuse card rather than the generic cost-model card.
        for term in ["тяжёл* tag", "один и тот же тяжёл* tag", "вычисляется пять раз"]:
            db.execute("INSERT OR REPLACE INTO card_alias_terms(card_id,term,weight) VALUES('PERF-005',?,9)", (term,))
        links = [
            ("MATH-009", "MATH-017", "applies_bounds"),
            ("MATH-016", "MATH-001", "uses_basis"),
            ("MATH-016", "MATH-017", "applies_bounds"),
            ("MATH-016", "MATH-019", "requires_lifecycle"),
            ("MATH-018", "MATH-001", "uses_basis"),
            ("VIS-009", "MATH-009", "uses_geometry"),
            ("VIS-029", "VIS-024", "uses_control_protocol"),
            ("VIS-029", "VIS-027", "requires_render_graph"),
            ("VIS-030", "VIS-024", "uses_control_protocol"),
            ("VIS-030", "VIS-027", "requires_render_graph"),
        ]
        for link in links:
            db.execute("INSERT OR IGNORE INTO card_links(from_id,to_id,relation) VALUES(?,?,?)", link)
        for test in TESTS:
            db.execute("INSERT OR REPLACE INTO retrieval_tests(id,query,intent,expected_domains,forbidden_domains,expected_cards,forbidden_cards,notes) VALUES(?,?,?,?,?,?,?,?)", test)
        # FTS content is external to cards and must be rebuilt after authored changes.
        db.execute("DELETE FROM card_search")
        db.execute("INSERT INTO card_search(id,title,summary,guidance) SELECT id,title,summary,guidance FROM cards")
        db.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('architecture_revision','generalized-visual-primitives-1')")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
