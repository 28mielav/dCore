"""Small, dependency-free syntax helpers used by the script linter."""

from __future__ import annotations

import re

NAMED_ARGUMENT = re.compile(r"^([A-Za-z_][A-Za-z0-9_.-]*):")

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

