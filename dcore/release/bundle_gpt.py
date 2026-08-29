"""Build the Custom GPT bundle.

Custom GPT Knowledge is a flat upload, so a package directory cannot be
imported from it. The package therefore ships as one importable zip: Python
adds a zip to `sys.path` and imports from it directly. That also cuts the
upload set from nineteen files to five.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import zipfile
from pathlib import Path

from dcore.release.artifacts import (
    DATABASE,
    MANIFEST,
    PACKAGE_DIRECTORY,
    package_sources,
    release_sources,
)
from dcore.release.bundle import ensure_safe_output, read_manifest, replace_bundle, verify_artifacts

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

PACKAGE_ARCHIVE = "dcore.zip"

KNOWLEDGE_UPLOAD = (
    PACKAGE_ARCHIVE,
    "dcore.sqlite",
    "manifest.json",
    "lint_contract.example.json",
    "pool4_golden_corpus.json",
)

BOOTSTRAP = f"""import sys

sys.path.insert(0, "/mnt/data/{PACKAGE_ARCHIVE}")

from dcore.knowledge.retrieval import main as retrieve
from dcore.lint.script import main as lint
"""


def write_package_archive(root: Path, destination: Path) -> None:
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in package_sources(root):
            archive.write(root / name, name)


def build(root: Path, output: Path, knowledge: Path | None = None) -> Path:
    root = root.resolve()
    knowledge = (knowledge or root / "knowledge").resolve()
    output = ensure_safe_output(root, output)
    manifest_path = knowledge / "manifest.json"
    manifest = read_manifest(manifest_path)
    sources = release_sources(root, knowledge)
    verify_artifacts(manifest, sources)
    replace_bundle(output)

    upload = output / "Knowledge"
    instructions = output / "Instructions"
    maintenance = output / "Maintenance"
    action = output / "Action"
    for directory in (upload, instructions, maintenance, action):
        directory.mkdir(parents=True, exist_ok=True)

    write_package_archive(root, upload / PACKAGE_ARCHIVE)
    shutil.copy2(sources[DATABASE], upload / "dcore.sqlite")
    shutil.copy2(manifest_path, upload / "manifest.json")
    shutil.copy2(sources["knowledge/lint_contract.example.json"], upload / "lint_contract.example.json")
    shutil.copy2(sources["knowledge/pool4_golden_corpus.json"], upload / "pool4_golden_corpus.json")
    (upload / "dcore_bootstrap.py").write_text(BOOTSTRAP, encoding="utf-8")

    shutil.copy2(sources["knowledge/DCORE_INSTRUCTIONS.txt"], instructions / "DCORE_INSTRUCTIONS.txt")
    shutil.copy2(sources["knowledge/visual_sources.json"], maintenance / "visual_sources.json")
    shutil.copy2(sources["knowledge/validation_contract.json"], maintenance / "validation_contract.json")
    shutil.copy2(sources["integrations/custom-gpt/openapi.yaml"], action / "openapi.yaml")

    action_text = (action / "openapi.yaml").read_text(encoding="utf-8")
    action_version_match = re.search(r"(?m)^\s*version:\s*([^\s#]+)", action_text)
    action_version = action_version_match.group(1) if action_version_match else "unknown"
    installed = json.loads((upload / "manifest.json").read_text(encoding="utf-8"))
    (output / "START_HERE.txt").write_text(
        f"""dCore {installed.get('version', 'unknown')} - ready Custom GPT bundle

1. Delete the previous dCore Knowledge files from the GPT.
2. Upload every file inside Knowledge ({len(KNOWLEDGE_UPLOAD) + 1} files).
3. Replace GPT Instructions with Instructions/DCORE_INSTRUCTIONS.txt.
4. This bundle uses Custom GPT Action schema {action_version}. Re-import
   Action/openapi.yaml only when the installed schema is older or different.

{PACKAGE_ARCHIVE} is an importable package archive. Run dcore_bootstrap.py, or
prepend it to sys.path, before importing anything from dcore.

Maintenance contains updater inputs for the private repository. It is not GPT Knowledge.
Action contains the current Action schema for backup and reinstallation.

Verified bundle: {installed.get('bundle_sha256', 'pending manifest rebuild')}
Database: {installed.get('sha256', 'pending manifest rebuild')}
""",
        encoding="utf-8",
    )
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Build one human-organized dCore Custom GPT bundle")
    parser.add_argument("--root", type=Path, default=REPOSITORY_ROOT)
    parser.add_argument("--knowledge", type=Path, help="Verified candidate directory used by CI")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(build(args.root, args.output, args.knowledge))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
