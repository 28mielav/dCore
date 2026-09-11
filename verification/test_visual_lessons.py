import json
from pathlib import Path
import pytest
from dcore.lint.resourcepack import Pack, lint_pack

ROOT = Path(__file__).resolve().parents[1] / 'dcore/examples/visual'


@pytest.mark.parametrize('name', ['outline-mask', 'outline-scene-blur', 'menu-background-blur'])
def test_lessons_resolve_custom_stages_and_graphs(name):
    pack = Pack.open(ROOT / name)
    result = lint_pack(pack, '1.21.8', 64, 'fancy', external_targets=('minecraft:entity_outline',))
    assert not [x for x in result['issues'] if x['severity'] == 'error'], result['issues']
    assert result['runtime_verdict'] == 'RUNTIME_UNVERIFIED'
    assert json.loads(pack.text('pack.mcmeta'))['pack']['pack_format'] == 64
    assert not any(x['code'] == 'missing_shader_stage_file' for x in result['issues'])


def test_lessons_detect_broken_custom_dependency():
    pack = Pack.open(ROOT / 'outline-scene-blur')
    del pack.files['assets/lesson/shaders/post/blur.fsh']
    result = lint_pack(pack, '1.21.8', 64)
    assert any(x['code'] == 'missing_shader_stage_file' for x in result['issues'])
