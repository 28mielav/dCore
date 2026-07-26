from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.build_gpt_bundle import KNOWLEDGE_FILES, build


class BundleTests(unittest.TestCase):
    def test_ready_bundle_separates_uploads_from_maintenance(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary:
            output = build(root, Path(temporary) / "dCore-0.30")
            self.assertEqual(set(KNOWLEDGE_FILES), {item.name for item in (output / "GPT_Knowledge").iterdir()})
            self.assertTrue((output / "GPT_Instructions" / "DCORE_INSTRUCTIONS.txt").is_file())
            self.assertTrue((output / "Maintenance" / "update_knowledge.py").is_file())
            self.assertTrue((output / "START_HERE.txt").is_file())
            self.assertIn("Action schema 1.3.0", (output / "START_HERE.txt").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
