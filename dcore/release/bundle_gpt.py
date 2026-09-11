"""Build a Custom GPT upload bundle without Actions or hosted services."""

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
    shutil.copy2(root / "gpt/bootstrap.py", upload / "dcore_bootstrap.py")
    (output / "START_HERE.txt").write_text(
        """dCore Custom GPT build

In the GPT editor enable Code Interpreter & Data Analysis,
upload every file from Knowledge, paste INSTRUCTIONS.txt into the GPT instruction field,
dCore analyses uploaded files with the same Python core used by the CLI.
If Knowledge files are unavailable to Python, attach dcore_runtime.zip, dcore.sqlite
and dcore_bootstrap.py directly in the conversation. Never report a run without executing it.
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
