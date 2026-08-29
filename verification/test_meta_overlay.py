from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path

from dcore.knowledge.meta_resolution import effective_sources, overlay_state
from dcore.knowledge.retrieval import resolve_meta


class MetaOverlayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = sqlite3.connect(Path(__file__).resolve().parents[1] / "dcore" / "knowledge" / "data" / "dcore.sqlite")
        self.db.row_factory = sqlite3.Row

    def tearDown(self) -> None:
        self.db.close()

    def test_historical_source_expands_to_current_base(self) -> None:
        selected = ["meta_denizenm_tag_7268m"]
        effective, state = effective_sources(self.db, selected)
        self.assertIn("denizenm_public_master", effective)
        self.assertEqual("denizenm_public_master", state[selected[0]]["base"])

    def test_old_target_preserves_override_after_compaction(self) -> None:
        result = resolve_meta(self.db, "teleport", "denizenm", (), denizenm_version="7268M")
        teleport = next(row for row in result["matches"] if row["product"] == "DenizenM" and row["name"] == "Teleport")
        self.assertEqual("meta_denizenm_tag_7268m", teleport["source_id"])
        self.assertNotIn("(async)", teleport["syntax"])

    def test_all_historical_sources_have_overlay_metadata(self) -> None:
        historical = self.db.execute("SELECT count(*) FROM meta_sources WHERE artifact_id IS NOT NULL").fetchone()[0]
        overlays = self.db.execute("SELECT count(*) FROM meta_delta_sources").fetchone()[0]
        self.assertEqual(historical, overlays)
        self.assertGreater(self.db.execute("SELECT count(*) FROM meta_version_tombstones").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
