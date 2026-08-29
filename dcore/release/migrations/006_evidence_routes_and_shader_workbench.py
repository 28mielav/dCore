from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


CARDS = [
    (
        "CORE-021", "core", "route_decision", "Complex work requires an evidence-backed route decision",
        "A plausible first route is not a design decision; compare viable routes and retain the rejection evidence.",
        "Before non-trivial implementation, state capabilities and hard constraints, obtain at least two genuinely different candidates when they exist, reject incompatible version/provider routes, then compare evidence strength, native support, blast radius, lifecycle risk, bounded cost and complexity. Use dcore_design.py. A tie or missing proof produces INCOMPLETE and a focused proof task, not an invented winner.",
        "Reject prose-only route claims, fake alternatives that differ only by naming, weighted scores that can hide a hard violation, or code written before the selected route has owners and verification.",
        "Attach decision JSON, evidence IDs, rejected routes and proof gaps. After coding, verify the implementation against the selected route invariants.",
        "Version-neutral decision protocol; candidate evidence remains version-sensitive", "core", 100, 1,
        "dCore 0.29 deterministic route-decision protocol",
    ),
    (
        "VER-010", "verification", "contrast_fixture", "Good and bad examples are executable contrast evidence",
        "A style rule becomes reliable only when a bad fixture triggers it and the corrected fixture does not.",
        "Retrieve at most the most relevant contrast pair. Use the bad snippet only as a labelled negative fixture. Tie each pair to an invariant, diagnostic code and verification step. When adding a lint rule, add both sides and test false-positive boundaries.",
        "Reject unlabeled bad code, examples with different behavior, aesthetic-only rewrites, or a good example that passes only because the risky feature was removed.",
        "Run the bad and good fixture against the same tool/profile; require the expected diagnostic only on the bad side.",
        "Fixture and linter revision sensitive", "core", 100, 1,
        "dCore 0.29 executable contrast corpus",
    ),
    (
        "VIS-033", "visual", "shader_diagnostics", "Instrument the actual render route before editing a shader",
        "A route/variable/vertex probe turns guessed shader placement into observable evidence.",
        "Build a disposable diagnostic pack that assigns distinct route colors or prints selected shader variables and vertex IDs. Test marked and unmarked controls, reload with F3+T, record graphics mode and remove the probe from production. Use VariablesViewer as a licensed diagnostic pattern, not as proof that historical filenames still exist.",
        "Reject choosing a core shader from entity type alone, shipping the debug override, or calling a route proven after testing only the marked object.",
        "dcore_rp_lint route census, temporary probe plan, one marked control, one ordinary control and client screenshot/log.",
        "Minecraft client render-route and pack-format sensitive", "high", 100, 1,
        "midorikuma/VariablesViewer@52b227a1b9a20015465b75f72b254b391c48640a (MIT), normalized diagnostic mechanism",
    ),
    (
        "VIS-034", "visual", "control_protocol", "Shader controls use a reserved, viewer-scoped protocol",
        "Marker values, buffer cells and reset behavior form a protocol, not a cosmetic particle trick.",
        "Reserve channel values and screen-buffer cells centrally. Define encoding range, sampling/filtering assumptions, viewer visibility, collision policy, update rate and reset. Keep ordinary unmarked content on the vanilla branch. Multiple effects allocate non-overlapping channels and declare ownership.",
        "Reject global carriers for per-player state, exact color matching through an uncontrolled filtered path, duplicate channel allocation, or an effect with no reset owner.",
        "Two viewers with different values, unmarked control, carrier removal, reload/world-change reset and channel collision scan.",
        "Historical examples require target-version re-derivation", "high", 100, 1,
        "ShaderSelectorV2 and common-shaders mechanism synthesis; code from unlicensed common-shaders is not redistributed",
    ),
    (
        "VIS-035", "visual", "postprocess", "Bloom and star glare are explicit bounded render graphs",
        "Bright extraction, reduced-resolution filtering and composite are separate stages; directional glare is not merely stronger blur.",
        "Define selection or luminance threshold, downsample targets, separable or directional filter passes, composite order, alpha handling and target ownership. Budget target resolution, passes and texture taps. Starburst uses directional streak kernels or anisotropic passes after extraction; preserve a no-effect control path.",
        "Reject full-resolution wide-kernel blur by default, feedback through the same target, applying bloom to every bright UI pixel accidentally, or promising identical behavior across graphics modes without proof.",
        "Static render-graph scan, target-size/pass/sample budget, black/bright/unmarked controls and client FPS comparison.",
        "Post schema, targets and graphics-mode sensitive", "high", 100, 1,
        "JNNGL/vanilla-shaders bloom historical mechanism plus graphics engineering synthesis",
    ),
    (
        "VIS-036", "visual", "temporal_postprocess", "Temporal effects own previous-frame state and invalidation",
        "Phosphor, motion blur and accumulation require explicit history buffers and reset conditions.",
        "Separate current and previous-frame targets. Define initialization, resize, pack reload, world/camera discontinuity, effect disable and strength decay. Never read an uninitialized history target. Treat camera teleport and dimension change as invalidation boundaries.",
        "Reject same-target feedback, permanent ghost frames after reset, server tick loops pretending to provide frame history, or temporal state shared between viewers.",
        "First-frame, resize, F5, teleport, world change, disable and reload tests; report runtime unverified until client-tested.",
        "Post pipeline and target schema sensitive", "high", 100, 1,
        "ShaderSelectorV2 phosphor previous-frame mechanism and JNNGL motion-blur historical mechanism",
    ),
    (
        "VIS-037", "visual", "colored_light", "Colored glow, surface tint and scene lighting are different capabilities",
        "A colored screenshot does not prove spatial colored lighting, occlusion or propagation.",
        "Classify the goal as emissive/glow, selected-surface recolor, screen-space light accumulation or world-aware lighting approximation. For spatial lighting define source encoding, attenuation, normals/depth, occlusion limits, maximum sources and blend rule. State Fabulous and transparency limitations explicitly.",
        "Reject calling bloom colored lighting, claiming block-light propagation without world data, unbounded source loops, or importing an old 1.21.3 pack as current code.",
        "Single-source colors, overlap, distance falloff, occluder, translucent/water, source cap and graphics-mode matrix.",
        "JNNGL colored-lights example is native 1.21.3 and Fabulous; port required", "high", 100, 1,
        "JNNGL/vanilla-shaders@d1ec6c4a432c4ce116d65b10ca4f91d421165d0e (MIT), version-scoped mechanism",
    ),
    (
        "VIS-038", "visual", "rp_static_analysis", "Validate the final merged resource pack as one program",
        "Individual JSON and GLSL files can be valid while their merged include, target and override graph is broken.",
        "Run dcore_rp_lint.py on the final directory or ZIP. Resolve moj_import paths, parse shader/post JSON, inventory route overrides, detect missing/case-colliding assets, target hazards, duplicate marker channels and provider collisions. Static success remains RUNTIME_UNVERIFIED.",
        "Reject linting only the custom namespace, ignoring merge order, treating JSON parse success as render proof, or leaving diagnostic shaders in production.",
        "Machine-readable RP report with zero errors, reviewed warnings, route census and manual client proof checklist.",
        "Minecraft pack layout and shader schema sensitive", "high", 100, 1,
        "dCore 0.29 resource-pack workbench",
    ),
    (
        "VIS-039", "visual", "source_provenance", "Shader sources remain pinned, licensed and version-scoped",
        "Public code is evidence only within its license, commit and native client scope.",
        "Record repository, exact commit, license status, source path, native version, graphics mode and ingest policy. Extract mechanisms into generalized cards. A missing license permits analysis of facts but blocks code redistribution. An upstream change creates review_pending rather than silently rewriting verified knowledge.",
        "Reject raw repository dumps into GPT Knowledge, unpinned snippets, missing-license copying, or combining foreign shader-loader syntax with vanilla core/post code.",
        "Source-registry validation, commit reachability, license gate and version-mismatch retrieval tests.",
        "Per-source version scope", "high", 100, 1,
        "Pinned public repository registry in dcore/knowledge/data/visual_sources.json",
    ),
    (
        "VIS-040", "visual", "custom_particle", "Custom particle atlases share one core-shader boundary",
        "Particle color and header pixels may encode atlas selection and metadata, but competing particle shader overrides must be merged deliberately.",
        "Reserve the encoding range, preserve ordinary particles, validate atlas bounds and header semantics, and merge exactly once at particle.vsh. Keep collision and gameplay independent from rendered particle pixels.",
        "Reject multiple packs overwriting particle.vsh, gameplay depending on particle visibility, or assuming a 1.20.5 example matches a later core shader interface.",
        "Ordinary-particle control, every atlas edge, age frames, scale metadata and final override census.",
        "Repository states Minecraft 1.20.5+; exact target core shader still requires proof", "high", 90, 1,
        "ps-dps/mc-Charcoal@24a8bf33c67faf707650a5d36a251112a7862a93 (MIT), normalized mechanism",
    ),
    (
        "PERF-011", "performance", "gpu_budget", "GPU effects declare targets, passes, taps and covered pixels",
        "Shader cost is measurable even when the server cost is nearly zero.",
        "For each effect list render-target dimensions, pass count, texture samples per output pixel, expected screen coverage, temporal buffers and graphics modes. Prefer reduced-resolution intermediate targets and bounded source counts. Compare disabled and enabled client frame time.",
        "Reject performance claims based on entity count alone, an unspecified blur radius, or server TPS as proof of client GPU cost.",
        "Static budget plus repeatable client frame-time comparison at fixed scene, resolution and graphics mode.",
        "GPU/client dependent", "high", 100, 1,
        "dCore shader performance budget synthesis",
    ),
]


