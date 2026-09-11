import json
from dcore.lint.resourcepack import Pack, lint_pack


def report(document, **target):
    pack = Pack('test', {'assets/demo/post_effect/test.json': json.dumps(document).encode()})
    return {x['code'] for x in lint_pack(pack, **target)['issues']}


def test_namespace_is_not_framebuffer_evidence():
    doc = {'targets': {'swap': {}}, 'passes': [{'program': 'minecraft:post/blit',
           'inputs': [{'sampler_name': 'In', 'target': 'typo:missing'}], 'output': 'swap'}]}
    assert 'unknown_external_shader_target' in report(doc, minecraft='1.21.4')
    doc['passes'][0]['inputs'][0]['target'] = 'missing'
    assert 'unknown_shader_target' in report(doc, minecraft='1.21.4')
    doc['passes'][0]['inputs'][0]['target'] = 'swap'
    assert 'shader_pass_read_write_hazard' in report(doc, minecraft='1.21.4')


def test_1218_uses_stages_and_uniform_blocks():
    doc = {'targets': {'swap': {}}, 'passes': [{'vertex_shader': 'minecraft:post/blit',
           'fragment_shader': 'minecraft:post/blit', 'inputs': [{'sampler_name': 'In', 'target': 'minecraft:main'}],
           'output': 'swap', 'uniforms': {'BlitConfig': [{'type': 'vec4', 'value': [1, 1, 1, 1]}]}}]}
    result = report(doc, minecraft='1.21.8')
    assert 'missing_shader_program' not in result
    assert 'unknown_external_shader_target' not in result
    doc['passes'][0]['uniforms'] = []
    assert 'shader_uniform_schema_mismatch' in report(doc, minecraft='1.21.8')
    assert 'shader_schema_unverified' in report(doc, minecraft='unknown-build')


def test_external_framebuffer_is_explicit_caller_evidence():
    doc = {'targets': {}, 'passes': [{'program': 'minecraft:post/blit', 'inputs': [
        {'target': 'minecraft:entity_outline', 'sampler_name': 'In'}], 'output': 'minecraft:main'}]}
    result = report(doc, minecraft='1.21.4', external_targets=('minecraft:entity_outline',))
    assert 'external_targets_supplied' in result
    assert 'unknown_external_shader_target' not in result
