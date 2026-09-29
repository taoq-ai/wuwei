"""Repository-local git commands returning plain port data."""

from datetime import date
from functools import wraps
import os
from pathlib import Path
import re
import subprocess
import sys

from wuwei.registry import Result


TIMEOUT = 30
_LOG_FORMAT = '--format=%H%x00%an%x00%ae%x00%cn%x00%ce%x00%cI%x00%s'
_HEAD_FORMAT = '--format=%H%x00%an%x00%ae%x00%cn%x00%ce'
_REPOSITORY_ENV = {
    'GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE', 'GIT_COMMON_DIR',
    'GIT_OBJECT_DIRECTORY', 'GIT_ALTERNATE_OBJECT_DIRECTORIES', 'GIT_NAMESPACE',
    'GIT_CEILING_DIRECTORIES', 'GIT_DISCOVERY_ACROSS_FILESYSTEM',
}


class UnknownCommit(ValueError):
    pass


def _operation(function):
    @wraps(function)
    def call(*args, **kwargs):
        try:
            return Result(0, function(*args, **kwargs))
        except UnknownCommit:
            return Result(1, None, 'git.resolve: unknown commit')
        except (OSError, subprocess.SubprocessError, ValueError, TypeError, IndexError, RecursionError) as exc:
            detail = str(exc) if type(exc) is ValueError else type(exc).__name__
            reason = f'git.{function.__name__}: could not run: {detail}'
            print(reason, file=sys.stderr)
            return Result(2, None, reason)
    return call


