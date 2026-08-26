"""Source-derived, bounded Denizen semantic core for dCore.

This is not a Bukkit replacement. It ports the portable queue/tag/control-flow
contract needed by dCore-lint and leaves platform commands to explicit adapters.
"""

from .engine import SemanticDiagnostic, SemanticResult, analyze_denizen, analyze_project

__all__ = ("SemanticDiagnostic", "SemanticResult", "analyze_denizen", "analyze_project")
