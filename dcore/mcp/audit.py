"""Unified project audit for the dCore MCP surface."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from dcore.lint.resourcepack import Pack, lint_pack
from dcore.lint.script import MetaIndex, lint_text
from dcore.paths import DATABASE_PATH

def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--db", type=Path, default=DATABASE_PATH)
    parser.add_argument("--profile", default="denizenm")
    parser.add_argument("--minecraft")
    parser.add_argument("--paper")
    parser.add_argument("--java")
    parser.add_argument("--denizen-version")
    parser.add_argument("--denizenm")
    parser.add_argument("--addon", action="append", default=[])
    parser.add_argument("--closed-world", action="store_true")
    args=parser.parse_args()
    files=[]
    packs=[]
    for raw in args.paths:
        path=Path(raw)
        if path.is_dir() and (path / "pack.mcmeta").is_file():
            packs.append(path)
        elif path.is_dir():
            files.extend(sorted(path.rglob("*.dsc")))
            files.extend(sorted(path.rglob("*.DSC")))
            if (path / "assets").is_dir(): packs.append(path)
        elif path.suffix.casefold()==".dsc": files.append(path)
        elif path.suffix.casefold()==".zip": packs.append(path)
    meta=MetaIndex(args.db, args.profile, set(args.addon), target={"minecraft": args.minecraft or "", "denizenm": args.denizenm or "", "denizen": args.denizen_version or ""})
    scripts=[]; blocking=False
    for path in dict.fromkeys(files):
        findings=lint_text(path.read_text(encoding="utf-8"), meta)
        scripts.append({"path":str(path),"findings":findings})
        blocking = blocking or any(item.get("severity") in {"error","warning"} for item in findings)
    shader=[]
    for path in dict.fromkeys(packs):
        report=lint_pack(Pack.open(path), minecraft=args.minecraft, pack_format=None)
        shader.append(report)
        blocking = blocking or report.get("static_verdict") == "ERROR"
    result={"verdict":"AUDIT_BLOCKED" if blocking else "AUDIT_STATIC_OK","scripts":scripts,"resource_packs":shader,"runtime_status":"RUNTIME_UNVERIFIED" if shader else None}
    print(json.dumps(result, ensure_ascii=False))
    return 1 if blocking else 0
if __name__ == "__main__": raise SystemExit(main())
