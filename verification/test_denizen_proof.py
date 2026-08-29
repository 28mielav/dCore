from __future__ import annotations

import unittest

from dcore.semantics.ir import build_project_ir
from dcore.semantics.proof import prove_transformation
from dcore.semantics.transform import transform_project


SOURCE = """public_item:
  type: item
  material: stone
entry:
  type: world
  events:
  - on server start:
    - run worker
worker:
  type: task
  definitions: target
  script:
  - define target player
  - narrate <[target]>
settings:
  stable: true
"""


class DenizenProofTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project = build_project_ir({"main.dsc": SOURCE})
        self.result = transform_project(self.project, salt=b"proof", verify=False)

    def test_clean_transformation_proves_equivalent(self) -> None:
        proof = prove_transformation(self.project, self.result.files, self.result.renames)
        self.assertTrue(proof.passed)
        self.assertEqual((), proof.issues)

    def test_removed_nonsemantic_section_is_detected(self) -> None:
        changed = dict(self.result.files)
        changed["main.dsc"] = changed["main.dsc"].replace("settings:\n  stable: true\n", "")
        proof = prove_transformation(self.project, changed, self.result.renames)
        self.assertFalse(proof.passed)
        self.assertIn("source_not_equivalent", {issue.code for issue in proof.issues})

    def test_added_command_is_detected_by_source_and_graph_proof(self) -> None:
        changed = dict(self.result.files)
        changed["main.dsc"] = changed["main.dsc"].replace("  - define", "  - narrate injected\n  - define", 1)
        proof = prove_transformation(self.project, changed, self.result.renames)
        self.assertFalse(proof.passed)
        codes = {issue.code for issue in proof.issues}
        self.assertTrue({"source_not_equivalent", "semantic_signature_changed"}.intersection(codes))

    def test_public_item_rename_is_rejected_even_if_internal_map_is_valid(self) -> None:
        changed = dict(self.result.files)
        changed["main.dsc"] = changed["main.dsc"].replace("public_item:", "renamed_public_item:", 1)
        proof = prove_transformation(self.project, changed, self.result.renames)
        self.assertFalse(proof.passed)
        self.assertIn("semantic_signature_changed", {issue.code for issue in proof.issues})


if __name__ == "__main__":
    unittest.main()
