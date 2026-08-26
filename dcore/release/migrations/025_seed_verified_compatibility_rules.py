from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


RULES = (
    (
        "itemsadder-4.0.3-mc-1.21.1", "itemsadder", "4.0.3",
        "1.21.1", "1.21.1", None, None, "Paper/Purpur",
        "reported_supported", "maintainer_report",
        "https://github.com/PluginBugs/Issues-ItemsAdder/issues/4082",
        "Maintainer comment dated 2024-10-27 says ItemsAdder 4.0.3 supported 1.21.1 at that time. This is a narrow historical record, not a claim for all 4.x releases.",
        "2026-08-08",
    ),
    (
        "itemsadder-4.0.5-mc-1.21.2-shader-transition", "itemsadder", "4.0.5",
        "1.21.2", None, None, None, "Paper/Purpur",
        "requires_pack_regeneration", "maintainer_report",
        "https://github.com/PluginBugs/Issues-ItemsAdder/issues/4177",
        "4.0.5 recorded an automatic overlay for the 1.21.2 shader JSON transition. Regenerate and validate the final resource pack for the exact client.",
        "2026-08-08",
    ),
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    args = parser.parse_args()
    with sqlite3.connect(args.db) as db:
        db.executemany(
            """INSERT OR REPLACE INTO compatibility_rules(
              rule_id,subject,release_family,minecraft_min,minecraft_max,paper_min,paper_max,
              provider,status,confidence,evidence_url,notes,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            RULES,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
