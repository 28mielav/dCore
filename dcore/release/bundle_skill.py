"""Build a portable Skill with the executable dCore core beside its instructions."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path, PurePosixPath

from dcore import __version__
from dcore.release.artifacts import DATABASE, package_sources

ROOT = Path(__file__).resolve().parents[2]
FIXED_TIME = (1980, 1, 1, 0, 0, 0)


def skill_files(root: Path) -> list[Path]:
    skill = root / "skill" / "dcore"
    if not (skill / "SKILL.md").is_file():
        raise FileNotFoundError(skill / "SKILL.md")
    return sorted(path for path in skill.rglob("*") if path.is_file())


def runtime_files(root: Path) -> list[tuple[str, bytes]]:
    """Return the executable core required by offline skill hosts."""
    files: list[tuple[str, bytes]] = []
    for name in package_sources(root):
        files.append((f"runtime/{name}", (root / name).read_bytes()))
    files.append(("runtime/knowledge/dcore.sqlite", (root / DATABASE).read_bytes()))
    files.append(("runtime/README.txt", (
        b"Add runtime/ to PYTHONPATH and run: python -m dcore.cli <command>\n"
        b"Use --db runtime/knowledge/dcore.sqlite where the selected command supports it.\n"
        b"Results remain static until runtime proof is supplied.\n"
    )))
    return files


def build(root: Path, output: Path) -> dict[str, object]:
    root, output = root.resolve(), output.resolve()
    allowed = {root / "dist", root / "build", root / "temp"}
    if output.parent not in allowed or output.suffix.lower() != ".zip":
        raise ValueError("output must be a .zip directly under dist/, build/, or temp/")
    output.parent.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for path in skill_files(root):
            relative = path.relative_to(root / "skill").as_posix()
            data = path.read_bytes().replace(b"\r\n", b"\n")
            info = zipfile.ZipInfo(str(PurePosixPath(relative)), FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            bundle.writestr(info, data)
            records.append({"path": relative, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)})
        for relative, raw in runtime_files(root):
            data = raw.replace(b"\r\n", b"\n") if Path(relative).suffix in {".py", ".txt", ".md"} else raw
            info = zipfile.ZipInfo(str(PurePosixPath(relative)), FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            bundle.writestr(info, data)
            records.append({"path": relative, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)})
    result = {
        "name": "dcore", "version": __version__, "output": str(output),
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "size": output.stat().st_size, "files": records,
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.root, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
