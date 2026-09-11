# Operations

## Local setup

```bash
python -m pip install -e ".[dev,obfuscation]"
python -m pytest -q
```

## Verify and build

```bash
dcore verify-skill --root . --json
dcore verify --root . --output dcore/knowledge/data/manifest.json
dcore build-cli --root . --output build/dcore-cli
dcore build-skill --root . --output build/dcore-skill.zip
dcore build-gpt --root . --output build/dcore-gpt
```

Ready deliveries stay under ignored `build/`. Technical checks and previews use `.dcore-work/` or isolated temporary directories. The source of truth is `dcore/`, the portable Skill is `skill/dcore/`, and Custom GPT instructions are `gpt/INSTRUCTIONS.txt`.

## Platform adapters

The repository has no root `AGENTS.md`, `CLAUDE.md`, `.agents`, or `.cursor` files. If a consuming editor requires one, copy the matching short shim from `skill/dcore/adapters/` into that consumer only.

## Update canonical knowledge

Run source refresh and migrations against an isolated copy. Validate retrieval and integrity, then replace `dcore/knowledge/data/dcore.sqlite` and regenerate `dcore/knowledge/data/manifest.json`. A failed candidate never replaces the last verified database.

## Evidence boundary

The shader command proves static structure only. Keep a runtime matrix for the exact Minecraft client and manual test session. `STATIC_OK` is not runtime proof.

## Build checklist

- verification passes;
- `verify-skill` returns `BUILD_OK` and `runtime=RUNTIME_UNVERIFIED` unless separately evidenced;
- the canonical database and manifest are current;
- CLI, Skill, and GPT builds succeed from the same tree;
- the GPT instructions stay within 8,000 characters;
- changelog matches the build.

## Installed entrypoints

CLI: `python /path/to/dcore-cli/dcore.py lint /path/to/project`.
Skill: install the entire extracted dcore folder, then use `python /path/to/dcore/scripts/dcore.py lint /path/to/project`. Its runtime is inside the Skill, and adapters locate the installed Skill rather than the source checkout.
GPT: follow [setup](../gpt/BUILD.md). The Python bootstrap is tested independently; hosted upload accessibility remains a separate check.

## Reusable target and evidence

Put versions under [target] in dcore.toml. The nearest parent config applies and command flags override it. Recognized keys: minecraft, paper, java, denizen_version, denizenm, profile, pack_format, graphics_mode and renderer; each command receives only keys it supports.

`run` emits project_sha256 (a SHA-256 of the sorted per-input UTF-8 text hashes). A report must carry that hash, matching environment values and provenance.runner/timestamp/method. Required cases are a map of scenario names to PASS. A supplied report remains RUNTIME_USER_REPORTED and cannot unlock READY: origin metadata is not independent authentication. The built-in scenario selection is a heuristic checklist, not a complete project test plan.
