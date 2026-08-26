"""Resolve compact historical Meta overlays without borrowing current API facts."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable


def table_exists(db: sqlite3.Connection, name: str) -> bool:
    return db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def entry_key(row: sqlite3.Row | dict) -> tuple[str, str, str]:
    return (str(row["category"]).casefold(), str(row["name"]).casefold(), str(row["object_type"]).casefold())


def overlay_state(db: sqlite3.Connection, selected_sources: Iterable[str]) -> dict[str, dict[str, object]]:
    if not table_exists(db, "meta_delta_sources"):
        return {}
    selected = tuple(dict.fromkeys(selected_sources))
    if not selected:
        return {}
    marks = ",".join("?" for _ in selected)
    state: dict[str, dict[str, object]] = {}
    for source_id, base_source_id in db.execute(
        f"SELECT source_id,base_source_id FROM meta_delta_sources WHERE source_id IN ({marks})", selected
    ):
        overrides = {
            (category.casefold(), name.casefold(), object_type.casefold())
            for category, name, object_type in db.execute(
                "SELECT category,name,object_type FROM meta_entries WHERE source_id=?", (source_id,)
            )
        }
        tombstones = {
            (category.casefold(), name.casefold(), object_type.casefold())
            for category, name, object_type in db.execute(
                "SELECT category,name,object_type FROM meta_version_tombstones WHERE source_id=?", (source_id,)
            )
        }
        state[source_id] = {"base": base_source_id, "overrides": overrides, "tombstones": tombstones}
    return state


def effective_sources(db: sqlite3.Connection, selected_sources: Iterable[str]) -> tuple[list[str], dict[str, dict[str, object]]]:
    selected = list(dict.fromkeys(selected_sources))
    state = overlay_state(db, selected)
    effective = list(selected)
    for value in state.values():
        base = str(value["base"])
        if base not in effective:
            effective.append(base)
    return effective, state


def visible(row: sqlite3.Row | dict, state: dict[str, dict[str, object]]) -> bool:
    source_id = str(row["source_id"])
    key = entry_key(row)
    if source_id in state:
        return key not in state[source_id]["tombstones"]
    for value in state.values():
        if source_id == value["base"] and (key in value["overrides"] or key in value["tombstones"]):
            return False
    return True
