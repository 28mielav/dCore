"""Stable finding contract and semantic severity policy for the script linter."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Iterable

CONTRAST_HINTS = {
    "broad_cancel_without_identity_guard": "CX-DEN-001",
    "broad_event_guarded": "CX-DEN-001",
    "deep_control_nesting": "CX-DEN-002",
    "busy_while_true": "CX-DEN-004",
    "unproven_loop_bound": "CX-DEN-004",
    "hot_event_entity_scan": "CX-DEN-004",
    "reflect_addon_not_enabled": "CX-DEN-007",
    "reflect_boundary": "CX-DEN-007",
    "large_event_handler": "CX-DEN-012",
    "oversized_event_handler": "CX-DEN-012",
    "forwarding_task": "CX-DEN-013",
    "ceremonial_container_name": "CX-DEN-013",
    "unreachable_after_terminal_command": "CX-DEN-014",
    "permission_policy_review": "CX-DEN-015",
    "ambiguous_event_matcher": "CX-DEN-018",
    "dog_navigation_owner_conflict": "CX-DEN-019",
    "dog_navigation_hot_repath": "CX-DEN-019",
    "dog_navigation_replaced_without_stop": "CX-DEN-019",
}

def issue(
    code: str,
    severity: str,
    line: int,
    message: str,
    *,
    layer: str = "structural",
    source: str = "dCore",
    suggestion: str | None = None,
    priority: str | None = None,
    confidence: str | None = None,
    evidence: dict[str, Any] | None = None,
    provenance: str | None = None,
) -> dict:
    result = {
        "code": code,
        "severity": severity,
        "line": line,
        "layer": layer,
        "source": source,
        "message": message,
    }
    if suggestion:
        result["suggestion"] = suggestion
    if priority:
        result["priority"] = priority
    if confidence:
        result["confidence"] = confidence
    if evidence:
        result["evidence"] = evidence
    if provenance:
        result["provenance"] = provenance
    if code in CONTRAST_HINTS:
        result["contrast_example"] = CONTRAST_HINTS[code]
    return result


# Queue-proof policy belongs to the lint boundary. Keeping it here means every
# public lint invocation produces the same finding contract; there is no second
# report-only implementation that can drift from the diagnostics it summarizes.
DEFAULT_PRIORITY = {
    "semantic_execution_limit": "P0",
    "while_semantic_limit": "P0",
    "run_recursive_cycle": "P0",
    "inject_recursive_cycle": "P0",
    "run_unknown_script": "P0",
    "inject_unknown_script": "P0",
    "invalid_determine": "P0",
    "foreach_not_static": "P2",
    "unknown_context": "P2",
    "wait_not_static": "P2",
    "repeat_not_static": "P2",
    "choose_without_match": "P1",
    "run_missing_definitions": "P1",
}
INFORMATIONAL_SEMANTIC_CODES = {
    "foreach_not_static", "unknown_context", "wait_not_static", "repeat_not_static",
}
LIFETIME_CODES = {"semantic_execution_limit", "while_semantic_limit"}
EVENT_SWITCH_HINTS = {
    "flagged", "with", "using", "hand", "type", "in_area", "within", "in_world",
    "radius", "from", "to", "at", "material", "entity_type", "cause", "priority",
}
PROVIDER_LABELS = {
    "denizen-core": "core",
    "denizenm": "denizenm",
    "denizen": "denizen",
    "denizen-reflect": "reflect",
    "voxizen": "voxizen",
}

def load_fixture(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("queue fixture must be a JSON object")
    for field in ("context", "definitions_by_container", "known_lifetime_paths"):
        if field in data and not isinstance(data[field], (dict, list)):
            raise ValueError(f"queue fixture field '{field}' has the wrong type")
    return data


def fixture_path_matches(fixture: dict[str, Any], source_path: str, line: int) -> bool:
    paths = fixture.get("known_lifetime_paths", [])
    if not isinstance(paths, list):
        return False
    normalized = Path(source_path).name.casefold() + f":{line}"
    return any(
        str(item).casefold() in {
            normalized,
            Path(source_path).as_posix().casefold() + f":{line}",
        }
        for item in paths
    )


def classify(
    code: str,
    message: str,
    *,
    fixture_matches: bool = False,
) -> tuple[str, str, str]:
    """Return severity, priority and confidence for semantic findings."""
    priority = DEFAULT_PRIORITY.get(code, "P2")
    if code in LIFETIME_CODES:
        if fixture_matches:
            return "information", "P1", "fixture_accepted_runtime_boundary"
        if "dynamic_or_event_driven_wait_boundary" in message:
            return "warning", "P1", "dynamic_or_event_driven_boundary"
        return "error", "P0", "unbounded_or_unresolved"
    if code in INFORMATIONAL_SEMANTIC_CODES:
        return "information", priority, "input_or_platform_boundary"
    severity = "error" if priority == "P0" else "warning"
    return severity, priority, "static_semantic_finding"


def apply_policy(
    findings: Iterable[dict[str, Any]],
    *,
    fixture: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    fixture = fixture or {}
    output: list[dict[str, Any]] = []
    for finding in findings:
        row = dict(finding)
        matched = fixture_path_matches(
            fixture,
            str(row.get("file", "")),
            int(row.get("line", 0)),
        )
        severity, priority, bucket = classify(
            str(row.get("code", "")),
            str(row.get("message", "")),
            fixture_matches=matched,
        )
        row["severity"], row["priority"], row["confidence_bucket"] = severity, priority, bucket
        if matched and row["code"] in LIFETIME_CODES:
            row["message"] = (
                f"{row['message']} Explicit fixture accepts this path as a runtime boundary; "
                "server proof is still required."
            )
        output.append(row)
    return output


def normalize_findings(findings: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Give every diagnostic one stable contract and collapse exact duplicates.

    The linter has several independent passes (YAML shape, Meta, queue-core and
    lifecycle).  They are useful independently, but the same root can otherwise
    be printed repeatedly.  Only byte-for-byte equivalent evidence is merged;
    distinct lines and distinct rules remain visible.
    """
    output: list[dict[str, Any]] = []
    positions: dict[tuple[str, str, int, str], int] = {}
    for finding in findings:
        row = dict(finding)
        code = str(row.get("code", ""))
        row.setdefault("priority", DEFAULT_PRIORITY.get(code, "P2"))
        row.setdefault("confidence", row.get("confidence_bucket", "static_heuristic"))
        row.setdefault("provenance", row.get("source", "dCore"))
        key = (str(row.get("file", "")), code, int(row.get("line", 0)), str(row.get("message", "")))
        previous = positions.get(key)
        if previous is None:
            positions[key] = len(output)
            output.append(row)
            continue
        merged = output[previous]
        evidence = merged.setdefault("evidence", {})
        evidence.setdefault("occurrences", 1)
        evidence["occurrences"] += 1
    return output


def build_report(findings: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(findings)
    semantic = [row for row in rows if row.get("layer") == "denizencore_lite"]
    return {
        "tool": "dcore_queue_report",
        "scope": "portable Denizen queue semantics; not Minecraft runtime",
        "summary": dict(Counter(row.get("confidence_bucket", "unknown") for row in semantic)),
        "priorities": dict(Counter(row.get("priority", "P2") for row in semantic)),
        "findings": semantic,
    }


