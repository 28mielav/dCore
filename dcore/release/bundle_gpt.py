"""Build a private Custom GPT upload bundle without Actions or hosted services."""

from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from pathlib import Path

from dcore.release.artifacts import DATABASE, package_sources
from dcore.release.bundle import ensure_safe_output, read_manifest, replace_bundle, verify_artifacts
from dcore.release.artifacts import release_sources

ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ARCHIVE = "dcore_runtime.zip"

BOOTSTRAP = """# dCore Code Interpreter bootstrap
import sys
from pathlib import Path

ROOT = Path('/mnt/data')
sys.path.insert(0, str(ROOT / 'dcore_runtime.zip'))
from dcore.cli import main as dcore_main

# Supply '--db', str(ROOT / 'dcore.sqlite') to commands that accept a database path.
# Example: dcore_main(['retrieve', '--db', str(ROOT / 'dcore.sqlite'), '--help'])
"""


def write_runtime(root: Path, destination: Path) -> None:
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in package_sources(root):
            archive.write(root / name, name)


def build(root: Path, output: Path, knowledge: Path | None = None) -> dict[str, object]:
    root = root.resolve()
    knowledge = (knowledge or root / "dcore/knowledge/data").resolve()
    output = ensure_safe_output(root, output)
    manifest = read_manifest(knowledge / "manifest.json")
    verify_artifacts(manifest, release_sources(root, knowledge))
    replace_bundle(output)

    upload = output / "Knowledge"
    upload.mkdir()
    write_runtime(root, upload / PACKAGE_ARCHIVE)
    for name in (DATABASE, "dcore/knowledge/data/manifest.json", "dcore/knowledge/data/lint_contract.example.json",
                 "dcore/knowledge/data/AGENT_INSTRUCTIONS.md"):
        shutil.copy2(root / name if name != DATABASE else knowledge / "dcore.sqlite", upload / Path(name).name)
    shutil.copy2(root / "gpt/INSTRUCTIONS.txt", output / "INSTRUCTIONS.txt")
    (upload / "dcore_bootstrap.py").write_text(BOOTSTRAP, encoding="utf-8")
    (output / "START_HERE.txt").write_text(
        """dCore Custom GPT build

Keep this directory private. In the GPT editor enable Code Interpreter & Data Analysis,
upload every file from Knowledge, paste INSTRUCTIONS.txt into the GPT instruction field,
and enable Code Interpreter & Data Analysis. dCore analyses uploaded files with the same Python core used by the CLI.
It has no Action, hosted bridge, API key, or network dependency.
""", encoding="utf-8")
    return {"name": "dcore-gpt", "output": str(output), "files": len(list(upload.iterdir()))}


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
