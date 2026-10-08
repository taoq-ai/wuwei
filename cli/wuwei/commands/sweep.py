"""Run an absolute-state sweep."""

import sys

from wuwei import obligations, shepherd, watch


def classes(args):
    """#567: the builder's class sweep: the classes whose files the item's diff touches."""
    from wuwei import dispatch, state, workspace
    try:
        root = workspace.find_workspace()
        tree = (root / args.worktree).resolve()
        items = state.read_state(root)['items']
        item = next((name for name, row in sorted(items.items()) if row.get('worktree')
                     and (root / row['worktree']).resolve() == tree), None)
        if item is None:
            raise ValueError(f'no item has the worktree {args.worktree}; pass the --worktree of its builder brief')
        record, found = dispatch.classes(root, workspace.load_config(root), items[item])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'wuwei sweep classes: {exc}', file=sys.stderr)
        return 2
    if record['tier'] == 'light':
        print('Depth: light; no class sweep')
        return 0
    print(f"Depth: {record['tier']}")
    for name, paths in found.items():
        print(f"{name}: {', '.join(paths) or 'none changed'}")
    return 0


def register(subparsers):
    parser = subparsers.add_parser('sweep', help='Check day obligations')
    sweeps = parser.add_subparsers(dest='sweep', required=True)
    parser = sweeps.add_parser('obligations', help='Check open PR replies and visibility')
    parser.add_argument('--headless', action='store_true',
                        help="One CLI-only shepherd sweep of the owning day's PRs (#511)")
    parser.set_defaults(func=lambda args: shepherd.loop(once=True) if args.headless else obligations.sweep())
    parser = sweeps.add_parser('watch', help='Check watch health, obligations, activity and traces')
    parser.set_defaults(func=lambda args: watch.sweep())
    parser = sweeps.add_parser('classes', help="List the builder's sweep classes the item's diff touches")
    parser.add_argument('worktree')
    parser.set_defaults(func=classes)
