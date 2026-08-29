"""Static, portable checks for Minecraft resource-pack shader pipelines.

A STATIC_OK result proves only the checks in this file.  Rendering route selection,
reload behaviour, F5, FPS and lifecycle behaviour remain RUNTIME_UNVERIFIED.
"""

from __future__ import annotations

import argparse
import json
import re
import textwrap
import sys
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

INCLUDE = re.compile(r'^\s*#moj_import\s+(?:<([^>]+)>|"([^"]+)")', re.MULTILINE)
UNIFORM = re.compile(r'\buniform\s+([A-Za-z_]\w*)\s+([A-Za-z_]\w*)\s*(?:\[\s*\d+\s*\])?\s*;')
VARYING_OUT = re.compile(r'\b(?:out|varying)\s+([A-Za-z_]\w*)\s+([A-Za-z_]\w*)\s*;')
VARYING_IN = re.compile(r'\b(?:in|varying)\s+([A-Za-z_]\w*)\s+([A-Za-z_]\w*)\s*;')
VERTEX_INPUT = re.compile(r'\b(?:in|attribute)\s+([A-Za-z_]\w*)\s+([A-Za-z_]\w*)\s*;')
MARKER_COMMENT = re.compile(r'\bdcore[-_: ]marker[-_: ]channel\s*[:=]\s*([A-Za-z0-9_.-]+)', re.I)
ROUTE_COMMENT = re.compile(r'\bdcore[-_: ]core[-_: ]route\s*[:=]\s*([A-Za-z0-9_.-]+)', re.I)


@dataclass
class Pack:
    """A tiny virtual filesystem over a directory or a zip archive."""

    label: str
    files: dict[str, bytes]

    @classmethod
    def open(cls, source: Path) -> "Pack":
        if source.is_dir():
            files = {p.relative_to(source).as_posix(): p.read_bytes() for p in source.rglob("*") if p.is_file()}
        elif source.is_file() and zipfile.is_zipfile(source):
            with zipfile.ZipFile(source) as archive:
                files = {i.filename.replace("\\", "/"): archive.read(i) for i in archive.infolist() if not i.is_dir()}
        else:
            raise ValueError("input must be a resource-pack directory or a readable zip archive")
        return cls(str(source), files)

    def text(self, name: str) -> str:
        return self.files[name].decode("utf-8", errors="replace")

    def resolve(self, wanted: str) -> tuple[str | None, bool]:
        wanted = wanted.replace("\\", "/").lstrip("/")
        if wanted in self.files:
            return wanted, False
        matches = [name for name in self.files if name.casefold() == wanted.casefold()]
        return (matches[0], True) if len(matches) == 1 else (None, False)


def issue(code: str, severity: str, path: str, message: str, **extra: Any) -> dict[str, Any]:
    result: dict[str, Any] = {"code": code, "severity": severity, "path": path, "layer": "static", "message": message}
    result.update(extra)
    return result


