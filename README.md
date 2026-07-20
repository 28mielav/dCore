# dCore private updater

Private update pipeline for the dCore Custom GPT knowledge bundle.

## Operation

- Runs weekly and on manual dispatch.
- Checks the configured Denizen/DenizenM/addon repositories and the latest Refined DenizenScript release.
- Rebuilds the SQLite database only when upstream revisions changed.
- Validates SQLite integrity, foreign keys, minimum catalogue sizes, and retrieval expectations.
- Publishes a private GitHub Release containing the verified bundle.
- Keeps the last known-good database when download, import, or validation fails.

The repository and its releases must remain private. No GitHub Pages deployment is used.

## Private GPT update bridge

`cloudflare/` contains a minimal read-only Worker. It exposes only health and
latest verified manifest endpoints. Only the GPT action key is stored as a
Cloudflare secret; no GitHub token is exposed to the Worker. Cloudflare's Git
integration rebuilds the Worker after the verified manifest changes.
`action/openapi.yaml` is the
schema to paste into the Custom GPT Actions editor after replacing its server
URL with the deployed `workers.dev` address.

## Manual run

Open **Actions → Update dCore knowledge → Run workflow**.

## Initial files

The `bundle/` directory contains the last known-good seed. The workflow copies it to a temporary build directory and never mutates the seed until every mandatory validation passes.
