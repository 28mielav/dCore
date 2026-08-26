"""Master-key handling and per-project key derivation.

The master key never leaves the operator's machine and is never written to a
release. Everything a release actually needs is a project-scoped key derived
from it with HKDF, salted per release so two releases never share a key even
if the project id repeats.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

APP_NAME = "DscPack"


def key_path() -> Path:
    appdata = os.environ.get("APPDATA")
    root = Path(appdata) if appdata else Path.home() / ".config"
    return root / APP_NAME / "master.key"


def install_key(path: Path, force: bool = False) -> None:
    if path.exists() and not force:
        raise SystemExit(f"key already exists: {path} (use --force to replace it)")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(secrets.token_bytes(32))
    print(f"installed master key: {path}")
    print("save a copy outside the server; losing it makes recovery impossible")


def read_key(path: Path | None) -> bytes:
    target = path or key_path()
    raw = target.read_bytes()
    if len(raw) != 32:
        raise ValueError(f"master key must be exactly 32 bytes: {target}")
    return raw


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii")


def unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value.encode("ascii"))


def derive_key(master: bytes, salt: bytes, project_id: str) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=("dscpack/v2/" + project_id).encode("utf-8"),
    ).derive(master)


def opaque_id(master: bytes, kind: str, value: str, size: int = 10) -> str:
    """A stable, non-reversible name derived from the master key.

    Same (master, kind, value) always yields the same id, so a container
    or definition keeps its obfuscated name across rebuilds without the
    release recording anything that identifies the original.
    """
    digest = hmac.new(master, f"dscpack:{kind}:{value}".encode("utf-8"), hashlib.sha256).digest()
    return base64.b32hexencode(digest[:size]).decode("ascii").lower().rstrip("=")
