# Changelog

All notable changes to dCore are documented here.

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
