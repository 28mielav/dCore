from dcore.config import apply_target


def test_nearest_config_and_cli_override(tmp_path):
    (tmp_path / 'dcore.toml').write_text('[target]\nminecraft="1.21.8"\ngraphics_mode="fancy"\n')
    nested = tmp_path / 'nested'
    nested.mkdir()
    args = apply_target('lint-pack', ['pack', '--minecraft=1.21.4'], nested)
    assert args.count('--minecraft=1.21.4') == 1
    assert '--minecraft' not in args
    assert args[-2:] == ['--graphics-mode', 'fancy']
    assert '--graphics-mode' not in apply_target('lint', ['project'], nested)
