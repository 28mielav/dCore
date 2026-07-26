from __future__ import annotations

import unittest
from pathlib import Path

from tools.dcore_lint import MetaIndex, lint_contract, lint_text, render_table


class DcoreLintTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.meta = MetaIndex(Path("knowledge/dcore.sqlite"), "denizenm", {"reflect"})

    def test_comparisons_are_not_tags(self) -> None:
        text = """example:
  type: task
  script:
  - if <[value]> < 3:
    - stop
  - if <[value]> > 1:
    - flag server values:<-:<[value]>
"""
        self.assertNotIn("uneven_tags", {item["code"] for item in lint_text(text)})

    def test_unclosed_tag_is_an_error(self) -> None:
        issues = lint_text("example:\n  type: task\n  script:\n  - narrate <[value]\n")
        self.assertIn("uneven_tags", {item["code"] for item in issues})

    def test_contract_requires_literal_witnesses(self) -> None:
        contract = {
            "design": {
                "expected_scale": "one player",
                "entry_points": ["click"],
                "state_owners": ["item"],
                "hot_path_budget": "one event",
                "concurrency": "item-local",
                "persistence_reload": "item data",
                "failure_cleanup": "none acquired",
                "change_axes": ["presentation"],
                "code_shape_budget": {"max_handler_commands": 10},
                "route_decision": {
                    "selected_for_proof": "native_denizenm",
                    "rationale": "Exact target Meta satisfies the capability.",
                },
            },
            "clauses": [
                {
                    "id": "mainhand",
                    "required_all": ["context.hand", "mainhand"],
                    "required_any": [],
                    "forbidden": ["offhand mutation"],
                }
            ]
        }
        self.assertEqual([], lint_contract("context.hand mainhand", contract))
        self.assertIn(
            "contract_missing",
            {item["code"] for item in lint_contract("# context.hand mainhand\ncontext.hand", contract)},
        )

    def test_contract_requires_precode_design(self) -> None:
        contract = {"clauses": [{"id": "proof", "required_all": ["narrate ok"]}]}
        self.assertIn(
            "contract_design_missing",
            {item["code"] for item in lint_contract("- narrate ok", contract)},
        )

    def test_contract_requires_route_decision(self) -> None:
        contract = {
            "design": {
                "expected_scale": "one", "entry_points": ["click"],
                "state_owners": ["item"], "hot_path_budget": "one event",
                "concurrency": "none", "persistence_reload": "item",
                "failure_cleanup": "none", "change_axes": ["provider"],
                "code_shape_budget": {"max_handler_commands": 10},
            },
            "clauses": [{"id": "proof", "required_all": ["narrate ok"]}],
        }
        self.assertIn(
            "contract_design_incomplete",
            {item["code"] for item in lint_contract("- narrate ok", contract)},
        )

    def test_decision_artifact_must_match_contract(self) -> None:
        contract = {
            "design": {
                "expected_scale": "one", "entry_points": ["click"],
                "state_owners": ["item"], "hot_path_budget": "one event",
                "concurrency": "none", "persistence_reload": "item",
                "failure_cleanup": "none", "change_axes": ["provider"],
                "code_shape_budget": {"max_handler_commands": 10},
                "route_decision": {"selected_for_proof": "native", "rationale": "Meta proof"},
            },
            "clauses": [{"id": "proof", "required_all": ["narrate ok"]}],
        }
        decision = {"tool": "dcore_design", "status": "READY_FOR_PROOF", "selected_for_proof": "reflect"}
        self.assertIn(
            "decision_contract_mismatch",
            {item["code"] for item in lint_contract("- narrate ok", contract, decision)},
        )

    def test_meta_detects_unknown_command_and_known_property(self) -> None:
        text = """example:
  type: task
  script:
  - definitely_not_a_denizen_command value
  - adjust <[entity]> has_ai:false
"""
        issues = lint_text(text, self.meta)
        self.assertIn("unknown_command", {item["code"] for item in issues})
        self.assertNotIn(
            "unknown_mechanism",
            {item["code"] for item in issues if item["line"] == 5},
        )

    def test_command_specific_runtime_regression(self) -> None:
        text = """example:
  type: task
  script:
  - playeffect effect:end_rod location:<player.location>
"""
        self.assertIn(
            "invalid_playeffect_location_argument",
            {item["code"] for item in lint_text(text, self.meta)},
        )

    def test_reflect_is_an_addon_boundary_not_unknown_core(self) -> None:
        text = """import:
  com.example.Api:

example:
  type: task
  script:
  - define value <invoke[Api].method[test]>
"""
        codes = {item["code"] for item in lint_text(text, self.meta)}
        self.assertIn("reflect_boundary", codes)
        self.assertNotIn("missing_container_type", codes)
        self.assertNotIn("unknown_command", codes)
        without_addon = MetaIndex(Path("knowledge/dcore.sqlite"), "denizenm", set())
        self.assertIn(
            "reflect_addon_not_enabled",
            {item["code"] for item in lint_text(text, without_addon)},
        )

    def test_broad_cancellation_requires_identity_first(self) -> None:
        bad = """example:
  type: world
  events:
    on player tries to attack slime:
    - determine cancelled
"""
        good = """example:
  type: world
  events:
    on player tries to attack slime:
    - stop if:<context.entity.has_flag[treasure_role].not>
    - determine cancelled
"""
        self.assertIn(
            "broad_cancel_without_identity_guard",
            {item["code"] for item in lint_text(bad, self.meta)},
        )
        good_codes = {item["code"] for item in lint_text(good, self.meta)}
        self.assertNotIn("broad_cancel_without_identity_guard", good_codes)
        self.assertIn("broad_event_guarded", good_codes)

    def test_terminal_determine_makes_following_command_unreachable(self) -> None:
        text = """example:
  type: world
  events:
    on player tries to attack slime:
    - determine cancelled
    - run treasure_dig
"""
        self.assertIn(
            "unreachable_after_terminal_command",
            {item["code"] for item in lint_text(text)},
        )

    def test_passive_determine_keeps_following_command_reachable(self) -> None:
        text = """example:
  type: world
  events:
    on player clicks:
    - determine passively cancelled
    - narrate ok
"""
        self.assertNotIn(
            "unreachable_after_terminal_command",
            {item["code"] for item in lint_text(text)},
        )

    def test_casted_entity_type_is_not_ambiguous(self) -> None:
        generic = "example:\n  type: task\n  script:\n  - if <[entity].type> == wolf:\n    - stop\n"
        casted = "example:\n  type: task\n  script:\n  - if <[entity].as[entity].type> == wolf:\n    - stop\n"
        self.assertIn("ambiguous_object_type", {item["code"] for item in lint_text(generic)})
        self.assertNotIn("ambiguous_object_type", {item["code"] for item in lint_text(casted)})

    def test_flow_and_bounded_loop_are_not_false_errors(self) -> None:
        text = """example:
  type: task
  script:
  - choose <[value]>:
    - case one:
      - while true:
        - wait 1t
        - stop if:<[session].is_expired>
    - default:
      - stop
"""
        codes = {item["code"] for item in lint_text(text, self.meta)}
        self.assertNotIn("unknown_command", codes)
        self.assertNotIn("busy_while_true", codes)
        self.assertNotIn("unproven_loop_bound", codes)

    def test_maintainability_budget_flags_oversized_event(self) -> None:
        commands = "\n".join("    - narrate x" for _ in range(61))
        text = f"example:\n  type: world\n  events:\n    on player joins:\n{commands}\n"
        issues = lint_text(text)
        oversized = [item for item in issues if item["code"] == "oversized_event_handler"]
        self.assertEqual(1, len(oversized))
        self.assertEqual("warning", oversized[0]["severity"])

    def test_maintainability_budget_flags_deep_nesting(self) -> None:
        text = """example:
  type: world
  events:
    on player joins:
    - if <player.is_online>:
      - if <player.is_spawned>:
        - if <player.is_op>:
          - if <player.is_sneaking>:
            - if <player.has_flag[test]>:
              - if <player.name.is_empty.not>:
                - narrate ok
"""
        self.assertIn("deep_control_nesting", {item["code"] for item in lint_text(text)})

    def test_small_guarded_handler_is_within_clean_code_budget(self) -> None:
        text = """example:
  type: world
  events:
    on player right clicks entity:
    - stop if:<context.entity.has_flag[owned_role].not>
    - determine cancelled
    - run owned_action
"""
        codes = {item["code"] for item in lint_text(text)}
        self.assertNotIn("oversized_event_handler", codes)
        self.assertNotIn("large_event_handler", codes)
        self.assertNotIn("deep_control_nesting", codes)

    def test_container_type_accepts_valid_deeper_indentation(self) -> None:
        text = "example:\n    type: task\n    script:\n    - narrate ok\n"
        self.assertNotIn("missing_container_type", {item["code"] for item in lint_text(text)})

    def test_forwarding_task_is_reviewed(self) -> None:
        text = """bridge:
  type: task
  script:
  - run real_owner

real_owner:
  type: task
  script:
  - narrate ok
"""
        self.assertIn("forwarding_task", {item["code"] for item in lint_text(text)})

    def test_command_permission_requires_product_policy_review(self) -> None:
        text = """demo_command:
  type: command
  name: demo
  permission: demo.use
  script:
  - narrate ok
"""
        self.assertIn("permission_policy_review", {item["code"] for item in lint_text(text)})

    def test_human_table_hides_information_by_default(self) -> None:
        report = render_table([
            {"file": "demo.dsc", "line": 4, "severity": "warning", "code": "demo", "message": "Problem", "suggestion": "Fix"},
            {"file": "demo.dsc", "line": 0, "severity": "information", "code": "source", "message": "Provenance"},
        ])
        self.assertIn("| WARNING |", report)
        self.assertNotIn("`source`", report)
        self.assertIn("Information rows are hidden", report)


if __name__ == "__main__":
    unittest.main()
