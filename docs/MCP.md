# MCP server

`dcore.mcp.server` serves dCore over the Model Context Protocol on stdio. It
replaces the local Codex Skill: the operating contract, tool surface and proof
boundaries now reach any MCP-speaking client instead of one vendor's packaging.
The Custom GPT product is unaffected; it still ships as its own bundle because
Custom GPT does not speak MCP.

## Why stdio and stdlib only

dCore ships with `dependencies = []`. The transport in `dcore/mcp/protocol.py`
is newline-delimited JSON-RPC 2.0 implemented on `sys.stdin`/`sys.stdout`, with
no SDK dependency, so a fresh Python 3.12 checkout runs the server without an
install step beyond the package itself.

## Install and run

```text
python -m pip install -e .
python -m dcore.mcp.server
```

`python -m dcore.mcp.server --describe` prints the tool, resource and prompt
inventory as JSON and exits, without starting the stdio loop. Use it to check
what a client will see before wiring up a config.

## Tool surface

Every tool runs the same `main()` the CLI runs, in-process, so tool behavior is
covered by the same tests that pin down `dcore lint`'s flags:

| Tool | CLI equivalent |
|---|---|
| `dcore_lint` | `dcore lint` |
| `dcore_lint_pack` | `dcore lint-pack` |
| `dcore_retrieve` | `dcore retrieve` |
| `dcore_design_compare` | `dcore design compare` |
| `dcore_versions` | `dcore versions` (read path only) |
| `dcore_shadow` | `dcore shadow` |
| `dcore_release_gate` | `dcore run` |
| `dcore_project_audit` | unified script and visual audit |
| `dcore_shader_review` | `dcore lint-pack` with shader proof workflow |
| `dcore_verify` | `dcore verify` |
| `dcore_accept_agent` | `dcore accept-agent` |
| `dcore_accept_pool4` | `dcore accept-pool4` |

`dcore_lint`, `dcore_project_audit` and `dcore_release_gate` accept either `paths` (files/directories
on disk) or inline `text`, which is materialised into a per-call temporary
workspace. Both report findings through `structuredContent.blocking` rather
than requiring the caller to infer pass/fail from a non-zero exit code, since a
linter exiting 1 on an error-severity finding did its job.

## Resources and prompts

- `dcore://instructions` is the operating contract: the local-evidence gate,
  the seven-step execution gate, Reflect boundaries and the clean production
  rules. Read it before answering a Denizen question.
- `dcore://architecture`, `dcore://operations` mirror `docs/ARCHITECTURE.md`
  and `docs/OPERATIONS.md`.
- `dcore://manifest` is the verified release identity.
- Prompts `dcore_task`, `dcore_review`, `dcore_project_audit`, `dcore_shader_review` and `dcore_release_review` put the execution and review gates
  in front of a request instead of depending on the client having read the
  instructions resource first.

## Client configuration

Claude Code (`.claude/settings.json` or `claude mcp add`):

```json
{
  "mcpServers": {
    "dcore": {
      "command": "python",
      "args": ["-m", "dcore.mcp.server"],
      "cwd": "/absolute/path/to/dcore/repository"
    }
  }
}
```

Cursor (`.cursor/mcp.json`), Codex (`~/.codex/config.toml` `[mcp_servers.dcore]`)
and Zed (`settings.json` `context_servers`) take the same `command`/`args`/`cwd`
triple; consult each client's MCP documentation for the exact key names.

`cwd` must be the repository root so `dcore.paths` resolves
`knowledge/dcore.sqlite` correctly; pass `db` in a tool call to override it
per call instead.

## Acceptance

`dcore.acceptance.agent` runs the ten deterministic Denizen scenarios (clean
task, malformed tag, broad cancel, Reflect enabled/disabled, JAR evidence,
dog-navigation ownership, terminal-command reachability) through
`dcore.mcp.tools.call` directly, so the acceptance suite exercises the exact
code path an MCP client calls, not a rebuilt bundle:

```text
python -m dcore.acceptance.agent --db knowledge/dcore.sqlite
```

`tests/test_mcp_server.py` drives the same dispatcher over the stdio protocol
itself: handshake, malformed-frame recovery, unknown-method/tool/resource
handling, and one round trip per tool category.
