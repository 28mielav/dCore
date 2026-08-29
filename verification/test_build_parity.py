from __future__ import annotations

import unittest
import zipfile
from pathlib import Path

from dcore.paths import REPOSITORY_ROOT
from dcore.release.bundle_cli import build as build_cli
from dcore.release.bundle_gpt import build as build_gpt


class BuildParityTests(unittest.TestCase):
    def test_cli_and_gpt_contain_the_executable_core_and_database(self) -> None:
        cli = REPOSITORY_ROOT / "build" / "verification-parity-cli"
        gpt = REPOSITORY_ROOT / "build" / "verification-parity-gpt"
        try:
            build_cli(REPOSITORY_ROOT, cli)
            build_gpt(REPOSITORY_ROOT, gpt)
            self.assertTrue((cli / "runtime" / "dcore" / "lint" / "script.py").is_file())
            self.assertTrue((cli / "runtime" / "dcore" / "knowledge" / "data" / "dcore.sqlite").is_file())
            self.assertTrue((gpt / "Knowledge" / "dcore.sqlite").is_file())
            with zipfile.ZipFile(gpt / "Knowledge" / "dcore_runtime.zip") as archive:
                self.assertIn("dcore/lint/script.py", archive.namelist())
        finally:
            for path in (cli, gpt):
                if path.exists():
                    import shutil
                    shutil.rmtree(path)


if __name__ == "__main__":
    unittest.main()
