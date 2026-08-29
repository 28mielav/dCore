# dCore

**dCore is an evidence-first engineering tool for DenizenScript and DenizenM.**

It gives server developers and coding agents a deterministic workflow for designing, reviewing, linting, testing, and maintaining Minecraft mechanics against exact Minecraft, Paper, Java, Denizen, DenizenM, addon, and resource-pack targets.

## Builds

| Build | Purpose | Runs the dCore core |
|---|---|---:|
| CLI | Local deterministic tooling | Yes |
| Skill | Codex, Claude Code, Antigravity, and Cursor workflow | Yes |
| GPT | Code Interpreter analysis of uploaded projects | Yes |

All builds are generated from the same Python core and target-pinned knowledge database. A build must pass parity verification before it is usable.

## Core capabilities

- exact-target Meta and knowledge retrieval;
- DenizenScript syntax, lifecycle, queue, event-scope, and ownership lint;
- resource-pack and shader graph validation;
- architecture-route comparison before non-trivial implementation;
- explicit separation of source, static, compile, client-log, and runtime evidence.

Resource-pack and shader work is an optional dCore route. It never overrides the Denizen/DenizenM engineering core.

## Install and run

Python 3.12+:

```bash
python -m pip install -e .
dcore retrieve --help
dcore lint --help
dcore lint-pack --help
dcore design --help
dcore versions --help
```

Install the canonical Skill directory directly:

```bash
# Codex
cp -R skill/dcore "$CODEX_HOME/skills/dcore"

# Antigravity
mkdir -p .agents/skills
cp -R skill/dcore .agents/skills/dcore
```

`AGENTS.md`, `CLAUDE.md`, and `.cursor/rules/dcore.mdc` are thin routers to the same canonical Skill.

## Evidence boundary

`STATIC_OK` means configured static checks passed. It does not prove that a server accepted a command, an addon API exists in an installed JAR, or a client rendered a resource pack correctly.

Version-sensitive implementation requires an explicit target matrix. When it is absent, dCore returns a target requirement or a version-neutral architecture/probe instead of invented syntax.

## Development

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
