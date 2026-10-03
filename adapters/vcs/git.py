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
_RECENT_FORMAT = '--format=%s%x1f%(trailers:key=Signed-off-by,valueonly,separator=%x2c)'
_REPOSITORY_ENV = {
    'GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE', 'GIT_COMMON_DIR',
    'GIT_OBJECT_DIRECTORY', 'GIT_ALTERNATE_OBJECT_DIRECTORIES', 'GIT_NAMESPACE',
    'GIT_CEILING_DIRECTORIES', 'GIT_DISCOVERY_ACROSS_FILESYSTEM',
}


class UnknownCommit(ValueError):
    pass


class RebaseConflict(ValueError):
    pass


def _operation(function):
    @wraps(function)
    def call(*args, **kwargs):
        try:
            return Result(0, function(*args, **kwargs))
        except UnknownCommit:
            return Result(1, None, 'git.resolve: unknown commit')
        except RebaseConflict:
            return Result(1, None, 'git.rebase: conflicts require resolution in the item worktree')
        except (OSError, subprocess.SubprocessError, ValueError, TypeError, IndexError, RecursionError) as exc:
            detail = str(exc) if type(exc) is ValueError else type(exc).__name__
            reason = f'git.{function.__name__}: could not run: {detail}'
            print(reason, file=sys.stderr)
            return Result(2, None, reason)
    return call


def _run(repo, *args, settings=None, env=None, missing=False, local=False, input=None):
    allowed = False
    match args:
        case ('init', '--quiet'):
            allowed = local
        case ('add', '-A', '--', *paths):
            allowed = local and bool(paths) and all(_workspace_path(p) for p in paths)
        case ('commit', '--only', '-m', message, '--', *paths):
            allowed = (local and message in (_PROMOTION_MESSAGE, _OWNER_EDIT_MESSAGE)
                       and bool(paths) and all(_workspace_path(p) for p in paths))
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
        case ('config', '-z', '--get-regexp', pattern):
            remote = re.fullmatch(r'\^\(push\\\.followtags\|remote\\\.(.+)\\\.\(mirror\|push\)\)\$', pattern)
            allowed = bool(remote) and pattern == _push_settings(remote[1].replace('\\.', '.'))
        case ('config', '--get', 'core.hooksPath'):
            allowed = True
        case ('config', '--local', 'extensions.worktreeConfig', 'true'):
            allowed = True
        case ('config', '--worktree', 'core.hooksPath', path):
            allowed = isinstance(path, str) and Path(path).is_absolute()
        case ('config', '--worktree', 'user.name' | 'user.email', value):
            allowed = isinstance(value, str) and bool(value) and not value.startswith('-')
        case ('config', '--local', '--get', 'core.bare' | 'core.worktree'):
            allowed = True
        case ('config', '--get', 'user.name' | 'user.email' | 'remote.origin.url'):
            allowed = True
        case ('var', 'GIT_AUTHOR_IDENT' | 'GIT_COMMITTER_IDENT'):
            allowed = True
        case ('rev-parse', '--verify', 'HEAD^{commit}' | 'FETCH_HEAD^{commit}'):
            allowed = True
        case ('rev-parse', '--git-path', 'rebase-merge' | 'rebase-apply'):
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
        case ('for-each-ref', '--format=%(refname)', 'refs/remotes/'):
            allowed = True
        case ('diff', '--numstat', '-z', '--no-renames', base, head, '--'):
            allowed = bool(_revision(base) and _revision(head))
        case ('log', '-z', format_arg, rev, '--'):
            allowed = (format_arg == _LOG_FORMAT and isinstance(rev, str) and
                       rev.endswith('..HEAD') and bool(_revision(rev[:-6])))
            if format_arg == _HEAD_FORMAT:
                base, _, tip = rev.rpartition('..')
                allowed = bool(re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', tip) and (
                    re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', base) or '..' not in base
                    and re.fullmatch(r'refs/remotes/[^\s~^:?*\[\\]+', base)))
        case ('log', '--format=', '--name-only', '-z', since, until, 'HEAD', '--'):
            allowed = bool(re.fullmatch(r'--since=\d{4}-\d{2}-\d{2}T00:00:00', since)
                           and re.fullmatch(r'--until=\d{4}-\d{2}-\d{2}T23:59:59', until))
        case ('ls-tree', '-r', '--name-only', '-z', ref, '--', *paths):
            allowed = bool(_tree_ref(ref) and paths and all(p == '.' or _tree_path(p) for p in paths))
        case ('log', '--format=%ae', since, branch, '--', *paths):
            allowed = (bool(re.fullmatch(r'--since=[1-9][0-9]{0,3}\.days', since))
                       and bool(_revision(branch)) and paths and all(_tree_path(p) for p in paths))
        case ('log', '--format=%ae', branch, '--', *paths):
            allowed = bool(_revision(branch) and paths and all(_tree_path(p) for p in paths))
        case ('log', '-z', '--max-count=100', format_arg, 'HEAD', '--'):
            allowed = format_arg == _RECENT_FORMAT
        case ('cat-file', '--batch'):
            allowed = True
        case ('worktree', 'add', '-b', branch, '--', path):
            allowed = (bool(_revision(branch)) and isinstance(path, str) and
                       bool(path) and '\0' not in path)
        case ('rebase', '--', ref):
            allowed = bool(_revision(ref))
        case ('fetch', '--no-tags', remote, branch):
            allowed = (bool(re.fullmatch(r'[A-Za-z0-9_.-]+', remote)) and not remote.startswith('-')
                       and bool(re.fullmatch(r'[A-Za-z0-9_./-]+', branch))
                       and not branch.startswith('-') and '..' not in branch)
        case ('push', lease, remote, refspec):
            matched = re.fullmatch(r'HEAD:refs/heads/([A-Za-z0-9_./-]+)', refspec)
            allowed = (bool(matched) and '..' not in matched[1] and
                       lease.startswith('--force-with-lease=' + matched[1] + ':') and
                       bool(re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}',
                                         lease.split(':', 1)[-1])) and
                       bool(re.fullmatch(r'[A-Za-z0-9_.-]+', remote)) and
                       not remote.startswith('-'))
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
    result = subprocess.run(argv, input=input, capture_output=True, timeout=TIMEOUT, **options)
    if missing and result.returncode == 1:
        return ''
    if result.returncode == 1 and args[:3] == ('rev-parse', '--verify', '--quiet'):
        raise UnknownCommit()
    if result.returncode == 1 and args[:1] == ('rebase',):
        if any(Path(_run(repo, 'rev-parse', '--git-path', name).strip()).exists()
               for name in ('rebase-merge', 'rebase-apply')):
            raise RebaseConflict()
        raise ValueError(result.stderr.decode('utf-8', errors='replace').strip() or 'git rebase exited 1')
    if result.returncode:
        if b'not a git repository' in result.stderr:
            raise ValueError('not a git repository')
        raise ValueError(f'git exited {result.returncode}')
    return result.stdout.decode('utf-8', errors='surrogateescape')


