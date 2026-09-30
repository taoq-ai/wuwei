"""Request day close, or inspect its retro preconditions."""

from pathlib import Path

from wuwei import closing, state, steward, workspace


def register(subparsers):
    parser = subparsers.add_parser('close', help='Refuse day close until all obligations land')
    parser.add_argument('--check', choices=('retro',))
    parser.set_defaults(func=run)


def run(args):
    root = workspace.guard_scope({'cwd': str(Path.cwd())})
    if root is None:
        return 0
    if args.check:
        code, reason = getattr(closing, args.check)(root)
    else:
        if not (workspace.day_dir(root) / 'state.json').is_file():
            raise ValueError('day state missing; close cannot infer empty ownership')
        steward.run(root, trigger='close')
        state._write_state(lambda data: data.update(close_requested=True), root, reserved=False,
                           kind='day.close_requested')
        code, reason = closing.check(root)
    if reason:
        print(reason)
    return code
