"""One hard proof-state gate for a dCore Denizen project.

This tool deliberately cannot turn a clean static lint into a READY release.
Runtime is an explicit report with required scenario witnesses.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from dcore.lint.script import MetaIndex, expand_input_paths, issue, lint_parsed, normalize_findings, parse_addon_spec, parse_file
from dcore.gates.shadow import load_plan, simulate
from dcore.knowledge.retrieval import resolve_meta, route


GENERIC_RUNTIME_CASES = ("reload", "quit", "death", "repeat_input", "cleanup")
DOG_RUNTIME_CASES = ("flat_ground", "water_boundary", "obstruction", "no_progress", *GENERIC_RUNTIME_CASES)
TRANSFORM_RUNTIME_CASES = ("owner_first_person", "owner_f5", "observer", "reload", "quit", "death", "repeat_transform", "two_controllers", "stale_entity_cleanup")
GRAVITY_RUNTIME_CASES = ("capture", "hold", "release", "drop", "world_change", "quit", "death", "cleanup", "repeat_capture", "two_targets")
TREASURE_RUNTIME_CASES = ("group_size_4", "session_isolation", "join_idempotency", "register", "discover", "open", "expire", "online_inventory", "offline_inventory", "duplicate_guard", "worker_loss", "cleanup", "repeat_input")
COMPLEX_TERMS = ("reflect", "shader", "resource pack", "modelengine", "itemsadder", "cmi", "voxizen", "physics")


def default_db() -> Path | None:
    candidates = (Path(__file__).with_name("dcore.sqlite"), Path(__file__).resolve().parents[1] / "knowledge" / "data" / "dcore.sqlite")
    return next((path for path in candidates if path.is_file()), None)


def runtime_cases(text: str) -> tuple[str, ...]:
    lowered = text.casefold()
    if any(term in lowered for term in ("gravity_gun", "gravity gun", "captured_by", "gravitygun")):
        return GRAVITY_RUNTIME_CASES
    if any(term in lowered for term in ("treasures.dsc", "treasure", "treasure_session", "session_isolation")):
        return TREASURE_RUNTIME_CASES
    if any(term in lowered for term in ("wolf", "dog", "собак", "pathfinding", "walk ")):
        return DOG_RUNTIME_CASES
    if any(term in lowered for term in ("modelengine", "transformation", "display", "shader")):
        return TRANSFORM_RUNTIME_CASES
    return GENERIC_RUNTIME_CASES


def read_runtime_report(path: Path | None, required: tuple[str, ...]) -> dict[str, Any]:
    if path is None:
        return {"state": "RUNTIME_NOT_RUN", "reason": "No --runtime-report was supplied.", "missing_cases": list(required)}
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"state": "RUNTIME_INVALID", "reason": f"Cannot read runtime report: {exc}", "missing_cases": list(required)}
    cases = report.get("cases") if isinstance(report, dict) else None
    if report.get("status") != "PASS" or not isinstance(cases, dict):
        return {"state": "RUNTIME_INVALID", "reason": "Runtime report requires status=PASS and a cases object.", "missing_cases": list(required)}
    missing = [case for case in required if cases.get(case) != "PASS"]
    return {
        "state": "RUNTIME_PASS" if not missing else "RUNTIME_PARTIAL",
        "reason": "All required runtime cases passed." if not missing else "Some required runtime cases are not PASS.",
        "missing_cases": missing,
    }


def read_route_decision(path: Path | None, required: bool) -> str:
    if not required:
        return "ROUTE_NOT_REQUIRED"
    if path is None:
        return "ROUTE_REQUIRED"
    try:
        decision = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "ROUTE_INVALID"
    if (
        isinstance(decision, dict)
        and decision.get("tool") == "dcore_design"
        and decision.get("status") == "READY_FOR_PROOF"
        and isinstance(decision.get("selected_for_proof"), str)
        and decision["selected_for_proof"]
    ):
        return "ROUTE_PASS"
    return "ROUTE_INVALID"


def execute(args: argparse.Namespace) -> dict[str, Any]:
    database = args.db or default_db()
    if not database or not database.is_file():
        raise ValueError("dCore database not found. Expected <skill-root>/dcore/knowledge/data/dcore.sqlite; pass --db explicitly.")
    paths = expand_input_paths(args.paths)
    scripts = {path: parse_file(path.read_text(encoding="utf-8")) for path in paths}
    source_text = "\n".join(parsed.text for parsed in scripts.values())
    target = {key: value for key, value in {
        "minecraft": args.minecraft, "paper": args.paper, "java": args.java,
        "denizen": args.denizen_version, "denizenm": args.denizenm,
    }.items() if value}
    jars: dict[str, Path] = {}
    for declaration in args.jar:
        name, separator, raw_path = declaration.partition("=")
        if not separator or not name or not raw_path:
            raise ValueError("--jar must use addon=path")
        jars[parse_addon_spec(name)[0]] = Path(raw_path)
    meta = MetaIndex(database, args.profile, set(args.addon), target=target, jars=jars, require_jar_evidence=args.require_jar_evidence)
    findings = []
    all_scripts = {name for parsed in scripts.values() for name in parsed.scripts}
    for path, parsed in scripts.items():
        items = lint_parsed(parsed, meta)
        for name, number in parsed.references:
            if name not in all_scripts:
                severity = "error" if getattr(args, "closed_world", False) else "warning"
                items.append(issue(
                    "unresolved_script", severity, number,
                    f"Referenced script '{name}' is not present in the lint artifact set.",
                    layer="reference",
                    suggestion="Add every project file to the dcore_run input or omit --closed-world for an intentional partial patch.",
                ))
        findings.extend({"file": str(path), **item} for item in items)
    findings = normalize_findings(findings)
    errors = [item for item in findings if item["severity"] == "error"]
    query = args.query or source_text[:12000]
    with sqlite3.connect(database) as db:
        domains, cards = route(db, query, args.intent)
        meta_result = resolve_meta(db, query, args.profile, tuple(args.addon), 8, args.denizen_version, args.denizenm)
    target_state = "TARGET_PASS" if args.minecraft and (args.denizenm or args.denizen_version) else "TARGET_PARTIAL"
    retrieval_state = "RETRIEVAL_PASS" if meta_result["matches"] and not meta_result["missing_version_meta"] else "RETRIEVAL_PARTIAL"
    complex_route = args.require_route or any(term in query.casefold() for term in COMPLEX_TERMS)
    route_state = read_route_decision(args.decision, complex_route)
    addon_state = "ADDON_SIGNATURE_PARTIAL" if meta.unverified_provider_addons or (args.require_jar_evidence and any(item["code"] == "jar_evidence_missing" for item in findings)) else "ADDON_SIGNATURE_PASS"
    static_state = "SYNTAX_FAIL" if errors else "SYNTAX_PASS"
    source_labels = " ".join(path.name for path in paths)
    required_runtime = runtime_cases(f"{source_labels}\n{source_text}")
    runtime = read_runtime_report(args.runtime_report, required_runtime)
    simulation = {"state": "SIMULATION_NOT_RUN", "reason": "No --shadow-plan was supplied."}
    if args.shadow_plan:
        try:
            shadow = simulate(load_plan(args.shadow_plan))
            simulation = {"state": shadow["verdict"], "result": shadow}
        except ValueError as exc:
            simulation = {"state": "SIMULATION_INVALID", "reason": str(exc)}
    blocked = [
        state for state in (target_state, retrieval_state, route_state, addon_state, static_state, runtime["state"], simulation["state"])
        if state in {"TARGET_PARTIAL", "RETRIEVAL_PARTIAL", "ROUTE_REQUIRED", "ROUTE_INVALID", "ADDON_SIGNATURE_PARTIAL", "SYNTAX_FAIL", "RUNTIME_NOT_RUN", "RUNTIME_INVALID", "RUNTIME_PARTIAL", "SIMULATION_FAIL", "SIMULATION_INVALID"}
    ]
    return {
        "tool": "dcore_run", "verdict": "READY" if not blocked else "RELEASE_BLOCKED",
        "proof": {"target": target_state, "retrieval": retrieval_state, "route": route_state, "addon_signature": addon_state, "static": static_state, "simulation": simulation["state"], "runtime": runtime["state"]},
        "blocked_by": blocked, "runtime_checklist": list(required_runtime), "runtime": runtime,
        "target": target, "routes": {"domains": domains, "cards": cards}, "simulation": simulation,
        "meta_matches": len(meta_result["matches"]), "findings": findings,
        "summary": dict(Counter(item["severity"] for item in findings)),
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Run dCore's hard target/static/runtime proof gate")
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--db", type=Path)
    parser.add_argument("--profile", default="denizenm")
    parser.add_argument("--minecraft")
    parser.add_argument("--paper")
    parser.add_argument("--java")
    parser.add_argument("--denizen-version")
    parser.add_argument("--denizenm")
    parser.add_argument("--addon", action="append", default=[])
    parser.add_argument("--jar", action="append", default=[])
    parser.add_argument("--require-jar-evidence", action="store_true")
    parser.add_argument("--closed-world", action="store_true", help="unresolved script references are errors")
    parser.add_argument("--intent", default="auto")
    parser.add_argument("--query")
    parser.add_argument("--require-route", action="store_true")
    parser.add_argument("--decision", type=Path, help="Recorded route-decision artifact; its runtime proof remains separate.")
    parser.add_argument("--runtime-report", type=Path)
    parser.add_argument("--shadow-plan", type=Path, help="Low-memory event-session simulation plan; does not replace Minecraft runtime.")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = execute(args)
    except ValueError as exc:
        parser.error(str(exc))
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if result["verdict"] == "READY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
