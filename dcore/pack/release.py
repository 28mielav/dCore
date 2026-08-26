"""Encrypted release archives: build, verify, restore.

A release contains executable obfuscated `.dsc` files plus an AES-GCM
encrypted copy of the original source and its manifest. The master key
derives a fresh per-release key from a random salt, so the release carries
everything needed to restore except the key itself.
"""

from __future__ import annotations

import hashlib
import io
import json
import secrets
import zipfile
from pathlib import Path
from typing import Iterable

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from dcore.pack.keys import b64, derive_key, unb64
from dcore.pack.semantic import semantic_obfuscate_sources

FORMAT_VERSION = 2


def collect_sources(inputs: Iterable[Path]) -> list[tuple[str, bytes]]:
    files: list[tuple[str, bytes]] = []
    for item in inputs:
        if item.is_dir():
            for path in sorted(item.rglob("*.dsc")):
                files.append((path.relative_to(item).as_posix(), path.read_bytes()))
        elif item.is_file() and item.suffix.lower() == ".dsc":
            files.append((item.name, item.read_bytes()))
        else:
            raise ValueError(f"input is not a .dsc file or directory: {item}")
    if not files:
        raise ValueError("no .dsc files selected")
    names = [name for name, _ in files]
    if len(names) != len(set(names)):
        raise ValueError("duplicate relative file names; select a directory or rename inputs")
    return files


def build_release(
    inputs: list[Path], output: Path, master: bytes, project_id: str, mode: str = "hard"
) -> None:
    sources = collect_sources(inputs)
    all_names, definition_maps, obfuscated = semantic_obfuscate_sources(sources, master, mode)

    original_zip = io.BytesIO()
    with zipfile.ZipFile(original_zip, "w", zipfile.ZIP_STORED) as archive:
        for relative, raw in sources:
            archive.writestr(relative, raw)

    manifest = {
        "format": FORMAT_VERSION,
        "project_id": project_id,
        "mode": mode,
        "sources": [{"source": relative, "sha256": hashlib.sha256(raw).hexdigest()} for relative, raw in sources],
        "files": [{"source": source, "output": output_name, "sha256": hashlib.sha256(data).hexdigest()} for output_name, data, source in obfuscated],
        "containers": all_names,
        "definitions": definition_maps,
    }
    manifest_bytes = json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
    salt = secrets.token_bytes(16)
    release_key = derive_key(master, salt, project_id)
    source_nonce = secrets.token_bytes(12)
    manifest_nonce = secrets.token_bytes(12)
    encrypted_source = AESGCM(release_key).encrypt(source_nonce, original_zip.getvalue(), f"source:{project_id}".encode())
    encrypted_manifest = AESGCM(release_key).encrypt(manifest_nonce, manifest_bytes, f"manifest:{project_id}".encode())

    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as release:
        release.writestr("meta.json", json.dumps({
            "format": FORMAT_VERSION,
            "project_id": project_id,
            "salt": b64(salt),
            "source_nonce": b64(source_nonce),
            "manifest_nonce": b64(manifest_nonce),
        }, sort_keys=True, indent=2))
        release.writestr("encrypted/source.bin", encrypted_source)
        release.writestr("encrypted/manifest.bin", encrypted_manifest)
        for output_name, data, _ in obfuscated:
            release.writestr(output_name, data)
    print(f"built {output} ({len(obfuscated)} executable files, {len(sources)} original files)")


def decrypt_release(release_path: Path, master: bytes) -> tuple[zipfile.ZipFile, dict, bytes]:
    """Read and authenticate the encrypted release payloads.

    The returned ZipFile is backed by an in-memory buffer and must be closed
    by the caller. Keeping this in one helper makes verify and restore use the
    same authentication path.
    """
    with zipfile.ZipFile(release_path, "r") as release:
        meta = json.loads(release.read("meta.json"))
        project_id = meta["project_id"]
        release_key = derive_key(master, unb64(meta["salt"]), project_id)
        original_zip = AESGCM(release_key).decrypt(
            unb64(meta["source_nonce"]), release.read("encrypted/source.bin"), f"source:{project_id}".encode()
        )
        manifest_bytes = AESGCM(release_key).decrypt(
            unb64(meta["manifest_nonce"]), release.read("encrypted/manifest.bin"), f"manifest:{project_id}".encode()
        )
    return zipfile.ZipFile(io.BytesIO(original_zip), "r"), json.loads(manifest_bytes), original_zip


def verify_release(release_path: Path, master: bytes) -> None:
    with zipfile.ZipFile(release_path, "r") as release:
        executable_names = {name for name in release.namelist() if name.endswith(".dsc")}
        source_archive, manifest, _ = decrypt_release(release_path, master)
        try:
            expected_outputs = {entry["output"]: entry["sha256"] for entry in manifest["files"]}
            if executable_names != set(expected_outputs):
                raise ValueError("release executable file list does not match its manifest")
            for name, expected_hash in expected_outputs.items():
                actual_hash = hashlib.sha256(release.read(name)).hexdigest()
                if actual_hash != expected_hash:
                    raise ValueError(f"executable checksum mismatch: {name}")
            expected_sources = {entry["source"]: entry["sha256"] for entry in manifest["sources"]}
            if set(source_archive.namelist()) != set(expected_sources):
                raise ValueError("encrypted source file list does not match its manifest")
            for name, expected_hash in expected_sources.items():
                actual_hash = hashlib.sha256(source_archive.read(name)).hexdigest()
                if actual_hash != expected_hash:
                    raise ValueError(f"source checksum mismatch: {name}")
        finally:
            source_archive.close()
    print(f"verified {release_path} ({len(expected_outputs)} executable files, {len(expected_sources)} original files)")


def restore_release(release_path: Path, output: Path, master: bytes) -> None:
    source_archive, _, _ = decrypt_release(release_path, master)
    output.mkdir(parents=True, exist_ok=True)
    try:
        for name in source_archive.namelist():
            destination = output / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source_archive.read(name))
    finally:
        source_archive.close()
    print(f"restored {release_path} to {output}")


__all__ = [
    "FORMAT_VERSION",
    "build_release",
    "collect_sources",
    "decrypt_release",
    "restore_release",
    "verify_release",
]
