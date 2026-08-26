"""Semantic obfuscation: turn source `.dsc` files into a renamed, whole-file set.

The original dscpack tool started as a regex splitter that cut a file at its
first container and repeated only the preamble, which could silently drop
later non-container sections (a trailing `settings:` block, for instance).
That path was already disabled upstream in favor of this one before the tool
moved here, so it is not carried forward.

This path keeps each source file whole and delegates naming/rewriting to
`dcore.semantics`: `build_project_ir` parses, `build_denizen_graph` links
calls and definitions, `transform_project` applies only proven-safe renames
and raises `UnsafeTransformError` for anything it cannot prove closed
(dynamic run targets, unresolved container references, and so on).
"""

from __future__ import annotations

import re
from typing import Iterable

from dcore.pack.keys import opaque_id
from dcore.semantics.graph import build_denizen_graph
from dcore.semantics.ir import build_project_ir
from dcore.semantics.transform import UnsafeTransformError, transform_project

MODES = ("hard", "balanced", "compat")

_DYNAMIC_CONTAINER_TAG = re.compile(r"<(?:script|proc|item|inventory|assignment|format)\[<")
_DYNAMIC_RUN = re.compile(r"^\s*-\s*~?(?:run|inject|runlater)\s+<")
_DYNAMIC_DEFMAP = re.compile(r"^\s*-\s*~?(?:run|inject|runlater)\b.*\bdefmap:")


def validate_static_references(relative: str, text: str) -> None:
    """Reject references that cannot be rewritten without evaluating Denizen.

    HARD/BALANCED mode must fail closed: a dynamic task/procedure name or a
    dynamic definition map would otherwise produce a release that loads but
    silently calls the old name at runtime.
    """
    for line_number, line in enumerate(text.splitlines(), 1):
        if _DYNAMIC_CONTAINER_TAG.search(line):
            raise ValueError(f"unsupported dynamic container reference at {relative}:{line_number}")
        if _DYNAMIC_RUN.search(line):
            raise ValueError(f"unsupported dynamic run target at {relative}:{line_number}")
        if _DYNAMIC_DEFMAP.search(line):
            raise ValueError(f"unsupported dynamic defmap argument at {relative}:{line_number}")


def semantic_name_factory(master: bytes, graph, mode: str):
    """Create dcore.pack names without exposing its naming policy to the parser."""
    def factory(kind: str, identifier: str) -> str:
        if kind == "container":
            record = graph.containers[identifier]
            if mode in {"balanced", "compat"}:
                return record.name
            return f"s_{opaque_id(master, 'container', record.uid, 10)}"
        if mode == "compat":
            return identifier.rsplit("\0", 1)[-1]
        return f"d_{opaque_id(master, 'definition', identifier, 8)}"
    return factory


def semantic_obfuscate_sources(
    sources: list[tuple[str, bytes]], master: bytes, mode: str
) -> tuple[dict[str, str], dict[str, dict[str, str]], list[tuple[str, bytes, str]]]:
    """Transform the complete project in place and return one file per source."""
    if mode not in MODES:
        raise ValueError(f"unsupported dcore.pack mode: {mode}")
    for relative, raw in sources:
        validate_static_references(relative, raw.decode("utf-8-sig"))
    if mode == "compat":
        outputs = {relative: raw.decode("utf-8-sig") for relative, raw in sources}
        return ({}, {}, [
            (f"p_{opaque_id(master, 'path', relative, 6)}/f_{opaque_id(master, 'file', relative)}.dsc", text.encode("utf-8"), relative)
            for relative, text in sorted(outputs.items())
        ])

    project = build_project_ir({relative: raw.decode("utf-8-sig") for relative, raw in sources})
    graph = build_denizen_graph(project)
    transformed = transform_project(
        project,
        name_factory=semantic_name_factory(master, graph, mode),
    )

    containers = {
        entry.original: entry.replacement
        for entry in transformed.renames
        if entry.kind == "container"
    }
    definitions: dict[str, dict[str, str]] = {}
    for entry in transformed.renames:
        if entry.kind == "definition":
            definitions.setdefault(entry.scope, {})[entry.original] = entry.replacement
    outputs = [
        (f"p_{opaque_id(master, 'path', relative, 6)}/f_{opaque_id(master, 'file', relative)}.dsc", transformed.files[relative].encode("utf-8"), relative)
        for relative, _ in sorted(sources)
    ]
    return containers, definitions, outputs


__all__ = [
    "MODES",
    "UnsafeTransformError",
    "semantic_name_factory",
    "semantic_obfuscate_sources",
    "validate_static_references",
]
