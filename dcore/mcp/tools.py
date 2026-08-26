"""The dCore tool surface exposed to any MCP-speaking agent.

Every tool runs the same `main()` the CLI runs, in-process, with a built argv.
That is deliberate: the flag semantics of `dcore lint` are already covered by the
acceptance suite, and a second hand-written argument path would be free to drift
from the behaviour those tests pin down. The MCP layer therefore owns schemas and
transport, never lint policy.

In-process rather than subprocess because the cost of a lint call is dominated by
building the Meta index from SQLite, and a long-lived server should be able to
amortise that instead of paying it per call.
"""

from __future__ import annotations

import importlib
import io
import json
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from dcore.paths import DATABASE_PATH


@dataclass(frozen=True)
class Outcome:
    exit_code: int
    stdout: str
    stderr: str


def invoke(module_name: str, argv: list[str]) -> Outcome:
    """Run a dCore module's main() with argv, capturing both streams.

    argparse failures raise SystemExit; a tool call must report that as an error
    payload rather than tearing down the server, so SystemExit is caught here.
    """
    import sys

    module = importlib.import_module(module_name)
    out, err = io.StringIO(), io.StringIO()
    saved = sys.argv
    sys.argv = [module_name.replace(".", "-"), *argv]
    try:
        with redirect_stdout(out), redirect_stderr(err):
            code = int(module.main() or 0)
    except SystemExit as exit_request:
        code = int(exit_request.code or 0)
    finally:
        sys.argv = saved
    return Outcome(code, out.getvalue(), err.getvalue())


# --- argv builders -----------------------------------------------------------
#
# Each builder turns validated MCP arguments into the flags the CLI already
# understands. Unknown keys are ignored rather than forwarded, so a client cannot
# smuggle arbitrary flags into a subprocess-free call.

TARGET_FLAGS = {
    "minecraft": "--minecraft",
    "paper": "--paper",
    "java": "--java",
    "denizen_version": "--denizen-version",
    "denizenm": "--denizenm",
    "profile": "--profile",
    "target_name": "--target-name",
}


def target_argv(arguments: dict[str, Any]) -> list[str]:
    argv: list[str] = []
    for key, flag in TARGET_FLAGS.items():
        value = arguments.get(key)
        if value:
            argv += [flag, str(value)]
    for addon in arguments.get("addons") or []:
        argv += ["--addon", str(addon)]
    for name, path in (arguments.get("jars") or {}).items():
        argv += ["--jar", f"{name}={path}"]
    if arguments.get("require_jar_evidence"):
        argv.append("--require-jar-evidence")
    return argv


def database_argv(arguments: dict[str, Any]) -> list[str]:
    database = arguments.get("db") or (str(DATABASE_PATH) if DATABASE_PATH.is_file() else None)
    return ["--db", str(database)] if database else []


@dataclass(frozen=True)
class Tool:
    name: str
    title: str
    description: str
    schema: dict[str, Any]
    module: str
    argv: Callable[[dict[str, Any], Path], list[str]]
    #: Tools whose non-zero exit means "findings present", not "call failed".
    #: A linter that exits 1 on an error-severity finding did its job.
    exit_is_findings: bool = False
    tags: tuple[str, ...] = field(default_factory=tuple)

    def descriptor(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "inputSchema": self.schema,
        }


TARGET_SCHEMA = {
    "profile": {"type": "string", "enum": ["denizenm", "official"], "description": "Meta dialect to resolve against"},
    "minecraft": {"type": "string", "description": "Target Minecraft version, such as 1.21.11"},
    "paper": {"type": "string", "description": "Target Paper version or build"},
    "java": {"type": "string", "description": "Target Java version"},
    "denizen_version": {"type": "string", "description": "Target Denizen/DenizenCore version"},
    "denizenm": {"type": "string", "description": "Target DenizenM build, such as 7299M"},
    "addons": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Enabled addons as name or name@version, such as reflect@2.4.2",
    },
    "jars": {
        "type": "object",
        "additionalProperties": {"type": "string"},
        "description": "Exact artifact evidence as {addon: jar path}",
    },
    "require_jar_evidence": {
        "type": "boolean",
        "description": "Block version-sensitive claims when a declared addon has no exact JAR",
    },
}


