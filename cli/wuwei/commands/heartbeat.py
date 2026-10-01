"""Run the heartbeat probes once; read-only (the watch tick records and pings)."""

import sys

from wuwei import heartbeat, workspace
from wuwei.exits import UNRUN


def register(subparsers):
    parser = subparsers.add_parser('heartbeat', help='Probe that hooks refuse, allow and answer in budget')
    parser.set_defaults(func=run)


def run(args):
    try:
        probes = heartbeat.measure(workspace.find_workspace())
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'wuwei heartbeat: {exc}', file=sys.stderr)
        return UNRUN
    for name, row in probes.items():
        print(f'{name}: {row["result"]} {row["value"]}')
    return heartbeat.CODES[heartbeat.health(probes)]
