"""#478: list the owner's grants; revoke a standing one from the owner host terminal."""

import sys

from wuwei import state, workspace
from wuwei.exits import CLEAN, FINDINGS, UNRUN


def register(subparsers):
    parser = subparsers.add_parser('grants', help="list the owner's grants for owner-only actions; "
                                                  'revoke <n> removes a standing one (owner, host terminal)')
    parser.add_argument('action', nargs='?', choices=('revoke',))
    parser.add_argument('n', nargs='?', type=int, help='the standing grant number bin/wuwei grants prints')
    parser.set_defaults(func=run)


def run(args):
    try:
        root = workspace.find_workspace()
        config = workspace.load_config(root)
        data = state.read_state(root)
    except (OSError, ValueError) as exc:
        print(f'grants: {exc}; run bin/wuwei doctor', file=sys.stderr)
        return UNRUN
    lines = config['grants']['standing']
    if args.action == 'revoke':
        if args.n is None or not 1 <= args.n <= len(lines):
            print(f'grants: no standing grant {args.n}; bin/wuwei grants lists them', file=sys.stderr)
            return FINDINGS
        from wuwei.commands import setup
        line = lines[args.n - 1]
        code = setup._edit('grants revoke', 'standing grant', None, lambda _, raw: setup.write_value(
            raw, 'grants.standing', lines[:args.n - 1] + lines[args.n:]), root)
        if code == CLEAN:
            state.append_event('grant.revoked', {key: line[key] for key in ('decision', 'action', 'target')}, root)
        return code
    ignored = ' (ignored under strict)' if workspace.posture(config)[0] == 'strict' else ''
    rows = [f"{index}. {line['action']} {line['target']} always ({line['decision']}, {line['date']}){ignored}"
            for index, line in enumerate(lines, 1)]
    rows += [f"today: {row['action']} {row['target']} {row['answered']} ({key})"
             for key, row in data.get('grants', {}).items() if row['answered'] in ('today', 'once')]
    print('\n'.join(rows) or 'No grants.')
    return CLEAN
