import sqlite3
from pathlib import Path

from dcore.knowledge.retrieval import card_payload, resolve_meta
from dcore.lint.script import MetaIndex
from dcore.lint.tagtypes import build_index
from dcore.lint.resourcepack import Pack, lint_pack

DB = Path(__file__).resolve().parents[1] / "dcore/knowledge/data/dcore.sqlite"


def test_historical_flag_syntax_does_not_leak_between_versions():
    with sqlite3.connect(DB) as db:
        db.row_factory = sqlite3.Row
        old = resolve_meta(db, "flag", "denizen", denizen_version="1.1.4-source-7f9353e83")
        new = resolve_meta(db, "flag", "denizen", denizen_version="1.2.6-b1782")
        old_flag = next(x for x in old["matches"] if x["category"] == "command" and x["name"] == "Flag")
        new_flag = next(x for x in new["matches"] if x["category"] == "command" and x["name"] == "Flag")
        assert "duration:" in old_flag["syntax"] and "expire:" not in old_flag["syntax"]
        assert "expire:" in new_flag["syntax"]
        assert "denizencore_official_master" not in old["source_scope"]
        assert old["source_evidence"]


def test_missing_historical_core_cannot_inherit_current_commands():
    meta = MetaIndex(DB, "denizen", set(), target={"denizen": "nonexistent-build"})
    assert not meta.commands
    assert not meta.effective_source_ids
    assert meta.version_meta_missing
    assert not build_index(DB, set()).attributes


def test_code_cards_filter_target_and_include_complete_pack():
    with sqlite3.connect(DB) as db:
        old = card_payload(db, ["VER-002", "VIS-024"], {"denizen": "1.1.4-source-7f9353e83", "minecraft": "1.16.5"})
        examples = {e["example_id"]: e for c in old for e in c["code_examples"]}
        assert "duration:10s" in examples["legacy-flag-duration"]["files"]["temporary_flag.dsc"]
        assert examples["core-flag-expire"]["files"] == {}
        assert examples["outline-mask"]["status"] == "not_applicable"
        modern = card_payload(db, ["VIS-024"], {"minecraft": "1.21.8"})[0]["code_examples"][0]
        assert "pack.mcmeta" in modern["files"]
        assert "assets/minecraft/post_effect/entity_outline.json" in modern["files"]
        assert any(p.endswith(".fsh") for p in modern["files"])


def test_1165_rejects_new_shader_route_and_schema():
    pack = Pack("old", {"assets/demo/shaders/core/test.fsh": b"void main() {}",
        "assets/demo/post_effect/test.json": b'{"targets":{},"passes":[{"inputs":[],"output":"minecraft:main"}]}'})
    codes = {i["code"] for i in lint_pack(pack, minecraft="1.16.5")["issues"]}
    assert "core_shader_route_unavailable" in codes
    assert "shader_schema_mismatch" in codes


def test_lint_expiry_option_follows_selected_meta():
    from dcore.lint.script import lint_text
    old = MetaIndex(DB, "denizen", set(), target={"denizen": "1.1.4-source-7f9353e83"})
    newer = MetaIndex(DB, "denizen", set(), target={"denizen": "1.2.6-b1782"})
    def codes(option, meta):
        return {i["code"] for i in lint_text(f"task:\n  type: task\n  script:\n  - flag server active:true {option}:10s\n", meta)}
    assert "flag_expiry_version_mismatch" in codes("expire", old)
    assert "flag_expiry_version_mismatch" not in codes("duration", old)
    assert "flag_expiry_version_mismatch" in codes("duration", newer)
    assert "flag_expiry_version_mismatch" not in codes("expire", newer)
