# Architecture

## Canonical delivery

`skill/dcore/SKILL.md` is the portable entrypoint. Shared guides under `dcore/knowledge/guides/` contain detailed knowledge and route-specific procedures. IDE files are deliberately thin adapters; they do not fork the knowledge base.

```mermaid
flowchart TB
  classDef input fill:#172033,stroke:#6ea8fe,color:#f8fbff,stroke-width:1px;
  classDef core fill:#17372d,stroke:#58d68d,color:#f8fbff,stroke-width:1px;
  classDef proof fill:#3b2d12,stroke:#f4c95d,color:#f8fbff,stroke-width:1px;
  classDef outcome fill:#31204d,stroke:#c7a4ff,color:#f8fbff,stroke-width:1px;

  A["<b>1. Request contract</b><br/>goal В· files В· exact target"]:::input
  B["<b>2. Evidence resolution</b><br/>target Meta В· versioned references В· JAR facts"]:::input
  C["<b>3. dCore core</b><br/>retrieve В· design В· lint В· pack validation"]:::core
  D["<b>4. Proof boundary</b><br/>source в†’ static в†’ compile/client в†’ runtime"]:::proof
  E["<b>5. Decision</b><br/>fix В· BUILD_BLOCKED В· ready with recorded evidence"]:::outcome
  A --> B --> C --> D --> E
```

The model is deliberately linear: target facts enter before analysis, and every
claim leaves with its proof state. This keeps the overview readable on one
screen while preserving the important boundary.

## Analysis pipeline

```mermaid
flowchart TB
  classDef input fill:#172033,stroke:#6ea8fe,color:#f8fbff,stroke-width:1px;
  classDef analysis fill:#17372d,stroke:#58d68d,color:#f8fbff,stroke-width:1px;
  classDef finding fill:#3b2d12,stroke:#f4c95d,color:#f8fbff,stroke-width:1px;
  classDef result fill:#31204d,stroke:#c7a4ff,color:#f8fbff,stroke-width:1px;

  S["<b>Project input</b><br/>.dsc files or merged resource pack"]:::input
  T["<b>Target evidence</b><br/>Minecraft В· Paper В· Denizen(M) В· addons В· exact JARs"]:::input
  S --> L["<b>Static lint</b><br/>syntax В· API В· event scope В· lifecycle"]:::analysis
  S --> Q["<b>Semantic analysis</b><br/>queues В· ownership В· cleanup В· bounded work"]:::analysis
  T --> L
  T --> Q
  L --> F["<b>Actionable findings</b><br/>severity В· code В· location В· reason В· fix"]:::finding
  Q --> F
  F --> P["<b>Proof-state classifier</b><br/>what the available evidence actually proves"]:::finding
  P --> U["<b>STATIC_OK</b><br/>runtime still unverified"]:::result
  P --> R["<b>Evidence complete</b><br/>supplied reports retain their origin"]:::result
```

## Local deterministic core

The Python package provides retrieval, Denizen lint, semantic/queue analysis, resource-pack graph validation, design comparison, proof gates, deterministic build generation, and build verification. The SQLite database is a target-scoped retrieval index. The core has no MCP server, hosted bridge, or vendor-specific implementation.

## Evidence boundary

`SOURCE_EVIDENCE`, `STATIC_OK`, `COMPILE_OK`, `CLIENT_LOG_OK`, and `RUNTIME_OK` are separate records. The build manifest inventories portable artifacts and knowledge inputs. A statically valid pack cannot be described as working runtime proof without client evidence.

## Shader profiles

Minecraft shader behavior is modeled by exact client and resource-pack format. The 1.21.x profile is separate and never inherits an activation route from another target.

## 0.82 frontend boundary

The source IR preserves commands, arguments, sections, references and spans. New event-filter and loop-path queries consume that IR. The legacy lint frontend and Denizen-Core semantic subset still have separate structural parsing; they have not been deleted or declared equivalent. Regression comparisons cover the transferred checks. Full control-flow/dataflow unification, dynamic callbacks and all Reflect extensions remain incremental work.
