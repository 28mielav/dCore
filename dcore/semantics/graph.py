"""Semantic graphs built from :mod:`denizen_ir`.

The graph is descriptive, not a transformer.  It records what is proven,
what is unresolved, and where state crosses queue/container boundaries.  A
future obfuscator may rename only after consulting this graph.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
import hashlib
import json
import re
from typing import Any

from dcore.semantics.ir import CommandNode, DenizenFileIR, DenizenProjectIR, Reference, SectionNode, SourceSpan, Symbol


DEFINITION_TAG = re.compile(r"<\[(?P<name>[A-Za-z_][A-Za-z0-9_.-]*)(?:[.\]])", re.IGNORECASE)
DEFINITION_ARGUMENT = re.compile(r"\bdef(?:\.|:)(?P<name>[A-Za-z_][A-Za-z0-9_.-]*):", re.IGNORECASE)
SERVER_FLAG_READ = re.compile(r"\bserver\.flag\[(?P<name>[^\]]+)", re.IGNORECASE)
OBJECT_FLAG_READ = re.compile(r"\b(?P<object>player|entity|npc|world)\.(?:has_)?flag\[(?P<name>[^\]]+)", re.IGNORECASE)
FLAG_COMMAND = re.compile(r"^(?P<target>\S+)\s+(?P<name>[^:\s]+)(?::|\s|$)", re.IGNORECASE)


@dataclass(frozen=True)
class ContainerRecord:
    uid: str
    path: str
    name: str
    container_type: str
    source: SourceSpan


@dataclass(frozen=True)
class CallEdge:
    source: str
    kind: str
    target_name: str
    target: str | None
    status: str
    line: int
    dynamic: bool


@dataclass
class DefinitionBinding:
    scope: str
    name: str
    declarations: list[int] = field(default_factory=list)
    uses: list[int] = field(default_factory=list)
    call_argument_uses: list[int] = field(default_factory=list)

    @property
    def status(self) -> str:
        if not self.declarations:
            return "unresolved"
        if not self.uses and not self.call_argument_uses:
            return "unused"
        if min(self.uses + self.call_argument_uses) < min(self.declarations):
            return "used_before_declaration"
        return "resolved"


@dataclass(frozen=True)
class StateAccess:
    storage: str
    root: str
    access: str
    container: str
    line: int
    persistent: bool
    expression: str


@dataclass
class DenizenGraph:
    containers: dict[str, ContainerRecord] = field(default_factory=dict)
    containers_by_name: dict[str, list[str]] = field(default_factory=dict)
    calls: list[CallEdge] = field(default_factory=list)
    definitions: dict[tuple[str, str], DefinitionBinding] = field(default_factory=dict)
    state: list[StateAccess] = field(default_factory=list)
    unresolved_references: list[CallEdge] = field(default_factory=list)
    dynamic_references: list[CallEdge] = field(default_factory=list)

    @property
    def duplicate_container_names(self) -> set[str]:
        return {name for name, entries in self.containers_by_name.items() if len(entries) > 1}

    @property
    def state_roots(self) -> dict[tuple[str, str], list[StateAccess]]:
        result: dict[tuple[str, str], list[StateAccess]] = defaultdict(list)
        for access in self.state:
            result[(access.storage, access.root)].append(access)
        return dict(result)

    @property
    def multi_writer_state(self) -> dict[tuple[str, str], set[str]]:
        result: dict[tuple[str, str], set[str]] = defaultdict(set)
        for key, accesses in self.state_roots.items():
            writers = {access.container for access in accesses if access.access == "write"}
            if len(writers) > 1:
                result[key] = writers
        return dict(result)

    def to_dict(self) -> dict[str, Any]:
        return {
            "containers": {
                uid: {
                    "path": record.path,
                    "name": record.name,
                    "type": record.container_type,
                    "line": record.source.line,
                }
                for uid, record in sorted(self.containers.items())
            },
            "calls": [
                {
                    "source": edge.source,
                    "kind": edge.kind,
                    "target_name": edge.target_name,
                    "target": edge.target,
                    "status": edge.status,
                    "line": edge.line,
                    "dynamic": edge.dynamic,
                }
                for edge in sorted(self.calls, key=lambda item: (item.source, item.line, item.kind, item.target_name))
            ],
            "definitions": {
                f"{scope}:{name}": {
                    "scope": binding.scope,
                    "name": binding.name,
                    "declarations": sorted(binding.declarations),
                    "uses": sorted(binding.uses),
                    "call_argument_uses": sorted(binding.call_argument_uses),
                    "status": binding.status,
                }
                for (scope, name), binding in sorted(self.definitions.items())
            },
            "state": [
                {
                    "storage": access.storage,
                    "root": access.root,
                    "access": access.access,
                    "container": access.container,
                    "line": access.line,
                    "persistent": access.persistent,
                }
                for access in sorted(self.state, key=lambda item: (item.storage, item.root, item.container, item.line, item.access))
            ],
            "unresolved_references": len(self.unresolved_references),
            "dynamic_references": len(self.dynamic_references),
        }

    def fingerprint(self) -> str:
        payload = json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _container_for_line(file_ir: DenizenFileIR, line: int) -> ContainerRecord | None:
    candidates = [
        section for section in file_ir.containers
        if section.source.line <= line <= section.end_line
    ]
    if not candidates:
        return None
    section = min(candidates, key=lambda item: item.source.line)
    return ContainerRecord(
        uid=f"{file_ir.path}::{section.name}",
        path=file_ir.path,
        name=section.name,
        container_type=section.container_type or "unknown",
        source=section.source,
    )


def _binding(graph: DenizenGraph, scope: str, name: str) -> DefinitionBinding:
    key = (scope, name.casefold())
    if key not in graph.definitions:
        graph.definitions[key] = DefinitionBinding(scope, name)
    return graph.definitions[key]


def _state_root(raw: str) -> str:
    clean = raw.strip().strip("<>")
    clean = clean.split(":", 1)[0].split(".", 1)[0].split("[", 1)[0]
    return clean.casefold()


def _state_from_command(command: CommandNode, container: ContainerRecord) -> list[StateAccess]:
    if command.name != "flag":
        return []
    match = FLAG_COMMAND.match(command.arguments)
    if not match:
        return []
    target = match.group("target").strip("<>").casefold()
    storage = target if target in {"server", "player", "entity", "npc", "world"} else "unknown"
    root = _state_root(match.group("name"))
    if not root:
        return []
    return [StateAccess(storage, root, "write", container.uid, command.line, storage == "server", command.arguments)]


def _state_from_expression(command: CommandNode, container: ContainerRecord) -> list[StateAccess]:
    result: list[StateAccess] = []
    expressions = (("server", SERVER_FLAG_READ), ("object", OBJECT_FLAG_READ))
    for storage_kind, pattern in expressions:
        for match in pattern.finditer(command.arguments):
            storage = match.groupdict().get("object") or storage_kind
            root = _state_root(match.group("name"))
            if root:
                result.append(StateAccess(storage.casefold(), root, "read", container.uid, command.line, storage.casefold() == "server", match.group(0)))
    return result


def _record_definitions(graph: DenizenGraph, command: CommandNode, container: ContainerRecord) -> None:
    for name in DEFINITION_TAG.findall(command.arguments):
        _binding(graph, container.uid, name.split(".", 1)[0]).uses.append(command.line)
    for match in DEFINITION_ARGUMENT.finditer(command.arguments):
        _binding(graph, container.uid, match.group("name").split(".", 1)[0]).call_argument_uses.append(command.line)


def build_denizen_graph(project: DenizenProjectIR) -> DenizenGraph:
    graph = DenizenGraph()
    file_containers: dict[str, dict[str, ContainerRecord]] = {}
    for path, file_ir in sorted(project.files.items()):
        by_name: dict[str, ContainerRecord] = {}
        for section in file_ir.containers:
            record = ContainerRecord(
                uid=f"{path}::{section.name}",
                path=path,
                name=section.name,
                container_type=section.container_type or "unknown",
                source=section.source,
            )
            graph.containers[record.uid] = record
            graph.containers_by_name.setdefault(section.name.casefold(), []).append(record.uid)
            by_name[section.name.casefold()] = record
            for symbol in file_ir.symbols:
                if symbol.scope.casefold() == section.name.casefold():
                    # Dotted paths are fields of one queue-local root.  The
                    # root is what Denizen definition tags and declarations
                    # share (state.phase is still the local definition state).
                    binding = _binding(graph, record.uid, symbol.name.split(".", 1)[0])
                    binding.declarations.append(symbol.line)
        file_containers[path] = by_name

    for path, file_ir in sorted(project.files.items()):
        for command in file_ir.commands:
            container = _container_for_line(file_ir, command.line)
            if not container or container.uid not in graph.containers:
                continue
            graph.state.extend(_state_from_command(command, container))
            graph.state.extend(_state_from_expression(command, container))
            _record_definitions(graph, command, container)

        for reference in file_ir.references:
            container = _container_for_line(file_ir, reference.line)
            if not container:
                continue
            targets = graph.containers_by_name.get(reference.value.casefold(), [])
            if reference.dynamic:
                status = "dynamic"
                target = None
            elif len(targets) == 1:
                status = "resolved"
                target = targets[0]
            elif len(targets) > 1:
                status = "ambiguous"
                target = None
            else:
                status = "unresolved"
                target = None
            edge = CallEdge(container.uid, reference.kind, reference.value, target, status, reference.line, reference.dynamic)
            graph.calls.append(edge)
            if status == "unresolved" or status == "ambiguous":
                graph.unresolved_references.append(edge)
            if status == "dynamic":
                graph.dynamic_references.append(edge)

    for binding in graph.definitions.values():
        binding.declarations = sorted(set(binding.declarations))
        binding.uses = sorted(set(binding.uses))
        binding.call_argument_uses = sorted(set(binding.call_argument_uses))
    return graph
