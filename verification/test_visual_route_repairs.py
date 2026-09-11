import json
import pytest
from dcore.lint.resourcepack import Pack, lint_pack
from dcore.lint.script import lint_text


def report(version, metadata, vertex="minecraft:core/screenquad", extra=None):
    files = {"pack.mcmeta": json.dumps({"pack": metadata}).encode(),
        "assets/test/post_effect/test.json": json.dumps({"targets": {"swap": {}}, "passes": [{
            "vertex_shader": vertex, "fragment_shader": "minecraft:post/blit",
            "inputs": [{"sampler_name": "In", "target": "minecraft:main"}], "output": "swap", "uniforms": {}}]}).encode()}
    files.update(extra or {})
    return lint_pack(Pack("fixture", files), minecraft=version)


def codes(result):
    return {i["code"] for i in result["issues"]}


def test_12111_is_known_and_builtin_stage_is_resolved():
    result = report("1.21.11", {"min_format": [75, 0], "max_format": 75})
    assert not codes(result) & {"shader_schema_unverified", "vanilla_shader_stage_not_in_pack", "vanilla_shader_stage_unavailable", "missing_shader_program"}
    assert result["runtime_verdict"] == "RUNTIME_UNVERIFIED"


def test_1218_does_not_inherit_12111_screenquad():
    assert "vanilla_shader_stage_unavailable" in codes(report("1.21.8", {"pack_format": 64}))


@pytest.mark.parametrize("metadata,expected", [
    ({"pack_format": 64}, "pack_format_range_required"),
    ({"min_format": [64, 0], "max_format": [64, 0]}, "pack_format_out_of_range"),
    ({"min_format": [76, 0], "max_format": [75, 0]}, "invalid_pack_format_range"),
    ({"min_format": True, "max_format": 75}, "pack_format_range_required"),
])
def test_real_mcmeta_is_checked(metadata, expected):
    assert expected in codes(report("1.21.11", metadata))


def test_old_post_vertex_buffer_is_not_accepted_on_12111():
    files = {"assets/test/shaders/post/quad.vsh": b"in vec3 Position; void main(){gl_Position=vec4(Position,1.0);}"}
    assert "post_vertex_interface_mismatch" in codes(report("1.21.11", {"min_format": 75, "max_format": 75}, "test:post/quad", files))
    assert "post_vertex_interface_mismatch" not in codes(report("1.21.8", {"pack_format": 64}, "test:post/quad", files))


def test_explicit_format_cannot_disagree_with_client():
    result = lint_pack(Pack("fixture", {"pack.mcmeta": b'{"pack":{"pack_format":64}}'}), minecraft="1.21.11", pack_format=64)
    assert "target_pack_format_mismatch" in codes(result)


def test_malformed_mcmeta_is_not_silently_skipped():
    assert "invalid_json" in codes(lint_pack(Pack("fixture", {"pack.mcmeta": b'{broken'}), minecraft="1.21.8"))


def test_camera_follow_warning_requires_actual_carrier_dataflow_and_loop():
    prefix = "demo:\n  type: task\n  script:\n  - spawn item_display save:marker\n  - define carrier <entry[marker].spawned_entity>\n"
    loop = "  - while true:\n    - teleport <[carrier]> <player.eye_location.forward[0.1]>\n    - wait 1t\n"
    assert "screen_carrier_tick_follow" in {i["code"] for i in lint_text(prefix + loop)}
    one_time = "  - teleport <[carrier]> <player.eye_location.forward[0.1]>\n"
    assert "screen_carrier_tick_follow" not in {i["code"] for i in lint_text(prefix + one_time)}
    reassigned = "  - define carrier <player>\n"
    assert "screen_carrier_tick_follow" not in {i["code"] for i in lint_text(prefix + reassigned + loop)}
    assert "display_mount_projection_unverified" in {i["code"] for i in lint_text(prefix + "  - mount <[carrier]>|<player>\n")}


def test_comments_and_narration_do_not_create_carriers():
    text = 'demo:\n  type: task\n  script:\n  # spawn item_display save:marker\n  - narrate "spawn item_display save:marker"\n  - define carrier <entry[marker].spawned_entity>\n  - while true:\n    - teleport <[carrier]> <player.eye_location>\n    - wait 1t\n'
    assert "screen_carrier_tick_follow" not in {i["code"] for i in lint_text(text)}


def test_reused_save_name_does_not_misclassify_non_display():
    text = "demo:\n  type: task\n  script:\n  - spawn item_display save:marker\n  - spawn pig save:marker\n  - define carrier <entry[marker].spawned_entity>\n  - while true:\n    - teleport <[carrier]> <player.eye_location>\n    - wait 1t\n"
    assert "screen_carrier_tick_follow" not in {i["code"] for i in lint_text(text)}
