"""dCore: evidence-first engineering for DenizenScript and Minecraft visual work.

The release identity lives here and nowhere else. Before 0.70 the version was
repeated in `pyproject.toml`, `dcore/knowledge/data/validation_contract.json`, the database
`metadata` table, the GPT instructions and the README, so a bump silently left
four of them behind. Everything that needs the version now derives it from
`__version__`, and `verification/test_release_identity.py` fails when a copy drifts.
"""

from __future__ import annotations

__version__ = "0.76"

#: The exact string the database `metadata.name` row and the release contract
#: must carry. The verify gate compares against this, so it is not cosmetic.
RELEASE_NAME = f"dCore {__version__}"

__all__ = ["__version__", "RELEASE_NAME"]
