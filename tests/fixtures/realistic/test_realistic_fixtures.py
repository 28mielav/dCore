from pathlib import Path
import unittest

from dcore.lint.script import lint_text

ROOT = Path(__file__).parent


class RealisticFixtureTests(unittest.TestCase):
    def test_realistic_denizenscript_fixtures_exercise_lint_rules(self) -> None:
        visual = lint_text((ROOT / "visual_controller.dsc").read_text(encoding="utf-8"))
        queue = lint_text((ROOT / "queue_probe.dsc").read_text(encoding="utf-8"))
        queue_codes = {item["code"] for item in queue}
        self.assertGreaterEqual(
            queue_codes,
            {"run_unknown_script", "unproven_loop_bound", "semantic_execution_limit"},
        )
        self.assertTrue(all("code" in item and "severity" in item and "line" in item for item in visual + queue))
        self.assertEqual([], visual)
