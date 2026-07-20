# Architecture

## Trust flow

```text
Public upstream repositories
          ↓ exact commits
Isolated SQLite candidate
          ↓ mandatory validation
Private GitHub repository (last known-good)
          ├─ dated private release for the owner
          └─ verified manifest → Cloudflare Worker → Custom GPT Action
```

## Sources of truth

| Fact | Owner |
|---|---|
| Curated cards, routing and retrieval tests | `knowledge/dcore.sqlite` |
| Current indexed upstream revisions | `meta_sources` inside SQLite |
| Integrity and release identity | `knowledge/manifest.json` |
| GPT behaviour contract | `knowledge/DCORE_INSTRUCTIONS.txt` |
| Deployment procedure | `.github/workflows/update.yml` |
| GPT freshness view | Cloudflare Worker response |

The Worker is not a database and the Action is not an updater. They expose the identity of the latest verified bundle so dCore can distinguish current, stale and unknown freshness states.

## Update transaction

The workflow copies the last known-good database to `build/`, refreshes only that candidate and validates it. Repository state changes only after validation succeeds. A failing candidate is retained only in short-lived diagnostics and never replaces working Knowledge.

Validation includes the full retrieval regression suite. Integrity without correct routing is not a passing candidate. A database that routes a thin-plane crossing request to a shader card, for example, is rejected even when SQLite itself is healthy.

## Reusable primitive layer

dCore stores mechanisms below named gameplay features. Portal crossing, laser gates and rotated triggers share oriented-plane intersection, local shape bounds and crossing hysteresis. Cursor menus and sliders share ray-plane input. Portals and linked cameras share paired-frame transforms. Blink, loading and fades share temporal masks; shake, recoil and roll share bounded screen impulses.

Concrete mechanics remain retrieval tests and compositions. This prevents a working solution from becoming trapped behind one keyword such as `portal`, `F5` or `roulette`.

## Failure behaviour

- Upstream unavailable: workflow fails; previous Knowledge and manifest remain authoritative.
- Import failure: candidate is discarded.
- Validation failure: candidate is not committed, released or advertised.
- Worker deployment failure: database may be current, but Action freshness remains at the previous deployed manifest until the next successful run.
- Action unavailable: dCore must report freshness as unknown, not fabricate currency.
- Custom GPT Knowledge stale: owner replaces attachments from the latest private release.

## Why SQLite is versioned

External Meta is only one layer. The database also contains authored architecture cards, diagnostics, routing knowledge and retrieval tests. Those cannot be regenerated from the five upstream repositories. Keeping the last passing SQLite file privately versioned supplies rollback, reproducibility and a safe seed for unattended maintenance.
