from __future__ import annotations

import unittest

from tools.dcore_lint import lint_contract, lint_text


class DcoreLintTests(unittest.TestCase):
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
            {item["code"] for item in lint_contract("context.hand", contract)},
        )


if __name__ == "__main__":
    unittest.main()
