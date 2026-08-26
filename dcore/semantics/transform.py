"""Fail-closed source transformation for Denizen projects.

Pool 4 deliberately performs only semantic, span-based rewrites.  It does
not split container files, does not rewrite arbitrary words, and never turns
an unknown surface into an assumption.  Pool 5 will add a stronger pre/post
semantic equivalence proof around this transformer.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from typing import Callable, Mapping

from dcore.semantics.graph import DenizenGraph, build_denizen_graph
from dcore.semantics.ir import CommandNode, DenizenFileIR, DenizenProjectIR, SectionNode, Symbol
from dcore.semantics.surface import SurfaceMap, classify_surface


DEFINITION_TAG = re.compile(r"<\[(?P<name>[A-Za-z_][A-Za-z0-9_.-]*)(?=[.\]])", re.IGNORECASE)
DEFINITION_ARGUMENT = re.compile(
    r"(?<![A-Za-z0-9_.-])def(?:\.|:)(?P<name>[A-Za-z_][A-Za-z0-9_.-]*):",
    re.IGNORECASE,
)
DEFINE_COMMAND = re.compile(
    r"^(?P<prefix>\s*)(?P<name>[A-Za-z_][A-Za-z0-9_.-]*)(?=[:\s]|$)",
)
LOOP_ALIAS = re.compile(
    r"\b(?P<key>as|key):(?P<name>[A-Za-z_][A-Za-z0-9_-]*)",
    re.IGNORECASE,
)
CONTAINER_TAG = re.compile(
    r"<(?P<kind>script|proc)\[(?P<name>[^\]<>]+)\](?:[^<>]*)>",
    re.IGNORECASE,
)
STATIC_CONTAINER_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")


class UnsafeTransformError(ValueError):
    """Raised when a project is not proven safe for semantic rewriting."""

    def __init__(self, message: str, surface: SurfaceMap | None = None) -> None:
        super().__init__(message)
        self.surface = surface


@dataclass(frozen=True)
class RenameEntry:
    kind: str
    scope: str
    original: str
    replacement: str


@dataclass(frozen=True)
class TransformResult:
    files: dict[str, str]
    renames: tuple[RenameEntry, ...]
    edit_count: int
    proof: object | None = None

    def rename_map(self) -> dict[str, str]:
        return {entry.original: entry.replacement for entry in self.renames}


@dataclass(frozen=True)
class _Edit:
    start: int
    end: int
    replacement: str
    reason: str


NameFactory = Callable[[str, str], str]


def deterministic_name(kind: str, identifier: str, salt: bytes = b"dcore-pool4") -> str:
    """Return a stable Denizen-safe name for a semantic identifier."""
    digest = hashlib.sha256(salt + b"\0" + kind.encode() + b"\0" + identifier.encode()).hexdigest()[:12]
    return ("s_" if kind == "container" else "d_") + digest


def _owner_uid(path: str, section: SectionNode) -> str:
    return f"{path}::{section.name}"


def _section_for_line(file_ir: DenizenFileIR, line: int) -> SectionNode | None:
    candidates = [
        section for section in file_ir.containers
        if section.source.line <= line <= section.end_line
    ]
    return min(candidates, key=lambda item: item.source.line) if candidates else None


def _container_renames(graph: DenizenGraph, surface: SurfaceMap, factory: NameFactory) -> dict[str, str]:
    result: dict[str, str] = {}
    for decision in surface.internal:
        if decision.kind != "container":
            continue
        record = graph.containers.get(decision.identifier)
        if record is None:
            raise UnsafeTransformError(f"surface references missing container: {decision.identifier}", surface)
        replacement = factory("container", record.uid)
        # A policy such as dscpack's ``balanced`` mode may deliberately keep
        # an internal container name.  Identity is not a collision and must
        # not be treated as an unsafe generated alias.
        if replacement.casefold() != record.name.casefold():
            result[record.name.casefold()] = replacement
    return result


def _definition_renames(graph: DenizenGraph, surface: SurfaceMap, factory: NameFactory) -> dict[tuple[str, str], str]:
    result: dict[tuple[str, str], str] = {}
    for (scope, name), binding in graph.definitions.items():
        decision = surface.decision(f"{scope}::{name}", "definition")
        if decision is None:
            raise UnsafeTransformError(f"definition has no surface decision: {scope}::{name}", surface)
        if decision.classification != "internal":
            continue
        result[(scope, name.casefold())] = factory("definition", f"{scope}\0{name.casefold()}")
    return result


def _assert_names_are_safe(project: DenizenProjectIR, renames: Mapping[str, str], definition_renames: Mapping[tuple[str, str], str]) -> None:
    occupied: set[str] = set()
    for entries in project.containers.values():
        occupied.update(section.name.casefold() for _, section in entries)
    for file_ir in project.files.values():
        for symbol in file_ir.symbols:
            occupied.add(symbol.name.casefold())

    replacements: set[str] = set()
    for replacement in (*renames.values(), *definition_renames.values()):
        lowered = replacement.casefold()
        if not STATIC_CONTAINER_NAME.fullmatch(replacement):
            raise UnsafeTransformError(f"generated name is not Denizen-safe: {replacement}")
        if lowered in occupied:
            raise UnsafeTransformError(f"generated name collides with source symbol: {replacement}")
        if lowered in replacements:
            raise UnsafeTransformError(f"generated names collide: {replacement}")
        replacements.add(lowered)


def _add_edit(edits: list[_Edit], text: str, start: int, end: int, replacement: str, reason: str) -> None:
    if start < 0 or end < start or end > len(text):
        raise UnsafeTransformError(f"invalid rewrite span for {reason}: {start}:{end}")
    if text[start:end] == replacement:
        return
    edits.append(_Edit(start, end, replacement, reason))


def _add_exact_edit(edits: list[_Edit], text: str, start: int, original: str, replacement: str, reason: str) -> None:
    if text[start:start + len(original)] != original:
        raise UnsafeTransformError(f"source changed under IR span for {reason}")
    _add_edit(edits, text, start, start + len(original), replacement, reason)


def _add_container_header_edits(file_ir: DenizenFileIR, graph: DenizenGraph, container_renames: Mapping[str, str], edits: list[_Edit]) -> None:
    for section in file_ir.containers:
        replacement = container_renames.get(section.name.casefold())
        if replacement is None:
            continue
        _add_exact_edit(edits, file_ir.text, section.source.start, section.name, replacement, f"container:{section.name}")


def _add_header_definition_edits(file_ir: DenizenFileIR, graph: DenizenGraph, definition_renames: Mapping[tuple[str, str], str], edits: list[_Edit]) -> None:
    for symbol in file_ir.symbols:
        if symbol.kind != "definition":
            continue
        if file_ir.text[symbol.source.start:symbol.source.end] != symbol.name:
            continue
        section = _section_for_line(file_ir, symbol.line)
        if section is None:
            raise UnsafeTransformError(f"definition outside container at {file_ir.path}:{symbol.line}")
        scope = _owner_uid(file_ir.path, section)
        replacement = definition_renames.get((scope, symbol.name.casefold()))
        if replacement is not None:
            _add_exact_edit(edits, file_ir.text, symbol.source.start, symbol.name, replacement, f"definition-header:{scope}:{symbol.name}")


def _add_command_definition_edits(file_ir: DenizenFileIR, definition_renames: Mapping[tuple[str, str], str], edits: list[_Edit]) -> None:
    for command in file_ir.commands:
        section = _section_for_line(file_ir, command.line)
        if section is None:
            continue
        scope = _owner_uid(file_ir.path, section)
        definition_map = {
            original: replacement
            for (candidate_scope, original), replacement in definition_renames.items()
            if candidate_scope == scope
        }
        if not definition_map:
            continue
        argument_start = command.argument_span.start
        arguments = command.arguments
        if command.name in {"define", "definemap"}:
            match = DEFINE_COMMAND.match(arguments)
            if match:
                original = match.group("name")
                root = original.split(".", 1)[0].casefold()
                replacement = definition_map.get(root)
                if replacement is not None:
                    start = argument_start + match.start("name")
                    suffix = original[len(original.split(".", 1)[0]):]
                    _add_edit(edits, file_ir.text, start, start + len(original), replacement + suffix, f"definition-command:{scope}:{original}")
        if command.name in {"foreach", "repeat", "while"}:
            for match in LOOP_ALIAS.finditer(arguments):
                original = match.group("name")
                replacement = definition_map.get(original.casefold())
                if replacement is not None:
                    start = argument_start + match.start("name")
                    _add_exact_edit(edits, file_ir.text, start, original, replacement, f"loop-alias:{scope}:{original}")

        for match in DEFINITION_TAG.finditer(arguments):
            original = match.group("name")
            root = original.split(".", 1)[0].casefold()
            replacement = definition_map.get(root)
            if replacement is not None:
                start = argument_start + match.start("name")
                suffix = original[len(original.split(".", 1)[0]):]
                _add_edit(edits, file_ir.text, start, start + len(original), replacement + suffix, f"definition-tag:{scope}:{original}")

        for match in DEFINITION_ARGUMENT.finditer(arguments):
            original = match.group("name")
            root = original.split(".", 1)[0].casefold()
            replacement = definition_map.get(root)
            if replacement is not None:
                start = argument_start + match.start("name")
                suffix = original[len(original.split(".", 1)[0]):]
                _add_edit(edits, file_ir.text, start, start + len(original), replacement + suffix, f"definition-argument:{scope}:{original}")


def _add_container_reference_edits(file_ir: DenizenFileIR, container_renames: Mapping[str, str], edits: list[_Edit]) -> None:
    for command in file_ir.commands:
        if command.name in {"run", "inject", "runlater"}:
            match = re.match(r"(?P<prefix>\s*)(?P<target>[^\s]+)", command.arguments)
            if match:
                target = match.group("target")
                if STATIC_CONTAINER_NAME.fullmatch(target):
                    replacement = container_renames.get(target.casefold())
                    if replacement is not None:
                        start = command.argument_span.start + match.start("target")
                        _add_exact_edit(edits, file_ir.text, start, target, replacement, f"container-call:{target}")

        for match in CONTAINER_TAG.finditer(command.arguments):
            target = match.group("name")
            if not STATIC_CONTAINER_NAME.fullmatch(target):
                continue
            replacement = container_renames.get(target.casefold())
            if replacement is not None:
                start = command.argument_span.start + match.start("name")
                _add_exact_edit(edits, file_ir.text, start, target, replacement, f"container-tag:{target}")


def _apply_edits(text: str, edits: list[_Edit]) -> str:
    ordered = sorted(edits, key=lambda item: (item.start, item.end, item.reason))
    previous_end = -1
    for edit in ordered:
        if edit.start < previous_end:
            raise UnsafeTransformError(f"overlapping rewrite spans near {edit.reason}")
        previous_end = edit.end
    for edit in reversed(ordered):
        text = text[:edit.start] + edit.replacement + text[edit.end:]
    return text


def transform_project(
    project: DenizenProjectIR,
    *,
    salt: bytes = b"dcore-pool4",
    name_factory: NameFactory | None = None,
    graph: DenizenGraph | None = None,
    surface: SurfaceMap | None = None,
    verify: bool = True,
) -> TransformResult:
    """Rename only proven internal symbols while preserving source layout.

    ``surface.unknown`` is a hard stop.  A caller may provide a graph/surface
    produced from the same project to make the proof artifact inspectable;
    otherwise both are rebuilt here.
    """
    graph = graph or build_denizen_graph(project)
    surface = surface or classify_surface(graph)
    if surface.hard_blocked:
        unknown = ", ".join(f"{item.kind}:{item.identifier}" for item in surface.unknown[:8])
        raise UnsafeTransformError(f"project surface is not proven safe; unknown={unknown}", surface)

    factory = name_factory or (lambda kind, identifier: deterministic_name(kind, identifier, salt))
    container_renames = _container_renames(graph, surface, factory)
    definition_renames = _definition_renames(graph, surface, factory)
    _assert_names_are_safe(project, container_renames, definition_renames)

    outputs: dict[str, str] = {}
    total_edits = 0
    for path, file_ir in sorted(project.files.items()):
        edits: list[_Edit] = []
        _add_container_header_edits(file_ir, graph, container_renames, edits)
        _add_header_definition_edits(file_ir, graph, definition_renames, edits)
        _add_command_definition_edits(file_ir, definition_renames, edits)
        _add_container_reference_edits(file_ir, container_renames, edits)
        outputs[path] = _apply_edits(file_ir.text, edits)
        total_edits += len(edits)

    renames: list[RenameEntry] = []
    for uid, replacement in sorted((uid, value) for uid, value in ((record.uid, container_renames.get(record.name.casefold())) for record in graph.containers.values()) if value):
        record = graph.containers[uid]
        renames.append(RenameEntry("container", uid, record.name, replacement))
    for (scope, name), replacement in sorted(definition_renames.items()):
        renames.append(RenameEntry("definition", scope, name, replacement))
    rename_tuple = tuple(renames)
    proof: object | None = None
    if verify:
        from dcore.semantics.proof import prove_transformation
        proof = prove_transformation(project, outputs, rename_tuple, pre_graph=graph, pre_surface=surface)
        if not proof.passed:
            detail = "; ".join(f"{issue.code}: {issue.detail}" for issue in proof.issues)
            raise UnsafeTransformError(f"pre/post semantic proof failed: {detail}", surface)
    return TransformResult(outputs, rename_tuple, total_edits, proof)


__all__ = [
    "NameFactory",
    "RenameEntry",
    "TransformResult",
    "UnsafeTransformError",
    "deterministic_name",
    "transform_project",
]
