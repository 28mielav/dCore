from __future__ import annotations

import hashlib
import unittest
import zipfile
from pathlib import Path

from dcore.paths import REPOSITORY_ROOT
from dcore.release.bundle_skill import build
from dcore.release.verify_skill import verify


class PortableSkillTests(unittest.TestCase):
    def test_repository_skill_verifies_without_runtime_overclaim(self) -> None:
        result = verify(REPOSITORY_ROOT)
        self.assertEqual("BUILD_OK", result["verdict"], result["failures"])
        self.assertEqual("STATIC_OK", result["portable_skill"])
        self.assertEqual("RUNTIME_UNVERIFIED", result["runtime"])

    def test_bundle_is_deterministic_and_rooted_at_dcore(self) -> None:
        # The builder deliberately restricts outputs to one direct build directory.
        (REPOSITORY_ROOT / "temp").mkdir(exist_ok=True)
        first = REPOSITORY_ROOT / "temp" / "skill-a.zip"
        second = REPOSITORY_ROOT / "temp" / "skill-b.zip"
        try:
            build(REPOSITORY_ROOT, first)
            build(REPOSITORY_ROOT, second)
            self.assertEqual(hashlib.sha256(first.read_bytes()).digest(), hashlib.sha256(second.read_bytes()).digest())
            with zipfile.ZipFile(first) as bundle:
                names = bundle.namelist()
            self.assertIn("dcore/SKILL.md", names)
            self.assertTrue(any(name.startswith("dcore/references/0.75/") for name in names))
            self.assertIn("runtime/dcore/cli.py", names)
            self.assertIn("runtime/knowledge/dcore.sqlite", names)
        finally:
            first.unlink(missing_ok=True)
            second.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
