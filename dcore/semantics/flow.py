"""Conservative control-flow queries over the existing source IR.

Unknown conditions fork paths. Recognized identity predicates establish only
an explicit context-object filter, never correctness of the ownership policy.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re

from dcore.semantics.ir import CommandNode, DenizenFileIR


@dataclass
class Block:
    command: CommandNode
    children: list[Block] = field(default_factory=list)


def blocks(ir: DenizenFileIR, start: int, end: int) -> list[Block]:
    roots: list[Block] = []
    stack: list[Block] = []
    for command in ir.commands:
        if not start < command.line <= end:
            continue
        while stack and stack[-1].command.source.column >= command.source.column:
            stack.pop()
        node = Block(command)
        (stack[-1].children if stack else roots).append(node)
        stack.append(node)
    return roots


def condition(value: str) -> str:
    return value.removesuffix(":").strip().casefold()


def identity_polarity(value: str) -> bool | None:
    # Deliberately exclude player flags: they need not identify the affected
    # entity/block. Compound conditions and dynamic marker names stay unknown.
    match = re.fullmatch(
        r"(!?)<context\.(?:entity|location|block|inventory|target)"
        r"\.has_flag\[[a-z0-9_.-]+\](\.not)?>(?:\s*==\s*(true|false))?", condition(value)
    )
    if not match:
        return None
    return (bool(match[1]) == bool(match[2])) == (match[3] != "false")


def cancellation_paths(nodes: list[Block], states: set[bool] | None = None) -> tuple[set[bool], dict[int, bool]]:
    states = {False} if states is None else set(states)
    findings: dict[int, bool] = {}
    index = 0
    while index < len(nodes) and states:
        node = nodes[index]
        cmd = node.command
        args = condition(cmd.arguments)
        if cmd.name == "if":
            polarity = identity_polarity(args)
            yes = {True} if polarity is True else states
            no = {True} if polarity is False else states
            yes = set() if args == "false" else yes
            no = set() if args == "true" else no
            yes, found = cancellation_paths(node.children, yes)
            findings.update(found)
            if index + 1 < len(nodes) and nodes[index + 1].command.name == "else":
                index += 1
                other = nodes[index]
                # else-if is conservatively optional until fully lowered.
                remainder, found = cancellation_paths(other.children, no)
                no = remainder | no if condition(other.command.arguments) else remainder
                findings.update(found)
            states = yes | no
        elif cmd.name == "stop":
            if not args:
                states = set()
            elif args.startswith("if:") and identity_polarity(args[3:]) is False:
                states = {True}
        elif cmd.name == "determine":
            if re.match(r"(?:passively\s+)?cancel(?:led)?(?:\s|$)", args):
                findings[cmd.line] = all(states)
            if not args.startswith("passively ") and "if:" not in args:
                states = set()
        elif node.children:
            # A loop/choose body may execute, but its filter cannot establish
            # a fact after it (zero iterations/default path).
            _, found = cancellation_paths(node.children, states)
            findings.update(found)
        index += 1
    return states, findings


def iteration_outcomes(nodes: list[Block], states: set[str] | None = None) -> set[str]:
    """Possible first-iteration outcomes: running, yielded, exit, continue.

    A conditional exit is evidence of a possible exit, not a finite bound.
    Nested loop exits are not exits from the enclosing loop.
    """
    states = {"running"} if states is None else set(states)
    index = 0
    while index < len(nodes):
        node = nodes[index]
        cmd, args = node.command.name, condition(node.command.arguments)
        active = states & {"running", "yielded"}
        done = states - active
        if not active:
            break
        if cmd == "if":
            yes = iteration_outcomes(node.children, active) if args != "false" else set()
            no = active if args != "true" else set()
            if index + 1 < len(nodes) and nodes[index + 1].command.name == "else":
                index += 1
                other = nodes[index]
                no_result = iteration_outcomes(other.children, no)
                no = no | no_result if condition(other.command.arguments) else no_result
            states = done | yes | no
        elif cmd in {"stop", "determine"} or (cmd == "while" and args == "stop"):
            if cmd == "determine" and args.startswith("passively "):
                pass
            else:
                states = done | {"exit"} | (active if "if:" in args else set())
        elif cmd == "while" and args == "next":
            states = done | {"continue" if x == "running" else "yielded_continue" for x in active}
        elif cmd == "wait":
            states = done | {"yielded"} | (active if "if:" in args else set())
        index += 1
    return states
