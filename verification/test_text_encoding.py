from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".md", ".txt", ".yaml", ".yml", ".json", ".py"}
MOJIBAKE_RUN = re.compile(r"(?:(?:Ð.|Р.|С.|вЂ)){3,}")


class TextEncodingTests(unittest.TestCase):
    def test_release_text_is_utf8_and_has_no_common_mojibake_runs(self) -> None:
        paths = [ROOT / "README.md"]
        for directory in (ROOT / "dcore" / "knowledge" / "data", ROOT / "skill", ROOT / "gpt", ROOT / "docs"):
            paths.extend(path for path in directory.rglob("*") if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES)
        failures = []
        for path in paths:
            text = path.read_text(encoding="utf-8")
            if MOJIBAKE_RUN.search(text):
                failures.append(str(path.relative_to(ROOT)))
        self.assertEqual([], failures, f"common UTF-8 mojibake detected: {failures}")


if __name__ == "__main__":
    unittest.main()