def _run(repo, *args, settings=None, env=None, missing=False, local=False):
    allowed = False
    match args:
        case ('init', '--quiet'):
            allowed = local
        case ('add', '-A', '--', *paths):
            allowed = local and bool(paths) and all(_workspace_path(p) for p in paths)
        case ('commit', '--only', '-m', 'WUWEI promotion\n\nPromoted-by: wuwei', '--', *paths):
            allowed = local and bool(paths) and all(_workspace_path(p) for p in paths)
        case ('commit', '--allow-empty', '-m', 'WUWEI promotion\n\nPromoted-by: wuwei'):
            allowed = local
        case ('log', '-z', '--format=%x1e%(trailers:key=Promoted-by,valueonly)%x00', '--name-only', '--no-renames', 'HEAD', '--', 'charters', 'memory', 'goals', 'voice'):
            allowed = local
        case ('rev-parse', '--absolute-git-dir') | ('rev-parse', '--path-format=absolute', '--git-common-dir') | ('rev-parse', '--path-format=absolute', '--git-path', 'hooks'):
            allowed = True
        case ('show', '-s', format_arg, 'HEAD'):
            allowed = format_arg == _HEAD_FORMAT
        case ('symbolic-ref', '--quiet', '--short', 'HEAD'):
            allowed = True
        case ('check-ref-format', ref):
            allowed = isinstance(ref, str) and ref.startswith('refs/heads/')
        case ('config', '--type=bool', '--get', key):
            allowed = key == 'push.followtags' or bool(re.fullmatch(r'remote\.[A-Za-z0-9_.-]+\.mirror', key))
        case ('config', '--get-all', key):
            allowed = bool(re.fullmatch(r'remote\.[A-Za-z0-9_.-]+\.push', key))
        case ('config', '--get', 'core.hooksPath'):
            allowed = True
        case ('config', '--local', 'extensions.worktreeConfig', 'true'):
            allowed = True
        case ('config', '--worktree', 'core.hooksPath', path):
            allowed = isinstance(path, str) and Path(path).is_absolute()
        case ('config', '--local', '--get', 'core.bare' | 'core.worktree'):
            allowed = True
        case ('config', '--get', 'user.name' | 'user.email'):
            allowed = True
        case ('var', 'GIT_AUTHOR_IDENT' | 'GIT_COMMITTER_IDENT'):
            allowed = True
        case ('rev-parse', '--verify', 'HEAD^{commit}'):
            allowed = True
        case ('rev-parse', '--verify', '--quiet', rev):
            allowed = isinstance(rev, str) and (bool(re.fullmatch(r'[0-9a-fA-F]{7,64}\^\{commit\}', rev))
                    or rev.startswith('refs/remotes/') and rev.endswith('^{commit}'))
        case ('merge-base', 'HEAD', rev):
            allowed = bool(_revision(rev))
        case ('status', '--porcelain=v1', '-z', '--untracked-files=all'):
            allowed = True
        case ('branch', '--list', '--format=%(refname:short)', '--', pattern):
            allowed = bool(_revision(pattern))
        case ('diff', '--numstat', '-z', '--no-renames', base, head, '--'):
            allowed = bool(_revision(base) and _revision(head))
        case ('log', '-z', format_arg, rev, '--'):
            allowed = (format_arg == _LOG_FORMAT and isinstance(rev, str) and
                       rev.endswith('..HEAD') and bool(_revision(rev[:-6])))
            if format_arg == _HEAD_FORMAT:
                allowed = bool(re.fullmatch(r'(?:[0-9a-f]{40}|[0-9a-f]{64})\.\.(?:[0-9a-f]{40}|[0-9a-f]{64})', rev))
        case ('log', '--format=', '--name-only', '-z', since, until, 'HEAD', '--'):
            allowed = bool(re.fullmatch(r'--since=\d{4}-\d{2}-\d{2}T00:00:00', since)
                           and re.fullmatch(r'--until=\d{4}-\d{2}-\d{2}T23:59:59', until))
        case ('ls-tree', '-r', '--name-only', '-z', ref, '--', *paths):
            allowed = bool(_tree_ref(ref) and paths and all(_tree_path(p) for p in paths))
        case ('log', '--format=%ae', since, branch, '--', *paths):
            allowed = (bool(re.fullmatch(r'--since=[1-9][0-9]{0,3}\.days', since))
                       and bool(_revision(branch)) and paths and all(_tree_path(p) for p in paths))
        case ('log', '--format=%ae', branch, '--', *paths):
            allowed = bool(_revision(branch) and paths and all(_tree_path(p) for p in paths))
        case ('show', object_name):
            ref, sep, path = object_name.partition(':')
            allowed = bool(sep and _tree_ref(ref) and _tree_path(path))
        case ('worktree', 'add', '-b', branch, '--', path):
            allowed = (bool(_revision(branch)) and isinstance(path, str) and
                       bool(path) and '\0' not in path)
    if not allowed:
        raise ValueError('unsupported git command')
    if not os.fspath(repo):
        raise ValueError('missing repository')
    if settings is None:
        argv = ['git', '-C', os.fspath(repo), *args]
        options = {'env': {k: v for k, v in os.environ.items()
                          if k not in _REPOSITORY_ENV and not k.startswith('GIT_CONFIG')}}
    else:
        # Context reads must observe the same identity/config as the pending command.
        argv = ['git']
        for key, value in settings.items():
            if key not in {f'{kind}.{field}' for kind in ('user', 'author', 'committer')
                           for field in ('name', 'email')} or not isinstance(value, str):
                raise ValueError('unsupported identity setting')
            argv.extend(['-c', key + '=' + value])
        argv.extend(args)
        options = {'cwd': os.fspath(repo), 'env': {**{k: v for k, v in os.environ.items()
                                      if k not in _REPOSITORY_ENV and not k.startswith('GIT_CONFIG')}, **env}}
    if local:
        argv[1:1] = ['-c', 'core.hooksPath=/dev/null', '-c', 'commit.gpgSign=false',
                     '-c', 'user.name=WUWEI', '-c', 'user.email=wuwei@localhost']
        options['env'].update(GIT_AUTHOR_NAME='WUWEI', GIT_AUTHOR_EMAIL='wuwei@localhost',
                              GIT_COMMITTER_NAME='WUWEI', GIT_COMMITTER_EMAIL='wuwei@localhost')
    options['env']['GIT_NO_REPLACE_OBJECTS'] = '1'
    result = subprocess.run(argv, capture_output=True, timeout=TIMEOUT, **options)
    if missing and result.returncode == 1:
        return ''
    if result.returncode == 1 and args[:3] == ('rev-parse', '--verify', '--quiet'):
        raise UnknownCommit()
    if result.returncode:
        raise ValueError(f'git exited {result.returncode}')
    return result.stdout.decode('utf-8', errors='surrogateescape')


