# Architecture

## Trust flow

```text
pinned public sources + authored rules
                |
                v
       isolated SQLite candidate
                |
     migrations + executable tests
                |
                v
 private last-known-good repository
       |                    |
       v                    v
 dated owner bundle    manifest freshness API
```

The Cloudflare Worker is not a database and cannot update dCore. It exposes only the latest verified manifest. GitHub Actions maintains the repository candidate. Custom GPT Knowledge replacement remains manual.

## Sources of truth

| Fact | Owner |
|---|---|
| Curated engineering cards and dependencies | `cards`, `card_links` |
| Exact Denizen APIs | `meta_sources`, `meta_entries`, `meta_preferred` |
| IDE diagnostics | `ide_sources`, `ide_diagnostics` |
| Retrieval behavior | routing tables plus `retrieval_tests` |
| Bad/good engineering examples | `contrast_examples` |
| Candidate implementation families | `route_patterns` |
| Public visual provenance | `visual_sources` |
| GPT behavior | `knowledge/DCORE_INSTRUCTIONS.txt` |
| Release identity | `knowledge/manifest.json` |

## Request pipeline

```text
request
  -> freshness check
  -> retrieval.py (intent, domains, dependencies, contrasts, route patterns)
  -> exact DenizenM-first Meta lookup
  -> route dossier only when genuine alternatives can change the design
  -> dcore_design.py for complex hard-gate + Pareto comparison
  -> pre-code ownership/cost/behavior contract
  -> implementation
  -> dcore_lint.py and, when applicable, dcore_rp_lint.py
  -> Refined + reload + focused runtime proof
```

The route comparator cannot declare runtime success. `READY_FOR_PROOF` means one route is the unique proven pre-code candidate for supplied facts. `DECISION_REPRODUCED` means only that verification recomputed the same artifact. Small exact fixes do not manufacture route dossiers.

## Clean-code boundary

Entry events prove identity and dispatch. Feature tasks own cohesive lifecycle phases. Connected state has one authoritative writer. Every acquired resource has one cleanup owner. Dormant objects have no queue, entity or chunk ticket. Provider-specific calls live in one adapter. Abstractions require a second consumer, removed duplication or isolated volatility.

`dcore_lint.py` distinguishes errors, warnings, suggestions and provenance, and defaults to a compact human table. It checks terminal-command reachability, event blast radius and ceremonial forwarding tasks. Valid denizen-reflect syntax is not misclassified as unknown core syntax, but exact Java signatures still require installed-version proof.

The response layer is deliberately progressive: a non-trivial request starts with a contract and one bounded learning step. A complete artifact is gated behind a settled route, lint and tests. The anti-vibe policy reviews missing evidence, duplicated responsibility, unbounded work and unexplained APIs; it does not infer authorship from style.

## Shader workbench boundary

The visual registry stores mechanisms below feature names: route probing, control channels, camera/plane transforms, temporal history, bloom graphs, custom particle encoding and GPU budgets. Public examples do not become production code merely because they render in an older client.

`dcore_rp_lint.py` analyzes the final merged directory or ZIP: JSON, `#moj_import`, namespace-aware program/stage linkage, post targets, path case, channels and route ownership. `STATIC_OK` always carries `RUNTIME_UNVERIFIED`; route selection, F5, graphics modes and frame cost require the exact client.

## Update transaction

The workflow mutates only a build copy. Curated migrations are deterministic. Upstream Denizen/IDE data may refresh automatically because it is indexed source material. A changed visual repository only updates `latest_seen_sha` and `review_status=review_pending`; its indexed commit, cards and excerpts do not move without review.

Validation covers SQLite integrity, foreign keys, minimum corpus sizes, required policy cards, source-license gates, retrieval regressions, tool unit tests and hashes of every GPT attachment. Only a passing bundle reaches the canonical database and private release.
