"""Read-only material an agent should load before answering.

The Skill product carried its policy in SKILL.md, which only one client could
read. The same policy is now a resource, so Claude Code, Cursor, Codex, Zed and
anything else speaking MCP receive the identical contract instead of each vendor
re-deriving it from a README.

Resources are files on disk rather than embedded strings: the release manifest
already hashes them, so what an agent reads is exactly what the verify gate
signed off.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dcore.paths import KNOWLEDGE_DIRECTORY, REPOSITORY_ROOT


@dataclass(frozen=True)
class Resource:
    uri: str
    name: str
    description: str
    path: Path
    mime_type: str = "text/markdown"

    def descriptor(self) -> dict[str, Any]:
        return {
            "uri": self.uri,
            "name": self.name,
            "description": self.description,
            "mimeType": self.mime_type,
        }


RESOURCES: tuple[Resource, ...] = (
    Resource(
        uri="dcore://instructions",
        name="dCore agent instructions",
        description=(
            "The mandatory operating contract: local-evidence gate, target resolution, execution gate, "
            "Reflect boundaries, clean production rules and delivery format. Read this first."
        ),
        path=KNOWLEDGE_DIRECTORY / "AGENT_INSTRUCTIONS.md",
    ),
    Resource(
        uri="dcore://architecture",
        name="dCore architecture",
        description="Trust flow, sources of truth, request pipeline and the clean-code boundary.",
        path=REPOSITORY_ROOT / "docs" / "ARCHITECTURE.md",
    ),
    Resource(
        uri="dcore://operations",
        name="dCore operations",
        description="Release boundaries, maintenance flow and what counts as proof.",
        path=REPOSITORY_ROOT / "docs" / "OPERATIONS.md",
    ),
    Resource(
        uri="dcore://manifest",
        name="dCore release manifest",
        description=(
            "The verified release identity: version, database digest, artifact hashes and validation state. "
            "Use it to report which dCore build produced an answer."
        ),
        path=KNOWLEDGE_DIRECTORY / "manifest.json",
        mime_type="application/json",
    ),
    Resource(
        uri="dcore://lint-contract-example",
        name="Lint contract example",
        description="A worked behaviour-witness manifest showing every required design field.",
        path=KNOWLEDGE_DIRECTORY / "lint_contract.example.json",
        mime_type="application/json",
    ),
)

BY_URI = {resource.uri: resource for resource in RESOURCES}


def descriptors() -> list[dict[str, Any]]:
    """List only resources that actually exist, so a bundle cannot advertise a gap."""
    return [resource.descriptor() for resource in RESOURCES if resource.path.is_file()]


def read(uri: str) -> dict[str, Any]:
    resource = BY_URI.get(uri)
    if resource is None:
        raise KeyError(uri)
    if not resource.path.is_file():
        raise FileNotFoundError(resource.path)
    text = resource.path.read_text(encoding="utf-8")
    if resource.mime_type == "application/json":
        # Reformat so a truncated or minified artifact still reads cleanly.
        text = json.dumps(json.loads(text), ensure_ascii=False, indent=2)
    return {
        "contents": [
            {"uri": resource.uri, "mimeType": resource.mime_type, "text": text}
        ]
    }
