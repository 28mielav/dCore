"""Update the maintained dCore knowledge database.

Refreshes the five indexed Denizen Meta sources plus the diagnostic catalogue
embedded in the latest Refined DenizenScript VSIX.  Work is performed on a
temporary SQLite copy, validated, backed up, and atomically committed.

The updater works on an isolated copy and atomically installs a candidate only
after validation. It cannot replace a Custom GPT Knowledge attachment; that
final platform-controlled step remains manual.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import sqlite3
import tempfile
import urllib.request
import urllib.error
import zipfile
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


GITHUB_API = "https://api.github.com"
REFINED_RELEASE_API = f"{GITHUB_API}/repos/Humususus/refined-denizenScript/releases/latest"
SHARP_ZIP = "https://github.com/DenizenScript/SharpDenizenTools/archive/{commit}.zip"


@dataclass(frozen=True)
class MetaSource:
    source_id: str
    product: str
    owner: str
    repo: str
    branch: str
    compatibility: str
    authority: str
    precedence: int

    @property
    def repo_url(self) -> str:
        return f"https://github.com/{self.owner}/{self.repo}"


META_SOURCES = (
    MetaSource(
        "denizen_official_dev", "Denizen", "DenizenScript", "Denizen", "dev",
        "Official source Meta; DenizenM deviations still require fork/runtime proof.",
        "official GitHub source Meta", 70,
    ),
    MetaSource(
        "denizencore_official_master", "Denizen-Core", "DenizenScript", "Denizen-Core", "master",
        "Official shared core Meta; fork deviations still require runtime proof.",
        "official GitHub source Meta", 80,
    ),
    MetaSource(
        "denizenm_public_master", "DenizenM", "Energobro", "DenizenM-Tjtoxshpilivili1", "master",
        "Preferred public fork source for the configured target; installed runtime is final proof.",
        "public fork GitHub source Meta", 100,
    ),
    MetaSource(
        "voxizen_public_main", "Voxizen", "nybikyt", "Voxizen", "main",
        "Addon Meta; activate only for Simple Voice Chat or explicit Voxizen work.",
        "addon GitHub source Meta", 90,
    ),
    MetaSource(
        "denizen_reflect_public_main", "denizen-reflect", "isnsest", "denizen-reflect", "main",
        "Last-mile addon boundary; never prefer over native DenizenM or a dedicated addon API.",
        "addon GitHub source Meta", 85,
    ),
)

START_RE = re.compile(r"<--\[([A-Za-z_]+)]", re.IGNORECASE)
END_RE = re.compile(r"^\s*//\s*-->\s*$")
FIELD_RE = re.compile(r"^@([A-Za-z_]+)(?:\s+(.*))?$", re.IGNORECASE)
WARN_RE = re.compile(
    r'(?:\bWarn|\.Warn)\s*\(\s*(?:[^,]+\.)?'
    r'(Errors|Warnings|MinorWarnings)\s*,(?:(?!\);).)*?'
    r'"([A-Za-z0-9_]+)"\s*,\s*(?:\$)?"((?:\\.|[^"\\])*)"',
    re.DOTALL,
)
SHARP_COMMIT_RE = re.compile(
    rb"raw\.githubusercontent\.com/DenizenScript/SharpDenizenTools/([0-9a-f]{40})/"
)


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "dCore-knowledge-updater/1.0"})
    with urllib.request.urlopen(request, timeout=90) as response:
        return response.read()


def fetch_json(url: str):
    return json.loads(fetch(url))


def branch_head(source: MetaSource) -> str:
    data = fetch_json(
        f"{GITHUB_API}/repos/{source.owner}/{source.repo}/commits/{source.branch}"
    )
    return data["sha"]


def meta_heads() -> dict[str, str]:
    return {source.source_id: branch_head(source) for source in META_SOURCES}


def refined_release_info() -> tuple[str, str]:
    release = fetch_json(REFINED_RELEASE_API)
    asset = next(
        (item for item in release.get("assets", []) if item["name"].lower().endswith(".vsix")),
        None,
    )
    if not asset:
        raise RuntimeError("Latest Refined DenizenScript release has no VSIX asset")
    return release.get("tag_name", "unknown"), asset["browser_download_url"]


def latest_ide_bundle(asset_url: str) -> tuple[str, str, bytes, bytes]:
    vsix = fetch(asset_url)
    with zipfile.ZipFile(io.BytesIO(vsix)) as archive:
        names = archive.namelist()
        package_name = next(
            name for name in names if name.endswith("/package.json") or name == "extension/package.json"
        )
        package = json.loads(archive.read(package_name))
        pdb_name = next(name for name in names if name.endswith("/server/SharpDenizenTools.pdb"))
        dll_name = next(name for name in names if name.endswith("/server/SharpDenizenTools.dll"))
        match = SHARP_COMMIT_RE.search(archive.read(pdb_name))
        if not match:
            raise RuntimeError("VSIX PDB does not expose an exact SharpDenizenTools source commit")
        commit = match.group(1).decode("ascii")
        dll = archive.read(dll_name)
    sharp = fetch(SHARP_ZIP.format(commit=commit))
    return package["version"], commit, dll, sharp


def strip_comment(line: str) -> str:
    line = line.strip()
    if line.startswith("//"):
        line = line[2:].lstrip()
    elif line.startswith("*"):
        line = line[1:].lstrip()
    return line.rstrip()


def parse_blocks(text: str):
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        start = START_RE.search(lines[i])
        if not start:
            i += 1
            continue
        category = start.group(1).lower()
        start_line = i + 1
        body: list[str] = []
        closed = False
        i += 1
        while i < len(lines):
            if END_RE.match(lines[i]):
                closed = True
                i += 1
                break
            if START_RE.search(lines[i]):
                break
            stripped = lines[i].lstrip()
            if stripped and not (stripped.startswith("//") or stripped.startswith("*")):
                break
            body.append(strip_comment(lines[i]))
            i += 1
        yield category, start_line, body, closed


def parse_fields(body: list[str]) -> list[tuple[str, str]]:
    fields: list[tuple[str, str]] = []
    current_name: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_name, current_lines
        if current_name is not None:
            fields.append((current_name, "\n".join(current_lines).strip()))
        current_name = None
        current_lines = []

    for raw in body:
        match = FIELD_RE.match(raw)
        if match:
            flush()
            current_name = match.group(1).lower()
            current_lines = [match.group(2) or ""]
        elif current_name is not None:
            current_lines.append(raw)
    flush()
    return fields


def all_values(fields: list[tuple[str, str]], key: str) -> list[str]:
    return [value for name, value in fields if name == key and value]


def first_value(fields: list[tuple[str, str]], *keys: str) -> str:
    for key in keys:
        values = all_values(fields, key)
        if values:
            return values[0]
    return ""


def entry_name(category: str, fields: list[tuple[str, str]]) -> tuple[str, str]:
    object_type = first_value(fields, "object")
    if category == "command":
        return first_value(fields, "name", "syntax"), object_type
    if category == "event":
        value = first_value(fields, "events", "event")
        return (value.splitlines()[0] if value else "unnamed event"), object_type
    if category == "tag":
        return first_value(fields, "attribute", "name"), object_type
    if category == "mechanism":
        name = first_value(fields, "name")
        return (f"{object_type}.{name}" if object_type and name else name), object_type
    if category == "objecttype":
        return first_value(fields, "name", "prefix"), object_type
    if category == "action":
        value = first_value(fields, "actions", "action", "name")
        return (value.splitlines()[0] if value else "unnamed action"), object_type
    return first_value(fields, "name", "property", "extension", "data", "syntax"), object_type


def ensure_meta_schema(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS meta_sources(
          source_id TEXT PRIMARY KEY, product TEXT NOT NULL, repo_url TEXT NOT NULL,
          branch TEXT NOT NULL, commit_sha TEXT NOT NULL, fetched_at TEXT NOT NULL,
          authority TEXT NOT NULL, compatibility TEXT NOT NULL,
          precedence INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS meta_entries(
          entry_id INTEGER PRIMARY KEY,
          source_id TEXT NOT NULL REFERENCES meta_sources(source_id) ON DELETE CASCADE,
          category TEXT NOT NULL, name TEXT NOT NULL, object_type TEXT NOT NULL DEFAULT '',
          syntax TEXT NOT NULL DEFAULT '', summary TEXT NOT NULL DEFAULT '',
          description TEXT NOT NULL DEFAULT '', plugin TEXT NOT NULL DEFAULT '',
          group_name TEXT NOT NULL DEFAULT '', deprecated TEXT NOT NULL DEFAULT '',
          source_file TEXT NOT NULL, source_line INTEGER NOT NULL,
          raw_fields_json TEXT NOT NULL,
          UNIQUE(source_id,category,source_file,source_line));
        CREATE TABLE IF NOT EXISTS meta_fields(
          entry_id INTEGER NOT NULL REFERENCES meta_entries(entry_id) ON DELETE CASCADE,
          field_name TEXT NOT NULL, ordinal INTEGER NOT NULL, value TEXT NOT NULL,
          PRIMARY KEY(entry_id,field_name,ordinal));
        CREATE INDEX IF NOT EXISTS meta_entries_category_name ON meta_entries(category,name);
        CREATE INDEX IF NOT EXISTS meta_entries_object_type ON meta_entries(object_type,category);
        CREATE INDEX IF NOT EXISTS meta_fields_name ON meta_fields(field_name,entry_id);
        CREATE VIRTUAL TABLE IF NOT EXISTS meta_search USING fts5(
          entry_id UNINDEXED,category,name,object_type,syntax,summary,description,fields,
          tokenize='unicode61 remove_diacritics 2');
        CREATE TABLE IF NOT EXISTS meta_deltas(
          entry_id INTEGER PRIMARY KEY REFERENCES meta_entries(entry_id) ON DELETE CASCADE,
          baseline_entry_id INTEGER REFERENCES meta_entries(entry_id) ON DELETE SET NULL,
          delta_kind TEXT NOT NULL CHECK(delta_kind IN ('same','modified','fork_only','addon_only')));
        """
    )
    db.execute("DROP VIEW IF EXISTS meta_preferred")
    db.execute(
        """CREATE VIEW meta_preferred AS
           SELECT e.*,s.product,s.authority,s.precedence,s.commit_sha,
                  COALESCE(d.delta_kind,'unclassified') AS delta_kind
           FROM meta_entries e JOIN meta_sources s ON s.source_id=e.source_id
           LEFT JOIN meta_deltas d ON d.entry_id=e.entry_id"""
    )


