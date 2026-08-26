"""The single declaration of what a dCore release contains.

Before 0.70 this list lived four times over: in the workflow's `--artifact`
flags, in the manifest writer, and in both bundle builders. They drifted, and
the published instructions ended up naming eight Knowledge files while the
builder emitted nineteen. Everything now resolves from here.

Artifact names are repository-relative POSIX paths and are stable regardless of
whether the files are read from the working tree or from a CI candidate
directory, so `bundle_sha256` stays comparable across jobs.
"""

from __future__ import annotations

from pathlib import Path

PACKAGE_DIRECTORY = "dcore"

PACKAGE_DATA = (
    "dcore/semantics/core/NOTICE.md",
    "dcore/semantics/core/LICENSE.md",
)

KNOWLEDGE_DATA = (
    "knowledge/dcore.sqlite",
    "knowledge/DCORE_INSTRUCTIONS.txt",
    "knowledge/AGENT_INSTRUCTIONS.md",
    "knowledge/lint_contract.example.json",
    "knowledge/pool4_golden_corpus.json",
    "knowledge/visual_sources.json",
    "knowledge/validation_contract.json",
)

PROJECT_DATA = (
    "integrations/custom-gpt/openapi.yaml",
    "docs/ARCHITECTURE.md",
    "docs/OPERATIONS.md",
)

DATABASE = "knowledge/dcore.sqlite"
MANIFEST = "knowledge/manifest.json"

#: Artifacts Git stores with LF and a Windows checkout materialises with CRLF.
#: Measuring the working-tree bytes made the release identity depend on the
#: platform that ran the gate: the same commit measured 77 bytes larger on a
#: Windows checkout than on a Linux runner, which tripped the 12000-byte
#: instructions ceiling on one platform only and made a locally regenerated
#: manifest fail CI's staleness comparison.
#:
#: Measurement lives here because both halves of the release need the identical
#: answer: the verifier writes these hashes into the manifest and the bundlers
#: check artifacts against it. When the two disagreed, every bundle build failed.
TEXT_SUFFIXES = frozenset({".txt", ".md", ".json", ".yaml", ".yml", ".py"})


def artifact_bytes(path: Path) -> bytes:
    """Return the platform-independent content of one release artifact.

    The database stays raw: it is binary, and a sqlite page can legitimately
    contain the CRLF byte pair, so normalising it would corrupt the digest.
    """
    raw = path.read_bytes()
    if path.suffix.casefold() in TEXT_SUFFIXES:
        return raw.replace(b"\r\n", b"\n")
    return raw


def package_sources(root: Path) -> tuple[str, ...]:
    """Every shipped module, discovered rather than listed, so additions cannot drift."""
    package = root / PACKAGE_DIRECTORY
    modules = sorted(
        path.relative_to(root).as_posix()
        for path in package.rglob("*.py")
        if "__pycache__" not in path.parts
    )
    return tuple(modules) + PACKAGE_DATA


def release_names(root: Path) -> tuple[str, ...]:
    """Artifact names covered by the manifest, excluding the manifest itself."""
    return tuple(sorted({*package_sources(root), *KNOWLEDGE_DATA, *PROJECT_DATA}))


def resolve(name: str, root: Path, knowledge: Path | None = None) -> Path:
    """Map an artifact name onto disk, preferring a CI candidate knowledge directory."""
    if knowledge is not None and name.startswith("knowledge/"):
        candidate = knowledge / Path(name).name
        if candidate.is_file():
            return candidate
    return root / name


def release_sources(root: Path, knowledge: Path | None = None) -> dict[str, Path]:
    return {name: resolve(name, root, knowledge) for name in release_names(root)}
