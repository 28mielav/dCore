from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path


KNOWLEDGE_FILES = (
    "dcore.sqlite",
    "manifest.json",
    "retrieval.py",
    "dcore_lint.py",
    "dcore_design.py",
    "dcore_rp_lint.py",
    "lint_contract.example.json",
)


def source_file(root: Path, knowledge: Path, name: str) -> Path:
    candidates = (knowledge / name, root / "tools" / name, root / "knowledge" / name)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(name)


def build(root: Path, output: Path, knowledge: Path | None = None) -> Path:
    root = root.resolve()
    knowledge = (knowledge or root / "knowledge").resolve()
    output = output.resolve()
    if output in {root, knowledge, root / "tools"}:
        raise ValueError("output must be a dedicated bundle directory")
    if output.exists():
        shutil.rmtree(output)

    upload = output / "GPT_Knowledge"
    instructions = output / "GPT_Instructions"
    maintenance = output / "Maintenance"
    action = output / "Custom_GPT_Action"
    for directory in (upload, instructions, maintenance, action):
        directory.mkdir(parents=True, exist_ok=True)

    for name in KNOWLEDGE_FILES:
        shutil.copy2(source_file(root, knowledge, name), upload / name)
    shutil.copy2(source_file(root, knowledge, "DCORE_INSTRUCTIONS.txt"), instructions / "DCORE_INSTRUCTIONS.txt")
    shutil.copy2(root / "tools" / "update_knowledge.py", maintenance / "update_knowledge.py")
    shutil.copy2(root / "knowledge" / "visual_sources.json", maintenance / "visual_sources.json")
    shutil.copy2(root / "integrations" / "custom-gpt" / "openapi.yaml", action / "openapi.yaml")

    manifest = json.loads((upload / "manifest.json").read_text(encoding="utf-8"))
    action_text = (action / "openapi.yaml").read_text(encoding="utf-8")
    action_version_match = re.search(r"(?m)^\s*version:\s*([^\s#]+)", action_text)
    action_version = action_version_match.group(1) if action_version_match else "unknown"
    readme = f"""dCore 0.31 - ready Custom GPT bundle

1. Delete the previous dCore Knowledge files from the GPT.
2. Upload only the 7 files inside GPT_Knowledge.
3. Replace GPT Instructions with GPT_Instructions/DCORE_INSTRUCTIONS.txt.
4. This bundle uses Custom GPT Action schema {action_version}. Re-import
   Custom_GPT_Action/openapi.yaml only when the installed schema is older or different.

Maintenance contains updater inputs for the private repository. It is not GPT Knowledge.
Custom_GPT_Action contains the current Action schema for backup/reinstallation.

Verified bundle: {manifest.get('bundle_sha256', 'pending manifest rebuild')}
Database: {manifest.get('sha256', 'pending manifest rebuild')}
"""
    (output / "START_HERE.txt").write_text(readme, encoding="utf-8")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Build one human-organized dCore Custom GPT bundle")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--knowledge", type=Path, help="Verified candidate directory used by CI")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(build(args.root, args.output, args.knowledge))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