CONTRASTS = [
    ("CX-DEN-001", "denizen", "Global slime damage listener", "event_blast_radius", "on player damages slime:\n- determine cancelled", "on player damages slime:\n- stop if:!<context.entity.has_flag[treasure_hitbox]>\n- run treasure_dig def:<context.entity>", "The bad handler changes every slime on the server.", "A broad matcher must prove role identity before mutation.", "Bad emits event_blast_radius; good does not."),
    ("CX-DEN-002", "denizen", "Nested branch ladder", "branch_density", "- if <[a]>:\n  - if <[b]>:\n    - if <[c]>:\n      - run work", "- stop if:!<[a]>\n- stop if:!<[b]>\n- stop if:!<[c]>\n- run work", "The normal path is hidden inside nesting.", "Independent rejection rules are guard clauses.", "Maintainability nesting decreases without behavior change."),
    ("CX-DEN-003", "denizen", "Duplicated session truth", "state_writer_count", "- flag player target:<[id]>\n- flag <[wolf]> target:<[id]>\n- flag <[hitbox]> target:<[id]>", "- flag server treasure_records.<[id]>:<[record]>\n- flag <[wolf]> active_treasure:<[id]>", "Three copies can diverge.", "One authoritative record owns connected state; other objects hold narrow lookup references.", "Writer inventory names exactly one authoritative writer."),
    ("CX-DEN-004", "denizen", "Per-object tick queue", "unbounded_active_loop", "- while true:\n  - chunkload <[location].chunk> duration:1m\n  - wait 1t", "on player enters chunk:\n- run restore_loaded_visuals def:<context.chunk>", "Dormant objects create permanent work and chunk tickets.", "Dormant state is event-driven and indexed.", "No hidden-object queue or forced chunk load."),
    ("CX-DEN-005", "denizen", "Mixed movement controllers", "movement_owner_conflict", "- walk <[wolf]> <[target]>\n- repeat 20:\n  - push <[wolf]> ...\n  - wait 1t", "- walk <[wolf]> stop\n- push <[wolf]> ...\n- wait 1s\n- run resume_navigation", "Navigation and scripted impulse fight for velocity.", "Only one movement controller owns the entity at a time.", "One impulse, bounded session, explicit restore."),
    ("CX-DEN-006", "denizen", "Item reconstruction", "partial_item_rebuild", "- give diamond_sword[custom_model_data=2]", "- define item <context.item>\n- adjust def:item custom_model_data:2\n- inventory set origin:<[item]> slot:<player.held_item_slot>", "Reconstruction discards unknown components.", "Derive from the full ItemTag and commit once.", "Unknown components survive the good fixture."),
    ("CX-DEN-007", "denizen", "Scattered Reflect calls", "provider_boundary", "on player clicks:\n- reflect object:... method:...", "reflect_adapter:\n  type: task\n  script:\n  - reflect object:... method:...", "Volatile Java signatures leak into gameplay handlers.", "Reflect is one isolated adapter after native capability lookup.", "Provider inventory shows one Reflect boundary."),
    ("CX-DEN-008", "denizen", "Native capability bypass", "native_first", "- execute as_server \"some workaround\"", "- walk <[wolf]> stop", "A workaround is chosen without checking installed DenizenM Meta.", "Exact native DenizenM capability wins when it satisfies the contract.", "Decision evidence contains the DenizenM Meta entry."),
    ("CX-DEN-009", "denizen", "Duplicated stage cases", "duplicate_command_shape", "- choose <[step]>:\n  - case 1: ...\n  - case 2: ...\n  - case 3: ...", "- define stage <script[data].data_key[stages.<[step]>]>\n- run apply_stage def:<[stage]>", "Value-only differences are copied as control flow.", "Data-driven stages share one transition implementation.", "Each stage has one writer and one commit path."),
    ("CX-DEN-010", "denizen", "GUI snapshot owns stock", "stale_snapshot_commit", "on player closes inventory:\n- flag server stock:<context.inventory.list_contents>", "on player clicks shop_inventory:\n- run purchase_transaction def:<context.slot>", "Closing an old view can overwrite current shared state.", "GUI renders authoritative state and never commits a full stale snapshot.", "Two-player last-item test preserves stock and payment."),
    ("CX-DEN-011", "denizen", "Cleanup copied into events", "duplicated_cleanup", "on player quits: ...remove...\non player dies: ...remove...\non player changes world: ...remove...", "on player quits:\n- run session_cleanup def:<player>|quit\non player dies:\n- run session_cleanup def:<player>|death", "Cleanup branches drift.", "Events dispatch reasons to one idempotent cleanup owner.", "Repeated cleanup is safe and leaves no state."),
    ("CX-DEN-012", "denizen", "Huge event handler", "handler_size", "on player right clicks entity:\n- if ...\n- else if ...\n- else if ...\n- ...", "on player right clicks entity:\n- stop if:!<context.entity.has_flag[role]>\n- run role_dispatch def:<context.entity>", "The entry point owns validation, phases and provider work.", "World events validate identity and dispatch to a cohesive owner.", "Handler budget and responsibility inventory pass."),
    ("CX-VIS-001", "visual", "Guessed shader route", "rp_route_unproven", "Edit rendertype_item_entity_translucent_cull.fsh because the carrier is an item display.", "Run route census/probe on the final pack, then edit the observed route.", "Entity class does not prove the client render route.", "Render route is observed in the exact merged pack.", "Marked and ordinary controls identify the route."),
    ("CX-VIS-002", "visual", "Fragile exact marker", "marker_protocol", "if (color == vec4(15,15,15,150)) effect();", "Decode a reserved channel only after proving lossless sampling; preserve an unmarked branch and reset.", "Filtering and conversion can change exact values.", "Marker encoding is an owned versioned protocol.", "Channel collision, filtering and unmarked controls pass."),
    ("CX-VIS-003", "visual", "Wide full-resolution blur", "gpu_unbounded_blur", "for (int i=-64;i<=64;i++) sum += texture(Main, uv+i*px);", "Extract bright pixels, downsample, use bounded separable passes, then composite.", "The bad route spends a wide kernel on every full-resolution pixel.", "Blur cost is bounded by target size, pass count and taps.", "Static pass/tap budget and client frame-time test."),
    ("CX-VIS-004", "visual", "Post target feedback", "rp_target_feedback", "Read Main and write Main in the same pass.", "Read current target, write a distinct target, swap explicitly.", "Same-pass feedback is undefined or pipeline-specific.", "Post passes declare distinct input/output ownership.", "RP lint reports no hazardous read/write overlap."),
    ("CX-VIS-005", "visual", "Effect without reset", "visual_reset_missing", "Spawn a marker when enabled; never remove it.", "Session owns carrier, value, disable and quit/world/reload cleanup.", "The effect can leak after its gameplay lifetime.", "Every control path has an idempotent reset owner.", "Disable, quit, world change and reload tests."),
    ("CX-VIS-006", "visual", "Shared per-player carrier", "viewer_scope", "Spawn one real glowing entity for all players.", "Create viewer-only control carriers or another proven per-view transport.", "All clients receive the same state.", "Per-player visual parameters require viewer-scoped delivery.", "Two viewers hold different values without bleed."),
    ("CX-VIS-007", "visual", "World-space camera HUD", "camera_space", "Teleport a display near player location every tick.", "Use a proven camera/clip-space route or declare F5 limitations; attachment only handles tracking.", "World chasing jitters and does not define screen placement.", "Tracking and projection are separate responsibilities.", "Resize, FOV and F5 matrix."),
    ("CX-VIS-008", "visual", "Uninitialized temporal history", "temporal_history", "Mix current frame with Previous on the first frame.", "Initialize/invalidate Previous on enable, resize, reload, teleport and camera discontinuity.", "Garbage or stale frames enter the effect.", "Temporal history has explicit initialization and invalidation.", "First-frame and discontinuity tests."),
    ("CX-VIS-009", "visual", "Bloom called colored lighting", "capability_mismatch", "Blur bright green pixels and claim world colored light.", "Choose emissive, surface tint, screen-space accumulation or spatial lighting based on required attenuation and occlusion.", "Glow does not provide world-space illumination.", "The route must satisfy the requested lighting capability.", "Occluder, falloff and source-overlap tests."),
    ("CX-VIS-010", "visual", "Old pack presented as current", "version_scope", "Copy a native 1.21.3 shader into 1.21.11 and call it production.", "Pin source/version, inspect target assets/schema, port behind a proof boundary and test the merged pack.", "Shader paths and schemas change between versions.", "Historical mechanisms are not current API proof.", "Version mismatch is reported before code generation."),
    ("CX-VIS-011", "visual", "Foreign pipeline contamination", "pipeline_mismatch", "Paste Iris shaderpack syntax into a vanilla core shader pack.", "Keep foreign algorithms provider-labelled and re-derive them against the vanilla core/post interfaces.", "The runtime contracts are different.", "Provider syntax never crosses the adapter boundary unverified.", "Route/provider lint rejects the mismatch."),
    ("CX-VIS-012", "visual", "Debug override shipped", "debug_asset_leak", "Merge VariablesViewer diagnostic shaders into production assets.", "Generate a disposable probe pack, capture evidence, then lint production with probes excluded.", "Debug routes alter ordinary rendering and collide with production overrides.", "Instrumentation is temporary and independently owned.", "Production census contains no diagnostic assets."),
]


