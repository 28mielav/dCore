# Contributing to dCore

## Before opening a change

1. Keep `skill/dcore/SKILL.md` canonical and adapters thin.
2. Pin target claims to exact Minecraft, resource-pack, Denizen, DenizenM, and addon versions.
3. Preserve the proof boundary: static output, compile/client logs, and gameplay observations are separate.
4. Add a focused regression test for behavior changes.
5. Record source revision and license policy; do not redistribute reference-only code.

## Local verification

```bash
python -m pytest -q
dcore verify-skill --root . --json
dcore validate-shader path/to/merged-pack --minecraft <client-version> --pack-format <format> --json
dcore build-skill --root . --output build/dcore-skill.zip
```

## Pull requests

Describe targets, evidence changed, user-visible behavior, commands and literal results, runtime rows not executed, and migration impact. Keep caches, local logs, secrets, upstream clones, and generated build directories out of the tree.
