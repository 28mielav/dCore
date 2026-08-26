"""Low-memory control-plane simulation for bounded multiplayer event sessions.

It models reservations and lifecycle ownership; it does not execute Denizen or
claim Minecraft/Paper runtime proof.
"""

from __future__ import annotations

import argparse
import json
from collections import deque
from pathlib import Path
from typing import Any


def load_plan(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read shadow plan: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("shadow plan must be a JSON object")
    return payload


def simulate(plan: dict[str, Any]) -> dict[str, Any]:
    group_size = plan.get("group_size", 4)
    workers = plan.get("workers")
    operations = plan.get("operations")
    if not isinstance(group_size, int) or group_size < 2:
        raise ValueError("group_size must be an integer >= 2")
    if not isinstance(workers, list) or not workers or not isinstance(operations, list):
        raise ValueError("shadow plan requires non-empty workers and operations arrays")
    capacity: dict[str, int] = {}
    for worker in workers:
        if not isinstance(worker, dict) or not isinstance(worker.get("id"), str) or not isinstance(worker.get("max_sessions"), int) or worker["max_sessions"] < 1:
            raise ValueError("every worker requires id and positive max_sessions")
        if worker["id"] in capacity:
            raise ValueError(f"duplicate worker id: {worker['id']}")
        capacity[worker["id"]] = worker["max_sessions"]

    waiting: deque[str] = deque()
    player_state: dict[str, str] = {}
    idempotency: dict[str, str] = {}
    sessions: dict[str, dict[str, Any]] = {}
    lost_workers: set[str] = set()
    trace: list[dict[str, Any]] = []
    failures: list[str] = []
    next_session = 1

    def active_count(worker_id: str) -> int:
        return sum(session["worker"] == worker_id and session["state"] == "active" for session in sessions.values())

    def reserve() -> None:
        nonlocal next_session
        while len(waiting) >= group_size:
            worker = next((worker_id for worker_id in capacity if worker_id not in lost_workers and active_count(worker_id) < capacity[worker_id]), None)
            if worker is None:
                return
            players = [waiting.popleft() for _ in range(group_size)]
            session_id = f"session-{next_session}"
            next_session += 1
            sessions[session_id] = {"worker": worker, "players": players, "state": "active"}
            for player in players:
                player_state[player] = session_id
            trace.append({"event": "reserved", "session": session_id, "worker": worker, "players": players})

    for index, operation in enumerate(operations, 1):
        if not isinstance(operation, dict) or not isinstance(operation.get("op"), str):
            failures.append(f"operation {index}: missing op")
            continue
        kind = operation["op"]
        if kind == "join":
            player = operation.get("player")
            key = operation.get("key", f"join:{player}")
            if not isinstance(player, str) or not isinstance(key, str):
                failures.append(f"operation {index}: join requires player and key")
                continue
            if key in idempotency:
                trace.append({"event": "duplicate_join_ignored", "player": player, "key": key})
            elif player in player_state:
                failures.append(f"operation {index}: player {player} already belongs to {player_state[player]}")
            else:
                idempotency[key] = player
                player_state[player] = "waiting"
                waiting.append(player)
                trace.append({"event": "queued", "player": player})
                reserve()
        elif kind in {"end", "transfer_failed"}:
            session_id = operation.get("session")
            session = sessions.get(session_id)
            if not isinstance(session_id, str) or not session or session["state"] != "active":
                failures.append(f"operation {index}: active session required for {kind}")
                continue
            session["state"] = "cleaned"
            for player in session["players"]:
                if kind == "transfer_failed":
                    player_state[player] = "waiting"
                    waiting.append(player)
                else:
                    player_state[player] = "completed"
            trace.append({"event": kind, "session": session_id})
            reserve()
        elif kind == "worker_lost":
            worker = operation.get("worker")
            if not isinstance(worker, str) or worker not in capacity:
                failures.append(f"operation {index}: known worker required")
                continue
            lost_workers.add(worker)
            for session_id, session in sessions.items():
                if session["worker"] != worker or session["state"] != "active":
                    continue
                session["state"] = "cleaned"
                for player in session["players"]:
                    player_state[player] = "waiting"
                    waiting.append(player)
                trace.append({"event": "worker_lost_cleanup", "session": session_id, "worker": worker})
            reserve()
        else:
            failures.append(f"operation {index}: unsupported op {kind}")

        for worker in capacity:
            if active_count(worker) > capacity[worker]:
                failures.append(f"worker {worker} exceeds session capacity")
        active_players = [player for session in sessions.values() if session["state"] == "active" for player in session["players"]]
        if len(active_players) != len(set(active_players)):
            failures.append("a player belongs to more than one active session")

    return {
        "tool": "dcore_shadow", "scope": "control-plane simulation only; not Minecraft or Denizen runtime",
        "verdict": "SIMULATION_PASS" if not failures else "SIMULATION_FAIL",
        "group_size": group_size, "waiting": list(waiting), "sessions": sessions,
        "worker_active_sessions": {worker: active_count(worker) for worker in capacity},
        "trace": trace, "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Simulate bounded multiplayer event-session control plane")
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = simulate(load_plan(args.plan))
    except ValueError as exc:
        parser.error(str(exc))
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if result["verdict"] == "SIMULATION_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
