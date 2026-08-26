"""A deliberately bounded port of Denizen-Core's portable script semantics.

The implementation follows the source-level model, not the Minecraft API:
ScriptBuilder turns indented command lists into entries, ScriptQueue owns
definitions and ordered execution, and TagManager resolves queue/context tags.
Only queue commands that can be evaluated without Bukkit are executed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Iterable


COMMAND = re.compile(r"^\s*-\s*(.+?)\s*$")
TAG = re.compile(r"<(?:(\[)([A-Za-z_][A-Za-z0-9_.-]*)\]|context\.([A-Za-z_][A-Za-z0-9_.-]*))>", re.I)
COMPARISON = re.compile(r"^(.+?)\s*(==|!=|>=|<=|>|<|equals|contains)\s*(.+)$", re.I)
TOP_LEVEL = re.compile(r"^([A-Za-z0-9_-]+):\s*(?:#.*)?$")
DECLARATIONS = re.compile(r"^\s+definitions:\s*(.*?)\s*(?:#.*)?$", re.I)
LIST_LITERAL = re.compile(r"(?:<)?list\[(.*)](?:>)?", re.I)
MAP_LITERAL = re.compile(r"(?:map@|<?map\[)(.*?)]?>?(?:\s|$)", re.I)
DURATION = re.compile(r"^(\d+(?:\.\d+)?)([tsmhd])$", re.I)


@dataclass(frozen=True)
class SemanticDiagnostic:
    code: str
    severity: str
    line: int
    message: str
    suggestion: str


@dataclass
class ScriptEntry:
    command: str
    arguments: str
    line: int
    children: list["ScriptEntry"] = field(default_factory=list)


@dataclass
class SemanticResult:
    diagnostics: list[SemanticDiagnostic]
    trace: list[str]
    definitions: dict[str, str]
    platform_commands: list[tuple[int, str]]
    stopped: bool
    determinations: list[str] = field(default_factory=list)
    waits: list[str] = field(default_factory=list)


@dataclass
class ScriptContainer:
    name: str
    definitions: list[str]
    entries: list[ScriptEntry]
    line_offset: int = 0


class LoopControl(Exception):
    def __init__(self, action: str):
        self.action = action


def _strip_comment(line: str) -> str:
    quote = ""
    escaped = False
    for index, char in enumerate(line):
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
        elif char in "\"'":
            quote = char
        elif char == "#":
            return line[:index]
    return line


def _split_command(raw: str) -> tuple[str, str]:
    raw = raw.rstrip(":").strip()
    command, _, arguments = raw.partition(" ")
    return command.casefold(), arguments.strip()


def build_entries(text: str) -> list[ScriptEntry]:
    """Python analogue of ScriptBuilder for YAML list commands.

    It is intentionally restricted to command list entries. YAML container
    parsing remains dCore-lint's responsibility; all indented `- command`
    lines are represented with their braced body exactly as queue commands use.
    """
    roots: list[ScriptEntry] = []
    stack: list[tuple[int, ScriptEntry]] = []
    for line_no, raw in enumerate(text.splitlines(), 1):
        line = _strip_comment(raw)
        found = COMMAND.match(line)
        if not found:
            # A top-level YAML key starts a new script container. Without this
            # boundary a command list in the next container can accidentally
            # become the last case/body of the preceding one.
            if line and not line[0].isspace() and line.rstrip().endswith(":"):
                stack.clear()
            continue
        indent = len(line) - len(line.lstrip(" "))
        command, arguments = _split_command(found.group(1))
        if not command:
            continue
        entry = ScriptEntry(command, arguments, line_no)
        while stack and stack[-1][0] >= indent:
            stack.pop()
        if stack:
            stack[-1][1].children.append(entry)
        else:
            roots.append(entry)
        stack.append((indent, entry))
    return roots


def _truthy(value: str) -> bool:
    return value.casefold() not in {"", "false", "null", "none", "0"}


class TagManager:
    """Small TagManager port for definitions and supplied event context."""

    def __init__(self, definitions: dict[str, str], context: dict[str, str], diagnostics: list[SemanticDiagnostic]):
        self.definitions = definitions
        self.context = {key.casefold(): str(value) for key, value in context.items()}
        self.diagnostics = diagnostics

    def fill(self, value: str, line: int) -> str:
        def replace(found: re.Match[str]) -> str:
            definition = found.group(2)
            context = found.group(3)
            if definition:
                root, _, tail = definition.casefold().partition(".")
                if root not in self.definitions:
                    self.diagnostics.append(SemanticDiagnostic(
                        "undefined_definition", "warning", line,
                        f"Definition '<[{root}]>' has no local writer or container declaration.",
                        "Define it on every reachable path or declare it in definitions: when it is a queue input.",
                    ))
                    return found.group(0)
                # MapTag traversal is platform object behavior. Preserve a known
                # root rather than pretend that Python understands every object.
                return self.definitions[root] if not tail else found.group(0)
            root, _, tail = context.casefold().partition(".")
            if root not in self.context:
                self.diagnostics.append(SemanticDiagnostic(
                    "unknown_context", "information", line,
                    f"Context '<context.{root}>' needs an event/runtime adapter to prove.",
                    "Declare its event contract; do not treat static analysis as runtime proof.",
                ))
                return found.group(0)
            return self.context[root] if not tail else found.group(0)
        return TAG.sub(replace, value)


class ScriptQueue:
    """Bounded equivalent of ScriptQueue for semantic execution and tracing."""

    def __init__(
        self, context: dict[str, str] | None = None, definitions: Iterable[str] = (),
        max_steps: int = 10_000, program: dict[str, ScriptContainer] | None = None,
        supplied_definitions: dict[str, str] | None = None, call_depth: int = 0,
        call_stack: tuple[str, ...] = (), inject_stack: tuple[str, ...] = (),
    ):
        self.definitions: dict[str, str] = {name.casefold(): f"<parameter:{name.casefold()}>" for name in definitions}
        self.definitions.update({key.casefold(): str(value) for key, value in (supplied_definitions or {}).items()})
        self.context = context or {}
        self.max_steps = max_steps
        self.steps = 0
        self.stopped = False
        self.diagnostics: list[SemanticDiagnostic] = []
        self.trace: list[str] = []
        self.platform_commands: list[tuple[int, str]] = []
        self.determinations: list[str] = []
        self.waits: list[str] = []
        self.program = program or {}
        self.call_depth = call_depth
        self.max_call_depth = 32
        self.call_stack = call_stack
        self.inject_stack = inject_stack
        self.loop_depth = 0
        self.tags = TagManager(self.definitions, self.context, self.diagnostics)

    def run(self, entries: Iterable[ScriptEntry]) -> SemanticResult:
        self._run_block(list(entries))
        return SemanticResult(self.diagnostics, self.trace, dict(self.definitions), self.platform_commands, self.stopped, self.determinations, self.waits)

    def _step(self, entry: ScriptEntry) -> bool:
        self.steps += 1
        if self.steps <= self.max_steps:
            return True
        self.diagnostics.append(SemanticDiagnostic(
            "semantic_execution_limit", "error", entry.line,
            f"Queue exceeded the bounded semantic budget ({self.max_steps} entries); proof class: {self._limit_class()}.",
            "Use the path/lifetime report: bound the loop, add an exit fixture, or run this path against the real server.",
        ))
        self.stopped = True
        return False

    def _run_block(self, entries: list[ScriptEntry]) -> None:
        index = 0
        while index < len(entries) and not self.stopped:
            entry = entries[index]
            if not self._step(entry):
                return
            if entry.command == "else" or entry.command == "case" or entry.command == "default":
                self.diagnostics.append(SemanticDiagnostic(
                    "orphaned_control_branch", "error", entry.line,
                    f"'{entry.command}' has no immediately preceding compatible control command.",
                    "Align it directly under an if/choose block.",
                ))
            elif entry.command == "if":
                consumed = self._run_if(entries, index)
                index = consumed
            elif entry.command == "choose":
                index = self._run_choose(entries, index)
            else:
                self._execute(entry)
            index += 1

    def _run_if(self, entries: list[ScriptEntry], index: int) -> int:
        entry = entries[index]
        chosen: ScriptEntry | None = entry if self._condition(entry.arguments, entry.line) else None
        cursor = index + 1
        while cursor < len(entries) and entries[cursor].command == "else":
            alternative = entries[cursor]
            if chosen is None and (not alternative.arguments or alternative.arguments.casefold().startswith("if ")):
                condition = alternative.arguments[3:] if alternative.arguments.casefold().startswith("if ") else "true"
                if self._condition(condition, alternative.line):
                    chosen = alternative
            cursor += 1
        if chosen:
            self.trace.append(f"if:{chosen.line}:taken")
            self._run_block(chosen.children)
        else:
            self.trace.append(f"if:{entry.line}:skipped")
        return cursor - 1

    def _run_choose(self, entries: list[ScriptEntry], index: int) -> int:
        entry = entries[index]
        value = self.tags.fill(entry.arguments, entry.line).casefold()
        chosen: ScriptEntry | None = None
        default: ScriptEntry | None = None
        # YAML-braced commands retain case/default as children of choose.
        # (If/else is different: its alternatives are adjacent queue entries.)
        for branch in entry.children:
            if branch.command not in {"case", "default"}:
                self.diagnostics.append(SemanticDiagnostic(
                    "choose_invalid_branch", "error", branch.line,
                    "Choose body must contain only case/default branches.",
                    "Nest the command below a case or default block.",
                ))
                continue
            if branch.command == "case" and self.tags.fill(branch.arguments, branch.line).casefold() == value and chosen is None:
                chosen = branch
            if branch.command == "default":
                default = branch
        chosen = chosen or default
        if chosen:
            self.trace.append(f"choose:{entry.line}:{chosen.command}@{chosen.line}")
            self._run_block(chosen.children)
        else:
            self.diagnostics.append(SemanticDiagnostic(
                "choose_without_match", "warning", entry.line,
                "Choose has no matching case or default for the resolved value.",
                "Add an explicit default or prove all possible values are covered.",
            ))
        return index

    def _execute(self, entry: ScriptEntry) -> None:
        if entry.command == "define":
            name, separator, value = entry.arguments.partition(" ")
            name = name.casefold().strip()
            action = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_.-]*):([+\-]):(.+)", name)
            if action and not separator:
                self._define_action(entry, action.group(1), action.group(2), action.group(3))
                return
            if name.endswith(":!") and not separator:
                self.definitions.pop(name[:-2], None)
                self.trace.append(f"define_remove:{name[:-2]}")
                return
            if not separator or not name or ":" in name:
                self.diagnostics.append(SemanticDiagnostic(
                    "invalid_define", "error", entry.line,
                    "Define requires a plain definition id and a value.",
                    "Use `define name value`; data actions remain a runtime adapter boundary.",
                ))
                return
            self.definitions[name] = self.tags.fill(value, entry.line)
            self.trace.append(f"define:{name}")
        elif entry.command == "stop":
            self.stopped = True
            self.trace.append(f"stop:{entry.line}")
        elif entry.command == "determine":
            self._determine(entry)
        elif entry.command == "definemap":
            # Definemap is a core queue writer. MapTag internals stay opaque,
            # but its root definition is definitely available after this line.
            name = entry.arguments.rstrip(":").strip().casefold()
            if name:
                self.definitions[name] = "<map>"
                self.trace.append(f"definemap:{name}")
            else:
                self.diagnostics.append(SemanticDiagnostic(
                    "invalid_definemap", "error", entry.line,
                    "Definemap requires a definition id.",
                    "Use `definemap name:` followed by map keys.",
                ))
        elif entry.command == "repeat":
            self._repeat(entry)
        elif entry.command == "foreach":
            self._foreach(entry)
        elif entry.command == "while":
            self._while(entry)
        elif entry.command == "run":
            self._run_script(entry)
        elif entry.command == "inject":
            self._inject_script(entry)
        elif entry.command == "wait":
            self._wait(entry)
        else:
            # Commands such as narrate are valid, but require their own executor
            # or Bukkit-facing implementation. Preserve them as an explicit
            # semantic boundary instead of inventing server behavior.
            # Tag filling still occurs before every real Denizen command, so it
            # must be analyzed even when the command executor is unavailable.
            self.tags.fill(entry.arguments, entry.line)
            self.platform_commands.append((entry.line, entry.command))
            self.trace.append(f"platform:{entry.command}@{entry.line}")

    def _define_action(self, entry: ScriptEntry, name: str, operation: str, raw_delta: str) -> None:
        current = self.definitions.get(name.casefold())
        if current is None:
            self.diagnostics.append(SemanticDiagnostic(
                "data_action_undefined", "warning", entry.line,
                f"Data action targets definition '<[{name}]>' without a local value.",
                "Define the value first or declare it as a queue input.",
            ))
            return
        delta = self.tags.fill(raw_delta, entry.line)
        try:
            result = float(current) + (1 if operation == "+" else -1) * float(delta)
        except ValueError:
            self.diagnostics.append(SemanticDiagnostic(
                "data_action_non_numeric", "warning", entry.line,
                f"Data action '{operation}' needs numeric definition and delta.",
                "Use a numeric fixture or leave object-specific actions to the runtime adapter.",
            ))
            return
        self.definitions[name.casefold()] = str(int(result) if result.is_integer() else result)
        self.trace.append(f"define_action:{name}{operation}")

    def _determine(self, entry: ScriptEntry) -> None:
        outcome = self.tags.fill(entry.arguments, entry.line)
        passive = outcome.casefold().startswith("passively ")
        if passive:
            outcome = outcome.split(" ", 1)[1] if " " in outcome else ""
        if not outcome:
            self.diagnostics.append(SemanticDiagnostic(
                "invalid_determine", "error", entry.line,
                "Determine requires an outcome.",
                "Provide a determination value; use passively only when the queue must continue.",
            ))
            return
        self.determinations.append(outcome)
        self.trace.append(f"determine:{entry.line}{':passive' if passive else ''}")
        if not passive:
            self.stopped = True

    def _foreach(self, entry: ScriptEntry) -> None:
        raw = self.tags.fill(entry.arguments, entry.line)
        if raw.casefold() in {"next", "stop"}:
            if not self.loop_depth:
                self.diagnostics.append(SemanticDiagnostic(
                    "loop_control_outside_loop", "error", entry.line,
                    f"'foreach {raw.casefold()}' is not inside a foreach body.",
                    "Place it inside a foreach block or remove it.",
                ))
                return
            raise LoopControl(raw.casefold())
        values, keys = self._foreach_values(raw)
        if values is None:
            self.diagnostics.append(SemanticDiagnostic(
                "foreach_not_static", "warning", entry.line,
                "Foreach input is not a list fixture resolvable by the semantic core.",
                "Supply a bounded list fixture; MapTag/object iteration remains a runtime adapter boundary.",
            ))
            return
        name = self._named_value(entry.arguments, "as", "value")
        key_name = self._named_value(entry.arguments, "key", "key") if keys is not None else ""
        saved = {key: self.definitions.get(key) for key in (name, "loop_index", key_name) if key}
        self.loop_depth += 1
        try:
            for index, value in enumerate(values, 1):
                self.definitions[name] = value
                self.definitions["loop_index"] = str(index)
                if keys is not None:
                    self.definitions[key_name] = keys[index - 1]
                try:
                    self._run_block(entry.children)
                except LoopControl as control:
                    if control.action == "stop":
                        break
                    continue
                if self.stopped:
                    break
        finally:
            self.loop_depth -= 1
            for key, value in saved.items():
                if value is None:
                    self.definitions.pop(key, None)
                else:
                    self.definitions[key] = value
        self.trace.append(f"foreach:{entry.line}:{len(values)}")

    def _run_script(self, entry: ScriptEntry) -> None:
        target, supplied = self._run_target(entry)
        if not target:
            self.diagnostics.append(SemanticDiagnostic(
                "run_missing_target", "error", entry.line,
                "Run requires a target script name before its options.",
                "Use `run task_name def:value` or `run task_name def.name:value`.",
            ))
            return
        container = self.program.get(target.casefold())
        if container is None:
            self.diagnostics.append(SemanticDiagnostic(
                "run_unknown_script", "error", entry.line,
                f"Run target '{target}' is not present in this lint project.",
                "Add the script to the project, declare it external, or correct the name.",
            ))
            return
        resolved_supplied = dict(supplied)
        for index, name in enumerate(container.definitions, 1):
            if name.casefold() not in resolved_supplied and str(index) in supplied:
                resolved_supplied[name.casefold()] = supplied[str(index)]
        missing = [name for name in container.definitions if name.casefold() not in resolved_supplied]
        if missing:
            self.diagnostics.append(SemanticDiagnostic(
                "run_missing_definitions", "warning", entry.line,
                f"Run target '{target}' declares definitions not supplied by this call: {', '.join(missing)}.",
                "Pass named def.<name>: values or document a deliberately optional input.",
            ))
        if self.call_depth >= self.max_call_depth:
            self.diagnostics.append(SemanticDiagnostic(
                "run_call_depth_limit", "error", entry.line,
                f"Run call graph exceeded bounded depth {self.max_call_depth} at '{target}'.",
                "Break the recursive cycle or provide an explicit runtime-only boundary.",
            ))
            return
        normalized_target = target.casefold()
        if normalized_target in self.call_stack:
            cycle = " -> ".join((*self.call_stack, normalized_target))
            self.diagnostics.append(SemanticDiagnostic(
                "run_recursive_cycle", "error", entry.line,
                f"Run creates an unbounded local call cycle: {cycle}.",
                "Add a concrete terminal condition or move the recursion behind an explicit runtime boundary.",
            ))
            return
        child = ScriptQueue(
            self.context, container.definitions, self.max_steps, self.program,
            resolved_supplied, self.call_depth + 1, (*self.call_stack, normalized_target),
        )
        result = child.run(container.entries)
        self.diagnostics.extend(result.diagnostics)
        self.trace.extend(f"run:{target}:{trace}" for trace in result.trace)
        self.platform_commands.extend(result.platform_commands)
        self.trace.append(f"run:{target}@{entry.line}")

    def _inject_script(self, entry: ScriptEntry) -> None:
        parts = entry.arguments.split()
        if not parts:
            self.diagnostics.append(SemanticDiagnostic("inject_missing_target", "error", entry.line, "Inject requires a target script name.", "Use `inject task_name` or `inject task_name path:section`."))
            return
        target = parts[0].split(".", 1)[0].casefold()
        container = self.program.get(target)
        if container is None:
            self.diagnostics.append(SemanticDiagnostic("inject_unknown_script", "error", entry.line, f"Inject target '{parts[0]}' is not present in this lint project.", "Add the script to the project or correct the target name."))
            return
        if target in self.inject_stack:
            self.diagnostics.append(SemanticDiagnostic("inject_recursive_cycle", "error", entry.line, f"Inject creates a shared-queue cycle: {' -> '.join((*self.inject_stack, target))}.", "Break the inject cycle; it cannot create a separate queue boundary."))
            return
        if any(part.casefold().startswith("path:") for part in parts[1:]) or "." in parts[0]:
            self.diagnostics.append(SemanticDiagnostic("inject_path_unverified", "information", entry.line, "Inject path is present but section-path resolution is not modeled yet.", "Verify the target path in Meta/runtime; base-container injection is still analyzed."))
        prior_stack = self.inject_stack
        self.inject_stack = (*self.inject_stack, target)
        try:
            self._run_block(container.entries)
        finally:
            self.inject_stack = prior_stack
        self.trace.append(f"inject:{target}@{entry.line}")

    def _wait(self, entry: ScriptEntry) -> None:
        value = self.tags.fill(entry.arguments.split()[0] if entry.arguments else "", entry.line)
        if not DURATION.match(value):
            self.diagnostics.append(SemanticDiagnostic("wait_not_static", "information", entry.line, "Wait duration needs a runtime value/adapter to quantify queue lifetime.", "Provide a duration fixture when timing affects a proof claim."))
            return
        self.waits.append(value)
        self.trace.append(f"wait:{value}@{entry.line}")

    def _run_target(self, entry: ScriptEntry) -> tuple[str, dict[str, str]]:
        parts = entry.arguments.split()
        if not parts:
            return "", {}
        target = parts[0]
        supplied: dict[str, str] = {}
        positional = 1
        for part in parts[1:]:
            if part.casefold().startswith("def.") and ":" in part:
                name, value = part[4:].split(":", 1)
                supplied[name.casefold()] = self.tags.fill(value, entry.line)
            elif part.casefold().startswith("def:"):
                for value in self.tags.fill(part[4:], entry.line).split("|"):
                    supplied[str(positional)] = value
                    positional += 1
        return target, supplied

    @staticmethod
    def _named_value(raw: str, name: str, default: str) -> str:
        found = re.search(rf"\b{re.escape(name)}:([^\s]+)", raw, re.I)
        return found.group(1).casefold() if found else default

    @staticmethod
    def _foreach_values(raw: str) -> tuple[list[str] | None, list[str] | None]:
        map_found = MAP_LITERAL.search(raw)
        if map_found:
            pairs = [part.split("=", 1) for part in map_found.group(1).split(";") if "=" in part]
            return [value for _, value in pairs], [key for key, _ in pairs]
        found = LIST_LITERAL.search(raw)
        return (found.group(1).split("|"), None) if found else (None, None)

    def _repeat(self, entry: ScriptEntry) -> None:
        first, *rest = self.tags.fill(entry.arguments, entry.line).split()
        try:
            amount = int(first)
        except (ValueError, IndexError):
            self.diagnostics.append(SemanticDiagnostic(
                "repeat_not_static", "warning", entry.line,
                "Repeat count is not a statically resolvable integer.",
                "Provide a bounded numeric fixture for semantic execution.",
            ))
            return
        name = "value"
        if "as:" in entry.arguments:
            name = entry.arguments.split("as:", 1)[1].split()[0].casefold()
        original = self.definitions.get(name)
        for value in range(1, max(0, amount) + 1):
            self.definitions[name] = str(value)
            self._run_block(entry.children)
            if self.stopped:
                break
        if original is None:
            self.definitions.pop(name, None)
        else:
            self.definitions[name] = original

    def _while(self, entry: ScriptEntry) -> None:
        original = self.definitions.get("loop_index")
        loop = 0
        while not self.stopped and self._condition(entry.arguments, entry.line):
            loop += 1
            self.definitions["loop_index"] = str(loop)
            self._run_block(entry.children)
            if loop >= self.max_steps:
                self.diagnostics.append(SemanticDiagnostic(
                    "while_semantic_limit", "error", entry.line,
                    f"While did not become false within the semantic execution budget; proof class: {self._limit_class()}.",
                    "Add a state-changing bound or prove the runtime wait/exit condition.",
                ))
                break
        if original is None:
            self.definitions.pop("loop_index", None)
        else:
            self.definitions["loop_index"] = original

    def _condition(self, raw: str, line: int) -> bool:
        value = self.tags.fill(raw.strip(), line)
        if value.casefold().startswith("!"):
            return not self._condition(value[1:].strip(), line)
        comparison = COMPARISON.match(value)
        if not comparison:
            return _truthy(value)
        left, operator, right = (part.strip().strip("\"'") for part in comparison.groups())
        if operator.casefold() == "equals":
            return left.casefold() == right.casefold()
        if operator.casefold() == "contains":
            return right.casefold() in left.casefold()
        try:
            numeric_left, numeric_right = float(left), float(right)
        except ValueError:
            numeric_left, numeric_right = left, right
        return {
            "==": numeric_left == numeric_right, "!=": numeric_left != numeric_right,
            ">": numeric_left > numeric_right, "<": numeric_left < numeric_right,
            ">=": numeric_left >= numeric_right, "<=": numeric_left <= numeric_right,
        }[operator]

    def _limit_class(self) -> str:
        if self.waits:
            return "dynamic_or_event_driven_wait_boundary"
        if self.call_stack and len(self.call_stack) > 1:
            return "cross_queue_lifetime_unresolved"
        return "unbounded_or_unresolved_loop"


def _container_chunks(text: str) -> list[tuple[str, list[str], str, int]]:
    """Split top-level YAML containers and capture their declared definitions."""
    chunks: list[tuple[str, str, int]] = []
    current: list[str] = []
    current_name = ""
    line_offset = 0
    for raw in text.splitlines(keepends=True):
        title = TOP_LEVEL.match(_strip_comment(raw).rstrip("\r\n"))
        if title and current:
            chunks.append((current_name, "".join(current), line_offset))
            line_offset += len(current)
            current = []
        if title:
            current_name = title.group(1).casefold()
        current.append(raw)
    if current:
        chunks.append((current_name, "".join(current), line_offset))
    result: list[tuple[str, list[str], str, int]] = []
    for name, chunk, offset in chunks:
        declared: list[str] = []
        for raw in chunk.splitlines():
            found = DECLARATIONS.match(_strip_comment(raw))
            if not found:
                continue
            declared.extend(value.strip() for value in found.group(1).split("|") if value.strip())
        result.append((name, declared, chunk, offset))
    return result


def _offset_entries(entries: list[ScriptEntry], offset: int) -> None:
    for entry in entries:
        entry.line += offset
        _offset_entries(entry.children, offset)


def build_program(text: str) -> dict[str, ScriptContainer]:
    """Build named containers so Run can follow the local call graph."""
    program: dict[str, ScriptContainer] = {}
    for name, declared, chunk, offset in _container_chunks(text):
        entries = build_entries(chunk)
        _offset_entries(entries, offset)
        if name:
            program[name] = ScriptContainer(name, declared, entries, offset)
    return program


def analyze_project(
    sources: dict[str, str], *, context: dict[str, str] | None = None,
    max_steps: int = 10_000, fixture: dict[str, object] | None = None,
    known_script_names: Iterable[str] = (),
) -> dict[str, SemanticResult]:
    """Execute each local container against one cross-file script program.

    Results are grouped by the file containing the root queue. A diagnostic
    emitted while following a cross-file call belongs to that caller's proof
    path, which makes a project lint actionable without claiming Bukkit state.
    """
    program: dict[str, ScriptContainer] = {}
    fixture = fixture or {}
    fixture_definitions = fixture.get("definitions_by_container", {})
    roots: list[tuple[str, ScriptContainer]] = []
    for source, text in sources.items():
        local = build_program(text)
        for name, container in local.items():
            # Duplicate container handling stays in the existing structural
            # lint. Keep its first body here to make semantic traversal stable.
            if name not in program:
                program[name] = container
                roots.append((source, container))
    for name in known_script_names:
        program.setdefault(str(name).casefold(), ScriptContainer(str(name).casefold(), [], []))
    grouped: dict[str, SemanticResult] = {}
    for source, container in roots:
        result = ScriptQueue(
            context=context, definitions=container.definitions, max_steps=max_steps,
            program=program, call_stack=(container.name,),
            supplied_definitions=(fixture_definitions.get(container.name, {}) if isinstance(fixture_definitions, dict) else {}),
        ).run(container.entries)
        previous = grouped.get(source)
        if previous is None:
            grouped[source] = result
            continue
        previous.diagnostics.extend(result.diagnostics)
        previous.trace.extend(result.trace)
        previous.definitions.update(result.definitions)
        previous.platform_commands.extend(result.platform_commands)
        previous.stopped = previous.stopped or result.stopped
        previous.determinations.extend(result.determinations)
        previous.waits.extend(result.waits)
    for result in grouped.values():
        unique: list[SemanticDiagnostic] = []
        seen: set[tuple[str, int, str]] = set()
        for diagnostic in result.diagnostics:
            key = (diagnostic.code, diagnostic.line, diagnostic.message)
            if key not in seen:
                seen.add(key)
                unique.append(diagnostic)
        result.diagnostics = unique
    return grouped


def analyze_denizen(
    text: str, *, context: dict[str, str] | None = None, max_steps: int = 10_000,
    known_script_names: Iterable[str] = (),
) -> SemanticResult:
    """Build entries and execute portable queue semantics for lint evidence.

    A queue is scoped to one Denizen container. Header `definitions:` are its
    input contract, not undeclared queue variables.
    """
    diagnostics: list[SemanticDiagnostic] = []
    trace: list[str] = []
    definitions: dict[str, str] = {}
    platform_commands: list[tuple[int, str]] = []
    determinations: list[str] = []
    waits: list[str] = []
    stopped = False
    program = build_program(text)
    # The project linter may process one .dsc at a time. Retain the fact that a
    # target exists elsewhere without fabricating its body or its Bukkit state.
    for name in known_script_names:
        program.setdefault(name.casefold(), ScriptContainer(name.casefold(), [], []))
    for container in program.values():
        result = ScriptQueue(
            context=context, definitions=container.definitions, max_steps=max_steps,
            program=program, call_stack=(container.name,),
        ).run(container.entries)
        for diagnostic in result.diagnostics:
            diagnostics.append(diagnostic)
        trace.extend(result.trace)
        definitions.update(result.definitions)
        platform_commands.extend(result.platform_commands)
        determinations.extend(result.determinations)
        waits.extend(result.waits)
        stopped = stopped or result.stopped
    return SemanticResult(diagnostics, trace, definitions, platform_commands, stopped, determinations, waits)
