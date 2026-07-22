"""Compatibility entry point. Use dcore_lint.py for new integrations."""

from dcore_lint import main


if __name__ == "__main__":
    raise SystemExit(main())
