from __future__ import annotations

import unittest

from dcore.semantics.graph import build_denizen_graph
from dcore.semantics.ir import build_project_ir


class DenizenGraphTests(unittest.TestCase):
    def test_resolves_static_calls_and_marks_dynamic_calls(self) -> None:
        project = build_project_ir({
            "main.dsc": """main:
  type: task
  script:
  - run worker
  - run <[dynamic_task]>
  - run missing_task
worker:
  type: task
  script:
  - stop
"""
        })
        graph = build_denizen_graph(project)
        statuses = {(edge.target_name, edge.status) for edge in graph.calls}
        self.assertIn(("worker", "resolved"), statuses)
        self.assertEqual(1, len(graph.dynamic_references))
        self.assertEqual(1, len(graph.unresolved_references))

    def test_duplicate_target_is_ambiguous_not_silently_selected(self) -> None:
        project = build_project_ir({
            "a.dsc": "main:\n  type: task\n  script:\n  - run shared\nshared:\n  type: task\n  script:\n  - stop\n",
            "b.dsc": "shared:\n  type: task\n  script:\n  - stop\n",
        })
        graph = build_denizen_graph(project)
        edge = next(edge for edge in graph.calls if edge.target_name == "shared")
        self.assertEqual("ambiguous", edge.status)
        self.assertIsNone(edge.target)

    def test_definition_scope_and_use_order_are_recorded(self) -> None:
        project = build_project_ir({
            "defs.dsc": """worker:
  type: task
  definitions: target
  script:
  - run child def:target:<[target]>
  - define target player
  - narrate <[target]>
child:
  type: task
  script:
  - stop
"""
        })
        graph = build_denizen_graph(project)
        worker = graph.containers_by_name["worker"][0]
        binding = graph.definitions[(worker, "target")]
        self.assertEqual([3, 6], binding.declarations)
        self.assertEqual("resolved", binding.status)
        self.assertIn(7, binding.uses)
        self.assertIn(5, binding.call_argument_uses)

    def test_state_graph_tracks_persistent_writers_and_readers(self) -> None:
        project = build_project_ir({
            "state.dsc": """open_session:
  type: task
  script:
  - flag server session.active:true
  - narrate <server.flag[session.active]>
close_session:
  type: task
  script:
  - flag server session.active:false
"""
        })
        graph = build_denizen_graph(project)
        accesses = graph.state_roots[("server", "session")]
        self.assertEqual(3, len(accesses))
        self.assertEqual(2, len(graph.multi_writer_state[("server", "session")]))
        self.assertTrue(all(access.persistent for access in accesses))

    def test_fingerprint_is_order_independent_for_project_input(self) -> None:
        files = {
            "a.dsc": "a:\n  type: task\n  script:\n  - stop\n",
            "b.dsc": "b:\n  type: task\n  script:\n  - stop\n",
        }
        first = build_denizen_graph(build_project_ir(files)).fingerprint()
        second = build_denizen_graph(build_project_ir(dict(reversed(list(files.items()))))).fingerprint()
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
