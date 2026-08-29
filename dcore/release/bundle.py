from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from dcore.release.artifacts import artifact_bytes


def sha256(path: Path) -> str:
    # Must be the same measurement the verifier wrote into the manifest. Hashing
    # raw bytes here while verify.py normalised text made every bundle build fail
    # on a CRLF checkout.
    return hashlib.sha256(artifact_bytes(path)).hexdigest()


def ensure_safe_output(root: Path, output: Path) -> Path:
    """Allow replacement only of one named bundle under builds/ or dist/."""
    root = root.resolve()
    output = output.resolve()
    allowed_roots = (root / "build", root / "builds", root / "dist", root / "temp")
    if not any(output.parent == allowed for allowed in allowed_roots):
        allowed_text = ", ".join(str(item) for item in allowed_roots)
        raise ValueError(f"output must be a direct child of: {allowed_text}")
    if output.name.startswith(".") or not output.name:
        raise ValueError("output must be a named bundle directory")
    return output


def replace_bundle(output: Path) -> None:
    """Remove only a path already accepted by ensure_safe_output()."""
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=False)


def read_manifest(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("status") != "verified":
        raise ValueError("cannot package an unverified manifest")
    if not isinstance(data.get("artifacts"), dict):
        raise ValueError("manifest has no artifact inventory")
    return data


def verify_artifacts(manifest: dict, sources: dict[str, Path]) -> None:
    expected = manifest["artifacts"]
    expected_names = set(expected)
    actual_names = set(sources)
    if expected_names != actual_names:
        missing = sorted(expected_names - actual_names)
        extra = sorted(actual_names - expected_names)
        raise ValueError(f"manifest/source mismatch: missing={missing}; extra={extra}")
    for name, path in sources.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        record = expected[name]
        # Compare against the normalised size the manifest recorded, not the raw
        # stat() size: a text artifact checked out with CRLF is bytes larger on
        # disk than the LF content that was actually hashed.
        if record.get("sha256") != sha256(path) or record.get("size") != len(artifact_bytes(path)):
            raise ValueError(f"artifact does not match verified manifest: {name}")
