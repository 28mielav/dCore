# Platform adapters

The canonical workflow is `../SKILL.md`. These files are deployment shims only.

- `codex.md` for a Codex project rule.
- `claude.md` for Claude Code project instructions.
- `cursor.mdc` for Cursor.
- `antigravity.md` for an Antigravity skill wrapper.

They stay inside the Skill so the source repository has no editor-specific root files. Copy the required shim only into the consuming project or editor configuration.
