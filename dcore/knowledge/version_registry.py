"""Discover and catalogue Denizen-family version artifacts.

The registry stores source/tag identity separately from Meta and runtime proof.
Discovering a tag proves only that a source revision exists.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3


DEFAULT_SOURCES = {
    "denizen": ("Denizen", "https://github.com/DenizenScript/Denizen.git"),
    "denizen-core": ("Denizen-Core", "https://github.com/DenizenScript/Denizen-Core.git"),
    "denizenm": ("DenizenM", "https://github.com/Energobro/DenizenM-Tjtoxshpilivili1.git"),
}


def normalize_product_version(product: str, version: str | None) -> str | None:
    """Normalize common build-label decoration without changing identity.

    DenizenM jars are often named with a leading ``b`` (for example
    ``b7299M``), while the registry stores the underlying build as
    ``7299M``.  Only remove that decoration for the exact DenizenM build
    shape; unknown labels must remain unknown rather than being guessed.
    """
    if version is None or product.casefold() != "denizenm":
        return version
    match = re.fullmatch(r"b(?P<build>\d{4}m\d*)", version, re.IGNORECASE)
    return match.group("build") if match else version


@dataclass(frozen=True)
class VersionArtifact:
    artifact_id: str
    product: str
    version: str
    repository: str
    tag: str
    commit_sha: str
    channel: str
    source_kind: str
    status: str = "catalogued"
    meta_status: str = "not_indexed"
    runtime_status: str = "unverified"
    discovered_at: str = ""


def _git_refs(repository: str, ref_type: str) -> list[tuple[str, str]]:
    output = subprocess.check_output(
        ["git", "ls-remote", f"--{ref_type}", "--refs", repository],
        text=True,
        stderr=subprocess.STDOUT,
        timeout=90,
    )
    rows: list[tuple[str, str]] = []
    for line in output.splitlines():
        commit, ref = line.split("\t", 1)
        prefix = f"refs/{ref_type}/"
        if ref.startswith(prefix):
            rows.append((ref[len(prefix):], commit))
    return rows


def _git_tags(repository: str) -> list[tuple[str, str, str]]:
    refs: list[tuple[str, str, str]] = []
    for tag, commit in _git_refs(repository, "tags"):
        refs.append((tag, commit, "tag"))
    for branch, commit in _git_refs(repository, "heads"):
        refs.append((branch, commit, "branch"))
    return refs


def discover(sources: dict[str, tuple[str, str]] = DEFAULT_SOURCES) -> list[VersionArtifact]:
    now = datetime.now(timezone.utc).isoformat()
    artifacts: list[VersionArtifact] = []
    for source_kind, (product, repository) in sources.items():
        for tag, commit, channel in _git_tags(repository):
            artifact_id = f"{source_kind}:{channel}:{tag}".lower()
            artifacts.append(VersionArtifact(
                artifact_id=artifact_id,
                product=product,
                version=tag,
                repository=repository.removesuffix(".git"),
                tag=tag,
                commit_sha=commit,
                channel=channel,
                source_kind=source_kind,
                discovered_at=now,
            ))
    return sorted(artifacts, key=lambda item: (item.product.lower(), item.version.lower()))


def discover_local_denizenm_builds(repo: Path) -> list[VersionArtifact]:
    """Find untagged DenizenM build bumps from the local, evidence-backed history."""
    output = subprocess.check_output(
        ["git", "-C", str(repo), "log", "--all", "--format=%H%x00%s"], text=True, timeout=120
    )
    now = datetime.now(timezone.utc).isoformat()
    seen: set[str] = set()
    artifacts: list[VersionArtifact] = []
    for line in output.splitlines():
        commit, separator, subject = line.partition("\x00")
        if not separator or not re.search(r"(?i)\bbump\s+to\b", subject):
            continue
        match = re.search(r"\b(7\d{3})\b", subject)
        if not match:
            continue
        version = match.group(1) + "M"
        if version in seen:
            continue
        seen.add(version)
        artifacts.append(VersionArtifact(
            artifact_id=f"denizenm:commit:{version}".lower(), product="DenizenM", version=version,
            repository="https://github.com/Energobro/DenizenM-Tjtoxshpilivili1",
            tag=commit, commit_sha=commit, channel="commit", source_kind="denizenm",
            discovered_at=now,
        ))
    return sorted(artifacts, key=lambda item: item.version.lower())


def ensure_schema(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS version_artifacts(
          artifact_id TEXT PRIMARY KEY,
          product TEXT NOT NULL,
          version TEXT NOT NULL,
          repository TEXT NOT NULL,
          tag TEXT NOT NULL,
          commit_sha TEXT NOT NULL,
          channel TEXT NOT NULL,
          source_kind TEXT NOT NULL,
          status TEXT NOT NULL,
          meta_status TEXT NOT NULL,
          runtime_status TEXT NOT NULL,
          discovered_at TEXT NOT NULL,
          UNIQUE(product,version,commit_sha)
        );
        CREATE INDEX IF NOT EXISTS idx_version_artifacts_product
          ON version_artifacts(product,version);
        CREATE TABLE IF NOT EXISTS version_edges(
          from_artifact_id TEXT NOT NULL REFERENCES version_artifacts(artifact_id) ON DELETE CASCADE,
          to_artifact_id TEXT NOT NULL REFERENCES version_artifacts(artifact_id) ON DELETE CASCADE,
          relation TEXT NOT NULL,
          PRIMARY KEY(from_artifact_id,to_artifact_id,relation)
        );
        """
    )


