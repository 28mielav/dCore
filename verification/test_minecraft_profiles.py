"""Compatibility boundaries and virtual overlays across the supported range."""
import json
import pytest

from dcore.lint.resourcepack import Pack, lint_pack
from dcore.lint.shader_profiles import PROFILES


def codes(report):
    return {i["code"] for i in report["issues"]}


@pytest.mark.parametrize("version,fmt,schema,blocks,vertex_id", [
    ("1.16.5", 6, "legacy", False, False),
    ("1.17.1", 7, "legacy", False, False),
    ("1.18.2", 8, "legacy", False, False),
    ("1.19.4", 13, "legacy", False, False),
    ("1.20.1", 15, "legacy", False, False),
    ("1.20.6", 32, "legacy", False, False),
    ("1.21.1", 34, "legacy", False, False),
    ("1.21.2", 42, "program", False, False),
    ("1.21.4", 46, "program", False, False),
    ("1.21.5", 55, "direct", False, False),
    ("1.21.6", 63, "direct", True, False),
    ("1.21.8", 64, "direct", True, False),
    ("1.21.9", 69, "direct", True, True),
    ("1.21.11", 75, "direct", True, True),
    ("26.1.2", 84, "direct", True, True),
    ("26.2", 88, "direct", True, True),
])
def test_exact_client_boundaries(version, fmt, schema, blocks, vertex_id):
    p = PROFILES[version]
    assert (p["resource_format"], p["post_schema"], p["uniform_blocks"], p["post_vertex_id"]) == (fmt, schema, blocks, vertex_id)
    assert len(p["client_sha1"]) == 40 and len(p["post_graph_sha256"]) == 64


@pytest.mark.parametrize("version", sorted(PROFILES))
def test_every_indexed_release_has_scoped_structural_analysis(version):
    p = PROFILES[version]
    graph = {"targets": ["swap"] if p["post_schema"] == "legacy" else {"swap": {}}, "passes": []}
    report = lint_pack(Pack("fixture", {p["post_graph"]: json.dumps(graph).encode()}), minecraft=version)
    assert "shader_schema_unverified" not in codes(report)
    assert report["scope"]["client_sha1"] == p["client_sha1"]
    assert report["runtime_verdict"] == "RUNTIME_UNVERIFIED"


def test_unknown_future_target_is_not_guessed_from_version_number():
    graph = b'{"targets":{},"passes":[]}'
    report = lint_pack(Pack("fixture", {"assets/test/post_effect/test.json": graph}), minecraft="27.9")
    assert "shader_schema_unverified" in codes(report)
    assert report["scope"]["client_sha1"] is None


def test_vanilla_stage_and_import_removals_have_exact_target_scope():
    source = "assets/minecraft/shaders/core/rendertype_item_entity_translucent_cull.vsh"
    assert source in PROFILES["1.21.11"]["shader_files"]
    assert source not in PROFILES["26.2"]["shader_files"]
    pack = Pack("fixture", {"assets/test/shaders/core/test.vsh": b"#moj_import <minecraft:does_not_exist.glsl>"})
    assert "vanilla_moj_import_unavailable" in codes(lint_pack(pack, minecraft="26.2"))


def test_target_overlays_select_only_active_files_and_last_wins():
    graph_path = "assets/test/post_effect/test.json"
    metadata = {"pack": {"pack_format": 64, "supported_formats": [64, 64], "min_format": 64, "max_format": 88},
                "overlays": {"entries": [
                    {"directory": "modern", "formats": [69, 88], "min_format": 69, "max_format": 88},
                    {"directory": "latest", "formats": [88, 88], "min_format": 88, "max_format": 88}]}}
    old = {"targets": {"swap": {}}, "passes": [{"vertex_shader": "test:post/quad", "fragment_shader": "minecraft:post/blit",
           "inputs": [{"target": "minecraft:main", "sampler_name": "In"}], "output": "swap", "uniforms": {}}]}
    modern = json.loads(json.dumps(old))
    modern["passes"][0]["vertex_shader"] = "minecraft:core/screenquad"
    files = {"pack.mcmeta": json.dumps(metadata).encode(), graph_path: json.dumps(old).encode(),
             "assets/test/shaders/post/quad.vsh": b"in vec3 Position; void main(){gl_Position=vec4(Position,1.0);}",
             "modern/" + graph_path: json.dumps(modern).encode(),
             "latest/" + graph_path: b'{"targets":{},"passes":[]}'}
    # Inactive broken files must not break another target.
    files["latest/assets/test/shaders/post/bad.json"] = b"broken"
    for version, overlays in (("1.21.8", []), ("1.21.11", ["modern"])):
        result = lint_pack(Pack("fixture", files), minecraft=version)
        assert result["static_verdict"] == "STATIC_OK", result["issues"]
        assert result["scope"]["applied_overlays"] == overlays
    result = lint_pack(Pack("fixture", files), minecraft="26.2")
    assert "invalid_json" in codes(result)
    assert result["scope"]["applied_overlays"] == ["modern", "latest"]


def test_old_client_ignores_overlay_assets():
    files = {"pack.mcmeta": b'{"pack":{"pack_format":6},"overlays":{"entries":[{"directory":"new","formats":88}]}}',
             "new/assets/test/post_effect/broken.json": b"broken"}
    assert "invalid_json" not in codes(lint_pack(Pack("fixture", files), minecraft="1.16.5"))


@pytest.mark.parametrize("version,unavailable", [("1.16.5",True),("1.18.2",True),("1.19.3",True),("1.19.4",False),("1.21.11",False),("26.2",False)])
def test_new_visual_entities_do_not_leak_to_older_servers(version, unavailable):
    from dcore.lint.script import MetaIndex, lint_text
    meta = MetaIndex(None, "official", set(), target={"minecraft": version})
    report = lint_text("demo:\n  type: task\n  script:\n  - spawn item_display <player.location>\n", meta)
    assert ("visual_entity_version_unavailable" in {i["code"] for i in report}) == unavailable


def test_empty_graph_still_checks_path_and_target_shape():
    report = lint_pack(Pack("fixture", {"assets/test/shaders/post/test.json": b'{"targets":[],"passes":[]}'}), minecraft="1.21.11")
    assert {"shader_graph_path_mismatch", "shader_target_schema_mismatch"} <= codes(report)
    report = lint_pack(Pack("fixture", {"assets/test/post_effect/test.json": b'{"passes":[]}'}), minecraft="1.21.11")
    assert "shader_target_schema_mismatch" not in codes(report)
