from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from dcore.knowledge.version_registry import VersionArtifact, ensure_schema, import_catalogue, normalize_product_version


class VersionRegistryTests(unittest.TestCase):
    def test_normalizes_only_denizenm_jar_build_decoration(self) -> None:
        self.assertEqual("7299M", normalize_product_version("DenizenM", "b7299M"))
        self.assertEqual("7299M2", normalize_product_version("denizenm", "b7299M2"))
        self.assertEqual("b7299M", normalize_product_version("Denizen", "b7299M"))
        self.assertEqual("unknown", normalize_product_version("DenizenM", "unknown"))

    def test_import_preserves_source_identity_and_edges(self) -> None:
        items = [
            VersionArtifact("denizenm:7290m", "DenizenM", "7290M", "repo", "7290M", "a" * 40, "tag", "denizenm", discovered_at="now"),
            VersionArtifact("denizenm:7299m", "DenizenM", "7299M", "repo", "7299M", "b" * 40, "tag", "denizenm", discovered_at="now"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "versions.sqlite"
            self.assertEqual(2, import_catalogue(db_path, items))
            db = sqlite3.connect(db_path)
            try:
                self.assertEqual(2, db.execute("SELECT count(*) FROM version_artifacts").fetchone()[0])
                self.assertEqual(1, db.execute("SELECT count(*) FROM version_edges").fetchone()[0])
                self.assertEqual("unverified", db.execute("SELECT runtime_status FROM version_artifacts LIMIT 1").fetchone()[0])
            finally:
                db.close()

    def test_schema_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db = sqlite3.connect(Path(directory) / "versions.sqlite")
            ensure_schema(db)
            ensure_schema(db)
            self.assertIsNotNone(db.execute("SELECT name FROM sqlite_master WHERE name='version_artifacts'").fetchone())
            db.close()


if __name__ == "__main__":
    unittest.main()
