"""Reversible obfuscation for Denizen `.dsc` projects.

Formerly the standalone `dscpack` tool living outside this repository. It is
now `dcore.pack`, so it ships, tests and versions with the rest of dCore
instead of drifting as a second unversioned project. Behavior is unchanged:
the master key location, release format and CLI subcommands are the same.

`build_release`/`direct_deploy` delegate naming and rewriting to
`dcore.semantics` (IR, graph, surface, transform) rather than the regex
splitter the original tool started with; that legacy path is not carried
forward because it was already permanently disabled upstream in favor of the
semantic one.
"""

from __future__ import annotations