def _revision(value):
    if not isinstance(value, str) or not value or value.startswith('-') or '\0' in value:
        raise ValueError('invalid revision')
    return value


def _sha(value):
    value = value.strip()
    if not re.fullmatch('[0-9a-fA-F]{40}|[0-9a-fA-F]{64}', value):
        raise ValueError('invalid commit ID')
    return value


def _identity(value):
    match = re.fullmatch(r'(.+) <([^<>\n]+)> [0-9]+ [+-][0-9]{4}\n?', value)
    if not match:
        raise ValueError('invalid identity')
    return {'name': match[1], 'email': match[2]}


@_operation
def identity(repo, root=None):
    name = _run(repo, 'config', '--get', 'user.name').strip()
    email = _run(repo, 'config', '--get', 'user.email').strip()
    if not name or not email or '\n' in name or '\n' in email:
        raise ValueError('missing configured identity')
    return {'name': name, 'email': email,
            'author': _identity(_run(repo, 'var', 'GIT_AUTHOR_IDENT')),
            'committer': _identity(_run(repo, 'var', 'GIT_COMMITTER_IDENT'))}


@_operation
def head(repo, root=None):
    output = _run(repo, 'show', '-s', _HEAD_FORMAT, 'HEAD').rstrip('\n').split('\0')
    if len(output) != 5 or not all(output):
        raise ValueError('invalid HEAD identity')
    sha, author, email, committer, committer_email = output
    return {'sha': _sha(sha), 'author': {'name': author, 'email': email},
            'committer': {'name': committer, 'email': committer_email}}


@_operation
def merge_base(repo, ref, root=None):
    return {'sha': _sha(_run(repo, 'merge-base', 'HEAD', _revision(ref)))}


def _records(value):
    if value and not value.endswith('\0'):
        raise ValueError('unterminated git record')
    return value.split('\0')[:-1]


@_operation
def status(repo, root=None):
    fields = iter(_records(_run(repo, 'status', '--porcelain=v1', '-z', '--untracked-files=all')))
    changes = []
    for field in fields:
        if (len(field) < 4 or field[2] != ' ' or
                any(char not in ' MTADRCU?!' for char in field[:2])):
            raise ValueError('invalid status record')
        original = None
        if 'R' in field[:2] or 'C' in field[:2]:
            original = next(fields, None)
            if not original:
                raise ValueError('missing rename source')
        changes.append({'path': field[3:], 'index': field[0], 'worktree': field[1],
                        'original_path': original})
    return changes


@_operation
def diff_stat(repo, base, head, root=None):
    output = _run(repo, 'diff', '--numstat', '-z', '--no-renames', _revision(base), _revision(head), '--')
    changes = []
    for field in _records(output):
        added, deleted, path = field.split('\t', 2)
        if not path or not (added == deleted == '-' or (added.isdigit() and deleted.isdigit())):
            raise ValueError('invalid diff statistic')
        changes.append({'path': path, 'additions': None if added == '-' else int(added),
                        'deletions': None if deleted == '-' else int(deleted)})
    return changes


@_operation
def log_since(repo, sha, root=None):
    output = _run(repo, 'log', '-z', _LOG_FORMAT,
                  _revision(sha) + '..HEAD', '--')
    fields = _records(output)
    if len(fields) % 7:
        raise ValueError('incomplete log record')
    return [{'sha': _sha(fields[i]), 'author': fields[i+1], 'email': fields[i+2],
             'committer': fields[i+3], 'committer_email': fields[i+4],
             'committed_at': fields[i+5], 'subject': fields[i+6]}
            for i in range(0, len(fields), 7)]