def import_meta_source(
    db: sqlite3.Connection, source: MetaSource, commit: str, snapshot: bytes
) -> int:
    now = datetime.now(timezone.utc).isoformat()
    db.execute(
        """INSERT INTO meta_sources
           (source_id,product,repo_url,branch,commit_sha,fetched_at,authority,compatibility,precedence)
           VALUES(?,?,?,?,?,?,?,?,?)
           ON CONFLICT(source_id) DO UPDATE SET product=excluded.product,
             repo_url=excluded.repo_url,branch=excluded.branch,commit_sha=excluded.commit_sha,
             fetched_at=excluded.fetched_at,authority=excluded.authority,
             compatibility=excluded.compatibility,precedence=excluded.precedence""",
        (source.source_id, source.product, source.repo_url, source.branch, commit, now,
         source.authority, source.compatibility, source.precedence),
    )
    db.execute("DELETE FROM meta_entries WHERE source_id=?", (source.source_id,))
    count = 0
    with zipfile.ZipFile(io.BytesIO(snapshot)) as archive:
        java_names = sorted(name for name in archive.namelist() if name.endswith(".java"))
        if not java_names:
            raise RuntimeError(f"{source.product} snapshot contains no Java sources")
        root = java_names[0].split("/", 1)[0] + "/"
        for name in java_names:
            rel = name[len(root):] if name.startswith(root) else name
            text = archive.read(name).decode("utf-8", errors="replace")
            for category, line, body, closed in parse_blocks(text):
                if not closed:
                    continue
                fields = parse_fields(body)
                entry, object_type = entry_name(category, fields)
                if not entry:
                    entry = f"unnamed {category} at {rel}:{line}"
                raw_json = json.dumps(fields, ensure_ascii=False, separators=(",", ":"))
                cursor = db.execute(
                    """INSERT INTO meta_entries
                       (source_id,category,name,object_type,syntax,summary,description,
                        plugin,group_name,deprecated,source_file,source_line,raw_fields_json)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (source.source_id, category, entry, object_type,
                     first_value(fields, "syntax", "attribute", "events"),
                     first_value(fields, "short", "triggers"), first_value(fields, "description"),
                     first_value(fields, "plugin"), first_value(fields, "group"),
                     first_value(fields, "deprecated"), rel, line, raw_json),
                )
                entry_id = cursor.lastrowid
                ordinals: dict[str, int] = {}
                for field_name, value in fields:
                    ordinal = ordinals.get(field_name, 0)
                    ordinals[field_name] = ordinal + 1
                    db.execute(
                        "INSERT INTO meta_fields(entry_id,field_name,ordinal,value) VALUES(?,?,?,?)",
                        (entry_id, field_name, ordinal, value),
                    )
                searchable = "\n".join(f"{key}: {value}" for key, value in fields)
                db.execute(
                    "INSERT INTO meta_search VALUES(?,?,?,?,?,?,?,?)",
                    (entry_id, category, entry, object_type,
                     first_value(fields, "syntax", "attribute", "events"),
                     first_value(fields, "short", "triggers"),
                     first_value(fields, "description"), searchable),
                )
                count += 1
    return count


def classify_deltas(db: sqlite3.Connection) -> None:
    db.execute("DELETE FROM meta_deltas")
    official = {
        (row[1], row[2]): (row[0], row[3])
        for row in db.execute(
            """SELECT entry_id,category,lower(name),raw_fields_json FROM meta_entries
               WHERE source_id IN ('denizen_official_dev','denizencore_official_master')"""
        )
    }
    for entry_id, source_id, category, lowered, raw_json in db.execute(
        "SELECT entry_id,source_id,category,lower(name),raw_fields_json FROM meta_entries"
    ):
        if source_id == "denizenm_public_master":
            baseline = official.get((category, lowered))
            baseline_id = baseline[0] if baseline else None
            kind = "fork_only" if baseline is None else ("same" if raw_json == baseline[1] else "modified")
        elif source_id in {"voxizen_public_main", "denizen_reflect_public_main"}:
            baseline_id, kind = None, "addon_only"
        else:
            continue
        db.execute(
            "INSERT INTO meta_deltas(entry_id,baseline_entry_id,delta_kind) VALUES(?,?,?)",
            (entry_id, baseline_id, kind),
        )


def set_meta_metadata(db: sqlite3.Connection, heads: dict[str, str], counts: dict[str, int]) -> None:
    by_product = {source.product: heads[source.source_id] for source in META_SOURCES}
    values = {
        "meta.enabled": "true",
        "meta.authority": "layered GitHub source Meta: DenizenM, Denizen, Denizen-Core, Voxizen, denizen-reflect",
        "meta.imported_at": datetime.now(timezone.utc).isoformat(),
        "meta.entries": str(sum(counts.values())),
        "meta.sources": str(len(META_SOURCES)),
        "meta.denizen.commit": by_product["Denizen"],
        "meta.denizencore.commit": by_product["Denizen-Core"],
        "meta.denizenm.commit": by_product["DenizenM"],
        "meta.voxizen.commit": by_product["Voxizen"],
        "meta.reflect.commit": by_product["denizen-reflect"],
        "meta.target": "Paper 1.21.11 + latest public DenizenM; installed runtime remains final proof",
        "meta.raw_source_docs_included": "true",
        "meta.query_protocol": (
            "Search meta_search first; join meta_preferred and order precedence DESC. "
            "Read meta_fields and confirm contexts/switches/determinations and API types before coding."
        ),
    }
    db.executemany(
        "INSERT INTO metadata(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        values.items(),
    )


def parse_diagnostics(sharp_zip: bytes) -> list[tuple]:
    found = []
    seen: dict[str, int] = {}
    severity_map = {"Errors": "error", "Warnings": "warning", "MinorWarnings": "information"}
    enforce = {
        "yaml_load", "raw_tab_symbol", "uneven_tags", "missing_quotes", "unknown_command",
        "too_few_args", "too_many_args", "duplicate_key", "duplicate_script",
        "empty_command_section", "empty_section", "invalid_container", "wrong_type",
        "bad_adjust_no_mech",
    }
    with zipfile.ZipFile(io.BytesIO(sharp_zip)) as archive:
        names = sorted(name for name in archive.namelist() if "/ScriptAnalysis/" in name and name.endswith(".cs"))
        if not names:
            raise RuntimeError("SharpDenizenTools snapshot has no ScriptAnalysis sources")
        for name in names:
            text = archive.read(name).decode("utf-8")
            for match in WARN_RE.finditer(text):
                severity, code, message = match.groups()
                ordinal = seen.get(code, 0) + 1
                seen[code] = ordinal
                found.append((
                    f"sharp:{code}:{ordinal}", "sharp_denizen_tools_installed", code,
                    severity_map[severity], bytes(message, "utf-8").decode("unicode_escape"),
                    name, text.count("\n", 0, match.start()) + 1, "structural",
                    "enforce" if code in enforce else "advisory",
                ))
    if len(found) < 40:
        raise RuntimeError(f"Diagnostic extraction unexpectedly found only {len(found)} entries")
    return found


def ensure_ide_schema(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS ide_sources(
          source_id TEXT PRIMARY KEY,product TEXT NOT NULL,version TEXT NOT NULL,
          commit_sha TEXT NOT NULL,artifact_sha256 TEXT NOT NULL,repo_url TEXT NOT NULL,
          fetched_at TEXT NOT NULL,authority TEXT NOT NULL,compatibility TEXT NOT NULL,
          precedence INTEGER NOT NULL,license TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS ide_diagnostics(
          diagnostic_id TEXT PRIMARY KEY,
          source_id TEXT NOT NULL REFERENCES ide_sources(source_id) ON DELETE CASCADE,
          code TEXT NOT NULL,severity TEXT NOT NULL,message_template TEXT NOT NULL,
          source_file TEXT NOT NULL,source_line INTEGER NOT NULL,
          scope TEXT NOT NULL DEFAULT 'structural',policy TEXT NOT NULL DEFAULT 'advisory');
        CREATE INDEX IF NOT EXISTS ide_diagnostics_code ON ide_diagnostics(code,severity);
        CREATE TABLE IF NOT EXISTS ide_capabilities(
          capability_id TEXT PRIMARY KEY,
          source_id TEXT NOT NULL REFERENCES ide_sources(source_id) ON DELETE CASCADE,
          name TEXT NOT NULL,summary TEXT NOT NULL,boundary TEXT NOT NULL);
        CREATE VIRTUAL TABLE IF NOT EXISTS ide_search USING fts5(
          item_id UNINDEXED,kind,name,summary,source,
          tokenize='unicode61 remove_diacritics 2');
        """
    )


