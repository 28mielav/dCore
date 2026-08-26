from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path

from dcore.knowledge.retrieval import compatibility_advice, resolve_meta


class MultiVersionMetaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = sqlite3.connect(Path(__file__).resolve().parents[1] / "knowledge" / "dcore.sqlite")

    def tearDown(self) -> None:
        self.db.close()

    def test_old_denizenm_target_does_not_borrow_current_async_teleport(self) -> None:
        old = resolve_meta(self.db, "teleport", "denizenm", (), denizenm_version="7268M")
        new = resolve_meta(self.db, "teleport", "denizenm", (), denizenm_version="7299M")
        old_syntax = next(row["syntax"] for row in old["matches"] if row["product"] == "DenizenM" and row["name"] == "Teleport")
        new_syntax = next(row["syntax"] for row in new["matches"] if row["product"] == "DenizenM" and row["name"] == "Teleport")
        self.assertIn("meta_denizenm_tag_7268m", old["source_scope"])
        self.assertNotIn("(async)", old_syntax)
        self.assertIn("(async)", new_syntax)

    def test_b_prefixed_denizenm_build_resolves_same_snapshot(self) -> None:
        plain = resolve_meta(self.db, "teleport", "denizenm", (), denizenm_version="7299M")
        prefixed = resolve_meta(self.db, "teleport", "denizenm", (), denizenm_version="b7299M")
        self.assertEqual(plain["source_scope"], prefixed["source_scope"])
        self.assertEqual(plain["matches"][0]["syntax"], prefixed["matches"][0]["syntax"])

    def test_unknown_addon_release_is_not_guessed(self) -> None:
        advice = compatibility_advice(self.db, ("itemsadder@3.6.5",), "1.20.6", None)
        self.assertEqual("no_recorded_rule", advice[0]["status"])

    def test_recorded_addon_transition_is_returned(self) -> None:
        advice = compatibility_advice(self.db, ("itemsadder@4.0.5",), "1.21.2", None)
        self.assertEqual("requires_pack_regeneration", advice[0]["status"])


if __name__ == "__main__":
    unittest.main()