def script_inputs(arguments: dict[str, Any], workspace: Path) -> list[str]:
    """Resolve either on-disk paths or inline script text into lint inputs.

    Agents routinely hold a draft in the conversation rather than on disk. Making
    them write a temp file first is friction the server can absorb, so `text` is
    materialised into the per-call workspace and linted like any other file.
    """
    paths = [str(item) for item in (arguments.get("paths") or [])]
    text = arguments.get("text")
    if text:
        name = str(arguments.get("filename") or "inline.dsc")
        # Keep the caller's basename for readable finding locations, but never let
        # it escape the workspace.
        target = workspace / Path(name).name
        target.write_text(str(text), encoding="utf-8")
        paths.append(str(target))
    if not paths:
        raise ValueError("provide either paths or text")
    return paths


def lint_argv(arguments: dict[str, Any], workspace: Path) -> list[str]:
    argv = [*script_inputs(arguments, workspace), "--json"]
    argv += database_argv(arguments)
    argv += target_argv(arguments)
    for name in arguments.get("external_scripts") or []:
        argv += ["--external-script", str(name)]
    if arguments.get("closed_world"):
        argv.append("--closed-world")
    if arguments.get("strict_warnings"):
        argv.append("--strict-warnings")
    if arguments.get("fixture"):
        argv += ["--fixture", str(arguments["fixture"])]
    if arguments.get("contract"):
        argv += ["--contract", str(arguments["contract"])]
    return argv


def audit_argv(arguments: dict[str, Any], workspace: Path) -> list[str]:
    paths = [str(item) for item in (arguments.get("paths") or [])]
    if not paths:
        raise ValueError("paths is required")
    argv = [*paths, "--json"] + target_argv(arguments) + database_argv(arguments)
    if arguments.get("closed_world"):
        argv.append("--closed-world")
    return argv


def pack_argv(arguments: dict[str, Any], workspace: Path) -> list[str]:
    argv = [str(arguments["input"]), "--json"]
    if arguments.get("minecraft"):
        argv += ["--minecraft", str(arguments["minecraft"])]
    if arguments.get("pack_format") is not None:
        argv += ["--pack-format", str(arguments["pack_format"])]
    return argv


def obfuscate_argv(arguments: dict[str, Any], workspace: Path) -> list[str]:
    # Obfuscation is opt-in and never runs implicitly (see dcore://instructions);
    # this builder only shapes the argv once a caller has explicitly chosen it.
    command = str(arguments.get("action") or "verify")
    argv = [command]
    if command in {"obfuscate", "deploy"}:
        argv += [str(item) for item in arguments.get("inputs") or []]
    elif command in {"deobfuscate", "verify"}:
        argv.append(str(arguments["release"]))
    elif command in {"deobfuscate-direct", "verify-direct"}:
        argv.append(str(arguments["directory"]))
    if arguments.get("output"):
        argv += ["--output", str(arguments["output"])]
    if arguments.get("root"):
        argv += ["--root", str(arguments["root"])]
    if arguments.get("key"):
        argv += ["--key", str(arguments["key"])]
    if arguments.get("project_id"):
        argv += ["--project-id", str(arguments["project_id"])]
    if arguments.get("mode"):
        argv += ["--mode", str(arguments["mode"])]
    return argv


def retrieve_argv(arguments: dict[str, Any], workspace: Path) -> list[str]:
    argv = database_argv(arguments)
    if arguments.get("meta_query"):
        argv += ["--meta-query", str(arguments["meta_query"])]
    elif arguments.get("query"):
        argv += ["--query", str(arguments["query"])]
    if arguments.get("intent"):
        argv += ["--intent", str(arguments["intent"])]
    argv += target_argv({key: value for key, value in arguments.items() if key != "target_name"})
    return argv


def versions_argv(arguments: dict[str, Any], workspace: Path) -> list[str]:
    # Discovery reaches the network; reading the catalogued registry does not.
    # Only the read path is exposed, so an agent cannot trigger upstream traffic.
    return ["--catalogue", str(arguments["catalogue"])] if arguments.get("catalogue") else []


def verify_argv(arguments: dict[str, Any], workspace: Path) -> list[str]:
    argv: list[str] = []
    for key in ("root", "knowledge", "db", "output", "contract"):
        if arguments.get(key):
            argv += [f"--{key}", str(arguments[key])]
    if "output" not in arguments:
        raise ValueError("output is required")
    return argv


def build_gpt_argv(arguments: dict[str, Any], workspace: Path) -> list[str]:
    argv: list[str] = []
    for key in ("root", "knowledge", "output"):
        if arguments.get(key):
            argv += [f"--{key}", str(arguments[key])]
    if "output" not in arguments:
        raise ValueError("output is required")
    return argv


def acceptance_argv(arguments: dict[str, Any], workspace: Path) -> list[str]:
    return database_argv(arguments)


def pool4_argv(arguments: dict[str, Any], workspace: Path) -> list[str]:
    return ["--phase", str(arguments.get("phase") or "post")]