def import_ide(db: sqlite3.Connection, version: str, commit: str, dll: bytes, sharp: bytes) -> int:
    diagnostics = parse_diagnostics(sharp)
    now = datetime.now(timezone.utc).isoformat()
    db.execute(
        """INSERT INTO ide_sources VALUES(?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(source_id) DO UPDATE SET product=excluded.product,version=excluded.version,
             commit_sha=excluded.commit_sha,artifact_sha256=excluded.artifact_sha256,
             repo_url=excluded.repo_url,fetched_at=excluded.fetched_at,
             authority=excluded.authority,compatibility=excluded.compatibility,
             precedence=excluded.precedence,license=excluded.license""",
        ("sharp_denizen_tools_installed", "SharpDenizenTools", "1.0.0.0", commit,
         hashlib.sha256(dll).hexdigest(), "https://github.com/DenizenScript/SharpDenizenTools",
         now, "exact source commit embedded in latest Refined VSIX PDB",
         "Structural checker; advisory on conflicts with preferred DenizenM Meta.", 60, "MIT"),
    )
    db.execute(
        """INSERT INTO ide_sources VALUES(?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(source_id) DO UPDATE SET version=excluded.version,
             commit_sha=excluded.commit_sha,artifact_sha256=excluded.artifact_sha256,
             fetched_at=excluded.fetched_at,compatibility=excluded.compatibility""",
        ("refined_denizenscript_installed", "Refined DenizenScript", version, f"release-{version}",
         hashlib.sha256(dll).hexdigest(), "https://github.com/Humususus/refined-denizenScript",
         now, "latest public Refined VSIX", "Maintained update source.", 80, "MIT"),
    )
    db.execute("DELETE FROM ide_diagnostics WHERE source_id='sharp_denizen_tools_installed'")
    db.executemany(
        """INSERT INTO ide_diagnostics
           (diagnostic_id,source_id,code,severity,message_template,source_file,
            source_line,scope,policy) VALUES(?,?,?,?,?,?,?,?,?)""",
        diagnostics,
    )
    db.execute("DELETE FROM ide_search WHERE kind='diagnostic'")
    db.executemany(
        "INSERT INTO ide_search(item_id,kind,name,summary,source) VALUES(?,'diagnostic',?,?,'SharpDenizenTools')",
        [(row[0], row[2], row[4]) for row in diagnostics],
    )
    db.execute(
        "INSERT OR REPLACE INTO metadata(key,value) VALUES('ide.layer',?)",
        (f"Refined {version} + SharpDenizenTools {commit}; maintained update",),
    )
    return len(diagnostics)


