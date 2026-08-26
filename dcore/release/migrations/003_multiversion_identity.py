from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


TARGET = (
    "Multi-version Minecraft/Paper + Denizen/DenizenM; select exact source/build "
    "per request and treat installed runtime as final proof"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    args = parser.parse_args()

    with sqlite3.connect(args.db) as db:
        db.execute(
            "INSERT INTO metadata(key,value) VALUES('meta.target',?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (TARGET,),
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
