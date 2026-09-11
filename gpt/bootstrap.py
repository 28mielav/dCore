"""Execute this file in Code Interpreter, then call dcore_main([...])."""
from pathlib import Path
import shutil
import sys
import zipfile


def initialize(base=Path('/mnt/data')):
    base = Path(base).resolve()
    runtime = base / 'dcore_runtime'
    runtime.mkdir(exist_ok=True)
    with zipfile.ZipFile(base / 'dcore_runtime.zip') as archive:
        for member in archive.infolist():
            destination = (runtime / member.filename).resolve()
            if not destination.is_relative_to(runtime):
                raise ValueError('Unsafe runtime archive path')
        archive.extractall(runtime)
    database = runtime / 'dcore/knowledge/data/dcore.sqlite'
    database.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(base / 'dcore.sqlite', database)
    sys.path.insert(0, str(runtime))
    from dcore.cli import main
    return main


if __name__ == '__main__':
    dcore_main = initialize()
