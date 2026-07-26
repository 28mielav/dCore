import contextlib
import io
import json
import sqlite3
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))

import dcore_design


class DesignComparatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db_path = self.root / "knowledge.sqlite"
        db = sqlite3.connect(str(self.db_path))
        db.execute(
            """CREATE TABLE meta_preferred(
                 entry_id INTEGER PRIMARY KEY,
                 product TEXT NOT NULL,
                 category TEXT NOT NULL,
                 name TEXT NOT NULL,
                 object_type TEXT NOT NULL,
                 syntax TEXT NOT NULL,
                 commit_sha TEXT NOT NULL,
                 source_file TEXT NOT NULL,
                 source_line INTEGER NOT NULL,
                 deprecated TEXT NOT NULL
               )"""
        )
        db.execute(
            """INSERT INTO meta_preferred VALUES(
                 1,'DenizenM','command','attach','','attach [<entity>]','abc123',
                 'commands/entity/AttachCommand.java',25,''
               )"""
        )
        db.execute(
            """INSERT INTO meta_preferred VALUES(
                 2,'Denizen','command','attach','','attach [<entity>]','official456',
                 'commands/entity/AttachCommand.java',21,''
               )"""
        )
        db.commit()
        db.close()

    def tearDown(self):
        self.temp.cleanup()

    def evidence(self, evidence_id, status="pass", kind="meta", scope="api", entry_id=1):
        value = {
            "id": evidence_id,
            "capability": "camera_attach",
            "scope": scope,
            "kind": kind,
            "status": status,
            "provider": "DenizenM",
            "provider_version": "1.3.3-b7290M",
        }
        if kind == "meta":
            value.update(
                {
                    "entry_id": entry_id,
                    "product": "DenizenM",
                    "category": "command",
                    "name": "attach",
                    "commit_sha": "abc123",
                }
            )
        else:
            value["source"] = "runtime:test/%s" % evidence_id
        return value

    def route(self, route_id, runtime_cost, blast_radius, evidence=None):
        return {
            "id": route_id,
            "covers": ["camera_attach"],
            "versions": {"minecraft": "1.21.11", "denizen": "1.3.3-b7290M"},
            "providers": {"DenizenM": "1.3.3-b7290M"},
            "constraints": {"viewer_only": "pass", "no_tick_loop": "pass"},
            "evidence": evidence if evidence is not None else [self.evidence("meta_" + route_id)],
            "metrics": {"runtime_cost": runtime_cost, "blast_radius": blast_radius},
            "falsifier": "The carrier is visible to another viewer.",
            "proof": {
                "test": "Spawn one marked carrier for two players.",
                "success": "Only the owner sees the carrier.",
                "failure": "The second player sees it or the owner does not.",
            },
        }

    def dossier(self, routes):
        return {
            "schema_version": 1,
            "request": "Attach a viewer-only display to the camera without a tick loop.",
            "profile": {
                "versions": {"minecraft": "1.21.11", "denizen": "1.3.3-b7290M"},
                "providers": {"DenizenM": "1.3.3-b7290M"},
            },
            "constraints": [
                {"id": "viewer_only", "kind": "hard"},
                {"id": "no_tick_loop", "kind": "hard"},
            ],
            "capabilities": [
                {
                    "id": "camera_attach",
                    "required": True,
                    "required_scopes": ["api"],
                    "provider": "DenizenM",
                }
            ],
            "axes": {"runtime_cost": "min", "blast_radius": "min"},
            "routes": routes,
        }

    def test_unique_pareto_winner_is_selected_for_proof(self):
        document = self.dossier(
            [self.route("native", 1, 1), self.route("polling", 10, 4)]
        )
        result = dcore_design.compare(document, self.db_path)
        self.assertEqual("READY_FOR_PROOF", result["status"])
        self.assertEqual("native", result["selected_for_proof"])
        self.assertEqual(["native"], result["pareto_front"])
        polling = next(item for item in result["routes"] if item["id"] == "polling")
        self.assertEqual(["native"], polling["dominated_by"])
        citation = result["routes"][0]["evidence"]["capabilities"]["camera_attach"][0]["evidence"][0]["citation"]
        self.assertEqual("abc123", citation["commit_sha"])

    def test_pareto_tradeoff_stays_incomplete(self):
        document = self.dossier(
            [self.route("cheap_wide", 1, 5), self.route("costly_narrow", 5, 1)]
        )
        result = dcore_design.compare(document, self.db_path)
        self.assertEqual("INCOMPLETE", result["status"])
        self.assertIsNone(result["selected_for_proof"])
        self.assertEqual(["cheap_wide", "costly_narrow"], result["pareto_front"])

    def test_unproven_route_blocks_false_winner(self):
        weak = self.evidence("forum", kind="community")
        weak["source"] = "https://example.invalid/forum"
        document = self.dossier(
            [self.route("native", 1, 1), self.route("unknown", 20, 20, [weak])]
        )
        result = dcore_design.compare(document, self.db_path)
        self.assertEqual("INCOMPLETE", result["status"])
        self.assertIsNone(result["selected_for_proof"])
        unknown = next(item for item in result["routes"] if item["id"] == "unknown")
        self.assertEqual("UNPROVEN", unknown["verdict"])
        self.assertEqual("community", unknown["context_only_evidence"][0]["kind"])

    def test_hard_constraint_failure_rejects_cheapest_route(self):
        bad = self.route("cheap_but_global", 0, 0)
        bad["constraints"]["viewer_only"] = "fail"
        good = self.route("scoped", 5, 2)
        result = dcore_design.compare(self.dossier([bad, good]), self.db_path)
        self.assertEqual("READY_FOR_PROOF", result["status"])
        self.assertEqual("scoped", result["selected_for_proof"])
        rejected = next(item for item in result["routes"] if item["id"] == "cheap_but_global")
        self.assertEqual("REJECTED", rejected["verdict"])
        self.assertIn("constraint 'viewer_only' failed", rejected["hard_failures"])

    def test_provider_and_version_mismatches_are_hard_failures(self):
        provider_bad = self.route("provider_bad", 1, 1)
        provider_bad["providers"] = {"DenizenM": "old-build"}
        version_bad = self.route("version_bad", 2, 2)
        version_bad["versions"]["minecraft"] = "1.20.6"
        result = dcore_design.compare(
            self.dossier([provider_bad, version_bad]), self.db_path
        )
        self.assertEqual("NO_VIABLE_ROUTE", result["status"])
        self.assertTrue(all(item["verdict"] == "REJECTED" for item in result["routes"]))
        messages = "\n".join(
            message for item in result["routes"] for message in item["hard_failures"]
        )
        self.assertIn("does not match target", messages)

    def test_meta_cannot_satisfy_runtime_scope(self):
        runtime_route = self.route(
            "runtime_proven",
            1,
            1,
            [self.evidence("runtime", kind="runtime", scope="runtime")],
        )
        meta_route = self.route(
            "meta_only",
            2,
            2,
            [self.evidence("meta_runtime", kind="meta", scope="runtime")],
        )
        document = self.dossier([runtime_route, meta_route])
        document["capabilities"][0]["required_scopes"] = ["runtime"]
        result = dcore_design.compare(document, self.db_path)
        self.assertEqual("INCOMPLETE", result["status"])
        meta_report = next(item for item in result["routes"] if item["id"] == "meta_only")
        self.assertEqual("UNPROVEN", meta_report["verdict"])
        excluded = meta_report["evidence"]["capabilities"]["camera_attach"][0]["excluded"]
        self.assertIn("cannot prove scope", excluded[0]["reason"])

    def test_exact_meta_mismatch_is_not_admissible(self):
        bad_evidence = self.evidence("wrong_product", entry_id=2)
        bad_evidence["product"] = "DenizenM"
        route = self.route("bad_meta", 1, 1, [bad_evidence])
        result = dcore_design.compare(
            self.dossier([route, self.route("good_meta", 2, 2)]), self.db_path
        )
        self.assertEqual("INCOMPLETE", result["status"])
        report = next(item for item in result["routes"] if item["id"] == "bad_meta")
        self.assertEqual("UNPROVEN", report["verdict"])
        excluded = report["evidence"]["capabilities"]["camera_attach"][0]["excluded"]
        self.assertIn("mismatch", excluded[0]["reason"])

    def test_equal_rank_conflict_is_unproven(self):
        passing = self.evidence("meta_pass")
        failing = self.evidence("meta_fail", status="fail")
        route = self.route("conflicted", 1, 1, [passing, failing])
        result = dcore_design.compare(
            self.dossier([route, self.route("other", 2, 2)]), self.db_path
        )
        report = next(item for item in result["routes"] if item["id"] == "conflicted")
        scope = report["evidence"]["capabilities"]["camera_attach"][0]
        self.assertEqual("conflict", scope["status"])
        self.assertEqual("UNPROVEN", report["verdict"])

    def test_verify_detects_tampering(self):
        document = self.dossier(
            [self.route("native", 1, 1), self.route("polling", 10, 4)]
        )
        decision = dcore_design.compare(document, self.db_path)
        clean = dcore_design.verify(document, decision, self.db_path)
        self.assertEqual("PASS", clean["status"])
        tampered = deepcopy(decision)
        tampered["selected_for_proof"] = "polling"
        changed = dcore_design.verify(document, tampered, self.db_path)
        self.assertEqual("FAIL", changed["status"])
        self.assertTrue(any("selected_for_proof" in item for item in changed["differences"]))

    def test_route_count_and_required_fields_are_validated(self):
        document = self.dossier([self.route("only", 1, 1)])
        with self.assertRaises(dcore_design.InputError) as caught:
            dcore_design.compare(document, self.db_path)
        self.assertTrue(any("at least 2" in error for error in caught.exception.errors))

    def test_cli_compare_and_verify_are_machine_readable(self):
        document = self.dossier(
            [self.route("native", 1, 1), self.route("polling", 10, 4)]
        )
        input_path = self.root / "routes.json"
        decision_path = self.root / "decision.json"
        input_path.write_text(json.dumps(document), encoding="utf-8")

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = dcore_design.main(
                [
                    "compare",
                    "--input",
                    str(input_path),
                    "--db",
                    str(self.db_path),
                    "--output",
                    str(decision_path),
                ]
            )
        self.assertEqual(0, code)
        self.assertEqual("READY_FOR_PROOF", json.loads(decision_path.read_text(encoding="utf-8"))["status"])

        verify_output = self.root / "verify.json"
        code = dcore_design.main(
            [
                "verify",
                "--input",
                str(input_path),
                "--decision",
                str(decision_path),
                "--db",
                str(self.db_path),
                "--output",
                str(verify_output),
            ]
        )
        self.assertEqual(0, code)
        self.assertEqual("PASS", json.loads(verify_output.read_text(encoding="utf-8"))["status"])


if __name__ == "__main__":
    unittest.main()
