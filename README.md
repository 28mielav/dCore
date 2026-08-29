# dCore

**dCore is a target-pinned engineering tool for building, reviewing, and verifying DenizenScript systems.**

It gives developers and coding agents one evidence-first workflow across exact Minecraft, Paper, Java, Denizen, DenizenM, addon, resource-pack, and shader targets.

## Deliveries

| Delivery | Where it runs | What it contains |
|---|---|---|
| CLI | Local Python | Full dCore engine and canonical knowledge database |
| Skill | Codex, Claude Code, Cursor, Antigravity | Full engine, database, workflow and platform adapters |
| Custom GPT | ChatGPT Code Interpreter | Full engine and database for uploaded-project analysis |

All deliveries are built from the same `dcore/` source and one canonical SQLite database at `dcore/knowledge/data/dcore.sqlite`.

## Core capabilities

- exact-target retrieval and version compatibility checks;
- DenizenScript syntax, lifecycle, queue, event-scope, ownership, and DenizenM lint;
- resource-pack and shader graph validation;
- architecture-route comparison before non-trivial implementation;
- explicit separation of source, static, API/JAR, server, and client evidence.

## Run locally

```bash
python -m pip install -e .
dcore retrieve --help
dcore lint --help
dcore lint-pack --help
dcore design --help
dcore versions --help
```

The canonical Skill is `skill/dcore/`. Its optional deployment shims live in `skill/dcore/adapters/`; the repository deliberately has no root editor adapters.

## Evidence boundary

`STATIC_OK` means configured static checks passed. It does not prove a server accepted a command, an addon API exists in an installed JAR, or a client rendered a resource pack correctly.

Version-sensitive implementation requires an explicit target matrix. Without one, dCore returns a target requirement or a version-neutral probe rather than invented syntax.

## Verification and builds

```bash
python -m pytest -q
dcore verify-skill --root . --json
dcore build-cli --root . --output build/dcore-cli
dcore build-skill --root . --output build/dcore-skill.zip
dcore build-gpt --root . --output build/dcore-gpt
```

See [CONTRIBUTING.md](CONTRIBUTING.md), [Architecture](docs/ARCHITECTURE.md), and [Operations](docs/OPERATIONS.md).

## License and name

The public source is MIT licensed. Third-party source facts remain attributed and license-gated. The dCore name and branding are covered by [TRADEMARKS.md](TRADEMARKS.md).
