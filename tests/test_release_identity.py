"""The release version must exist in exactly one place.

Before 0.70 the version was restated in `pyproject.toml`, the validation
contract, the database `metadata` table and the GPT instructions header. A bump
updated some of them, and the verify gate only noticed when `metadata.name`
happened to be one of the stale copies. These tests make every derived copy
answer to `dcore.__version__`.
"""

from __future__ import annotations

import json
import sqlite3
import unittest
from pathlib import Path

import dcore
from dcore.paths import DATABASE_PATH, KNOWLEDGE_DIRECTORY, REPOSITORY_ROOT


class ReleaseIdentityTest(unittest.TestCase):
    def test_release_name_is_derived(self) -> None:
        self.assertEqual(dcore.RELEASE_NAME, f"dCore {dcore.__version__}")

    def test_pyproject_takes_the_version_from_the_package(self) -> None:
        text = (REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('dynamic = ["version"]', text)
        self.assertIn('version = { attr = "dcore.__version__" }', text)
        self.assertNotIn(f'version = "{dcore.__version__}"', text)

    def test_validation_contract_matches_the_package(self) -> None:
        contract = json.loads(
            (KNOWLEDGE_DIRECTORY / "validation_contract.json").read_text(encoding="utf-8")
        )
        self.assertEqual(contract["release_version"], dcore.__version__)
        self.assertEqual(contract["metadata_name"], dcore.RELEASE_NAME)

    def test_instructions_header_matches_the_package(self) -> None:
        instructions = KNOWLEDGE_DIRECTORY / "DCORE_INSTRUCTIONS.txt"
        first_line = instructions.read_text(encoding="utf-8").splitlines()[0]
        self.assertIn(f"$dCore {dcore.__version__},", first_line)

    def test_instructions_stay_inside_the_verify_size_gate(self) -> None:
        # dcore.release.verify fails the release above 12000 bytes, measured on the
        # normalised (LF) content so the gate agrees across checkout platforms.
        # The file sits close to that ceiling, so an edit that pushes it over
        # should fail here rather than at release time.
        from dcore.release.artifacts import artifact_bytes

        size = len(artifact_bytes(KNOWLEDGE_DIRECTORY / "DCORE_INSTRUCTIONS.txt"))
        self.assertLessEqual(size, 12000, f"instructions are {size} bytes")

    def test_database_identity_matches_the_package(self) -> None:
        if not DATABASE_PATH.is_file():
            self.skipTest("knowledge database is not present")
        with sqlite3.connect(DATABASE_PATH) as db:
            rows = dict(db.execute("SELECT key,value FROM metadata WHERE key IN ('name','release.version')"))
        self.assertEqual(rows.get("name"), dcore.RELEASE_NAME)
        self.assertEqual(rows.get("release.version"), dcore.__version__)

    def test_a_migration_records_the_current_identity(self) -> None:
        # The database half of the bump is a migration, so a fresh rebuild lands
        # on the same identity as an upgraded copy.
        migrations = REPOSITORY_ROOT / "dcore" / "release" / "migrations"
        recorded = [
            path.name for path in migrations.glob("[0-9][0-9][0-9]_*.py")
            if dcore.RELEASE_NAME in path.read_text(encoding="utf-8")
        ]
        self.assertTrue(recorded, f"no migration writes metadata name {dcore.RELEASE_NAME!r}")


if __name__ == "__main__":
    unittest.main()
