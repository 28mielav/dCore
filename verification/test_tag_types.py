"""Tag chain type checking against the Meta snapshot.

The valuable half of these tests is the fail-open half: a type checker that
invents errors on valid code is worse than none, so most cases here assert
that nothing is reported.
"""

from __future__ import annotations

import unittest

from dcore.lint.script import MetaIndex, lint_text
from dcore.lint.tagtypes import build_index, check_chain, faults_in_text, split_segments
from dcore.paths import DATABASE_PATH


class SegmentSplitTests(unittest.TestCase):
    def test_top_level_dots_only(self) -> None:
        self.assertEqual(split_segments("player.name"), ["player", "name"])

    def test_dots_inside_parameters_are_not_separators(self) -> None:
        self.assertEqual(
            split_segments("player.flag[a.b].size"),
            ["player", "flag[a.b]", "size"],
        )

    def test_unbalanced_brackets_are_not_walkable(self) -> None:
        self.assertIsNone(split_segments("player.flag[a"))


class TagTypeIndexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not DATABASE_PATH.is_file():
            raise unittest.SkipTest("knowledge database is not present")
        cls.index = build_index(DATABASE_PATH)

    def test_index_is_populated(self) -> None:
        self.assertTrue(self.index.available())
        self.assertIn("player", self.index.roots)

    def test_inherited_attributes_resolve_through_the_base_chain(self) -> None:
        # location lives on EntityTag; a PlayerTag must still find it.
        self.assertEqual(self.index.returns("PlayerTag", "location"), "LocationTag")

    def test_ancestry_terminates_on_cycles(self) -> None:
        chain = self.index.ancestry("PlayerTag")
        self.assertEqual(len(chain), len(set(chain)))


class ChainCheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not DATABASE_PATH.is_file():
            raise unittest.SkipTest("knowledge database is not present")
        cls.index = build_index(DATABASE_PATH)

    def fault(self, body: str):
        return check_chain(self.index, body)

    def test_attribute_missing_on_returned_type_is_reported(self) -> None:
        # location returns LocationTag, which has no lore (that is an ItemTag attribute).
        fault = self.fault("player.location.lore")
        self.assertIsNotNone(fault)
        self.assertEqual(fault.segment, "lore")
        self.assertEqual(fault.owner_type, "LocationTag")

    def test_globally_unknown_attribute_fails_open(self) -> None:
        # An attribute the snapshot has never seen on any type is far more likely
        # an unindexed addon tag than a mistake, so it is deliberately not
        # reported. Guessing here produced false positives across the corpus
        # (viaversion_protocol, fake_entities).
        self.assertIsNone(self.fault("player.definitely_not_a_tag"))

    def test_valid_chains_are_silent(self) -> None:
        for body in ("player.name", "player.location", "player.location.world", "server.online_players"):
            with self.subTest(body=body):
                self.assertIsNone(self.fault(body))

    def test_single_segment_is_never_reported(self) -> None:
        self.assertIsNone(self.fault("player"))

    def test_definition_roots_fail_open(self) -> None:
        # <[thing]> has no statically known type.
        self.assertIsNone(self.fault("[thing].whatever"))

    def test_unknown_root_fails_open(self) -> None:
        self.assertIsNone(self.fault("not_a_real_root.whatever"))

    def test_explicit_fallback_fails_open(self) -> None:
        self.assertIsNone(self.fault("player.location.lore||nothing"))

    def test_dynamic_segment_stops_the_walk(self) -> None:
        self.assertIsNone(self.fault("player.<[attribute]>"))

    def test_parameterised_attributes_are_walked_by_name(self) -> None:
        self.assertIsNone(self.fault("player.flag[some_flag]"))


class LinterIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not DATABASE_PATH.is_file():
            raise unittest.SkipTest("knowledge database is not present")
        cls.meta = MetaIndex(DATABASE_PATH, "denizenm", set())

    def codes(self, text: str) -> set[str]:
        return {item["code"] for item in lint_text(text, self.meta)}

    def test_bad_chain_becomes_a_finding(self) -> None:
        text = "demo:\n  type: task\n  script:\n  - narrate <player.location.lore>\n"
        self.assertIn("tag_attribute_not_on_type", self.codes(text))

    def test_good_chain_produces_no_type_finding(self) -> None:
        text = "demo:\n  type: task\n  script:\n  - narrate <player.location>\n"
        self.assertNotIn("tag_attribute_not_on_type", self.codes(text))

    def test_commented_lines_are_ignored(self) -> None:
        text = "demo:\n  type: task\n  script:\n  # <player.location.lore>\n  - narrate hi\n"
        self.assertNotIn("tag_attribute_not_on_type", self.codes(text))

    def test_real_corpus_stays_free_of_type_false_positives(self) -> None:
        # The reference corpus is known-good production script; any finding here
        # is a checker bug, not a user bug.
        from pathlib import Path

        corpus = Path(__file__).resolve().parents[2] / "references" / "examples"
        if not corpus.is_dir():
            self.skipTest("reference corpus is not present")
        offenders: list[str] = []
        for path in sorted(corpus.glob("*.dsc")):
            text = path.read_text(encoding="utf-8", errors="replace")
            for item in lint_text(text, self.meta):
                if item["code"] == "tag_attribute_not_on_type":
                    offenders.append(f"{path.name}:{item['line']} {item['message']}")
        self.assertEqual(offenders, [], "\n".join(offenders[:20]))


if __name__ == "__main__":
    unittest.main()
