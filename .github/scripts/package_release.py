"""Assemble the three verified distributions and their public checksums."""
import hashlib
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from dcore import __version__
from dcore.release.artifacts import artifact_bytes
from dcore.release.bundle import read_manifest, verify_artifacts
from dcore.release.artifacts import release_sources
from dcore.release.bundle_cli import build as build_cli
from dcore.release.bundle_gpt import build as build_gpt
from dcore.release.bundle_skill import build as build_skill


def archive_directory(directory, output):
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(directory.rglob('*')):
            if path.is_file():
                info = zipfile.ZipInfo(path.relative_to(directory.parent).as_posix(), (1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, artifact_bytes(path))


def main():
    verify_artifacts(read_manifest(ROOT / 'dcore/knowledge/data/manifest.json'), release_sources(ROOT))
    output = ROOT / 'build'
    build_cli(ROOT, output / 'dcore-cli')
    build_gpt(ROOT, output / 'dcore-gpt')
    skill = output / f'dcore-skill-{__version__}.zip'
    build_skill(ROOT, skill)
    assets = [skill]
    for name in ('dcore-cli', 'dcore-gpt'):
        archive = output / f'{name}-{__version__}.zip'
        archive_directory(output / name, archive)
        assets.append(archive)
    checksums = '\n'.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}' for p in sorted(assets)) + '\n'
    (output / 'SHA256SUMS.txt').write_text(checksums, encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
