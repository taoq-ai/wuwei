"""Record a small fix a seat found (#646)."""

import re
import sys

from wuwei.exits import CLEAN, FINDINGS, UNRUN
from wuwei.workspace import find_workspace, now


def register(subparsers):
    parser = subparsers.add_parser('note', help='record a small fix a seat found')
    parser.add_argument('--fix', metavar='TITLE',
                        help='Record a small fix a seat found; wuwei next proposes it as an item')
    parser.set_defaults(func=run_fix)


def run_fix(args):
    """#646: today's seat_findings.<id>; plan add <id> --from-finding admits it as a small item."""
    from wuwei import state
    from wuwei.tracker import ABSOLUTE
    if args.fix is None:
        print('wuwei note: pass --fix "<title>"', file=sys.stderr)
        return UNRUN
    title = ' '.join(args.fix.split())
    words = re.findall(r'[a-z0-9]+', title.lower())
    reason = ('the title must be one line; pass --fix "<title>"' if not title or '\n' in args.fix
              else 'the title must be at most 120 characters' if len(title) > 120
              else 'the title must hold letters or digits' if not words
              else 'the title must not hold an absolute path; name the file from the repository root'
              if ABSOLUTE.search(title) else '')
    if reason:
        print(f'wuwei note: {reason}', file=sys.stderr)
        return FINDINGS
    ident = 'fix-' + '-'.join(words[:6])

    def update(data):
        if ident in data.get('seat_findings', {}) or ident in data['items']:
            raise state.StateError(f'{ident} is already recorded; wuwei next proposes it')
        data.setdefault('seat_findings', {})[ident] = {
            'scope': title, 'evidence': 'seat finding', 'track': 'SLICE', 'at': now().isoformat()}
    try:
        state._write_state(update, find_workspace(), kind='finding.noted',
                           payload={'id': ident, 'title': title})
    except state.StateError as exc:
        print(f'wuwei note: {exc}', file=sys.stderr)
        return FINDINGS
    print(ident)
    return CLEAN