def current_versions(db_path: Path) -> tuple[dict[str, str], dict[str, str]]:
    with closing(sqlite3.connect(db_path)) as db:
        meta_exists = db.execute("SELECT 1 FROM sqlite_master WHERE name='meta_sources'").fetchone()
        ide_exists = db.execute("SELECT 1 FROM sqlite_master WHERE name='ide_sources'").fetchone()
        meta = dict(db.execute("SELECT source_id,commit_sha FROM meta_sources")) if meta_exists else {}
        ide = dict(db.execute("SELECT product,version || ' @ ' || commit_sha FROM ide_sources")) if ide_exists else {}
    return meta, ide


def network_failure_payload(exc: Exception, update_required=None) -> dict:
    return {
        "update_required": update_required,
        "network_available": False,
        "database_modified": False,
        "error_type": type(exc).__name__,
        "error": str(exc),
    }


def apply_update(
    db_path: Path,
    heads: dict[str, str],
    snapshots: dict[str, bytes],
    ide_bundle: tuple[str, str, bytes, bytes],
) -> tuple[Path, dict[str, int], int]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = db_path.with_name(f"{db_path.stem}.pre_update_{stamp}{db_path.suffix}")
    with tempfile.TemporaryDirectory(prefix="dcore_update_") as temp:
        candidate = Path(temp) / db_path.name
        shutil.copy2(db_path, candidate)
        with closing(sqlite3.connect(candidate)) as db:
            db.execute("PRAGMA foreign_keys=ON")
            ensure_meta_schema(db)
            ensure_ide_schema(db)
            db.execute("DELETE FROM meta_search")
            counts = {
                source.product: import_meta_source(
                    db, source, heads[source.source_id], snapshots[source.source_id]
                )
                for source in META_SOURCES
            }
            classify_deltas(db)
            set_meta_metadata(db, heads, counts)
            diagnostics = import_ide(db, *ide_bundle)
            db.execute("INSERT INTO meta_search(meta_search) VALUES('optimize')")
            db.execute("INSERT INTO ide_search(ide_search) VALUES('optimize')")
            db.commit()
            integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
            foreign_keys = db.execute("PRAGMA foreign_key_check").fetchall()
            if integrity != "ok" or foreign_keys:
                raise RuntimeError(f"candidate database failed validation: {integrity}, FK={len(foreign_keys)}")
            total = db.execute("SELECT count(*) FROM meta_entries").fetchone()[0]
            if total < 4500:
                raise RuntimeError(f"Meta import unexpectedly small: {total}")
            codes = {row[0] for row in db.execute("SELECT code FROM ide_diagnostics")}
            if not {"yaml_load", "too_many_args", "unknown_command", "duplicate_script"} <= codes:
                raise RuntimeError("critical IDE diagnostic definitions are missing")
            # Repeated session updates otherwise retain deleted FTS/database
            # pages and inflate the Knowledge attachment on every refresh.
            db.execute("VACUUM")
            if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("candidate database failed validation after VACUUM")
        shutil.copy2(db_path, backup)
        os.replace(candidate, db_path)
    return backup, counts, diagnostics


