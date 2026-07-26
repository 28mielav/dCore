from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from tools.dcore_rp_lint import Pack, lint_pack

VERTEX = """#version 150
in vec3 Position;
uniform mat4 ModelViewMat;
out vec2 texCoord;
void main() { texCoord = vec2(0.0); gl_Position = ModelViewMat * vec4(Position, 1.0); }
"""
FRAGMENT = """#version 150
in vec2 texCoord;
uniform sampler2D Sampler0;
out vec4 fragColor;
void main() { fragColor = texture(Sampler0, texCoord); }
"""


class ResourcePackLintTests(unittest.TestCase):
    def write(self, root: Path, relative: str, value: str) -> None:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8")

    def clean_pack(self, root: Path) -> None:
        self.write(root, "pack.mcmeta", json.dumps({"pack": {"pack_format": 34, "description": "test"}}))
        self.write(root, "assets/minecraft/shaders/core/demo.json", json.dumps({
            "vertex": "demo", "fragment": "demo", "attributes": ["Position"],
            "samplers": [{"name": "Sampler0"}], "uniforms": [{"name": "ModelViewMat"}],
        }))
        self.write(root, "assets/minecraft/shaders/core/demo.vsh", VERTEX)
        self.write(root, "assets/minecraft/shaders/core/demo.fsh", FRAGMENT)

    @staticmethod
    def codes(report: dict) -> set[str]:
        return {issue["code"] for issue in report["issues"]}

    def test_clean_pack_is_static_ok_but_runtime_unverified(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.clean_pack(root)
            report = lint_pack(Pack.open(root), minecraft="1.21.4", pack_format=34)
        self.assertEqual("STATIC_OK", report["static_verdict"])
        self.assertEqual("RUNTIME_UNVERIFIED", report["runtime_verdict"])
        self.assertIn("route-census", {check["id"] for check in report["proof_checklist"]})

    def test_json_stage_and_include_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write(root, "broken.json", "{")
            self.write(root, "assets/minecraft/shaders/core/a.json", json.dumps({"vertex": "a", "fragment": "missing"}))
            self.write(root, "assets/minecraft/shaders/core/a.vsh", "#moj_import <not_here.glsl>\n")
            codes = self.codes(lint_pack(Pack.open(root), minecraft="1.21.4"))
        self.assertTrue({"invalid_json", "missing_shader_stage_file", "missing_moj_import"} <= codes)

    def test_varying_and_target_hazards(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.clean_pack(root)
            self.write(root, "assets/minecraft/shaders/core/demo.fsh", "in vec3 texCoord; void main() {}")
            self.write(root, "assets/minecraft/shaders/post/test.json", json.dumps({
                "targets": ["a"],
                "passes": [{"intarget": "a", "outtarget": "a"}, {"intarget": "missing", "outtarget": "a"}],
            }))
            codes = self.codes(lint_pack(Pack.open(root), minecraft="1.21.4"))
        self.assertIn("varying_type_mismatch", codes)
        self.assertIn("shader_pass_read_write_hazard", codes)
        self.assertIn("unknown_shader_target", codes)

    def test_case_marker_and_route_conflicts(self) -> None:
        # A directory on Windows cannot contain these two paths, but a zip can.
        one = {"vertex": "x", "fragment": "x", "dcore_core_route": "entity", "dcore_marker_channel": "uv2"}
        two = {"vertex": "y", "fragment": "y", "dcore_core_route": "entity", "dcore_marker_channel": "uv2"}
        pack = Pack("case-test", {
            "Assets/X.txt": b"a", "assets/x.txt": b"b",
            "assets/minecraft/shaders/core/x.json": json.dumps(one).encode(),
            "assets/minecraft/shaders/core/y.json": json.dumps(two).encode(),
        })
        codes = self.codes(lint_pack(pack, pack_format=34))
        self.assertTrue({"path_case_collision", "conflicting_core_shader_route_override", "reserved_marker_channel_duplicate"} <= codes)

    def test_zip_input_and_cli_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "pack"
            root.mkdir()
            self.clean_pack(root)
            archive = Path(tmp) / "pack.zip"
            with zipfile.ZipFile(archive, "w") as bundle:
                for file in root.rglob("*"):
                    if file.is_file():
                        bundle.write(file, file.relative_to(root).as_posix())
            completed = subprocess.run(
                [sys.executable, "tools/dcore_rp_lint.py", str(archive), "--minecraft", "1.21.4", "--json"],
                capture_output=True, text=True, check=False,
            )
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertEqual("STATIC_OK", json.loads(completed.stdout)["verdict"])

    def test_modern_post_effect_and_namespaced_program(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.clean_pack(root)
            self.write(root, "assets/demo/shaders/fx/pass.json", json.dumps({
                "vertex": "demo:fx/pass", "fragment": "demo:fx/pass",
                "samplers": [{"name": "InSampler"}],
            }))
            self.write(root, "assets/demo/shaders/fx/pass.vsh", VERTEX)
            self.write(root, "assets/demo/shaders/fx/pass.fsh", FRAGMENT.replace("Sampler0", "InSampler"))
            self.write(root, "assets/minecraft/post_effect/demo.json", json.dumps({
                "targets": {"swap": {}},
                "passes": [{
                    "program": "demo:fx/pass",
                    "inputs": [{"sampler_name": "In", "target": "minecraft:main"}],
                    "output": "swap",
                }],
            }))
            report = lint_pack(Pack.open(root), minecraft="1.21.4", pack_format=34)
        self.assertEqual("STATIC_OK", report["static_verdict"])
        self.assertIn("assets/minecraft/post_effect/demo.json", report["route_census"]["modern_post_json"])


if __name__ == "__main__":
    unittest.main()
