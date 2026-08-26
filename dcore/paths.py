"""Filesystem anchors resolved once.

Every module used to recompute the root with its own `parents[N]`, so moving a
file silently changed where it looked for the database. The package root is the
only thing worth deriving from `__file__`; both bundles place `knowledge/`
beside the package, so the same anchors hold in a release.
"""

from __future__ import annotations

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = PACKAGE_ROOT.parent
KNOWLEDGE_DIRECTORY = REPOSITORY_ROOT / "knowledge"
DATABASE_PATH = KNOWLEDGE_DIRECTORY / "dcore.sqlite"
TEMP_DIRECTORY = REPOSITORY_ROOT / "temp"