ROUTES = [
    ("ROUTE-DEN-NATIVE", "denizen", "Exact native DenizenM capability", "server_mutation", 100, "Exact installed build", ["exact_meta"], [], ["CORE-021", "ADD-001"], "Preferred when capability and semantics match; runtime remains final proof.", {"blast_radius": 1, "lifecycle_risk": 1, "complexity": 1}),
    ("ROUTE-DEN-OFFICIAL", "denizen", "Compatible official Denizen/Core capability", "server_mutation", 80, "Version/build compatibility required", ["official_meta", "compatibility_proof"], [], ["CORE-021", "ADD-001"], "Fallback only after fork compatibility is shown.", {"blast_radius": 1, "lifecycle_risk": 2, "complexity": 1}),
    ("ROUTE-DEN-ADDON", "addons", "Dedicated addon capability", "external_provider", 70, "Exact addon build", ["addon_meta"], [], ["CORE-021", "ADD-007"], "Keep behind one adapter and own its external session lifecycle.", {"blast_radius": 2, "lifecycle_risk": 2, "complexity": 2}),
    ("ROUTE-DEN-REFLECT", "addons", "Isolated Reflect adapter", "external_provider", 50, "Exact Java signature and installed jar", ["signature_proof"], ["native_capability_available"], ["CORE-021", "ADD-002"], "Last-mile boundary; never a guessed generic method.", {"blast_radius": 2, "lifecycle_risk": 3, "complexity": 3}),
    ("ROUTE-VIS-CORE", "visual", "Marked carrier through observed core route", "selective_material", 75, "Exact final client pack", ["route_census", "marker_protocol"], [], ["VIS-031", "VIS-033", "VIS-034"], "For selective procedural material or control extraction.", {"gpu_cost": 2, "compatibility_risk": 3, "complexity": 3}),
    ("ROUTE-VIS-POST", "visual", "Post render graph with viewer control channel", "fullscreen_effect", 80, "Exact post schema and graphics mode", ["post_route", "control_channel", "reset"], [], ["VIS-027", "VIS-034", "VIS-038"], "For fullscreen composition; declare Fabulous and target lifecycle.", {"gpu_cost": 3, "compatibility_risk": 3, "complexity": 4}),
    ("ROUTE-VIS-GLYPH", "visual", "Resource-pack glyph compositor", "screen_ui", 85, "Pack/font version", ["font_assets"], [], ["VIS-026"], "Good for authored screen UI; input and camera effects remain separate.", {"gpu_cost": 1, "compatibility_risk": 2, "complexity": 2}),
    ("ROUTE-VIS-CAMERA", "visual", "Camera/clip-space projection route", "camera_bound_ui", 70, "Observed camera uniforms/route", ["camera_source", "route_census"], [], ["VIS-023", "VIS-032", "VIS-033"], "Required for stable F5-aware geometry when glyph UI is insufficient.", {"gpu_cost": 2, "compatibility_risk": 4, "complexity": 4}),
    ("ROUTE-VIS-WORLD", "visual", "World display with explicit limitations", "world_visual", 90, "Display API build", ["display_api"], [], ["VIS-003"], "Use for world geometry, not as a fake fullscreen/camera route.", {"server_cost": 2, "compatibility_risk": 1, "complexity": 2}),
    ("ROUTE-VIS-HYBRID", "visual", "Server geometry plus client shader presentation", "portal_scanner", 85, "Server geometry and exact client pack", ["local_geometry", "route_census", "cleanup"], [], ["MATH-016", "VIS-007", "VIS-015", "VIS-038"], "Portal/scanner truth stays server-side while the shader owns presentation.", {"server_cost": 2, "gpu_cost": 2, "complexity": 4}),
]


