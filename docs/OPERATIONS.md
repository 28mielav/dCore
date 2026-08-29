# Operations

## Local setup

```bash
python -m pip install -e .
python -m pytest -q
```

## Verify and build

```bash
dcore verify-skill --root . --json
dcore build-cli --root . --output build/dcore-cli
dcore build-skill --root . --output build/dcore-skill.zip
dcore build-gpt --root . --output build/dcore-gpt
```

All generated outputs stay under ignored `build/`. The source of truth is `dcore/`, the portable Skill is `skill/dcore/`, and Custom GPT instructions are `gpt/INSTRUCTIONS.txt`.

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