def _together(*calls):
    """Run independent reads concurrently; results and the first error keep call order."""
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(len(calls)) as pool:
        futures = [pool.submit(call) for call in calls]
    return [future.result() for future in futures]


def _later(call):
    """Keep a speculative read's error until its result is used."""
    def run():
        try:
            return call()
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            return exc
    return run


def _used(value):
    if isinstance(value, Exception):
        raise value
    return value


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
def remote_url(repo, root=None):
    return {'url': _run(repo, 'config', '--get', 'remote.origin.url', missing=True).strip()}


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


@_operation
def rebase(repo, ref, root=None):
    _run(repo, 'rebase', '--', _revision(ref))
    return {'rebased': True}


@_operation
def fetch(repo, remote, branch, expected, root=None):
    expected = _sha(expected)
    _run(repo, 'fetch', '--no-tags', remote, branch)
    actual = _sha(_run(repo, 'rev-parse', '--verify', 'FETCH_HEAD^{commit}'))
    if actual != expected:
        raise ValueError('fetched base differs from current PR base')
    return {'sha': actual}


@_operation
def push(repo, remote, branch, expected, root=None):
    _run(repo, 'push', f'--force-with-lease={branch}:{expected}', remote,
         'HEAD:refs/heads/' + branch)
    return {'pushed': True}


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
def recent_commits(repo, root=None):
    commits = []
    for record in _records(_run(repo, 'log', '-z', '--max-count=100', _RECENT_FORMAT, 'HEAD', '--')):
        subject, trailer = record.split('\x1f')
        commits.append({'subject': subject, 'signed_off': bool(trailer.strip())})
    return commits


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
def pushed_branches(repo, root=None):
    """Branch names observed on any remote, without fetching at day close."""
    refs = _run(repo, 'for-each-ref', '--format=%(refname)', 'refs/remotes/').splitlines()
    names = set()
    for ref in refs:
        match = re.fullmatch(r'refs/remotes/[^/\s]+/([^\s]+)', ref)
        if not match or any(ord(c) < 32 for c in ref):
            raise ValueError('invalid remote branch evidence')
        if match[1] != 'HEAD':
            names.add(match[1])
    return sorted(names)


