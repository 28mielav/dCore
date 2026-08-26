"""The dCore MCP server: one agent surface for every MCP-speaking client.

Before 0.70 the agent surface was a Codex Skill, so the operating contract, the
tool list and the proof boundaries only reached one client. Everything an agent
needs is now protocol, not vendor packaging:

- tools mirror the CLI exactly (dcore.mcp.tools);
- the operating contract is a resource (dcore.mcp.resources);
- the evidence and execution gates are prompts (dcore.mcp.prompts).

The Custom GPT product is unaffected. It keeps its Action schema and Knowledge
bundle because Custom GPT does not speak MCP.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import dcore
from dcore.mcp import prompts, resources, tools
from dcore.mcp.protocol import (
    INVALID_PARAMS,
    Dispatcher,
    JsonRpcError,
    serve,
)

#: Revisions this server implements. A client asking for something else is
#: answered with the newest one we support, which the spec permits.
SUPPORTED_PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
DEFAULT_PROTOCOL_VERSION = SUPPORTED_PROTOCOL_VERSIONS[0]

SERVER_INFO = {
    "name": "dcore",
    "title": "dCore",
    "version": dcore.__version__,
}

INSTRUCTIONS = (
    "dCore is an evidence-first workbench for DenizenScript, DenizenM and Minecraft "
    "visual work. Read the dcore://instructions resource before answering a Denizen "
    "question, and call dcore_retrieve for target-pinned evidence before relying on "
    "memory or web search. Lint findings are static: never report them as runtime proof."
)


def build_dispatcher() -> Dispatcher:
    dispatcher = Dispatcher()

    @dispatcher.method("initialize")
    def initialize(params: dict[str, Any]) -> dict[str, Any]:
        requested = params.get("protocolVersion")
        version = requested if requested in SUPPORTED_PROTOCOL_VERSIONS else DEFAULT_PROTOCOL_VERSION
        return {
            "protocolVersion": version,
            "capabilities": {
                # listChanged is false everywhere: the tool, resource and prompt sets
                # are fixed at build time, so promising notifications would be a lie.
                "tools": {"listChanged": False},
                "resources": {"listChanged": False, "subscribe": False},
                "prompts": {"listChanged": False},
            },
            "serverInfo": SERVER_INFO,
            "instructions": INSTRUCTIONS,
        }

    @dispatcher.method("notifications/initialized")
    def initialized(params: dict[str, Any]) -> None:
        return None

    @dispatcher.method("ping")
    def ping(params: dict[str, Any]) -> dict[str, Any]:
        return {}

    @dispatcher.method("tools/list")
    def list_tools(params: dict[str, Any]) -> dict[str, Any]:
        return {"tools": tools.descriptors()}

    @dispatcher.method("tools/call")
    def call_tool(params: dict[str, Any]) -> dict[str, Any]:
        name = params.get("name")
        if not isinstance(name, str):
            raise JsonRpcError(INVALID_PARAMS, "tools/call requires a tool name")
        arguments = params.get("arguments") or {}
        if not isinstance(arguments, dict):
            raise JsonRpcError(INVALID_PARAMS, "tool arguments must be an object")
        return tools.call(name, arguments)

    @dispatcher.method("resources/list")
    def list_resources(params: dict[str, Any]) -> dict[str, Any]:
        return {"resources": resources.descriptors()}

    @dispatcher.method("resources/read")
    def read_resource(params: dict[str, Any]) -> dict[str, Any]:
        uri = params.get("uri")
        if not isinstance(uri, str):
            raise JsonRpcError(INVALID_PARAMS, "resources/read requires a uri")
        try:
            return resources.read(uri)
        except KeyError as error:
            raise JsonRpcError(INVALID_PARAMS, f"unknown resource: {uri}") from error
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise JsonRpcError(INVALID_PARAMS, f"unreadable resource: {uri}", str(error)) from error

    @dispatcher.method("prompts/list")
    def list_prompts(params: dict[str, Any]) -> dict[str, Any]:
        return {"prompts": prompts.descriptors()}

    @dispatcher.method("prompts/get")
    def get_prompt(params: dict[str, Any]) -> dict[str, Any]:
        name = params.get("name")
        if not isinstance(name, str):
            raise JsonRpcError(INVALID_PARAMS, "prompts/get requires a name")
        arguments = params.get("arguments") or {}
        if not isinstance(arguments, dict):
            raise JsonRpcError(INVALID_PARAMS, "prompt arguments must be an object")
        try:
            return prompts.render(name, arguments)
        except KeyError as error:
            raise JsonRpcError(INVALID_PARAMS, f"unknown prompt: {name}") from error
        except ValueError as error:
            raise JsonRpcError(INVALID_PARAMS, str(error)) from error

    return dispatcher


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Serve dCore tools over the Model Context Protocol on stdio"
    )
    parser.add_argument(
        "--describe",
        action="store_true",
        help="Print the tool, resource and prompt inventory as JSON and exit",
    )
    args = parser.parse_args()

    if args.describe:
        print(json.dumps(
            {
                "serverInfo": SERVER_INFO,
                "protocolVersions": list(SUPPORTED_PROTOCOL_VERSIONS),
                "tools": tools.descriptors(),
                "resources": resources.descriptors(),
                "prompts": prompts.descriptors(),
            },
            ensure_ascii=False,
            indent=2,
        ))
        return 0

    # stdout carries protocol frames only. Anything a tool prints to stderr stays
    # on stderr, where a client shows it as server log output.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")
    return serve(build_dispatcher())


if __name__ == "__main__":
    raise SystemExit(main())
