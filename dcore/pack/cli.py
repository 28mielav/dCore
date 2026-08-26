"""Command-line entry point for dcore.pack.

Same subcommands as the standalone dscpack tool: key install, obfuscate
(release archive), deobfuscate, verify, deploy (direct, incremental),
verify-direct, deobfuscate-direct.
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

from dcore.pack.direct import direct_deploy, restore_direct, verify_direct
from dcore.pack.keys import install_key, key_path, read_key
from dcore.pack.release import build_release, restore_release, verify_release


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dcore pack", description="Reversible obfuscation for Denizen .dsc projects")
    sub = parser.add_subparsers(dest="command", required=True)

    key = sub.add_parser("key")
    key_sub = key.add_subparsers(dest="key_command", required=True)
    install = key_sub.add_parser("install")
    install.add_argument("--path", type=Path)
    install.add_argument("--force", action="store_true")

    obfuscate = sub.add_parser("obfuscate")
    obfuscate.add_argument("inputs", nargs="+", type=Path)
    obfuscate.add_argument("--output", required=True, type=Path)
    obfuscate.add_argument("--key", type=Path)
    obfuscate.add_argument("--project-id", default="default")
    obfuscate.add_argument("--mode", choices=("hard", "balanced", "compat"), default="hard")

    restore = sub.add_parser("deobfuscate")
    restore.add_argument("release", type=Path)
    restore.add_argument("--output", required=True, type=Path)
    restore.add_argument("--key", type=Path)

    verify = sub.add_parser("verify")
    verify.add_argument("release", type=Path)
    verify.add_argument("--key", type=Path)

    direct = sub.add_parser("deploy")
    direct.add_argument("inputs", nargs="+", type=Path)
    direct.add_argument("--output", required=True, type=Path)
    direct.add_argument("--root", type=Path, default=Path.cwd())
    direct.add_argument("--key", type=Path)
    direct.add_argument("--project-id", default="default")
    direct.add_argument("--mode", choices=("hard", "balanced", "compat"), default="hard")

    direct_verify = sub.add_parser("verify-direct")
    direct_verify.add_argument("directory", type=Path)
    direct_verify.add_argument("--key", type=Path)

    direct_restore = sub.add_parser("deobfuscate-direct")
    direct_restore.add_argument("directory", type=Path)
    direct_restore.add_argument("--output", required=True, type=Path)
    direct_restore.add_argument("--key", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "key":
        install_key(args.path or key_path(), args.force)
        return 0
    master = read_key(args.key)
    if args.command == "obfuscate":
        build_release(args.inputs, args.output, master, args.project_id, args.mode)
    elif args.command == "deobfuscate":
        restore_release(args.release, args.output, master)
    elif args.command == "verify":
        verify_release(args.release, master)
    elif args.command == "deploy":
        direct_deploy(args.inputs, args.output, master, args.project_id, args.root, args.mode)
    elif args.command == "verify-direct":
        verify_direct(args.directory, master)
    else:
        restore_direct(args.directory, args.output, master)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2)
