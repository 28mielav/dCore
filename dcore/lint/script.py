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
import sys
import textwrap
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from dcore.knowledge.meta_resolution import effective_sources, entry_key, visible
from dcore.knowledge.version_registry import normalize_product_version
from dcore.lint.tagtypes import TagTypeIndex, build_index, deprecations_in_text, faults_in_text
from dcore.semantics.core import analyze_denizen, analyze_project
from typing import Any, Iterable


SPLIT_IF = re.compile(r"\b(?:stop|determine)\s+if:\S+\s+(?:==|!=|>=|<=|>|<|\|\||&&)\s+")
SCRIPT_TITLE = re.compile(r"^([A-Za-z0-9_\-]+):\s*(?:#.*)?$")
YAML_KEY = re.compile(r"^\s*([A-Za-z0-9_ <>|*./\-]+):(?:\s|$)")
REFERENCE = re.compile(
    r"(?:\brun\s+|<proc\[|<script\[)([A-Za-z0-9_\-]+)", re.IGNORECASE
)
CONTEXT_TAG = re.compile(r"<context\.([A-Za-z0-9_]+)", re.IGNORECASE)
NAMED_ARGUMENT = re.compile(r"^([A-Za-z_][A-Za-z0-9_.-]*):")
COMMAND_TOKEN = re.compile(r"^[~^]?([A-Za-z][A-Za-z0-9_\-]*)\b")
REFLECT_TAG = re.compile(r"<invoke\[(.*?)\]([^<>]*)>", re.IGNORECASE)
EVENT_LINE = re.compile(r"^(\s*)(on|after)\s+(.+):\s*(?:#.*)?$", re.IGNORECASE)
IMPORT_LINE = re.compile(r"^\s{2,}([A-Za-z_$][\w.$]*):?\s*$")
RAW_CYRILLIC_TAG = re.compile(r"<(?!(?:\[|&|[A-Za-z_]))[А-Яа-яЁё][^>]*>")
POINTLESS_DATA_QUOTES = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_\-]*):\s*(['\"])([^\s<>]+)\2\s*(?:#.*)?$")

ALLOWED_CONTAINERS = {
    "assignment", "book", "command", "data", "economy", "entity", "format",
    "interact", "inventory", "item", "map", "procedure", "task", "world",
}
UNIVERSAL_NAMED_ARGUMENTS = {"if", "save"}
FLOW_PSEUDO_COMMANDS = {"case", "choose", "default"}
HOT_EVENTS = ("on tick", "tick", "moves", "walks", "steps on block")
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
    "ambiguous_event_matcher": "CX-DEN-018",
    "dog_navigation_owner_conflict": "CX-DEN-019",
    "dog_navigation_hot_repath": "CX-DEN-019",
    "dog_navigation_replaced_without_stop": "CX-DEN-019",
}
MUTATION_COMMANDS = {
    "adjust", "adjustblock", "animate", "create", "determine", "equip",
    "flag", "inventory", "modifyblock", "push", "remove", "spawn", "take",
    "teleport", "walk",
}

# High-signal rules distilled from the official Denizen Beginner's Guide.
# Keep this list small: the guide is teaching material and a work in progress,
# not a machine-readable grammar. Exact syntax and version claims still come
# from the selected Meta/JAR evidence.
OFFICIAL_GUIDE_SOURCE = "Denizen official Beginner's Guide"
OFFICIAL_GUIDE_URLS = {
    "procedure": "https://guide.denizenscript.com/guides/basics/procedures.html",
    "common_mistakes": "https://guide.denizenscript.com/guides/troubleshooting/common-mistakes.html",
    "ex": "https://guide.denizenscript.com/guides/first-steps/ex-command.html",
    "queue": "https://guide.denizenscript.com/guides/basics/queues.html",
}
DISPLAY_TAG = re.compile(r"\.(?:lore|display_name|custom_name)(?:[.>\]])", re.IGNORECASE)
PLAYER_NAME_TAG = re.compile(r"<player\.name(?:[.>\]])", re.IGNORECASE)
DEFINE_LIVE_OBJECT = re.compile(
    r"^define\s+(?P<name>[A-Za-z_][A-Za-z0-9_.-]*)\s+(?P<value>.+)$",
    re.IGNORECASE,
)
DEFINITION_TAG = re.compile(r"<\[(?P<name>[A-Za-z_][A-Za-z0-9_.-]*)\]", re.IGNORECASE)
LIVE_REFERENCE = re.compile(
    r"(?:<context\.(?:entity|player|location)|<player(?:[.>\]])|<npc(?:[.>\]])|<entity(?:[.>\]])|<\[(?:entity|player|location|npc)[^\]]*\])",
    re.IGNORECASE,
)


from dcore.lint.diagnostics import (
    DEFAULT_PRIORITY,
    classify,
    fixture_path_matches,
    load_fixture,
    EVENT_SWITCH_HINTS,
    INFORMATIONAL_SEMANTIC_CODES,
    LIFETIME_CODES,
    PROVIDER_LABELS,
    apply_policy,
    build_report,
    issue,
    normalize_findings,
)


def parse_addon_spec(value: str) -> tuple[str, str | None]:
    """Return a normalized addon name and optional pinned version."""
    name, separator, version = value.partition("@")
    return name.strip().lower(), version.strip() if separator and version.strip() else None


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

    @property
    def is_deprecated(self) -> bool:
        return bool(self.deprecated and self.deprecated.strip())


class MetaIndex:
    """Small in-memory index over the current dCore Meta snapshot."""

    def __init__(
        self,
        db_path: Path | None,
        profile: str,
        addons: set[str],
        *,
        target: dict[str, str] | None = None,
        jars: dict[str, Path] | None = None,
        require_jar_evidence: bool = False,
    ):
        self.available = bool(db_path and db_path.is_file())
        self.profile = profile
        parsed_addons = [parse_addon_spec(value) for value in addons]
        self.addons = {name for name, _ in parsed_addons}
        self.addon_versions = {name: version for name, version in parsed_addons if version}
        self.target = dict(target or {})
        if self.target.get("denizenm"):
            self.target["denizenm"] = normalize_product_version("DenizenM", self.target["denizenm"])
        self.jars = dict(jars or {})
        self.require_jar_evidence = require_jar_evidence
        self.unverified_provider_addons = self.addons.intersection({"megizen", "denizen_physics"})
        self.version_meta_missing: list[str] = []
        self.commands: dict[str, list[MetaEntry]] = defaultdict(list)
        self.mechanisms: dict[str, list[MetaEntry]] = defaultdict(list)
        self.command_providers: dict[str, set[str]] = defaultdict(set)
        self.mechanism_providers: dict[str, set[str]] = defaultdict(set)
        self.events: list[MetaEntry] = []
        self.event_switches: set[str] = set()
        self.effective_source_ids: set[str] = set()
        self.db_path = Path(db_path) if db_path else None
        self._tag_types: "TagTypeIndex | None" = None
        if not self.available:
            return
        products = {"Denizen-Core"}
        if profile == "denizenm":
            products.add("DenizenM")
        else:
            products.add("Denizen")
        if "reflect" in self.addons:
            products.add("denizen-reflect")
        if "voxizen" in self.addons:
            products.add("Voxizen")
        with sqlite3.connect(db_path) as db:
            db.row_factory = sqlite3.Row
            # Keep a lightweight capability index for disabled providers too.
            # The active Meta remains authoritative for syntax, while this
            # side index lets the linter say "Reflect is missing" instead of
            # misclassifying a known provider command as unknown everywhere.
            for capability in db.execute(
                "SELECT category,name,product FROM meta_preferred "
                "WHERE category IN ('command','mechanism','property')"
            ):
                product = str(capability["product"] or "").casefold()
                provider = PROVIDER_LABELS.get(product, product)
                raw_name = str(capability["name"] or "")
                if capability["category"] == "command":
                    match = re.match(r"[A-Za-z][A-Za-z0-9_\-]*", raw_name)
                    if match:
                        self.command_providers[match.group(0).casefold()].add(provider)
                else:
                    self.mechanism_providers[raw_name.rsplit(".", 1)[-1].casefold()].add(provider)
            source_ids = {"denizencore_official_master"}
            if profile == "denizenm":
                requested = self.target.get("denizenm")
                current_source, product = "denizenm_public_master", "DenizenM"
            else:
                requested = self.target.get("denizen")
                current_source, product = "denizen_official_dev", "Denizen"
            if requested:
                has_registry = db.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='version_artifacts'"
                ).fetchone()
                source_columns = {row[1] for row in db.execute("PRAGMA table_info(meta_sources)")}
                scoped = db.execute(
                    "SELECT m.source_id FROM version_artifacts v JOIN meta_sources m ON m.artifact_id=v.artifact_id "
                    "WHERE lower(v.product)=lower(?) AND lower(v.version)=lower(?) ORDER BY m.source_id",
                    (product, requested),
                ).fetchall() if has_registry and "artifact_id" in source_columns else []
                if scoped:
                    source_ids.update(row[0] for row in scoped)
                else:
                    self.version_meta_missing.append(f"{product} {requested}")
            else:
                source_ids.add(current_source)
            if "reflect" in self.addons:
                source_ids.add("denizen_reflect_public_main")
            if "voxizen" in self.addons:
                source_ids.add("voxizen_public_main")
            marks = ",".join("?" for _ in products)
            effective_source_ids, overlay = effective_sources(db, source_ids)
            # Kept so the tag type index resolves against the same sources the
            # rest of this snapshot did; a historical target must not borrow
            # current tag return types.
            self.effective_source_ids = set(effective_source_ids)
            source_marks = ",".join("?" for _ in effective_source_ids)
            rows = db.execute(
                f"SELECT entry_id,source_id,product,category,name,object_type,syntax,deprecated "
                f"FROM meta_preferred WHERE product IN ({marks}) AND source_id IN ({source_marks})",
                (*sorted(products), *sorted(effective_source_ids)),
            ).fetchall()
            rows = [row for row in rows if visible(row, overlay)]
            entry_ids = [row["entry_id"] for row in rows]
            fields_by_entry: dict[int, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
            if entry_ids:
                field_marks = ",".join("?" for _ in entry_ids)
                for field_row in db.execute(
                    f"SELECT entry_id,field_name,value FROM meta_fields "
                    f"WHERE entry_id IN ({field_marks}) ORDER BY entry_id,field_name,ordinal",
                    entry_ids,
                ):
                    fields_by_entry[field_row["entry_id"]][field_row["field_name"]].append(field_row["value"])
            for row in rows:
                fields = fields_by_entry[row["entry_id"]]
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

    def tag_types(self) -> TagTypeIndex:
        """Tag attribute/return index for this snapshot, built on first use.

        Built lazily because most lint runs never reach a tag chain worth
        walking, and the index costs an extra pass over the tag corpus.
        """
        if self._tag_types is None:
            self._tag_types = build_index(self.db_path, self.effective_source_ids or None)
        return self._tag_types

    def target_label(self) -> str:
        parts = [f"{key}={value}" for key, value in sorted(self.target.items()) if value]
        parts.extend(
            f"addon:{name}@{version}" for name, version in sorted(self.addon_versions.items())
        )
        return ", ".join(parts) or self.profile

    def command(self, name: str) -> list[MetaEntry]:
        return self.commands.get(name.lower(), [])

    def providers_for_command(self, name: str) -> set[str]:
        return set(self.command_providers.get(name.lower(), set()))

    def mechanism(self, name: str) -> list[MetaEntry]:
        return self.mechanisms.get(name.lower(), [])

    def providers_for_mechanism(self, name: str) -> set[str]:
        return set(self.mechanism_providers.get(name.lower(), set()))

    def match_event(self, matcher: str) -> list[MetaEntry]:
        return self.match_event_detailed(matcher)[1]

    def match_event_detailed(self, matcher: str) -> tuple[str, list[MetaEntry], set[str]]:
        """Match an event exactly, by base event, or not at all.

        Denizen event switches are version/provider-sensitive. A failed full
        match must not erase the fact that the base event is documented.
        """
        parts = split_arguments(matcher)
        base = " ".join(
            part for part in parts
            if not ((found := NAMED_ARGUMENT.match(part)) and found.group(1).lower() in self.event_switches)
        ).lower()
        def match_base(value: str) -> list[MetaEntry]:
            matched: list[MetaEntry] = []
            for entry in self.events:
                patterns: list[str] = []
                for field_value in entry.fields.get("events", []) + entry.fields.get("event", []):
                    patterns.extend(line.strip() for line in field_value.splitlines() if line.strip())
                if not patterns:
                    patterns = [entry.name]
                for pattern in patterns:
                    compiled = pattern_regex(pattern)
                    if compiled and compiled.match(value):
                        matched.append(entry)
                        break
            return matched

        exact = match_base(base)
        if exact:
            return "exact", exact, set()

        # Only strip known switch-shaped labels in the relaxed pass. Object
        # labels such as entity_flagged:<role> are part of the event subject,
        # not switches, and must remain in the base matcher.
        relaxed_parts: list[str] = []
        unknown_switches: set[str] = set()
        for part in parts:
            found = NAMED_ARGUMENT.match(part)
            if not found:
                relaxed_parts.append(part)
                continue
            name = found.group(1).lower()
            if name in self.event_switches or name in EVENT_SWITCH_HINTS:
                if name not in self.event_switches:
                    unknown_switches.add(name)
                continue
            relaxed_parts.append(part)
        relaxed = " ".join(relaxed_parts).lower()
        relaxed_matches = match_base(relaxed)
        if relaxed_matches:
            return "base", relaxed_matches, unknown_switches
        return "none", [], unknown_switches


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


def _balanced_reflect_expression(expression: str) -> bool:
    """Check the cheap, high-confidence structure of an Invoke expression.

    This is deliberately not a Java parser. Exact overload and type checking
    belong to the installed-JAR verifier; this gate only rejects expressions
    that are visibly incomplete before they reach Reflect.
    """
    pairs = {')': '(', ']': '[', '}': '{'}
    stack: list[str] = []
    quote: str | None = None
    escaped = False
    for char in expression.strip():
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in {"'", '"'}:
            quote = char
        elif char in "([{":
            stack.append(char)
        elif char in pairs:
            if not stack or stack.pop() != pairs[char]:
                return False
    return not stack and quote is None


def lint_reflect_usage(parsed: ParsedFile, meta: MetaIndex, commands: list[tuple[int, str]]) -> list[dict]:
    """Lint Reflect's dialect boundary without pretending to verify Java APIs."""
    results: list[dict] = []
    tag_matches = list(REFLECT_TAG.finditer(parsed.text))
    command_matches = [
        (number, content)
        for number, content in commands
        if re.match(r"^[~^]?invoke\b", content, re.IGNORECASE)
    ]
    if not tag_matches and not command_matches:
        return results

    if meta.available and "reflect" not in meta.addons:
        results.append(issue(
            "reflect_addon_not_enabled", "error", 0,
            "Reflect syntax is present but the reflect addon dialect is not enabled.",
            layer="api",
            suggestion="Run lint with --addon reflect and pin the installed denizen-reflect version.",
        ))
        return results

    malformed_lines: set[int] = set()
    for match in tag_matches:
        expression = (match.group(1) + match.group(2)).strip()
        line = parsed.text[:match.start()].count("\n") + 1
        if not expression or not _balanced_reflect_expression(expression):
            malformed_lines.add(line)
            results.append(issue(
                "reflect_expression_malformed", "error", line,
                "Reflect invoke expression is empty or structurally unbalanced.",
                layer="api", source="dCore Reflect dialect gate",
                suggestion="Keep one complete Java expression inside <invoke[...]>; exact class, method and overload still require JAR proof.",
            ))

    for number, content in command_matches:
        expression = re.sub(r"^[~^]?invoke\b", "", content, count=1, flags=re.IGNORECASE).strip()
        if not expression:
            results.append(issue(
                "reflect_command_missing_expression", "error", number,
                "Reflect invoke command has no Java expression.",
                layer="api", source="dCore Reflect dialect gate",
                suggestion="Provide one complete expression after invoke, or use a native DenizenM route.",
            ))
        elif not _balanced_reflect_expression(expression):
            results.append(issue(
                "reflect_expression_malformed", "error", number,
                "Reflect invoke command expression is structurally unbalanced.",
                layer="api", source="dCore Reflect dialect gate",
                suggestion="Fix parentheses, brackets or quotes before investigating runtime behavior.",
            ))

    results.append(issue(
        "reflect_boundary", "information", 0,
        "Reflect syntax was parsed as an addon dialect, not as an unknown core command/tag.",
        layer="api", source="denizen-reflect Meta",
        suggestion="Keep it behind one adapter and record why no native DenizenM route satisfies the same requirement.",
    ))
    return results


def lint_dog_navigation(
    parsed: ParsedFile,
    commands: list[tuple[int, str]],
    container_regions: list[tuple[str, int, int, str | None]],
) -> list[dict]:
    """Reject only unambiguous competing movement in dog/wolf scopes.

    This is intentionally narrower than a generic movement analyser. Denizen
    permits legitimate teleports, pushes and walks in unrelated mechanics; a
    dog session is the known failure-prone domain where issuing a new owner
    before stopping native navigation has a direct, actionable meaning.
    """
    results: list[dict] = []
    regions: list[tuple[int, int, str, bool]] = []
    for name, start, end, container_type in container_regions:
        if container_type != "world":
            regions.append((start, end, name, False))
    for start, end, matcher in parsed.events:
        event_name = f"on {matcher.lower()}"
        regions.append((start, end, matcher, any(hot in event_name for hot in HOT_EVENTS)))

    for start, end, label, hot_event in regions:
        scope_lines = "\n".join(parsed.lines[start - 1:end]).lower()
        if not any(marker in scope_lines for marker in ("wolf", "dog", "собак")):
            continue
        scope_commands = [(number, content) for number, content in commands if start < number <= end]
        navigation_active = False
        for number, content in scope_commands:
            token = COMMAND_TOKEN.match(content)
            if not token:
                continue
            command = token.group(1).lower()
            lowered = content.lower()
            if command == "walk":
                if re.search(r"\bwalk\s+.+\s+stop(?:\s|$)", lowered):
                    navigation_active = False
                    continue
                if hot_event:
                    results.append(issue(
                        "dog_navigation_hot_repath", "error", number,
                        "A dog/wolf high-frequency event starts native walk; this replaces the path every tick/move.",
                        layer="performance", source="dCore dog navigation gate",
                        suggestion="Replan from a bounded session task only after timeout, insufficient progress or target invalidation.",
                    ))
                if navigation_active:
                    results.append(issue(
                        "dog_navigation_replaced_without_stop", "warning", number,
                        "A dog/wolf scope starts another native walk before stopping the prior navigation owner.",
                        layer="lifecycle", source="dCore dog navigation gate",
                        suggestion="Issue `walk <entity> stop` before replacing a waypoint, then record the new phase/target.",
                    ))
                navigation_active = True
                continue
            if command in {"push", "teleport"} and navigation_active:
                results.append(issue(
                    "dog_navigation_owner_conflict", "error", number,
                    f"Dog/wolf native walk is still active when `{command}` takes movement ownership.",
                    layer="lifecycle", source="dCore dog navigation gate",
                    suggestion="Stop native walk before the impulse/correction; restore navigation only in the next explicit phase.",
                ))
                navigation_active = False
    return results


def lint_generated_architecture_risk(
    parsed: ParsedFile,
    commands: list[tuple[int, str]],
    container_regions: list[tuple[str, int, int, str | None]],
) -> list[dict]:
    """Detect unchecked generated expansion from observable structural signals.

    This deliberately does not identify authorship.  The finding means that the
    artifact has the measurable shape of code that grew by accumulating prompts,
    patches, and wrappers without a bounded ownership model.
    """
    command_tokens = [COMMAND_TOKEN.match(content).group(1).lower() for _, content in commands if COMMAND_TOKEN.match(content)]
    executable_count = len(commands)
    event_count = len(parsed.events)
    container_count = len(container_regions)
    run_count = sum(token in {"run", "inject"} for token in command_tokens)
    loop_count = sum(token in {"while", "foreach", "repeat"} for token in command_tokens)
    server_state_writes = sum(
        bool(re.match(r"flag\s+server(?:\s|$)", content, re.IGNORECASE))
        for _, content in commands
    )

    signals: list[str] = []
    if container_count >= 24:
        signals.append(f"{container_count} containers")
    if executable_count >= 500:
        signals.append(f"{executable_count} executable commands")
    if event_count >= 15:
        signals.append(f"{event_count} event entry points")
    if run_count >= 60:
        signals.append(f"{run_count} queue handoffs")
    if loop_count >= 20:
        signals.append(f"{loop_count} loop constructs")
    if server_state_writes >= 50:
        signals.append(f"{server_state_writes} server-state writes")

    # Four independent signals are required.  Size alone must never label a
    # script as generated or bad: a large but well-owned system is allowed.
    if len(signals) < 4:
        return []

    line = min((start for _, start, _, _ in container_regions), default=1)
    finding = issue(
        "generated_architecture_risk",
        "warning",
        line,
        "The script matches an unchecked generated-expansion profile: "
        + ", ".join(signals)
        + ". This is a structural risk, not an authorship claim.",
        layer="architecture",
        source="dCore anti-vibe structural model",
        suggestion=(
            "Stop adding local patches. Define one session/state owner, explicit phases, "
            "bounded hot-path work, provider adapters, idempotent cleanup, and a proof "
            "fixture before extending the feature."
        ),
    )
    finding.update({
        "priority": "P1",
        "confidence": "high_structural",
        "evidence": {
            "containers": container_count,
            "executable_commands": executable_count,
            "event_entry_points": event_count,
            "run_or_inject_calls": run_count,
            "loop_constructs": loop_count,
            "server_state_writes": server_state_writes,
        },
        "estimated_cost": (
            f"per-event and per-queue cost is unresolved; observed {loop_count} loops "
            f"and {run_count} queue handoffs"
        ),
    })
    return [finding]


def classify_loop_bound(loop_content: str, body: str) -> tuple[str, str]:
    """Classify the bound visible to static analysis without guessing runtime size."""
    text = f"{loop_content}\n{body}".casefold()
    if "while true" in text:
        return "unbounded", "while true requires an explicit lifetime owner"
    repeat = re.search(r"\brepeat\s+(\d+)\b", text)
    if repeat:
        return "bounded_by_constant", f"repeat count {repeat.group(1)}"
    literal = re.search(r"\bforeach\s+(?:<)?list\[([^\]]*)\]", text)
    if literal:
        count = 0 if not literal.group(1).strip() else len(literal.group(1).split("|"))
        return "bounded_by_constant", f"literal list size {count}"
    if re.search(r"\b(?:limit|max|maximum|count):\s*\d+", text):
        return "bounded_by_constant", "explicit numeric limit"
    if re.search(r"find_entities|\.entities|server\.players|server\.worlds|context\.", text):
        return "input_bounded", "bound depends on a runtime collection"
    return "runtime_adapter", "bound depends on a runtime adapter or unresolved tag"


def lint_runtime_risks(
    parsed: ParsedFile,
    commands: list[tuple[int, str]],
    container_regions: list[tuple[str, int, int, str | None]],
) -> list[dict]:
    """Report high-signal ownership and workload risks.

    These checks intentionally describe observable execution structure. They do
    not infer author, framework quality, or actual TPS without runtime proof.
    """
    results: list[dict] = []

    def indent(number: int) -> int:
        raw = parsed.lines[number - 1]
        return len(raw) - len(raw.lstrip(" "))

    def owner(number: int) -> str:
        for name, start, end, _ in container_regions:
            if start < number <= end:
                return name
        return "<unknown>"

    def region_commands(start: int, end: int) -> list[tuple[int, str]]:
        return [(number, content) for number, content in commands if start < number <= end]

    def loop_body(loop_number: int) -> list[tuple[int, str]]:
        loop_indent = indent(loop_number)
        body: list[tuple[int, str]] = []
        for number, content in commands:
            if number <= loop_number:
                continue
            if indent(number) <= loop_indent:
                if body:
                    break
                continue
            body.append((number, content))
        return body

    # One server state key should have one authoritative writer. Dynamic
    # children such as records.<id> are normalized to their stable root.
    writers: defaultdict[str, defaultdict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    ignored_state_roots = {"cooldown", "guard", "history", "lock", "pending", "ratelimit"}
    for number, content in commands:
        match = re.match(r"flag\s+server\s+([^:\s]+)", content, re.IGNORECASE)
        if not match:
            continue
        root = re.split(r"[.\[]", match.group(1), maxsplit=1)[0].casefold()
        if root in ignored_state_roots or root.endswith(("_cooldown", "_guard", "_lock", "_pending")):
            continue
        writers[root][owner(number)].append(number)
    for root, by_owner in sorted(writers.items()):
        if len(by_owner) < 2:
            continue
        lines = [line for values in by_owner.values() for line in values]
        owner_names = sorted(by_owner)
        if len(owner_names) == 2 and not any(
            token in root for token in ("record", "session", "index", "claim", "location", "target", "state")
        ):
            continue
        finding = issue(
            "shared_state_multi_writer",
            "warning",
            min(lines),
            f"Server state root '{root}' is written by {len(owner_names)} containers: {', '.join(owner_names)}.",
            layer="lifecycle",
            source="dCore state-ownership model",
            suggestion="Choose one authoritative state writer; other containers may request a transition or hold only a narrow lookup reference.",
        )
        finding.update({
            "priority": "P1",
            "confidence": "high_structural",
            "evidence": {"state_root": root, "writers": owner_names, "write_lines": sorted(lines)},
        })
        results.append(finding)

    families = {
        "persistence": re.compile(r"flag\s+server|server\.flag|yaml|save", re.I),
        "provider": re.compile(r"invoke\[|modelengine|mechanism", re.I),
        "inventory": re.compile(r"inventory|open_inventory|item_on_cursor|context\.clicked", re.I),
        "movement": re.compile(r"teleport|walk\b|push\b|velocity|location", re.I),
        "feedback": re.compile(r"narrate|actionbar|playsound|playeffect|debug", re.I),
        "lifecycle": re.compile(r"cleanup|release|destroy|remove|finish|reset|expire", re.I),
        "control": re.compile(r"\b(?:if|else if|choose|case|while|foreach|repeat)\b", re.I),
    }
    scans = re.compile(r"find_entities|find\.blocks|server\.worlds\.parse\[entities\]|\.entities|location\.find_", re.I)

    for name, start, end, container_type in container_regions:
        region = region_commands(start, end)
        if not region:
            continue
        body = "\n".join(content for _, content in region)
        lower = body.casefold()
        tokens = [match.group(1).casefold() for _, content in region if (match := COMMAND_TOKEN.match(content))]
        loop_lines = [
            (number, content)
            for number, content in region
            if content.casefold().startswith(("while ", "foreach ", "repeat "))
            and not content.casefold().startswith("while stop")
            and not content.casefold().startswith("foreach next")
        ]

        # A loop that emits queues per item is a multiplicative workload. One
        # ordinary foreach + one call is allowed; repeated calls or a 1-tick
        # permanent runner require an explicit fan-out budget.
        best_loop: tuple[int, int] | None = None
        for loop_number, loop_content in loop_lines:
            calls = sum(
                COMMAND_TOKEN.match(content).group(1).casefold() in {"run", "inject"}
                for _, content in loop_body(loop_number)
                if COMMAND_TOKEN.match(content)
            )
            if calls and (best_loop is None or calls > best_loop[1]):
                best_loop = (loop_number, calls)
        if best_loop and (best_loop[1] >= 2 or ("while true" in lower and "wait 1t" in lower)):
            loop_number, calls = best_loop
            loop_content = next(content for number, content in loop_lines if number == loop_number)
            loop_body_text = "\n".join(content for _, content in loop_body(loop_number))
            bound_class, bound_reason = classify_loop_bound(loop_content, loop_body_text)
            severity = "suggestion" if bound_class == "bounded_by_constant" and calls <= 2 else "warning"
            finding = issue(
                "queue_fanout",
                severity,
                loop_number,
                f"Loop emits {calls} queue handoff(s) per iteration in '{name}'.",
                layer="performance",
                source="dCore queue fan-out model",
                suggestion="Bound the input, record a per-session ticket, and prove the maximum concurrent queues before adding another handoff.",
            )
            finding.update({
                "priority": "P2" if severity == "suggestion" else "P1",
                "confidence": "bounded_static" if severity == "suggestion" else "high_structural",
                "evidence": {"container": name, "loop_line": loop_number, "handoffs_per_iteration": calls, "bound_class": bound_class, "bound_reason": bound_reason},
                "estimated_cost": f"O(iterations × {calls} queue handoffs)",
            })
            results.append(finding)

        # A tick-like handler or 1-tick scheduler that scans a dynamic world or
        # active list has a measurable multiplicative cost.
        matching_events = [matcher for event_start, event_end, matcher in parsed.events if start < event_start <= end]
        hot_event = any(any(hot in matcher.casefold() for hot in HOT_EVENTS) for matcher in matching_events)
        scheduler = "while true" in lower and "wait 1t" in lower
        if loop_lines and (hot_event or scheduler) and scans.search(body) or (
            loop_lines and (hot_event or scheduler) and "server.flag[" in lower and ("run " in lower or "flag " in lower)
        ):
            loops = len(loop_lines)
            finding = issue(
                "hot_path_cost",
                "warning",
                start,
                f"Hot-path container '{name}' combines {loops} loop(s) with dynamic collection/entity work.",
                layer="performance",
                source="dCore hot-path cost model",
                suggestion="Replace broad scans with an active-session index, bound candidate work, and record the per-tick budget.",
            )
            finding.update({
                "priority": "P1",
                "confidence": "high_structural",
                "evidence": {"container": name, "loops": loops, "dynamic_scan": bool(scans.search(body)), "scheduler": scheduler},
                "estimated_cost": "O(active sessions × candidates per tick) until a finite bound is supplied",
            })
            results.append(finding)

        # A persistent runner is not automatically wrong, but it must expose a
        # cadence, singleton guard, workload ceiling and shutdown owner.
        while_lines = [(number, content) for number, content in region if content.casefold().startswith("while true")]
        for while_number, _ in while_lines:
            body_lines = loop_body(while_number)
            body_text = "\n".join(content for _, content in body_lines).casefold()
            if not re.search(r"\bwait\s+(?:[01](?:\.\d+)?t|1t)\b", body_text) or not any(
                token in body_text for token in ("foreach ", "run ", "flag ", "teleport ", "find_")
            ):
                continue
            singleton_guard = "has_flag" in body_text and "active" in body_text
            severity = "suggestion" if singleton_guard else "warning"
            finding = issue(
                "persistent_scheduler_without_budget",
                severity,
                while_number,
                f"Persistent 1-tick scheduler in '{name}' has no explicit workload/shutdown contract.",
                layer="lifecycle",
                source="dCore scheduler contract model",
                suggestion="Declare singleton ownership, maximum work per tick, stale-session cleanup, and a reload/shutdown path.",
            )
            finding.update({
                "priority": "P1" if severity == "warning" else "P2",
                "confidence": "high_structural" if severity == "warning" else "bounded_but_uncontracted",
                "evidence": {"container": name, "singleton_guard_detected": singleton_guard, "cadence": "1t"},
            })
            results.append(finding)

        # Resource/state acquisition without an observable release owner is a
        # lifecycle gap. The rule is deliberately narrow: it requires a
        # lifecycle-shaped container and at least two acquisition signals.
        lifecycle_name = re.search(r"(?:session|queue|target|register|open|spawn|create|hold|visual)", name, re.I)
        acquisition_signals = sum(bool(pattern.search(body)) for pattern in (
            re.compile(r"\bspawn\b|\bcreate\b", re.I),
            re.compile(r"inventory\s+open|open_inventory", re.I),
            re.compile(r"flag\s+server\s+\S*(?:session|record|active|target)", re.I),
        ))
        cleanup_signal = re.search(
            r"(?:cleanup|release|destroy|remove|finish|reset|expire|queue\s+<[^>]+>\s+stop)",
            body,
            re.I,
        )
        cleanup_call = re.search(
            r"(?:run|inject)\s+\S*(?:cleanup|release|destroy|finish|reset|remove|expire)",
            body,
            re.I,
        )
        if (
            container_type in {"task", "procedure"}
            and lifecycle_name
            and acquisition_signals >= 2
            and not cleanup_signal
            and not cleanup_call
        ):
            finding = issue(
                "cleanup_owner_gap",
                "warning",
                start,
                f"Lifecycle container '{name}' acquires state/resources but exposes no cleanup owner.",
                layer="lifecycle",
                source="dCore cleanup-ownership model",
                suggestion="Add one idempotent cleanup owner and route success, failure, quit, reload and timeout exits through it.",
            )
            finding.update({
                "priority": "P1",
                "confidence": "medium_structural",
                "evidence": {"container": name, "acquisition_signals": acquisition_signals, "cleanup_owner_found": False},
            })
            results.append(finding)

        # Mixing four or more domains in one executable container is a phase
        # boundary problem, not a line-count problem.
        present = sorted(family for family, pattern in families.items() if pattern.search(body))
        if len(region) >= 40 and len(present) >= 4:
            finding = issue(
                "phase_mixed_container",
                "warning",
                start,
                f"Container '{name}' mixes {len(present)} responsibility families: {', '.join(present)}.",
                layer="architecture",
                source="dCore phase/ownership model",
                suggestion="Split only at stable phase or provider boundaries; keep one orchestrator and one cleanup owner.",
            )
            finding.update({
                "priority": "P1",
                "confidence": "high_structural",
                "evidence": {"container": name, "families": present, "commands": len(region)},
            })
            results.append(finding)

    # Project-level ownership graph: acquisition is not ownership. A feature
    # with session/resource roots must expose a lifecycle exit that can release it.
    all_body = "\n".join(content for _, content in commands)
    acquisition_tokens = sorted(set(re.findall(
        r"\b(?:spawn|create|open_inventory|inventory\s+open|flag\s+server\s+\S*(?:session|record|active|target)|run\s+\S*(?:session|register|open))",
        all_body,
        re.IGNORECASE,
    )))
    cleanup_tokens = sorted(set(re.findall(
        r"\b(?:cleanup|release|destroy|remove|finish|reset|expire|quit|death|reload)\b",
        all_body,
        re.IGNORECASE,
    )))
    lifecycle_events = [
        matcher for _, _, matcher in parsed.events
        if re.search(r"quit|death|reload|unload|shutdown", matcher, re.IGNORECASE)
    ]
    if len(acquisition_tokens) >= 2 and not cleanup_tokens and not lifecycle_events:
        root = min((start for _, start, _, _ in container_regions), default=1)
        results.append(issue(
            "ownership_graph_gap",
            "error",
            root,
            "The file acquires session/resource state but no cleanup owner or lifecycle exit is visible.",
            layer="lifecycle",
            source="dCore ownership/lifetime graph",
            suggestion="Declare one owner, make cleanup idempotent, and route quit, death, reload, timeout and failure through it.",
            priority="P0",
            confidence="ownership_unresolved",
            evidence={"acquisitions": acquisition_tokens, "cleanup_tokens": cleanup_tokens, "lifecycle_events": lifecycle_events},
            provenance="project-level acquisition-to-release graph",
        ))

    return results


def lint_official_semantics(
    parsed: ParsedFile,
    meta: MetaIndex,
    commands: list[tuple[int, str]],
    container_regions: list[tuple[str, int, int, str | None]],
) -> list[dict]:
    """Apply only high-confidence semantics extracted from the official guide.

    These are deliberately conservative. The guide explains intent and common
    failure modes, while Meta/JAR evidence remains authoritative for syntax.
    """
    results: list[dict] = []

    # A procedure is a value-producing container. A procedure that never
    # determines a value is almost always a task accidentally declared as one.
    for name, start, end, container_type in container_regions:
        if container_type != "procedure":
            continue
        local = [(line, content) for line, content in commands if start < line <= end]
        if not any(re.match(r"^determine(?:\s|$)", content, re.IGNORECASE) for _, content in local):
            results.append(issue(
                "procedure_missing_determine", "error", start,
                f"Procedure '{name}' never determines a return value.",
                layer="semantics", source=OFFICIAL_GUIDE_SOURCE,
                suggestion="Use `determine <value>` on every reachable return path, or change the container to a task.",
                priority="P1", confidence="high",
                provenance=OFFICIAL_GUIDE_URLS["procedure"],
            ))

    # Display values are presentation, not authoritative state. Only inspect
    # data/control commands, so a normal `narrate <item.lore>` stays clean.
    data_commands = {"choose", "define", "determine", "flag", "foreach", "if", "run", "while"}
    for number, content in commands:
        token = COMMAND_TOKEN.match(content)
        if not token:
            continue
        command = token.group(1).lower()
        if command in data_commands and DISPLAY_TAG.search(content):
            results.append(issue(
                "display_value_used_as_data", "warning", number,
                "Display text (lore/name) is being used in control or state logic.",
                layer="semantics", source=OFFICIAL_GUIDE_SOURCE,
                suggestion="Store the real item state in a flag/script item/vanilla attribute and derive lore or name from it.",
                priority="P1", confidence="high",
                provenance=OFFICIAL_GUIDE_URLS["common_mistakes"],
            ))

        # `/ex` is a privileged interactive test tool, not a production
        # dispatch mechanism. Catch only an explicit ex payload.
        if command == "execute" and re.search(r"(?:^|[\s\"'])/?ex(?:\s|$)", content, re.IGNORECASE):
            results.append(issue(
                "ex_command_in_production", "error", number,
                "Production script dispatches `/ex`, a privileged interactive test command.",
                layer="safety", source=OFFICIAL_GUIDE_SOURCE,
                suggestion="Remove `/ex` from the script; test it manually with a trusted operator and call the real Denizen command directly in production.",
                priority="P0", confidence="high",
                provenance=OFFICIAL_GUIDE_URLS["ex"],
            ))

        # Prefer a native command only when the selected Meta proves that the
        # quoted console command exists. Otherwise leave this at the evidence
        # boundary instead of guessing and producing lint noise.
        if command == "execute" and meta.available:
            native = re.search(
                r"\b(?:as_server|as_console|as_op)\s+[\"']([A-Za-z][A-Za-z0-9_-]*)",
                content, re.IGNORECASE,
            )
            if native and meta.command(native.group(1).lower()):
                results.append(issue(
                    "execute_native_command", "suggestion", number,
                    f"Console dispatch wraps native Denizen command '{native.group(1)}'.",
                    layer="semantics", source=OFFICIAL_GUIDE_SOURCE,
                    suggestion=f"Call `{native.group(1).lower()}` directly so Meta, arguments and target semantics remain lintable.",
                    priority="P2", confidence="selected_meta_match",
                    provenance=OFFICIAL_GUIDE_URLS["common_mistakes"],
                ))

        # A server-wide flag keyed by player.name is not a stable identity.
        # Limit this to persistent/global state; names in narration or display
        # text are legitimate.
        if command == "flag" and re.search(r"^flag\s+(?:server|global|world)\b", content, re.IGNORECASE) and PLAYER_NAME_TAG.search(content):
            results.append(issue(
                "player_name_used_as_identity", "warning", number,
                "Persistent state is keyed by player.name.",
                layer="lifecycle", source=OFFICIAL_GUIDE_SOURCE,
                suggestion="Key state by the player object/UUID or a session token; names can change and are not identity storage.",
                priority="P1", confidence="high",
                provenance=OFFICIAL_GUIDE_URLS["common_mistakes"],
            ))

    # Values captured from live context before a wait must be re-resolved or
    # validated after the queue yields. Track only explicit queue definitions,
    # not every direct player/entity tag, to avoid false positives.
    for name, start, end, _ in container_regions:
        local = [(line, content) for line, content in commands if start < line <= end]
        captured: dict[str, int] = {}
        wait_line: int | None = None
        reported: set[tuple[str, int]] = set()
        for number, content in local:
            defined = DEFINE_LIVE_OBJECT.match(content)
            if defined:
                key = defined.group("name").casefold()
                if LIVE_REFERENCE.search(defined.group("value")):
                    captured[key] = number
                else:
                    captured.pop(key, None)
            token = COMMAND_TOKEN.match(content)
            command = token.group(1).lower() if token else ""
            if command == "wait":
                wait_line = number
                continue
            if wait_line is None:
                continue
            for reference in DEFINITION_TAG.finditer(content):
                key = reference.group("name").casefold()
                if key not in captured or captured[key] >= wait_line or (key, wait_line) in reported:
                    continue
                reported.add((key, wait_line))
                results.append(issue(
                    "stale_live_reference_after_wait", "warning", number,
                    f"Queue uses live object definition '<[{key}]>' after wait {wait_line} without revalidation.",
                    layer="lifecycle", source=OFFICIAL_GUIDE_SOURCE,
                    suggestion="Re-resolve the player/entity/location after the wait and verify existence, ownership and session state before mutation.",
                    priority="P1", confidence="high",
                    evidence={"definition": key, "captured_line": captured[key], "wait_line": wait_line},
                    provenance=OFFICIAL_GUIDE_URLS["queue"],
                ))

    return results


def lint_tag_types(parsed: ParsedFile, meta: MetaIndex) -> list[dict]:
    """Reject tag chains whose attribute does not exist on the incoming type.

    Meta records a return type for every tag and a base type for every object
    type, so `<player.name.lore>` is provably wrong: `name` returns ElementTag
    and ElementTag has no `lore`. Only chains the snapshot fully describes are
    reported; see dcore.lint.tagtypes for the fail-open boundaries.
    """
    index = meta.tag_types()
    if not index.available():
        return []
    results: list[dict] = []
    for number, raw in enumerate(parsed.lines, 1):
        line = strip_comment(raw)
        if "<" not in line:
            continue
        for step in deprecations_in_text(index, line):
            results.append(issue(
                "deprecated_tag", "warning", number,
                f"<{step.chain}> uses deprecated {step.owner_type}.{step.segment}: {step.notice}",
                layer="api", source="dCore tag type index",
                confidence="selected_meta_deprecation",
                evidence={"chain": step.chain, "segment": step.segment, "type": step.owner_type},
                suggestion="Migrate to the replacement named in the deprecation notice before it is removed.",
                priority="P2",
                provenance=f"tag deprecations for {meta.target_label()}",
            ))
        for fault in faults_in_text(index, line):
            results.append(issue(
                "tag_attribute_not_on_type", "error", number,
                f"'{fault.segment}' is not an attribute of {fault.owner_type} in <{fault.chain}>.",
                layer="api", source="dCore tag type index",
                confidence="meta_return_type_chain",
                evidence={"chain": fault.chain, "segment": fault.segment, "type": fault.owner_type},
                suggestion=(
                    f"Check what {fault.owner_type} actually returns, or add an explicit fallback "
                    "if the chain is intentionally allowed to fail."
                ),
                provenance=f"tag return types for {meta.target_label()}",
            ))
    return results


def lint_parsed(parsed: ParsedFile, meta: MetaIndex) -> list[dict]:
    results: list[dict] = []
    results.extend(lint_tag_types(parsed, meta))
    if meta.unverified_provider_addons:
        names = ", ".join(sorted(meta.unverified_provider_addons))
        results.append(issue(
            "provider_meta_pending", "information", 0,
            f"Provider addon Meta is not indexed for: {names}.",
            layer="api", source="dCore addon policy",
            suggestion="Keep calls behind one adapter and verify the exact jar/docs/runtime before treating them as valid.",
        ))
    if meta.version_meta_missing:
        results.append(issue(
            "version_meta_unindexed", "error", 0,
            f"No historical Meta snapshot is indexed for: {', '.join(meta.version_meta_missing)}.",
            layer="evidence", source="dCore multiversion Meta",
            suggestion="Import the exact source artifact or remove the version pin; do not lint this target against current Meta.",
        ))
    if meta.require_jar_evidence:
        missing = [name for name in sorted(meta.addons) if name not in meta.jars]
        if missing:
            results.append(issue(
                "jar_evidence_missing", "error", 0,
                f"Exact JAR evidence is required but missing for: {', '.join(missing)}.",
                layer="evidence", source="dCore target gate",
                suggestion="Pass --jar addon=path for every version-sensitive addon in the target.",
            ))
        invalid = [name for name, path in sorted(meta.jars.items()) if not path.is_file()]
        if invalid:
            results.append(issue(
                "jar_path_missing", "error", 0,
                f"Declared JAR path does not exist for: {', '.join(invalid)}.",
                layer="evidence", source="dCore target gate",
                suggestion="Point --jar to the installed artifact or remove --require-jar-evidence.",
            ))
    if meta.target:
        results.append(issue(
            "target_context", "information", 0,
            f"Lint target: {meta.target_label()}.",
            layer="evidence", source="dCore target resolver",
            suggestion="Version-sensitive findings are valid only for this declared target.",
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
        if RAW_CYRILLIC_TAG.search(stripped):
            results.append(issue(
                "raw_cyrillic_tag", "error", number,
                "A raw `<...>` tag starts with Cyrillic text and will be parsed as an invalid tag base.",
                layer="ide", source="Refined diagnostic parity",
                suggestion="Use `<[definition]>` for a definition, `<player.name>` for an object tag, or write literal text without angle brackets.",
            ))
        if stripped.count('"') % 2 or stripped.count("'") % 2:
            results.append(issue("missing_quotes", "warning", number, "Uneven quotes."))
        data_quotes = POINTLESS_DATA_QUOTES.match(raw)
        if data_quotes and not raw.lstrip().startswith("-"):
            path = {part.lower() for part in parsed.paths[number - 1]}
            if not {"script", "events"}.intersection(path) and data_quotes.group(1).lower() != "type":
                results.append(issue(
                    "pointless_data_quotes", "information", number,
                    "A plain data value is quoted although it contains no whitespace or tag syntax.",
                    layer="ide", source="Refined diagnostic parity",
                    suggestion="Remove the quotes, unless another consumer explicitly requires a string literal.",
                ))
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

    results.extend(lint_generated_architecture_risk(parsed, commands, container_regions))
    results.extend(lint_runtime_risks(parsed, commands, container_regions))
    results.extend(lint_official_semantics(parsed, meta, commands, container_regions))

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
            providers = meta.providers_for_command(name)
            if providers:
                enabled = set(meta.addons) | {meta.profile, "core"}
                missing = sorted(provider for provider in providers if provider not in enabled)
                results.append(issue(
                    "addon_required" if missing else "version_api_unverified",
                    "error" if missing else "warning",
                    number,
                    f"Command '{name}' is known to provider(s) {', '.join(sorted(providers))}, "
                    f"but is absent from the selected {meta.profile} + addon Meta.",
                    layer="api",
                    source="dCore capability resolver",
                    suggestion=(
                        f"Enable and version-pin addon(s): {', '.join(missing)}."
                        if missing else
                        "Resolve the exact target snapshot before treating this command as invalid."
                    ),
                    priority="P1" if missing else "P2",
                    confidence="known_provider_disabled" if missing else "known_capability_version_gap",
                    evidence={"command": name, "known_providers": sorted(providers), "enabled": sorted(enabled)},
                    provenance="indexed Meta capability registry",
                ))
            else:
                results.append(issue(
                    "unknown_command", "error", number,
                    f"Command '{name}' is absent from the selected {meta.profile} + addon Meta and the indexed provider registry.",
                    layer="api",
                    source="dcore.sqlite Meta",
                    suggestion="Resolve the exact installed dialect or enable the required addon; do not replace it with a console workaround automatically.",
                    priority="P0",
                    confidence="unknown_everywhere",
                    provenance="selected Meta + indexed capability registry",
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
                if mechanism and meta.available:
                    entries = meta.mechanism(mechanism.group(1))
                    if not entries:
                        results.append(issue(
                            "unknown_mechanism", "error", number,
                            f"Mechanism '{mechanism.group(1)}' is absent from the selected Meta.",
                            layer="api",
                            source="dcore.sqlite Meta",
                        ))
                    else:
                        deprecated = next((entry for entry in entries if entry.is_deprecated), None)
                        if deprecated:
                            results.append(issue(
                                "deprecated_mechanism", "warning", number,
                                f"Mechanism '{mechanism.group(1)}' is deprecated: {deprecated.deprecated.strip()}",
                                layer="api", source="dcore.sqlite Meta",
                                suggestion="Migrate to the mechanism/approach named in the deprecation notice before it is removed.",
                                priority="P2", confidence="selected_meta_match",
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
        match_state, matched, relaxed_switches = (
            meta.match_event_detailed(matcher) if meta.available else ("none", [], set())
        )
        if meta.available and not matched:
            results.append(issue(
                "unknown_event", "warning", start,
                f"Event matcher '{matcher}' was not matched by the selected Meta.",
                layer="api",
                source="dcore.sqlite Meta",
                suggestion="Treat this as a proof boundary: check exact matcher and addon/fork switches before delivery.",
                priority="P1",
                confidence="event_not_matched",
                provenance="selected event Meta",
            ))
        elif meta.available and match_state == "base" and relaxed_switches:
            results.append(issue(
                "event_switch_unverified", "warning", start,
                f"Base event is documented, but switch(es) {', '.join(sorted(relaxed_switches))} are not confirmed by the selected Meta.",
                layer="api",
                source="dCore event capability resolver",
                suggestion="Verify each switch against the exact Denizen/DenizenM build; do not treat base-event matching as full syntax proof.",
                priority="P1",
                confidence="base_event_switch_gap",
                evidence={"matcher": matcher, "switches": sorted(relaxed_switches)},
                provenance="exact/base event matcher comparison",
            ))
        _, supplied_switches = remove_event_switches(matcher)
        matched_names = {entry.name.casefold() for entry in matched}
        damage_collision = (
            len(matched_names) > 1
            and re.search(r"\bdamages?\b|\bdamaged\b", matcher, re.I)
            and any("<vehicle>" in name for name in matched_names)
            and any("<entity>" in name for name in matched_names)
        )
        if damage_collision and "type" not in supplied_switches:
            results.append(issue(
                "ambiguous_event_matcher", "warning", start,
                f"Event matcher '{matcher}' overlaps entity and vehicle damage ScriptEvents.",
                layer="api", source="DenizenM event Meta",
                suggestion="Add the documented `type:<entity matcher>` switch, such as `type:slime`, and verify the exact installed build.",
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

    results.extend(lint_dog_navigation(parsed, commands, container_regions))

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

    results.extend(lint_reflect_usage(parsed, meta, commands))
    return results


def lint_semantic_core(text: str, known_scripts: Iterable[str] = ()) -> list[dict]:
    """Emit portable Denizen-Core queue/tag diagnostics for one source text."""
    # The source-derived queue core supplements, rather than replaces, Meta
    # validation. It knows only portable Denizen semantics and never claims a
    # Bukkit command or addon was executed.
    semantic = analyze_denizen(text, known_script_names=known_scripts)
    return semantic_issues(semantic)


def semantic_issues(semantic: object, source_path: str = "", fixture: dict | None = None) -> list[dict]:
    """Convert a DenizenCore-lite result to stable dCore lint rows."""
    findings = [
        issue(
            diagnostic.code,
            diagnostic.severity,
            diagnostic.line,
            diagnostic.message,
            layer="denizencore_lite",
            source="DenizenCore-lite queue/tag semantic port",
            suggestion=diagnostic.suggestion,
        )
        for diagnostic in semantic.diagnostics
    ]
    for finding in findings:
        if source_path:
            finding["file"] = source_path
    return apply_policy(findings, fixture=fixture)


def lint_text(text: str, meta: MetaIndex | None = None) -> list[dict]:
    """Compatibility API used by tests and external callers."""
    if meta is None:
        meta = MetaIndex(None, "denizenm", set())
    results = lint_parsed(parse_file(text), meta)
    results.extend(lint_semantic_core(text))
    return normalize_findings(results)


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


def expand_input_paths(paths: Iterable[Path]) -> list[Path]:
    """Expand project directories into a stable, duplicate-free .dsc file set."""
    expanded: list[Path] = []
    seen: set[Path] = set()
    for supplied in paths:
        if not supplied.exists():
            raise ValueError(f"input path does not exist: {supplied}")
        candidates = sorted(supplied.rglob("*")) if supplied.is_dir() else [supplied]
        for candidate in candidates:
            if not candidate.is_file() or candidate.suffix.casefold() != ".dsc":
                continue
            resolved = candidate.resolve()
            if resolved not in seen:
                seen.add(resolved)
                expanded.append(candidate)
    if not expanded:
        raise ValueError("no .dsc files found in the supplied paths")
    return expanded


def _table_cell(value: object, width: int) -> str:
    text = " ".join(str(value).replace("|", "\\|").split())
    return textwrap.shorten(text, width=width, placeholder="...") if len(text) > width else text


def render_table(results: list[dict], *, show_information: bool = False) -> str:
    visible = [
        result for result in results
        if show_information or result["severity"] != "information"
    ]
    rows = ["| Sev | Priority | Code | Location | Problem | Fix |", "|---|---|---|---|---|---|"]
    for result in visible:
        location = Path(result["file"]).name
        if result["line"]:
            location += f":{result['line']}"
        rows.append(
            "| {sev} | {priority} | `{code}` | `{location}` | {problem} | {fix} |".format(
                sev=result["severity"].upper(),
                priority=result.get("priority", "P2"),
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
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="DenizenM-aware structural, API and lifecycle lint")
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--json", action="store_true", help="Emit machine JSON instead of the human table")
    parser.add_argument("--format", choices=("table", "json"), default="table")
    parser.add_argument("--show-information", action="store_true", help="Include provenance-only rows in table output")
    parser.add_argument("--contract", type=Path, help="JSON behavior witness manifest")
    parser.add_argument("--decision", type=Path, help="JSON result emitted by dcore_design compare")
    parser.add_argument("--db", type=Path, default=default_db())
    parser.add_argument("--profile", default="denizenm", help="Meta dialect, such as denizenm or official")
    parser.add_argument("--minecraft", help="Target Minecraft version")
    parser.add_argument("--paper", help="Target Paper version/build")
    parser.add_argument("--java", help="Target Java version")
    parser.add_argument("--denizen-version", help="Target Denizen/DenizenCore version")
    parser.add_argument("--denizenm", help="Target DenizenM build")
    parser.add_argument("--addon", action="append", default=[], help="Addon name or name@version; repeatable")
    parser.add_argument("--jar", action="append", default=[], help="Exact artifact as name=path; repeatable")
    parser.add_argument("--require-jar-evidence", action="store_true", help="Fail when a declared addon has no exact JAR path")
    parser.add_argument("--target-name", help="Human label for the selected target")
    parser.add_argument("--external-script", action="append", default=[], help="Known project script intentionally outside this partial lint artifact")
    parser.add_argument("--closed-world", action="store_true", help="unresolved script references are errors")
    parser.add_argument("--strict-warnings", action="store_true")
    parser.add_argument("--fixture", type=Path, help="JSON queue fixture for explicit event/context inputs")
    parser.add_argument("--queue-report", type=Path, help="Write the compact semantic queue report JSON")
    args = parser.parse_args()

    try:
        fixture = load_fixture(args.fixture)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        parser.error(f"invalid --fixture: {exc}")

    try:
        input_paths = expand_input_paths(args.paths)
    except ValueError as exc:
        parser.error(str(exc))
    parsed_files: dict[Path, ParsedFile] = {}
    for path in input_paths:
        text = path.read_text(encoding="utf-8")
        parsed_files[path] = parse_file(text)
    jars: dict[str, Path] = {}
    for specification in args.jar:
        name, separator, raw_path = specification.partition("=")
        if not separator or not name.strip() or not raw_path.strip():
            parser.error("--jar must use name=path")
        jars[parse_addon_spec(name)[0]] = Path(raw_path).expanduser()
    target = {
        key: value for key, value in {
            "name": args.target_name,
            "minecraft": args.minecraft,
            "paper": args.paper,
            "java": args.java,
            "denizen": args.denizen_version,
            "denizenm": args.denizenm,
        }.items() if value
    }
    meta = MetaIndex(
        args.db, args.profile, set(args.addon), target=target, jars=jars,
        require_jar_evidence=args.require_jar_evidence,
    )
    all_scripts = {name for parsed in parsed_files.values() for name in parsed.scripts}
    all_scripts.update(name.casefold() for name in args.external_script)
    semantic_by_file = analyze_project(
        {str(path): parsed.text for path, parsed in parsed_files.items()},
        context=fixture.get("context") if isinstance(fixture.get("context"), dict) else None,
        fixture=fixture,
        known_script_names=all_scripts,
    )
    all_results: list[dict] = []
    contract = json.loads(args.contract.read_text(encoding="utf-8")) if args.contract else None
    decision = json.loads(args.decision.read_text(encoding="utf-8")) if args.decision else None
    if decision is not None and contract is None:
        parser.error("--decision requires --contract")
    for path, parsed in parsed_files.items():
        results = lint_parsed(parsed, meta)
        semantic = semantic_by_file.get(str(path))
        if semantic is not None:
            results.extend(semantic_issues(semantic, str(path), fixture))
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

    all_results = normalize_findings(all_results)

    if args.json or args.format == "json":
        print(json.dumps(all_results, ensure_ascii=False, indent=2))
    else:
        print(render_table(all_results, show_information=args.show_information))
    if args.queue_report:
        args.queue_report.parent.mkdir(parents=True, exist_ok=True)
        args.queue_report.write_text(json.dumps(build_report(all_results), ensure_ascii=False, indent=2), encoding="utf-8")
    blocking = any(result["severity"] == "error" for result in all_results)
    if args.strict_warnings:
        blocking = blocking or any(result["severity"] == "warning" for result in all_results)
    return 1 if blocking else 0


if __name__ == "__main__":
    raise SystemExit(main())
