"""Verify the portable skill and its thin editor adapters."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REQUIRED = (
    "skill/dcore/SKILL.md", "skill/dcore/references/0.75/evidence-and-versions.md",
    "skill/dcore/references/0.75/denizen-engineering.md", "skill/dcore/references/0.75/core-shader-pipeline.md",
    "skill/dcore/references/0.75/post-effects.md", "skill/dcore/references/0.75/minecraft-1.21.md",
    "skill/dcore/references/0.75/verification.md", "skill/dcore/references/0.75/sources.md",
    "AGENTS.md", "CLAUDE.md", ".agents/rules/dcore.md", ".cursor/rules/dcore.mdc",
)
ADAPTERS = ("AGENTS.md", "CLAUDE.md", ".agents/rules/dcore.md", ".cursor/rules/dcore.mdc")


def verify(root: Path) -> dict[str, object]:
    root = root.resolve()
    failures: list[str] = []
    for name in REQUIRED:
        if not (root / name).is_file():
            failures.append(f"missing:{name}")
    skill = root / "skill/dcore/SKILL.md"
    text = skill.read_text(encoding="utf-8") if skill.is_file() else ""
    if not re.match(r"^---\s+name:\s*dcore\s+description:\s*.+?\s+---", text, re.S):
        failures.append("invalid:skill-frontmatter")
    for link in re.findall(r"\]\((references/[^)]+)\)", text):
        if not (skill.parent / link).is_file():
            failures.append(f"broken-skill-link:{link}")
    for name in ADAPTERS:
        path = root / name
        if path.is_file() and len(path.read_text(encoding="utf-8")) > 1200:
            failures.append(f"adapter-not-thin:{name}")
    for forbidden in (root / "dcore/mcp", root / "integrations/custom-gpt", root / "services/update-bridge"):
        if forbidden.exists():
            failures.append(f"forbidden-runtime:{forbidden.relative_to(root).as_posix()}")
    return {
        "verdict": "BUILD_OK" if not failures else "BUILD_BLOCKED",
        "portable_skill": "STATIC_OK" if not failures else "ERROR",
        "runtime": "RUNTIME_UNVERIFIED", "failures": failures, "required_files": len(REQUIRED),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = verify(args.root)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print(f"{result['verdict']} portable={result['portable_skill']} runtime={result['runtime']}")
        for failure in result["failures"]:
            print(f"- {failure}")
    return 0 if not result["failures"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
