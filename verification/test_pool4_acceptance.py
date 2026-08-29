from __future__ import annotations

import unittest

from dcore.acceptance.pool4 import load_corpus, phase_post


class Pool4AcceptanceTests(unittest.TestCase):
    def test_golden_corpus_has_ten_scenarios_and_five_sources(self) -> None:
        corpus = load_corpus()
        self.assertEqual("pool4-1", corpus["version"])
        self.assertEqual(5, len(corpus["sources"]))
        self.assertEqual(10, len(corpus["scenarios"]))

    def test_final_five_pool4_checks_are_green(self) -> None:
        results = phase_post(load_corpus())
        self.assertEqual(5, len(results))
        self.assertEqual([], [item for item in results if item["status"] != "PASS"])


if __name__ == "__main__":
    unittest.main()
