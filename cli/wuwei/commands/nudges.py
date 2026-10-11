"""List open owner attention with its source."""

from datetime import datetime
import json
import sys

from wuwei import workspace
from wuwei.commands.status import attention, surfaced

# source: (text, command); {reason} is the row reason, {id} its first word.
ACTIONS = {
    'decision.pending': ('{reason}', 'wuwei decision show {id}'),
    'decision.answered': ('{reason}', None),
    'decision.cruise': ('{reason}', 'wuwei decision show {id} --widget'),  # #283: Keep or Undo  # the reason names wuwei decide D-n <option>
    'cruise.burn': ('{reason}', 'wuwei cruise budget'),  # #558: the error budget table
    'item.escalated': ('{reason} is escalated and waits for you', 'wuwei why {reason}'),
    'mcp.checked': ('The last MCP registry check did not pass or could not run', 'wuwei mcp check'),
    'draft.created': ('An outward draft waits for owner approval', 'bin/wuwei drafts'),
    'watch: health': ('{reason}', 'wuwei doctor'),
    'listen: health': ('{reason}', 'wuwei doctor'),
    'watch: sweep:unmeasured': ('A sweep could not read a record (unmeasured)', 'wuwei doctor'),
    'nudges.dropped': ('{reason}', None),  # #786: expired and capped nudges, counted
}


def register(subparsers):
    parser = subparsers.add_parser('nudges', help='List open nudges and pages')
    parser.add_argument('--json', action='store_true', help='one JSON row per cause')
    parser.add_argument('--all', action='store_true', help='every open cause, whatever nudges.mode says')
    parser.set_defaults(func=run)


def line(row, count, now=None):
    """One readable line: what is open, how often, how long since the last event and the
    command that clears it."""
    reason = row['reason']
    action = ACTIONS.get(row['source']) if reason else None
    if action:
        text, command = (part and part.format(reason=reason, id=reason.split()[0]) for part in action)
    else:
        text = reason
        command = None if 'wuwei ' in reason or '/wuwei:' in reason else 'wuwei next'
    parts = [f'{count} times'] if count > 1 else []
    if now is not None and row.get('ts'):
        minutes = max(0, int((now - datetime.fromisoformat(row['ts']).astimezone()).total_seconds() // 60))
        parts.append(f'last {minutes} min ago' if minutes < 60 else f'last {minutes // 60} h ago')
    return (f"{row['tier']}: {text}" + (f" ({', '.join(parts)})" if parts else '')
            + (f'. Run: {command}' if command else ''))


def run(args):
    try:
        try:
            rows = attention(workspace.day_dir())
            if not getattr(args, 'all', False):  # #742: a bare namespace in tests has no all
                rows = surfaced(workspace.day_dir(), rows)[1]
        except FileNotFoundError:
            rows = []  # No day state yet means nothing is owed.
        if args.json:
            print(json.dumps(rows, allow_nan=False))
            return 0
        counts, newest = {}, {}
        for row in rows:
            key = (row['tier'], row['source'], row['reason'])
            counts[key] = counts.get(key, 0) + row.get('count', 1)
            if row.get('ts') and (key not in newest or datetime.fromisoformat(row['ts']).astimezone()
                                  > datetime.fromisoformat(newest[key]).astimezone()):
                newest[key] = row['ts']
        now = workspace.now()
        lines = [line(dict(zip(('tier', 'source', 'reason'), key), ts=newest.get(key)), count, now)
                 for key, count in counts.items()]
        print('\n'.join(lines) or 'No open pages or nudges.')
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'wuwei nudges: {exc}', file=sys.stderr)
        return 2
