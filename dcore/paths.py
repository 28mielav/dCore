"""Filesystem anchors resolved once.

Every module used to recompute the root with its own `parents[N]`, so moving a
file silently changed where it looked for the database. The canonical database
stays inside the product package, so every delivery starts from the same source.
"""

from __future__ import annotations

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = PACKAGE_ROOT.parent
KNOWLEDGE_DIRECTORY = PACKAGE_ROOT / "knowledge" / "data"
DATABASE_PATH = KNOWLEDGE_DIRECTORY / "dcore.sqlite"
VERIFICATION_DIRECTORY = REPOSITORY_ROOT / "build" / "verification"
