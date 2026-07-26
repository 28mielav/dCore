from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from retrieval import (
    classify_intent,
    contrast_payload,
    resolve_meta,
    route,
    route_pattern_payload,
    run_tests,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run dCore retrieval routing tests.")
    parser.add_argument("--db", type=Path, default=Path("knowledge/dcore.sqlite"))
    parser.add_argument("--ids", nargs="*", help="Run only these retrieval test IDs.")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    with sqlite3.connect(args.db) as db:
        total = db.execute("SELECT count(*) FROM retrieval_tests").fetchone()[0]
        failures = run_tests(db, set(args.ids) if args.ids else None)
        if not args.ids:
            evidence = resolve_meta(db, "attach entity", "denizenm", (), 20)
            attach = next(
                (
                    row for row in evidence["matches"]
                    if row["product"] == "DenizenM"
                    and row["category"] == "command"
                    and row["name"].lower() == "attach"
                ),
                None,
            )
            description = " ".join(
                field["value"] for field in (attach or {}).get("fields", [])
                if field["name"] == "description"
            )
            if attach is None or "not be properly visible" not in description:
                failures.append({
                    "id": "META_NATIVE_FIRST",
                    "query": "attach entity",
                    "message": "DenizenM attach capability or its self-view limitation was not retrieved.",
                })
            intent, _ = classify_intent(
                db,
                "Сделай post shader bloom, сравни маршруты и проверь resource pack",
            )
            domains, cards = route(
                db,
                "Сделай post shader bloom, сравни маршруты и проверь resource pack",
                intent,
            )
            candidates = route_pattern_payload(
                db,
                "Сделай post shader bloom, сравни маршруты и проверь resource pack",
                domains,
                cards,
                4,
            )
            if len(candidates) < 2 or len({item["id"] for item in candidates}) < 2:
                failures.append({
                    "id": "ROUTE_CANDIDATES",
                    "query": "post shader bloom",
                    "message": "Complex visual retrieval did not expose at least two distinct route patterns.",
                })
            contrasts = contrast_payload(
                db,
                "Почему нельзя делать bloom широким blur на полном разрешении",
                ["visual", "performance"],
                2,
            )
            if not contrasts or contrasts[0]["id"] != "CX-VIS-003":
                failures.append({
                    "id": "CONTRAST_PAIR",
                    "query": "bloom blur",
                    "message": "The relevant labelled shader contrast fixture was not ranked first.",
                })
    print(json.dumps({"total": total, "failures": failures}, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
