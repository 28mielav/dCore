import pytest

from dcore.lint.script import lint_text
from dcore.semantics.ir import parse_denizen_ir


def event(body):
    return "scope:\n  type: world\n  events:\n    on player right clicks entity:\n" + body


def codes(text):
    return {item['code'] for item in lint_text(text)}


@pytest.mark.parametrize('prefix', [
    '    # has_flag[treasure]\n',
    '    - narrate <player.flag[anything]>\n',
    '    - narrate "determine cancelled has_flag[owned]"\n',
    '    - if <player.has_flag[owned]>:\n      - narrate yes\n',
    '    - if <context.entity.has_flag[owned]>:\n      - narrate yes\n',
])
def test_reads_comments_and_non_dominating_filters_do_not_prove_guard(prefix):
    result = codes(event(prefix + '    - determine cancelled\n'))
    assert 'broad_cancel_without_identity_guard' in result
    assert 'broad_event_guarded' not in result


@pytest.mark.parametrize('body', [
    '    - stop if:<context.entity.has_flag[owned].not>\n    - determine cancelled\n',
    '    - if !<context.entity.has_flag[owned]>:\n      - stop\n    - determine cancelled\n',
    '    - if <context.entity.has_flag[owned]>:\n      - determine cancelled\n',
])
def test_context_filter_on_every_cancellation_path(body):
    result = codes(event(body))
    assert 'broad_event_guarded' in result
    assert 'broad_cancel_without_identity_guard' not in result


def test_unrelated_sibling_and_dead_code_do_not_prove_guard():
    result = codes(event('    - if false:\n      - stop if:<context.entity.has_flag[owned].not>\n    - determine cancelled\n'))
    assert 'broad_cancel_without_identity_guard' in result


@pytest.mark.parametrize('body', [
    '    # wait 1t timeout\n    - narrate session\n',
    '    - if false:\n      - wait 1t\n      - while stop\n',
    '    - while next\n    - wait 1t\n',
])
def test_non_executed_wait_does_not_suppress_busy_loop(body):
    result = codes('worker:\n  type: task\n  script:\n  - while true:\n' + body)
    assert 'busy_while_true' in result
    assert 'unproven_loop_bound' in result


def test_immediate_exit_is_finite_without_wait():
    result = codes('worker:\n  type: task\n  script:\n  - while true:\n    - while stop\n')
    assert not {'busy_while_true', 'unproven_loop_bound'} & result


def test_ir_command_arguments_exclude_comments_but_preserve_quoted_hash():
    ir = parse_denizen_ir('worker:\n  type: task\n  script:\n  - narrate "# literal" # comment\n')
    assert ir.commands[0].arguments == '"# literal"'
