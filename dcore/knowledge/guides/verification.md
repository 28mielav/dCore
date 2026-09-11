# Verification and build gates

## Static commands

```bash
python -m pytest -q
dcore lint path/to/project --help
dcore validate-shader path/to/merged-pack --minecraft <client-version> --pack-format <format> --json
dcore verify-skill --root . --json
dcore build-skill --root . --output build/dcore-skill.zip
```

Save the literal command, input path/hash, stdout/stderr, and exit status. Re-run against the final merged resource pack or ZIP; validating source fragments does not validate pack precedence.

## Shader evidence record

Every shader example/build note must contain:

- exact target and pack format;
- complete file list and hashes;
- activation/deactivation/list/clear commands;
- expected visible result;
- actual static, compile, client-log, and gameplay results as separate fields;
- limitations and unrun tests;
- graphics backend/mode, resolution, GUI scale, camera, pack order, and FPS method.

Use a project-specific runtime matrix. Replace `RUNTIME_UNVERIFIED` only with a dated observation and attached log/capture reference.

## Release decision

A portable-skill build requires:

1. canonical `skill/dcore/SKILL.md` validates and routes every reference;
2. adapters remain thin and contain no duplicated domain knowledge;
3. no MCP runtime or vendor-specific core dependency exists;
4. Python tests pass;
5. bundle build is deterministic (same content yields same hash);
6. build verification reports runtime evidence rows honestly.

Build integrity never upgrades a visual claim to `RUNTIME_OK`. A production-ready visual claim requires client-log and manual matrix evidence.

## Failure triage

Stop at the first failing layer:

- malformed/missing files -> fix packaging;
- graph/program/stage linkage -> fix static route;
- client compile/link log -> fix exact profile syntax/interface;
- constant tint absent -> fix activation or fullscreen route;
- tint works but animation does not -> prove time uniform update;
- animation works but level/cleanup fails -> fix bridge ownership;
- matrix/FPS regression -> bound algorithm or choose another route.
