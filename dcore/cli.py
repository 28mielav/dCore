"""Single entry point for every dCore tool.

Each subcommand owns its own argument parser, so this dispatcher forwards the
remaining argv untouched instead of trying to describe every flag twice.
"""

from __future__ import annotations

import importlib
import sys

COMMANDS: dict[str, tuple[str, str]] = {
    "retrieve": ("dcore.knowledge.retrieval", "Route a request to cards, Meta and route patterns"),
    "lint": ("dcore.lint.script", "Lint DenizenScript against a resolved multi-version target"),
    "lint-pack": ("dcore.lint.resourcepack", "Lint a merged resource pack or shader pipeline"),
    "design": ("dcore.design.routes", "Compare candidate routes before writing code"),
    "run": ("dcore.gates.release", "Run the target, static and runtime proof gate"),
    "shadow": ("dcore.gates.shadow", "Simulate a bounded event-session control plane"),
    "versions": ("dcore.knowledge.version_registry", "Discover Denizen and DenizenM version artifacts"),
    "verify": ("dcore.release.verify", "Validate the database and write a release manifest"),
    "build-gpt": ("dcore.release.bundle_gpt", "Build the Custom GPT bundle"),
    "update": ("dcore.release.update", "Refresh knowledge from pinned upstream sources"),
    "compact": ("dcore.release.compact", "Compact Meta overlays and merge search segments"),
    "import-meta": ("dcore.release.import_meta", "Import target-pinned historical Meta snapshots"),
    "migrate": ("dcore.release.migrate", "Apply curated database migrations"),
    "accept-agent": ("dcore.acceptance.agent", "Run the agent acceptance scenarios over the MCP surface"),
    "pack": ("dcore.pack.cli", "Reversible obfuscation for Denizen .dsc projects"),
    "accept-pool4": ("dcore.acceptance.pool4", "Run the Pool 4 golden acceptance corpus"),
    "mcp": ("dcore.mcp.server", "Serve dCore tools over the Model Context Protocol"),
}


def usage() -> str:
    width = max(len(name) for name in COMMANDS)
    lines = [
        "usage: dcore <command> [options]",
        "",
        "commands:",
        *(f"  {name:<{width}}  {summary}" for name, (_, summary) in COMMANDS.items()),
        "",
        "Run 'dcore <command> --help' for the options of one command.",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in {"-h", "--help", "help"}:
        print(usage())
        return 0
    command, *rest = argv
    if command not in COMMANDS:
        print(f"unknown command: {command}\n", file=sys.stderr)
        print(usage(), file=sys.stderr)
        return 2

    module_name, _ = COMMANDS[command]
    module = importlib.import_module(module_name)
    sys.argv = [f"dcore {command}", *rest]
    return int(module.main() or 0)


if __name__ == "__main__":
    raise SystemExit(main())
