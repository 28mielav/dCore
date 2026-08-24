# dCore

dCore is a version-aware engineering system for DenizenScript and Minecraft visual engineering, designed to turn GPT into a specialized engineering assistant for the Denizen ecosystem.

dCore is built for serious Denizen development rather than generic Minecraft scripting. Denizen is a mature scripting engine used by established Minecraft server projects for gameplay systems, automation, NPCs, effects, interfaces and complex server-side behavior.

The problem is that Denizen development is highly version-sensitive. Minecraft/Paper, Denizen, DenizenM, addons, Java APIs and client-side resource-pack/rendering capabilities can all differ between builds. A generic LLM can produce plausible-looking code while silently mixing APIs, inventing mechanisms or applying techniques from the wrong version.

dCore solves this by resolving the target environment first and grounding engineering decisions in version-pinned evidence, structured knowledge, retrieval tests, static analysis and explicit proof states.

The goal is simple: make GPT substantially better at producing, reviewing, debugging and explaining real Denizen code and complex visual/resource-pack systems.

> **Current development status**
>
> The public `main` branch currently contains an older public snapshot.
>
> **dCore 0.62 is the current development release.**
>
> 0.62 was developed and refined through a closed beta period focused on finding implementation, retrieval, compatibility, linting and workflow issues before the next public release.
>
> The public repository will be updated to 0.62 after the final cleanup and validation pass.

## What 0.62 adds

0.55 established the frozen baseline.

0.56 added a hard proof-state release gate: a static result can no longer quietly be promoted to a runtime claim.

0.58 introduced **DenizenCore-lite**, a source-derived and MIT-attributed Python semantic layer under dCore-lint. It builds command entries, scopes container definitions, fills portable queue/context tags and evaluates `if`, `choose`, `repeat`, `while` and `stop` without pretending to execute Bukkit or Minecraft.

0.61 introduced **project-wide queue proof**:

- cross-file `run` traversal;
- shared-queue `inject`;
- static/dynamic `wait` boundaries;
- MapTag foreach fixtures;
- classified lifetime reports for semantic execution limits.

0.62 adds **explicit queue fixtures and confidence policy**:

- input/platform gaps are not treated as errors;
- dynamic wait limitations become P1 warnings;
- only a fixture identifying the exact source path can lower such a finding to an informational runtime-boundary state.

The 0.62 development line also includes:

- human-first delivery: retrieval, route dossiers and machine lint stay backstage;
- stable Markdown lint tables with severity, code, location, problem and fix;
- control-flow detection after terminal `determine`/`stop`;
- flexible container indentation and ceremonial-task review;
- namespace-aware legacy post-program reference validation;
- explicit `DECISION_REPRODUCED` instead of a misleading generic verification `PASS`;
- proportional design gates: complex choices compare routes while exact local fixes remain local;
- two independent generated products: a local Codex Skill and a Custom GPT bundle;
- one canonical knowledge database and one updater, with no hand-maintained copies;
- a hard teaching gate with bounded fragments/exercises instead of automatically dumping complete scripts;
- worked-example fading, user attempts, feedback and transfer checks;
- anti-vibe review based on observable engineering risk rather than alleged authorship;
- consistent lint policy for DenizenM and documented Reflect boundaries;
- target-aware linting for Minecraft, Paper, Java, DenizenM, addons and exact JAR evidence;
- a version-artifact registry for Denizen, Denizen-Core and DenizenM tags/branches;
- separate Meta and runtime proof states;
- structural Reflect invocation checks without confusing syntax validity with Java signature proof;
- release-policy cards for target resolution, Reflect boundaries and verified manifests;
- target-pinned historical Meta snapshots so old targets cannot borrow current syntax;
- evidence-backed addon compatibility records instead of guessed major-version ranges;
- structured version scopes enforced by retrieval as applicable, deferred or not-applicable advice;
- overlay-based historical Meta, storing identical API rows once while preserving exact old-build differences;
- dog-search session architecture with explicit phases, one state owner and idempotent cleanup;
- dog-navigation lint gates for `walk` ownership conflicts, path replacement without `stop` and `on tick` repathing;
- a deterministic acceptance suite of representative Denizen scenarios;
- `dcore_run.py`, exposing target, retrieval, route, addon/JAR, static and runtime proof states with `RELEASE_BLOCKED` until required evidence passes;
- bounded four-player event-session architecture using queue tickets, worker reservations, capacity telemetry and idempotent cleanup instead of an unbounded global event loop.

## Why version awareness matters

dCore does not assume that the newest API is automatically correct.

For every request, the system can resolve:

- Minecraft version;
- Paper version;
- Denizen version;
- DenizenM version;
- addon versions;
- exact JAR evidence;
- resource-pack/client target;
- historical API differences.

Version-neutral engineering principles remain reusable, but syntax, plugin bindings, Java/Reflect behavior and rendering capabilities remain pinned to evidence for the selected build.

This allows the same system to reason about both current and historical Denizen environments without silently borrowing modern syntax for an older target.

## Architecture

```text
pinned public sources + authored rules
                |
                v
       isolated SQLite candidate
                |
     migrations + executable tests
                |
                v
 private last-known-good repository
       |                    |
       v                    v
 dated owner bundles   freshness API
