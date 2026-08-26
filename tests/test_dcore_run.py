from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from dcore.gates.release import execute


class DcoreRunTests(unittest.TestCase):
    def run_project(self, script: str, **overrides: object) -> dict:
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=root / "temp") as temporary:
            path = Path(temporary) / "case.dsc"
            path.write_text(script, encoding="utf-8")
            defaults = {
                "paths": [path], "db": root / "knowledge" / "dcore.sqlite", "profile": "denizenm",
                "minecraft": "1.21.10", "paper": "1.21.10", "java": "21", "denizen_version": None,
                "denizenm": "7299M", "addon": [], "jar": [], "require_jar_evidence": False,
                "intent": "auto", "query": "narrate", "require_route": False,
                "decision": None, "runtime_report": None, "shadow_plan": None,
                "closed_world": False,
            }
            defaults.update(overrides)
            return execute(argparse.Namespace(**defaults))

    def test_static_pass_is_blocked_without_runtime(self) -> None:
        result = self.run_project("demo:\n  type: task\n  script:\n  - narrate ok\n")
        self.assertEqual("SYNTAX_PASS", result["proof"]["static"])
        self.assertEqual("RUNTIME_NOT_RUN", result["proof"]["runtime"])
        self.assertEqual("RELEASE_BLOCKED", result["verdict"])

    def test_closed_world_promotes_missing_script_to_error(self) -> None:
        result = self.run_project(
            "demo:\n  type: task\n  script:\n  - run missing_task\n",
            closed_world=True,
        )
        rows = [item for item in result["findings"] if item["code"] == "unresolved_script"]
        self.assertEqual(1, len(rows))
        self.assertEqual("error", rows[0]["severity"])
        self.assertEqual("SYNTAX_FAIL", result["proof"]["static"])

    def test_cli_json_is_utf8_on_windows_console(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=root / "temp") as temporary:
            path = Path(temporary) / "case.dsc"
            path.write_text("demo:\n  type: task\n  script:\n  - run missing_task\n", encoding="utf-8")
            process = subprocess.run(
                [
                    sys.executable, "-m", "dcore.gates.release", str(path),
                    "--db", str(root / "knowledge" / "dcore.sqlite"), "--minecraft", "1.21.10", "--denizenm", "7299M",
                ],
                capture_output=True,
                cwd=root,
            )
            self.assertNotEqual(0, process.returncode)
            payload = json.loads(process.stdout.decode("utf-8"))
            self.assertEqual("RELEASE_BLOCKED", payload["verdict"])

    def test_runtime_report_unlocks_simple_project(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=root / "temp") as temporary:
            report = Path(temporary) / "runtime.json"
            report.write_text(json.dumps({"status": "PASS", "cases": {case: "PASS" for case in ("reload", "quit", "death", "repeat_input", "cleanup")}}), encoding="utf-8")
            result = self.run_project("demo:\n  type: task\n  script:\n  - narrate ok\n", runtime_report=report)
        self.assertEqual("RUNTIME_PASS", result["proof"]["runtime"])
        self.assertEqual("READY", result["verdict"])

    def test_dog_runtime_matrix_is_required(self) -> None:
        result = self.run_project("dog_search:\n  type: task\n  script:\n  - walk <[wolf]> <player.location>\n")
        self.assertIn("water_boundary", result["runtime_checklist"])
        self.assertIn("no_progress", result["runtime_checklist"])

    def test_gravity_runtime_matrix_is_required(self) -> None:
        result = self.run_project("gravity_gun: capture target\n")
        self.assertIn("capture", result["runtime_checklist"])
        self.assertIn("release", result["runtime_checklist"])
        self.assertIn("world_change", result["runtime_checklist"])

    def test_treasure_session_matrix_is_required(self) -> None:
        result = self.run_project("treasure_session: group of four players\n")
        self.assertIn("group_size_4", result["runtime_checklist"])
        self.assertIn("session_isolation", result["runtime_checklist"])
        self.assertIn("worker_loss", result["runtime_checklist"])

    def test_complex_provider_requires_route_artifact(self) -> None:
        result = self.run_project("demo:\n  type: task\n  script:\n  - define name <invoke[player.getName()]>\n", query="Reflect provider work", addon=["reflect@2.4.2"])
        self.assertEqual("ROUTE_REQUIRED", result["proof"]["route"])
        self.assertEqual("RELEASE_BLOCKED", result["verdict"])

    def test_complex_provider_rejects_fake_route_artifact(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=root / "temp") as temporary:
            decision = Path(temporary) / "decision.json"
            decision.write_text(json.dumps({"tool": "dcore_design", "status": "READY_FOR_PROOF"}), encoding="utf-8")
            result = self.run_project(
                "demo:\n  type: task\n  script:\n  - define name <invoke[player.getName()]>\n",
                query="Reflect provider work", addon=["reflect@2.4.2"], decision=decision,
            )
        self.assertEqual("ROUTE_INVALID", result["proof"]["route"])

    def test_shadow_failure_blocks_even_before_minecraft_runtime(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=root / "temp") as temporary:
            plan = Path(temporary) / "plan.json"
            plan.write_text(json.dumps({"group_size": 1, "workers": [{"id": "a", "max_sessions": 1}], "operations": []}), encoding="utf-8")
            result = self.run_project("demo:\n  type: task\n  script:\n  - narrate ok\n", shadow_plan=plan)
        self.assertEqual("SIMULATION_INVALID", result["proof"]["simulation"])
        self.assertIn("SIMULATION_INVALID", result["blocked_by"])


if __name__ == "__main__":
    unittest.main()
