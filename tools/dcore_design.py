"""Deterministic pre-code route comparison for dCore.

The tool deliberately does not invent routes and does not turn prose confidence
into a numeric score.  A caller supplies two to four candidate route dossiers.
The comparator then applies hard gates, validates exact Meta references when
used, filters evidence by target version/provider and finds the Pareto front of
the remaining viable routes.

`READY_FOR_PROOF` means only that one candidate is proven preferable *for the
declared pre-code facts*.  It never means that the implementation or runtime
behaviour passed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple


TOOL_VERSION = "0.31"
SCHEMA_VERSION = 1

DEFAULT_AXES: Dict[str, str] = {
    "runtime_cost": "min",
    "blast_radius": "min",
    "lifecycle_risk": "min",
    "provider_coupling": "min",
    "proof_burden": "min",
    "change_surface": "min",
}

# Higher values outrank lower values when evidence about the same scope
# conflicts.  Context-only kinds never prove a required scope.
EVIDENCE_RANK: Dict[str, int] = {
    "runtime": 60,
    "installed_runtime": 60,
    "artifact": 50,
    "source": 40,
    "meta": 40,
    "static_analysis": 30,
    "card": 0,
    "community": 0,
    "assumption": 0,
    "memory": 0,
}

# A Meta entry can prove that an API surface is documented, but not that a
# shader route renders, gameplay works, or a performance target is met.
SCOPE_KINDS: Dict[str, Set[str]] = {
    "api": {"meta", "source", "installed_runtime", "runtime"},
    "syntax": {"meta", "source", "installed_runtime", "runtime"},
    "source": {"meta", "source"},
    "version": {"meta", "source", "artifact", "installed_runtime", "runtime"},
    "provider": {"meta", "source", "artifact", "installed_runtime", "runtime"},
    "architecture": {"static_analysis", "source", "artifact", "runtime"},
    "runtime": {"installed_runtime", "runtime"},
    "behavior": {"runtime"},
    "render": {"runtime"},
    "render_route": {"runtime"},
    "performance": {"artifact", "runtime"},
}

PASS_STATUSES = {"pass", "fail", "unknown"}
WEAK_KINDS = {kind for kind, rank in EVIDENCE_RANK.items() if rank == 0}


class InputError(Exception):
    """Raised after collecting one or more input-schema errors."""

    def __init__(self, errors: Sequence[str]):
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def norm(value: Any) -> str:
    return str(value).strip().casefold()


def sorted_unique(values: Iterable[str]) -> List[str]:
    return sorted(set(values))


def default_db() -> Optional[Path]:
    candidate = Path(__file__).resolve().parents[1] / "knowledge" / "dcore.sqlite"
    return candidate if candidate.is_file() else None


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _string_map(value: Any, path: str, errors: List[str], allow_empty: bool = False) -> Dict[str, str]:
    if not isinstance(value, dict):
        errors.append("%s must be an object of string:string pairs" % path)
        return {}
    result: Dict[str, str] = {}
    for key, item in value.items():
        if not _nonempty_string(key) or not _nonempty_string(item):
            errors.append("%s keys and values must be non-empty strings" % path)
            continue
        result[norm(key)] = str(item).strip()
    if not result and not allow_empty:
        errors.append("%s must not be empty" % path)
    return result


def _string_list(value: Any, path: str, errors: List[str], allow_empty: bool = True) -> List[str]:
    if not isinstance(value, list) or any(not _nonempty_string(item) for item in value):
        errors.append("%s must be a list of non-empty strings" % path)
        return []
    result = [str(item).strip() for item in value]
    if not result and not allow_empty:
        errors.append("%s must not be empty" % path)
    return result


def _id_list(items: Any, path: str, errors: List[str], minimum: int = 0) -> List[Dict[str, Any]]:
    if not isinstance(items, list):
        errors.append("%s must be a list" % path)
        return []
    if len(items) < minimum:
        errors.append("%s must contain at least %d item(s)" % (path, minimum))
    result: List[Dict[str, Any]] = []
    seen: Set[str] = set()
    for index, item in enumerate(items):
        item_path = "%s[%d]" % (path, index)
        if not isinstance(item, dict):
            errors.append("%s must be an object" % item_path)
            continue
        item_id = item.get("id")
        if not _nonempty_string(item_id):
            errors.append("%s.id must be a non-empty string" % item_path)
            continue
        lowered = norm(item_id)
        if lowered in seen:
            errors.append("%s contains duplicate id '%s'" % (path, item_id))
            continue
        seen.add(lowered)
        copied = dict(item)
        copied["id"] = str(item_id).strip()
        result.append(copied)
    return result


def validate_input(document: Any) -> Dict[str, Any]:
    """Validate and normalize a comparison dossier.

    Validation is intentionally strict.  Unknown top-level fields are retained
    for forward compatibility, while every field used by the decision is
    normalized here.
    """

    errors: List[str] = []
    if not isinstance(document, dict):
        raise InputError(["input must be a JSON object"])

    schema_version = document.get("schema_version")
    if schema_version != SCHEMA_VERSION:
        errors.append("schema_version must be %d" % SCHEMA_VERSION)
    if not _nonempty_string(document.get("request")):
        errors.append("request must be a non-empty string")

    profile = document.get("profile")
    if not isinstance(profile, dict):
        errors.append("profile must be an object")
        profile = {}
    profile_versions = _string_map(profile.get("versions"), "profile.versions", errors)
    profile_providers = _string_map(profile.get("providers"), "profile.providers", errors)

    constraints = _id_list(document.get("constraints"), "constraints", errors, minimum=1)
    constraint_ids = {norm(item["id"]) for item in constraints}
    normalized_constraints: List[Dict[str, Any]] = []
    for index, item in enumerate(constraints):
        path = "constraints[%d]" % index
        kind = norm(item.get("kind", "hard"))
        if kind not in {"hard", "soft"}:
            errors.append("%s.kind must be 'hard' or 'soft'" % path)
            kind = "hard"
        scopes = _string_list(item.get("required_scopes", []), path + ".required_scopes", errors)
        normalized_constraints.append({
            **item,
            "kind": kind,
            "required_scopes": [norm(scope) for scope in scopes],
        })

    capabilities = _id_list(document.get("capabilities"), "capabilities", errors, minimum=1)
    capability_ids = {norm(item["id"]) for item in capabilities}
    normalized_capabilities: List[Dict[str, Any]] = []
    for index, item in enumerate(capabilities):
        path = "capabilities[%d]" % index
        required = item.get("required", True)
        if not isinstance(required, bool):
            errors.append("%s.required must be boolean" % path)
            required = True
        default_scopes = ["api"] if required else []
        scopes = _string_list(item.get("required_scopes", default_scopes), path + ".required_scopes", errors)
        if required and not scopes:
            errors.append("%s.required_scopes must not be empty for a required capability" % path)
        version_keys = _string_list(item.get("version_keys", []), path + ".version_keys", errors)
        for key in version_keys:
            if norm(key) not in profile_versions:
                errors.append("%s.version_keys references unknown profile version '%s'" % (path, key))
        provider = item.get("provider")
        if provider is not None and not _nonempty_string(provider):
            errors.append("%s.provider must be a non-empty string" % path)
            provider = None
        if provider is not None and norm(provider) not in profile_providers:
            errors.append("%s.provider '%s' is absent from profile.providers" % (path, provider))
        normalized_capabilities.append({
            **item,
            "required": required,
            "required_scopes": [norm(scope) for scope in scopes],
            "version_keys": [norm(key) for key in version_keys],
            "provider": norm(provider) if provider is not None else None,
        })

    axes_value = document.get("axes", DEFAULT_AXES)
    if not isinstance(axes_value, dict) or not axes_value:
        errors.append("axes must be a non-empty object")
        axes_value = DEFAULT_AXES
    axes: Dict[str, str] = {}
    for axis, config in axes_value.items():
        if not _nonempty_string(axis):
            errors.append("axis names must be non-empty strings")
            continue
        goal = config.get("goal") if isinstance(config, dict) else config
        goal = norm(goal)
        if goal not in {"min", "max"}:
            errors.append("axes.%s must be 'min', 'max', or an object with that goal" % axis)
            continue
        axes[norm(axis)] = goal

    routes = _id_list(document.get("routes"), "routes", errors, minimum=2)
    if len(routes) > 4:
        errors.append("routes must contain at most 4 candidates")
    normalized_routes: List[Dict[str, Any]] = []
    for index, route in enumerate(routes):
        path = "routes[%d]" % index
        covers = _string_list(route.get("covers"), path + ".covers", errors, allow_empty=False)
        for capability_id in covers:
            if norm(capability_id) not in capability_ids:
                errors.append("%s.covers references unknown capability '%s'" % (path, capability_id))

        versions = _string_map(route.get("versions"), path + ".versions", errors, allow_empty=True)
        providers = _string_map(route.get("providers"), path + ".providers", errors, allow_empty=True)

        constraint_results = route.get("constraints")
        if not isinstance(constraint_results, dict):
            errors.append("%s.constraints must be an object keyed by constraint id" % path)
            constraint_results = {}
        normalized_results: Dict[str, Dict[str, Any]] = {}
        for key, value in constraint_results.items():
            lowered = norm(key)
            if lowered not in constraint_ids:
                errors.append("%s.constraints references unknown constraint '%s'" % (path, key))
                continue
            if isinstance(value, str):
                status = norm(value)
                refs: List[str] = []
            elif isinstance(value, dict):
                status = norm(value.get("status"))
                refs = _string_list(value.get("evidence", []), path + ".constraints.%s.evidence" % key, errors)
            else:
                errors.append("%s.constraints.%s must be a status string or object" % (path, key))
                continue
            if status not in PASS_STATUSES:
                errors.append("%s.constraints.%s.status must be pass, fail, or unknown" % (path, key))
            normalized_results[lowered] = {"status": status, "evidence": refs}

        evidence = _id_list(route.get("evidence", []), path + ".evidence", errors)
        evidence_ids = {norm(item["id"]) for item in evidence}
        normalized_evidence: List[Dict[str, Any]] = []
        for eindex, item in enumerate(evidence):
            epath = "%s.evidence[%d]" % (path, eindex)
            kind = norm(item.get("kind"))
            status = norm(item.get("status"))
            scope = norm(item.get("scope"))
            capability = item.get("capability")
            constraint = item.get("constraint")
            if kind not in EVIDENCE_RANK:
                errors.append("%s.kind is unsupported: %s" % (epath, item.get("kind")))
            if status not in PASS_STATUSES:
                errors.append("%s.status must be pass, fail, or unknown" % epath)
            if not scope:
                errors.append("%s.scope must be a non-empty string" % epath)
            if (capability is None) == (constraint is None):
                errors.append("%s must reference exactly one capability or constraint" % epath)
            if capability is not None and norm(capability) not in capability_ids:
                errors.append("%s.capability references unknown id '%s'" % (epath, capability))
            if constraint is not None and norm(constraint) not in constraint_ids:
                errors.append("%s.constraint references unknown id '%s'" % (epath, constraint))
            provider = item.get("provider")
            if provider is not None and not _nonempty_string(provider):
                errors.append("%s.provider must be a non-empty string" % epath)
                provider = None
            provider_version = item.get("provider_version")
            if provider_version is not None and not _nonempty_string(provider_version):
                errors.append("%s.provider_version must be a non-empty string" % epath)
                provider_version = None
            evidence_versions = item.get("versions", {})
            evidence_versions = _string_map(evidence_versions, epath + ".versions", errors, allow_empty=True)
            if kind != "meta" and kind not in WEAK_KINDS and not _nonempty_string(item.get("source")):
                errors.append("%s.source is required for admissible non-Meta evidence" % epath)
            if kind == "meta" and not isinstance(item.get("entry_id"), int):
                errors.append("%s.entry_id must be an integer for Meta evidence" % epath)
            normalized_evidence.append({
                **item,
                "kind": kind,
                "status": status,
                "scope": scope,
                "capability": norm(capability) if capability is not None else None,
                "constraint": norm(constraint) if constraint is not None else None,
                "provider": norm(provider) if provider is not None else None,
                "provider_version": str(provider_version).strip() if provider_version is not None else None,
                "versions": evidence_versions,
            })

        for constraint_id, result in normalized_results.items():
            for evidence_id in result["evidence"]:
                if norm(evidence_id) not in evidence_ids:
                    errors.append("%s.constraints.%s references unknown evidence '%s'" % (path, constraint_id, evidence_id))

        metrics = route.get("metrics")
        if not isinstance(metrics, dict):
            errors.append("%s.metrics must be an object" % path)
            metrics = {}
        normalized_metrics: Dict[str, Optional[float]] = {}
        for axis in axes:
            value = metrics.get(axis)
            if value is None:
                normalized_metrics[axis] = None
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                errors.append("%s.metrics.%s must be a finite number" % (path, axis))
                normalized_metrics[axis] = None
            else:
                normalized_metrics[axis] = float(value)

        falsifier = route.get("falsifier")
        if not _nonempty_string(falsifier):
            errors.append("%s.falsifier must state what would disprove this route" % path)
        proof = route.get("proof")
        if not isinstance(proof, dict):
            errors.append("%s.proof must be an object" % path)
            proof = {}
        for field in ("test", "success", "failure"):
            if not _nonempty_string(proof.get(field)):
                errors.append("%s.proof.%s must be a non-empty string" % (path, field))

        normalized_routes.append({
            **route,
            "covers": [norm(item) for item in covers],
            "versions": versions,
            "providers": providers,
            "constraints": normalized_results,
            "evidence": normalized_evidence,
            "metrics": normalized_metrics,
            "falsifier": str(falsifier).strip() if _nonempty_string(falsifier) else "",
            "proof": dict(proof),
        })

    if errors:
        raise InputError(errors)

    return {
        **document,
        "schema_version": SCHEMA_VERSION,
        "request": str(document["request"]).strip(),
        "profile": {**profile, "versions": profile_versions, "providers": profile_providers},
        "constraints": normalized_constraints,
        "capabilities": normalized_capabilities,
        "axes": axes,
        "routes": normalized_routes,
    }


@dataclass
class MetaCheck:
    valid: bool
    reason: str
    citation: Optional[Dict[str, Any]] = None


class MetaIndex:
    """Small exact-reference reader for dCore's existing Meta tables."""

    def __init__(self, path: Optional[Path]):
        self.path = path
        self.db: Optional[sqlite3.Connection] = None
        if path is not None and path.is_file():
            self.db = sqlite3.connect(str(path))
            self.db.row_factory = sqlite3.Row

    def close(self) -> None:
        if self.db is not None:
            self.db.close()

    def check(self, evidence: Mapping[str, Any]) -> MetaCheck:
        if self.db is None:
            return MetaCheck(False, "Meta evidence cannot be checked because no database is available")
        try:
            row = self.db.execute(
                """SELECT p.entry_id,p.product,p.category,p.name,p.object_type,p.syntax,
                          p.commit_sha,p.source_file,p.source_line,p.deprecated
                   FROM meta_preferred p WHERE p.entry_id=?""",
                (evidence.get("entry_id"),),
            ).fetchone()
        except sqlite3.Error as exc:
            return MetaCheck(False, "Meta database is incompatible: %s" % exc)
        if row is None:
            return MetaCheck(False, "Meta entry_id %s does not exist" % evidence.get("entry_id"))

        exact_fields = {
            "product": "product",
            "category": "category",
            "name": "name",
            "object_type": "object_type",
            "commit_sha": "commit_sha",
        }
        for input_name, row_name in exact_fields.items():
            expected = evidence.get(input_name)
            if expected is not None and norm(expected) != norm(row[row_name]):
                return MetaCheck(
                    False,
                    "Meta entry %s %s mismatch: expected '%s', database has '%s'"
                    % (row["entry_id"], input_name, expected, row[row_name]),
                )
        citation = {
            "entry_id": row["entry_id"],
            "product": row["product"],
            "category": row["category"],
            "name": row["name"],
            "object_type": row["object_type"],
            "syntax": row["syntax"],
            "commit_sha": row["commit_sha"],
            "source_file": row["source_file"],
            "source_line": row["source_line"],
            "deprecated": row["deprecated"],
        }
        return MetaCheck(True, "exact Meta reference matched", citation)


