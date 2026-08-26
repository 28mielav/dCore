"""Prompts that put the dCore gates in front of the work, not after it.

A resource is only read if the agent decides to read it. A prompt is something a
user can invoke directly, so the local-evidence gate and the execution gate stop
depending on the client having loaded the instructions first.

Each prompt is a small template over the same policy text the instructions
resource carries; nothing here restates lint rules or version policy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Argument:
    name: str
    description: str
    required: bool = False


@dataclass(frozen=True)
class Prompt:
    name: str
    title: str
    description: str
    template: str
    arguments: tuple[Argument, ...] = field(default_factory=tuple)

    def descriptor(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "arguments": [
                {"name": item.name, "description": item.description, "required": item.required}
                for item in self.arguments
            ],
        }

    def render(self, arguments: dict[str, Any]) -> dict[str, Any]:
        values = {item.name: str(arguments.get(item.name) or "") for item in self.arguments}
        missing = [item.name for item in self.arguments if item.required and not values[item.name]]
        if missing:
            raise ValueError(f"missing required argument(s): {', '.join(missing)}")
        text = self.template.format(**values)
        return {
            "description": self.description,
            "messages": [{"role": "user", "content": {"type": "text", "text": text}}],
        }


PROMPTS: tuple[Prompt, ...] = (
    Prompt(
        name="dcore_task",
        title="Run a Denizen task through the dCore gates",
        description="Apply the local-evidence and seven-step execution gates to a Denizen work request.",
        arguments=(
            Argument("request", "What the user wants built, fixed or changed", required=True),
            Argument("target", "Known target versions, such as 'paper 1.21.11, denizenm 7299M, reflect 2.4.2'"),
        ),
        template="""Read dcore://instructions before starting.

Request: {request}
Declared target: {target}

Work the gates in order and do not skip a step because the request looks small:

1. Inspect the actual project files, ownership, lifetime, persistence, failure
   paths and cleanup before proposing anything.
2. Resolve the target matrix. If a version-sensitive fact is needed and the target
   is missing, ask for it rather than merging facts across builds.
3. Call dcore_retrieve for the evidence. Compare native DenizenM, a dedicated
   addon and Reflect. Reflect goes behind one narrow adapter or not at all.
4. Design the smallest complete state shape: one authoritative writer, one
   lifecycle owner, one cleanup owner, bounded loops and queues.
5. Implement the complete in-scope change.
6. Call dcore_lint over the whole project, closed_world when it is complete.
7. Report changed files, static results, JAR evidence, runtime proof and what
   remains unknown. Static success is not runtime success.

Show findings as a table: severity, code, location, problem, fix.""",
    ),
    Prompt(
        name="dcore_review",
        title="Review Denizen code for production risk",
        description="Review supplied Denizen code against the clean production rules without editing it.",
        arguments=(
            Argument("paths", "Files or directories to review", required=True),
            Argument("target", "Known target versions"),
        ),
        template="""Read dcore://instructions before starting. This is a diagnosis, so do not
silently edit the project.

Review: {paths}
Declared target: {target}

Call dcore_lint over everything supplied, then judge what the linter cannot see:
event blast radius and identity guards before mutation, a single authoritative
writer per connected fact, one cleanup owner per acquired resource, bounded scans
and queues, live references revalidated after wait, movement ownership, and
ceremonial structure that carries no weight.

Review observable code risk only. Never infer authorship or effort from style.

Report a table of severity, code, location, problem and fix, then the risks that
need runtime proof rather than static argument.""",
    ),
    Prompt(
        name="dcore_project_audit",
        title="Audit a complete dCore project",
        description="Run the unified script, visual, evidence and proof audit over a project.",
        arguments=(
            Argument("paths", "Project files or directories", required=True),
            Argument("target", "Exact Minecraft, Paper, Denizen or DenizenM target"),
        ),
        template="""Read dcore://instructions, dcore://architecture and dcore://manifest first.

Project: {paths}
Target: {target}

Call dcore_project_audit over the supplied project. Then use dcore_retrieve for any
version-sensitive claim, dcore_shader_review for resource-pack inputs, and
dcore_release_gate when the project is intended for release. Separate static
findings, semantic findings and runtime proof requirements. Do not call
maintenance or obfuscation operations unless explicitly requested.""",
    ),
    Prompt(
        name="dcore_shader_review",
        title="Review a Minecraft shader pipeline",
        description="Review a resource-pack shader pipeline and produce a runtime proof checklist.",
        arguments=(
            Argument("input", "Resource-pack directory or ZIP", required=True),
            Argument("target", "Minecraft version and pack format"),
        ),
        template="""Read dcore://instructions and dcore://manifest first.

Shader input: {input}
Target: {target}

Call dcore_shader_review. Report stage linkage, imports, uniforms, samplers,
attributes, varyings, post-processing routes, static verdict and every runtime
check still required in Minecraft. Never convert STATIC_OK into runtime success.""",
    ),
    Prompt(
        name="dcore_release_review",
        title="Review dCore release readiness",
        description="Run the complete release and OSS verification workflow.",
        arguments=(Argument("paths", "Project paths", required=True),),
        template="""Read dcore://instructions, dcore://operations and dcore://manifest.

Project: {paths}

Run dcore_project_audit, dcore_verify, dcore_accept_agent and the relevant
release gate. Check CLI/MCP parity, GPT bundle inputs, documentation, manifests,
fixtures and runtime proof boundaries. Return a release checklist with exact
blocking items and verified results.""",
    ),
)

BY_NAME = {prompt.name: prompt for prompt in PROMPTS}


def descriptors() -> list[dict[str, Any]]:
    return [prompt.descriptor() for prompt in PROMPTS]


def render(name: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
    prompt = BY_NAME.get(name)
    if prompt is None:
        raise KeyError(name)
    return prompt.render(arguments or {})
