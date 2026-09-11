---
name: dcore
description: Implement, teach, or review DenizenScript and DenizenM projects; analyze resource packs, core shaders and post effects against exact client versions.
---

# dCore

Use the installed Skill directory as the anchor. Run `python <skill-directory>/scripts/dcore.py <command>` from any working directory. Its `runtime/` contains the shared engine, database, guides and examples. Python 3.12+ is required. Basic analysis uses the standard library; encrypted packing additionally needs cryptography.

## Match the requested work

dCore is multiversion: the intended range is Minecraft 1.16.5 through the latest Minecraft version supported by Denizen. 1.21.8 and 1.21.11 are priority targets, not an allowlist or upper bound. Select evidence for the actual target; gaps in indexed schemas remain explicit.

- Implementation: deliver the requested complete patch or files, including the setup needed to use them. A small fix needs a short explanation and focused checks.
- Teaching: explain one mechanism with a runnable example, give a manageable next step, and check understanding before adding complexity.
- Review: report concrete findings with locations, consequences and repairs. Distinguish proven errors from suspicions and unknown APIs.

Inspect supplied files and determine versions relevant to the task. Use `retrieve --query "..."` for recipes and `retrieve --meta-query "..."` for exact API; pass `--denizenm BUILD` or `--profile official --denizen-version BUILD` where known. A project `dcore.toml` can retain the target. Missing versions limit version-sensitive claims, not unrelated progress.

Run `lint <project>` or `lint-pack <pack> --minecraft VERSION --pack-format FORMAT --graphics-mode MODE`. Use `--json` for automation. Read the diagnostic reason and evidence; do not rewrite working code merely to silence an advisory.

Prefer a verified native DenizenM capability when it meets the task. For a complex mechanism compare feasible routes briefly, then implement the selected route with ownership, interruption and cleanup. Loops need bounded work and a credible lifetime; `while true` and if/else are not bugs by themselves. Replacing a loop with infinitely rescheduled queues is not a universal fix.

Use natural speech and meaningful container names. Do not insert dcore into user flags, permissions or scripts. Do not infer AI authorship from code style. Preserve public names unless the requested change needs a migration.

## Read only relevant shared material

- [Denizen engineering](runtime/dcore/knowledge/guides/denizen-engineering.md): queues, scope and API boundaries.
- [Visual workbench](runtime/dcore/knowledge/guides/visual-workbench.md): complete teaching packs, activation, buffers, cost and verification.
- [Core shader pipeline](runtime/dcore/knowledge/guides/core-shader-pipeline.md) and [post effects](runtime/dcore/knowledge/guides/post-effects.md): interfaces and version boundaries.
- [1.21 compatibility](runtime/dcore/knowledge/guides/minecraft-1.21.md): distinguish outline, menu and arbitrary post-effect routes.
- [Evidence and versions](runtime/dcore/knowledge/guides/evidence-and-versions.md), [verification](runtime/dcore/knowledge/guides/verification.md), [sources](runtime/dcore/knowledge/guides/sources.md).

For visuals, pin client, pack format, renderer and graphics mode. First validate a small visible effect on the actual route; then add controls or blur. World, HUD and GUI are different draw boundaries. A route's limitation does not apply to every implementation. No subsystem called Vision is defined here: resolve that ambiguous name from the user's files or description.

For visual work, primary tested schema targets are 1.21.11 and 1.21.8; select the user's actual version and retain historical support. Read the compatibility guide before diagnosing attachment. Mount, a visible diagnostic band and clean reload logs prove different things; none alone proves a working fullscreen effect.

Report what was actually run. Static checks do not execute Paper or a GPU. A supplied runtime report remains user-reported even when its project hash and versions match. Give exact next client/server checks for remaining gaps without claiming they passed.
