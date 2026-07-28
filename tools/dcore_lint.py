"""dCore DenizenScript lint.

The linter is intentionally portable, but it is no longer a bracket-only smoke
test.  With dcore.sqlite it validates the selected Denizen dialect and enabled
addons, then adds high-confidence lifecycle and event-scope diagnostics.

It still does not replace `/ex reload` or gameplay testing.  Every diagnostic
states which layer produced it so a clean report is not confused with runtime
proof.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import textwrap
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


SPLIT_IF = re.compile(r"\b(?:stop|determine)\s+if:\S+\s+(?:==|!=|>=|<=|>|<|\|\||&&)\s+")
SCRIPT_TITLE = re.compile(r"^([A-Za-z0-9_\-]+):\s*(?:#.*)?$")
YAML_KEY = re.compile(r"^\s*([A-Za-z0-9_ <>|*./\-]+):(?:\s|$)")
REFERENCE = re.compile(
    r"(?:\brun\s+|<proc\[|<script\[)([A-Za-z0-9_\-]+)", re.IGNORECASE
)
CONTEXT_TAG = re.compile(r"<context\.([A-Za-z0-9_]+)", re.IGNORECASE)
NAMED_ARGUMENT = re.compile(r"^([A-Za-z_][A-Za-z0-9_.-]*):")
COMMAND_TOKEN = re.compile(r"^[~^]?([A-Za-z][A-Za-z0-9_\-]*)\b")
EVENT_LINE = re.compile(r"^(\s*)(on|after)\s+(.+):\s*(?:#.*)?$", re.IGNORECASE)
IMPORT_LINE = re.compile(r"^\s{2,}([A-Za-z_$][\w.$]*):?\s*$")

ALLOWED_CONTAINERS = {
    "assignment", "book", "command", "data", "economy", "entity", "format",
    "interact", "inventory", "item", "map", "procedure", "task", "world",
}
UNIVERSAL_NAMED_ARGUMENTS = {"if", "save"}
FLOW_PSEUDO_COMMANDS = {"case", "choose", "default"}
HOT_EVENTS = ("on tick", "moves", "walks", "steps on block")
BROAD_CANCEL_EVENTS = (
    "right clicks entity", "damaged", "tries to attack", "breaks block", "destroyed by explosion",
    "piston extends", "piston retracts", "liquid", "water", "block forms",
    "block spreads", "targets entity", "teleports", "splits",
)
IDENTITY_GUARDS = (
    "has_flag[", ".flag[", ".script.name", "inventory_flagged:",
    "location_ids", "context.location.flag[", "context.block.flag[",
)
DESIGN_FIELDS = (
    "expected_scale", "entry_points", "state_owners", "hot_path_budget",
    "concurrency", "persistence_reload", "failure_cleanup", "change_axes",
    "code_shape_budget", "route_decision",
)
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
}
MUTATION_COMMANDS = {
    "adjust", "adjustblock", "animate", "create", "determine", "equip",
    "flag", "inventory", "modifyblock", "push", "remove", "spawn", "take",
    "teleport", "walk",
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
    if code in CONTRAST_HINTS:
        result["contrast_example"] = CONTRAST_HINTS[code]
    return result


def has_unclosed_tags(line: str) -> bool:
    """Detect structural Denizen tag imbalance without treating `< 3` as a tag."""
    depth = 0
    for index, char in enumerate(line):
        if char == "<":
            if line.startswith("<-:", index):
                continue
            next_char = line[index + 1] if index + 1 < len(line) else ""
            if next_char and not next_char.isspace() and next_char not in "=>":
                depth += 1
        elif char == ">" and depth:
            depth -= 1
    return depth != 0


def strip_comment(line: str) -> str:
    """Remove a YAML comment while preserving hashes inside quotes and tags."""
    quote: str | None = None
    angle = square = 0
    for index, char in enumerate(line):
        if quote:
            if char == quote and (index == 0 or line[index - 1] != "\\"):
                quote = None
            continue
        if char in "\"'":
            quote = char
        elif char == "<":
            angle += 1
        elif char == ">" and angle:
            angle -= 1
        elif char == "[":
            square += 1
        elif char == "]" and square:
            square -= 1
        elif char == "#" and not angle and not square:
            return line[:index].rstrip()
    return line.rstrip()


def split_arguments(text: str) -> list[str]:
    """Split a Denizen command without splitting nested tags/maps or quoted text."""
    output: list[str] = []
    current: list[str] = []
    quote: str | None = None
    angle = square = round_depth = curly = 0
    for index, char in enumerate(text):
        if quote:
            current.append(char)
            if char == quote and (index == 0 or text[index - 1] != "\\"):
                quote = None
            continue
        if char in "\"'":
            quote = char
            current.append(char)
        elif char == "<":
            angle += 1
            current.append(char)
        elif char == ">" and angle:
            angle -= 1
            current.append(char)
        elif char == "[":
            square += 1
            current.append(char)
        elif char == "]" and square:
            square -= 1
            current.append(char)
        elif char == "(":
            round_depth += 1
            current.append(char)
        elif char == ")" and round_depth:
            round_depth -= 1
            current.append(char)
        elif char == "{":
            curly += 1
            current.append(char)
        elif char == "}" and curly:
            curly -= 1
            current.append(char)
        elif char.isspace() and not any((angle, square, round_depth, curly)):
            if current:
                output.append("".join(current))
                current = []
        else:
            current.append(char)
    if current:
        output.append("".join(current))
    return output


def pattern_regex(pattern: str) -> re.Pattern[str] | None:
    """Compile Denizen event Meta placeholders, alternatives and optional groups."""
    pattern = pattern.strip().lower()
    if not pattern or pattern.startswith("unnamed "):
        return None

    def compile_part(start: int, closing: str | None = None) -> tuple[str, int] | None:
        output: list[str] = []
        index = start
        while index < len(pattern):
            char = pattern[index]
            if closing and char == closing:
                return "".join(output), index + 1
            if char.isspace():
                end = index
                while end < len(pattern) and pattern[end].isspace():
                    end += 1
                if end < len(pattern) and pattern[end] == "(":
                    nested = compile_part(end + 1, ")")
                    if nested is None:
                        return None
                    body, index = nested
                    output.append(r"(?:\s+" + body + r")?")
                    continue
                output.append(r"\s+")
                index = end
                continue
            if char == "(":
                nested = compile_part(index + 1, ")")
                if nested is None:
                    return None
                body, index = nested
                output.append(r"(?:" + body + r")?")
                continue
            if char == "<":
                end = pattern.find(">", index + 1)
                if end == -1:
                    return None
                output.append(r"\S+")
                index = end + 1
                continue
            end = index
            while end < len(pattern) and not pattern[end].isspace() and pattern[end] not in "()<":
                end += 1
            token = pattern[index:end]
            if "|" in token:
                output.append("(?:" + "|".join(re.escape(part) for part in token.split("|")) + ")")
            else:
                output.append(re.escape(token))
            index = end
        return ("".join(output), index) if closing is None else None

    compiled = compile_part(0)
    if compiled is None:
        return None
    try:
        return re.compile(r"^" + compiled[0] + r"$")
    except re.error:
        return None


def remove_event_switches(matcher: str) -> tuple[str, set[str]]:
    parts = split_arguments(matcher)
    switches: set[str] = set()
    base: list[str] = []
    for part in parts:
        found = NAMED_ARGUMENT.match(part)
        if found:
            switches.add(found.group(1).lower())
        else:
            base.append(part)
    return " ".join(base).lower(), switches


@dataclass
class MetaEntry:
    product: str
    name: str
    syntax: str
    deprecated: str
    fields: dict[str, list[str]] = field(default_factory=dict)


class MetaIndex:
    """Small in-memory index over the current dCore Meta snapshot."""

    def __init__(self, db_path: Path | None, profile: str, addons: set[str]):
        self.available = bool(db_path and db_path.is_file())
        self.profile = profile
        self.addons = set(addons)
        self.unverified_provider_addons = self.addons.intersection({"megizen", "denizen_physics"})
        self.commands: dict[str, list[MetaEntry]] = defaultdict(list)
        self.mechanisms: dict[str, list[MetaEntry]] = defaultdict(list)
        self.events: list[MetaEntry] = []
        self.event_switches: set[str] = set()
        if not self.available:
            return
        products = {"Denizen-Core"}
        if profile == "denizenm":
            products.add("DenizenM")
        else:
            products.add("Denizen")
        if "reflect" in addons:
            products.add("denizen-reflect")
        if "voxizen" in addons:
            products.add("Voxizen")
        with sqlite3.connect(db_path) as db:
            db.row_factory = sqlite3.Row
            marks = ",".join("?" for _ in products)
            rows = db.execute(
                f"SELECT entry_id,product,category,name,syntax,deprecated "
                f"FROM meta_preferred WHERE product IN ({marks})",
                sorted(products),
            ).fetchall()
            for row in rows:
                fields: dict[str, list[str]] = defaultdict(list)
                for field_name, value in db.execute(
                    "SELECT field_name,value FROM meta_fields WHERE entry_id=? ORDER BY field_name,ordinal",
                    (row["entry_id"],),
                ):
                    fields[field_name].append(value)
                entry = MetaEntry(
                    row["product"], row["name"], row["syntax"], row["deprecated"], dict(fields)
                )
                category = row["category"].lower()
                if category == "command":
                    command = re.match(r"[A-Za-z][A-Za-z0-9_\-]*", row["name"])
                    if command:
                        self.commands[command.group(0).lower()].append(entry)
                elif category in {"mechanism", "property"}:
                    raw = fields.get("name", [])
                    names = raw or [row["name"].rsplit(".", 1)[-1]]
                    for name in names:
                        self.mechanisms[name.strip().lower()].append(entry)
                elif category == "event":
                    self.events.append(entry)
                    for value in fields.get("switch", []) + fields.get("switches", []):
                        found = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*):", value)
                        if found:
                            self.event_switches.add(found.group(1).lower())

    def command(self, name: str) -> list[MetaEntry]:
        return self.commands.get(name.lower(), [])

    def mechanism(self, name: str) -> list[MetaEntry]:
        return self.mechanisms.get(name.lower(), [])

    def match_event(self, matcher: str) -> list[MetaEntry]:
        parts = split_arguments(matcher)
        base = " ".join(
            part for part in parts
            if not ((found := NAMED_ARGUMENT.match(part)) and found.group(1).lower() in self.event_switches)
        ).lower()
        matched: list[MetaEntry] = []
        for entry in self.events:
            patterns: list[str] = []
            for value in entry.fields.get("events", []) + entry.fields.get("event", []):
                patterns.extend(line.strip() for line in value.splitlines() if line.strip())
            if not patterns:
                patterns = [entry.name]
            for pattern in patterns:
                compiled = pattern_regex(pattern)
                if compiled and compiled.match(base):
                    matched.append(entry)
                    break
        return matched


@dataclass
class ParsedFile:
    text: str
    lines: list[str]
    paths: list[tuple[str, ...]]
    scripts: dict[str, int]
    references: list[tuple[str, int]]
    events: list[tuple[int, int, str]]


def parse_file(text: str) -> ParsedFile:
    lines = text.splitlines()
    stack: list[tuple[int, str]] = []
    paths: list[tuple[str, ...]] = []
    scripts: dict[str, int] = {}
    references: list[tuple[str, int]] = []
    event_starts: list[tuple[int, int, str]] = []
    for number, raw in enumerate(lines, 1):
        line = strip_comment(raw)
        if not line.strip():
            paths.append(tuple(item[1] for item in stack))
            continue
        indent = len(line) - len(line.lstrip(" "))
        list_item = line.lstrip().startswith("- ")
        while stack and (stack[-1][0] > indent if list_item else stack[-1][0] >= indent):
            stack.pop()
        paths.append(tuple(item[1] for item in stack))
        if raw and not raw[0].isspace():
            match = SCRIPT_TITLE.match(raw)
            if match and match.group(1).lower() != "import":
                scripts[match.group(1).lower()] = number
        event_match = EVENT_LINE.match(line)
        if event_match and "events" in (item[1].lower() for item in stack):
            event_starts.append((number, len(event_match.group(1)), event_match.group(3)))
        for match in REFERENCE.finditer(line.strip()):
            references.append((match.group(1).lower(), number))
        key_match = YAML_KEY.match(line)
        if key_match and not line.lstrip().startswith("-"):
            stack.append((indent, key_match.group(1).strip()))
    events: list[tuple[int, int, str]] = []
    script_starts = sorted(scripts.values())
    for index, (start, indent, matcher) in enumerate(event_starts):
        end = next((line - 1 for line in script_starts if line > start), len(lines))
        for candidate, candidate_indent, _ in event_starts[index + 1:]:
            if candidate > end:
                break
            if candidate_indent <= indent:
                end = candidate - 1
                break
        events.append((start, end, matcher))
    return ParsedFile(text, lines, paths, scripts, references, events)


def command_lines(parsed: ParsedFile) -> Iterable[tuple[int, str]]:
    for number, raw in enumerate(parsed.lines, 1):
        stripped = strip_comment(raw).strip()
        if not stripped.startswith("- "):
            continue
        path = {part.lower() for part in parsed.paths[number - 1]}
        if "script" not in path and "events" not in path:
            continue
        content = stripped[2:].strip()
        token = COMMAND_TOKEN.match(content)
        if token:
            yield number, content


def command_named_arguments(entry: MetaEntry) -> set[str]:
    syntax = "\n".join([entry.syntax, *entry.fields.get("syntax", [])])
    return {
        match.group(1).lower()
        for match in re.finditer(r"(?<![A-Za-z0-9_.-])([A-Za-z_][A-Za-z0-9_.-]*):", syntax)
    }


def lint_parsed(parsed: ParsedFile, meta: MetaIndex) -> list[dict]:
    results: list[dict] = []
    if meta.unverified_provider_addons:
        names = ", ".join(sorted(meta.unverified_provider_addons))
        results.append(issue(
            "provider_meta_pending", "information", 0,
            f"Provider addon Meta is not indexed for: {names}.",
            layer="api", source="dCore addon policy",
            suggestion="Keep calls behind one adapter and verify the exact jar/docs/runtime before treating them as valid.",
        ))
    seen_scripts: set[str] = set()
    key_seen: dict[tuple[tuple[str, ...], str], int] = {}

    for number, raw in enumerate(parsed.lines, 1):
        stripped = strip_comment(raw).strip()
        indent_text = raw[: len(raw) - len(raw.lstrip())]
        if "\t" in indent_text:
            results.append(issue("raw_tab_symbol", "error", number, "Indentation contains a raw tab."))
        if raw.rstrip() != raw:
            results.append(issue("stray_space_eol", "information", number, "Trailing whitespace."))
        spaces = len(raw) - len(raw.lstrip(" "))
        if stripped and spaces % 2:
            results.append(issue(
                "odd_indentation", "warning", number,
                "Indentation is not a multiple of two spaces.",
                suggestion="Normalize indentation before reload.",
            ))
        if SPLIT_IF.search(stripped):
            results.append(issue(
                "split_if_switch", "error", number,
                "if: is one argument; spaced comparisons require an if block.",
            ))
        if stripped.endswith("\\"):
            results.append(issue(
                "shell_continuation", "error", number,
                "DenizenScript has no shell-style backslash continuation.",
            ))
        if has_unclosed_tags(stripped):
            results.append(issue("uneven_tags", "error", number, "Uneven tag brackets."))
        if stripped.count('"') % 2 or stripped.count("'") % 2:
            results.append(issue("missing_quotes", "warning", number, "Uneven quotes."))
        if raw and not raw[0].isspace():
            match = SCRIPT_TITLE.match(raw)
            if match:
                name = match.group(1).lower()
                if name in seen_scripts:
                    results.append(issue(
                        "duplicate_script", "error", number,
                        f"Duplicate script container '{name}'.",
                    ))
                seen_scripts.add(name)
        key_match = YAML_KEY.match(strip_comment(raw))
        if key_match and not raw.lstrip().startswith("-"):
            key = key_match.group(1).strip().lower()
            parent = tuple(part.lower() for part in parsed.paths[number - 1])
            identity = (parent, key)
            executable_path = bool({"script", "events"}.intersection(parent))
            if (
                identity in key_seen
                and spaces > 0
                and not executable_path
                and not key.startswith(("on ", "after "))
            ):
                results.append(issue(
                    "duplicate_key", "error", number,
                    f"Duplicate YAML key '{key}' under the same parent (first at line {key_seen[identity]}).",
                ))
            else:
                key_seen[identity] = number

        if re.search(r"<\[[^>\]]+\]\.(?!as\[entity\]\.)type(?:[.>])", stripped, re.IGNORECASE):
            results.append(issue(
                "ambiguous_object_type", "warning", number,
                "`.type` on an untyped definition can resolve as deprecated ObjectTag.type.",
                layer="api",
                source="DenizenM Meta/runtime regression",
                suggestion="Use `.object_type` for generic type checks or cast with `.as[entity]` before EntityTag.type.",
            ))

    # Container shape.
    ordered_scripts = sorted(parsed.scripts.items(), key=lambda item: item[1])
    container_regions: list[tuple[str, int, int, str | None]] = []
    for index, (name, start) in enumerate(ordered_scripts):
        end = ordered_scripts[index + 1][1] - 1 if index + 1 < len(ordered_scripts) else len(parsed.lines)
        container_type = None
        for number in range(start + 1, end + 1):
            match = re.match(r"^\s+type:\s*([A-Za-z_\-]+)", strip_comment(parsed.lines[number - 1]), re.I)
            if match:
                container_type = match.group(1).lower()
                break
        if not container_type:
            results.append(issue("missing_container_type", "error", start, f"Container '{name}' has no type."))
        elif container_type not in ALLOWED_CONTAINERS:
            results.append(issue(
                "invalid_container", "error", start,
                f"Container '{name}' uses unknown type '{container_type}'.",
                layer="api",
            ))
        container_regions.append((name, start, end, container_type))

    # Maintainability is measured, not inferred from line count alone. These
    # thresholds are review gates: large cohesive recovery code can be valid,
    # but it must be deliberately decomposed or justified.
    commands = list(command_lines(parsed))

    # A non-passive determine and an unconditional stop terminate the current
    # queue path. The next command at the same indentation is therefore dead;
    # a lower indentation has left the branch and remains reachable.
    for index, (number, content) in enumerate(commands):
        lowered = content.lower()
        terminal = (
            lowered == "stop"
            or (lowered.startswith("determine ") and not lowered.startswith("determine passively "))
        )
        if not terminal:
            continue
        scope_end = next(
            (event_end for event_start, event_end, _ in parsed.events if event_start < number <= event_end),
            next((end for _, start, end, _ in container_regions if start < number <= end), number),
        )
        indent = len(parsed.lines[number - 1]) - len(parsed.lines[number - 1].lstrip(" "))
        for following_number, _ in commands[index + 1:]:
            if following_number > scope_end:
                break
            following_indent = len(parsed.lines[following_number - 1]) - len(parsed.lines[following_number - 1].lstrip(" "))
            if following_indent > indent:
                continue
            if following_indent == indent:
                results.append(issue(
                    "unreachable_after_terminal_command", "error", following_number,
                    f"This command is unreachable because line {number} terminates the current queue path.",
                    layer="control_flow", source="dCore terminal-command rule",
                    suggestion="Move required work before the terminal command, or use `determine passively` only when continued execution is intentional.",
                ))
            break

    def region_metrics(start: int, end: int) -> tuple[list[tuple[int, str]], int, int, int]:
        region = [(number, content) for number, content in commands if start < number <= end]
        if not region:
            return region, 0, 0, 0
        indents = [len(parsed.lines[number - 1]) - len(parsed.lines[number - 1].lstrip(" ")) for number, _ in region]
        nesting = (max(indents) - min(indents)) // 2
        branches = sum(
            content.lower().startswith(("if ", "else if ", "choose ", "case "))
            for _, content in region
        )
        else_if_by_indent: Counter[int] = Counter(
            len(parsed.lines[number - 1]) - len(parsed.lines[number - 1].lstrip(" "))
            for number, content in region if content.lower().startswith("else if ")
        )
        ladder = max(else_if_by_indent.values(), default=0)
        return region, nesting, branches, ladder

    for start, end, matcher in parsed.events:
        region, nesting, branches, ladder = region_metrics(start, end)
        count = len(region)
        if count > 60:
            results.append(issue(
                "oversized_event_handler", "warning", start,
                f"Event handler contains {count} executable commands; its orchestration and domain work are coupled.",
                layer="maintainability", source="dCore clean-code budget",
                suggestion="Keep the event as validate -> dispatch. Move only cohesive lifecycle operations behind named tasks; do not create forwarding micro-tasks.",
            ))
        elif count > 35:
            results.append(issue(
                "large_event_handler", "suggestion", start,
                f"Event handler contains {count} executable commands.",
                layer="maintainability", source="dCore clean-code budget",
                suggestion="Check whether validation, selection, commit and feedback can be separated without adding ceremonial layers.",
            ))
        if nesting >= 6:
            results.append(issue(
                "deep_control_nesting", "warning", start,
                f"Event reaches {nesting} nested command levels.",
                layer="maintainability", source="dCore clean-code budget",
                suggestion="Use ownership guards and early exits; express exclusive modes with choose and repeated variation with data.",
            ))
        elif nesting >= 4:
            results.append(issue(
                "deep_control_nesting", "suggestion", start,
                f"Event reaches {nesting} nested command levels.",
                layer="maintainability", source="dCore clean-code budget",
                suggestion="Flatten with guard clauses before adding another branch.",
            ))
        if branches >= 24:
            severity = "warning"
        elif branches >= 14:
            severity = "suggestion"
        else:
            severity = ""
        if severity:
            results.append(issue(
                "branch_dense_handler", severity, start,
                f"Event contains {branches} control branches.",
                layer="maintainability", source="dCore clean-code budget",
                suggestion="Separate independent phases and replace value-selection ladders with choose or config maps. Guard clauses are acceptable and should remain local.",
            ))
        if ladder >= 4:
            results.append(issue(
                "else_if_ladder", "suggestion", start,
                f"Event contains an else-if ladder with at least {ladder} alternatives at one level.",
                layer="maintainability", source="dCore clean-code budget",
                suggestion="Use choose for exclusive modes or a data map when branches differ only by values.",
            ))

    for name, start, end, container_type in container_regions:
        if container_type == "world":
            event_count = sum(start < event_start <= end for event_start, _, _ in parsed.events)
            if event_count > 12:
                results.append(issue(
                    "world_container_many_entry_points", "suggestion", start,
                    f"World container '{name}' owns {event_count} event entry points.",
                    layer="maintainability", source="dCore clean-code budget",
                    suggestion="Group entry points by one lifecycle authority or feature boundary; splitting by arbitrary event type is not an improvement.",
                ))
            continue
        if container_type not in {"task", "procedure", "command"}:
            continue
        region, nesting, branches, ladder = region_metrics(start, end)
        count = len(region)
        if container_type == "command":
            for line_number in range(start + 1, end + 1):
                if re.match(r"^\s+permission:\s*\S+", strip_comment(parsed.lines[line_number - 1]), re.I):
                    results.append(issue(
                        "permission_policy_review", "suggestion", line_number,
                        f"Command '{name}' declares an access permission.",
                        layer="access_contract", source="dCore permission-policy rule",
                        suggestion="Keep it only when the requested access policy requires it, and test both allowed and denied behavior.",
                    ))
        if container_type == "task" and count == 1:
            command = COMMAND_TOKEN.match(region[0][1])
            if command and command.group(1).lower() in {"inject", "run"}:
                results.append(issue(
                    "forwarding_task", "suggestion", start,
                    f"Task '{name}' only forwards to another container.",
                    layer="maintainability", source="dCore clean-code budget",
                    suggestion="Call the cohesive owner directly, or inline the forwarding boundary if it has no independent contract.",
                ))
        if (
            container_type in {"task", "procedure"}
            and count <= 5
            and re.search(r"(?:^|_)(?:manager|service|processor|orchestrator|helper)(?:_|$)", name)
        ):
            results.append(issue(
                "ceremonial_container_name", "suggestion", start,
                f"Small {container_type} '{name}' uses an architectural role name without showing that responsibility.",
                layer="maintainability", source="dCore clean-code budget",
                suggestion="Name the domain action or owned transition; keep manager/service names only when the container actually owns that lifecycle.",
            ))
        if count > 90:
            results.append(issue(
                "oversized_executable_container", "warning", start,
                f"{container_type.title()} container '{name}' contains {count} executable commands.",
                layer="maintainability", source="dCore clean-code budget",
                suggestion="Split only at stable phase, ownership or provider boundaries; retain one orchestrator and one cleanup owner.",
            ))
        elif count > 55:
            results.append(issue(
                "large_executable_container", "suggestion", start,
                f"{container_type.title()} container '{name}' contains {count} executable commands.",
                layer="maintainability", source="dCore clean-code budget",
                suggestion="Review mixed responsibilities, repeated command shapes and duplicated state reads before delivery.",
            ))
        if nesting >= 6:
            results.append(issue(
                "deep_control_nesting", "warning", start,
                f"Container '{name}' reaches {nesting} nested command levels.",
                layer="maintainability", source="dCore clean-code budget",
                suggestion="Flatten guards or extract a cohesive phase; do not hide nesting behind forwarding tasks.",
            ))
        if branches >= 24:
            results.append(issue(
                "branch_dense_container", "warning", start,
                f"Container '{name}' contains {branches} control branches.",
                layer="maintainability", source="dCore clean-code budget",
                suggestion="Define explicit phases and use data-driven variation where only values differ.",
            ))
        if ladder >= 4:
            results.append(issue(
                "else_if_ladder", "suggestion", start,
                f"Container '{name}' contains an else-if ladder with at least {ladder} alternatives at one level.",
                layer="maintainability", source="dCore clean-code budget",
                suggestion="Use choose for exclusive modes or a data map for value-only variation.",
            ))

    # Meta-backed commands and their named arguments.
    for number, content in command_lines(parsed):
        token = COMMAND_TOKEN.match(content)
        if not token:
            continue
        name = token.group(1).lower()
        if name in FLOW_PSEUDO_COMMANDS:
            continue
        entries = meta.command(name) if meta.available else []
        if meta.available and not entries:
            results.append(issue(
                "unknown_command", "error", number,
                f"Command '{name}' is absent from the selected {meta.profile} + addon Meta.",
                layer="api",
                source="dcore.sqlite Meta",
                suggestion="Resolve the exact installed dialect or enable the required addon; do not replace it with a console workaround automatically.",
            ))
            continue
        if not entries:
            continue
        # Generic `name:value` validation is deliberately not attempted here.
        # Denizen action syntax, MapTags and comparison operands all use colons,
        # while the exported Meta syntax is not a machine grammar. Validate only
        # high-confidence command-specific regressions until an AST parser exists.
        if name == "playeffect" and re.search(r"(?:^|\s)location:", content, re.I):
            results.append(issue(
                "invalid_playeffect_location_argument", "error", number,
                "playeffect uses `at:`, not `location:`.",
                layer="api",
                source="DenizenM Meta/runtime regression",
                suggestion="Replace `location:<location>` with `at:<location>`.",
            ))

        if name == "adjust":
            args = split_arguments(content)
            if len(args) >= 3:
                mechanism = NAMED_ARGUMENT.match(args[2])
                if mechanism and meta.available and not meta.mechanism(mechanism.group(1)):
                    results.append(issue(
                        "unknown_mechanism", "error", number,
                        f"Mechanism '{mechanism.group(1)}' is absent from the selected Meta.",
                        layer="api",
                        source="dcore.sqlite Meta",
                    ))

    # Entity/item container mechanism keys.
    if meta.available:
        for number, raw in enumerate(parsed.lines, 1):
            path = tuple(part.lower() for part in parsed.paths[number - 1])
            if not path or path[-1] != "mechanisms":
                continue
            match = re.match(r"^\s+([A-Za-z_][A-Za-z0-9_]*):", strip_comment(raw))
            if match and not meta.mechanism(match.group(1)):
                results.append(issue(
                    "unknown_mechanism", "error", number,
                    f"Mechanism '{match.group(1)}' is absent from the selected Meta.",
                    layer="api",
                    source="dcore.sqlite Meta",
                ))

    # Event Meta, contexts, scope and cancellation ownership.
    for start, end, matcher in parsed.events:
        matched = meta.match_event(matcher) if meta.available else []
        if meta.available and not matched:
            results.append(issue(
                "unknown_event", "warning", start,
                f"Event matcher '{matcher}' was not matched by the selected Meta.",
                layer="api",
                source="dcore.sqlite Meta",
                suggestion="Treat this as a proof boundary: check exact matcher and addon/fork switches before delivery.",
            ))
        body = "\n".join(parsed.lines[start:end])
        body_lower = body.lower()
        contexts = {match.group(1).lower() for match in CONTEXT_TAG.finditer(body)}
        documented_contexts: set[str] = set()
        for entry in matched:
            for value in entry.fields.get("context", []) + entry.fields.get("contexts", []):
                documented_contexts.update(
                    found.group(1).lower()
                    for found in re.finditer(r"<context\.([A-Za-z_][A-Za-z0-9_]*)", value, re.I)
                )
        for context in sorted(contexts - documented_contexts):
            if matched and context not in {"cancelled"}:
                results.append(issue(
                    "undocumented_event_context", "suggestion", start,
                    f"context.{context} is not documented on the matched event Meta entry.",
                    layer="api",
                    source="dcore.sqlite Meta",
                    suggestion="Verify the installed build; context names do not transfer between similar events.",
                ))

        cancellation_lines = [
            start + offset + 1
            for offset, line in enumerate(parsed.lines[start:end])
            if re.search(r"\bdetermine\b.*\bcancel", line, re.I)
        ]
        broad = any(term in matcher.lower() for term in BROAD_CANCEL_EVENTS)
        if broad and cancellation_lines:
            first_cancel = min(cancellation_lines)
            prefix = "\n".join(parsed.lines[start:first_cancel - 1]).lower()
            guarded = any(marker in prefix for marker in IDENTITY_GUARDS)
            if not guarded:
                results.append(issue(
                    "broad_cancel_without_identity_guard", "error", first_cancel,
                    "A broad world event cancels vanilla behavior before proving ownership/identity.",
                    layer="lifecycle",
                    source="dCore event blast-radius rule",
                    suggestion="Use a script/entity matcher when available, or stop on a stable ownership marker before any determination or mutation.",
                ))
            else:
                results.append(issue(
                    "broad_event_guarded", "information", start,
                    "This global matcher is guarded, but still receives unrelated world events.",
                    layer="performance",
                    source="dCore event blast-radius rule",
                    suggestion="Prefer the narrowest script/entity/location matcher supported by the installed DenizenM Meta.",
                ))
        elif broad:
            mutation_present = any(
                (token := COMMAND_TOKEN.match(content)) and token.group(1).lower() in MUTATION_COMMANDS
                for number, content in commands if start < number <= end
            )
            if mutation_present:
                results.append(issue(
                    "broad_event_mutation_scope", "suggestion", start,
                    "A broad world event performs mutations and therefore receives unrelated server traffic.",
                    layer="performance", source="dCore event blast-radius rule",
                    suggestion="Use the narrowest matcher and make stable identity/session/location rejection the first executable path.",
                ))
        if any(hot in matcher.lower() for hot in HOT_EVENTS):
            if "server.worlds.parse[entities]" in body_lower or ".find_entities[" in body_lower:
                results.append(issue(
                    "hot_event_entity_scan", "error", start,
                    "A high-frequency event performs an entity/world scan.",
                    layer="performance",
                    suggestion="Use an active-session reference or spatial index and bound all candidate work.",
                ))

    # Busy/unbounded loops and Reflect dialect handling.
    for number, raw in enumerate(parsed.lines, 1):
        if re.match(r"^\s*-\s*while\s+true\s*:", strip_comment(raw), re.I):
            indent = len(raw) - len(raw.lstrip(" "))
            block: list[str] = []
            for following in parsed.lines[number:]:
                if following.strip() and len(following) - len(following.lstrip(" ")) <= indent:
                    break
                block.append(following)
            joined = "\n".join(block).lower()
            if "wait " not in joined:
                results.append(issue(
                    "busy_while_true", "error", number,
                    "while true has no wait in its body.", layer="performance",
                ))
            elif not any(token in joined for token in (" stop", "timeout", "elapsed", "expire", "session")):
                results.append(issue(
                    "unproven_loop_bound", "warning", number,
                    "The loop yields, but no explicit lifetime/session/timeout exit was recognized.",
                    layer="lifecycle",
                    suggestion="State the hard lifetime owner and prove every exit reaches cleanup.",
                ))

    reflect_used = bool(re.search(r"(?:<invoke\[|\-\s*invoke\b)", parsed.text, re.I))
    if reflect_used:
        if meta.available and "reflect" not in meta.addons:
            results.append(issue(
                "reflect_addon_not_enabled", "error", 0,
                "Reflect syntax is present but the reflect addon dialect is not enabled.",
                layer="api",
                suggestion="Run lint with --addon reflect and pin the installed denizen-reflect version.",
            ))
        else:
            results.append(issue(
                "reflect_boundary", "information", 0,
                "Reflect syntax was parsed as an addon dialect, not as an unknown core command/tag.",
                layer="api",
                source="denizen-reflect Meta",
                suggestion="Keep it behind one adapter and record why no native DenizenM route satisfies the same requirement.",
            ))
    return results


def lint_text(text: str, meta: MetaIndex | None = None) -> list[dict]:
    """Compatibility API used by tests and external callers."""
    if meta is None:
        meta = MetaIndex(None, "denizenm", set())
    return lint_parsed(parse_file(text), meta)


def executable_contract_text(text: str) -> str:
    return "\n".join(
        strip_comment(line) for line in text.splitlines() if strip_comment(line).strip()
    )


def lint_decision(decision: object, expected: object = None) -> list[dict]:
    """Validate a dcore_design result without pretending it proves runtime."""
    if not isinstance(decision, dict) or decision.get("tool") != "dcore_design":
        return [issue(
            "decision_invalid", "error", 0,
            "Decision artifact must be machine JSON emitted by dcore_design.",
            layer="contract",
        )]
    results: list[dict] = []
    status = decision.get("status")
    selected = decision.get("selected_for_proof")
    if status != "READY_FOR_PROOF" or not isinstance(selected, str) or not selected:
        results.append(issue(
            "decision_incomplete", "error", 0,
            f"Route decision is {status!r}; no unique proven route may enter implementation.",
            layer="contract",
            suggestion="Supply more evidence, reject a failed route, or make the trade-off an explicit user decision.",
        ))
    if isinstance(expected, dict):
        expected_selected = expected.get("selected_for_proof")
        if expected_selected and expected_selected != selected:
            results.append(issue(
                "decision_contract_mismatch", "error", 0,
                f"Contract selects '{expected_selected}', but decision artifact selects '{selected}'.",
                layer="contract",
            ))
    return results


def lint_contract(text: str, contract: dict, decision: object = None) -> list[dict]:
    """Check explicit witnesses without allowing comments to satisfy a clause."""
    results: list[dict] = []
    executable = executable_contract_text(text)
    design = contract.get("design")
    if not isinstance(design, dict):
        results.append(issue(
            "contract_design_missing", "error", 0,
            "A non-trivial behavior contract requires a pre-code design section.",
            layer="contract",
            suggestion="Record usage scale, entry points, state owners, hot-path budget, concurrency, persistence/reload, cleanup, change axes and code-shape budget before implementation.",
        ))
    else:
        for field_name in DESIGN_FIELDS:
            value = design.get(field_name)
            if value is None or value == "" or value == [] or value == {}:
                results.append(issue(
                    "contract_design_incomplete", "error", 0,
                    f"Pre-code design field '{field_name}' is missing or empty.",
                    layer="contract",
                ))
        route_decision = design.get("route_decision")
        if route_decision is not None and not isinstance(route_decision, dict):
            results.append(issue(
                "contract_route_decision_invalid", "error", 0,
                "design.route_decision must be an object with selected_for_proof and rationale.",
                layer="contract",
            ))
        elif isinstance(route_decision, dict):
            if not route_decision.get("selected_for_proof") or not route_decision.get("rationale"):
                results.append(issue(
                    "contract_route_decision_incomplete", "error", 0,
                    "design.route_decision requires selected_for_proof and rationale.",
                    layer="contract",
                ))
        if decision is not None:
            results.extend(lint_decision(decision, route_decision))
    clauses = contract.get("clauses")
    if not isinstance(clauses, list) or not clauses:
        return [issue("contract_empty", "error", 0, "Contract must contain at least one clause.", layer="contract")]
    seen: set[str] = set()
    for clause in clauses:
        if not isinstance(clause, dict) or not str(clause.get("id", "")).strip():
            results.append(issue("contract_invalid", "error", 0, "Every contract clause requires an id.", layer="contract"))
            continue
        clause_id = str(clause["id"])
        if clause_id in seen:
            results.append(issue("contract_duplicate", "error", 0, f"Duplicate contract clause '{clause_id}'.", layer="contract"))
            continue
        seen.add(clause_id)
        required_all = clause.get("required_all", [])
        required_any = clause.get("required_any", [])
        forbidden = clause.get("forbidden", [])
        required_regex = clause.get("required_regex", [])
        forbidden_regex = clause.get("forbidden_regex", [])
        if not any((required_all, required_any, forbidden, required_regex, forbidden_regex)):
            results.append(issue("contract_no_witness", "error", 0, f"Clause '{clause_id}' has no testable witness.", layer="contract"))
            continue
        for literal in required_all:
            if literal not in executable:
                results.append(issue("contract_missing", "error", 0, f"Clause '{clause_id}' requires executable literal: {literal}", layer="contract"))
        if required_any and not any(literal in executable for literal in required_any):
            results.append(issue("contract_missing", "error", 0, f"Clause '{clause_id}' requires one of: {required_any}", layer="contract"))
        for literal in forbidden:
            if literal in executable:
                results.append(issue("contract_forbidden", "error", 0, f"Clause '{clause_id}' forbids literal: {literal}", layer="contract"))
        for expression in required_regex:
            if not re.search(expression, executable, re.MULTILINE):
                results.append(issue("contract_missing", "error", 0, f"Clause '{clause_id}' requires regex: {expression}", layer="contract"))
        for expression in forbidden_regex:
            if re.search(expression, executable, re.MULTILINE):
                results.append(issue("contract_forbidden", "error", 0, f"Clause '{clause_id}' forbids regex: {expression}", layer="contract"))
    return results


def default_db() -> Path | None:
    candidates = (
        Path(__file__).with_name("dcore.sqlite"),
        Path(__file__).resolve().parents[1] / "knowledge" / "dcore.sqlite",
    )
    return next((path for path in candidates if path.is_file()), None)


def _table_cell(value: object, width: int) -> str:
    text = " ".join(str(value).replace("|", "\\|").split())
    return textwrap.shorten(text, width=width, placeholder="...") if len(text) > width else text


def render_table(results: list[dict], *, show_information: bool = False) -> str:
    visible = [
        result for result in results
        if show_information or result["severity"] != "information"
    ]
    rows = ["| Sev | Code | Location | Problem | Fix |", "|---|---|---|---|---|"]
    for result in visible:
        location = Path(result["file"]).name
        if result["line"]:
            location += f":{result['line']}"
        rows.append(
            "| {sev} | `{code}` | `{location}` | {problem} | {fix} |".format(
                sev=result["severity"].upper(),
                code=result["code"],
                location=location,
                problem=_table_cell(result["message"], 72),
                fix=_table_cell(result.get("suggestion", "-"), 72),
            )
        )
    if not visible:
        rows.append("| PASS | - | - | No static diagnostics. | - |")
    counts = Counter(result["severity"] for result in results)
    blocking = counts["error"] > 0
    verdict = "ERROR" if blocking else "STATIC_OK"
    rows.extend([
        "",
        "| Verdict | Error | Warning | Suggestion | Information |",
        "|---|---:|---:|---:|---:|",
        f"| **{verdict}** | {counts['error']} | {counts['warning']} | {counts['suggestion']} | {counts['information']} |",
        "",
        "Scope: static structure/API/lifecycle only; Refined, `/ex reload`, and gameplay remain separate proof.",
    ])
    if counts["information"] and not show_information:
        rows.append("Information rows are hidden; use `--show-information` when provenance is needed.")
    return "\n".join(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="DenizenM-aware structural, API and lifecycle lint")
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--json", action="store_true", help="Emit machine JSON instead of the human table")
    parser.add_argument("--format", choices=("table", "json"), default="table")
    parser.add_argument("--show-information", action="store_true", help="Include provenance-only rows in table output")
    parser.add_argument("--contract", type=Path, help="JSON behavior witness manifest")
    parser.add_argument("--decision", type=Path, help="JSON result emitted by dcore_design compare")
    parser.add_argument("--db", type=Path, default=default_db())
    parser.add_argument("--profile", choices=("denizenm", "official"), default="denizenm")
    parser.add_argument("--addon", action="append", choices=("reflect", "voxizen", "megizen", "denizen_physics"), default=[])
    parser.add_argument("--external-script", action="append", default=[], help="Known project script intentionally outside this partial lint artifact")
    parser.add_argument("--closed-world", action="store_true", help="unresolved script references are errors")
    parser.add_argument("--strict-warnings", action="store_true")
    args = parser.parse_args()

    parsed_files: dict[Path, ParsedFile] = {}
    for path in args.paths:
        text = path.read_text(encoding="utf-8")
        parsed_files[path] = parse_file(text)
    meta = MetaIndex(args.db, args.profile, set(args.addon))
    all_scripts = {name for parsed in parsed_files.values() for name in parsed.scripts}
    all_scripts.update(name.casefold() for name in args.external_script)
    all_results: list[dict] = []
    contract = json.loads(args.contract.read_text(encoding="utf-8")) if args.contract else None
    decision = json.loads(args.decision.read_text(encoding="utf-8")) if args.decision else None
    if decision is not None and contract is None:
        parser.error("--decision requires --contract")
    for path, parsed in parsed_files.items():
        results = lint_parsed(parsed, meta)
        for name, number in parsed.references:
            if name not in all_scripts:
                severity = "error" if args.closed_world else "warning"
                results.append(issue(
                    "unresolved_script", severity, number,
                    f"Referenced script '{name}' is not present in the lint artifact set.",
                    layer="reference",
                    suggestion="Add every project file to the lint command or omit --closed-world for an intentional partial patch.",
                ))
        if contract:
            results.extend(lint_contract(parsed.text, contract, decision))
        all_results.extend({"file": str(path), **result} for result in results)

    if args.json or args.format == "json":
        print(json.dumps(all_results, ensure_ascii=False, indent=2))
    else:
        print(render_table(all_results, show_information=args.show_information))
    blocking = any(result["severity"] == "error" for result in all_results)
    if args.strict_warnings:
        blocking = blocking or any(result["severity"] == "warning" for result in all_results)
    return 1 if blocking else 0


if __name__ == "__main__":
    raise SystemExit(main())