def import_catalogue(db_path: Path, artifacts: list[VersionArtifact]) -> int:
    db = sqlite3.connect(db_path)
    try:
        ensure_schema(db)
        existing_versions = {
            (row[0].casefold(), row[1].casefold(), row[2])
            for row in db.execute("SELECT product,version,source_kind FROM version_artifacts")
        }
        canonical = [
            item for item in artifacts
            if (item.product.casefold(), item.version.casefold(), item.source_kind) not in existing_versions
            or item.artifact_id in {row[0] for row in db.execute("SELECT artifact_id FROM version_artifacts")}
        ]
        db.executemany(
            """INSERT INTO version_artifacts(
                artifact_id,product,version,repository,tag,commit_sha,channel,
                source_kind,status,meta_status,runtime_status,discovered_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(artifact_id) DO UPDATE SET
                product=excluded.product, version=excluded.version,
                repository=excluded.repository, tag=excluded.tag,
                commit_sha=excluded.commit_sha, channel=excluded.channel,
                source_kind=excluded.source_kind, discovered_at=excluded.discovered_at
            """,
            [tuple(asdict(item).values()) for item in canonical],
        )
        by_product: dict[str, list[VersionArtifact]] = {}
        for item in canonical:
            by_product.setdefault(item.product, []).append(item)
        for product_items in by_product.values():
            ordered = sorted(product_items, key=lambda item: item.version.lower())
            for previous, current in zip(ordered, ordered[1:]):
                db.execute(
                    "INSERT OR IGNORE INTO version_edges VALUES(?,?,?)",
                    (previous.artifact_id, current.artifact_id, "successor"),
                )
        if db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='metadata'"
        ).fetchone():
            db.execute("INSERT OR REPLACE INTO metadata VALUES('version.registry','version_artifacts + version_edges')")
            db.execute("INSERT OR REPLACE INTO metadata VALUES('version.registry.status','catalogued source identities; Meta/runtime proof separate')")
        db.commit()
    finally:
        db.close()
    return len(canonical)


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover Denizen, Denizen-Core and DenizenM version artifacts")
    parser.add_argument("--output", type=Path, help="Write discovered catalogue JSON")
    parser.add_argument("--db", type=Path, help="Import catalogue into SQLite")
    parser.add_argument("--catalogue", type=Path, help="Import an existing catalogue JSON instead of discovering")
    parser.add_argument("--local-denizenm-history", type=Path, help="Add untagged DenizenM build bumps from a local Git clone")
    args = parser.parse_args()
    if args.catalogue:
        payload = json.loads(args.catalogue.read_text(encoding="utf-8"))
        artifacts = [VersionArtifact(**item) for item in payload["artifacts"]]
    else:
        artifacts = discover()
    if args.local_denizenm_history:
        artifacts.extend(discover_local_denizenm_builds(args.local_denizenm_history))
        artifacts = sorted({item.artifact_id: item for item in artifacts}.values(), key=lambda item: (item.product.lower(), item.version.lower(), item.channel))
    payload = {"schema": 1, "status": "catalogued", "artifacts": [asdict(item) for item in artifacts]}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.db:
        print(f"imported={import_catalogue(args.db, artifacts)}")
    if not args.output and not args.db:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
