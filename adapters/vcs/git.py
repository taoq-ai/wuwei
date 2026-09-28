"""Repository-local git commands returning plain port data."""

from functools import wraps
import os
import re
import subprocess
import sys

from wuwei.registry import Result


TIMEOUT = 30
_LOG_FORMAT = '--format=%H%x00%an%x00%ae%x00%cn%x00%ce%x00%cI%x00%s'
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


def _run(repo, *args):
    allowed = False
    match args:
        case ('config', '--get', 'user.name' | 'user.email'):
            allowed = True
        case ('var', 'GIT_AUTHOR_IDENT' | 'GIT_COMMITTER_IDENT'):
            allowed = True
        case ('rev-parse', '--verify', 'HEAD^{commit}'):
            allowed = True
        case ('rev-parse', '--verify', '--quiet', rev):
            allowed = bool(re.fullmatch(r'[0-9a-fA-F]{7,64}\^\{commit\}', rev))
        case ('merge-base', 'HEAD', rev):
            allowed = bool(_revision(rev))
        case ('status', '--porcelain=v1', '-z', '--untracked-files=all'):
            allowed = True
        case ('diff', '--numstat', '-z', '--no-renames', base, head, '--'):
            allowed = bool(_revision(base) and _revision(head))
        case ('log', '-z', format_arg, rev, '--'):
            allowed = (format_arg == _LOG_FORMAT and isinstance(rev, str) and
                       rev.endswith('..HEAD') and bool(_revision(rev[:-6])))
        case ('worktree', 'add', '-b', branch, '--', path):
            allowed = (bool(_revision(branch)) and isinstance(path, str) and
                       bool(path) and '\0' not in path)
    if not allowed:
        raise ValueError('unsupported git command')
    if not os.fspath(repo):
        raise ValueError('missing repository')
    result = subprocess.run(['git', '-C', os.fspath(repo), *args],
                            capture_output=True, timeout=TIMEOUT,
                            env={k: v for k, v in os.environ.items()
                                 if k not in _REPOSITORY_ENV and not k.startswith('GIT_CONFIG')})
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
    return {'sha': _sha(_run(repo, 'rev-parse', '--verify', 'HEAD^{commit}'))}


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
