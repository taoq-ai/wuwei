"""Create an anchored item worktree after the morning gate."""

import json
from pathlib import Path
import sys

from wuwei import brief, registry, state, workspace


def register(subparsers):
    parser = subparsers.add_parser('worktree', help='Create an anchored item worktree')
    actions = parser.add_subparsers(dest='worktree_action', required=True)
    add = actions.add_parser('add', help='Create worktrees/<item> on branch <item lowercased>')
    add.add_argument('item')
    add.add_argument('--repo', help='Configured repository name; required when several are configured')
    parser.set_defaults(func=run)


def run(args):
    root = workspace.find_workspace()
    config = workspace.load_config(root)
    item = brief.identifier(args.item)
    repos = config['repos']
    if args.repo is not None:
        repos = [repo for repo in repos if repo['name'] == args.repo]
        if not repos:
            raise ValueError(f'unknown repository: {args.repo}')
    elif len(repos) > 1:
        raise ValueError('several repositories configured; pass --repo <name>')
    if not repos:
        raise ValueError('no repository configured')
    repo = (root / Path(repos[0]['path']).expanduser()).resolve()
    try:
        result = workspace.create_worktree(repo, item.lower(), root / 'worktrees' / item, root,
                                           registry.load('vcs', config), identity=repos[0]['identity'])
    except state.StateError as exc:
        print(f'wuwei worktree: {exc}', file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0
