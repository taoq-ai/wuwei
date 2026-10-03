"""Discover commands and enforce the three-state exit contract."""

import sys

# #346: Claude Code starts a hook process on every tool call and a status line on every
# refresh. Those processes live tens of milliseconds and free their objects by reference
# counting, so they run without the cyclic collector and skip the interpreter teardown.
# A leading --workspace <path> (#354) is consumed first, as _main does.
_ARGV = sys.argv[3:] if sys.argv[1:2] == ["--workspace"] and len(sys.argv) > 2 else sys.argv[1:]
_FAST = __name__ == "__main__" and (_ARGV[:1] == ["hook"] or _ARGV == ["status", "--line"])
if _FAST:
    import gc
    gc.disable()

from contextlib import redirect_stdout, redirect_stderr
import os

from wuwei import env, redact
from wuwei.exits import CLEAN, FINDINGS, UNRUN

# Top-level help groups, in the order printed; plumbing shows only with --all.
GROUPS = (
    ('Daily: the session runs these through the day',
     'next status nudges plan decision worktree brief build dispatch pr merge reply discover '
     'note metrics report retro close steward'),
    ('Owner: run these in your own host terminal',
     'setup init config decide calibrate goals voice drafts remote mcp outbound watch listen '
     'dashboard promote consolidate'),
    ('Recovery: when something is stuck',
     'doctor why state shadow heartbeat integrity runtime sessions'),
    ('Plumbing: hooks, seats and the plugin call these',
     'agents board event fast-checks git-hook hook index memory payload rank signal sweep verdict'),
)


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
    if argv[:1] == ['--workspace'] and len(argv) > 1:
        # ponytail: leading form only; it selects the workspace for this process (#354).
        os.environ['WUWEI_WORKSPACE'], argv = argv[1], argv[2:]
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
    try:
        if argv and argv[0] not in ('hook', 'init'):
            from wuwei import workspace
            try:
                root = workspace.find_workspace()
            except FileNotFoundError:
                root = None
            if root is not None:
                env.load(root)
        if argv == ['status', '--line']:
            # Status-line fast path: Claude Code runs it on every refresh, so it skips the
            # parser (argparse, gettext, shutil), the manifest and the command listing.
            from types import SimpleNamespace
            from wuwei.commands import status
    except Exception as exc:
        print(f"wuwei: {str(exc) or type(exc).__name__}", file=sys.stderr)
        return UNRUN
    if argv == ['status', '--line']:
        return _call(status.run, SimpleNamespace(command='status', line=True, json=False))
    import argparse
    from importlib import import_module
    import json
    from pathlib import Path
    from wuwei import commands
    parser = argparse.ArgumentParser(prog="wuwei")
    subparsers = parser.add_subparsers(dest="command", required=True, metavar="<command>")
    try:
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

    if argv and set(argv) <= {"-h", "--help", "--all"}:
        print(_help(parser, subparsers, "--all" in argv))
        return CLEAN
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


def _help(parser, subparsers, everything):
    """Top-level help grouped by who runs each command."""
    # argparse keeps the one-line command help only on _choices_actions (3.11 to 3.14).
    helps = {action.dest: action.help or "" for action in subparsers._choices_actions}
    grouped = {name for _, names in GROUPS for name in names.split()}
    groups = [group for group in GROUPS if everything or not group[0].startswith("Plumbing")]
    groups.append(("Other", " ".join(sorted(set(helps) - grouped))))
    lines = [parser.format_usage().rstrip()]
    for heading, names in groups:
        listed = [name for name in names.split() if name in helps]
        if listed:
            lines += ["", heading, *(f"  {name:<13} {helps[name]}" for name in listed)]
    lines += ["", "bin/wuwei <command> --help shows its options."]
    if not everything:
        lines.append("bin/wuwei --help --all also lists the plumbing commands.")
    return "\n".join(lines)


if __name__ == "__main__":
    status = main()
    if _FAST:
        import atexit
        import os
        atexit._run_exitfuncs()
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        except BaseException:
            sys.exit(status)  # A closed stream keeps the interpreter's own exit handling.
        os._exit(status)
    sys.exit(status)
