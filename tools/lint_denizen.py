"""Portable fail-fast lint gate for dCore-generated DenizenScript.

This intentionally covers high-confidence structural failures only. Run the
full Refined DenizenScript checker and server reload after it.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


SPLIT_IF = re.compile(r"\b(?:stop|determine)\s+if:\S+\s+(?:==|!=|>=|<=|>|<|\|\||&&)\s+")
SCRIPT_TITLE = re.compile(r"^([A-Za-z0-9_\-]+):\s*(?:#.*)?$")
REFERENCE = re.compile(r"(?:\brun\s+|<proc\[)([A-Za-z0-9_\-]+)", re.IGNORECASE)


def issue(code: str, severity: str, line: int, message: str) -> dict:
    return {"code": code, "severity": severity, "line": line, "message": message}


def lint_text(text: str) -> list[dict]:
    results: list[dict] = []
    lines = text.splitlines()
    scripts: set[str] = set()
    references: list[tuple[str, int]] = []
    for number, line in enumerate(lines, 1):
        stripped = line.strip()
        if "\t" in line[: len(line) - len(line.lstrip())]:
            results.append(issue("raw_tab_symbol", "error", number, "Indentation contains a raw tab."))
        if line.rstrip() != line:
            results.append(issue("stray_space_eol", "information", number, "Trailing whitespace."))
        if SPLIT_IF.search(stripped):
            results.append(issue("split_if_switch", "error", number, "if: is one argument; remove spaces or use an if block."))
        if stripped.endswith("\\"):
            results.append(issue("shell_continuation", "error", number, "DenizenScript has no shell-style backslash continuation."))
        if stripped.count("<") != stripped.count(">"):
            results.append(issue("uneven_tags", "error", number, "Uneven tag brackets."))
        if stripped.count('"') % 2 or stripped.count("'") % 2:
            results.append(issue("missing_quotes", "warning", number, "Uneven quotes."))
        if line and not line[0].isspace():
            match = SCRIPT_TITLE.match(line)
            if match:
                name = match.group(1).lower()
                if name in scripts:
                    results.append(issue("duplicate_script", "error", number, f"Duplicate script container '{name}'."))
                scripts.add(name)
        for match in REFERENCE.finditer(stripped):
            references.append((match.group(1).lower(), number))
    for name, number in references:
        if name not in scripts:
            results.append(issue("unresolved_script", "error", number, f"Referenced script '{name}' is not present in this artifact."))
    return results


def lint_contract(text: str, contract: dict) -> list[dict]:
    """Check literal contract witnesses against the complete artifact text.

    This does not prove gameplay semantics. It prevents a full-file response
    from silently omitting or contradicting clauses that the model explicitly
    recorded before generation.
    """
    results: list[dict] = []
    clauses = contract.get("clauses")
    if not isinstance(clauses, list) or not clauses:
        return [issue("contract_empty", "error", 0, "Contract must contain at least one clause.")]
    seen: set[str] = set()
    for clause in clauses:
        if not isinstance(clause, dict) or not str(clause.get("id", "")).strip():
            results.append(issue("contract_invalid", "error", 0, "Every contract clause requires an id."))
            continue
        clause_id = str(clause["id"])
        if clause_id in seen:
            results.append(issue("contract_duplicate", "error", 0, f"Duplicate contract clause '{clause_id}'."))
            continue
        seen.add(clause_id)
        required_all = clause.get("required_all", [])
        required_any = clause.get("required_any", [])
        forbidden = clause.get("forbidden", [])
        if not any((required_all, required_any, forbidden)):
            results.append(issue("contract_no_witness", "error", 0, f"Clause '{clause_id}' has no testable witness."))
            continue
        for literal in required_all:
            if literal not in text:
                results.append(issue("contract_missing", "error", 0, f"Clause '{clause_id}' requires literal: {literal}"))
        if required_any and not any(literal in text for literal in required_any):
            results.append(issue("contract_missing", "error", 0, f"Clause '{clause_id}' requires one of: {required_any}"))
        for literal in forbidden:
            if literal in text:
                results.append(issue("contract_forbidden", "error", 0, f"Clause '{clause_id}' forbids literal: {literal}"))
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--contract", type=Path, help="JSON contract witness manifest")
    args = parser.parse_args()
    all_results = []
    for path in args.paths:
        text = path.read_text(encoding="utf-8")
        for result in lint_text(text):
            all_results.append({"file": str(path), **result})
        if args.contract:
            contract = json.loads(args.contract.read_text(encoding="utf-8"))
            for result in lint_contract(text, contract):
                all_results.append({"file": str(path), **result})
    if args.json:
        print(json.dumps(all_results, ensure_ascii=False, indent=2))
    else:
        for result in all_results:
            print(f"{result['file']}:{result['line']} [{result['severity']}] {result['code']}: {result['message']}")
        print(f"dCore lint: {len(all_results)} issue(s)")
    return 1 if any(result["severity"] == "error" for result in all_results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
