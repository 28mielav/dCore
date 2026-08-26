from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path

from dcore.lint.script import MetaIndex, lint_text
from dcore.knowledge.retrieval import card_contract, card_contract_audit, resolve_meta, route, router_trace


ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "knowledge" / "dcore.sqlite"


class SkillScenarioTests(unittest.TestCase):
    """Offline end-to-end regression scenarios for the public $dCore workflow."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.denizenm = MetaIndex(DATABASE, "denizenm", set())
        cls.reflect = MetaIndex(DATABASE, "denizenm", {"reflect@2.4.2"})

    @staticmethod
    def codes(text: str, meta: MetaIndex | None = None) -> set[str]:
        return {item["code"] for item in lint_text(text, meta)}

    def test_known_command_is_not_reported_unknown(self) -> None:
        codes = self.codes("demo:\n  type: task\n  script:\n  - narrate hello\n", self.denizenm)
        self.assertNotIn("unknown_command", codes)

    def test_malformed_tag_is_rejected(self) -> None:
        codes = self.codes("demo:\n  type: task\n  script:\n  - narrate <player.name\n")
        self.assertIn("uneven_tags", codes)

    def test_broad_cancellation_requires_identity_guard(self) -> None:
        codes = self.codes("""demo:
  type: world
  events:
    on player tries to attack slime:
    - determine cancelled
""", self.denizenm)
        self.assertIn("broad_cancel_without_identity_guard", codes)

    def test_reflect_requires_enabled_addon_dialect(self) -> None:
        text = "demo:\n  type: task\n  script:\n  - define name <invoke[player.getName()]>\n"
        self.assertIn("reflect_addon_not_enabled", self.codes(text, self.denizenm))

    def test_reflect_enabled_is_a_boundary_not_an_unknown_command(self) -> None:
        text = "demo:\n  type: task\n  script:\n  - define name <invoke[player.getName()]>\n"
        codes = self.codes(text, self.reflect)
        self.assertIn("reflect_boundary", codes)
        self.assertNotIn("unknown_command", codes)

    def test_targeted_reflect_requires_jar_evidence_when_requested(self) -> None:
        target = MetaIndex(
            DATABASE, "denizenm", {"reflect@2.4.2"},
            target={"minecraft": "1.21.10", "denizenm": "7299M"},
            require_jar_evidence=True,
        )
        codes = self.codes("demo:\n  type: task\n  script:\n  - define name <invoke[player.getName()]>\n", target)
        self.assertIn("target_context", codes)
        self.assertIn("jar_evidence_missing", codes)

    def test_old_denizenm_query_keeps_historical_syntax(self) -> None:
        with sqlite3.connect(DATABASE) as db:
            result = resolve_meta(db, "teleport", "denizenm", (), denizenm_version="7268M")
        teleport = next(row for row in result["matches"] if row["product"] == "DenizenM" and row["name"] == "Teleport")
        self.assertEqual("meta_denizenm_tag_7268m", teleport["source_id"])
        self.assertNotIn("(async)", teleport["syntax"])

    def test_dog_walk_and_push_conflict_is_rejected(self) -> None:
        codes = self.codes("""dog_search:
  type: task
  script:
  - walk <[wolf]> <player.location>
  - push <[wolf]> origin:<[wolf].location> destination:<player.location> speed:1
""")
        self.assertIn("dog_navigation_owner_conflict", codes)

    def test_dog_tick_repath_is_rejected(self) -> None:
        codes = self.codes("""dog_events:
  type: world
  events:
    on tick:
    - walk <[wolf]> <player.location>
""")
        self.assertIn("dog_navigation_hot_repath", codes)

    def test_clean_dog_transition_stops_first_owner(self) -> None:
        codes = self.codes("""dog_search:
  type: task
  script:
  - walk <[wolf]> <player.location>
  - walk <[wolf]> stop
  - push <[wolf]> origin:<[wolf].location> destination:<player.location> speed:1
""")
        self.assertNotIn("dog_navigation_owner_conflict", codes)

    def test_retrieval_dog_query_activates_navigation_card(self) -> None:
        with sqlite3.connect(DATABASE) as db:
            domains, cards = route(db, "treasure dog walk pathfinding cleanup")
        self.assertIn("denizen", domains)
        self.assertIn("DOG-001", cards)

    def test_router_trace_explains_selected_cards_and_coverage(self) -> None:
        with sqlite3.connect(DATABASE) as db:
            trace = router_trace(db, "treasure dog walk pathfinding cleanup")
        self.assertIn("DOG-001", trace["selected_cards"])
        self.assertIn("DOG-001", trace["selection_reasons"])
        self.assertIn("coverage", trace)
        self.assertIn("card_contracts", trace)
        self.assertIn("status", trace["coverage"])

    def test_card_contract_exposes_required_proof_fields(self) -> None:
        with sqlite3.connect(DATABASE) as db:
            contract = card_contract(db, "DOG-001")
        self.assertTrue(contract["trigger_terms"])
        self.assertTrue(contract["verification"])
        self.assertTrue(contract["version_scope"])
        self.assertIn("required_retrieval_tests", contract)

    def test_card_contract_audit_requires_complete_corpus(self) -> None:
        with sqlite3.connect(DATABASE) as db:
            audit = card_contract_audit(db)
        self.assertEqual(176, audit["checked"])
        self.assertEqual("complete", audit["status"])
        self.assertEqual(0, audit["incomplete"])


if __name__ == "__main__":
    unittest.main()