def main() -> int:
    parser = argparse.ArgumentParser(description="Update the maintained dCore knowledge database")
    parser.add_argument(
        "--db",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "knowledge" / "dcore.sqlite",
    )
    parser.add_argument(
        "--output", type=Path,
        help="write the validated candidate here instead of replacing --db",
    )
    parser.add_argument("--check", action="store_true", help="compare versions without rebuilding the DB")
    args = parser.parse_args()

    target = args.output or args.db
    current_path = target if target.exists() else args.db
    current_meta, current_ide = current_versions(current_path)
    try:
        heads = meta_heads()
        release_tag, asset_url = refined_release_info()
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, KeyError, RuntimeError) as exc:
        print(json.dumps(network_failure_payload(exc), ensure_ascii=False))
        return 0 if args.check else 2
    stale_meta = [source.product for source in META_SOURCES if current_meta.get(source.source_id) != heads[source.source_id]]
    current_refined = current_ide.get("Refined DenizenScript", "none")
    refined_stale = release_tag.lstrip("v") not in current_refined
    print(json.dumps({
        "update_required": bool(stale_meta or refined_stale),
        "network_available": True,
        "database_modified": False,
        "meta_stale": stale_meta,
        "refined_latest": release_tag,
        "refined_current": current_refined,
        "refined_stale": refined_stale,
    }, ensure_ascii=False))
    if args.check:
        return 0

    try:
        snapshots = {
            source.source_id: fetch(f"{source.repo_url}/archive/{heads[source.source_id]}.zip")
            for source in META_SOURCES
        }
        ide_bundle = latest_ide_bundle(asset_url)
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, KeyError, zipfile.BadZipFile, RuntimeError) as exc:
        print(json.dumps(network_failure_payload(exc, True), ensure_ascii=False))
        return 2
    if target != args.db and not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(args.db, target)
    backup, counts, diagnostics = apply_update(target, heads, snapshots, ide_bundle)
    print(json.dumps({
        "updated": str(target),
        "backup": str(backup),
        "meta_entries": counts,
        "ide_diagnostics": diagnostics,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
