"""Shared target selection: historical API never inherits today's Core."""
import sqlite3


def target_sources(db: sqlite3.Connection, product: str, version: str | None):
    current = "denizenm_public_master" if product == "DenizenM" else "denizen_official_dev"
    if not version:
        return [current, "denizencore_official_master"], []
    tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    rows = db.execute(
        "SELECT m.source_id FROM version_artifacts v JOIN meta_sources m ON m.artifact_id=v.artifact_id "
        "WHERE lower(v.product)=lower(?) AND lower(v.version)=lower(?) ORDER BY m.source_id",
        (product, version),
    ).fetchall() if "version_artifacts" in tables else []
    sources = [r[0] for r in rows]
    missing = [] if sources else [f"{product} {version}"]
    dependencies = []
    if sources and "meta_source_dependencies" in tables:
        marks = ",".join("?" for _ in sources)
        dependencies = [r[0] for r in db.execute(
            f"SELECT dependency_source_id FROM meta_source_dependencies WHERE source_id IN ({marks})", sources)]
    if not dependencies:
        missing.append(f"Denizen-Core dependency for {product} {version}")
    return list(dict.fromkeys(sources + dependencies)), missing


def source_evidence(db, sources):
    if not sources:
        return []
    marks = ",".join("?" for _ in sources)
    return [dict(zip(("source_id", "commit_sha", "compatibility"), row)) for row in db.execute(
        f"SELECT source_id,commit_sha,compatibility FROM meta_sources WHERE source_id IN ({marks}) ORDER BY source_id", sources)]
