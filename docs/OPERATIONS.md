# Operations

## Local setup

```bash
python -m pip install -e .
python -m pytest -q
```

## Verify the portable build

```bash
dcore verify-skill --root . --json
dcore validate-shader path/to/merged-pack --minecraft <client-version> --pack-format <format> --json
dcore verify --root . --output temp/manifest.verify.json
```

The shader command proves static structure only. Keep a runtime matrix for the exact Minecraft client and manual test session.

## Build and install

```bash
dcore build-skill --root . --output build/dcore-skill.zip
```

Install `skill/dcore/` directly for Codex, expose the same `SKILL.md` to Claude Code, copy it under `.agents/skills/dcore/` for Antigravity, or use the Cursor routing adapter. Do not duplicate references into adapters.

## Update knowledge

Run source refresh and migrations against an isolated database copy, validate retrieval/integrity, then replace `knowledge/dcore.sqlite` and regenerate `knowledge/manifest.json`. A failed candidate never replaces the current database.

## Build checklist

- tests pass;
- `verify-skill` returns `BUILD_OK` and `runtime=RUNTIME_UNVERIFIED` or a separately evidenced runtime state;
- each included visual fixture passes static validation;
- two bundle builds have the same SHA-256;
- manifest is regenerated from the final tree;
- changelog matches the build.
