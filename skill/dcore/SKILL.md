---
name: dcore
description: Evidence-first DenizenScript and DenizenM engineering across exact targets; use for design, implementation, lint, compatibility, and runtime proof planning. Load the optional visual route only for resource-pack or shader work.
---

# dCore

Engineer DenizenScript and DenizenM systems from evidence rather than plausible syntax. Resource packs and shaders are an optional route, not the default identity of this skill. Preserve the user's architecture unless the target makes it impossible.

## Start with the target and claim

Record Minecraft client, server/Paper, Java, Denizen, DenizenM, addons, resource-pack format, graphics backend/mode, and the artifact actually inspected. Mark unknown fields explicitly. Do not borrow current Meta or shader behavior for another build.

Classify each conclusion as `SOURCE_EVIDENCE`, `STATIC_OK`, `COMPILE_OK`, `CLIENT_LOG_OK`, `RUNTIME_OK`, or `RUNTIME_UNVERIFIED`. A clean linter is never runtime proof. A server command succeeding does not prove that a client resource exists or rendered.

## Route the work

- Denizen syntax, tags, mechanisms, events, queues, flags, addons, reloads, or lifecycles: read [Denizen engineering](references/0.75/denizen-engineering.md).
- Version or evidence questions: read [Evidence and versions](references/0.75/evidence-and-versions.md).
- Core shaders, stages, inputs, uniforms, blend/depth/cull, NDC, framebuffers, post effects, or pack composition: read [Core shader pipeline](references/0.75/core-shader-pipeline.md), [Post-effect engineering](references/0.75/post-effects.md), and [1.21.x compatibility](references/0.75/minecraft-1.21.md).
- Minecraft 1.21.x visual work: read [1.21.x compatibility](references/0.75/minecraft-1.21.md). Do not describe overlays or entity-outline routing as native arbitrary post-effect activation.
- Verification or build work: read [Verification](references/0.75/verification.md).
- Source attribution or a changing shader claim: read [Sources](references/0.75/sources.md) and verify the pinned primary source.

## Engineering loop

1. Retrieve target-scoped evidence with `dcore retrieve` before inventing API.
2. Compare routes when ownership, lifecycle, or client capability differs materially.
3. Define state owner and complete lifecycle: start, update, stop, interruption, death, quit, reconnect, reload, and cleanup.
4. Implement the smallest proof. For shaders, prove a constant fullscreen tint before animation, levels, distortion, blur, or server bridges.
5. Run deterministic static checks. Use `dcore lint` for `.dsc` and `dcore validate-shader` for packs.
6. Record compile/client log and manual gameplay results separately, including failures and unrun matrix cells.
7. Build with the relevant `dcore build-*` command only after the static gate passes. Runtime status remains separate from build integrity.

## Non-negotiable boundaries

- Treat every shader profile as target-pinned. Pin client version and pack format; shader syntax and render behavior change between versions.
- Resource packs contain client resources. The server cannot infer that a named post effect exists or rendered on a client.
- `entity_outline` is a useful mask target when the render graph supplies it. It is not a magic per-player fullscreen trigger.
- Resource-pack-only code cannot read arbitrary server state. Choose an explicit bridge and a neutral missing-state decode.
- Every shader example must state target, pack format, all file paths, activation command, expected result, actual evidence, and limitations.
- Never fabricate `RUNTIME_OK`. If a client log and manual run are absent, finish at `RUNTIME_UNVERIFIED` with the exact next test.
