"""Discover commands and enforce the three-state exit contract."""

from contextlib import redirect_stdout, redirect_stderr
import sys

from wuwei import env, redact
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
    if len(argv) == 2 and argv[0] == 'hook':
        # Hook fast path: no parser, manifest or command listing on every tool call.
        try:
            from types import SimpleNamespace
            from wuwei.commands import hook
        except Exception as exc:
            print(f"wuwei: {str(exc) or type(exc).__name__}", file=sys.stderr)
            return UNRUN
        if argv[1] in hook.EVENTS:
            return _call(hook.run, SimpleNamespace(command='hook', event=argv[1]))
    import argparse
    from importlib import import_module
    import json
    from pathlib import Path
    from wuwei import commands, workspace
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
        name = argv[0].replace("-", "_") if argv else ""
        if (name.isidentifier() and not name.startswith("_")
                and (Path(commands.__file__).parent / f"{name}.py").is_file()):
            import_module(f"{commands.__name__}.{name}").register(subparsers)
        if not argv or (argv[0] != "--version" and argv[0] not in subparsers.choices):
            import pkgutil
            for module in pkgutil.iter_modules(commands.__path__, commands.__name__ + "."):
                short = module.name.rsplit(".", 1)[-1]
                if not short.startswith("_") and short != name:
                    import_module(module.name).register(subparsers)
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
    return _call(args.func, args)


def _call(func, args):
    try:
        status = func(args)
        if isinstance(status, bool) or not isinstance(status, int) or status not in (CLEAN, FINDINGS, UNRUN):
            raise ValueError(f"invalid exit status {status!r}; expected 0, 1, or 2")
        return status
    except BaseException as exc:
        print(f"wuwei {args.command}: {str(exc) or type(exc).__name__}", file=sys.stderr)
        return UNRUN


if __name__ == "__main__":
    sys.exit(main())
