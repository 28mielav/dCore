# Evidence and version discipline

## Target matrix

Before code, record a matrix instead of one ambiguous "version":

| Field | Required evidence |
|---|---|
| Minecraft client | exact release or snapshot id |
| Resource pack | exact format number and pack metadata |
| Server | exact Minecraft and Paper/build |
| Java | major version |
| Denizen | build/tag/commit and Meta source |
| DenizenM/addons | build/JAR hash or explicit unknown |
| Rendering | backend, graphics mode, window size, GUI scale |

A missing field is `UNKNOWN`, not "latest". Select API/tag/mechanism facts from target-pinned Meta or an inspected JAR. Current documentation is only evidence for the current version it describes.

## Evidence ladder

1. `SOURCE_EVIDENCE`: a pinned primary source, exact artifact, or inspected runtime file supports the claim.
2. `STATIC_OK`: syntax/structure/linkage rules configured for the target pass.
3. `COMPILE_OK`: the exact server, script engine, or client compiler accepts the artifact.
4. `CLIENT_LOG_OK`: the pinned client log contains no relevant load/compile/link error and identifies the tested resource.
5. `RUNTIME_OK`: a named manual or automated scenario produced its expected observable result.

Higher states do not erase lower artifacts. Record commands, inputs, literal outputs, hashes, and environment. `STATIC_OK` never implies `COMPILE_OK` or `RUNTIME_OK`.

## Changing Minecraft shader profiles

Treat shader layout, global uniforms, includes, program JSON, pack format, and commands as a profile, not timeless API. For 26.3 snapshots, pin the snapshot. Snapshot 3 introduced `/posteffect` with resource-pack format 91.0; later snapshots changed resource-pack format and compilation behavior. Revalidate examples before carrying them forward.

## Claim template

```text
TARGET: Minecraft ___; pack format ___; backend ___; Denizen ___; DenizenM ___
ARTIFACT: path/hash ___
CLAIM: ___
EVIDENCE: SOURCE_EVIDENCE | STATIC_OK | COMPILE_OK | CLIENT_LOG_OK | RUNTIME_OK | RUNTIME_UNVERIFIED
COMMAND: ___
OBSERVED: ___
LIMITATION/NEXT TEST: ___
```

## Retrieval

Use `dcore retrieve --help` and pass explicit target selectors where supported. If retrieval returns multiple versions, prefer exact target records, then compatible range records, then version-neutral architecture. Do not silently use a foreign-version record. For addon behavior absent from indexed evidence, inspect the installed JAR or label the API surface unverified.
