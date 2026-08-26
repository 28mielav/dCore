"""Public/internal/unknown identifier policy for Denizen obfuscation.

This layer is intentionally conservative.  It does not rename anything; it
only describes what a future transformer is allowed to consider.  ``unknown``
is a hard stop for safe and hard release modes, not an invitation to guess.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from typing import Any

from dcore.semantics.graph import DenizenGraph


PUBLIC_CONTAINER_TYPES = {"item", "command", "world"}
INTERNAL_CONTAINER_TYPES = {"task", "procedure"}


@dataclass(frozen=True)
class SurfaceDecision:
    identifier: str
    kind: str
    scope: str
    classification: str
    confidence: str
    reasons: tuple[str, ...]
    lines: tuple[int, ...] = ()


@dataclass
class SurfaceMap:
    decisions: list[SurfaceDecision] = field(default_factory=list)

    @property
    def public(self) -> list[SurfaceDecision]:
        return [item for item in self.decisions if item.classification == "public"]

    @property
    def internal(self) -> list[SurfaceDecision]:
        return [item for item in self.decisions if item.classification == "internal"]

    @property
    def unknown(self) -> list[SurfaceDecision]:
        return [item for item in self.decisions if item.classification == "unknown"]

    @property
    def renameable(self) -> set[str]:
        return {
            item.identifier for item in self.internal
            if item.kind in {"container", "definition", "loop_alias"}
        }

    @property
    def hard_blocked(self) -> bool:
        return bool(self.unknown)

    def decision(self, identifier: str, kind: str | None = None) -> SurfaceDecision | None:
        for item in self.decisions:
            if item.identifier == identifier and (kind is None or item.kind == kind):
                return item
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": {
                "public": len(self.public),
                "internal": len(self.internal),
                "unknown": len(self.unknown),
                "hard_blocked": self.hard_blocked,
            },
            "decisions": [
                {
                    "identifier": item.identifier,
                    "kind": item.kind,
                    "scope": item.scope,
                    "classification": item.classification,
                    "confidence": item.confidence,
                    "reasons": list(item.reasons),
                    "lines": list(item.lines),
                }
                for item in sorted(self.decisions, key=lambda value: (value.kind, value.identifier, value.scope))
            ],
        }

    def fingerprint(self) -> str:
        payload = json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _decision(identifier: str, kind: str, scope: str, classification: str, confidence: str, *reasons: str, lines: tuple[int, ...] = ()) -> SurfaceDecision:
    return SurfaceDecision(identifier, kind, scope, classification, confidence, tuple(dict.fromkeys(reasons)), lines)


def _container_decisions(graph: DenizenGraph) -> list[SurfaceDecision]:
    decisions: list[SurfaceDecision] = []
    incoming: dict[str, list[Any]] = {uid: [] for uid in graph.containers}
    for edge in graph.calls:
        if edge.target:
            incoming.setdefault(edge.target, []).append(edge)

    for uid, container in sorted(graph.containers.items()):
        name = container.name
        kind = "container"
        if container.container_type in PUBLIC_CONTAINER_TYPES:
            decisions.append(_decision(
                uid, kind, name, "public", "high",
                f"container_type:{container.container_type}",
                "registered_or_external_entrypoint",
                lines=(container.source.line,),
            ))
            continue
        if container.container_type not in INTERNAL_CONTAINER_TYPES:
            decisions.append(_decision(
                uid, kind, name, "unknown", "low",
                f"unsupported_container_type:{container.container_type}",
                "external_surface_not_proven",
                lines=(container.source.line,),
            ))
            continue
        edges = incoming.get(uid, [])
        if not edges:
            decisions.append(_decision(
                uid, kind, name, "unknown", "medium",
                "no_static_incoming_edge",
                "may_be_externally_invoked",
                lines=(container.source.line,),
            ))
            continue
        if any(edge.status != "resolved" for edge in edges):
            decisions.append(_decision(
                uid, kind, name, "unknown", "high",
                "incoming_edge_not_fully_resolved",
                "dynamic_or_ambiguous_external_surface",
                lines=(container.source.line,),
            ))
            continue
        decisions.append(_decision(
            uid, kind, name, "internal", "high",
            f"container_type:{container.container_type}",
            "all_incoming_edges_static_and_resolved",
            lines=(container.source.line,),
        ))
    return decisions


def _definition_decisions(graph: DenizenGraph) -> list[SurfaceDecision]:
    decisions: list[SurfaceDecision] = []
    for (scope, name), binding in sorted(graph.definitions.items()):
        if binding.status in {"resolved", "unused"}:
            classification, confidence, reasons = "internal", "high", ("queue_local_scope", f"binding_status:{binding.status}")
        else:
            classification, confidence, reasons = "unknown", "high", (f"binding_status:{binding.status}", "definition_scope_not_proven")
        decisions.append(_decision(
            f"{scope}::{name}",
            "definition",
            scope,
            classification,
            confidence,
            *reasons,
            lines=tuple(sorted(set(binding.declarations + binding.uses + binding.call_argument_uses))),
        ))
    return decisions


def _state_decisions(graph: DenizenGraph) -> list[SurfaceDecision]:
    decisions: list[SurfaceDecision] = []
    for (storage, root), accesses in sorted(graph.state_roots.items()):
        lines = tuple(sorted({access.line for access in accesses}))
        identifier = f"{storage}:{root}"
        if storage == "server":
            decisions.append(_decision(
                identifier,
                "state",
                storage,
                "public",
                "high",
                "persistent_server_state",
                "may_be_read_by_external_scripts",
                lines=lines,
            ))
        else:
            decisions.append(_decision(
                identifier,
                "state",
                storage,
                "unknown",
                "medium",
                "non_server_state_can_cross_script_boundaries",
                "external_reader_not_proven_absent",
                lines=lines,
            ))
    return decisions


def _reference_decisions(graph: DenizenGraph) -> list[SurfaceDecision]:
    decisions: list[SurfaceDecision] = []
    for index, edge in enumerate(graph.unresolved_references + graph.dynamic_references):
        if edge.status == "dynamic":
            reason = "dynamic_reference_target"
            identifier = f"dynamic::{index}::{edge.target_name}"
        elif edge.status == "ambiguous":
            reason = "ambiguous_reference_target"
            identifier = f"ambiguous::{edge.target_name}"
        else:
            reason = "unresolved_reference_target"
            identifier = f"external::{edge.target_name}"
        decisions.append(_decision(
            identifier,
            "reference",
            edge.source,
            "unknown",
            "high",
            reason,
            f"reference_kind:{edge.kind}",
            lines=(edge.line,),
        ))
    return decisions


def classify_surface(graph: DenizenGraph) -> SurfaceMap:
    """Classify every identifier that can affect safe obfuscation."""
    decisions = _container_decisions(graph)
    decisions.extend(_definition_decisions(graph))
    decisions.extend(_state_decisions(graph))
    decisions.extend(_reference_decisions(graph))
    return SurfaceMap(decisions)
