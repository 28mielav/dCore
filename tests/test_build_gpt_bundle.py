from __future__ import annotations

import shutil
import unittest
from pathlib import Path

from dcore.release.bundle_gpt import KNOWLEDGE_UPLOAD, PACKAGE_ARCHIVE, build


class BundleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).resolve().parents[1]
        self.output = self.root / "temp" / "test-gpt-bundle"
        self.candidate = self.root / "temp" / "test-candidate-knowledge"

    def tearDown(self) -> None:
        if self.output.exists():
            shutil.rmtree(self.output)
        if self.candidate.exists():
            shutil.rmtree(self.candidate)

    def test_ready_bundle_separates_uploads_from_maintenance(self) -> None:
        output = build(self.root, self.output)
        self.assertEqual(
            set(KNOWLEDGE_UPLOAD) | {"dcore_bootstrap.py"},
            {item.name for item in (output / "Knowledge").iterdir()},
        )
        self.assertTrue((output / "Instructions" / "DCORE_INSTRUCTIONS.txt").is_file())
        self.assertTrue((output / "Maintenance" / "validation_contract.json").is_file())
        self.assertTrue((output / "START_HERE.txt").is_file())
        self.assertIn("Action schema 1.3.0", (output / "START_HERE.txt").read_text(encoding="utf-8"))

    def test_refuses_to_delete_arbitrary_directory(self) -> None:
        with self.assertRaises(ValueError):
            build(self.root, self.root / "knowledge")

    def test_candidate_layout_uses_root_release_references(self) -> None:
        self.candidate.mkdir(parents=True)
        for name in ("dcore.sqlite", "manifest.json", "DCORE_INSTRUCTIONS.txt", "lint_contract.example.json", "pool4_golden_corpus.json"):
            shutil.copy2(self.root / "knowledge" / name, self.candidate / name)
        output = build(self.root, self.output, self.candidate)
        self.assertTrue((output / "Action" / "openapi.yaml").is_file())
        self.assertTrue((output / "Maintenance" / "visual_sources.json").is_file())

    def test_rejects_candidate_that_does_not_match_its_verified_manifest(self) -> None:
        self.candidate.mkdir(parents=True)
        for name in ("dcore.sqlite", "manifest.json", "DCORE_INSTRUCTIONS.txt", "lint_contract.example.json", "pool4_golden_corpus.json"):
            shutil.copy2(self.root / "knowledge" / name, self.candidate / name)
        with (self.candidate / "DCORE_INSTRUCTIONS.txt").open("a", encoding="utf-8") as handle:
            handle.write("stale candidate")
        with self.assertRaises(ValueError):
            build(self.root, self.output, self.candidate)


if __name__ == "__main__":
    unittest.main()
