"""DenizenScript structural parsing primitives."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from dcore.lint.syntax import strip_comment

SCRIPT_TITLE = re.compile(r"^([A-Za-z0-9_\-]+):\s*(?:#.*)?$")
YAML_KEY = re.compile(r"^\s*([A-Za-z0-9_ <>|*./\-]+):(?:\s|$)")
REFERENCE = re.compile(
    r"(?:\brun\s+|<proc\[|<script\[)([A-Za-z0-9_\-]+)", re.IGNORECASE
)
COMMAND_TOKEN = re.compile(r"^[~^]?([A-Za-z][A-Za-z0-9_\-]*)\b")
EVENT_LINE = re.compile(r"^(\s*)(on|after)\s+(.+):\s*(?:#.*)?$", re.IGNORECASE)

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

