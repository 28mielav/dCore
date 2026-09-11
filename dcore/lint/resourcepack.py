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
from dcore.lint.shader_profiles import PROFILES

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
    if ":" in stage_name:
        namespace, resource = stage_name.split(":", 1)
        prefix = PurePosixPath(*parts[:parts.index("assets")]) if "assets" in parts else PurePosixPath()
        return [str(prefix / "assets" / namespace / "shaders" / f"{resource}.{suffix}")]
    try:
        assets = parts.index("assets")
        shaders = parts.index("shaders", assets + 2)
    except ValueError:
        return [str(current.parent / f"{stage_name}.{suffix}")]
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


def lint_pack(pack: Pack, minecraft: str | None = None, pack_format: float | None = None,
              graphics_mode: str | None = None, renderer: str = "vanilla",
              external_targets: tuple[str, ...] = ()) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    resolved_format = PROFILES.get(minecraft, {}).get("resource_format", pack_format)
    pack, applied_overlays = select_overlays(pack, resolved_format, issues)
    parsed: dict[str, Any] = {}
    folds: defaultdict[str, list[str]] = defaultdict(list)
    profile = PROFILES.get(minecraft, {})
    if profile.get("core_shaders") is False and renderer == "vanilla":
        for path in pack.files:
            if "/shaders/core/" in f"/{path}":
                issues.append(issue("core_shader_route_unavailable", "error", path,
                    f"Vanilla {minecraft} does not expose the resource-pack core shader pipeline introduced in 21w10a; use its legacy post route or declare a renderer mod."))
    for path in pack.files:
        folds[path.casefold()].append(path)
    for paths in folds.values():
        if len(paths) > 1:
            issues.append(issue("path_case_collision", "error", paths[0], "Paths differ only by case and are not portable.", paths=sorted(paths)))

    for path in sorted(pack.files):
        if path.lower().endswith((".json", ".mcmeta")):
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
                if minecraft in PROFILES and wanted in PROFILES[minecraft]["shader_files"]:
                    continue
                if minecraft in PROFILES and bracketed and target.startswith("minecraft:"):
                    issues.append(issue("vanilla_moj_import_unavailable", "error", path,
                                        f"Import '{target}' is absent from the official {minecraft} client and this pack.", expected=wanted))
                    continue
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
            lint_core_shader(pack, path, document, issues, minecraft)
        for channel in extension_values(document, {"dcore_marker_channel", "reserved_marker_channel"}):
            marker_claims[channel].append(path)
        if ("passes" in document or "targets" in document) and (
            "/shaders/post/" in f"/{path}" or "/post_effect/" in f"/{path}"
        ):
            lint_post_chain(pack, path, document, issues, minecraft, graphics_mode, renderer, external_targets)

    for path in sources:
        shader_text = re.sub(r"/\*.*?\*/|//[^\n]*", "", pack.text(path), flags=re.S)
        if profile and renderer == "vanilla" and path.startswith("assets/minecraft/shaders/core/") and path not in profile["shader_files"]:
            issues.append(issue("core_shader_override_unreferenced", "warning", path,
                f"The official {minecraft} client has no core stage at this path. This file does not override a vanilla stage; prove an explicit custom reference or use the target's actual route."))
        if path.endswith(".vsh") and "/shaders/core/" in f"/{path}" and re.search(r"\bgl_Position\s*=\s*vec4\s*\(", shader_text):
            issues.append(issue("screen_space_carrier_culling_unverified", "information", path,
                "Direct clip-space placement runs only after the carrier reaches this draw call. It cannot repair CPU frustum culling, an absent producer or the wrong render route; mount/view_range are not proof of screen attachment."))
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
    expected_format = profile.get("resource_format")
    if expected_format is not None and pack_format is not None and pack_format != expected_format:
        issues.append(issue("target_pack_format_mismatch", "error", "pack.mcmeta",
                            f"Minecraft {minecraft} uses resource format {expected_format}, not {pack_format}."))
    check_pack_format(parsed.get("pack.mcmeta"), expected_format if expected_format is not None else pack_format, issues, minecraft)
    static = "ERROR" if any(item["severity"] == "error" for item in issues) else "STATIC_OK"
    return {
        "schema_version": 1, "input": pack.label,
        "scope": {"minecraft": minecraft, "pack_format": pack_format,
                  "resolved_pack_format": expected_format, "post_schema": profile.get("post_schema"),
                  "client_sha1": profile.get("client_sha1"),
                  "applied_overlays": applied_overlays,
                  "scoped": minecraft is not None or pack_format is not None},
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


def lint_core_shader(pack: Pack, path: str, document: dict[str, Any], issues: list[dict[str, Any]], minecraft: str | None = None) -> None:
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
                if minecraft in PROFILES:
                    if wanted not in PROFILES[minecraft]["shader_files"]:
                        issues.append(issue("vanilla_shader_stage_unavailable", "error", path,
                                            f"Stage '{stage_name}' is absent from the official {minecraft} client and this pack.", expected_any=candidates))
                    continue
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
    for name in names(document.get("uniforms")) if not isinstance(document.get("uniforms"), dict) else []:
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


def lint_post_chain(pack: Pack, path: str, document: dict[str, Any], issues: list[dict[str, Any]],
                    minecraft: str | None = None, graphics_mode: str | None = None,
                    renderer: str = "vanilla", external_targets: tuple[str, ...] = ()) -> None:
    raw_targets = document.get("targets", [])
    if isinstance(raw_targets, dict):
        targets = [str(value) for value in raw_targets]
    else:
        targets = [target_name(value) for value in raw_targets] if isinstance(raw_targets, list) else []
    targets = [value for value in targets if value]
    duplicates = sorted(name for name, count in Counter(targets).items() if count > 1)
    if duplicates:
        issues.append(issue("duplicate_shader_target", "error", path, "Post chain defines a target more than once.", names=duplicates))
    known = set(targets) | {"main", "minecraft:main"} | set(external_targets)
    profile = PROFILES.get(minecraft, {})
    schema = profile.get("post_schema")
    direct_stages = schema == "direct"
    if not schema:
        issues.append(issue("shader_schema_unverified", "warning", path, "No audited shader schema for this exact client; structure is inspected without claiming version compatibility."))
    if schema == "legacy" and "/post_effect/" in path:
        issues.append(issue("shader_graph_path_mismatch", "error", path,
                            f"{minecraft} reads legacy graphs under shaders/post, not post_effect."))
    elif schema in {"program", "direct"} and "/shaders/post/" in path:
        issues.append(issue("shader_graph_path_mismatch", "error", path,
                            f"{minecraft} reads effect graphs under post_effect; this legacy graph path is inactive."))
    if "targets" in document:
        if schema == "legacy" and not isinstance(raw_targets, list):
            issues.append(issue("shader_target_schema_mismatch", "error", path, "This client requires a targets array."))
        elif schema in {"direct", "program"} and not isinstance(raw_targets, dict):
            issues.append(issue("shader_target_schema_mismatch", "error", path, "This client requires a targets object."))
    if renderer != "vanilla":
        issues.append(issue("renderer_interface_unverified", "warning", path, f"Renderer '{renderer}' interfaces are not independently verified."))
    if path.endswith("/transparency.json") and graphics_mode != "fabulous":
        issues.append(issue("fabulous_route_unverified", "warning", path, "This transparency override needs its Fabulous route checked; select graphics mode and verify the client."))
    if external_targets:
        issues.append(issue("external_targets_supplied", "information", path, "External target availability is caller-supplied evidence, not proven by the pack.", targets=list(external_targets)))

    def known_target(value: str) -> bool:
        if value in known:
            return True
        if ":" in value:
            issues.append(issue("unknown_external_shader_target", "warning", path,
                                f"External target '{value}' is not declared or verified for this render route; namespace alone does not create a framebuffer."))
            return True  # Already diagnosed; avoid a second local-target error.
        return False
    passes = document.get("passes")
    if passes is not None and not isinstance(passes, list):
        issues.append(issue("invalid_shader_passes", "error", path, "'passes' must be an array."))
        return
    for index, shader_pass in enumerate(passes or []):
        if not isinstance(shader_pass, dict):
            issues.append(issue("invalid_shader_pass", "error", path, f"Pass {index} must be an object."))
            continue
        modern = "inputs" in shader_pass or "output" in shader_pass
        if schema == "legacy" and modern:
            issues.append(issue("shader_schema_mismatch", "error", path, f"Pass {index} uses post-1.21.1 fields on a legacy client."))
        if schema in {"direct", "program"} and not modern:
            issues.append(issue("shader_schema_mismatch", "error", path, f"Pass {index} uses legacy target fields on {minecraft}."))
        if modern:
            inputs = shader_pass.get("inputs", [])
            outgoing = shader_pass.get("output")
            if not isinstance(inputs, list):
                issues.append(issue("invalid_shader_inputs", "error", path, f"Pass {index} 'inputs' must be an array."))
                inputs = []
            input_targets: list[str] = []
            for input_index, item in enumerate(inputs):
                if isinstance(item, dict) and isinstance(item.get("location"), str):
                    namespace, _, resource = item["location"].partition(":")
                    wanted = f"assets/{namespace}/textures/{resource}.png" if resource else f"assets/minecraft/textures/{namespace}.png"
                    if pack.resolve(wanted)[0] is None:
                        issues.append(issue("shader_input_texture_unverified", "warning", path, f"Texture input '{item['location']}' is not bundled.", expected=wanted))
                    continue
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
            if direct_stages or "vertex_shader" in shader_pass or "fragment_shader" in shader_pass:
                if schema == "program":
                    issues.append(issue("shader_schema_mismatch", "error", path,
                                        f"{minecraft} requires a program reference; direct shader stages belong to a newer schema."))
                if direct_stages and "program" in shader_pass:
                    issues.append(issue("removed_shader_program_field", "error", path, "This client requires vertex_shader and fragment_shader, not program JSON."))
                lint_core_shader(pack, path, shader_pass, issues, minecraft)
                vertex = shader_pass.get("vertex_shader", "")
                if profile.get("post_vertex_id") and isinstance(vertex, str):
                    for candidate in shader_source_candidates(path, vertex, "vsh"):
                        actual, _ = pack.resolve(candidate)
                        vertex_source = re.sub(r"/\*.*?\*/|//[^\n]*", "", pack.text(actual), flags=re.S) if actual else ""
                        if actual and re.search(r"\bin\s+\w+\s+Position\s*;", vertex_source):
                            issues.append(issue("post_vertex_interface_mismatch", "error", actual,
                                f"{minecraft} post passes use a vertex-ID fullscreen triangle; this stage expects a Position vertex buffer. Use the target screenquad interface."))
                            break
                uniforms = shader_pass.get("uniforms", {})
                if profile.get("uniform_blocks") and not isinstance(uniforms, dict):
                    issues.append(issue("shader_uniform_schema_mismatch", "error", path, "This client requires uniforms grouped by uniform-block name."))
                elif schema and not profile.get("uniform_blocks") and isinstance(uniforms, dict) and uniforms:
                    issues.append(issue("shader_uniform_schema_mismatch", "error", path, "This client uses a list of named uniforms, not uniform blocks."))
                continue
            program = shader_pass.get("program")
            if not isinstance(program, str) or not program:
                issues.append(issue("missing_shader_program", "error", path, f"Pass {index} lacks string 'program'."))
            else:
                wanted = shader_program_json_path(program)
                actual, wrong_case = pack.resolve(wanted)
                if actual is None:
                    if program.startswith("minecraft:") and profile and wanted in profile["shader_files"]:
                        pass
                    else:
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
                if profile and wanted in profile["shader_files"]:
                    pass
                else:
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


def format_pair(value: Any, upper: bool = False) -> tuple[int, int] | None:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value, 2147483647 if upper else 0
    if isinstance(value, list) and 1 <= len(value) <= 2 and all(type(x) is int and x >= 0 for x in value):
        return value[0], value[1] if len(value) == 2 else 2147483647 if upper else 0
    return None


def select_overlays(pack: Pack, target: float | None, issues: list[dict[str, Any]]) -> tuple[Pack, list[str]]:
    """Inspect only resources selected by the target, with later overlays winning.

    Overlay bytes stay in the input pack; this constructs a virtual merged view.
    Files inactive on the selected client must not generate wrong-version errors.
    """
    try:
        metadata = json.loads(pack.text("pack.mcmeta"))
    except (KeyError, ValueError):
        return pack, []  # The normal JSON reader diagnoses malformed metadata.
    overlays = metadata.get("overlays") if isinstance(metadata, dict) else None
    if overlays is None:
        return pack, []
    entries = overlays.get("entries") if isinstance(overlays, dict) else None
    if not isinstance(entries, list):
        issues.append(issue("invalid_pack_overlays", "error", "pack.mcmeta", "overlays.entries must be an array."))
        return pack, []
    if target is None:
        issues.append(issue("overlay_target_unresolved", "warning", "pack.mcmeta", "Select an exact Minecraft or resource format to resolve pack overlays."))
        return pack, []
    files = {path: value for path, value in pack.files.items() if not path.startswith(tuple(
        str(e.get("directory", "")) + "/" for e in entries if isinstance(e, dict) and e.get("directory")))}
    applied = []
    for entry in entries:
        if not isinstance(entry, dict):
            issues.append(issue("invalid_pack_overlay", "error", "pack.mcmeta", "Each overlay must be an object."))
            continue
        directory = entry.get("directory")
        if not isinstance(directory, str) or not re.fullmatch(r"[a-zA-Z0-9_-]+", directory):
            issues.append(issue("invalid_pack_overlay", "error", "pack.mcmeta", "Overlay directory must be a simple directory name."))
            continue
        if target < 16:
            continue  # These clients do not support overlays.
        if target >= 65:
            low, high = format_pair(entry.get("min_format")), format_pair(entry.get("max_format"), True)
        else:
            formats = entry.get("formats")
            if isinstance(formats, list) and len(formats) == 2:
                low, high = format_pair(formats[0]), format_pair(formats[1], True)
            elif isinstance(formats, dict):
                low, high = format_pair(formats.get("min_inclusive")), format_pair(formats.get("max_inclusive"), True)
            else:
                low, high = format_pair(formats), format_pair(formats, True)
        if low is None or high is None or low > high:
            issues.append(issue("invalid_overlay_format_range", "error", "pack.mcmeta", f"Overlay '{directory}' has an invalid format range for this client."))
            continue
        requested = (int(target), int(round((target - int(target)) * 10)))
        if low <= requested <= high:
            prefix = directory + "/"
            files.update({path[len(prefix):]: value for path, value in pack.files.items()
                          if path.startswith(prefix + "assets/")})
            applied.append(directory)
    return Pack(pack.label, files), applied


def check_pack_format(meta: Any, requested: float | None, issues: list[dict[str, Any]], minecraft: str | None = None) -> None:
    if requested is None or not isinstance(meta, dict) or not isinstance(meta.get("pack"), dict):
        return
    pack = meta["pack"]
    target = (int(requested), int(round((requested - int(requested)) * 10)))
    if requested >= 65:
        low, high = format_pair(pack.get("min_format")), format_pair(pack.get("max_format"), True)
        if low is None or high is None:
            issues.append(issue("pack_format_range_required", "error", "pack.mcmeta",
                "This target requires pack.min_format and pack.max_format as an integer or [major, minor]."))
        elif low > high:
            issues.append(issue("invalid_pack_format_range", "error", "pack.mcmeta", "min_format exceeds max_format."))
        elif not low <= target <= high:
            issues.append(issue("pack_format_out_of_range", "warning", "pack.mcmeta", f"Target resource format {requested} is outside the declared range."))
        return
    value = pack.get("pack_format")
    supported = pack.get("supported_formats")
    if isinstance(supported, list) and len(supported) == 2:
        low, high = supported
    elif isinstance(supported, dict):
        low, high = supported.get("min_inclusive"), supported.get("max_inclusive")
    else:
        low = high = supported
    if type(low) is int and type(high) is int and low <= requested <= high:
        return
    if isinstance(value, (int, float)) and value != requested:
        issues.append(issue("pack_format_mismatch", "warning", "pack.mcmeta", f"pack.mcmeta declares {value}, but target resource format is {requested}."))


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
    parser.add_argument("--graphics-mode", choices=("fast", "fancy", "fabulous"))
    parser.add_argument("--renderer", default="vanilla")
    parser.add_argument("--external-target", action="append", default=[], help="Caller-verified framebuffer supplied by this render route")
    parser.add_argument("--json", action="store_true", help="Emit machine JSON instead of the human table")
    parser.add_argument("--format", choices=("table", "json"), default="table")
    parser.add_argument("--probe-plan", action="store_true", help="Include runtime checklist (included by default)")
    args = parser.parse_args(argv)
    try:
        report = lint_pack(Pack.open(args.input), args.minecraft, args.pack_format, args.graphics_mode, args.renderer, tuple(args.external_target))
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        report = {"verdict": "ERROR", "static_verdict": "ERROR", "runtime_verdict": "RUNTIME_UNVERIFIED", "statuses": ["ERROR", "RUNTIME_UNVERIFIED"], "issues": [issue("input_error", "error", str(args.input), str(exc))], "proof_checklist": proof_checklist(args.minecraft, args.pack_format)}
    if args.json or args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(render_report_table(report))
    return 1 if report["static_verdict"] == "ERROR" else 0


if __name__ == "__main__":
    raise SystemExit(main())
