"""Release measurement must not depend on the checkout platform.

Git stores text artifacts with LF and materialises them with CRLF on Windows.
Hashing the working-tree bytes made `bundle_sha256` and the 12000-byte
instructions ceiling platform-dependent: the same commit measured 77 bytes larger
on a Windows checkout than on a Linux runner, so a manifest regenerated locally
failed CI's staleness comparison and the instructions ceiling tripped on one
platform only.
"""

from __future__ import annotations

import hashlib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from dcore.release.artifacts import TEXT_SUFFIXES, artifact_bytes


class ArtifactMeasurementTests(unittest.TestCase):
    def test_text_artifacts_measure_the_same_with_either_line_ending(self) -> None:
        with TemporaryDirectory() as temporary:
            directory = Path(temporary)
            lf = directory / "lf.md"
            crlf = directory / "crlf.md"
            lf.write_bytes(b"# title\n\nbody line\n")
            crlf.write_bytes(b"# title\r\n\r\nbody line\r\n")
            self.assertEqual(artifact_bytes(lf), artifact_bytes(crlf))
            self.assertEqual(
                hashlib.sha256(artifact_bytes(lf)).hexdigest(),
                hashlib.sha256(artifact_bytes(crlf)).hexdigest(),
            )

    def test_binary_artifacts_are_never_rewritten(self) -> None:
        # A sqlite page can legitimately contain the CRLF byte pair; normalising it
        # would corrupt the digest of the database the release is built around.
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "payload.sqlite"
            payload = b"SQLite format 3\x00\r\n\x01\x02\r\n"
            path.write_bytes(payload)
            self.assertEqual(artifact_bytes(path), payload)

    def test_every_shipped_text_kind_is_normalised(self) -> None:
        from dcore.release.artifacts import KNOWLEDGE_DATA, PROJECT_DATA

        for name in (*KNOWLEDGE_DATA, *PROJECT_DATA):
            suffix = Path(name).suffix.casefold()
            if suffix == ".sqlite":
                continue
            with self.subTest(artifact=name):
                self.assertIn(suffix, TEXT_SUFFIXES, f"{name} would be hashed raw")


if __name__ == "__main__":
    unittest.main()