def names(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [x if isinstance(x, str) else x["name"] for x in value if isinstance(x, str) or isinstance(x, dict) and isinstance(x.get("name"), str)]


def extension_values(value: Any, keys: set[str]) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key.casefold().replace("-", "_") in keys:
                if isinstance(child, str):
                    found.append(child)
                elif isinstance(child, list):
                    found.extend(x for x in child if isinstance(x, str))
            found.extend(extension_values(child, keys))
    elif isinstance(value, list):
        for child in value:
            found.extend(extension_values(child, keys))
    return found


def shader_source_candidates(json_path: str, stage_name: str, suffix: str) -> list[str]:
    """Resolve both legacy relative stage names and namespaced shader IDs."""
    current = PurePosixPath(json_path)
    parts = current.parts
    try:
        assets = parts.index("assets")
        shaders = parts.index("shaders", assets + 2)
    except ValueError:
        return [str(current.parent / f"{stage_name}.{suffix}")]
    if ":" in stage_name:
        namespace, resource = stage_name.split(":", 1)
        return [str(PurePosixPath(*parts[:assets]) / "assets" / namespace / "shaders" / f"{resource}.{suffix}")]
    shader_root = PurePosixPath(*parts[:shaders + 1])
    candidates = [
        str(current.parent / f"{stage_name}.{suffix}"),
        str(shader_root / f"{stage_name}.{suffix}"),
    ]
    return list(dict.fromkeys(candidates))


def include_path(current: str, target: str, angle: bool) -> str:
    if angle:
        path = PurePosixPath(current)
        if ":" in target:
            namespace, resource = target.split(":", 1)
            parts = path.parts
            if "assets" in parts:
                assets = parts.index("assets")
                return str(PurePosixPath(*parts[:assets]) / "assets" / namespace / "shaders" / "include" / resource)
        # Angle imports are rooted at assets/<namespace>/shaders/include,
        # including when the importing file is already in include/.
        parts = path.parts
        indices = [index for index, part in enumerate(parts) if part == "shaders"]
        if indices:
            return str(PurePosixPath(*parts[:indices[-1] + 1]) / "include" / target)
        return str(path.parent / "include" / target)
    return str(PurePosixPath(current).parent / target)


def lint_pack(pack: Pack, minecraft: str | None = None, pack_format: float | None = None) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    parsed: dict[str, Any] = {}
    folds: defaultdict[str, list[str]] = defaultdict(list)
    for path in pack.files:
        folds[path.casefold()].append(path)
    for paths in folds.values():
        if len(paths) > 1:
            issues.append(issue("path_case_collision", "error", paths[0], "Paths differ only by case and are not portable.", paths=sorted(paths)))

    for path in sorted(pack.files):
        if path.lower().endswith(".json"):
            try:
                parsed[path] = json.loads(pack.text(path))
            except json.JSONDecodeError as exc:
                issues.append(issue("invalid_json", "error", path, f"Invalid JSON: {exc.msg} (line {exc.lineno}, column {exc.colno})."))

    sources = [p for p in pack.files if p.lower().endswith((".vsh", ".fsh", ".glsl"))]
    edges: defaultdict[str, list[str]] = defaultdict(list)
    for path in sources:
        for bracketed, quoted in INCLUDE.findall(pack.text(path)):
            target = bracketed or quoted
            wanted = include_path(path, target, bool(bracketed))
            actual, wrong_case = pack.resolve(wanted)
            if actual is None:
                if bracketed and target.startswith("minecraft:"):
                    issues.append(issue(
                        "vanilla_moj_import_not_in_pack", "warning", path,
                        f"#moj_import '{target}' is not bundled; prove the exact target client supplies it.",
                        expected=wanted,
                    ))
                else:
                    issues.append(issue("missing_moj_import", "error", path, f"#moj_import cannot resolve '{target}'.", expected=wanted))
            else:
                edges[path].append(actual)
                if wrong_case:
                    issues.append(issue("path_case_mismatch", "error", path, f"Import uses '{wanted}', but pack contains '{actual}'."))

    visiting: set[str] = set()
    visited: set[str] = set()
    def walk(node: str, stack: list[str]) -> None:
        if node in visiting:
            begin = stack.index(node) if node in stack else 0
            issues.append(issue("moj_import_cycle", "error", node, "#moj_import cycle detected.", cycle=stack[begin:] + [node]))
            return
        if node in visited:
            return
        visiting.add(node)
        for child in edges[node]:
            walk(child, stack + [node])
        visiting.remove(node)
        visited.add(node)
    for source in sources:
        walk(source, [])

    route_claims: defaultdict[str, list[str]] = defaultdict(list)
    marker_claims: defaultdict[str, list[str]] = defaultdict(list)
    for path, document in parsed.items():
        if not isinstance(document, dict):
            continue
        core = "/shaders/core/" in f"/{path}" and path.endswith(".json")
        if core:
            for route in extension_values(document, {"dcore_core_route", "core_shader_route"}):
                route_claims[route].append(path)
        if "/shaders/" in f"/{path}" and any(
            key in document for key in ("vertex", "fragment", "vertex_shader", "fragment_shader")
        ):
            lint_core_shader(pack, path, document, issues)
        for channel in extension_values(document, {"dcore_marker_channel", "reserved_marker_channel"}):
            marker_claims[channel].append(path)
        if ("passes" in document or "targets" in document) and (
            "/shaders/post/" in f"/{path}" or "/post_effect/" in f"/{path}"
        ):
            lint_post_chain(pack, path, document, issues)

    for path in sources:
        for channel in MARKER_COMMENT.findall(pack.text(path)):
            marker_claims[channel].append(path)
        if "/shaders/core/" in f"/{path}":
            for route in ROUTE_COMMENT.findall(pack.text(path)):
                route_claims[route].append(path)
    for code, severity, claims, label in (
        ("conflicting_core_shader_route_override", "error", route_claims, "Core route"),
        ("reserved_marker_channel_duplicate", "warning", marker_claims, "Reserved marker channel"),
    ):
        for name, paths in claims.items():
            unique = sorted(set(paths))
            if len(unique) > 1:
                issues.append(issue(code, severity, unique[0], f"{label} '{name}' is claimed more than once; verify that this is one owner spanning stages, not two providers.", paths=unique, name=name))

    # Since 1.21.2, post-effect *programs* legitimately live under
    # shaders/post while effect graphs live under post_effect. Only graph JSON
    # at the legacy path is evidence of a mixed schema; counting every modern
    # stage/source there produced a warning for every valid modern pack.
    legacy_post = sorted(
        path for path, value in parsed.items()
        if "/shaders/post/" in f"/{path}" and path.endswith(".json")
        and isinstance(value, dict) and ("passes" in value or "targets" in value)
    )
    modern_post = sorted(
        path for path in parsed if "/post_effect/" in f"/{path}" and path.endswith(".json")
    )
    if legacy_post and modern_post:
        issues.append(issue(
            "mixed_post_schema_paths", "warning", legacy_post[0],
            "The pack contains both legacy shaders/post and modern post_effect graphs; prove the target client uses the intended one.",
            legacy_count=len(legacy_post), modern_count=len(modern_post),
        ))

    if minecraft is None and pack_format is None:
        issues.append(issue("version_scope_missing", "warning", "pack.mcmeta", "No --minecraft or --pack-format supplied; version-sensitive checks are unscoped."))
    check_pack_format(parsed.get("pack.mcmeta"), pack_format, issues)
    static = "ERROR" if any(item["severity"] == "error" for item in issues) else "STATIC_OK"
    return {
        "schema_version": 1, "input": pack.label,
        "scope": {"minecraft": minecraft, "pack_format": pack_format, "scoped": minecraft is not None or pack_format is not None},
        "verdict": static, "static_verdict": static, "runtime_verdict": "RUNTIME_UNVERIFIED",
        "statuses": [static, "RUNTIME_UNVERIFIED"], "issue_counts": dict(Counter(x["severity"] for x in issues)),
        "issues": issues,
        "route_census": {
            "core_program_json": sorted(path for path in parsed if "/shaders/core/" in f"/{path}"),
            "shader_program_json": sorted(path for path, value in parsed.items() if "/shaders/" in f"/{path}" and isinstance(value, dict) and any(key in value for key in ("vertex", "fragment", "vertex_shader", "fragment_shader"))),
            "legacy_post_json": legacy_post,
            "modern_post_json": modern_post,
            "glsl_sources": sorted(sources),
        },
        "proof_checklist": proof_checklist(minecraft, pack_format),
    }


def lint_core_shader(pack: Pack, path: str, document: dict[str, Any], issues: list[dict[str, Any]]) -> None:
    stages: dict[str, str] = {}
    for field, modern_field, suffix in (("vertex", "vertex_shader", "vsh"), ("fragment", "fragment_shader", "fsh")):
        stage_name = document.get(field, document.get(modern_field))
        if not isinstance(stage_name, str) or not stage_name:
            issues.append(issue("missing_shader_stage", "error", path, f"Shader program JSON requires non-empty '{field}' or '{modern_field}'."))
            continue
        candidates = shader_source_candidates(path, stage_name, suffix)
        resolved = [(candidate, *pack.resolve(candidate)) for candidate in candidates]
        match = next((item for item in resolved if item[1] is not None), None)
        wanted = candidates[0]
        actual, wrong_case = (match[1], match[2]) if match else (None, False)
        if actual is None:
            # A minecraft: stage can deliberately reuse a client-owned vanilla
            # source that is absent from this override pack. Static inspection
            # cannot prove that source for an arbitrary target build.
            if stage_name.startswith("minecraft:"):
                issues.append(issue(
                    "vanilla_shader_stage_not_in_pack", "warning", path,
                    f"{field.title()} stage '{stage_name}' is not bundled; prove the exact target client supplies it.",
                    expected_any=candidates,
                ))
            else:
                issues.append(issue("missing_shader_stage_file", "error", path, f"{field.title()} stage '{stage_name}' is missing.", expected_any=candidates))
        else:
            stages[field] = actual
            if wrong_case:
                issues.append(issue("path_case_mismatch", "error", path, f"Stage declares '{wanted}', but pack contains '{actual}'."))

    attributes = names(document.get("attributes"))
    duplicates = sorted(name for name, count in Counter(attributes).items() if count > 1)
    if duplicates:
        issues.append(issue("duplicate_shader_attribute", "error", path, "Shader JSON declares an attribute more than once.", names=duplicates))
    if "vertex" not in stages or "fragment" not in stages:
        return
    vertex, fragment = pack.text(stages["vertex"]), pack.text(stages["fragment"])
    inputs = {name: kind for kind, name in VERTEX_INPUT.findall(vertex)}
    missing = [name for name in attributes if name not in inputs]
    if missing:
        issues.append(issue("shader_attribute_not_declared", "warning", path, "JSON attributes have no matching vertex input.", names=missing))

    vu = {name: kind for kind, name in UNIFORM.findall(vertex)}
    fu = {name: kind for kind, name in UNIFORM.findall(fragment)}
    for name in sorted(set(vu) & set(fu)):
        if vu[name] != fu[name]:
            issues.append(issue("uniform_type_mismatch", "error", path, f"Uniform '{name}' has different vertex and fragment types."))
    for name in names(document.get("uniforms")):
        if name not in vu and name not in fu:
            issues.append(issue("uniform_not_declared", "warning", path, f"JSON uniform '{name}' is absent from both stages."))
    source_samplers = {name for name, kind in {**vu, **fu}.items() if kind.startswith("sampler")}
    for name in names(document.get("samplers")):
        if name not in source_samplers:
            issues.append(issue("sampler_not_declared", "warning", path, f"JSON sampler '{name}' is absent from both stages."))

    vo = {name: kind for kind, name in VARYING_OUT.findall(vertex)}
    fi = {name: kind for kind, name in VARYING_IN.findall(fragment)}
    for name, kind in fi.items():
        if name.startswith("gl_"):
            continue
        if name not in vo:
            issues.append(issue("fragment_varying_without_vertex_output", "warning", path, f"Fragment input '{name}' has no vertex output."))
        elif vo[name] != kind:
            issues.append(issue("varying_type_mismatch", "error", path, f"Varying '{name}' has different vertex and fragment types."))


def target_name(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict) and isinstance(value.get("name"), str):
        return value["name"]
    return None


def shader_program_json_path(reference: str) -> str:
    namespace, resource = reference.split(":", 1) if ":" in reference else ("minecraft", reference)
    return f"assets/{namespace}/shaders/{resource}.json"


def legacy_program_json_path(reference: str) -> str:
    namespace, resource = reference.split(":", 1) if ":" in reference else ("minecraft", reference)
    return f"assets/{namespace}/shaders/program/{resource}.json"


def lint_post_chain(pack: Pack, path: str, document: dict[str, Any], issues: list[dict[str, Any]]) -> None:
    raw_targets = document.get("targets", [])
    if isinstance(raw_targets, dict):
        targets = [str(value) for value in raw_targets]
    else:
        targets = [target_name(value) for value in raw_targets] if isinstance(raw_targets, list) else []
    targets = [value for value in targets if value]
    duplicates = sorted(name for name, count in Counter(targets).items() if count > 1)
    if duplicates:
        issues.append(issue("duplicate_shader_target", "error", path, "Post chain defines a target more than once.", names=duplicates))
    known = set(targets) | {"main", "minecraft:main"}
    known_target = lambda value: isinstance(value, str) and (value in known or ":" in value)
    passes = document.get("passes")
    if passes is not None and not isinstance(passes, list):
        issues.append(issue("invalid_shader_passes", "error", path, "'passes' must be an array."))
        return
    for index, shader_pass in enumerate(passes or []):
        if not isinstance(shader_pass, dict):
            issues.append(issue("invalid_shader_pass", "error", path, f"Pass {index} must be an object."))
            continue
        modern = "inputs" in shader_pass or "output" in shader_pass
        if modern:
            inputs = shader_pass.get("inputs", [])
            outgoing = shader_pass.get("output")
            if not isinstance(inputs, list):
                issues.append(issue("invalid_shader_inputs", "error", path, f"Pass {index} 'inputs' must be an array."))
                inputs = []
            input_targets: list[str] = []
            for input_index, item in enumerate(inputs):
                target = item.get("target") if isinstance(item, dict) else None
                if not isinstance(target, str):
                    issues.append(issue("missing_shader_pass_target", "error", path, f"Pass {index} input {input_index} lacks string 'target'."))
                elif not known_target(target):
                    issues.append(issue("unknown_shader_target", "error", path, f"Pass {index} references unknown input target '{target}'."))
                else:
                    input_targets.append(target)
            if not isinstance(outgoing, str):
                issues.append(issue("missing_shader_pass_target", "error", path, f"Pass {index} lacks string 'output'."))
            elif not known_target(outgoing):
                issues.append(issue("unknown_shader_target", "error", path, f"Pass {index} references unknown output '{outgoing}'."))
            if isinstance(outgoing, str) and outgoing in input_targets:
                issues.append(issue("shader_pass_read_write_hazard", "warning", path, f"Pass {index} reads and writes '{outgoing}' in one pass."))
            program = shader_pass.get("program")
            if not isinstance(program, str) or not program:
                issues.append(issue("missing_shader_program", "error", path, f"Pass {index} lacks string 'program'."))
            else:
                wanted = shader_program_json_path(program)
                actual, wrong_case = pack.resolve(wanted)
                if actual is None:
                    issues.append(issue(
                        "shader_program_not_in_pack", "warning", path,
                        f"Pass {index} program '{program}' is not present in this pack; prove it is supplied by the target client or merge input.",
                        expected=wanted,
                    ))
                elif wrong_case:
                    issues.append(issue("path_case_mismatch", "error", path, f"Program declares '{wanted}', but pack contains '{actual}'."))
            continue

        incoming, outgoing = shader_pass.get("intarget"), shader_pass.get("outtarget")
        for role, target in (("intarget", incoming), ("outtarget", outgoing)):
            if not isinstance(target, str):
                issues.append(issue("missing_shader_pass_target", "error", path, f"Pass {index} lacks string '{role}'."))
            elif not known_target(target):
                issues.append(issue("unknown_shader_target", "error", path, f"Pass {index} references unknown {role} '{target}'."))
        if isinstance(incoming, str) and incoming == outgoing:
            issues.append(issue("shader_pass_read_write_hazard", "warning", path, f"Pass {index} reads and writes '{incoming}' in one pass."))
        program = shader_pass.get("name")
        if not isinstance(program, str) or not program:
            issues.append(issue("missing_shader_program", "error", path, f"Pass {index} lacks string 'name'."))
        else:
            wanted = legacy_program_json_path(program)
            actual, wrong_case = pack.resolve(wanted)
            if actual is None:
                severity = "warning" if program.startswith("minecraft:") or ":" not in program else "error"
                issues.append(issue(
                    "shader_program_not_in_pack", severity, path,
                    f"Pass {index} program '{program}' is not present in this pack.",
                    expected=wanted,
                ))
            elif wrong_case:
                issues.append(issue("path_case_mismatch", "error", path, f"Program declares '{wanted}', but pack contains '{actual}'."))
        for auxiliary in shader_pass.get("auxtargets", []):
            name = target_name(auxiliary)
            if name and not known_target(name):
                issues.append(issue("unknown_shader_target", "error", path, f"Pass {index} auxiliary target '{name}' is not defined."))


def check_pack_format(meta: Any, requested: float | None, issues: list[dict[str, Any]]) -> None:
    if requested is None or not isinstance(meta, dict) or not isinstance(meta.get("pack"), dict):
        return
    value = meta["pack"].get("pack_format")
    if isinstance(value, (int, float)) and value != requested:
        issues.append(issue("pack_format_mismatch", "warning", "pack.mcmeta", f"pack.mcmeta declares {value}, but --pack-format is {requested}."))
    if isinstance(value, dict):
        low, high = value.get("min_format"), value.get("max_format")
        if (isinstance(low, (int, float)) and requested < low) or (isinstance(high, (int, float)) and requested > high):
            issues.append(issue("pack_format_out_of_range", "warning", "pack.mcmeta", f"--pack-format {requested} is outside the declared range."))


def proof_checklist(minecraft: str | None, pack_format: float | None) -> list[dict[str, str]]:
    scope = minecraft or (f"pack format {pack_format}" if pack_format is not None else "the target Minecraft build")
    return [
        {"id": "route-census", "status": "RUNTIME_UNVERIFIED", "check": f"On {scope}, prove the final merged pack selects this route for the exact object."},
        {"id": "marker-control", "status": "RUNTIME_UNVERIFIED", "check": "Prove one marked carrier changes and an unmarked control does not."},
        {"id": "render-matrix", "status": "RUNTIME_UNVERIFIED", "check": "Check reload, F5/FOV/resize, culling, transparency, graphics modes, and collateral routes."},
        {"id": "lifecycle-performance", "status": "RUNTIME_UNVERIFIED", "check": "Check multiple viewers, reset/cleanup, and FPS/GPU cost."},
    ]


def _table_cell(value: object, width: int = 88) -> str:
    text = " ".join(str(value).replace("|", "\\|").split())
    return textwrap.shorten(text, width=width, placeholder="...") if len(text) > width else text


def render_report_table(report: dict[str, Any]) -> str:
    rows = ["| Sev | Code | Path | Problem |", "|---|---|---|---|"]
    for item in report.get("issues", []):
        rows.append(
            f"| {item['severity'].upper()} | `{item['code']}` | `{item.get('path', '-')}` | "
            f"{_table_cell(item['message'])} |"
        )
    if not report.get("issues"):
        rows.append("| PASS | - | - | No static diagnostics. |")
    counts = Counter(item["severity"] for item in report.get("issues", []))
    rows.extend([
        "",
        "| Static | Runtime | Error | Warning |",
        "|---|---|---:|---:|",
        f"| **{report['static_verdict']}** | **{report['runtime_verdict']}** | {counts['error']} | {counts['warning']} |",
        "",
        "Runtime proof still required:",
        "",
        "| Check | Status |",
        "|---|---|",
    ])
    rows.extend(
        f"| {_table_cell(item['check'])} | {item['status']} |"
        for item in report.get("proof_checklist", [])
    )
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Static Minecraft resource-pack and shader pipeline linter.")
    parser.add_argument("input", type=Path, help="Resource-pack directory or zip archive")
    parser.add_argument("--minecraft", help="Target Minecraft version")
    parser.add_argument("--pack-format", type=float, help="Target resource-pack format (integer or decimal)")
    parser.add_argument("--json", action="store_true", help="Emit machine JSON instead of the human table")
    parser.add_argument("--format", choices=("table", "json"), default="table")
    parser.add_argument("--probe-plan", action="store_true", help="Include runtime checklist (included by default)")
    args = parser.parse_args(argv)
    try:
        report = lint_pack(Pack.open(args.input), args.minecraft, args.pack_format)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        report = {"verdict": "ERROR", "static_verdict": "ERROR", "runtime_verdict": "RUNTIME_UNVERIFIED", "statuses": ["ERROR", "RUNTIME_UNVERIFIED"], "issues": [issue("input_error", "error", str(args.input), str(exc))], "proof_checklist": proof_checklist(args.minecraft, args.pack_format)}
    if args.json or args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(render_report_table(report))
    return 1 if report["static_verdict"] == "ERROR" else 0


if __name__ == "__main__":
    raise SystemExit(main())