def shadow_argv(arguments: dict[str, Any], workspace: Path) -> list[str]:
    plan = arguments.get("plan")
    if not plan:
        inline = arguments.get("plan_json")
        if not inline:
            raise ValueError("provide either plan or plan_json")
        path = workspace / "shadow_plan.json"
        path.write_text(
            inline if isinstance(inline, str) else json.dumps(inline), encoding="utf-8"
        )
        plan = str(path)
    return ["--plan", str(plan)]


def design_argv(arguments: dict[str, Any], workspace: Path) -> list[str]:
    dossier = arguments.get("dossier")
    if not dossier:
        inline = arguments.get("dossier_json")
        if not inline:
            raise ValueError("provide either dossier or dossier_json")
        path = workspace / "dossier.json"
        path.write_text(
            inline if isinstance(inline, str) else json.dumps(inline), encoding="utf-8"
        )
        dossier = str(path)
    return ["compare", "--input", str(dossier), *database_argv(arguments), "--pretty"]


def release_gate_argv(arguments: dict[str, Any], workspace: Path) -> list[str]:
    argv = script_inputs(arguments, workspace)
    argv += database_argv(arguments)
    argv += target_argv(arguments)
    if arguments.get("closed_world"):
        argv.append("--closed-world")
    if arguments.get("query"):
        argv += ["--query", str(arguments["query"])]
    if arguments.get("require_route"):
        argv.append("--require-route")
    if arguments.get("runtime_report"):
        argv += ["--runtime-report", str(arguments["runtime_report"])]
    if arguments.get("shadow_plan"):
        argv += ["--shadow-plan", str(arguments["shadow_plan"])]
    if arguments.get("decision"):
        argv += ["--decision", str(arguments["decision"])]
    return argv


SCRIPT_INPUT_SCHEMA = {
    "paths": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Files or directories to lint. Pass the whole project for cross-file queue proof.",
    },
    "text": {"type": "string", "description": "Inline DenizenScript, linted as a temporary file"},
    "filename": {"type": "string", "description": "Basename used in findings when linting inline text"},
}


