"""Build a self-contained local dCore CLI directory."""

from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from pathlib import Path

from dcore.release.artifacts import DATABASE, package_sources, release_sources
from dcore.release.bundle import ensure_safe_output, read_manifest, replace_bundle, verify_artifacts

ROOT = Path(__file__).resolve().parents[2]


def build(root: Path, output: Path, knowledge: Path | None = None) -> dict[str, object]:
    root = root.resolve()
    knowledge = (knowledge or root / "dcore/knowledge/data").resolve()
    output = ensure_safe_output(root, output)
    manifest = read_manifest(knowledge / "manifest.json")
    verify_artifacts(manifest, release_sources(root, knowledge))
    replace_bundle(output)
    runtime = output / "runtime"
    runtime.mkdir()
    for name in package_sources(root):
        destination = runtime / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / name, destination)
    database = runtime / "dcore" / "knowledge" / "data" / "dcore.sqlite"
    database.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(knowledge / "dcore.sqlite", database)
    (output / "dcore.py").write_text(
        """from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).with_name('runtime')))
from dcore.cli import main
raise SystemExit(main())
""", encoding="utf-8")
    (output / "README.txt").write_text(
        """Run: python dcore.py <command>
The canonical database is bundled at runtime/dcore/knowledge/data/dcore.sqlite.
Python 3.12+ is required.
""", encoding="utf-8")
    return {"name": "dcore-cli", "output": str(output), "files": len(list(runtime.rglob('*')))}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--knowledge", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.root, args.output, args.knowledge), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
