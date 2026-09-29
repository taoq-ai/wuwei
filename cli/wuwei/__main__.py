"""Discover commands and enforce the three-state exit contract."""

import argparse
from contextlib import redirect_stdout, redirect_stderr
from importlib import import_module
import json
from pathlib import Path
import pkgutil
import sys

from wuwei import commands, env, redact, workspace
from wuwei.exits import CLEAN, FINDINGS, UNRUN


def main(argv=None):
    output, errors = redact.Output(sys.stdout), redact.Output(sys.stderr)
    with env.session(), redirect_stdout(output), redirect_stderr(errors):
        try:
            return _main(argv)
        finally:
            output.flush()
            errors.flush()


def _main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    parser = argparse.ArgumentParser(prog="wuwei")
    subparsers = parser.add_subparsers(dest="command", required=True)
    try:
        if argv and argv[0] not in ('hook', 'init'):
            try:
                root = workspace.find_workspace()
            except FileNotFoundError:
                root = None
            if root is not None:
                env.load(root)
        manifest = Path(__file__).resolve().parents[2] / ".claude-plugin/plugin.json"
        version = json.loads(manifest.read_text())["version"]
        if not isinstance(version, str) or not version.strip():
            raise ValueError("plugin version must be a non-empty string")
        parser.add_argument("--version", action="version", version=version)
        modules = {
            module.name.rsplit(".", 1)[-1]: module.name
            for module in pkgutil.iter_modules(commands.__path__, commands.__name__ + ".")
            if not module.name.rsplit(".", 1)[-1].startswith("_")
        }
        selected = modules.pop(argv[0].replace("-", "_"), None) if argv else None
        if selected:
            import_module(selected).register(subparsers)
        if not argv or (argv[0] != "--version" and argv[0] not in subparsers.choices):
            for module in modules.values():
                import_module(module).register(subparsers)
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