TOOLS: tuple[Tool, ...] = (
    Tool(
        name="dcore_lint",
        title="Lint DenizenScript",
        description=(
            "Lint DenizenScript against a resolved multi-version target. Returns JSON findings with "
            "severity, priority, confidence, layer and provenance. Static success is not runtime proof."
        ),
        schema={
            "type": "object",
            "properties": {
                **SCRIPT_INPUT_SCHEMA,
                **TARGET_SCHEMA,
                "closed_world": {
                    "type": "boolean",
                    "description": "Treat unresolved script references as errors; use for a complete project",
                },
                "strict_warnings": {"type": "boolean", "description": "Exit non-zero on warnings too"},
                "external_scripts": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Known project scripts intentionally outside this partial lint set",
                },
                "fixture": {"type": "string", "description": "Path to a JSON queue fixture"},
                "contract": {"type": "string", "description": "Path to a JSON behaviour witness manifest"},
                "db": {"type": "string", "description": "Override the knowledge database path"},
            },
            "anyOf": [{"required": ["paths"]}, {"required": ["text"]}],
        },
        module="dcore.lint.script",
        argv=lint_argv,
        exit_is_findings=True,
        tags=("lint", "static"),
    ),
    Tool(
        name="dcore_pack",
        title="Obfuscate or restore a Denizen project",
        description=(
            "Reversible obfuscation for Denizen .dsc projects: build an encrypted release, verify or "
            "restore it, or deploy/verify/restore incrementally straight into a scripts folder. Opt-in "
            "only; never run this unless the user explicitly asks to hide, protect, package, obfuscate "
            "or restore source."
        ),
        schema={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["obfuscate", "deobfuscate", "verify", "deploy", "verify-direct", "deobfuscate-direct"],
                    "description": "obfuscate/deobfuscate/verify build a release archive; the -direct actions write straight into a scripts folder",
                },
                "inputs": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Source .dsc files or directories (obfuscate, deploy)",
                },
                "release": {"type": "string", "description": "Release archive path (deobfuscate, verify)"},
                "directory": {"type": "string", "description": "Direct deployment folder (verify-direct, deobfuscate-direct)"},
                "output": {"type": "string", "description": "Output path for the action's result"},
                "root": {"type": "string", "description": "Base directory inputs are made relative to (deploy)"},
                "key": {"type": "string", "description": "Master key path; defaults to the installed key"},
                "project_id": {"type": "string", "description": "Project id salting the derived release key"},
                "mode": {
                    "type": "string",
                    "enum": ["hard", "balanced", "compat"],
                    "description": "hard hides containers and definitions; balanced keeps public container names; compat renames nothing",
                },
            },
            "required": ["action"],
        },
        module="dcore.pack.cli",
        argv=obfuscate_argv,
        tags=("pack", "opt-in"),
    ),
    Tool(
        name="dcore_project_audit",
        title="Audit a complete dCore project",
        description="Run one evidence-first audit over DenizenScript files and resource-pack/shader inputs in a project.",
        schema={
            "type": "object",
            "properties": {
                "paths": {"type": "array", "items": {"type": "string"}},
                **TARGET_SCHEMA,
                "closed_world": {"type": "boolean"},
                "db": {"type": "string"},
            },
            "required": ["paths"],
        },
        module="dcore.mcp.audit",
        argv=audit_argv,
        exit_is_findings=True,
        tags=("audit", "lint", "visual", "project"),
    ),
    Tool(
        name="dcore_lint_pack",
        title="Lint a resource pack",
        description=(
            "Lint a merged resource pack or shader pipeline directory/zip against a target pack format. "
            "Reports namespace and legacy post-program reference problems plus a runtime checklist."
        ),
        schema={
            "type": "object",
            "properties": {
                "input": {"type": "string", "description": "Resource-pack directory or zip archive"},
                "minecraft": {"type": "string", "description": "Target Minecraft version"},
                "pack_format": {"type": "number", "description": "Target pack format, integer or decimal"},
            },
            "required": ["input"],
        },
        module="dcore.lint.resourcepack",
        argv=pack_argv,
        exit_is_findings=True,
        tags=("lint", "visual"),
    ),
    Tool(
        name="dcore_shader_review",
        title="Review a shader pipeline",
        description="Run the resource-pack lint with an explicit shader-review workflow and runtime proof checklist.",
        schema={
            "type": "object",
            "properties": {
                "input": {"type": "string"},
                "minecraft": {"type": "string"},
                "pack_format": {"type": "number"},
            },
            "required": ["input"],
        },
        module="dcore.lint.resourcepack",
        argv=pack_argv,
        exit_is_findings=True,
        tags=("visual", "shader", "proof"),
    ),
    Tool(
        name="dcore_retrieve",
        title="Retrieve target-pinned evidence",
        description=(
            "Route a request to curated cards, exact Meta entries and route patterns for a resolved target. "
            "Use this before answering any Denizen question; it reports applicability and provenance, and "
            "says not_indexed rather than guessing."
        ),
        schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Focused engineering topic"},
                "meta_query": {"type": "string", "description": "Exact API lookup, for syntax questions"},
                "intent": {"type": "string", "description": "Routing intent; 'auto' by default"},
                **{key: value for key, value in TARGET_SCHEMA.items() if key != "require_jar_evidence"},
                "db": {"type": "string", "description": "Override the knowledge database path"},
            },
        },
        module="dcore.knowledge.retrieval",
        argv=retrieve_argv,
        tags=("knowledge",),
    ),
    Tool(
        name="dcore_design_compare",
        title="Compare candidate routes",
        description=(
            "Compare candidate implementation routes before writing code. Use only when genuine "
            "alternatives can change the design; an exact local fix does not need a route dossier. "
            "READY_FOR_PROOF means one route is the unique pre-code candidate, never runtime success."
        ),
        schema={
            "type": "object",
            "properties": {
                "dossier": {"type": "string", "description": "Path to a route dossier JSON"},
                "dossier_json": {
                    "type": ["object", "string"],
                    "description": "Inline route dossier, written to a temporary file",
                },
                "db": {"type": "string", "description": "Override the knowledge database path"},
            },
            "anyOf": [{"required": ["dossier"]}, {"required": ["dossier_json"]}],
        },
        module="dcore.design.routes",
        argv=design_argv,
        tags=("design",),
    ),
    Tool(
        name="dcore_versions",
        title="Read the version artifact registry",
        description=(
            "Read catalogued Denizen, Denizen-Core and DenizenM version artifacts with separate Meta and "
            "runtime proof states. Upstream discovery is not exposed here; this reads recorded evidence."
        ),
        schema={
            "type": "object",
            "properties": {
                "catalogue": {"type": "string", "description": "Path to an existing catalogue JSON to read"},
            },
        },
        module="dcore.knowledge.version_registry",
        argv=versions_argv,
        tags=("knowledge", "versions"),
    ),
    Tool(
        name="dcore_shadow",
        title="Simulate a bounded event session",
        description=(
            "Simulate a bounded queue/reservation/capacity/cleanup control plane. This is an intermediate "
            "proof layer only; it never replaces a Minecraft server runtime report."
        ),
        schema={
            "type": "object",
            "properties": {
                "plan": {"type": "string", "description": "Path to a shadow plan JSON"},
                "plan_json": {
                    "type": ["object", "string"],
                    "description": "Inline shadow plan, written to a temporary file",
                },
            },
            "anyOf": [{"required": ["plan"]}, {"required": ["plan_json"]}],
        },
        module="dcore.gates.shadow",
        argv=shadow_argv,
        tags=("gate", "simulation"),
    ),
    Tool(
        name="dcore_verify",
        title="Verify the dCore release",
        description="Validate the knowledge database and write a complete verified release manifest.",
        schema={
            "type": "object",
            "properties": {
                "root": {"type": "string"}, "knowledge": {"type": "string"},
                "db": {"type": "string"}, "output": {"type": "string"},
                "contract": {"type": "string"},
            },
            "required": ["output"],
        },
        module="dcore.release.verify",
        argv=verify_argv,
        tags=("release", "verification"),
    ),
    Tool(
        name="dcore_accept_agent",
        title="Run MCP agent acceptance",
        description="Run deterministic acceptance scenarios over the same MCP tool surface.",
        schema={"type": "object", "properties": {"db": {"type": "string"}}},
        module="dcore.acceptance.agent",
        argv=acceptance_argv,
        tags=("acceptance", "mcp"),
    ),
    Tool(
        name="dcore_accept_pool4",
        title="Run Pool 4 acceptance",
        description="Run the dCore golden acceptance corpus for source and runtime-boundary checks.",
        schema={"type": "object", "properties": {"phase": {"type": "string", "enum": ["pre", "post"]}}},
        module="dcore.acceptance.pool4",
        argv=pool4_argv,
        tags=("acceptance", "release"),
    ),
    Tool(
        name="dcore_release_gate",
        title="Run the release proof gate",
        description=(
            "Run the combined target, retrieval, route, addon/JAR, static and runtime proof gate. "
            "RELEASE_BLOCKED is the correct verdict when Minecraft runtime was not run; do not "
            "report a static pass as runtime success."
        ),
        schema={
            "type": "object",
            "properties": {
                **SCRIPT_INPUT_SCHEMA,
                **TARGET_SCHEMA,
                "closed_world": {"type": "boolean", "description": "Unresolved script references are errors"},
                "query": {"type": "string", "description": "Retrieval query recorded as evidence"},
                "require_route": {"type": "boolean", "description": "Demand a route decision artifact"},
                "decision": {"type": "string", "description": "Path to a recorded route decision JSON"},
                "runtime_report": {"type": "string", "description": "Path to a server runtime report"},
                "shadow_plan": {"type": "string", "description": "Path to a shadow simulation plan"},
                "db": {"type": "string", "description": "Override the knowledge database path"},
            },
            "anyOf": [{"required": ["paths"]}, {"required": ["text"]}],
        },
        module="dcore.gates.release",
        argv=release_gate_argv,
        exit_is_findings=True,
        tags=("gate", "release"),
    ),
)

