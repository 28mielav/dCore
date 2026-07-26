# dCore

Private source and maintenance repository for dCore, a multi-version DenizenScript and Minecraft resource-pack engineering GPT.

dCore is not tied to Paper 1.21.11. Each request resolves its own Minecraft/Paper, Denizen or DenizenM, addon and resource-pack versions. Version-neutral engineering rules are reusable; syntax, plugin bindings and rendering behavior remain pinned to evidence for the selected build.

## What 0.29 adds

- deterministic comparison of 2-4 implementation routes before code is written;
- a DenizenM-native-first gate, with addon, Reflect and console fallbacks kept behind explicit boundaries;
- executable bad/good contrast fixtures for code quality and shader design;
- a final-pack resource-pack/shader linter with route census and runtime proof plan;
- pinned public visual sources with commit, license, version and ingest policy;
- automatic upstream monitoring that marks changed visual sources `review_pending` instead of silently copying them;
- stricter clean-code, event blast-radius, ownership and lifecycle verification.

## Maintenance flow

GitHub Actions runs weekly and on demand:

1. copies the last verified SQLite database into an isolated build directory;
2. checks Denizen, Denizen-Core, DenizenM, Voxizen, denizen-reflect, Refined DenizenScript and registered visual sources;
3. refreshes source Meta and IDE diagnostics; visual source changes are recorded for human review;
4. applies curated migrations;
5. runs unit, retrieval, integrity, provenance and artifact validation;
6. commits only a passing candidate, deploys the read-only freshness bridge and publishes a private UTC-dated release.

A failed download, import or test never replaces the last known-good database.

## Repository layout

```text
knowledge/                  Canonical database, GPT instructions and manifest
tools/                      Retrieval, route decision, lint, updater and tests
services/update-bridge/     Read-only Cloudflare freshness API
integrations/custom-gpt/    Custom GPT OpenAPI schema
docs/                       Architecture and operating procedure
.github/workflows/          Scheduled verified maintenance
```

## Custom GPT attachment set

Upload exactly these Knowledge files:

- `knowledge/dcore.sqlite`
- `knowledge/manifest.json`
- `tools/retrieval.py`
- `tools/dcore_lint.py`
- `tools/dcore_design.py`
- `tools/dcore_rp_lint.py`
- `knowledge/lint_contract.example.json`

Paste `knowledge/DCORE_INSTRUCTIONS.txt` into the GPT Instructions field; it is not a Knowledge attachment.

The SQLite file intentionally remains versioned in this private repository. Public Meta cannot reconstruct the authored cards, routing graph, contrast corpus, source policies or retrieval tests. The repository database is the reproducible update seed and rollback point, while private releases are immutable distribution snapshots.

## Public source policy

`knowledge/visual_sources.json` registers external repositories by exact commit. Licensed material may be studied under its recorded policy. Missing-license sources are reference-only: dCore may extract facts and architecture, but must not redistribute their code. Historical shader packs are mechanisms to port and test, never proof of current compatibility.

## Manual boundary

GitHub Actions and the Cloudflare bridge can report a newer verified bundle, but the Custom GPT platform cannot replace its own attached Knowledge. The owner must download the private release and replace the seven files when `bundle_sha256` changes.

See [Architecture](docs/ARCHITECTURE.md) and [Operations](docs/OPERATIONS.md).
