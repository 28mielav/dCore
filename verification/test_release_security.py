"""Filesystem boundaries for restored and shipped files."""
import io
import os
import stat
import zipfile

import pytest

from dcore.pack import release
from dcore.pack.keys import install_key
from dcore.release.bundle_skill import skill_files


@pytest.mark.parametrize('name', ['../outside.dsc', '/outside.dsc', 'C:/outside.dsc', '..\\outside.dsc'])
def test_restore_rejects_unsafe_paths_before_writing(tmp_path, monkeypatch, name):
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, 'w') as archive:
        archive.writestr('valid.dsc', b'valid')
        archive.writestr(name, b'unsafe')
    monkeypatch.setattr(release, 'decrypt_release', lambda *args: (
        zipfile.ZipFile(io.BytesIO(payload.getvalue())), {}, payload.getvalue()))
    output = tmp_path / 'restored'
    with pytest.raises(ValueError, match='unsafe restored path'):
        release.restore_release(tmp_path / 'release.zip', output, b'k' * 32)
    assert not (output / 'valid.dsc').exists()
    assert not (tmp_path / 'outside.dsc').exists()


def test_skill_omits_python_cache(tmp_path):
    skill = tmp_path / 'skill/dcore'
    cache = skill / 'scripts/__pycache__'
    cache.mkdir(parents=True)
    (skill / 'SKILL.md').write_text('instructions')
    (cache / 'dcore.cpython-312.pyc').write_bytes(b'cache')
    assert skill_files(tmp_path) == [skill / 'SKILL.md']


def test_key_install_preserves_existing_key_without_force(tmp_path):
    path = tmp_path / 'master.key'
    install_key(path)
    original = path.read_bytes()
    assert len(original) == 32
    with pytest.raises(SystemExit):
        install_key(path)
    assert path.read_bytes() == original


@pytest.mark.skipif(os.name != 'posix', reason='POSIX permissions; Windows uses directory ACLs')
def test_key_permissions_are_private_even_when_replacing(tmp_path):
    path = tmp_path / 'master.key'
    path.write_bytes(b'old')
    path.chmod(0o644)
    install_key(path, force=True)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
