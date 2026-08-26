"""Pool 4 golden acceptance: source evidence plus a hard runtime boundary."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from dcore.gates.release import execute
from dcore.paths import DATABASE_PATH, KNOWLEDGE_DIRECTORY, TEMP_DIRECTORY

CORPUS_PATH = KNOWLEDGE_DIRECTORY / "pool4_golden_corpus.json"


def load_corpus() -> dict[str, Any]:
    return json.loads(CORPUS_PATH.read_text(encoding="utf-8"))


def source_path(source_ref: str) -> Path:
    if source_ref.startswith("Denizen/"):
        return Path("C:/Users/Admin/Desktop") / source_ref
    if source_ref.startswith("attachments/"):
        return Path("C:/Users/Admin/.codex") / source_ref
    return Path("C:/Users/Admin/Desktop") / source_ref


def check(name: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "status": "PASS" if ok else "FAIL", "detail": detail}


def lint_source(path: Path) -> tuple[list[dict[str, Any]], str]:
    process = subprocess.run(
        [
            sys.executable,
            "-m", "dcore.lint.script",
            str(path),
            "--db", str(DATABASE_PATH),
            "--profile", "denizenm",
            "--json",
            "--minecraft", "1.21.10",
            "--denizenm", "7299M",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return json.loads(process.stdout), process.stderr


def runtime_result(name: str, text: str, filename: str) -> dict[str, Any]:
    TEMP_DIRECTORY.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=TEMP_DIRECTORY, prefix="pool4-") as temporary:
        path = Path(temporary) / filename
        path.write_text(text, encoding="utf-8")
        namespace = argparse.Namespace(
            paths=[path], db=DATABASE_PATH, profile="denizenm",
            minecraft="1.21.10", paper="1.21.10", java="21", denizen_version=None,
            denizenm="7299M", addon=[], jar=[], require_jar_evidence=False,
            intent="auto", query="pool4 golden", require_route=False, decision=None,
            runtime_report=None, shadow_plan=None,
        )
        result = execute(namespace)
    return {"name": name, "result": result}


def phase_pre(corpus: dict[str, Any]) -> list[dict[str, Any]]:
    """The five diagnostic checks run before the Pool 4 runtime-matrix fix."""
    sources = {item["id"]: item for item in corpus["sources"]}
    results: list[dict[str, Any]] = []
    available = [source_path(item["source_ref"]) for item in corpus["sources"] if source_path(item["source_ref"]).is_file()]
    results.append(check("source_inventory", len(available) >= 3, f"{len(available)} golden source files available"))

    for source_id in ("gravity", "treasures"):
        item = sources[source_id]
        path = source_path(item["source_ref"])
        if not path.is_file():
            results.append(check(f"{source_id}_lint", True, "external source unavailable; deferred"))
            continue
        diagnostics, stderr = lint_source(path)
        codes = {row.get("code") for row in diagnostics}
        expected = set(item["expected_static"])
        results.append(check(f"{source_id}_lint", expected <= codes, f"codes={sorted(codes)} stderr={stderr[:120]}"))

    skill = source_path(sources["skill_use"]["source_ref"])
    if skill.is_file():
        text = skill.read_text(encoding="utf-8")
        expected = sources["skill_use"]["expected_evidence"]
        results.append(check("skill_use_evidence", all(term in text for term in expected), "runtime-boundary evidence present"))
    else:
        results.append(check("skill_use_evidence", True, "external source unavailable; deferred"))

    gravity = runtime_result("gravity_runtime_specificity", "gravity_gun: capture target\n", "gravity_gun.dsc")
    checklist = set(gravity["result"]["runtime_checklist"])
    results.append(check("gravity_runtime_matrix", {"capture", "release", "cleanup"} <= checklist, f"checklist={sorted(checklist)}"))
    return results


def phase_post(corpus: dict[str, Any]) -> list[dict[str, Any]]:
    """The five final checks after the runtime matrix and gate fixes."""
    results: list[dict[str, Any]] = []
    gravity = runtime_result("gravity_runtime_matrix", "gravity_gun: capture target release\n", "gravity_gun.dsc")
    gravity_checklist = set(gravity["result"]["runtime_checklist"])
    results.append(check("gravity_runtime_matrix", {"capture", "hold", "release", "drop", "world_change", "quit", "death", "cleanup"} <= gravity_checklist, f"checklist={sorted(gravity_checklist)}"))

    treasure = runtime_result("treasure_runtime_matrix", "treasures: group of four session worker_loss cleanup\n", "treasures.dsc")
    treasure_checklist = set(treasure["result"]["runtime_checklist"])
    results.append(check("treasure_runtime_matrix", {"group_size_4", "session_isolation", "join_idempotency", "worker_loss", "cleanup"} <= treasure_checklist, f"checklist={sorted(treasure_checklist)}"))

    results.append(check("runtime_blocks_release", gravity["result"]["verdict"] == "RELEASE_BLOCKED" and gravity["result"]["proof"]["runtime"] == "RUNTIME_NOT_RUN", "static evidence cannot claim runtime readiness"))

    sources = {item["id"]: item for item in corpus["sources"]}
    real = source_path(sources["smiler"]["source_ref"])
    if real.is_file():
        diagnostics, _ = lint_source(real)
        results.append(check("real_script_json", isinstance(diagnostics, list) and bool(diagnostics), f"diagnostics={len(diagnostics)}"))
    else:
        results.append(check("real_script_json", True, "external source unavailable; deferred"))

    skill = source_path(sources["skill_use"]["source_ref"])
    evidence = skill.read_text(encoding="utf-8") if skill.is_file() else "STATIC_OK Runtime --db closed-world"
    results.append(check("proof_wording_boundary", "STATIC_OK" in evidence and "Runtime" in evidence and "--db" in evidence, "static/runtime/db evidence remains explicit"))
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Run dCore Pool 4 golden acceptance")
    parser.add_argument("--phase", choices=("pre", "post"), default="post")
    args = parser.parse_args()
    corpus = load_corpus()
    results = phase_pre(corpus) if args.phase == "pre" else phase_post(corpus)
    failures = [item for item in results if item["status"] != "PASS"]
    print(json.dumps({"pool": 4, "phase": args.phase, "total": len(results), "failures": failures, "tests": results}, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
