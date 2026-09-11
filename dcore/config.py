"""Small reusable target config. Command-line flags always take precedence."""
from pathlib import Path
import tomllib

FLAGS = {
    'lint': {'minecraft', 'paper', 'java', 'denizen-version', 'denizenm', 'profile'},
    'run': {'minecraft', 'paper', 'java', 'denizen-version', 'denizenm', 'profile'},
    'retrieve': {'minecraft', 'paper', 'java', 'denizen-version', 'denizenm', 'profile'},
    'lint-pack': {'minecraft', 'pack-format', 'graphics-mode', 'renderer'},
    'validate-shader': {'minecraft', 'pack-format', 'graphics-mode', 'renderer'},
}


def apply_target(command: str, argv: list[str], cwd: Path | None = None) -> list[str]:
    if command not in FLAGS:
        return argv
    folder = (cwd or Path.cwd()).resolve()
    config = next((p / 'dcore.toml' for p in (folder, *folder.parents) if (p / 'dcore.toml').is_file()), None)
    if config is None:
        return argv
    with config.open('rb') as stream:
        target = tomllib.load(stream).get('target', {})
    if not isinstance(target, dict):
        raise ValueError('dcore.toml [target] must be a table')
    options = {arg.split('=', 1)[0] for arg in argv if arg.startswith('--')}
    result = list(argv)
    for key, value in target.items():
        flag = key.replace('_', '-')
        if flag in FLAGS[command] and '--' + flag not in options:
            if not isinstance(value, (str, int, float)) or isinstance(value, bool):
                raise ValueError(f'dcore.toml target.{key} must be a string or number')
            result.extend(['--' + flag, str(value)])
    return result