BY_NAME = {tool.name: tool for tool in TOOLS}


def descriptors() -> list[dict[str, Any]]:
    return [tool.descriptor() for tool in TOOLS]


def call(name: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
    """Run one tool and return an MCP tool result."""
    tool = BY_NAME.get(name)
    if tool is None:
        return {
            "content": [{"type": "text", "text": f"unknown tool: {name}"}],
            "isError": True,
        }
    arguments = arguments or {}
    with tempfile.TemporaryDirectory(prefix="dcore-mcp-") as workspace:
        try:
            argv = tool.argv(arguments, Path(workspace))
        except (KeyError, ValueError, TypeError) as error:
            return {
                "content": [{"type": "text", "text": f"invalid arguments for {name}: {error}"}],
                "isError": True,
            }
        outcome = invoke(tool.module, argv)

    text = outcome.stdout.strip()
    failed = outcome.exit_code != 0 and not tool.exit_is_findings
    if failed or (not text and outcome.stderr.strip()):
        detail = outcome.stderr.strip() or f"exit code {outcome.exit_code}"
        return {"content": [{"type": "text", "text": detail}], "isError": True}
    result: dict[str, Any] = {"content": [{"type": "text", "text": text}]}
    if tool.exit_is_findings:
        # Report the gate verdict separately so an agent does not have to infer
        # "blocking findings exist" from the presence of text.
        result["structuredContent"] = {"blocking": outcome.exit_code != 0}
    return result
