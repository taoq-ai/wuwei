"""Discover commands and enforce the three-state exit contract."""

import argparse
from importlib import import_module
import json
from pathlib import Path
import pkgutil
import sys

from wuwei import commands
from wuwei.exits import CLEAN, FINDINGS, UNRUN


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    parser = argparse.ArgumentParser(prog="wuwei")
    subparsers = parser.add_subparsers(dest="command", required=True)
    try:
        manifest = Path(__file__).resolve().parents[2] / ".claude-plugin/plugin.json"
        version = json.loads(manifest.read_text())["version"]
        if not isinstance(version, str) or not version.strip():
            raise ValueError("plugin version must be a non-empty string")
        parser.add_argument("--version", action="version", version=version)
        for module in pkgutil.iter_modules(commands.__path__, commands.__name__ + "."):
            if module.name.rsplit(".", 1)[-1].startswith("_"):
                continue
            name = module.name.rsplit(".", 1)[-1]
            if argv and argv[0] in (name, '--help', '-h'):
                import_module(module.name).register(subparsers)
            else:
                subparsers.add_parser(name)
    except Exception as exc:
        print(f"wuwei: {str(exc) or type(exc).__name__}", file=sys.stderr)
        return UNRUN

    try:
        args = parser.parse_args(argv)
    except SystemExit:
        raise
    except BaseException as exc:
        print(f"wuwei: {str(exc) or type(exc).__name__}", file=sys.stderr)
        return UNRUN
    try:
        status = args.func(args)
        if isinstance(status, bool) or not isinstance(status, int) or status not in (CLEAN, FINDINGS, UNRUN):
            raise ValueError(f"invalid exit status {status!r}; expected 0, 1, or 2")
        return status
    except BaseException as exc:
        print(f"wuwei {args.command}: {str(exc) or type(exc).__name__}", file=sys.stderr)
        return UNRUN


if __name__ == "__main__":
    sys.exit(main())
