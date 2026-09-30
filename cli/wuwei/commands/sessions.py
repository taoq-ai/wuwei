"""List the Claude Code sessions registered in today's workspace state."""

import json
import sys

from wuwei import sessions, state, workspace
from wuwei.exits import CLEAN, UNRUN


def register(subparsers):
    parser = subparsers.add_parser('sessions', help='List registered sessions, roles and claims')
    parser.set_defaults(func=run)


def run(args):
    try:
        root = workspace.find_workspace()
        rows = sessions.rows(state.read_state(root), workspace.now(), sessions.stale_seconds(root))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'wuwei sessions: {exc}', file=sys.stderr)
        return UNRUN
    print(json.dumps(rows))
    return CLEAN
