"""Portable entrypoint: resolves its runtime independently of the current directory."""
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
runtime = root / "runtime"
if not runtime.is_dir():
    # Source checkout only; released Skills always use their bundled runtime.
    runtime = root.parents[1]
sys.path.insert(0, str(runtime))
from dcore.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
