# Changelog

All notable changes to dCore are documented here.

## 0.82

- Publish standalone CLI, Skill and GPT release archives with SHA-256 checksums. Simplify installation documentation and repair CI test dependencies.
- Validate archive restore destinations before writing files, restrict POSIX master-key permissions and omit Python caches from Skill bundles.

- Index all 34 stable Minecraft shader interfaces from 1.16.5 through 26.2. Resolve pack overlays by target before lint, detect removed built-in paths and pre-1.19.4 display entity usage, and expose offline version coverage.

- Repair visual carrier advice and add focused diagnostics for server-tick camera following and mount/projection ambiguity. Check 1.21.11 post interfaces, official stage availability and actual pack.mcmeta ranges alongside 1.21.8. No new shader packs are added by these repairs.

- Follow cancellation paths and loop backedges using the shared IR; comments and unrelated flag reads no longer prove identity or lifetime.
- Keep historical Meta sources isolated from current Core, add three Denizen source profiles with date-associated Core evidence, and return version-selected code directly in cards.
- Check legacy 1.16.5 and modern shader interfaces; ship three original 1.21.8 lesson packs with explicit runtime limits.
- Load project targets from dcore.toml, bind supplied runtime reports to input hashes and provenance, and preserve user-reported proof status.
- Package the same runtime, database, guides and examples inside independent CLI, Skill and GPT deliveries. Add execution parity tests outside the checkout.
- Refresh README, installation instructions, practical guidance and licensing boundaries. Full frontend consolidation and GPU/server validation remain unfinished; see the 0.82 audit.

## 0.76

### Added

- Exact DenizenM 7302M Meta from commit 25d5164a4fbf396868345d12d0bc76a65b5548e6.
- Target-pinned DenizenM async-boundary diagnostics for live server mutations, including loop crossings.

### Changed

- Refined DenizenScript remains a versioned diagnostic source, not a replacement for dCore lifecycle analysis.

## 0.75

### Added

- Canonical portable Agent Skill under `skill/dcore/` with versioned references.
- Thin Codex, Claude Code, Antigravity, and Cursor adapters.
- Deterministic `build-skill` and portable `verify-skill` commands; `validate-shader` CLI alias.
- Explicit 1.21.x compatibility and target-pinned evidence guidance.

### Changed

- Build delivery is skill-first; Python remains the local deterministic CLI.
- Shader claims distinguish source, static, compile, client-log, and gameplay evidence.
- Repository and CI no longer include MCP, Cloudflare bridge, or vendor-specific runtime surfaces.

## 0.70

- Added target-pinned Meta overlays, semantic queue proof, and resource-pack graph validation.
- Made static and runtime proof states explicit.
