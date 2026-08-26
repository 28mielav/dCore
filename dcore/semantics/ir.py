"""Denizen-aware source frontend for dCore transformations.

This module deliberately stops before rewriting source.  It turns a .dsc file
into spans and semantic candidates while preserving unknown syntax as opaque
text.  The obfuscator can therefore make a fail-closed decision instead of
guessing from regular-expression matches.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Iterable, Mapping


TOP_LEVEL = re.compile(r"^(?P<key>[A-Za-z0-9_\- <>|*/.]+):(?:\s|$)")
EVENT_LINE = re.compile(r"^\s*(?:on|after)\s+(.+?):\s*$", re.IGNORECASE)
COMMAND_LINE = re.compile(r"^(?P<indent>\s*)-\s+(?P<body>.*?)(?:\r?\n)?$")
COMMAND_NAME = re.compile(r"^[~^]?(?P<name>[A-Za-z][A-Za-z0-9_-]*)\b(?P<rest>.*)$")
SCRIPT_REF = re.compile(r"<(?:script|proc)\[(?P<value>[^\]<>]*)\](?:[^<>]*)>", re.IGNORECASE)
STATIC_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")
KEY_VALUE = re.compile(r"(?<![A-Za-z0-9_.-])(?P<key>[A-Za-z_][A-Za-z0-9_.-]*):")


@dataclass(frozen=True)
class SourceSpan:
    """A half-open source span with stable line/column coordinates."""

    start: int
    end: int
    line: int
    column: int
    end_line: int
    end_column: int


@dataclass(frozen=True)
class OpaqueSpan:
    kind: str
    value: str
    span: SourceSpan


@dataclass(frozen=True)
class Symbol:
    name: str
    kind: str
    scope: str
    line: int
    source: SourceSpan
    dynamic: bool = False


@dataclass(frozen=True)
class Reference:
    kind: str
    value: str
    line: int
    source: SourceSpan
    dynamic: bool = False


@dataclass(frozen=True)
class CommandNode:
    name: str
    arguments: str
    line: int
    source: SourceSpan
    argument_span: SourceSpan
    opaque: tuple[OpaqueSpan, ...] = ()
    named_arguments: tuple[str, ...] = ()


@dataclass(frozen=True)
class EventNode:
    matcher: str
    line: int
    source: SourceSpan
    commands: tuple[CommandNode, ...] = ()


@dataclass(frozen=True)
class SectionNode:
    name: str
    source: SourceSpan
    end_line: int
    container_type: str | None
    is_container: bool


@dataclass
class DenizenFileIR:
    path: str
    text: str
    sections: list[SectionNode] = field(default_factory=list)
    commands: list[CommandNode] = field(default_factory=list)
    events: list[EventNode] = field(default_factory=list)
    symbols: list[Symbol] = field(default_factory=list)
    references: list[Reference] = field(default_factory=list)
    opaque: list[OpaqueSpan] = field(default_factory=list)

    @property
    def containers(self) -> list[SectionNode]:
        return [section for section in self.sections if section.is_container]

    @property
    def dynamic_references(self) -> list[Reference]:
        return [reference for reference in self.references if reference.dynamic]


@dataclass
class DenizenProjectIR:
    files: dict[str, DenizenFileIR]

    @property
    def containers(self) -> dict[str, list[tuple[str, SectionNode]]]:
        """Return every container occurrence; never silently overwrite duplicates."""
        result: dict[str, list[tuple[str, SectionNode]]] = {}
        for path, file_ir in self.files.items():
            for section in file_ir.containers:
                result.setdefault(section.name.casefold(), []).append((path, section))
        return result

    @property
    def unique_containers(self) -> dict[str, tuple[str, SectionNode]]:
        return {
            name: entries[0]
            for name, entries in self.containers.items()
            if len(entries) == 1
        }

    @property
    def duplicate_containers(self) -> set[str]:
        seen: set[str] = set()
        duplicates: set[str] = set()
        for file_ir in self.files.values():
            for section in file_ir.containers:
                key = section.name.casefold()
                if key in seen:
                    duplicates.add(key)
                seen.add(key)
        return duplicates


def _line_starts(text: str) -> list[int]:
    starts = [0]
    for match in re.finditer(r"\n", text):
        starts.append(match.end())
    return starts


def _span(text: str, starts: list[int], start: int, end: int) -> SourceSpan:
    line_index = max(0, __import__("bisect").bisect_right(starts, start) - 1)
    end_index = max(0, __import__("bisect").bisect_right(starts, max(start, end - 1)) - 1)
    return SourceSpan(
        start,
        end,
        line_index + 1,
        start - starts[line_index] + 1,
        end_index + 1,
        end - starts[end_index] + 1,
    )


def _strip_comment(line: str) -> tuple[str, list[tuple[int, int]]]:
    quote = ""
    escaped = False
    angle = square = curly = 0
    comment_start: int | None = None
    for index, char in enumerate(line):
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
            continue
        if char in "'\"":
            quote = char
        elif char == "<":
            angle += 1
        elif char == ">" and angle:
            angle -= 1
        elif char == "[":
            square += 1
        elif char == "]" and square:
            square -= 1
        elif char == "{":
            curly += 1
        elif char == "}" and curly:
            curly -= 1
        elif char == "#" and not angle and not square and not curly:
            comment_start = index
            break
    if comment_start is None:
        return line.rstrip("\r\n"), []
    return line[:comment_start].rstrip(), [(comment_start, len(line.rstrip("\r\n")))]


def _opaque_spans(value: str, absolute_start: int, line: int, starts: list[int], text: str) -> list[OpaqueSpan]:
    spans: list[OpaqueSpan] = []
    quote = ""
    escaped = False
    stack: list[tuple[str, int]] = []
    for index, char in enumerate(value):
        if quote:
            if char == "<":
                end = _balanced_end(value, index, "<", ">")
                if end is not None:
                    spans.append(OpaqueSpan("tag", value[index:end + 1], _span(text, starts, absolute_start + index, absolute_start + end + 1)))
                    continue
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                start = stack.pop()[1] if stack and stack[-1][0] == quote else index
                spans.append(OpaqueSpan("quoted", value[start:index + 1], _span(text, starts, absolute_start + start, absolute_start + index + 1)))
                quote = ""
            continue
        if char in "'\"":
            quote = char
            stack.append((char, index))
        elif char == "<":
            end = _balanced_end(value, index, "<", ">")
            if end is not None:
                spans.append(OpaqueSpan("tag", value[index:end + 1], _span(text, starts, absolute_start + index, absolute_start + end + 1)))
        elif char in "[{":
            closing = "]" if char == "[" else "}"
            end = _balanced_end(value, index, char, closing)
            if end is not None:
                kind = "list_or_map" if char == "[" else "map"
                spans.append(OpaqueSpan(kind, value[index:end + 1], _span(text, starts, absolute_start + index, absolute_start + end + 1)))
    return spans


def _balanced_end(value: str, start: int, opening: str, closing: str) -> int | None:
    depth = 0
    quote = ""
    escaped = False
    for index in range(start, len(value)):
        char = value[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
            continue
        if char in "'\"":
            quote = char
        elif char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                return index
    return None


def _split_named_arguments(value: str) -> tuple[str, ...]:
    found: list[str] = []
    for match in KEY_VALUE.finditer(value):
        prefix = value[:match.start()]
        if prefix.count("<") != prefix.count(">"):
            continue
        if prefix.count("[") != prefix.count("]"):
            continue
        found.append(match.group("key").casefold())
    return tuple(dict.fromkeys(found))


def _static_or_dynamic(value: str) -> tuple[str, bool]:
    clean = value.strip()
    if STATIC_NAME.fullmatch(clean):
        return clean, False
    return clean, True


def _paths_for_lines(lines: list[str]) -> list[tuple[str, ...]]:
    stack: list[tuple[int, str]] = []
    paths: list[tuple[str, ...]] = []
    for raw in lines:
        body, _ = _strip_comment(raw)
        if not body.strip():
            paths.append(tuple(item[1] for item in stack))
            continue
        indent = len(body) - len(body.lstrip(" "))
        list_item = body.lstrip().startswith("- ")
        while stack and (stack[-1][0] > indent if list_item else stack[-1][0] >= indent):
            stack.pop()
        paths.append(tuple(item[1] for item in stack))
        if not body.lstrip().startswith("-"):
            key = body.lstrip().split(":", 1)[0].strip()
            if key:
                stack.append((indent, key))
    return paths


def parse_denizen_ir(text: str, path: str = "") -> DenizenFileIR:
    starts = _line_starts(text)
    lines = text.splitlines(keepends=True)
    paths = _paths_for_lines(lines)
    file_ir = DenizenFileIR(path=path, text=text)
    top_level: list[tuple[str, int, int, int]] = []
    for number, raw in enumerate(lines, 1):
        body, comments = _strip_comment(raw)
        line_start = starts[number - 1]
        for comment_start, comment_end in comments:
            file_ir.opaque.append(OpaqueSpan("comment", raw[comment_start:comment_end], _span(text, starts, line_start + comment_start, line_start + comment_end)))
        if raw and not raw[0].isspace():
            match = TOP_LEVEL.match(body)
            if match:
                top_level.append((match.group("key").strip(), number, line_start, len(body)))

    for index, (name, number, line_start, _) in enumerate(top_level):
        end_offset = top_level[index + 1][2] if index + 1 < len(top_level) else len(text)
        end_line = text.count("\n", 0, end_offset)
        if end_offset == len(text) and (not text or not text.endswith("\n")):
            end_line += 1
        block = text[line_start:end_offset]
        type_match = re.search(r"(?m)^\s+type:\s*([^#\s]+)", block, re.IGNORECASE)
        kind = type_match.group(1).casefold() if type_match else None
        file_ir.sections.append(SectionNode(
            name=name,
            source=_span(text, starts, line_start, end_offset),
            end_line=end_line,
            container_type=kind,
            is_container=kind is not None,
        ))

    section_for_line: dict[int, SectionNode] = {}
    for section in file_ir.sections:
        for number in range(section.source.line, section.end_line + 1):
            section_for_line[number] = section

    event_headers: list[EventNode] = []
    for number, raw in enumerate(lines, 1):
        body, _ = _strip_comment(raw)
        line_start = starts[number - 1]
        section = section_for_line.get(number)
        event_match = EVENT_LINE.match(body)
        if event_match and section and section.container_type == "world":
            source_end = line_start + len(body)
            event_headers.append(EventNode(event_match.group(1).strip(), number, _span(text, starts, line_start, source_end), ()))
        command_match = COMMAND_LINE.match(raw)
        if not command_match or not section or section.container_type is None:
            continue
        path_names = {item.casefold() for item in paths[number - 1]}
        if not {"script", "events"}.intersection(path_names):
            continue
        indent = len(command_match.group("indent").replace("\t", "  "))
        if indent < 2:
            continue
        command_body = command_match.group("body").strip()
        command = COMMAND_NAME.match(command_body)
        if not command:
            continue
        name_value = command.group("name").casefold()
        arguments = command.group("rest").lstrip()
        command_start = line_start + command_match.start("body")
        # ``rest`` includes the whitespace between the command name and its
        # arguments.  The previous implementation searched for the trimmed
        # value from the command start, producing a span at ``un worker`` for
        # ``run worker``.  Keep the span at the first argument byte so later
        # semantic rewrites never have to guess around command names.
        rest = command.group("rest")
        leading_rest = len(rest) - len(rest.lstrip())
        argument_start = command_start + command.start("rest") + leading_rest if arguments else command_start + command.start("rest") + len(rest)
        node = CommandNode(
            name=name_value,
            arguments=arguments,
            line=number,
            source=_span(text, starts, command_start, line_start + len(body)),
            argument_span=_span(text, starts, argument_start, line_start + len(body)),
            opaque=tuple(_opaque_spans(arguments, argument_start, number, starts, text)),
            named_arguments=_split_named_arguments(arguments),
        )
        file_ir.commands.append(node)
        if name_value in {"define", "definemap"}:
            target = arguments.split(None, 1)[0] if arguments else ""
            clean, dynamic = _static_or_dynamic(target.split(":", 1)[0])
            if clean:
                file_ir.symbols.append(Symbol(clean, "definition", section.name, number, node.argument_span, dynamic))
        if name_value in {"foreach", "repeat", "while"}:
            for alias_match in re.finditer(r"\b(?:as|key):([A-Za-z_][A-Za-z0-9_-]*)", arguments, re.IGNORECASE):
                clean, dynamic = _static_or_dynamic(alias_match.group(1))
                if clean:
                    file_ir.symbols.append(Symbol(clean, "loop_alias", section.name, number, node.argument_span, dynamic))
        if name_value in {"run", "inject", "runlater"}:
            target = arguments.split(None, 1)[0] if arguments else ""
            clean, dynamic = _static_or_dynamic(target)
            if clean:
                file_ir.references.append(Reference("container_call", clean, number, node.argument_span, dynamic))
        for reference in SCRIPT_REF.finditer(arguments):
            clean, dynamic = _static_or_dynamic(reference.group("value"))
            file_ir.references.append(Reference("container_tag", clean, number, node.argument_span, dynamic))

    for index, header in enumerate(event_headers):
        section = section_for_line.get(header.line)
        end_line = section.end_line if section else len(lines)
        if index + 1 < len(event_headers):
            next_header = event_headers[index + 1]
            if next_header.line <= end_line:
                end_line = next_header.line - 1
        commands = tuple(
            command for command in file_ir.commands
            if header.line < command.line <= end_line
            and section_for_line.get(command.line) == section
        )
        file_ir.events.append(EventNode(header.matcher, header.line, header.source, commands))

    for section in file_ir.sections:
        for number in range(section.source.line, section.end_line + 1):
            raw = lines[number - 1]
            body, _ = _strip_comment(raw)
            match = re.match(r"^\s+definitions:\s*([^#\r\n]*)", body, re.IGNORECASE)
            if not match:
                continue
            for part in match.group(1).split("|"):
                name = part.split("[", 1)[0].strip()
                if name and STATIC_NAME.fullmatch(name):
                    start = starts[number - 1] + match.start(1) + match.group(1).find(name)
                    file_ir.symbols.append(Symbol(name, "definition", section.name, number, _span(text, starts, start, start + len(name))))
    return file_ir


def build_project_ir(files: Mapping[str, str] | Iterable[tuple[str, str]]) -> DenizenProjectIR:
    items = files.items() if isinstance(files, Mapping) else files
    return DenizenProjectIR({path: parse_denizen_ir(text, path) for path, text in items})
