"""Move the database release identity to 0.70.

The verify gate compares `metadata.name` against the release contract, so the
version cannot be bumped in text alone.

The strings below are deliberately frozen literals rather than an import of
`dcore.__version__`. A migration is a historical record: if it read the current
version, rebuilding a database from scratch after the next bump would write that
newer name here and make the following migration's intent ambiguous. Drift
between this row and the running package is caught by
`tests/test_release_identity.py`, which is the right place for a live check.
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


ROWS = (
    ("name", "dCore 0.70"),
    ("release.version", "0.70"),
    
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    args = parser.parse_args()
    with sqlite3.connect(args.db) as db:
        db.executemany("INSERT OR REPLACE INTO metadata(key,value) VALUES(?,?)", ROWS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
