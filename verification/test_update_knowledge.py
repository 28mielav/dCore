import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from dcore.release.update import current_versions, load_visual_registry, record_visual_heads


SCHEMA = """
CREATE TABLE visual_sources(
  source_id TEXT PRIMARY KEY, repository TEXT, url TEXT, branch TEXT,
  indexed_commit_sha TEXT, latest_seen_sha TEXT, license TEXT,
  license_status TEXT, ingest_policy TEXT, version_scope TEXT,
  pipelines_json TEXT, graphics_modes_json TEXT, modules_json TEXT,
  review_status TEXT, notes TEXT);
"""


class VisualSourceUpdateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "dcore.sqlite"
        with closing(sqlite3.connect(self.db_path)) as db:
            db.executescript(SCHEMA)
            db.execute(
                "INSERT INTO visual_sources VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                ("source", "owner/repo", "https://example.invalid", "main", "old", "old",
                 "MIT", "verified", "mechanism", "v1", "[]", "[]", "[]", "indexed", ""),
            )
            db.commit()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_changed_source_is_review_pending_without_advancing_index(self) -> None:
        with closing(sqlite3.connect(self.db_path)) as db:
            record_visual_heads(db, {"source": "new"})
            db.commit()
            row = db.execute(
                "SELECT indexed_commit_sha,latest_seen_sha,review_status FROM visual_sources"
            ).fetchone()
        self.assertEqual(("old", "new", "review_pending"), row)

    def test_matching_source_is_indexed(self) -> None:
        with closing(sqlite3.connect(self.db_path)) as db:
            record_visual_heads(db, {"source": "old"})
            db.commit()
        _, _, visual = current_versions(self.db_path)
        self.assertEqual("indexed", visual["source"]["review_status"])

    def test_registry_requires_sources(self) -> None:
        path = Path(self.temp.name) / "registry.json"
        path.write_text(json.dumps({"schema_version": 1, "sources": []}), encoding="utf-8")
        with self.assertRaises(RuntimeError):
            load_visual_registry(path)


if __name__ == "__main__":
    unittest.main()
