"""MCP startup and dCore knowledge health check."""
from __future__ import annotations
import argparse
import json
import sqlite3
from pathlib import Path
from dcore import __version__
from dcore.paths import DATABASE_PATH, KNOWLEDGE_DIRECTORY

def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DATABASE_PATH)
    parser.add_argument("--json", action="store_true")
    args=parser.parse_args()
    db=args.db.resolve()
    manifest=KNOWLEDGE_DIRECTORY / "manifest.json"
    result={"server":"dcore","version":__version__,"status":"STARTED","database":{"path":str(db),"available":db.is_file()},"manifest":{"path":str(manifest),"available":manifest.is_file()}}
    if not db.is_file():
        result["status"]="DEGRADED"
        print(json.dumps(result,ensure_ascii=False))
        return 1
    with sqlite3.connect(db) as conn:
        tables=[row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        result["database"]["tables"]=tables
        result["database"]["counts"]={table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in ("cards","meta_preferred","ide_diagnostics","version_artifacts","visual_sources") if table in tables}
    print(json.dumps(result,ensure_ascii=False))
    return 0

if __name__ == "__main__": raise SystemExit(main())
