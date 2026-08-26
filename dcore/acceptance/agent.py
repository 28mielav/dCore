"""Run the deterministic Denizen scenarios through the MCP tool surface.

This replaces the Skill acceptance runner. That runner built a Skill bundle and
shelled into it, which proved the bundle layout more than the behaviour; the thing
worth pinning down is that an agent calling `dcore_lint` over the protocol gets the
same findings the CLI produces.

Scenarios are expressed as required and forbidden finding codes rather than exact
output, so a new rule or a reworded message does not fail acceptance while a lost
diagnostic does.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from typing import Any

from dcore.mcp import tools


@dataclass(frozen=True)
class Scenario:
    name: str
    text: str
    required: frozenset[str]
    forbidden: frozenset[str] = frozenset()
    arguments: dict[str, Any] = field(default_factory=dict)


REFLECT_CALL = "demo:\n  type: task\n  script:\n  - define name <invoke[player.getName()]>\n"

SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        "clean_task",
        "demo:\n  type: task\n  script:\n  - narrate hello\n",
        frozenset(),
        frozenset({"unknown_command"}),
    ),
    Scenario(
        "malformed_tag",
        "demo:\n  type: task\n  script:\n  - narrate <player.name\n",
        frozenset({"uneven_tags"}),
    ),
    Scenario(
        "broad_cancel",
        "demo:\n  type: world\n  events:\n    on player tries to attack slime:\n    - determine cancelled\n",
        frozenset({"broad_cancel_without_identity_guard"}),
    ),
    Scenario("reflect_disabled", REFLECT_CALL, frozenset({"reflect_addon_not_enabled"})),
    Scenario(
        "reflect_enabled",
        REFLECT_CALL,
        frozenset({"reflect_boundary"}),
        frozenset({"unknown_command"}),
        {"addons": ["reflect@2.4.2"]},
    ),
    Scenario(
        "jar_evidence",
        "demo:\n  type: task\n  script:\n  - narrate hello\n",
        frozenset({"jar_evidence_missing", "target_context"}),
        arguments={
            "minecraft": "1.21.10",
            "denizenm": "7299M",
            "addons": ["reflect@2.4.2"],
            "require_jar_evidence": True,
        },
    ),
    Scenario(
        "dog_owner_conflict",
        "dog_search:\n  type: task\n  script:\n  - walk <[wolf]> <player.location>\n"
        "  - push <[wolf]> origin:<[wolf].location> destination:<player.location> speed:1\n",
        frozenset({"dog_navigation_owner_conflict"}),
    ),
    Scenario(
        "dog_hot_repath",
        "dog_events:\n  type: world\n  events:\n    on tick:\n    - walk <[wolf]> <player.location>\n",
        frozenset({"dog_navigation_hot_repath"}),
    ),
    Scenario(
        "dog_clean_transition",
        "dog_search:\n  type: task\n  script:\n  - walk <[wolf]> <player.location>\n"
        "  - walk <[wolf]> stop\n"
        "  - push <[wolf]> origin:<[wolf].location> destination:<player.location> speed:1\n",
        frozenset(),
        frozenset({"dog_navigation_owner_conflict", "dog_navigation_replaced_without_stop"}),
    ),
    Scenario(
        "terminal_path",
        "demo:\n  type: world\n  events:\n    on player tries to attack slime:\n"
        "    - determine cancelled\n    - narrate unreachable\n",
        frozenset({"unreachable_after_terminal_command"}),
    ),
)


def run(database: str | None = None) -> list[dict[str, Any]]:
    outcomes: list[dict[str, Any]] = []
    for scenario in SCENARIOS:
        arguments: dict[str, Any] = {
            "text": scenario.text,
            "filename": f"{scenario.name}.dsc",
            "profile": "denizenm",
            **scenario.arguments,
        }
        if database:
            arguments["db"] = database
        result = tools.call("dcore_lint", arguments)
        if result.get("isError"):
            outcomes.append({
                "scenario": scenario.name,
                "codes": [],
                "missing": sorted(scenario.required),
                "forbidden": [],
                "error": result["content"][0]["text"],
            })
            continue
        findings = json.loads(result["content"][0]["text"] or "[]")
        codes = {item["code"] for item in findings}
        outcomes.append({
            "scenario": scenario.name,
            "blocking": bool(result.get("structuredContent", {}).get("blocking")),
            "codes": sorted(codes),
            "missing": sorted(scenario.required - codes),
            "forbidden": sorted(scenario.forbidden.intersection(codes)),
        })
    return outcomes


def failures(outcomes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in outcomes if item["missing"] or item["forbidden"] or item.get("error")]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the dCore agent acceptance scenarios over the MCP tool surface"
    )
    parser.add_argument("--db", help="Knowledge database to lint against")
    args = parser.parse_args()
    outcomes = run(args.db)
    failed = failures(outcomes)
    print(json.dumps(
        {"total": len(outcomes), "failures": failed, "scenarios": outcomes},
        ensure_ascii=False,
        indent=2,
    ))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