def ensure_schema(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS visual_sources(
          source_id TEXT PRIMARY KEY, repository TEXT NOT NULL, url TEXT NOT NULL,
          branch TEXT NOT NULL, indexed_commit_sha TEXT NOT NULL, latest_seen_sha TEXT NOT NULL,
          license TEXT NOT NULL, license_status TEXT NOT NULL, ingest_policy TEXT NOT NULL,
          version_scope TEXT NOT NULL, pipelines_json TEXT NOT NULL, graphics_modes_json TEXT NOT NULL,
          modules_json TEXT NOT NULL, review_status TEXT NOT NULL, notes TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS contrast_examples(
          id TEXT PRIMARY KEY, domain TEXT NOT NULL, title TEXT NOT NULL,
          diagnostic_code TEXT NOT NULL, bad_snippet TEXT NOT NULL, good_snippet TEXT NOT NULL,
          bad_reason TEXT NOT NULL, invariant TEXT NOT NULL, verification TEXT NOT NULL,
          version_scope TEXT NOT NULL DEFAULT 'version-neutral principle',
          source_basis TEXT NOT NULL DEFAULT 'dCore executable contrast fixture', priority INTEGER NOT NULL DEFAULT 50);
        CREATE TABLE IF NOT EXISTS contrast_terms(
          example_id TEXT NOT NULL REFERENCES contrast_examples(id) ON DELETE CASCADE,
          term TEXT NOT NULL, weight INTEGER NOT NULL DEFAULT 1,
          PRIMARY KEY(example_id,term));
        CREATE TABLE IF NOT EXISTS route_patterns(
          id TEXT PRIMARY KEY, domain TEXT NOT NULL, title TEXT NOT NULL,
          capability TEXT NOT NULL, provider_rank INTEGER NOT NULL, version_scope TEXT NOT NULL,
          requires_json TEXT NOT NULL, forbids_json TEXT NOT NULL, evidence_cards_json TEXT NOT NULL,
          verification TEXT NOT NULL, cost_json TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS route_pattern_terms(
          route_id TEXT NOT NULL REFERENCES route_patterns(id) ON DELETE CASCADE,
          term TEXT NOT NULL, weight INTEGER NOT NULL DEFAULT 1,
          PRIMARY KEY(route_id,term));
        """
    )


def seed_sources(db: sqlite3.Connection, registry_path: Path) -> None:
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    for source in payload["sources"]:
        db.execute(
            """INSERT OR REPLACE INTO visual_sources VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                source["source_id"], source["repository"], source["url"], source["branch"],
                source["indexed_commit_sha"], source["indexed_commit_sha"], source["license"],
                source["license_status"], source["ingest_policy"], source["version_scope"],
                json.dumps(source["pipelines"], ensure_ascii=False),
                json.dumps(source["graphics_modes"], ensure_ascii=False),
                json.dumps(source["modules"], ensure_ascii=False), "indexed", source["notes"],
            ),
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path("dcore/knowledge/data/dcore.sqlite"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    with sqlite3.connect(args.db) as db:
        db.execute("PRAGMA foreign_keys=ON")
        ensure_schema(db)
        seed_sources(db, root / "dcore" / "knowledge" / "data" / "visual_sources.json")
        for card in CARDS:
            db.execute(
                "INSERT OR REPLACE INTO cards(id,domain,kind,title,summary,guidance,reject_when,verification,version_scope,confidence,priority,token_weight,source_basis) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                card,
            )
        for item in CONTRASTS:
            db.execute(
                "INSERT OR REPLACE INTO contrast_examples(id,domain,title,diagnostic_code,bad_snippet,good_snippet,bad_reason,invariant,verification) VALUES(?,?,?,?,?,?,?,?,?)",
                item,
            )
            terms = set((item[2] + " " + item[3] + " " + item[6] + " " + item[7]).lower().replace("/", " ").replace("_", " ").split())
            for term in terms:
                if len(term) >= 4:
                    db.execute("INSERT OR REPLACE INTO contrast_terms VALUES(?,?,1)", (item[0], term))
        contrast_aliases = {
            "CX-DEN-001": ["глобальный обработчик", "все слизни", "широкое событие", "blast radius"],
            "CX-DEN-002": ["if else каша", "вложенные if", "guard clauses"],
            "CX-DEN-003": ["много flags", "несколько владельцев", "authoritative state"],
            "CX-DEN-004": ["tick loop", "chunkload", "вечная очередь"],
            "CX-DEN-005": ["walk push", "собака странно летит", "movement ownership"],
            "CX-DEN-006": ["itemtag", "сохранить компоненты", "один commit"],
            "CX-DEN-007": ["reflect", "java adapter", "рефлект"],
            "CX-DEN-008": ["native denizenm", "нативная поддержка", "workaround"],
            "CX-DEN-009": ["стадии", "копипаста case", "data driven"],
            "CX-DEN-010": ["общий stock", "gui snapshot", "гонка покупки"],
            "CX-DEN-011": ["cleanup", "очистка во всех событиях"],
            "CX-DEN-012": ["огромный handler", "монолитное событие"],
            "CX-VIS-001": ["shader route", "шейдер не срабатывает", "variables viewer"],
            "CX-VIS-002": ["rgba marker", "точный цвет", "marker protocol"],
            "CX-VIS-003": ["bloom", "blur", "starburst", "gpu"],
            "CX-VIS-004": ["post target", "feedback", "render graph"],
            "CX-VIS-005": ["reset shader", "эффект не исчезает", "reload"],
            "CX-VIS-006": ["per player shader", "viewer only", "два игрока"],
            "CX-VIS-007": ["f5", "camera hud", "курсор меню"],
            "CX-VIS-008": ["previous frame", "motion blur", "phosphor"],
            "CX-VIS-009": ["цветной свет", "colored lights", "не bloom"],
            "CX-VIS-010": ["старый репозиторий", "версия шейдера", "портировать"],
            "CX-VIS-011": ["iris", "optifine", "чужой pipeline"],
            "CX-VIS-012": ["debug shader", "probe pack", "диагностический pack"],
        }
        for example_id, terms in contrast_aliases.items():
            for term in terms:
                db.execute("INSERT OR REPLACE INTO contrast_terms VALUES(?,?,8)", (example_id, term))
        for route in ROUTES:
            route_id, domain, title, capability, rank, scope, requires, forbids, cards, verification, cost = route
            db.execute(
                "INSERT OR REPLACE INTO route_patterns VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (route_id, domain, title, capability, rank, scope, json.dumps(requires), json.dumps(forbids), json.dumps(cards), verification, json.dumps(cost)),
            )
            terms = set((title + " " + capability + " " + domain).lower().replace("/", " ").replace("_", " ").split())
            for term in terms:
                if len(term) >= 3:
                    db.execute("INSERT OR REPLACE INTO route_pattern_terms VALUES(?,?,1)", (route_id, term))

        aliases = {
            "CORE-021": ["сравни", "сравни маршруты", "выбери маршрут", "варианты реализации", "route decision", "не бери первый вариант", "архитектурные альтернативы"],
            "VER-010": ["хороший и плохой код", "покажи как плохо", "contrast fixture", "good bad example", "самопроверка кода"],
            "VIS-033": ["variables viewer", "variablesviewer", "какой shader route", "визуализируй переменные", "vertex id", "route probe", "шейдер не срабатывает"],
            "VIS-034": ["marker channel", "control buffer", "управление шейдером", "per player shader", "viewer only shader", "для одного игрока"],
            "VIS-035": ["bloom", "starburst", "glare", "блюм", "свечение звездочкой", "пост шейдер свечение"],
            "VIS-036": ["motion blur", "phosphor", "previous frame", "temporal shader", "след прошлого кадра"],
            "VIS-037": ["colored lights", "цветной свет", "rgb lighting", "освещение разными цветами"],
            "VIS-038": ["shader lint", "resource pack lint", "resource pack", "проверь ресурс пак", "проверь конфликт", "particle.vsh", "портируй", "variablesviewer", "merged pack", "шейдер сломан"],
            "VIS-039": ["старый shader repo", "старый JNNGL", "портируй", "лицензия шейдера", "github shader source", "версия ресурс пака"],
            "VIS-040": ["custom particles", "кастомные частицы", "particle atlas", "header pixel"],
            "PERF-011": ["gpu budget", "стоимость шейдера", "texture samples", "shader fps", "render target budget"],
        }
        for card_id, terms in aliases.items():
            db.execute("INSERT OR REPLACE INTO card_activation_rules(card_id,min_hits) VALUES(?,1)", (card_id,))
            for term in terms:
                db.execute("INSERT OR IGNORE INTO card_terms VALUES(?,?)", (card_id, term))
                db.execute("INSERT OR IGNORE INTO card_activation_terms VALUES(?,?)", (card_id, term))
                db.execute("INSERT OR REPLACE INTO card_alias_terms VALUES(?,?,14)", (card_id, term))

        for term in ("post shader", "пост шейдер", "bloom", "starburst", "colored lights", "variables viewer", "shader route", "resource pack lint", "кастомные частицы"):
            db.execute("INSERT OR IGNORE INTO domain_terms(domain,term) VALUES('visual',?)", (term,))
        for term in ("gpu budget", "shader fps", "texture samples", "render target"):
            db.execute("INSERT OR IGNORE INTO domain_terms(domain,term) VALUES('performance',?)", (term,))
        for term in ("сравни маршруты", "варианты реализации", "route decision"):
            db.execute("INSERT OR IGNORE INTO domain_terms(domain,term) VALUES('core',?)", (term,))
        for term in ("shader lint", "проверь ресурс пак", "contrast fixture", "самопроверка"):
            db.execute("INSERT OR IGNORE INTO domain_terms(domain,term) VALUES('verification',?)", (term,))
        for intent, term, weight in (
            ("diagnose", "шейдер не работает", 20),
            ("teach", "хороший и плохой код", 20),
            ("performance_review", "GPU стоимость", 20),
            ("performance_review", "texture samples", 15),
            ("visual_design", "control buffer", 15),
            ("visual_design", "phosphor", 15),
            ("visual_design", "motion blur", 15),
            ("visual_design", "цветной свет", 15),
            ("visual_design", "loading screen", 15),
        ):
            db.execute("INSERT OR REPLACE INTO intent_terms(intent,term,weight) VALUES(?,?,?)", (intent, term, weight))
        for term in ("portal scanner", "наклонной плоскости"):
            db.execute("INSERT OR IGNORE INTO card_terms(card_id,term) VALUES('MATH-016',?)", (term,))
            db.execute("INSERT OR REPLACE INTO card_alias_terms(card_id,term,weight) VALUES('MATH-016',?,14)", (term,))
            db.execute("INSERT OR IGNORE INTO card_activation_terms(card_id,term) VALUES('MATH-016',?)", (term,))
        db.execute("INSERT OR REPLACE INTO card_activation_rules(card_id,min_hits) VALUES('MATH-016',1)")

        links = [
            ("CORE-021", "CORE-019", "supports_design", 0),
            ("CORE-021", "CORE-020", "supports_clean_architecture", 0),
            ("CORE-021", "VER-010", "supports_contrast_review", 0),
            ("VIS-033", "VIS-031", "requires_render_route", 1),
            ("VIS-034", "VIS-003", "requires_lifecycle", 1),
            ("VIS-035", "VIS-027", "requires_render_graph", 1),
            ("VIS-035", "PERF-011", "requires_gpu_budget", 1),
            ("VIS-036", "VIS-027", "requires_render_graph", 1),
            ("VIS-037", "PERF-011", "requires_gpu_budget", 1),
            ("VIS-038", "VIS-033", "requires_route_probe", 1),
            ("VIS-039", "VIS-012", "requires_client_scope", 1),
            ("VIS-040", "VIS-016", "requires_override_safety", 1),
        ]
        for link in links:
            db.execute("INSERT OR REPLACE INTO card_links VALUES(?,?,?,?)", link)

        tests = [
            ("AUTO16", "Сделай ахуенный post shader bloom со звездными лучами, но сначала сравни маршруты и проверь итоговый resource pack", "visual_design", "visual,core,verification,performance", "", "CORE-021,VIS-035,VIS-038,PERF-011", "", "Bloom route and proof."),
            ("AUTO17", "Шейдер не работает на item display: используй VariablesViewer и выясни фактический shader route", "diagnose", "visual,verification", "", "VIS-033,VIS-038", "", "Render-route probe."),
            ("AUTO18", "Нужен per player control buffer для тряски экрана и обязательный reset при reload", "visual_design", "visual,core", "", "VIS-034", "", "Viewer protocol."),
            ("AUTO19", "Сделай phosphor и motion blur через previous frame без утечек после телепорта", "visual_design", "visual,core", "", "VIS-036", "", "Temporal history."),
            ("AUTO20", "Сделай цветной свет как на скрине, но не называй обычный bloom освещением", "visual_design", "visual,performance", "", "VIS-037,PERF-011", "", "Lighting capability."),
            ("AUTO21", "Возьми старый JNNGL vanilla-shaders и портируй под точную новую версию, не копируй вслепую", "visual_design", "visual,verification", "", "VIS-039,VIS-038", "", "Version provenance."),
            ("AUTO22", "Добавь кастомные частицы через particle atlas и проверь конфликт particle.vsh", "visual_design", "visual,verification", "", "VIS-040,VIS-038", "", "Particle override."),
            ("AUTO23", "Перед rewrite собак сравни native DenizenM, addon и Reflect и докажи победителя", "refactor", "core,addons,verification", "", "CORE-021", "", "Native-first route decision."),
            ("AUTO24", "Покажи хороший и плохой код глобального обработчика слизней и прогони lint", "teach", "verification", "", "VER-010", "", "Contrast retrieval."),
            ("AUTO25", "Сделай portal scanner в наклонной плоскости плюс shader, серверная геометрия не должна зависеть от пикселей", "visual_design", "visual,math,core", "", "MATH-016", "", "Hybrid route."),
            ("AUTO26", "Полный loading screen, blink и fade для одного игрока с reset и проверкой F5", "visual_design", "visual,core", "", "VIS-029,VIS-034", "", "Fullscreen transitions."),
            ("AUTO27", "Оцени GPU стоимость post эффекта: passes targets texture samples и FPS", "performance_review", "performance,visual,core", "", "PERF-011", "", "GPU budget."),
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
        db.execute("INSERT OR REPLACE INTO metadata VALUES('name','dCore 0.29')")
        db.execute("INSERT OR REPLACE INTO metadata VALUES('architecture_revision','evidence-routes-shader-workbench-5')")
        db.execute("INSERT OR REPLACE INTO metadata VALUES('visual_source_registry','5 pinned public sources; license and version scoped')")
        db.execute("INSERT OR REPLACE INTO metadata VALUES('decision_protocol','dcore_design compare -> implement -> verify; INCOMPLETE on unresolved proof')")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