def _repository(read, pair=None):
    """Validated git and common directory; `pair` holds both reads when already made."""
    path, common = pair or (read('rev-parse', '--absolute-git-dir'),
                            read('rev-parse', '--path-format=absolute', '--git-common-dir'))
    path, common = path.rstrip('\n'), common.rstrip('\n')
    if not path or not Path(path).is_absolute():
        raise ValueError('invalid repository path')
    if not common or not Path(common).is_absolute():
        raise ValueError('invalid common directory')
    return {'path': str(Path(path).resolve()), 'common_dir': str(Path(common).resolve())}


@_operation
def repo_context(repo, root=None):
    """Git and common directory only; needs no commit identity."""
    return _repository(lambda *args: _run(repo, *args, settings={}, env={}))


@_operation
def commit_context(repo, settings, env, root=None):
    def read(*args):
        return _run(repo, *args, settings=settings, env=env)
    path, common, author, committer = _together(
        lambda: read('rev-parse', '--absolute-git-dir'),
        lambda: read('rev-parse', '--path-format=absolute', '--git-common-dir'),
        lambda: read('var', 'GIT_AUTHOR_IDENT'), lambda: read('var', 'GIT_COMMITTER_IDENT'))
    return {**_repository(read, (path, common)),
            'author': _identity(author), 'committer': _identity(committer)}


def _push_settings(remote):
    """One read for push.followtags and the named remote's mirror and push keys."""
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', remote):
        raise ValueError('use a named push remote')
    return r'^(push\.followtags|remote\.' + remote.replace('.', r'\.') + r'\.(mirror|push))$'


@_operation
def push_context(repo, remote, refspecs, root=None):
    def read(*args, missing=False):
        try:
            return _run(repo, *args, missing=missing)
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            detail = str(exc) if type(exc) is ValueError else type(exc).__name__
            action = ('use a valid refs/heads/<branch> destination'
                      if args[0] == 'check-ref-format' else
                      'check repository state, Git installation and configuration before retrying')
            raise ValueError(f'git {args[0]} failed ({detail}); {action}') from exc

    if not remote or not refspecs:
        raise ValueError('use an explicit remote and branch refspec: git push origin <branch>')

    def current():
        result = head(repo, root=root)
        if result.exit:
            raise ValueError(f'HEAD is unavailable ({result.reason}); check the repository and Git '
                             'installation; create a commit if the branch has no commits before pushing')
        return result.data

    named = isinstance(remote, str) and re.fullmatch(r'[A-Za-z0-9_.-]+', remote) and not remote.startswith('-')
    key = f'remote.{remote}.'
    settings = [lambda: read('config', '-z', '--get-regexp', _push_settings(remote), missing=True)]
    # Explicit destinations are validated alongside; each result is used only where it was before.
    targets = sorted({ref.removeprefix('+').partition(':')[2] for ref in refspecs
                      if isinstance(ref, str) and ':' in ref} - {''})
    head_data, branch, *values = _together(
        current, lambda: read('symbolic-ref', '--quiet', '--short', 'HEAD', missing=True),
        *(settings if named else ()),
        *(_later(lambda target=target: read('check-ref-format', target)) for target in targets))
    checked = dict(zip(targets, values[-len(targets):] if targets else []))
    branch = branch.strip()
    if not branch:
        raise ValueError('detached HEAD; check out a branch before pushing')
    if not named:
        raise ValueError('use a named push remote')

    def boolean(value):
        # Git's bool parsing: a key without a value is true; the last value wins.
        value = value.lower()
        if value in ('true', 'yes', 'on') or re.fullmatch(r'[+-]?\d+', value) and int(value):
            return True
        if value in ('false', 'no', 'off', '') or re.fullmatch(r'[+-]?\d+', value):
            return False
        raise ValueError('invalid boolean push setting')

    found = {}
    for entry in values[0].split('\0')[:-1]:
        name, sep, value = entry.partition('\n')
        found.setdefault(name, []).append(value if sep else 'true')
    if boolean(found.get('push.followtags', [''])[-1]):
        raise ValueError('tag pushes require deployment policy')
    force = boolean(found.get(key + 'mirror', [''])[-1])
    configured = found.get(key + 'push')
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
        _used(checked[destination]) if destination in checked else read('check-ref-format', destination)
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
def worktree_identity(repo, name, email, root=None):
    for value in (name, email):
        if (not isinstance(value, str) or not value.strip() or value.startswith('-')
                or any(char in value for char in '\n\r\0<>')):
            raise ValueError('invalid identity')
    _run(repo, 'config', '--worktree', 'user.name', name)
    _run(repo, 'config', '--worktree', 'user.email', email)
    return {'name': name, 'email': email}


