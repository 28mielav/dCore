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

## Manual run

Open **Actions → Update dCore knowledge → Run workflow**.

## Initial files

The `bundle/` directory contains the last known-good seed. The workflow copies it to a temporary build directory and never mutates the seed until every mandatory validation passes.

