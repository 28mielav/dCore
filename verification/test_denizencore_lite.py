from __future__ import annotations

import unittest

from dcore.semantics.core import analyze_denizen, analyze_project
from dcore.lint.script import apply_policy, build_report


class DenizenCoreLiteTests(unittest.TestCase):
    def test_queue_definitions_if_choose_and_repeat_follow_portable_semantics(self) -> None:
        result = analyze_denizen("""demo:
  type: task
  script:
  - define mode wolf
  - if <[mode]> == wolf:
    - define chosen yes
  - else:
    - define chosen no
  - choose <[chosen]>:
    - case yes:
      - repeat 2 as:index:
        - narrate <[index]>
    - default:
      - stop
""")
        self.assertEqual([], [item for item in result.diagnostics if item.severity == "error"])
        self.assertEqual("yes", result.definitions["chosen"])
        self.assertEqual(2, len(result.platform_commands))
        self.assertTrue(all(command == "narrate" for _, command in result.platform_commands))

    def test_read_before_define_is_a_semantic_error(self) -> None:
        result = analyze_denizen("""demo:
  type: task
  script:
  - narrate <[missing]>
""")
        self.assertIn("undefined_definition", {item.code for item in result.diagnostics})

    def test_stop_prevents_later_queue_entries(self) -> None:
        result = analyze_denizen("""demo:
  type: task
  script:
  - stop
  - narrate should_not_run
""")
        self.assertTrue(result.stopped)
        self.assertEqual([], result.platform_commands)

    def test_while_has_a_hard_semantic_limit(self) -> None:
        result = analyze_denizen("""demo:
  type: task
  script:
  - while true:
    - narrate loop
""", max_steps=4)
        self.assertIn("semantic_execution_limit", {item.code for item in result.diagnostics})

    def test_foreach_scopes_value_and_loop_index_then_restores_them(self) -> None:
        result = analyze_denizen("""demo:
  type: task
  script:
  - define value outer
  - foreach <list[a|b]> as:value:
    - narrate <[value]>/<[loop_index]>
  - narrate <[value]>
""")
        self.assertEqual("outer", result.definitions["value"])
        self.assertNotIn("loop_index", result.definitions)
        self.assertEqual(3, len(result.platform_commands))

    def test_foreach_next_and_stop_are_local_to_the_loop(self) -> None:
        result = analyze_denizen("""demo:
  type: task
  script:
  - foreach <list[a|b|c]> as:value:
    - if <[value]> == b:
      - foreach next
    - if <[value]> == c:
      - foreach stop
    - narrate <[value]>
""")
        self.assertEqual(1, len(result.platform_commands))
        self.assertEqual("narrate", result.platform_commands[0][1])

    def test_run_validates_target_definitions_and_executes_local_queue_semantics(self) -> None:
        result = analyze_denizen("""caller:
  type: task
  script:
  - run target def.name:denizen instantly
target:
  type: task
  definitions: name
  script:
  - define greeting hello_<[name]>
  - narrate <[greeting]>
""")
        self.assertNotIn("run_unknown_script", {item.code for item in result.diagnostics})
        self.assertNotIn("run_missing_definitions", {item.code for item in result.diagnostics})
        self.assertIn((10, "narrate"), result.platform_commands)

    def test_run_reports_missing_target_and_declared_inputs(self) -> None:
        missing = analyze_denizen("demo:\n  type: task\n  script:\n  - run nowhere\n")
        self.assertIn("run_unknown_script", {item.code for item in missing.diagnostics})
        undersupplied = analyze_denizen("""caller:
  type: task
  script:
  - run target
target:
  type: task
  definitions: needed
  script:
  - stop
""")
        self.assertIn("run_missing_definitions", {item.code for item in undersupplied.diagnostics})

    def test_known_cross_file_run_target_is_not_reported_as_missing(self) -> None:
        result = analyze_denizen(
            "demo:\n  type: task\n  script:\n  - run owned_elsewhere\n",
            known_script_names={"owned_elsewhere"},
        )
        self.assertNotIn("run_unknown_script", {item.code for item in result.diagnostics})

    def test_run_positional_definitions_map_to_declared_order(self) -> None:
        result = analyze_denizen("""caller:
  type: task
  script:
  - run target def:one|two
target:
  type: task
  definitions: first|second
  script:
  - narrate <[first]>/<[second]>
""")
        self.assertNotIn("run_missing_definitions", {item.code for item in result.diagnostics})

    def test_run_recursion_is_reported_without_waiting_for_depth_limit(self) -> None:
        result = analyze_denizen("""loop:
  type: task
  script:
  - run loop
""")
        self.assertIn("run_recursive_cycle", {item.code for item in result.diagnostics})

    def test_determine_stops_but_passive_determine_does_not(self) -> None:
        terminal = analyze_denizen("""demo:
  type: procedure
  script:
  - determine done
  - narrate unreachable
""")
        self.assertEqual(["done"], terminal.determinations)
        self.assertEqual([], terminal.platform_commands)
        passive = analyze_denizen("""demo:
  type: world
  script:
  - determine passively cancelled
  - narrate reachable
""")
        self.assertEqual(["cancelled"], passive.determinations)
        self.assertEqual([(5, "narrate")], passive.platform_commands)

    def test_numeric_definition_action_is_evaluated(self) -> None:
        result = analyze_denizen("""demo:
  type: task
  script:
  - define count 2
  - define count:+:3
  - if <[count]> == 5:
    - narrate good
""")
        self.assertEqual("5", result.definitions["count"])
        self.assertEqual([(7, "narrate")], result.platform_commands)

    def test_map_foreach_scopes_key_and_value(self) -> None:
        result = analyze_denizen("""demo:
  type: task
  script:
  - foreach map@wolf=fast;dog=loyal as:value key:name:
    - narrate <[name]>/<[value]>
""")
        self.assertEqual(2, len(result.platform_commands))
        self.assertNotIn("name", result.definitions)
        self.assertNotIn("value", result.definitions)

    def test_inject_runs_target_in_current_definition_scope(self) -> None:
        result = analyze_denizen("""caller:
  type: task
  script:
  - define name dcore
  - inject target
  - narrate unreachable
target:
  type: task
  script:
  - define greeting hello_<[name]>
  - stop
""")
        self.assertIn("inject:target@5", result.trace)
        self.assertEqual([], result.platform_commands)

    def test_inject_cycle_and_unknown_target_are_errors(self) -> None:
        cycle = analyze_denizen("""a:
  type: task
  script:
  - inject a
""")
        self.assertIn("inject_recursive_cycle", {item.code for item in cycle.diagnostics})
        missing = analyze_denizen("demo:\n  type: task\n  script:\n  - inject absent\n")
        self.assertIn("inject_unknown_script", {item.code for item in missing.diagnostics})

    def test_wait_records_static_duration_and_marks_dynamic_duration(self) -> None:
        static = analyze_denizen("demo:\n  type: task\n  script:\n  - wait 2s\n")
        self.assertEqual(["2s"], static.waits)
        dynamic = analyze_denizen("demo:\n  type: task\n  script:\n  - wait <context.delay>\n")
        self.assertIn("wait_not_static", {item.code for item in dynamic.diagnostics})

    def test_execution_limit_explains_wait_boundary_class(self) -> None:
        result = analyze_denizen("""demo:
  type: task
  script:
  - while true:
    - wait 1t
""", max_steps=4)
        limit = next(item for item in result.diagnostics if item.code == "semantic_execution_limit")
        self.assertIn("dynamic_or_event_driven_wait_boundary", limit.message)

    def test_queue_policy_downgrades_only_an_explicit_fixture_path(self) -> None:
        finding = {
            "file": r"C:\project\gravity_gun.dsc", "line": 350,
            "code": "semantic_execution_limit", "severity": "error",
            "message": "proof class: dynamic_or_event_driven_wait_boundary",
            "layer": "denizencore_lite",
        }
        without = apply_policy([finding])
        with_fixture = apply_policy([finding], fixture={"known_lifetime_paths": ["gravity_gun.dsc:350"]})
        self.assertEqual("warning", without[0]["severity"])
        self.assertEqual("information", with_fixture[0]["severity"])
        self.assertEqual("P1", with_fixture[0]["priority"])
        self.assertEqual(1, len(build_report(with_fixture)["findings"]))

    def test_project_program_follows_cross_file_run_and_cycle(self) -> None:
        project = analyze_project({
            "caller.dsc": "caller:\n  type: task\n  script:\n  - run target\n",
            "target.dsc": "target:\n  type: task\n  script:\n  - run caller\n",
        })
        caller_codes = {item.code for item in project["caller.dsc"].diagnostics}
        self.assertIn("run_recursive_cycle", caller_codes)

    def test_project_known_external_script_is_a_boundary_not_unknown_target(self) -> None:
        project = analyze_project(
            {"caller.dsc": "caller:\n  type: task\n  script:\n  - run installed_task\n"},
            known_script_names={"installed_task"},
        )
        self.assertNotIn("run_unknown_script", {item.code for item in project["caller.dsc"].diagnostics})


if __name__ == "__main__":
    unittest.main()
