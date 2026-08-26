from __future__ import annotations

import unittest

from dcore.semantics.graph import build_denizen_graph
from dcore.semantics.ir import build_project_ir
from dcore.semantics.surface import classify_surface


class DenizenSurfaceTests(unittest.TestCase):
    def test_registered_container_types_are_public(self) -> None:
        project = build_project_ir({
            "public.dsc": """item_name:
  type: item
  material: stone
my_command:
  type: command
  name: /demo
  script:
  - narrate hello
my_world:
  type: world
  events:
  - on server start:
    - narrate started
"""
        })
        surface = classify_surface(build_denizen_graph(project))
        self.assertEqual({"public.dsc::item_name", "public.dsc::my_command", "public.dsc::my_world"},
                         {item.identifier for item in surface.public})
        self.assertFalse(surface.hard_blocked)

    def test_called_task_is_internal_but_orphan_task_is_unknown(self) -> None:
        project = build_project_ir({
            "tasks.dsc": """entry:
  type: world
  events:
  - on server start:
    - run worker
worker:
  type: task
  script:
  - stop
orphan:
  type: task
  script:
  - stop
"""
        })
        surface = classify_surface(build_denizen_graph(project))
        worker = surface.decision("tasks.dsc::worker", "container")
        orphan = surface.decision("tasks.dsc::orphan", "container")
        self.assertIsNotNone(worker)
        self.assertEqual("internal", worker.classification)
        self.assertIsNotNone(orphan)
        self.assertEqual("unknown", orphan.classification)
        self.assertIn("tasks.dsc::worker", surface.renameable)
        self.assertNotIn("tasks.dsc::orphan", surface.renameable)

    def test_dynamic_unresolved_and_ambiguous_references_block(self) -> None:
        project = build_project_ir({
            "a.dsc": """entry:
  type: world
  events:
  - on server start:
    - run shared
    - run missing
    - run <[dynamic_task]>
shared:
  type: task
  script:
  - stop
""",
            "b.dsc": """shared:
  type: task
  script:
  - stop
""",
        })
        surface = classify_surface(build_denizen_graph(project))
        self.assertTrue(surface.hard_blocked)
        reasons = {reason for item in surface.unknown for reason in item.reasons}
        self.assertIn("ambiguous_reference_target", reasons)
        self.assertIn("unresolved_reference_target", reasons)
        self.assertIn("dynamic_reference_target", reasons)

    def test_server_state_is_public_other_state_is_unknown(self) -> None:
        project = build_project_ir({
            "state.dsc": """entry:
  type: world
  events:
  - on server start:
    - flag server rollout.active:true
    - flag player rollout.active:true
    - narrate <server.flag[rollout.active]>
    - narrate <player.flag[rollout.active]>
"""
        })
        surface = classify_surface(build_denizen_graph(project))
        self.assertEqual("public", surface.decision("server:rollout", "state").classification)
        self.assertEqual("unknown", surface.decision("player:rollout", "state").classification)

    def test_definition_status_controls_renameability_and_fingerprint_is_stable(self) -> None:
        project = build_project_ir({
            "defs.dsc": """worker:
  type: task
  definitions: target
  script:
  - define target player
  - narrate <[target]>
  - narrate <[missing]>
"""
        })
        graph = build_denizen_graph(project)
        surface = classify_surface(graph)
        self.assertEqual("internal", surface.decision("defs.dsc::worker::target", "definition").classification)
        missing = surface.decision("defs.dsc::worker::missing", "definition")
        self.assertIsNotNone(missing)
        self.assertEqual("unknown", missing.classification)
        self.assertIn("defs.dsc::worker::target", surface.renameable)
        self.assertEqual(surface.fingerprint(), classify_surface(graph).fingerprint())


if __name__ == "__main__":
    unittest.main()
