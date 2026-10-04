"""List open owner attention with its source."""

import json
import sys

from wuwei import workspace
from wuwei.commands.status import attention

# source: (text, command); {reason} is the row reason, {id} its first word.
ACTIONS = {
    'decision.pending': ('{reason}', 'wuwei decision show {id}'),
    'decision.answered': ('{reason}', None),  # the reason names wuwei decide D-n <option>
    'item.escalated': ('{reason} is escalated and waits for you', 'wuwei why {reason}'),
    'mcp.checked': ('The last MCP registry check did not pass or could not run', 'wuwei mcp check'),
    'draft.created': ('An outward draft waits for owner approval', 'bin/wuwei drafts'),
    'watch: health': ('{reason}', 'wuwei doctor'),
    'listen: health': ('{reason}', 'wuwei doctor'),
    'watch: sweep:unmeasured': ('A sweep could not read a record (unmeasured)', 'wuwei doctor'),
}


def register(subparsers):
    parser = subparsers.add_parser('nudges', help='List open nudges and pages')
    parser.add_argument('--json', action='store_true', help='one JSON row per cause')
    parser.set_defaults(func=run)


def line(row, count):
    """One readable line: what is open, how often, and the command that clears it."""
    reason = row['reason']
    action = ACTIONS.get(row['source']) if reason else None
    if action:
        text, command = (part and part.format(reason=reason, id=reason.split()[0]) for part in action)
    else:
        text = reason
        command = None if 'wuwei ' in reason or '/wuwei:' in reason else 'wuwei next'
    return (f"{row['tier']}: {text}" + (f' ({count} times)' if count > 1 else '')
            + (f'. Run: {command}' if command else ''))


def run(args):
    try:
        try:
            rows = attention(workspace.day_dir())
        except FileNotFoundError:
            rows = []  # No day state yet means nothing is owed.
        if args.json:
            print(json.dumps(rows, allow_nan=False))
            return 0
        counts = {}
        for row in rows:
            key = (row['tier'], row['source'], row['reason'])
            counts[key] = counts.get(key, 0) + 1
        lines = [line(dict(zip(('tier', 'source', 'reason'), key)), count) for key, count in counts.items()]
        print('\n'.join(lines) or 'No open pages or nudges.')
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'wuwei nudges: {exc}', file=sys.stderr)
        return 2
