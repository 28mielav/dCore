"""Pre/post semantic proof for Pool 4 Denizen transformations."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Iterable, Mapping

try:
    from dcore.semantics.graph import DenizenGraph, build_denizen_graph
    from dcore.semantics.ir import DenizenFileIR, DenizenProjectIR, SectionNode, build_project_ir
    from dcore.semantics.surface import SurfaceMap, classify_surface
    from dcore.semantics.transform import (
        CONTAINER_TAG,
        DEFINITION_ARGUMENT,
        DEFINITION_TAG,
        DEFINE_COMMAND,
        LOOP_ALIAS,
        RenameEntry,
        _Edit,
        _add_edit,
        _add_exact_edit,
        _apply_edits,
        _section_for_line,
    )
except ImportError:  # direct execution from a bundled tools directory
    from dcore.semantics.graph import DenizenGraph, build_denizen_graph
    from dcore.semantics.ir import DenizenFileIR, DenizenProjectIR, SectionNode, build_project_ir
    from dcore.semantics.surface import SurfaceMap, classify_surface
    from dcore.semantics.transform import (
        CONTAINER_TAG,
        DEFINITION_ARGUMENT,
        DEFINITION_TAG,
        DEFINE_COMMAND,
        LOOP_ALIAS,
        RenameEntry,
        _Edit,
        _add_edit,
        _add_exact_edit,
        _apply_edits,
        _section_for_line,
    )


@dataclass(frozen=True)
class ProofIssue:
    code: str
    detail: str


@dataclass(frozen=True)
class SemanticProof:
    passed: bool
    issues: tuple[ProofIssue, ...]
    pre_signature: str
    post_signature: str

    def require(self) -> "SemanticProof":
        if not self.passed:
            detail = "; ".join(f"{issue.code}: {issue.detail}" for issue in self.issues)
            raise ValueError(f"semantic proof failed: {detail}")
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "issues": [{"code": issue.code, "detail": issue.detail} for issue in self.issues],
            "pre_signature": self.pre_signature,
            "post_signature": self.post_signature,
        }


def _reverse_maps(renames: Iterable[RenameEntry]) -> tuple[dict[str, str], dict[str, str], dict[tuple[str, str], str], dict[str, str]]:
    container_names: dict[str, str] = {}
    pre_scope_to_post: dict[str, str] = {}
    post_scope_to_pre: dict[str, str] = {}
    definition_names: dict[tuple[str, str], str] = {}
    for entry in renames:
        if entry.kind == "container":
            container_names[entry.replacement.casefold()] = entry.original
            pre_scope_to_post[entry.scope] = f"{entry.scope.rsplit('::', 1)[0]}::{entry.replacement}"
            post_scope_to_pre[f"{entry.scope.rsplit('::', 1)[0]}::{entry.replacement}"] = entry.scope
        elif entry.kind == "definition":
            post_scope = pre_scope_to_post.get(entry.scope, entry.scope)
            definition_names[(post_scope, entry.replacement.casefold())] = entry.original
    return container_names, pre_scope_to_post, definition_names, post_scope_to_pre


def _pre_uid_for_post(uid: str, post_scope_to_pre: Mapping[str, str]) -> str:
    return post_scope_to_pre.get(uid, uid)


def _normalize_argument(value: str, scope: str, container_names: Mapping[str, str], definition_names: Mapping[tuple[str, str], str]) -> str:
    result = value

    def container_tag(match: Any) -> str:
        name = match.group("name")
        return match.group(0).replace(name, container_names.get(name.casefold(), name), 1)

    result = CONTAINER_TAG.sub(container_tag, result)
    if result.strip():
        parts = result.split(None, 1)
        if parts and parts[0].casefold() in {name.casefold() for name in container_names}:
            parts[0] = container_names[parts[0].casefold()]
            result = " ".join(parts)

    def definition_tag(match: Any) -> str:
        name = match.group("name")
        root = name.split(".", 1)[0]
        replacement = definition_names.get((scope, root.casefold()))
        if replacement is None:
            return match.group(0)
        return match.group(0).replace(name, replacement + name[len(root):], 1)

    result = DEFINITION_TAG.sub(definition_tag, result)

    def definition_argument(match: Any) -> str:
        name = match.group("name")
        root = name.split(".", 1)[0]
        replacement = definition_names.get((scope, root.casefold()))
        return match.group(0).replace(name, replacement + name[len(root):], 1) if replacement else match.group(0)

    result = DEFINITION_ARGUMENT.sub(definition_argument, result)
    if result.strip():
        parts = result.split(None, 1)
        if parts and parts[0].split(".", 1)[0].casefold() in {key[1] for key in definition_names if key[0] == scope}:
            root = parts[0].split(".", 1)[0]
            replacement = definition_names.get((scope, root.casefold()))
            if replacement:
                parts[0] = replacement + parts[0][len(root):]
                result = " ".join(parts)
    result = LOOP_ALIAS.sub(
        lambda match: match.group(0).replace(
            match.group("name"),
            definition_names.get((scope, match.group("name").casefold()), match.group("name")),
            1,
        ),
        result,
    )
    return result


def _canonical_text(file_ir: DenizenFileIR, container_names: Mapping[str, str], definition_names: Mapping[tuple[str, str], str]) -> str:
    edits: list[_Edit] = []
    for section in file_ir.containers:
        original = container_names.get(section.name.casefold())
        if original is not None:
            _add_exact_edit(edits, file_ir.text, section.source.start, section.name, original, f"proof-container:{section.name}")

    for symbol in file_ir.symbols:
        if symbol.kind != "definition" or file_ir.text[symbol.source.start:symbol.source.end] != symbol.name:
            continue
        section = _section_for_line(file_ir, symbol.line)
        if section is None:
            continue
        scope = f"{file_ir.path}::{section.name}"
        original = definition_names.get((scope, symbol.name.casefold()))
        if original is not None:
            _add_exact_edit(edits, file_ir.text, symbol.source.start, symbol.name, original, f"proof-definition:{scope}:{symbol.name}")

    for command in file_ir.commands:
        section = _section_for_line(file_ir, command.line)
        scope = f"{file_ir.path}::{section.name}" if section else ""
        definition_map = {name: original for (candidate_scope, name), original in definition_names.items() if candidate_scope == scope}
        arguments = command.arguments
        argument_start = command.argument_span.start
        if command.name in {"run", "inject", "runlater"}:
            parts = arguments.split(None, 1)
            if parts:
                original = container_names.get(parts[0].casefold())
                if original:
                    start = argument_start + arguments.find(parts[0])
                    _add_exact_edit(edits, file_ir.text, start, parts[0], original, f"proof-call:{parts[0]}")
        for match in CONTAINER_TAG.finditer(arguments):
            original = container_names.get(match.group("name").casefold())
            if original:
                start = argument_start + match.start("name")
                _add_exact_edit(edits, file_ir.text, start, match.group("name"), original, f"proof-tag:{match.group('name')}")
        if command.name in {"define", "definemap"}:
            match = DEFINE_COMMAND.match(arguments)
            if match:
                name = match.group("name")
                root = name.split(".", 1)[0]
                original = definition_map.get(root.casefold())
                if original:
                    start = argument_start + match.start("name")
                    _add_edit(edits, file_ir.text, start, start + len(name), original + name[len(root):], f"proof-define:{name}")
        for match in DEFINITION_TAG.finditer(arguments):
            name = match.group("name")
            root = name.split(".", 1)[0]
            original = definition_map.get(root.casefold())
            if original:
                start = argument_start + match.start("name")
                _add_edit(edits, file_ir.text, start, start + len(name), original + name[len(root):], f"proof-definition-tag:{name}")
        for match in DEFINITION_ARGUMENT.finditer(arguments):
            name = match.group("name")
            root = name.split(".", 1)[0]
            original = definition_map.get(root.casefold())
            if original:
                start = argument_start + match.start("name")
                _add_edit(edits, file_ir.text, start, start + len(name), original + name[len(root):], f"proof-definition-argument:{name}")
        for match in LOOP_ALIAS.finditer(arguments):
            original = definition_map.get(match.group("name").casefold())
            if original:
                start = argument_start + match.start("name")
                _add_exact_edit(edits, file_ir.text, start, match.group("name"), original, f"proof-loop:{match.group('name')}")
    return _apply_edits(file_ir.text, edits)


def _section_signature(project: DenizenProjectIR, container_names: Mapping[str, str]) -> list[tuple[Any, ...]]:
    result: list[tuple[Any, ...]] = []
    for path, file_ir in sorted(project.files.items()):
        for section in file_ir.sections:
            name = container_names.get(section.name.casefold(), section.name)
            result.append((path, name, section.end_line, section.container_type, section.is_container))
    return result


def _graph_signature(graph: DenizenGraph, container_names: Mapping[str, str], post_scope_to_pre: Mapping[str, str], definition_names: Mapping[tuple[str, str], str], post: bool) -> dict[str, Any]:
    def scope(uid: str) -> str:
        return _pre_uid_for_post(uid, post_scope_to_pre) if post else uid

    def container_name(name: str) -> str:
        return container_names.get(name.casefold(), name) if post else name

    def definition(scope_uid: str, name: str) -> str:
        if not post:
            return name
        return definition_names.get((scope_uid, name.casefold()), name)

    containers = sorted([
        (scope(uid), container_name(record.name), record.container_type, record.source.line)
        for uid, record in sorted(graph.containers.items())
    ])
    calls = sorted([
        (scope(edge.source), edge.kind, container_name(edge.target_name), scope(edge.target) if edge.target else None, edge.status, edge.line, edge.dynamic)
        for edge in sorted(graph.calls, key=lambda item: (item.source, item.line, item.kind, item.target_name))
    ])
    definitions = sorted([
        (scope_uid if not post else scope(scope_uid), definition(scope_uid, name), tuple(binding.declarations), tuple(binding.uses), tuple(binding.call_argument_uses), binding.status)
        for (scope_uid, name), binding in sorted(graph.definitions.items())
    ])
    state = sorted([
        (access.storage, access.root, access.access, scope(access.container), access.line, access.persistent, _normalize_argument(access.expression, access.container, container_names, definition_names) if post else access.expression)
        for access in sorted(graph.state, key=lambda item: (item.storage, item.root, item.container, item.line, item.access))
    ])
    return {"containers": containers, "calls": calls, "definitions": definitions, "state": state}


def _surface_signature(surface: SurfaceMap, container_names: Mapping[str, str], post_scope_to_pre: Mapping[str, str], definition_names: Mapping[tuple[str, str], str], post: bool) -> list[tuple[Any, ...]]:
    result: list[tuple[Any, ...]] = []
    for item in surface.decisions:
        identifier = item.identifier
        scope = item.scope
        if post and item.kind == "container":
            identifier = _pre_uid_for_post(identifier, post_scope_to_pre)
            scope = container_names.get(scope.casefold(), scope)
        elif post and item.kind == "definition":
            raw_scope, raw_name = identifier.rsplit("::", 1)
            pre_scope = _pre_uid_for_post(raw_scope, post_scope_to_pre)
            identifier = f"{pre_scope}::{definition_names.get((raw_scope, raw_name.casefold()), raw_name)}"
            scope = pre_scope
        elif post and item.kind == "reference":
            for replacement, original in container_names.items():
                if identifier.endswith(f"::{replacement}") or identifier.endswith(f"::{replacement.casefold()}"):
                    identifier = identifier.rsplit("::", 1)[0] + "::" + original
        result.append((identifier, item.kind, scope, item.classification, item.confidence, tuple(item.reasons), tuple(item.lines)))
    return sorted(result)


def prove_transformation(
    original: DenizenProjectIR,
    transformed_files: Mapping[str, str],
    renames: Iterable[RenameEntry],
    *,
    pre_graph: DenizenGraph | None = None,
    pre_surface: SurfaceMap | None = None,
) -> SemanticProof:
    """Reparse and prove that a transformed project is semantically equivalent."""
    entries = tuple(renames)
    container_names, _, definition_names, post_scope_to_pre = _reverse_maps(entries)
    issues: list[ProofIssue] = []
    pre_graph = pre_graph or build_denizen_graph(original)
    pre_surface = pre_surface or classify_surface(pre_graph)
    post_project = build_project_ir(transformed_files)
    if set(original.files) != set(post_project.files):
        issues.append(ProofIssue("file_set_changed", "transformation changed the project file set"))

    for path in sorted(set(original.files) & set(post_project.files)):
        try:
            canonical = _canonical_text(post_project.files[path], container_names, definition_names)
        except (ValueError, IndexError) as error:
            issues.append(ProofIssue("canonicalization_failed", f"{path}: {error}"))
            continue
        if canonical != original.files[path].text:
            issues.append(ProofIssue("source_not_equivalent", path))

    post_graph = build_denizen_graph(post_project)
    post_surface = classify_surface(post_graph)
    if post_surface.hard_blocked:
        issues.append(ProofIssue("post_unknown_surface", f"{len(post_surface.unknown)} unknown decisions after transform"))
    if _section_signature(original, {}) != _section_signature(post_project, container_names):
        issues.append(ProofIssue("section_structure_changed", "top-level section names/types/line ranges changed"))
    pre_signature_data = {
        "graph": _graph_signature(pre_graph, {}, {}, {}, False),
        "surface": _surface_signature(pre_surface, {}, {}, {}, False),
        "sections": _section_signature(original, {}),
    }
    post_signature_data = {
        "graph": _graph_signature(post_graph, container_names, post_scope_to_pre, definition_names, True),
        "surface": _surface_signature(post_surface, container_names, post_scope_to_pre, definition_names, True),
        "sections": _section_signature(post_project, container_names),
    }
    pre_signature = json.dumps(pre_signature_data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    post_signature = json.dumps(post_signature_data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if pre_signature != post_signature:
        issues.append(ProofIssue("semantic_signature_changed", "canonical IR/graph/surface signature differs"))
    return SemanticProof(not issues, tuple(issues), pre_signature, post_signature)


__all__ = ["ProofIssue", "SemanticProof", "prove_transformation"]
