from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from dcore.lint.parser import parse_file
from dcore.lint.script import MetaIndex, expand_input_paths, lint_contract, lint_parsed, lint_text, render_table


class DcoreLintTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.meta = MetaIndex(Path("dcore/knowledge/data/dcore.sqlite"), "denizenm", {"reflect"})

    def test_project_directory_expands_all_dsc_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "nested").mkdir()
            first = root / "first.dsc"
            second = root / "nested" / "second.DSC"
            ignored = root / "notes.txt"
            first.write_text("first:\n  type: task\n  script:\n  - stop\n", encoding="utf-8")
            second.write_text("second:\n  type: task\n  script:\n  - stop\n", encoding="utf-8")
            ignored.write_text("not a script", encoding="utf-8")
            self.assertEqual(
                {first.resolve(), second.resolve()},
                {path.resolve() for path in expand_input_paths([root])},
            )

    def test_project_directory_deduplicates_explicit_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            script = root / "only.dsc"
            script.write_text("only:\n  type: task\n  script:\n  - stop\n", encoding="utf-8")
            self.assertEqual(1, len(expand_input_paths([root, script])))

    def test_project_directory_requires_dsc_input(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, "no .dsc files"):
                expand_input_paths([Path(temporary)])

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
        without_addon = MetaIndex(Path("dcore/knowledge/data/dcore.sqlite"), "denizenm", set())
        self.assertIn(
            "reflect_addon_not_enabled",
            {item["code"] for item in lint_text(text, without_addon)},
        )

    def test_provider_resolver_marks_disabled_capability(self) -> None:
        text = "example:\n  type: task\n  script:\n  - invoke player.getName()\n"
        rows = lint_text(text, MetaIndex(Path("dcore/knowledge/data/dcore.sqlite"), "denizenm", set()))
        invoke_rows = [item for item in rows if item["line"] == 4 and item["code"] in {"addon_required", "version_api_unverified"}]
        self.assertEqual(1, len(invoke_rows))
        self.assertEqual("addon_required", invoke_rows[0]["code"])
        self.assertEqual("known_provider_disabled", invoke_rows[0]["confidence"])

    def test_reflect_empty_tag_is_a_structural_error(self) -> None:
        text = "example:\n  type: task\n  script:\n  - define value <invoke[]>\n"
        codes = {item["code"] for item in lint_text(text, self.meta)}
        self.assertIn("reflect_expression_malformed", codes)

    def test_reflect_command_requires_expression(self) -> None:
        text = "example:\n  type: task\n  script:\n  - invoke\n"
        codes = {item["code"] for item in lint_text(text, self.meta)}
        self.assertIn("reflect_command_missing_expression", codes)

    def test_reflect_balanced_expression_is_not_rejected(self) -> None:
        text = "example:\n  type: task\n  script:\n  - define value <invoke[player.getName()]>\n"
        codes = {item["code"] for item in lint_text(text, self.meta)}
        self.assertNotIn("reflect_expression_malformed", codes)
        self.assertIn("reflect_boundary", codes)

    def test_versioned_addon_spec_is_normalized(self) -> None:
        meta = MetaIndex(Path("dcore/knowledge/data/dcore.sqlite"), "denizenm", {"reflect@2.4.2"})
        self.assertIn("reflect", meta.addons)
        self.assertEqual("2.4.2", meta.addon_versions["reflect"])

    def test_b_prefixed_denizenm_target_is_canonicalized(self) -> None:
        meta = MetaIndex(
            Path("dcore/knowledge/data/dcore.sqlite"), "denizenm", set(),
            target={"minecraft": "1.21.11", "denizenm": "b7299M"},
        )
        self.assertEqual("7299M", meta.target["denizenm"])
        self.assertEqual([], meta.version_meta_missing)

    def test_required_jar_evidence_is_a_real_gate(self) -> None:
        text = "example:\n  type: task\n  script:\n  - define value <invoke[player.getName()]>\n"
        meta = MetaIndex(
            Path("dcore/knowledge/data/dcore.sqlite"), "denizenm", {"reflect@2.4.2"},
            target={"minecraft": "1.21.11", "denizenm": "b7299M"},
            require_jar_evidence=True,
        )
        codes = {item["code"] for item in lint_text(text, meta)}
        self.assertIn("jar_evidence_missing", codes)
        self.assertIn("target_context", codes)

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

    def test_damage_event_collision_requires_type_switch(self) -> None:
        ambiguous = """example:
  type: world
  events:
    on entity_flagged:treasure_role damaged:
    - stop
"""
        narrowed = """example:
  type: world
  events:
    on entity_flagged:treasure_role damaged type:slime:
    - stop
"""
        self.assertIn(
            "ambiguous_event_matcher",
            {item["code"] for item in lint_text(ambiguous, self.meta)},
        )
        self.assertNotIn(
            "ambiguous_event_matcher",
            {item["code"] for item in lint_text(narrowed, self.meta)},
        )

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

    def test_generated_architecture_risk_requires_multiple_observable_signals(self) -> None:
        containers = []
        for index in range(26):
            body = [
                f"task_{index}:",
                "  type: task",
                "  script:",
            ]
            body.extend("  - flag server records:<-:value" for _ in range(20))
            body.extend("  - foreach <list[a|b]> as:item" for _ in range(2))
            body.extend("    - run task_0" for _ in range(3))
            containers.append("\n".join(body))
        findings = lint_text("\n".join(containers))
        risk = [item for item in findings if item["code"] == "generated_architecture_risk"]
        self.assertEqual(1, len(risk))
        self.assertEqual("P1", risk[0]["priority"])
        self.assertGreaterEqual(risk[0]["evidence"]["server_state_writes"], 50)

    def test_generated_architecture_risk_does_not_trigger_on_one_large_dimension(self) -> None:
        text = "\n".join(
            [
                "large_task:",
                "  type: task",
                "  script:",
                *["  - narrate ok" for _ in range(120)],
            ]
        )
        self.assertNotIn(
            "generated_architecture_risk",
            {item["code"] for item in lint_text(text)},
        )

    def test_shared_state_multi_writer_requires_authority(self) -> None:
        text = """first:
  type: task
  script:
  - flag server session.<[id]>:open
second:
  type: task
  script:
  - flag server session.<[id]>:closed
"""
        findings = lint_text(text)
        rows = [item for item in findings if item["code"] == "shared_state_multi_writer"]
        self.assertEqual(1, len(rows))
        self.assertEqual("P1", rows[0]["priority"])
        self.assertEqual({"first", "second"}, set(rows[0]["evidence"]["writers"]))

    def test_queue_fanout_requires_repeated_handoffs_in_a_loop(self) -> None:
        text = """fanout:
  type: task
  script:
  - foreach <list[a|b]> as:item
    - run first def:item:<[item]>
    - run second def:item:<[item]>
"""
        codes = {item["code"] for item in lint_text(text)}
        self.assertIn("queue_fanout", codes)
        row = next(item for item in lint_text(text) if item["code"] == "queue_fanout")
        self.assertEqual("bounded_by_constant", row["evidence"]["bound_class"])

    def test_ownership_graph_requires_a_project_cleanup_edge(self) -> None:
        text = """session_open:
  type: task
  script:
  - create entity_tag
  - open_inventory
  - flag server session.active:true
"""
        rows = lint_text(text)
        graph = [item for item in rows if item["code"] == "ownership_graph_gap"]
        self.assertEqual(1, len(graph))
        self.assertEqual("P0", graph[0]["priority"])
        self.assertIn("acquisitions", graph[0]["evidence"])

    def test_hot_path_cost_requires_dynamic_work(self) -> None:
        text = """ticker:
  type: world
  events:
    on tick:
    - foreach <server.worlds.parse[entities]> as:entity
      - run inspect def:entity:<[entity]>
"""
        rows = [item for item in lint_text(text) if item["code"] == "hot_path_cost"]
        self.assertEqual(1, len(rows))
        self.assertIn("active sessions", rows[0]["estimated_cost"])

    def test_persistent_scheduler_requires_budget_contract(self) -> None:
        text = """runner:
  type: task
  script:
  - while true:
    - foreach <server.flag[active_sessions]> as:session
      - run tick_session def:session:<[session]>
    - wait 1t
"""
        rows = [
            item for item in lint_text(text)
            if item["code"] == "persistent_scheduler_without_budget"
        ]
        self.assertEqual(1, len(rows))
        self.assertEqual("warning", rows[0]["severity"])

    def test_phase_mixed_container_requires_size_and_domain_mix(self) -> None:
        commands = [
            "  - flag server session:<[value]>",
            "  - inventory open destination:<player.inventory>",
            "  - teleport <player> <player.location>",
            "  - playsound <player> sound:block.note_block.harp",
            "  - if <[value]> == one:",
            "    - narrate value",
        ] * 8
        text = "mixed:\n  type: task\n  script:\n" + "\n".join(commands) + "\n"
        rows = [item for item in lint_text(text) if item["code"] == "phase_mixed_container"]
        self.assertEqual(1, len(rows))
        self.assertGreaterEqual(len(rows[0]["evidence"]["families"]), 4)

    def test_cleanup_owner_gap_requires_acquisition_without_release(self) -> None:
        bad = """session_start:
  type: task
  script:
  - create player
  - flag server session.<[id]>:active
"""
        good = """session_start:
  type: task
  script:
  - create player
  - flag server session.<[id]>:active
  - run session_cleanup def:id:<[id]>
session_cleanup:
  type: task
  script:
  - flag server session.<[id]>:!
"""
        self.assertIn(
            "cleanup_owner_gap",
            {item["code"] for item in lint_text(bad)},
        )
        self.assertNotIn(
            "cleanup_owner_gap",
            {item["code"] for item in lint_text(good)},
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

    def test_dog_navigation_stops_before_impulse_owner_change(self) -> None:
        bad = """dog_search:
  type: task
  script:
  - define wolf <server.spawned_entities.find[entity_type=wolf].first>
  - walk <[wolf]> <player.location>
  - push <[wolf]> origin:<[wolf].location> destination:<player.location> speed:1
"""
        good = """dog_search:
  type: task
  script:
  - define wolf <server.spawned_entities.find[entity_type=wolf].first>
  - walk <[wolf]> <player.location>
  - walk <[wolf]> stop
  - push <[wolf]> origin:<[wolf].location> destination:<player.location> speed:1
"""
        self.assertIn(
            "dog_navigation_owner_conflict",
            {item["code"] for item in lint_text(bad)},
        )
        self.assertNotIn(
            "dog_navigation_owner_conflict",
            {item["code"] for item in lint_text(good)},
        )

    def test_dog_navigation_does_not_repath_from_tick_event(self) -> None:
        text = """dog_events:
  type: world
  events:
    on tick:
    - define wolf <server.spawned_entities.find[entity_type=wolf].first>
    - walk <[wolf]> <player.location>
"""
        self.assertIn(
            "dog_navigation_hot_repath",
            {item["code"] for item in lint_text(text)},
        )

    def test_dog_navigation_reports_second_walk_without_stop(self) -> None:
        text = """wolf_search:
  type: task
  script:
  - walk <[wolf]> <player.location>
  - walk <[wolf]> <player.location.add[3,0,0]>
"""
        self.assertIn(
            "dog_navigation_replaced_without_stop",
            {item["code"] for item in lint_text(text)},
        )

    def test_official_semantics_require_procedure_determination(self) -> None:
        bad = "demo:\n  type: procedure\n  script:\n  - narrate side_effect\n"
        good = "demo:\n  type: procedure\n  script:\n  - determine value\n"
        self.assertIn("procedure_missing_determine", {item["code"] for item in lint_text(bad)})
        self.assertNotIn("procedure_missing_determine", {item["code"] for item in lint_text(good)})

    def test_official_semantics_separate_display_from_state(self) -> None:
        bad = """demo:
  type: task
  script:
  - if <player.item_in_hand.lore.contains[admin]>:
    - flag server state:admin
"""
        good = """demo:
  type: task
  script:
  - narrate <player.item_in_hand.lore>
"""
        self.assertIn("display_value_used_as_data", {item["code"] for item in lint_text(bad)})
        self.assertNotIn("display_value_used_as_data", {item["code"] for item in lint_text(good)})

    def test_official_semantics_reject_player_name_as_persistent_identity(self) -> None:
        text = "demo:\n  type: task\n  script:\n  - flag server player_<player.name>:active\n"
        self.assertIn("player_name_used_as_identity", {item["code"] for item in lint_text(text)})

    def test_official_semantics_reject_ex_inside_production_script(self) -> None:
        text = 'demo:\n  type: task\n  script:\n  - execute as_server "/ex reload"\n'
        self.assertIn("ex_command_in_production", {item["code"] for item in lint_text(text)})

    def test_official_semantics_revalidate_captured_live_object_after_wait(self) -> None:
        bad = """demo:
  type: task
  script:
  - define entity <context.entity>
  - wait 1t
  - teleport <[entity]> <player.location>
"""
        refreshed = """demo:
  type: task
  script:
  - define entity <context.entity>
  - wait 1t
  - define entity <context.entity>
  - teleport <[entity]> <player.location>
"""
        self.assertIn("stale_live_reference_after_wait", {item["code"] for item in lint_text(bad)})
        self.assertNotIn("stale_live_reference_after_wait", {item["code"] for item in lint_text(refreshed)})

    def test_refined_parity_rejects_raw_cyrillic_tag(self) -> None:
        text = "demo:\n  type: task\n  script:\n  - narrate <ник>\n"
        self.assertIn("raw_cyrillic_tag", {item["code"] for item in lint_text(text)})

    def test_refined_parity_reports_pointless_plain_data_quotes(self) -> None:
        text = "demo:\n  type: data\n  value: \"plain\"\n"
        self.assertIn("pointless_data_quotes", {item["code"] for item in lint_text(text)})

    def test_denizenm_async_block_reports_live_mutation_crossing(self) -> None:
        text = (
            "demo:\n  type: task\n  script:\n  - async:\n"
            "    - foreach <list[a|b]>:\n      - teleport <player> <player.location>\n"
        )
        meta = MetaIndex(Path("dcore/knowledge/data/dcore.sqlite"), "denizenm", set(), target={"denizenm": "7302M"})
        codes = {item["code"] for item in lint_parsed(parse_file(text), meta)}
        self.assertIn("async_crossing_in_loop", codes)

    def test_latest_denizenm_target_has_an_exact_meta_snapshot(self) -> None:
        meta = MetaIndex(Path("dcore/knowledge/data/dcore.sqlite"), "denizenm", set(), target={"denizenm": "7302M"})
        self.assertEqual([], meta.version_meta_missing)

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
