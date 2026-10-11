"""Print and save the local owner report; then supervise merges and step the telemetry week."""

from contextlib import redirect_stdout
from pathlib import Path
import sys

from wuwei import report, state, workspace


def register(subparsers):
    subparsers.add_parser('report', help='Show the owner report').set_defaults(func=run)


def run(args):
    root = workspace.guard_scope({'cwd': str(Path.cwd())})
    if root is None:
        return 0
    if not state.day_started(workspace.day_dir(root)):
        print('No report today: no day has started. Start one with /wuwei:wuwei-plan.')
        return 0
    print(report.write().read_text(encoding='utf-8'), end='')
    # #847: the jobs the watch ran once a day; each failure is one stderr line, never the exit.
    from wuwei import merge, telemetry
    from wuwei.watch import ERRORS
    with redirect_stdout(sys.stderr):
        merge.poll(root)
    try:
        telemetry.step(root, workspace.load_config(root))
    except ERRORS as exc:
        print(f'wuwei report: telemetry unmeasured: {exc}; run bin/wuwei doctor', file=sys.stderr)
    return 0