@_operation
def worktree_add(repo, branch, path, root=None):
    branch = _revision(branch)
    path = os.fspath(path)
    if not path:
        raise ValueError('missing worktree path')
    _run(repo, 'worktree', 'add', '-b', branch, '--', path)
    return {'branch': branch, 'path': path}


@_operation
def resolve(repo, sha, root=None):
    if not isinstance(sha, str) or not re.fullmatch('[0-9a-fA-F]{7,64}', sha):
        raise ValueError('invalid commit ID')
    resolved = _sha(_run(repo, 'rev-parse', '--verify', '--quiet', sha + '^{commit}'))
    if not resolved.lower().startswith(sha.lower()):
        raise UnknownCommit()
    return {'sha': resolved}


@_operation
def branches(repo, pattern, root=None):
    names = _run(repo, 'branch', '--list', '--format=%(refname:short)', '--',
                 _revision(pattern)).splitlines()
    if any(not name or any(c.isspace() or ord(c) < 32 for c in name) for name in names):
        raise ValueError('invalid branch name')
    return names


@_operation
def commit_context(repo, settings, env, root=None):
    def read(*args):
        return _run(repo, *args, settings=settings, env=env)
    path = read('rev-parse', '--absolute-git-dir').rstrip('\n')
    if not path or not Path(path).is_absolute():
        raise ValueError('invalid repository path')
    common = read('rev-parse', '--path-format=absolute', '--git-common-dir').rstrip('\n')
    if not common or not Path(common).is_absolute():
        raise ValueError('invalid common directory')
    return {'path': str(Path(path).resolve()), 'common_dir': str(Path(common).resolve()),
            'author': _identity(read('var', 'GIT_AUTHOR_IDENT')),
            'committer': _identity(read('var', 'GIT_COMMITTER_IDENT'))}


@_operation
def push_context(repo, remote, refspecs, root=None):
    if not remote or not refspecs:
        raise ValueError('use an explicit remote and branch refspec: git push origin <branch>')
    result = head(repo, root=root)
    if result.exit:
        raise ValueError(result.reason)
    head_data = result.data
    sha = head_data['sha']
    branch = _run(repo, 'symbolic-ref', '--quiet', '--short', 'HEAD').strip()
    if not branch:
        raise ValueError('missing current branch')
    if not isinstance(remote, str) or not re.fullmatch(r'[A-Za-z0-9_.-]+', remote) or remote.startswith('-'):
        raise ValueError('use a named push remote')

    def boolean(key):
        value = _run(repo, 'config', '--type=bool', '--get', key, missing=True).strip()
        if value not in ('', 'true', 'false'):
            raise ValueError('invalid boolean push setting')
        return value == 'true'

    if boolean('push.followtags'):
        raise ValueError('tag pushes require deployment policy')
    force = boolean(f'remote.{remote}.mirror')
    configured = _run(repo, 'config', '--get-all', f'remote.{remote}.push', missing=True)
    updates = []
    for ref in refspecs:
        if ref.startswith('+'):
            force, ref = True, ref[1:]
        source, sep, destination = ref.partition(':')
        if source not in ('HEAD', branch, 'refs/heads/' + branch):
            raise ValueError('only current HEAD branch pushes are supported')
        if not sep:
            if configured or source == 'HEAD':
                raise ValueError('use an explicit HEAD:refs/heads/branch refspec')
            destination = 'refs/heads/' + branch
        _run(repo, 'check-ref-format', destination)
        if not destination.startswith('refs/heads/') or destination == 'refs/heads/':
            raise ValueError('only branch pushes are supported')
        updates.append({'source': head_data['sha'], 'destination': destination})
    return {'head': head_data, 'updates': updates, 'force': force, 'remote': remote}


