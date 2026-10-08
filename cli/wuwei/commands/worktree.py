"""Create or adopt an anchored item worktree after the morning gate."""

import json
from pathlib import Path
import sys

from wuwei import brief, registry, state, workspace


def register(subparsers):
    parser = subparsers.add_parser('worktree', help='Create or adopt an anchored item worktree')
    actions = parser.add_subparsers(dest='worktree_action', required=True)
    add = actions.add_parser('add', help='Create worktrees/<item> on branch <item lowercased>')
    add.add_argument('item')
    add.add_argument('--repo', help='Configured repository name; required when several are configured')
    add.add_argument('--branch', help='Check out this existing branch instead and record the worktree as the item\'s')
    adopt = actions.add_parser('adopt', help='Register an existing clean worktree as the item\'s')
    adopt.add_argument('path')
    adopt.add_argument('--item', required=True)
    parser.set_defaults(func=run)


def run(args):
    root = workspace.find_workspace()
    config = workspace.load_config(root)
    item = brief.identifier(args.item)
    try:
        if args.worktree_action == 'adopt':
            result = workspace.adopt_worktree(root, item, args.path, registry.load('vcs', config))
        else:
            result = add(args, root, config, item)
    except state.StateError as exc:
        print(f'wuwei worktree: {exc}', file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0


def add(args, root, config, item):
    repos = config['repos']
    if args.repo is not None:
        repos = [repo for repo in repos if repo['name'] == args.repo]
        if not repos:
            raise ValueError(f'unknown repository: {args.repo}')
    elif len(repos) > 1:
        raise ValueError('several repositories configured; pass --repo <name>')
    if not repos:
        raise ValueError('no repository configured; the owner adds one with bin/wuwei config add-repo in a host terminal')
    repo = (root / Path(repos[0]['path']).expanduser()).resolve()
    tree = root / 'worktrees' / item
    result = workspace.create_worktree(repo, args.branch or item.lower(), tree, root,
                                       registry.load('vcs', config), identity=repos[0]['identity'],
                                       existing=args.branch is not None)
    # #520: a fresh worktree has no untracked venv; build one or say which interpreter checks use.
    bootstrap = config['checks']['bootstrap']
    if bootstrap:
        found = registry.load('checks', config).run(str(tree), bootstrap, root=root)
        if found.exit != 0:
            reason = f': {found.reason}' if found.reason else ''
            print(f'wuwei worktree warning: checks.bootstrap exited {found.exit}{reason}', file=sys.stderr)
    else:
        from wuwei import fast_checks
        for command in repos[0]['fast_checks']:
            found = fast_checks.interpreter(command, tree, repos[0], root, config)
            if found and found[1] == 'main worktree':
                print(f'wuwei worktree warning: {command.split()[0]} is not in this worktree; fast checks will run '
                      f'{found[0]} from the main worktree. Set [checks] bootstrap to build one per worktree',
                      file=sys.stderr)
    return result
