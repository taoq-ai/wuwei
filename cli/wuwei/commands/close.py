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
    parser.add_argument('--why', action='store_true',
                        help='Print one line per approved item saying what holds the close; writes nothing')
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
    elif getattr(args, 'why', False):
        names, notes = [], []
        code, reason = closing.unresolved(root, pr_actions.evaluate(root)[1], open_items=names, notes=notes)
        if code == 2:
            print(reason, file=sys.stderr)
        for name in state.read_state(root)['approved_items']:
            print(next((note for note in notes if note.startswith(name + ':')), f'{name}: resolved')
                  if name not in names else
                  f'{name}: ' + next((line for line in reason.splitlines()
                                      if line.startswith(f'{name} is still open')), 'open'))
        return code
    else:
        if not (workspace.day_dir(root) / 'state.json').is_file():
            print('Nothing to close today: no day has started. Start one with /wuwei:wuwei-plan.')
            return 0
        state._write_state(lambda data: data.update(close_requested=True), root, reserved=False,
                           kind='day.close_requested')
        # ponytail: owned PRs are read again by closing.check; close runs a few times a day.
        names, notes = [], []
        code, reason = closing.unresolved(root, pr_actions.evaluate(root)[1], open_items=names, notes=notes)
        if not names and code < 2:
            steward.run(root, trigger='close')
            code, reason = closing.check(root)
            if code == 0:
                from wuwei import digest, tracker
                digest.write(root, workspace.now().date(), 'week')
                try:  # Comments are hygiene; strict_close is the close rule.
                    if tracker.log(root):
                        print('tracker log: some comments were not written; run bin/wuwei tracker log '
                              'to see why', file=sys.stderr)
                except (OSError, ValueError, TypeError, KeyError) as exc:
                    print(f'tracker log: {exc}', file=sys.stderr)
        if notes:
            print('\n'.join(notes))
    if reason:
        print(reason)
    return code