@_operation
def hooks_path(repo, path, root=None):
    path = os.fspath(path)
    git_dir = _run(repo, 'rev-parse', '--absolute-git-dir').strip()
    common_dir = _run(repo, 'rev-parse', '--path-format=absolute', '--git-common-dir').strip()
    if not Path(git_dir).is_absolute() or not Path(common_dir).is_absolute() or git_dir == common_dir:
        raise ValueError('hooks require a linked worktree')
    existing = _run(repo, 'config', '--get', 'core.hooksPath', missing=True).strip()
    if existing and existing != path:
        raise ValueError('custom core.hooksPath exists; refusing to replace hooks')
    if not existing:
        default = Path(_run(repo, 'rev-parse', '--path-format=absolute', '--git-path', 'hooks').strip())
        if not default.is_absolute():
            raise ValueError('invalid default hooks path')
        if default.exists() and any(not item.name.endswith('.sample') for item in default.iterdir()):
            raise ValueError('existing default hooks would be disabled')
    # These common settings change meaning when worktreeConfig is enabled.
    bare = _run(repo, 'config', '--local', '--get', 'core.bare', missing=True).strip()
    worktree = _run(repo, 'config', '--local', '--get', 'core.worktree', missing=True).strip()
    if bare not in ('', 'false') or worktree:
        raise ValueError('migrate core.bare/core.worktree before enabling worktreeConfig')
    _run(repo, 'config', '--local', 'extensions.worktreeConfig', 'true')
    _run(repo, 'config', '--worktree', 'core.hooksPath', path)
    return {'git_dir': git_dir}


@_operation
def push_commits(repo, remote, destination, local_sha, remote_sha, default_branch, root=None):
    """Read every outgoing commit, using actual hook SHAs when available."""
    local_sha = _sha(local_sha)
    if not isinstance(remote, str) or not re.fullmatch(r'[A-Za-z0-9_.-]+', remote) or remote.startswith('-'):
        raise ValueError('use a named push remote')
    if not destination.startswith('refs/heads/'):
        raise ValueError('only branch pushes are supported')
    if remote_sha is None:
        tracking = 'refs/remotes/' + remote + '/' + destination.removeprefix('refs/heads/')
        remote_sha = _run(repo, 'rev-parse', '--verify', '--quiet', tracking + '^{commit}', missing=True).strip()
    if not remote_sha or set(remote_sha) == {'0'}:
        remote_sha = _run(repo, 'merge-base', 'HEAD', 'refs/remotes/' + remote + '/' + default_branch).strip()
    base = _sha(remote_sha)
    fields = _records(_run(repo, 'log', '-z', _HEAD_FORMAT, base + '..' + local_sha, '--'))
    if len(fields) % 5:
        raise ValueError('incomplete pushed commit record')
    return {'commits': [{'sha': _sha(fields[i]),
                         'author': {'name': fields[i+1], 'email': fields[i+2]},
                         'committer': {'name': fields[i+3], 'email': fields[i+4]}}
                        for i in range(0, len(fields), 5)]}


def _tree_ref(ref):
    if ref != 'HEAD' and (not isinstance(ref, str) or not re.fullmatch(r'[0-9a-fA-F]{40}|[0-9a-fA-F]{64}', ref)):
        raise ValueError('tree ref must be HEAD or a full commit ID')
    return ref


def _tree_path(path):
    if (not isinstance(path, str) or not path or Path(path).is_absolute()
            or any(part in ('..', '.') for part in path.split('/'))
            or path.startswith(('-', ':')) or any(ord(c) < 32 for c in path)
            or any(c in path for c in '*?[]')):
        raise ValueError('expected literal repository-relative path')
    return path


