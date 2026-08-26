"""Regression tests for dcore.pack (formerly the standalone dscpack tool).

Ported as-is: same scenarios, same assertions. Only the imports changed to
the split modules (dcore.pack.release, dcore.pack.direct).
"""

from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from dcore.pack.direct import direct_deploy, restore_direct, verify_direct
from dcore.pack.release import build_release, restore_release, verify_release


class DscPackTests(unittest.TestCase):
    def test_release_restores_original_bytes_and_obfuscates_references(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            source.mkdir()
            original = (
                "import:\n"
                "  java.lang.String as S\n"
                "alpha_task:\n"
                "  type: task\n"
                "  script:\n"
                "    # private comment\n"
                "    - run beta_task\n"
                "beta_task:\n"
                "  type: task\n"
                "  script:\n"
                "    - narrate <script[alpha_task].name>\n"
                "    - ~run alpha_task\n"
                "    - spawn beta_task <player.location>\n"
            ).encode("utf-8")
            (source / "sample.dsc").write_bytes(original)
            release = root / "release.dcp.zip"
            master = b"k" * 32
            build_release([source], release, master, "test")
            verify_release(release, master)
            with zipfile.ZipFile(release) as archive:
                executable = b"\n".join(archive.read(name) for name in archive.namelist() if name.endswith(".dsc"))
            self.assertNotIn(b"alpha_task", executable)
            # ``spawn beta_task`` is an entity type, not a Denizen container
            # call. The semantic transformer deliberately keeps it stable
            # instead of applying an unsafe global target rewrite.
            self.assertIn(b"spawn beta_task", executable)
            restored = root / "restored"
            restore_release(release, restored, master)
            self.assertEqual((restored / "sample.dsc").read_bytes(), original)

    def test_queue_definitions_and_named_run_arguments_are_obfuscated(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            source.mkdir()
            original = (
                "caller:\n"
                "  type: world\n"
                "  script:\n"
                "    - define target <player>\n"
                "    - run worker def.target:<[target]>\n"
                "worker:\n"
                "  type: task\n"
                "  definitions: target\n"
                "  script:\n"
                "    - narrate <[target].name>\n"
            ).encode("utf-8")
            (source / "defs.dsc").write_bytes(original)
            release = root / "defs.dcp.zip"
            build_release([source], release, b"d" * 32, "defs")
            with zipfile.ZipFile(release) as archive:
                executable = b"\n".join(archive.read(name) for name in archive.namelist() if name.endswith(".dsc"))
            self.assertNotIn(b"define target", executable)
            self.assertNotIn(b"<[target]>", executable)
            self.assertNotIn(b"def.target:", executable)
            restored = root / "restored"
            restore_release(release, restored, b"d" * 32)
            self.assertEqual((restored / "defs.dsc").read_bytes(), original)

    def test_definemap_data_actions_and_loop_aliases_are_obfuscated(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            source.mkdir()
            original = (
                "worker:\n"
                "  type: world\n"
                "  script:\n"
                "    - definemap state:\n"
                "        phase: charging\n"
                "    - define state.phase:ready\n"
                "    - repeat 2 as:fill:\n"
                "        - define state.progress:<[fill]>\n"
                "        - narrate <[state].get[progress]>\n"
            ).encode("utf-8")
            (source / "maps.dsc").write_bytes(original)
            release = root / "maps.dcp.zip"
            build_release([source], release, b"m" * 32, "maps")
            with zipfile.ZipFile(release) as archive:
                executable = b"\n".join(archive.read(name) for name in archive.namelist() if name.endswith(".dsc"))
            self.assertNotIn(b"definemap state", executable)
            self.assertNotIn(b"define state", executable)
            self.assertNotIn(b"<[state]>", executable)
            self.assertNotIn(b"as:fill", executable)
            restored = root / "restored"
            restore_release(release, restored, b"m" * 32)
            self.assertEqual((restored / "maps.dsc").read_bytes(), original)

    def test_dynamic_run_targets_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            source.mkdir()
            (source / "dynamic.dsc").write_text(
                "caller:\n"
                "  type: world\n"
                "  script:\n"
                "    - run <[task_name]>\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "unsupported dynamic run target"):
                build_release([source], root / "dynamic.dcp.zip", b"x" * 32, "dynamic")

    def test_foreach_key_and_as_aliases_and_item_event_references_are_obfuscated(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            source.mkdir()
            original = (
                "custom_item:\n"
                "  type: item\n"
                "  material: stick\n"
                "caller:\n"
                "  type: world\n"
                "  script:\n"
                "    - foreach <list[a|b]> key:key_name as:value:\n"
                "        - narrate <[key_name]> <[value]>\n"
                "    - narrate done\n"
                "  events:\n"
                "    on player drops custom_item:\n"
                "      - narrate dropped\n"
            ).encode("utf-8")
            (source / "events.dsc").write_bytes(original)
            release = root / "events.dcp.zip"
            build_release([source], release, b"e" * 32, "events")
            with zipfile.ZipFile(release) as archive:
                executable = b"\n".join(archive.read(name) for name in archive.namelist() if name.endswith(".dsc"))
            self.assertNotIn(b"as:value", executable)
            self.assertNotIn(b"key:key_name", executable)
            self.assertIn(b"drops custom_item", executable)
            restored = root / "restored"
            restore_release(release, restored, b"e" * 32)
            self.assertEqual((restored / "events.dsc").read_bytes(), original)

    def test_direct_deploy_is_incremental_and_restores_each_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            item_path = source / "items" / "custom.dsc"
            task_path = source / "other" / "task.dsc"
            item_path.parent.mkdir(parents=True)
            task_path.parent.mkdir(parents=True)
            item_bytes = (
                "custom_item:\n"
                "  type: item\n"
                "  material: stick\n"
            ).encode("utf-8")
            task_bytes = (
                "caller:\n"
                "  type: world\n"
                "  events:\n"
                "    on player drops custom_item:\n"
                "      - narrate <item[custom_item].material>\n"
            ).encode("utf-8")
            item_path.write_bytes(item_bytes)
            task_path.write_bytes(task_bytes)
            deploy = root / "server_scripts"
            master = b"q" * 32
            direct_deploy([item_path], deploy, master, "direct", root)
            direct_deploy([task_path], deploy, master, "direct", root)
            verify_direct(deploy, master)
            executable = b"\n".join(path.read_bytes() for path in deploy.rglob("*.dsc"))
            self.assertIn(b"drops custom_item", executable)
            self.assertIn(b"<item[custom_item]", executable)
            task_bytes_updated = task_bytes.replace(b"narrate", b"narrate updated")
            task_path.write_bytes(task_bytes_updated)
            direct_deploy([task_path], deploy, master, "direct", root)
            restored = root / "restored"
            restore_direct(deploy, restored, master)
            self.assertEqual((restored / "source/items/custom.dsc").read_bytes(), item_bytes)
            self.assertEqual((restored / "source/other/task.dsc").read_bytes(), task_bytes_updated)

    def test_semantic_release_keeps_late_non_container_sections(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            source.mkdir()
            original = (
                "entry:\n"
                "  type: world\n"
                "  events:\n"
                "  - on server start:\n"
                "    - run worker\n"
                "worker:\n"
                "  type: task\n"
                "  script:\n"
                "  - stop\n"
                "settings:\n"
                "  keep: true\n"
            ).encode("utf-8")
            (source / "late.dsc").write_bytes(original)
            release = root / "late.dcp.zip"
            build_release([source], release, b"l" * 32, "late")
            with zipfile.ZipFile(release) as archive:
                executable = b"\n".join(archive.read(name) for name in archive.namelist() if name.endswith(".dsc"))
            self.assertIn(b"settings:\n  keep: true", executable)
            self.assertNotIn(b"\nworker:\n", executable)

    def test_balanced_mode_allows_identity_container_names(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            source.mkdir()
            original = (
                "entry:\n"
                "  type: world\n"
                "  events:\n"
                "  - on server start:\n"
                "    - run worker\n"
                "worker:\n"
                "  type: task\n"
                "  definitions: target\n"
                "  script:\n"
                "  - define target hello\n"
            ).encode("utf-8")
            (source / "balanced.dsc").write_bytes(original)
            release = root / "balanced.dcp.zip"
            build_release([source], release, b"b" * 32, "balanced", "balanced")
            with zipfile.ZipFile(release) as archive:
                executable = b"\n".join(archive.read(name) for name in archive.namelist() if name.endswith(".dsc"))
            self.assertIn(b"worker:", executable)
            self.assertNotIn(b"define target", executable)
            restored = root / "restored"
            restore_release(release, restored, b"b" * 32)
            self.assertEqual((restored / "balanced.dsc").read_bytes(), original)

    def test_orphan_task_is_rejected_in_hard_mode(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            source.mkdir()
            (source / "orphan.dsc").write_text(
                "orphan:\n"
                "  type: task\n"
                "  script:\n"
                "  - stop\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "unknown"):
                build_release([source], root / "orphan.dcp.zip", b"o" * 32, "orphan")

    def test_release_executable_tamper_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            source.mkdir()
            (source / "tamper.dsc").write_text(
                "entry:\n"
                "  type: world\n"
                "  events:\n"
                "  - on server start:\n"
                "    - narrate hello\n",
                encoding="utf-8",
            )
            release = root / "release.dcp.zip"
            build_release([source], release, b"t" * 32, "tamper")
            tampered = root / "tampered.dcp.zip"
            with zipfile.ZipFile(release, "r") as original, zipfile.ZipFile(tampered, "w") as output:
                for info in original.infolist():
                    data = original.read(info.filename)
                    if info.filename.endswith(".dsc"):
                        data += b"\n# tampered"
                    output.writestr(info, data)
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                verify_release(tampered, b"t" * 32)


if __name__ == "__main__":
    unittest.main()