def _scope_allows_kind(scope: str, kind: str) -> bool:
    if EVIDENCE_RANK.get(kind, 0) <= 0:
        return False
    allowed = SCOPE_KINDS.get(scope)
    return True if allowed is None else kind in allowed


def _version_compatible(candidate: str, target: str) -> bool:
    return norm(candidate) == norm(target)


def _evidence_applicability(
    evidence: Mapping[str, Any],
    scope: str,
    capability: Optional[Mapping[str, Any]],
    route: Mapping[str, Any],
    profile: Mapping[str, Any],
    meta: MetaIndex,
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    kind = evidence["kind"]
    if evidence["scope"] != scope:
        return False, "scope mismatch", None
    if not _scope_allows_kind(scope, kind):
        return False, "evidence kind '%s' cannot prove scope '%s'" % (kind, scope), None

    required_provider = capability.get("provider") if capability else None
    evidence_provider = evidence.get("provider")
    if required_provider:
        if evidence_provider != required_provider:
            return False, "evidence provider does not match required provider '%s'" % required_provider, None
        target_provider_version = profile["providers"][required_provider]
        if evidence.get("provider_version") is None:
            return False, "provider_version is missing", None
        if not _version_compatible(evidence["provider_version"], target_provider_version):
            return False, "provider version does not match target", None
        if route["providers"].get(required_provider) != target_provider_version:
            return False, "route provider does not match target", None
    elif evidence_provider:
        if evidence_provider not in route["providers"]:
            return False, "evidence provider is not declared by the route", None
        target_version = profile["providers"].get(evidence_provider)
        if target_version is None:
            return False, "evidence provider is not allowed by the target profile", None
        if evidence.get("provider_version") is None or not _version_compatible(
            evidence["provider_version"], target_version
        ):
            return False, "evidence provider version does not match target", None

    for version_key in capability.get("version_keys", []) if capability else []:
        candidate = evidence["versions"].get(version_key)
        target = profile["versions"][version_key]
        if candidate is None:
            return False, "evidence is missing target version '%s'" % version_key, None
        if not _version_compatible(candidate, target):
            return False, "evidence version '%s' does not match target" % version_key, None

    citation = None
    if kind == "meta":
        check = meta.check(evidence)
        if not check.valid:
            return False, check.reason, None
        citation = check.citation
        if required_provider and norm(citation["product"]) != required_provider:
            return False, "Meta product does not match required provider '%s'" % required_provider, citation
        if evidence_provider and norm(citation["product"]) != evidence_provider:
            return False, "Meta product does not match evidence provider", citation
    return True, "eligible", citation


def _resolve_scope(
    evidence_items: Sequence[Mapping[str, Any]],
    scope: str,
    capability: Optional[Mapping[str, Any]],
    route: Mapping[str, Any],
    profile: Mapping[str, Any],
    meta: MetaIndex,
) -> Dict[str, Any]:
    eligible: List[Tuple[Mapping[str, Any], int, Optional[Dict[str, Any]]]] = []
    excluded: List[Dict[str, str]] = []
    for evidence in evidence_items:
        applicable, reason, citation = _evidence_applicability(
            evidence, scope, capability, route, profile, meta
        )
        if not applicable:
            excluded.append({"evidence_id": evidence["id"], "reason": reason})
            continue
        if evidence["status"] == "unknown":
            excluded.append({"evidence_id": evidence["id"], "reason": "evidence status is unknown"})
            continue
        eligible.append((evidence, EVIDENCE_RANK[evidence["kind"]], citation))

    if not eligible:
        return {
            "scope": scope,
            "status": "unknown",
            "reason": "no admissible evidence",
            "evidence": [],
            "excluded": excluded,
        }
    highest = max(rank for _, rank, _ in eligible)
    strongest = [(item, citation) for item, rank, citation in eligible if rank == highest]
    statuses = {item["status"] for item, _ in strongest}
    rendered = []
    for item, citation in strongest:
        rendered.append({
            "evidence_id": item["id"],
            "kind": item["kind"],
            "status": item["status"],
            "source": item.get("source"),
            "citation": citation,
        })
    if len(statuses) > 1:
        status = "conflict"
        reason = "equally strong evidence conflicts"
    else:
        status = next(iter(statuses))
        reason = "strongest admissible evidence is %s" % status
    return {
        "scope": scope,
        "status": status,
        "reason": reason,
        "evidence": rendered,
        "excluded": excluded,
    }


def _profile_checks(route: Mapping[str, Any], profile: Mapping[str, Any]) -> Tuple[List[str], List[str]]:
    failures: List[str] = []
    unknowns: List[str] = []
    for key, target in profile["versions"].items():
        candidate = route["versions"].get(key)
        if candidate is None or norm(candidate) in {"unknown", "*"}:
            unknowns.append("route version '%s' is not proven" % key)
        elif not _version_compatible(candidate, target):
            failures.append("route version '%s' (%s) does not match target (%s)" % (key, candidate, target))
    for provider, version in route["providers"].items():
        target = profile["providers"].get(provider)
        if target is None:
            failures.append("route uses undeclared provider '%s'" % provider)
        elif not _version_compatible(version, target):
            failures.append("route provider '%s' version (%s) does not match target (%s)" % (provider, version, target))
    return failures, unknowns


def _route_report(
    route: Mapping[str, Any],
    profile: Mapping[str, Any],
    constraints: Sequence[Mapping[str, Any]],
    capabilities: Sequence[Mapping[str, Any]],
    axes: Mapping[str, str],
    meta: MetaIndex,
) -> Dict[str, Any]:
    failures, unknowns = _profile_checks(route, profile)
    warnings: List[str] = []
    evidence_report: Dict[str, Any] = {"capabilities": {}, "constraints": {}}

    by_capability: Dict[str, List[Mapping[str, Any]]] = {}
    by_constraint: Dict[str, List[Mapping[str, Any]]] = {}
    evidence_by_id = {norm(item["id"]): item for item in route["evidence"]}
    for evidence in route["evidence"]:
        if evidence.get("capability"):
            by_capability.setdefault(evidence["capability"], []).append(evidence)
        if evidence.get("constraint"):
            by_constraint.setdefault(evidence["constraint"], []).append(evidence)

    for capability in capabilities:
        capability_id = norm(capability["id"])
        if capability["required"] and capability_id not in route["covers"]:
            failures.append("required capability '%s' is not covered" % capability["id"])
            continue
        if capability_id not in route["covers"]:
            continue
        required_provider = capability.get("provider")
        if required_provider and required_provider not in route["providers"]:
            failures.append("capability '%s' requires undeclared route provider '%s'" % (capability["id"], required_provider))
        scopes = []
        for scope in capability["required_scopes"]:
            resolved = _resolve_scope(
                by_capability.get(capability_id, []), scope, capability, route, profile, meta
            )
            scopes.append(resolved)
            if resolved["status"] == "fail":
                failures.append("capability '%s' scope '%s' has failing evidence" % (capability["id"], scope))
            elif resolved["status"] != "pass":
                unknowns.append("capability '%s' scope '%s' is not proven" % (capability["id"], scope))
        evidence_report["capabilities"][capability["id"]] = scopes

    for constraint in constraints:
        constraint_id = norm(constraint["id"])
        result = route["constraints"].get(constraint_id, {"status": "unknown", "evidence": []})
        blocking = constraint["kind"] == "hard"
        if result["status"] == "fail":
            message = "constraint '%s' failed" % constraint["id"]
            (failures if blocking else warnings).append(message)
        elif result["status"] != "pass":
            message = "constraint '%s' is unknown" % constraint["id"]
            (unknowns if blocking else warnings).append(message)

        candidates = by_constraint.get(constraint_id, [])
        if result["evidence"]:
            allowed = {norm(item) for item in result["evidence"]}
            candidates = [item for item in candidates if norm(item["id"]) in allowed]
        scopes = []
        for scope in constraint["required_scopes"]:
            resolved = _resolve_scope(candidates, scope, None, route, profile, meta)
            scopes.append(resolved)
            if resolved["status"] == "fail":
                message = "constraint '%s' scope '%s' has failing evidence" % (constraint["id"], scope)
                (failures if blocking else warnings).append(message)
            elif resolved["status"] != "pass":
                message = "constraint '%s' scope '%s' is not proven" % (constraint["id"], scope)
                (unknowns if blocking else warnings).append(message)
        evidence_report["constraints"][constraint["id"]] = {
            "declared_status": result["status"],
            "scopes": scopes,
        }

    for axis in axes:
        if route["metrics"].get(axis) is None:
            unknowns.append("comparison metric '%s' is missing" % axis)

    # Context-only evidence is kept visible, but never upgrades a verdict.
    contextual = [
        {"evidence_id": item["id"], "kind": item["kind"], "scope": item["scope"]}
        for item in route["evidence"]
        if item["kind"] in WEAK_KINDS
    ]

    failures = sorted_unique(failures)
    unknowns = sorted_unique(unknowns)
    warnings = sorted_unique(warnings)
    if failures:
        verdict = "REJECTED"
    elif unknowns:
        verdict = "UNPROVEN"
    else:
        verdict = "VIABLE"
    return {
        "id": route["id"],
        "verdict": verdict,
        "hard_failures": failures,
        "unknowns": unknowns,
        "warnings": warnings,
        "metrics": route["metrics"],
        "evidence": evidence_report,
        "context_only_evidence": contextual,
        "falsifier": route["falsifier"],
        "proof": {
            "test": route["proof"]["test"],
            "success": route["proof"]["success"],
            "failure": route["proof"]["failure"],
        },
    }


def dominates(a: Mapping[str, Any], b: Mapping[str, Any], axes: Mapping[str, str]) -> bool:
    """Return true when a is no worse on all axes and better on at least one."""

    strictly_better = False
    for axis, goal in axes.items():
        avalue = a["metrics"][axis]
        bvalue = b["metrics"][axis]
        if avalue is None or bvalue is None:
            return False
        if goal == "min":
            if avalue > bvalue:
                return False
            if avalue < bvalue:
                strictly_better = True
        else:
            if avalue < bvalue:
                return False
            if avalue > bvalue:
                strictly_better = True
    return strictly_better


def compare(document: Any, db_path: Optional[Path] = None) -> Dict[str, Any]:
    normalized = validate_input(document)
    meta = MetaIndex(db_path)
    try:
        reports = [
            _route_report(
                route,
                normalized["profile"],
                normalized["constraints"],
                normalized["capabilities"],
                normalized["axes"],
                meta,
            )
            for route in normalized["routes"]
        ]
    finally:
        meta.close()

    viable = [report for report in reports if report["verdict"] == "VIABLE"]
    unproven = [report for report in reports if report["verdict"] == "UNPROVEN"]
    dominated_by: Dict[str, List[str]] = {report["id"]: [] for report in reports}
    for candidate in viable:
        for competitor in viable:
            if candidate is competitor:
                continue
            if dominates(competitor, candidate, normalized["axes"]):
                dominated_by[candidate["id"]].append(competitor["id"])
    for report in reports:
        report["dominated_by"] = sorted(dominated_by[report["id"]])

    pareto_front = sorted(
        report["id"] for report in viable if not dominated_by[report["id"]]
    )
    selected: Optional[str] = None
    if not viable:
        status = "NO_VIABLE_ROUTE" if not unproven else "INCOMPLETE"
        reason = "no route is proven viable"
    elif unproven:
        status = "INCOMPLETE"
        reason = "an unproven route could still change the comparison"
    elif len(pareto_front) != 1:
        status = "INCOMPLETE"
        reason = "multiple non-dominated routes remain"
    else:
        status = "READY_FOR_PROOF"
        selected = pareto_front[0]
        reason = "one proven route is the unique non-dominated candidate"

    next_proofs = [
        {"route_id": report["id"], **report["proof"]}
        for report in reports
        if (
            report["verdict"] == "UNPROVEN"
            or report["id"] in pareto_front
            or report["id"] == selected
        )
    ]
    next_proofs.sort(key=lambda item: item["route_id"])

    result = {
        "tool": "dcore_design",
        "tool_version": TOOL_VERSION,
        "schema_version": SCHEMA_VERSION,
        "input_sha256": sha256_json(document),
        "status": status,
        "reason": reason,
        "selected_for_proof": selected,
        "pareto_front": pareto_front,
        "axes": normalized["axes"],
        "routes": sorted(reports, key=lambda item: item["id"]),
        "next_proofs": next_proofs,
        "scope": "pre-code route decision only; runtime and implementation remain unverified",
    }
    return result


def _json_diff(expected: Any, actual: Any, path: str = "$") -> List[str]:
    if type(expected) is not type(actual):
        return ["%s type differs (%s != %s)" % (path, type(expected).__name__, type(actual).__name__)]
    if isinstance(expected, dict):
        differences: List[str] = []
        keys = sorted(set(expected) | set(actual))
        for key in keys:
            child = "%s.%s" % (path, key)
            if key not in expected:
                differences.append("%s is unexpected" % child)
            elif key not in actual:
                differences.append("%s is missing" % child)
            else:
                differences.extend(_json_diff(expected[key], actual[key], child))
        return differences
    if isinstance(expected, list):
        if len(expected) != len(actual):
            return ["%s length differs (%d != %d)" % (path, len(expected), len(actual))]
        differences = []
        for index, (left, right) in enumerate(zip(expected, actual)):
            differences.extend(_json_diff(left, right, "%s[%d]" % (path, index)))
        return differences
    return [] if expected == actual else ["%s differs (%r != %r)" % (path, expected, actual)]


def verify(document: Any, decision: Any, db_path: Optional[Path] = None) -> Dict[str, Any]:
    expected = compare(document, db_path)
    differences = _json_diff(expected, decision)
    return {
        "tool": "dcore_design",
        "tool_version": TOOL_VERSION,
        "status": "DECISION_REPRODUCED" if not differences else "DECISION_MISMATCH",
        "input_sha256": sha256_json(document),
        "decision_status": expected["status"],
        "selected_for_proof": expected["selected_for_proof"],
        "differences": differences,
    }


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise InputError(["cannot read %s: %s" % (path, exc)])
    except json.JSONDecodeError as exc:
        raise InputError(["invalid JSON in %s: %s" % (path, exc)])


def _write_json(value: Any, output: Optional[Path], pretty: bool) -> None:
    text = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        indent=2 if pretty else None,
        separators=None if pretty else (",", ":"),
    ) + "\n"
    if output is None:
        sys.stdout.write(text)
    else:
        output.write_text(text, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Deterministic hard-gate and Pareto comparison of 2-4 dCore routes"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    compare_parser = subparsers.add_parser("compare", help="compare candidate routes")
    compare_parser.add_argument("--input", type=Path, required=True, help="route dossier JSON")
    compare_parser.add_argument("--db", type=Path, default=default_db(), help="dCore SQLite database")
    compare_parser.add_argument("--output", type=Path, help="write decision JSON to this file")
    compare_parser.add_argument("--pretty", action="store_true")

    verify_parser = subparsers.add_parser("verify", help="recompute and verify a decision JSON")
    verify_parser.add_argument("--input", type=Path, required=True, help="original route dossier JSON")
    verify_parser.add_argument("--decision", type=Path, required=True, help="decision JSON from compare")
    verify_parser.add_argument("--db", type=Path, default=default_db(), help="dCore SQLite database")
    verify_parser.add_argument("--output", type=Path, help="write verification JSON to this file")
    verify_parser.add_argument("--pretty", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        document = _read_json(args.input)
        if args.command == "compare":
            result = compare(document, args.db)
            _write_json(result, args.output, args.pretty)
            return 0 if result["status"] == "READY_FOR_PROOF" else 2
        decision = _read_json(args.decision)
        result = verify(document, decision, args.db)
        _write_json(result, args.output, args.pretty)
        return 0 if result["status"] == "DECISION_REPRODUCED" else 3
    except InputError as exc:
        result = {
            "tool": "dcore_design",
            "tool_version": TOOL_VERSION,
            "status": "INVALID_INPUT",
            "errors": exc.errors,
        }
        _write_json(result, getattr(args, "output", None), getattr(args, "pretty", False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
