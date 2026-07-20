# dCore

Private source and maintenance repository for the dCore Custom GPT: a DenizenScript engineering assistant targeting Paper 1.21.11 and the maintained DenizenM line.

This repository keeps the last known-good Knowledge bundle, refreshes version-sensitive Meta sources, validates every candidate, publishes dated private releases, and exposes a minimal read-only freshness API to the Custom GPT.

## What is automated

Every Monday, and on manual request, GitHub Actions:

1. compares the indexed upstream commits;
2. updates Denizen, Denizen-Core, DenizenM, Voxizen, denizen-reflect and Refined DenizenScript metadata in an isolated database copy;
3. validates SQLite integrity, foreign keys, catalogue minimums and retrieval-test inventory;
4. installs and commits only a passing candidate;
5. deploys the verified manifest to the private Cloudflare bridge;
6. publishes a dated private release when Knowledge changed.

The last known-good database remains untouched when download, import or validation fails.

## What remains manual

Custom GPT Actions cannot replace files attached to GPT Knowledge. The Action can prove that a newer verified bundle exists, but the owner must still download the private dated release and replace the GPT Knowledge attachments when the SHA-256 differs.

## Repository layout

```text
knowledge/                  Last known-good GPT Knowledge and manifest
tools/                      Updater, validator and Denizen lint helper
services/update-bridge/     Read-only Cloudflare Worker
integrations/custom-gpt/    OpenAPI schema for the GPT Action
docs/                       Architecture and operating instructions
.github/workflows/          Scheduled maintenance pipeline
```

## Knowledge files

- `knowledge/dcore.sqlite` — authoritative maintained knowledge database and seed for future updates.
- `knowledge/DCORE_INSTRUCTIONS.txt` — dCore operating contract.
- `knowledge/manifest.json` — SHA-256, catalogue counts, validation result and exact upstream commits.

The SQLite file intentionally stays in this private repository. The updater refreshes external Meta inside an existing curated database; it cannot reconstruct the authored cards, routing rules and retrieval tests from upstream repositories alone.

## Normal operation

- Scheduled maintenance requires no intervention.
- Check workflow health under **Actions → Maintain dCore knowledge**.
- A green run with no new release means all indexed sources were already current.
- A new release is named only by its UTC date: `YYYY-MM-DD`.
- Detailed recovery and rotation procedures are in [docs/OPERATIONS.md](docs/OPERATIONS.md).

## Security boundary

- The repository and releases remain private.
- GitHub stores only the Cloudflare deployment token and account ID as Actions secrets.
- Cloudflare stores only `DCORE_ACTION_KEY`.
- The Custom GPT receives only the read-only Action key.
- The Worker returns health and the verified manifest; it cannot modify GitHub, Cloudflare or Knowledge.
- `DCORE_ACTION_KEY_PRIVATE.txt`, `.dev.vars` and other secrets must never be committed or uploaded as GPT Knowledge.

## Status API

- `GET /v1/health` — bridge health.
- `GET /v1/latest` — latest verified manifest.
- `GET /privacy` — public privacy policy.

The Custom GPT schema is [integrations/custom-gpt/openapi.yaml](integrations/custom-gpt/openapi.yaml).
