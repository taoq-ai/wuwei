"""Save a seat's spec-kit analyze report: a Claude Code subagent cannot write analysis.md (#614)."""

import sys
from pathlib import Path


def register(subparsers):
    parser = subparsers.add_parser('spec', help="Save a seat's spec-kit analysis report")
    actions = parser.add_subparsers(dest='spec_action', required=True)
    analysis = actions.add_parser('analysis', help="write the report on stdin as analysis.md in the item's spec directory")
    analysis.add_argument('item')
    analysis.add_argument('--file', help='read the report from PATH instead of stdin')
    analysis.set_defaults(func=run_analysis)


def run_analysis(args):
    try:
        print(write(args.item, Path(args.file).read_text(encoding='utf-8') if args.file else sys.stdin.read()))
        return 0
    except (OSError, ValueError, UnicodeError) as exc:
        print(f'wuwei spec analysis: {exc}', file=sys.stderr)
        return 2


def write(item, text, root=None):
    """Write text as analysis.md in the item's one spec-kit directory; the path relative to
    its worktree."""
    from wuwei import specmode, state, workspace
    root = workspace.find_workspace(root)
    items = state.read_state(root)['items']
    # The step line formats {item} lowercased, like every spec step.
    names = [item] if item in items else [name for name in items if name.lower() == item.lower()]
    if len(names) != 1:
        raise ValueError(f'unknown item {item}; use the item id from the brief (bin/wuwei status lists them)')
    name, = names
    worktree = items[name].get('worktree')
    if not isinstance(worktree, str) or not worktree:
        raise ValueError(f'no worktree recorded for {name}; the planner creates it with bin/wuwei worktree add {name}')
    tree = (root / worktree).resolve()
    location, reason = specmode._location(tree, 'speckit', name)
    if location is None:
        raise ValueError(f'no single spec directory: {reason}; run /speckit.specify first, or remove the extra directory')
    directory = tree / location
    if directory.is_symlink() or not directory.resolve().is_relative_to(tree):
        raise ValueError(f'{location} is a symlink or leaves the worktree; replace it with the directory itself')
    if not (directory / 'spec.md').is_file():
        raise ValueError(f'{location} has no spec.md yet; run /speckit.specify first')
    target = directory / 'analysis.md'
    if target.is_symlink():
        raise ValueError(f'{location}/analysis.md is a symlink; remove the link, then run this again')
    if not text.strip():
        raise ValueError('empty report; pass the /speckit.analyze report on stdin or with --file PATH')
    found = specmode.governing(tree, items[name], location)  # #664
    gap = found and specmode.governed(text, (directory / 'spec.md').read_text(encoding='utf-8'))
    if gap:
        reference, first, last, _ = found
        raise ValueError(f'{name} is governed by {reference} (lines {first}-{last}) and {gap}; add one row '
                         'per assumption: | <assumption> | agrees, conflicts or not covered | <path>:<line> |, '
                         'then run this again')
    workspace.atomic_write(target, text if text.endswith('\n') else text + '\n', mode=0o644)
    return target.relative_to(tree).as_posix()
