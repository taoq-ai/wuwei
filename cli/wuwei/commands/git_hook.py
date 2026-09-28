"""Native Git hook translation and workspace-managed hook installation."""

import os
from pathlib import Path
import re
import sys

from wuwei import workspace
from wuwei.guards import commit_push as guard


def register(subparsers):
    parser = subparsers.add_parser('git-hook', help='Run a native Git identity/push guard')
    parser.add_argument('event', choices=('pre-commit', 'pre-push'))
    parser.add_argument('remote', nargs='?')
    parser.add_argument('url', nargs='?')
    parser.set_defaults(func=run)


def install(path, root, vcs):
    """Write policy-free shims, then enable them through the VCS port."""
    root = Path(root).resolve()
    if not (root / '.wuwei').is_dir():
        raise ValueError('hook installation requires a workspace')
    directory = root / '.wuwei/git-hooks'
    directory.mkdir(exist_ok=True)
    for event in ('pre-commit', 'pre-push'):
        source = ('''#!/bin/sh
git_dir=$(git rev-parse --absolute-git-dir) || exit 0
[ -f "$git_dir/wuwei-workspace" ] || exit 0
IFS= read -r WUWEI_WORKSPACE < "$git_dir/wuwei-workspace" || exit 2
export WUWEI_WORKSPACE
if [ ! -f "$WUWEI_WORKSPACE/.wuwei/executable" ]; then
    echo 'WUWEI executable pointer is missing; run wuwei init --upgrade' >&2
    exit 2
fi
IFS= read -r executable < "$WUWEI_WORKSPACE/.wuwei/executable" || executable=
if [ ! -x "$executable" ]; then
    echo 'WUWEI executable is missing; run wuwei init --upgrade' >&2
    exit 2
fi
exec "$executable" git-hook ''' + event + ' "$@"\n')
        target = directory / event
        if target.exists() and target.read_text() != source:
            raise ValueError('managed Git hook differs; refusing to overwrite it')
        workspace.atomic_write(target, source, mode=0o755)
    installed = guard.data(vcs.hooks_path(str(path), str(directory), root=root))
    git_dir = Path(installed['git_dir'])
    if not git_dir.is_absolute():
        raise ValueError('invalid worktree Git directory')
    workspace.atomic_write(git_dir / 'wuwei-workspace', str(root) + '\n')


def run(args):
    try:
        try:
            root = workspace.find_workspace()
        except FileNotFoundError:
            return 0
        env = {key: value for key, value in os.environ.items() if key.startswith('GIT_')}
        repo, actual, vcs = guard.context(Path.cwd(), {}, env, root)
        result = guard.identity_check(repo['identity'], actual)
        if not result[0] and args.event == 'pre-push':
            updates, ancestors = [], []
            for line in sys.stdin:
                fields = line.split()
                if len(fields) != 4 or any(not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', fields[i])
                                           for i in (1, 3)):
                    raise ValueError('malformed pre-push update')
                _, local_sha, destination, remote_sha = fields
                updates.append({'source': local_sha, 'destination': destination, 'remote_sha': remote_sha})
                if set(remote_sha) != {'0'}:
                    ancestors.append(remote_sha)
            if not updates:
                raise ValueError('pre-push update list is empty')
            push = {'head': guard.data(vcs.head(actual['path'], root=root)),
                    'remote': args.remote, 'updates': updates, 'force': False}
            result = guard.push_check(repo, actual, push, root, vcs)
            if not result[0]:
                for older in ancestors:
                    base = guard.data(vcs.merge_base(actual['path'], older, root=root))
                    if base.get('sha') != older:
                        result = 1, 'non-fast-forward push is refused'
                        break
    except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError) as exc:
        result = 2, f'Git hook could not run: {exc}'
    if result[1]:
        print(result[1], file=sys.stderr)
    return result[0]
