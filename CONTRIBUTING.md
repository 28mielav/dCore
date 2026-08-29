# Contributing to dCore

## Before opening a change

1. Open an issue for a new rule, source, target, or design change that affects public behavior.
2. Keep target claims version-scoped. Do not describe a current API as evidence for an older build.
3. Preserve the proof boundary. Static analysis, source evidence, and Minecraft runtime verification are separate claims.
4. Add or update a focused regression test for every behavior change.

## Local verification

```bash
python -m unittest discover -s tests -v
python -m dcore.release.verify --db knowledge/dcore.sqlite --output temp/manifest.verify.json
```

## Contributions involving sources

Record exact upstream revisions and their license status. A source without a redistributable license can inform a fact or mechanism but must not be copied into dCore.

## Pull requests

Describe the target versions, evidence changed, user-visible behavior, and verification commands. Keep unrelated formatting or generated artifacts out of the change.
