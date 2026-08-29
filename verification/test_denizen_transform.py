from __future__ import annotations

import unittest

from dcore.semantics.graph import build_denizen_graph
from dcore.semantics.ir import build_project_ir
from dcore.semantics.surface import classify_surface
from dcore.semantics.transform import UnsafeTransformError, transform_project


class DenizenTransformTests(unittest.TestCase):
    def test_renames_only_internal_container_and_local_definitions(self) -> None:
        source = """public_item:
  type: item
  material: stone
entry:
  type: world
  events:
  - on server start:
    - run worker
    - spawn worker
worker:
  type: task
  definitions: target
  script:
  - define target player
  - foreach <server.list_players> as:target:
    - narrate <[target.name]>
  - narrate <[target]>
settings:
  worker: worker
"""
        project = build_project_ir({"main.dsc": source})
        result = transform_project(project, salt=b"test")
        transformed = result.files["main.dsc"]
        container = next(item.replacement for item in result.renames if item.kind == "container" and item.original == "worker")
        definition = next(item.replacement for item in result.renames if item.kind == "definition" and item.original == "target")
        self.assertIn(f"- run {container}", transformed)
        self.assertIn("- spawn worker", transformed)
        self.assertIn("public_item:", transformed)
        self.assertIn(f"{container}:\n  type: task\n  definitions: {definition}", transformed)
        self.assertIn(f"define {definition} player", transformed)
        self.assertIn(f"as:{definition}", transformed)
        self.assertIn(f"<[{definition}.name]>", transformed)
        self.assertIn("settings:\n  worker: worker", transformed)
        self.assertNotIn("entry:", transformed.replace("entry:", "", 1))

    def test_static_script_tag_is_rewritten_but_public_item_tag_is_stable(self) -> None:
        source = """public_item:
  type: item
  material: stone
entry:
  type: world
  events:
  - on server start:
    - run worker
    - narrate <script[worker]>
    - narrate <item[public_item]>
worker:
  type: task
  script:
  - stop
"""
        result = transform_project(build_project_ir({"main.dsc": source}), salt=b"test")
        transformed = result.files["main.dsc"]
        worker = next(item.replacement for item in result.renames if item.original == "worker")
        self.assertIn(f"<script[{worker}]>", transformed)
        self.assertIn("<item[public_item]>", transformed)

    def test_unknown_surface_is_a_hard_stop_and_does_not_return_partial_output(self) -> None:
        source = """entry:
  type: world
  events:
  - on server start:
    - run <[dynamic_task]>
worker:
  type: task
  script:
  - stop
"""
        project = build_project_ir({"main.dsc": source})
        with self.assertRaises(UnsafeTransformError) as context:
            transform_project(project)
        self.assertTrue(context.exception.surface.hard_blocked)

    def test_unresolved_definition_and_external_task_are_not_guessed(self) -> None:
        source = """entry:
  type: world
  events:
  - on server start:
    - run missing_task
worker:
  type: task
  script:
  - narrate <[not_declared]>
"""
        project = build_project_ir({"main.dsc": source})
        surface = classify_surface(build_denizen_graph(project))
        self.assertTrue(surface.hard_blocked)
        with self.assertRaises(UnsafeTransformError):
            transform_project(project, surface=surface)

    def test_custom_name_factory_is_used_and_fingerprint_input_is_not_mutated(self) -> None:
        source = """entry:
  type: world
  events:
  - on server start:
    - run worker
worker:
  type: task
  script:
  - stop
"""
        project = build_project_ir({"main.dsc": source})
        original = project.files["main.dsc"].text
        result = transform_project(
            project,
            name_factory=lambda kind, identifier: "safe_worker" if kind == "container" else "safe_definition",
        )
        self.assertEqual(original, project.files["main.dsc"].text)
        self.assertIn("- run safe_worker", result.files["main.dsc"])
        self.assertIn("safe_worker:\n", result.files["main.dsc"])
        self.assertEqual(2, result.edit_count)


if __name__ == "__main__":
    unittest.main()
