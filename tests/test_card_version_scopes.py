from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path

from dcore.knowledge.retrieval import card_payload


class CardVersionScopeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = sqlite3.connect(Path(__file__).resolve().parents[1] / "knowledge" / "dcore.sqlite")

    def tearDown(self) -> None:
        self.db.close()

    def test_every_card_has_one_structured_scope(self) -> None:
        cards = self.db.execute("SELECT count(*) FROM cards").fetchone()[0]
        scopes = self.db.execute("SELECT count(*) FROM card_version_scopes").fetchone()[0]
        self.assertEqual(cards, scopes)

    def test_visual_card_requires_minecraft_target(self) -> None:
        unpinned = card_payload(self.db, ["VIS-033"])[0]["version_scope_structured"]
        pinned = card_payload(self.db, ["VIS-033"], {"minecraft": "1.21.2"})[0]["version_scope_structured"]
        self.assertEqual("target_required", unpinned["status"])
        self.assertEqual("applicable_target_pinned", pinned["status"])

    def test_reflect_card_does_not_apply_without_reflect_target(self) -> None:
        scope = card_payload(self.db, ["ADD-010"], {"minecraft": "1.21.10"}, ("itemsadder@4.0.5",))[0]["version_scope_structured"]
        self.assertEqual("not_applicable", scope["status"])


if __name__ == "__main__":
    unittest.main()
