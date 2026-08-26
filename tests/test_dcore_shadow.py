from __future__ import annotations

import unittest

from dcore.gates.shadow import simulate


class DcoreShadowTests(unittest.TestCase):
    def test_capacity_keeps_second_group_queued(self) -> None:
        plan = {
            "group_size": 4, "workers": [{"id": "worker-a", "max_sessions": 1}],
            "operations": [{"op": "join", "player": f"p{i}", "key": f"k{i}"} for i in range(8)],
        }
        result = simulate(plan)
        self.assertEqual("SIMULATION_PASS", result["verdict"])
        self.assertEqual(1, result["worker_active_sessions"]["worker-a"])
        self.assertEqual(["p4", "p5", "p6", "p7"], result["waiting"])

    def test_duplicate_join_is_idempotent(self) -> None:
        result = simulate({
            "group_size": 4, "workers": [{"id": "worker-a", "max_sessions": 1}],
            "operations": [{"op": "join", "player": "p1", "key": "join-p1"}, {"op": "join", "player": "p1", "key": "join-p1"}],
        })
        self.assertEqual("SIMULATION_PASS", result["verdict"])
        self.assertEqual(["p1"], result["waiting"])

    def test_worker_loss_cleans_and_requeues_session(self) -> None:
        operations = [{"op": "join", "player": f"p{i}", "key": f"k{i}"} for i in range(4)]
        operations.append({"op": "worker_lost", "worker": "worker-a"})
        result = simulate({"group_size": 4, "workers": [{"id": "worker-a", "max_sessions": 1}], "operations": operations})
        self.assertEqual("SIMULATION_PASS", result["verdict"])
        self.assertEqual(["p0", "p1", "p2", "p3"], result["waiting"])
        self.assertEqual(0, result["worker_active_sessions"]["worker-a"])

    def test_rejects_second_live_membership(self) -> None:
        result = simulate({
            "group_size": 4, "workers": [{"id": "worker-a", "max_sessions": 1}],
            "operations": [{"op": "join", "player": "p1", "key": "first"}, {"op": "join", "player": "p1", "key": "second"}],
        })
        self.assertEqual("SIMULATION_FAIL", result["verdict"])
        self.assertTrue(result["failures"])


if __name__ == "__main__":
    unittest.main()
