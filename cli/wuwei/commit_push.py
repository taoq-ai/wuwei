"""Commit and push policy of pr act and dispatch."""

from pathlib import Path
import json
from fnmatch import fnmatchcase
import re
import shlex

from wuwei.registry import data
from wuwei.exits import DAMAGED


def _identity(value):
    if not isinstance(value, dict) or any(
            not isinstance(value.get(key), str) or not value[key].strip()
            or any(char in value[key] for char in '\n\r\0<>')
            for key in ('name', 'email')):
        raise ValueError(f'missing or malformed identity; {DAMAGED}')
    return value['name'], value['email']


def unset_identity(identity, index='<n>', found=None):
    """#605: the one rule doctor's identity row and this guard share. None when
    repos.<index>.identity is a valid identity, else (reason, fix); found is the identity git
    resolves (doctor reads the checkout, the guard the commit context it already has), shown
    in the fix when it is valid, else placeholders."""
    try:
        _identity(identity)
        return None
    except ValueError:
        pass
    try:
        name, email = map(json.dumps, _identity(found))
    except ValueError:
        name, email = '"<name>"', '"<email>"'
    return (f'repos.{index}.identity is empty or malformed',
            f'bin/wuwei config set repos.{index}.identity '
            + shlex.quote(f'{{name = {name}, email = {email}}}'))


def identity_check(expected, actual, head=None):
    """Preserve harness order: effective author, committer, then HEAD identities."""
    try:
        owner = _identity(expected)
        for kind in ('author', 'committer'):
            if _identity(actual[kind]) != owner:
                return 1, (f'GIT_{kind.upper()}_IDENT differs from configured identity; '
                           'create item worktrees with wuwei worktree add. Or run '
                           f'git config user.name {shlex.quote(owner[0])} and then '
                           f'git config user.email {shlex.quote(owner[1])} in this worktree')
        if head is not None:
            for kind in ('author', 'committer'):
                if _identity(head[kind]) != owner:
                    return 1, 'HEAD author/committer do not match configured identity; run git commit --amend --reset-author --no-edit in the item worktree, then push again'
        return 0, ''
    except (KeyError, TypeError, ValueError) as exc:
        return 2, f'could not check identity: {exc}'


REPO_ENV = {'GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE'}


def context(cwd, settings, env, root, push=None, identity=True):
    """Match cwd to a configured repository; identity=False reads no commit identity.

    With push=(remote, refspecs), also return push_context read alongside, or None.
    """
    from wuwei import registry, workspace

    if 'GIT_COMMON_DIR' in env:
        raise ValueError('GIT_COMMON_DIR overrides cannot be inspected safely; run unset GIT_COMMON_DIR, then run plain git from the item worktree')
    if not identity and (settings or env):
        raise ValueError('identity-free repository read takes no settings or env overrides; retry; if it repeats, run bin/wuwei doctor')
    if not identity and push is not None:
        raise ValueError('push checks need the commit identity; retry; if it repeats, run bin/wuwei doctor')
    config = workspace.load_config(root)
    vcs = registry.load('vcs', config)
    if push is None:
        return _context(cwd, settings, env, root, config, vcs, identity)
    if REPO_ENV & env.keys():
        return *_context(cwd, settings, env, root, config, vcs, identity), None
    # Without repository overrides, Git discovers the same repository from cwd.
    found, early = registry.together(lambda: _context(cwd, settings, env, root, config, vcs, identity),
                                     lambda: vcs.push_context(str(cwd), *push, root=root))
    return *found, early


def _context(cwd, settings, env, root, config, vcs, identity):
    actual = data(vcs.commit_context(str(cwd), settings, env, root=root) if identity
                  else vcs.repo_context(str(cwd), root=root))
    for key in ('path', 'common_dir'):
        if not isinstance(actual.get(key), str) or not Path(actual[key]).is_absolute():
            raise ValueError('missing repository context; run the command from inside a repository checkout or worktree; if it is one, run bin/wuwei doctor')
    for repo in config['repos']:
        path = (root / Path(repo['path']).expanduser()).resolve()
        # A checkout whose own .git directory is the common directory Git just measured
        # is that repository; reading it again would return the same directory.
        if (path / '.git').is_dir() and str((path / '.git').resolve()) == actual['common_dir']:
            return repo, actual, vcs
        configured = data(vcs.repo_context(str(path), root=root))
        if configured.get('common_dir') == actual['common_dir']:
            return repo, actual, vcs
    raise ValueError('repository is not configured in this workspace; work in a configured repository. Or the owner adds this one with bin/wuwei config add-repo')


def push_check(repo, actual, push, root, vcs):
    """Check identities and push shape for either anchor; fast_evidence reads the evidence."""
    from wuwei import workspace

    result = identity_check(repo['identity'], actual, push['head'])
    if result[0]:
        return result
    item = _item(actual['path'], root)
    branch = item.lower() if item else '<branch>'
    sha = push['head']['sha']
    if not isinstance(sha, str) or not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', sha):
        raise ValueError(f'invalid HEAD; {DAMAGED}')
    if type(push['force']) is not bool:
        raise ValueError(f'invalid force evidence; {DAMAGED}')
    if push['force']:
        return 1, f'force-push is refused; run it without --force: git push origin HEAD:refs/heads/{branch}'
    updates = push['updates']
    if not isinstance(updates, list) or not updates:
        raise ValueError(f'push destinations are unmeasured; run git push origin HEAD:refs/heads/{branch}')
    if not repo['default_branch'].strip():
        raise ValueError('missing default branch; the owner sets repos.<n>.default_branch with bin/wuwei config set')
    config = workspace.load_config(root)
    for update in updates:
        destination = update['destination']
        if isinstance(destination, str) and destination.startswith('refs/tags/'):
            continue  # #530, #816: a tag is a release; the deploy guard's tag push rule asks the owner
        if not isinstance(destination, str) or not destination.startswith('refs/heads/'):
            raise ValueError(f'only branch and tag pushes are supported; run git push origin HEAD:refs/heads/{branch}')
        if destination == 'refs/heads/' + repo['default_branch']:
            return 1, (f'push to the default branch {repo["default_branch"]} is refused; run git push '
                       f'origin HEAD:refs/heads/{branch} for the item branch instead')
        if any(fnmatchcase(destination.removeprefix('refs/heads/'), pattern)
               for pattern in config['environments']):
            return 1, f'push to an environment branch is refused; deploying is an owner action, so run git push origin HEAD:refs/heads/{branch} for the item branch'
        if update['source'] != sha:
            return 1, 'push must use the checked current HEAD; run git push <remote> HEAD:<branch> from the item worktree'
        commits = data(vcs.push_commits(actual['path'], push['remote'], destination,
                                       sha, update.get('remote_sha'), repo['default_branch'],
                                       root=root))['commits']
        if not isinstance(commits, list):
            raise ValueError('malformed pushed commit range; run git fetch origin in the worktree, then push again; if it repeats, run bin/wuwei doctor')
        for commit in commits:
            result = identity_check(repo['identity'], commit)
            if result[0]:
                return result[0], 'pushed commit identity: ' + result[1]
    return 0, ''


def _item(path, root):
    """The item of an item worktree (<root>/worktrees/<ITEM>), else None."""
    try:
        return Path(path).resolve().relative_to(Path(root).resolve() / 'worktrees').parts[0]
    except (ValueError, IndexError):
        return None
