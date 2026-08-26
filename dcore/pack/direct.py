"""Direct deployment: obfuscated `.dsc` straight into a server scripts folder.

No archive. Each source gets one encrypted sidecar (`.bin`) recording enough
to restore it and to verify its current obfuscated output, so a later call
touching only a changed file can leave every other file's sidecar alone.
Denizen never loads `.bin`, so nothing here changes what the server reads.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from dcore.pack.keys import b64, derive_key, unb64, opaque_id
from dcore.pack.release import FORMAT_VERSION
from dcore.pack.semantic import semantic_obfuscate_sources

DIRECT_MAGIC = b"DSCP_DIRECT_FILE_2\0"


def collect_direct_sources(inputs: list[Path], base_dir: Path) -> list[tuple[str, bytes]]:
    """Collect sources with stable paths for incremental direct deployment."""
    base = base_dir.resolve()
    files: list[tuple[str, bytes]] = []
    for item in inputs:
        path = item.resolve()
        candidates = sorted(path.rglob("*.dsc")) if path.is_dir() else [path]
        if not candidates or (not path.is_dir() and path.suffix.lower() != ".dsc"):
            raise ValueError(f"input is not a .dsc file or directory: {item}")
        for candidate in candidates:
            if not candidate.is_file() or candidate.suffix.lower() != ".dsc":
                continue
            try:
                relative = candidate.relative_to(base).as_posix()
            except ValueError as error:
                raise ValueError(f"source must be inside --root: {candidate}") from error
            files.append((relative, candidate.read_bytes()))
    if not files:
        raise ValueError("no .dsc files selected")
    names = [name for name, _ in files]
    if len(names) != len(set(names)):
        raise ValueError("duplicate relative file names; select each source only once")
    return files


def direct_sidecar_path(output: Path, master: bytes, relative: str) -> Path:
    module = output / f"p_{opaque_id(master, 'path', relative, 6)}"
    return module / f"r_{opaque_id(master, 'restore', relative)}.bin"


def encode_direct_sidecar(
    master: bytes, project_id: str, relative: str, raw: bytes, outputs: dict[str, str], mode: str
) -> bytes:
    salt = secrets.token_bytes(16)
    nonce = secrets.token_bytes(12)
    header = {
        "format": FORMAT_VERSION,
        "project_id": project_id,
        "mode": mode,
        "salt": b64(salt),
        "nonce": b64(nonce),
    }
    payload = json.dumps({
        "source": relative,
        "raw": b64(raw),
        "outputs": outputs,
    }, sort_keys=True).encode("utf-8")
    key = derive_key(master, salt, project_id)
    encrypted = AESGCM(key).encrypt(nonce, payload, f"direct:{project_id}".encode())
    header_bytes = json.dumps(header, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return DIRECT_MAGIC + len(header_bytes).to_bytes(4, "big") + header_bytes + encrypted


def decode_direct_sidecar(path: Path, master: bytes) -> tuple[str, bytes, dict[str, str], str]:
    data = path.read_bytes()
    if not data.startswith(DIRECT_MAGIC):
        raise ValueError(f"not a dcore.pack sidecar: {path}")
    header_start = len(DIRECT_MAGIC)
    header_end = header_start + 4 + int.from_bytes(data[header_start:header_start + 4], "big")
    header = json.loads(data[header_start + 4:header_end])
    project_id = header["project_id"]
    salt = unb64(header["salt"])
    nonce = unb64(header["nonce"])
    payload = AESGCM(derive_key(master, salt, project_id)).decrypt(
        nonce, data[header_end:], f"direct:{project_id}".encode()
    )
    decoded = json.loads(payload)
    return decoded["source"], unb64(decoded["raw"]), decoded.get("outputs", {}), header.get("mode", "hard")


def load_direct_catalog(output: Path, master: bytes) -> dict[str, tuple[bytes, Path, dict[str, str], str]]:
    catalog: dict[str, tuple[bytes, Path, dict[str, str], str]] = {}
    if not output.exists():
        return catalog
    for sidecar in output.rglob("*.bin"):
        if not sidecar.is_file() or not sidecar.read_bytes().startswith(DIRECT_MAGIC):
            continue
        relative, raw, outputs, mode = decode_direct_sidecar(sidecar, master)
        if relative in catalog:
            raise ValueError(f"duplicate direct source sidecar: {relative}")
        catalog[relative] = (raw, sidecar, outputs, mode)
    return catalog


def direct_deploy(
    inputs: list[Path], output: Path, master: bytes, project_id: str, base_dir: Path, mode: str = "hard"
) -> None:
    selected = collect_direct_sources(inputs, base_dir)
    catalog = load_direct_catalog(output, master)
    existing_modes = {entry[3] for entry in catalog.values()}
    if existing_modes and existing_modes != {mode}:
        raise ValueError(f"direct deployment mode mismatch: existing={sorted(existing_modes)} requested={mode}; use a clean output folder")
    for relative, raw in selected:
        catalog[relative] = (raw, direct_sidecar_path(output, master, relative), {}, mode)

    all_sources = [(relative, entry[0]) for relative, entry in sorted(catalog.items())]
    _, _, semantic_outputs = semantic_obfuscate_sources(all_sources, master, mode)
    transformed_by_source = {source: data for _, data, source in semantic_outputs}

    output.mkdir(parents=True, exist_ok=True)
    selected_names = {relative for relative, _ in selected}
    for relative, raw in selected:
        module = output / f"p_{opaque_id(master, 'path', relative, 6)}"
        module.mkdir(parents=True, exist_ok=True)
        for stale in (*module.glob("c_*.dsc"), *module.glob("f_*.dsc")):
            stale.unlink()
        transformed_outputs = [
            (f"p_{opaque_id(master, 'path', relative, 6)}/f_{opaque_id(master, 'file', relative)}.dsc", transformed_by_source[relative], [])
        ]
        output_hashes: dict[str, str] = {}
        for output_name, data, _ in transformed_outputs:
            destination = output / output_name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
            output_hashes[output_name] = hashlib.sha256(data).hexdigest()
        sidecar = direct_sidecar_path(output, master, relative)
        sidecar.parent.mkdir(parents=True, exist_ok=True)
        sidecar.write_bytes(encode_direct_sidecar(master, project_id, relative, raw, output_hashes, mode))
    print(f"deployed {len(selected_names)} source files to {output}")


def verify_direct(output: Path, master: bytes) -> None:
    catalog = load_direct_catalog(output, master)
    if not catalog:
        raise ValueError(f"no dcore.pack sidecars found in: {output}")
    checked_outputs = 0
    modes = {entry[3] for entry in catalog.values()}
    for relative, (_, _, outputs, _) in catalog.items():
        for output_name, expected_hash in outputs.items():
            path = output / output_name
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
                raise ValueError(f"direct executable checksum mismatch for {relative}: {output_name}")
            checked_outputs += 1
    print(f"verified direct deployment {output} mode={','.join(sorted(modes))} ({len(catalog)} source files, {checked_outputs} executable files)")


def restore_direct(output: Path, destination: Path, master: bytes) -> None:
    catalog = load_direct_catalog(output, master)
    if not catalog:
        raise ValueError(f"no dcore.pack sidecars found in: {output}")
    destination.mkdir(parents=True, exist_ok=True)
    for relative, (raw, _, _, _) in catalog.items():
        target = (destination / relative).resolve()
        root = destination.resolve()
        if target != root and root not in target.parents:
            raise ValueError(f"unsafe restored path: {relative}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    print(f"restored direct deployment {output} to {destination}")


__all__ = [
    "DIRECT_MAGIC",
    "collect_direct_sources",
    "decode_direct_sidecar",
    "direct_deploy",
    "direct_sidecar_path",
    "encode_direct_sidecar",
    "load_direct_catalog",
    "restore_direct",
    "verify_direct",
]