@_operation
def push_commits(repo, remote, destination, local_sha, remote_sha, default_branch, root=None):
    """Read every outgoing commit, using actual hook SHAs when available."""
    local_sha = _sha(local_sha)
    if not isinstance(remote, str) or not re.fullmatch(r'[A-Za-z0-9_.-]+', remote) or remote.startswith('-'):
        raise ValueError('use a named push remote')
    if not destination.startswith('refs/heads/'):
        raise ValueError('only branch pushes are supported')
    def log(base):
        return _run(repo, 'log', '-z', _HEAD_FORMAT, base + '..' + local_sha, '--')

    # A new branch sends what the default branch lacks (merge base..local when that base
    # is unique). The tracking-ref range is read alongside and used only if the ref exists.
    fallback = _later(lambda: log('refs/remotes/' + remote + '/' + default_branch))
    if remote_sha is None:
        tracking = 'refs/remotes/' + remote + '/' + destination.removeprefix('refs/heads/')
        remote_sha, known, other = _together(lambda: _run(
            repo, 'rev-parse', '--verify', '--quiet', tracking + '^{commit}', missing=True).strip(),
            _later(lambda: log(tracking)), fallback)
        output = _used(known if remote_sha else other)
    elif not remote_sha or set(remote_sha) == {'0'}:
        output = _used(fallback())
    else:
        output = log(_sha(remote_sha))
    fields = _records(output)
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
    paths = [path if path == '.' else _tree_path(path) for path in paths]
    _tree_ref(ref)
    names = [_tree_path(name) for name in
             _records(_run(repo, 'ls-tree', '-r', '--name-only', '-z', ref, '--', *paths))]
    if not names:
        return {}
    # _tree_path rejects control characters, so one name per stdin line is unambiguous.
    request = ''.join(f'{ref}:{name}\n' for name in names).encode('utf-8', 'surrogateescape')
    output = _run(repo, 'cat-file', '--batch', input=request).encode('utf-8', 'surrogateescape')
    tree = {}
    for name in names:
        header, _, output = output.partition(b'\n')
        _, kind, size = header.split(b' ')
        if kind != b'blob' or not size.isdigit() or output[int(size):int(size) + 1] != b'\n':
            raise ValueError(f'unreadable tree entry: {name}')
        tree[name] = output[:int(size)].decode('utf-8', 'surrogateescape')
        output = output[int(size) + 1:]
    if output:
        raise ValueError('unexpected git cat-file output')
    return tree


_WORKSPACE_DIRS = ('charters', 'memory', 'goals', 'voice')
_PROMOTION_MESSAGE = 'WUWEI promotion\n\nPromoted-by: wuwei'
_OWNER_EDIT_MESSAGE = _PROMOTION_MESSAGE + '\nEdited-by: owner'


def _workspace_repository(repo):
    metadata = Path(repo) / '.git'
    if metadata.is_symlink() or not metadata.is_dir():
        raise ValueError('workspace needs its own local git repository')


def _workspace_path(path):
    _tree_path(path)
    if path.split('/')[0] not in (*_WORKSPACE_DIRS, 'days', 'archive'):
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
    return _commit_workspace(repo, paths, _PROMOTION_MESSAGE)


@_operation
def workspace_owner_commit(repo, paths, root=None):
    if paths not in (['memory/goals.md'], ['memory/voice.md']):
        raise ValueError('owner edit must name goals or voice')
    return _commit_workspace(repo, paths, _OWNER_EDIT_MESSAGE)


def _commit_workspace(repo, paths, message):
    _workspace_repository(repo)
    if not isinstance(paths, list) or not paths:
        raise ValueError('expected nonempty workspace paths')
    paths = [_workspace_path(p) for p in paths]
    _run(repo, 'add', '-A', '--', *paths, local=True)
    # --only excludes unrelated staged edits from the producer's commit.
    _run(repo, 'commit', '--only', '-m', message, '--', *paths, local=True)


@_operation
def workspace_changes(repo, root=None):
    _workspace_repository(repo)

    def current():
        result = status(repo, root=root)
        if result.exit:
            raise ValueError(result.reason)
        return result.data

    # ponytail: inspect all procedure history; add a verified checkpoint if it grows costly.
    rows, history = _together(current, lambda: _run(
        repo, 'log', '-z', '--format=%x1e%(trailers:key=Promoted-by,valueonly)%x00',
        '--name-only', '--no-renames', 'HEAD', '--', *_WORKSPACE_DIRS, local=True))
    changes = {p for row in rows for p in (row['path'], row['original_path'])
               if p and p.split('/')[0] in _WORKSPACE_DIRS and not p.endswith('/state.lock')}
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
