from __future__ import annotations

import unittest

from dcore.semantics.ir import build_project_ir, parse_denizen_ir


class DenizenIrTests(unittest.TestCase):
    def test_preserves_all_top_level_sections_after_containers(self) -> None:
        text = """first:
  type: task
  script:
  - narrate first
settings:
  foo: bar
second:
  type: task
  script:
  - narrate second
"""
        ir = parse_denizen_ir(text, "sample.dsc")
        self.assertEqual(["first", "settings", "second"], [section.name for section in ir.sections])
        self.assertEqual(["first", "second"], [section.name for section in ir.containers])
        self.assertFalse(ir.sections[1].is_container)

    def test_commands_keep_spans_and_opaque_tags(self) -> None:
        text = """demo:
  type: task
  script:
  - narrate "hello <[name]> <context.entity>"
"""
        ir = parse_denizen_ir(text, "demo.dsc")
        self.assertEqual(["narrate"], [command.name for command in ir.commands])
        self.assertEqual(4, ir.commands[0].line)
        self.assertEqual(2, len([item for item in ir.commands[0].opaque if item.kind == "tag"]))
        self.assertGreater(ir.commands[0].argument_span.end, ir.commands[0].argument_span.start)

    def test_definition_and_loop_symbols_are_scoped(self) -> None:
        text = """worker:
  type: task
  definitions: target|mode
  script:
  - define target player
  - foreach <list[a|b]> as:item key:index
    - run child def:target:<[target]>
"""
        ir = parse_denizen_ir(text, "defs.dsc")
        symbols = {(symbol.name, symbol.kind, symbol.scope) for symbol in ir.symbols}
        self.assertIn(("target", "definition", "worker"), symbols)
        self.assertIn(("mode", "definition", "worker"), symbols)
        self.assertIn(("item", "loop_alias", "worker"), symbols)
        self.assertIn(("index", "loop_alias", "worker"), symbols)

    def test_dynamic_and_static_container_calls_are_distinguished(self) -> None:
        text = """demo:
  type: task
  script:
  - run fixed_task
  - run <[dynamic_task]>
  - narrate <script[fixed_task].name>
"""
        ir = parse_denizen_ir(text, "refs.dsc")
        calls = [reference for reference in ir.references if reference.kind == "container_call"]
        tags = [reference for reference in ir.references if reference.kind == "container_tag"]
        self.assertEqual([False, True], [reference.dynamic for reference in calls])
        self.assertEqual(["fixed_task"], [reference.value for reference in tags])

    def test_project_reports_duplicate_containers_and_cross_file_symbols(self) -> None:
        project = build_project_ir({
            "a.dsc": "shared:\n  type: task\n  script:\n  - stop\n",
            "b.dsc": "shared:\n  type: task\n  script:\n  - stop\n",
        })
        self.assertEqual({"shared"}, project.duplicate_containers)
        self.assertEqual(2, sum("shared" in file_ir.containers[0].name for file_ir in project.files.values()))


if __name__ == "__main__":
    unittest.main()