@_operation
def changes_on(repo, day, root=None):
    if not isinstance(day, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', day):
        raise ValueError('expected ISO date')
    date.fromisoformat(day)
    output = _run(repo, 'log', '--format=', '--name-only', '-z',
                  '--since=' + day + 'T00:00:00', '--until=' + day + 'T23:59:59', 'HEAD', '--')
    return sorted({path.lstrip('\n') for path in _records(output) if path.lstrip('\n')})


@_operation
def authorship(repo, branch, paths, days, root=None):
    if type(days) is not int or not 0 <= days <= 9999 or not isinstance(paths, list) or not paths:
        raise ValueError('expected authorship window and source paths')
    paths = [_tree_path(path) for path in paths]
    args = ('--since=' + str(days) + '.days',) if days else ()
    output = _run(repo, 'log', '--format=%ae', *args, _revision(branch), '--', *paths)
    counts = {}
    for email in output.splitlines():
        if not email or '@' not in email or any(ord(c) < 32 for c in email):
            raise ValueError('invalid author email')
        counts[email.casefold()] = counts.get(email.casefold(), 0) + 1
    return [{'email': email, 'commits': count} for email, count in counts.items()]


@_operation
def branch(repo, root=None):
    name = _run(repo, 'symbolic-ref', '--quiet', '--short', 'HEAD').strip()
    if not name or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/-]*', name):
        raise ValueError('invalid current branch')
    return {'name': name}


@_operation
def read_tree(repo, ref, paths, root=None):
    if not isinstance(paths, list) or not paths:
        raise ValueError('expected nonempty paths')
    paths = [_tree_path(path) for path in paths]
    _tree_ref(ref)
    names = _records(_run(repo, 'ls-tree', '-r', '--name-only', '-z', ref, '--', *paths))
    return {_tree_path(name): _run(repo, 'show', ref + ':' + name) for name in names}


_WORKSPACE_DIRS = ('charters', 'memory', 'goals', 'voice')
_PROMOTION_MESSAGE = 'WUWEI promotion\n\nPromoted-by: wuwei'


def _workspace_repository(repo):
    metadata = Path(repo) / '.git'
    if metadata.is_symlink() or not metadata.is_dir():
        raise ValueError('workspace needs its own local git repository')


def _workspace_path(path):
    _tree_path(path)
    if path.split('/')[0] not in _WORKSPACE_DIRS:
        raise ValueError('not a workspace procedure path')
    return path


@_operation
def workspace_init(repo, root=None):
    if (Path(repo) / '.git').exists():
        raise ValueError('workspace history already exists')
    _run(repo, 'init', '--quiet', local=True)
    paths = sorted(p.relative_to(repo).as_posix() for name in _WORKSPACE_DIRS
                   for p in (Path(repo) / name).rglob('*') if p.is_file())
    if paths:
        result = workspace_commit(repo, paths, root=root)
        if result.exit:
            raise ValueError(result.reason)
    else:
        _run(repo, 'commit', '--allow-empty', '-m', _PROMOTION_MESSAGE, local=True)


@_operation
def workspace_commit(repo, paths, root=None):
    _workspace_repository(repo)
    if not isinstance(paths, list) or not paths:
        raise ValueError('expected nonempty workspace paths')
    paths = [_workspace_path(p) for p in paths]
    _run(repo, 'add', '-A', '--', *paths, local=True)
    # --only excludes unrelated staged edits from the producer's commit.
    _run(repo, 'commit', '--only', '-m', _PROMOTION_MESSAGE, '--', *paths, local=True)


@_operation
def workspace_changes(repo, root=None):
    _workspace_repository(repo)
    current = status(repo, root=root)
    if current.exit:
        raise ValueError(current.reason)
    changes = {p for row in current.data for p in (row['path'], row['original_path'])
               if p and p.split('/')[0] in _WORKSPACE_DIRS and not p.endswith('/state.lock')}
    # ponytail: inspect all procedure history; add a verified checkpoint if it grows costly.
    history = _run(repo, 'log', '-z',
                   '--format=%x1e%(trailers:key=Promoted-by,valueonly)%x00',
                   '--name-only', '--no-renames', 'HEAD', '--', *_WORKSPACE_DIRS, local=True)
    if not history.startswith('\x1e'):
        raise ValueError('workspace history missing or malformed')
    for entry in history.split('\x1e')[1:]:
        trailer, separator, names = entry.partition('\0')
        if not separator:
            raise ValueError('malformed workspace history')
        paths = [p.lstrip('\n') for p in names.split('\0') if p.lstrip('\n')]
        for path in paths:
            _workspace_path(path)
        if trailer.strip() != 'wuwei':
            changes.update(paths)
    return sorted(changes)
