"""Durable state in git. .wuwei/ travels on its own branch, wuwei/state, never in a working branch,
so a cloud session's fresh clone starts where the last session stopped. Each clone pushes only its
own ledger file, so no session drops another's rows; other files follow the last writer, and a file
changed both here and on the branch keeps the local copy."""

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from wuwei import ws

BRANCH = 'wuwei/state'
REF = 'refs/remotes/origin/' + BRANCH
LOCAL = ('cache', 'traces.jsonl', 'executable', 'plan.html', 'canary')  # per machine, never synced


def remote():
    return os.environ.get('CLAUDE_CODE_REMOTE') == 'true'


def _git(cwd, *args, env=None, data=None):
    done = subprocess.run(['git', *args], cwd=cwd, input=data, capture_output=True, timeout=60,
                          env={**os.environ, **(env or {})})
    if done.returncode:
        raise RuntimeError(done.stderr.decode(errors='replace').strip() or f'git {args[0]} failed')
    return done.stdout


def _text(cwd, *args, **kwargs):
    return _git(cwd, *args, **kwargs).decode().strip()


def _top(path):
    try:
        return _text(path, 'rev-parse', '--show-toplevel')
    except (RuntimeError, OSError):
        return None


def _fetch(top):
    """The state branch's commit after a fetch, or None when it does not exist (or cannot be read)."""
    try:
        _git(top, 'fetch', '-q', 'origin', f'+refs/heads/{BRANCH}:{REF}')
        return _text(top, 'rev-parse', REF)
    except RuntimeError:
        return None


def files(root):
    """The durable files under .wuwei/, by their path inside it."""
    base = Path(root) / ws.DIR
    return {path.relative_to(base).as_posix(): path.read_bytes() for path in sorted(base.rglob('*'))
            if path.is_file() and path.relative_to(base).parts[0] not in LOCAL and not path.name.endswith('.tmp')}


def _digests(found):
    return {name: hashlib.sha256(data).hexdigest() for name, data in found.items()}


def _theirs(root, name):
    return name.startswith('ledger/') and name != f'ledger/{ws.clone(root)}.jsonl'


def pull(root):
    """Bring the state branch into .wuwei/."""
    if not (top := _top(root)):
        return 'not a git repository: the state stays local'
    if not (commit := _fetch(top)):
        return f'no {BRANCH} branch yet'
    synced = ws.cache_get(root, 'sync', float('inf')) or {}
    here, kept, branch = files(root), [], {}
    for name in _text(top, 'ls-tree', '-r', '--name-only', commit).splitlines():
        data = _git(top, 'cat-file', 'blob', f'{commit}:{name}')
        branch[name] = hashlib.sha256(data).hexdigest()
        local = here.get(name)
        if local == data or name == f'ledger/{ws.clone(root)}.jsonl':
            continue
        if _theirs(root, name) or local is None or _digests({name: local})[name] == synced.get(name):
            ws.atomic_write(Path(root) / ws.DIR / name, data.decode('utf-8'), Path(root) / ws.DIR)  # no link a seat planted is followed
        elif branch[name] != synced.get(name):  # only here: kept and pushed next, no note
            kept.append(name)
    ws.cache_put(root, 'sync', branch)  # what the branch holds, so push still sends what was kept or is new here (#1060)
    note = f'; kept local {", ".join(kept)} (changed here and on the branch; the next push wins)' if kept else ''
    return f'pulled {BRANCH} at {commit[:7]}{note}'


def push(root):
    """Commit .wuwei/ onto the state branch, beside the working branch, and push it."""
    if not (top := _top(root)):
        return 'not a git repository: the state stays local'
    here = files(root)
    if (ws.cache_get(root, 'sync', float('inf')) or {}) == _digests(here):
        return 'state already pushed'
    try:
        _text(top, 'config', 'user.email')
        ident = {}
    except RuntimeError:
        ident = {f'GIT_{who}_{what}': value for who in ('AUTHOR', 'COMMITTER')
                 for what, value in (('NAME', 'wuwei'), ('EMAIL', 'wuwei@localhost'))}
    for attempt in (1, 2):
        parent = _fetch(top)
        names = set(_text(top, 'ls-tree', '-r', '--name-only', parent).splitlines()) if parent else set()
        with tempfile.TemporaryDirectory() as temp:
            env = {'GIT_INDEX_FILE': str(Path(temp) / 'index'), **ident}
            _git(top, 'read-tree', *([parent] if parent else ['--empty']), env=env)
            for name, data in here.items():
                if _theirs(root, name) and name in names:
                    continue  # another clone's rows: that clone pushes them
                blob = _text(top, 'hash-object', '-w', '--stdin', data=data)
                _git(top, 'update-index', '--add', '--cacheinfo', f'100644,{blob},{name}', env=env)
            tree = _text(top, 'write-tree', env=env)
            if parent and tree == _text(top, 'rev-parse', parent + '^{tree}'):
                break
            commit = _text(top, 'commit-tree', tree, *(['-p', parent] if parent else []), '-m',
                           f'wuwei: state from clone {ws.clone(root)}', env=env)
        try:
            _git(top, 'push', '-q', 'origin', f'{commit}:refs/heads/{BRANCH}')
            break
        except RuntimeError:
            if attempt == 2:
                raise
    ws.cache_put(root, 'sync', _digests(here))
    return f'pushed .wuwei/ to {BRANCH}'


def restore(cwd):
    """At a cloud session's start: the workspace, rebuilt from the state branch when the clone has none."""
    root = ws.find(cwd)
    if root is not None:
        pull(root)
        return root
    if not (top := _top(cwd or os.getcwd())):
        return None
    base = Path(top) / ws.DIR
    base.mkdir()
    if pull(top).startswith('pulled'):
        return Path(top)
    shutil.rmtree(base)
    return None
