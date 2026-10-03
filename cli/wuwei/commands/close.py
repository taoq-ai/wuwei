"""Request day close, or inspect its retro preconditions."""

import json
from pathlib import Path
import sys

from wuwei import closing, decision, pr_actions, state, steward, workspace


def register(subparsers):
    parser = subparsers.add_parser('close', help='Refuse day close until all obligations land')
    parser.add_argument('--check', choices=('retro',))
    parser.add_argument('--widget', action='store_true',
                        help='Print each open item as an AskUserQuestion widget; writes nothing')
    parser.set_defaults(func=run)


def widget(root, name, item):
    return decision.widget(
        decision.gate(root) + f'{name} is still open ({item["status"]}/{item["phase"]}): '
        'carry it to tomorrow, park it, or keep working?', 'Open item',
        [('carry', f"Recommended. Carry {name} to tomorrow; tomorrow's plan brings it back."),
         ('park', f'Park {name}; it waits until someone resumes it.'),
         ('Skip', f'Keep working on {name}; run bin/wuwei close again when it is done.')],
        f'bin/wuwei plan <label> {name}')


def run(args):
    root = workspace.guard_scope({'cwd': str(Path.cwd())})
    if root is None:
        return 0
    if args.check:
        code, reason = getattr(closing, args.check)(root)
    elif getattr(args, 'widget', False):
        names = []
        code, reason = closing.unresolved(root, pr_actions.evaluate(root)[1], open_items=names)
        if code == 2:
            print(reason, file=sys.stderr)
            return 2
        items = state.read_state(root)['items']
        print(json.dumps([widget(root, name, items[name]) for name in names], indent=2))
        return int(bool(names))
    else:
        if not (workspace.day_dir(root) / 'state.json').is_file():
            print('Nothing to close today: no day has started. Start one with /wuwei:wuwei-plan.')
            return 0
        state._write_state(lambda data: data.update(close_requested=True), root, reserved=False,
                           kind='day.close_requested')
        # ponytail: owned PRs are read again by closing.check; close runs a few times a day.
        code, reason = closing.unresolved(root, pr_actions.evaluate(root)[1])
        if code == 0:
            steward.run(root, trigger='close')
            code, reason = closing.check(root)
    if reason:
        print(reason)
    return code
