"""GitHub mechanics and normalization, with no policy or override capability."""

from functools import wraps
import json
import os
import re
import subprocess
import sys
from urllib.parse import quote

from wuwei.registry import Result, outward_operation
from wuwei.references import pull_request, repository as _repo


TIMEOUT = 30
_THREADS = ('query($o:String!,$r:String!,$n:Int!){repository(owner:$o,name:$r){'
            'pullRequest(number:$n){reviewThreads(first:100){pageInfo{hasNextPage} '
            'nodes{id isResolved isOutdated comments(first:100){pageInfo{hasNextPage} '
            'nodes{databaseId author{login __typename} body createdAt}}}}}}}')

_REVERT = ('mutation($id:ID!){revertPullRequest(input:{pullRequestId:$id})'
           '{revertPullRequest{number url}}}')


def _operation(function):
    @wraps(function)
    def call(*args, **kwargs):
        try:
            return Result(0, function(*args, **kwargs))
        except (OSError, subprocess.SubprocessError, ValueError, TypeError,
                KeyError, AttributeError, IndexError, RecursionError) as exc:
            # Do not print response bodies or arguments, which may contain private text.
            detail = str(exc) if type(exc) is ValueError else type(exc).__name__
            reason = f'github.{function.__name__}: could not run: {detail}'
            print(reason, file=sys.stderr)
            return Result(2, None, reason)
    return call


def _errors(value):
    if isinstance(value, dict):
        if ('message' in value and 'documentation_url' in value) or value.get('errors'):
            raise ValueError('GitHub error response')
        for child in value.values():
            _errors(child)
    elif isinstance(value, list):
        for child in value:
            _errors(child)


def _run(args, payload=None, *, json_output=True, env=None):
    allowed = False
    match args:
        case ['auth', 'status', '--hostname', 'github.com']:
            allowed = payload is None and not json_output
        case ['pr', 'merge', url, '--squash', '--match-head-commit', sha]:
            repo, number = _ref(url)
            allowed = (url == f'https://github.com/{repo}/pull/{number}' and
                       bool(_sha(sha)) and payload is None)
        case ['api', '--include', 'user']:
            allowed = payload is None and not json_output
        case ['api', 'graphql', '--input', '-']:
            allowed = isinstance(payload, dict) and payload.get('query') in (_THREADS, _REVERT)
        case ['api', endpoint, *options]:
            if re.fullmatch(r'search/commits\?q=author-email%3A[A-Za-z0-9._%+-]+'
                            r'%20repo%3A[A-Za-z0-9._%-]+&per_page=1', endpoint):
                allowed = payload is None and options == ['-H', 'Cache-Control: no-cache']
            match = re.fullmatch(r'repos/([^/]+/[^/]+)/(.+)', endpoint)
            if match:
                _repo(match[1])
                if payload is None:
                    allowed = options in ([], ['-H', 'Cache-Control: no-cache'],
                                          ['-H', 'Cache-Control: no-cache', '--paginate', '--slurp'])
                else:
                    allowed = (options == ['--method', 'POST', '--input', '-'] and
                               re.fullmatch(r'pulls|pulls/[1-9][0-9]*/requested_reviewers|'
                                            r'issues/[1-9][0-9]*/comments|'
                                            r'pulls/[1-9][0-9]*/comments/[1-9][0-9]*/replies',
                                            match[2]) is not None)
    if not allowed:
        raise ValueError('unsupported gh command')
    if args[0] == 'api':
        args = [*args, '--hostname', 'github.com']
    result = subprocess.run(['gh', *args], input=json.dumps(payload) if payload is not None else None,
                            capture_output=True, text=True, timeout=TIMEOUT, env=env)
    if args[0] == 'auth':
        return result.returncode
    if result.returncode:
        if (args[:1] == ['api'] and len(args) > 1 and
                re.fullmatch(r'repos/[^/]+/[^/]+/branches/.+/protection', args[1]) and
                re.search(r'Branch not protected \(HTTP 404\)', result.stderr)):
            raise ValueError('branch protection absent')
        raise ValueError(f'gh exited {result.returncode}')
    if json_output:
        value = json.loads(result.stdout)
        _errors(value)
        return value
    # gh pr merge prints prose or nothing, but an error JSON body is still a failure.
    if result.stdout.lstrip().startswith(('{', '[')):
        _errors(json.loads(result.stdout))
    return result.stdout


def _api(endpoint, *, pages=False, payload=None):
    if payload is not None:
        return _run(['api', endpoint, '--method', 'POST', '--input', '-'], payload)
    return _run(['api', endpoint, '-H', 'Cache-Control: no-cache'] +
                (['--paginate', '--slurp'] if pages else []))


def _field(value, key, kind, *, nullable=False):
    item = value[key]
    if nullable and item is None:
        return None
    if type(item) is not kind:
        raise ValueError(f'invalid {key}')
    return item


def _list(value):
    if not isinstance(value, list):
        raise ValueError('expected list')
    return value


def _pages(endpoint, key=None):
    pages = _list(_api(endpoint + '?per_page=100', pages=True))
    if not pages:
        raise ValueError('missing page')
    return [item for page in pages for item in _list(page[key] if key else page)]


def _ref(ref):
    if isinstance(ref, str):
        ref = re.sub(r'^https://github\.com/([^/]+/[^/]+)/pull/', r'\1#', ref)
    repo, number = pull_request(ref).split('#')
    return repo, int(number)


def _sha(sha):
    if not isinstance(sha, str) or not re.fullmatch('[0-9a-fA-F]{40}|[0-9a-fA-F]{64}', sha):
        raise ValueError('expected full commit SHA')
    return sha


def _login(value):
    return _field(value, 'login', str) if value is not None else None


def _bot(actor, field='type'):
    kind = _field(actor, field, str)
    if kind not in ('User', 'Bot'):
        raise ValueError('unknown actor type')
    return kind == 'Bot'


@_operation
def pr(ref, root=None):
    repo, number = _ref(ref)
    value = _api(f'repos/{repo}/pulls/{number}')
    return {
        'repo': repo, 'number': _field(value, 'number', int),
        'url': _field(value, 'html_url', str), 'author': _login(value['user']),
        'state': _field(value, 'state', str), 'merged': _field(value, 'merged', bool), 'draft': _field(value, 'draft', bool),
        'head': _sha(value['head']['sha']), 'base': _field(value['base'], 'ref', str),
        'base_sha': _sha(value['base']['sha']), 'branch': _field(value['head'], 'ref', str),
        'merged_at': _field(value, 'merged_at', str, nullable=True),
        'created_at': _field(value, 'created_at', str),
        'merge_commit': (_sha(value['merge_commit_sha']) if value['merged'] else None),
        'mergeable': _field(value, 'mergeable', bool, nullable=True),
        'merge_state': _field(value, 'mergeable_state', str),
        'additions': _field(value, 'additions', int), 'deletions': _field(value, 'deletions', int),
        'changed_files': _field(value, 'changed_files', int),
        'updated_at': _field(value, 'updated_at', str), 'node_id': _field(value, 'node_id', str),
        'requested_reviewers': [_field(v, 'login', str) for v in _list(value['requested_reviewers'])],
        'requested_teams': [_field(v, 'slug', str) for v in _list(value['requested_teams'])],
    }


@_operation
def checks(ref, sha, root=None):
    repo, _ = _ref(ref)
    endpoint = f'repos/{repo}/commits/{_sha(sha)}'
    results = []
    for check in _pages(endpoint + '/check-runs', 'check_runs'):
        if _field(check, 'head_sha', str) != sha:
            raise ValueError('check belongs to a different head')
        results.append({'name': _field(check, 'name', str), 'state': _field(check, 'status', str),
                        'conclusion': _field(check, 'conclusion', str, nullable=True),
                        'sha': sha, 'app_id': _field(check['app'], 'id', int),
                        'url': _field(check, 'html_url', str)})
    # The statuses endpoint is newest first; retain only the latest per context.
    seen = set()
    for status in _pages(endpoint + '/statuses'):
        name = _field(status, 'context', str)
        state = _field(status, 'state', str)
        if name not in seen:
            seen.add(name)
            results.append({'name': name, 'state': 'pending' if state == 'pending' else 'completed',
                            'conclusion': None if state == 'pending' else state, 'sha': sha,
                            'app_id': None, 'url': _field(status, 'target_url', str, nullable=True)})
    return results


@_operation
def commits(ref, root=None):
    repo, number = _ref(ref)
    return [{'sha': _sha(value['sha']),
             'at': _field(value['commit']['committer'], 'date', str)}
            for value in _pages(f'repos/{repo}/pulls/{number}/commits')]


@_operation
def reviews(ref, root=None):
    repo, number = _ref(ref)
    return [{'id': _field(v, 'id', int), 'author': _login(v['user']),
             'is_bot': _bot(v['user']),
             'state': _field(v, 'state', str).lower(), 'body': _field(v, 'body', str),
             'sha': _field(v, 'commit_id', str, nullable=True),
             'submitted_at': _field(v, 'submitted_at', str, nullable=True)}
            for v in _pages(f'repos/{repo}/pulls/{number}/reviews')]


def _nodes(connection):
    # ponytail: fail closed beyond 100 nested records; add cursor traversal when needed.
    if _field(connection['pageInfo'], 'hasNextPage', bool):
        raise ValueError('incomplete thread evidence')
    return _list(connection['nodes'])


@_operation
def threads(ref, root=None):
    repo, number = _ref(ref)
    comments = [{'id': _field(v, 'id', int), 'author': _login(v['user']),
                 'is_bot': _bot(v['user']),
                 'body': _field(v, 'body', str), 'created_at': _field(v, 'created_at', str),
                 'updated_at': _field(v, 'updated_at', str)}
                for v in _pages(f'repos/{repo}/issues/{number}/comments')]
    owner, name = repo.split('/')
    value = _run(['api', 'graphql', '--input', '-'],
                 {'query': _THREADS, 'variables': {'o': owner, 'r': name, 'n': number}})
    connection = value['data']['repository']['pullRequest']['reviewThreads']
    return {'comments': comments, 'threads': [
        {'id': _field(v, 'id', str), 'resolved': _field(v, 'isResolved', bool),
         'outdated': _field(v, 'isOutdated', bool),
         'comments': [{'id': _field(c, 'databaseId', int), 'author': _login(c['author']),
                       'is_bot': _bot(c['author'], '__typename'),
                       'body': _field(c, 'body', str), 'created_at': _field(c, 'createdAt', str)}
                      for c in _nodes(v['comments'])]} for v in _nodes(connection)]}


@_operation
def protection(repo, branch, root=None):
    if not isinstance(branch, str) or not branch:
        raise ValueError('missing branch')
    value = _api(f'repos/{_repo(repo)}/branches/{quote(branch, safe="")}/protection')
    # enforce_admins is always present on a successful protection response.
    admins = _field(value['enforce_admins'], 'enabled', bool)
    checks = value.get('required_status_checks')
    reviews = value.get('required_pull_request_reviews')
    required = []
    if checks is not None:
        for check in _list(checks.get('checks', [])):
            required.append({'name': _field(check, 'context', str),
                             'app_id': _field(check, 'app_id', int, nullable=True)})
        for name in _list(checks['contexts']):
            if not isinstance(name, str):
                raise ValueError('invalid check context')
            if not any(check['name'] == name for check in required):
                required.append({'name': name, 'app_id': None})
    result = {'required_checks': required,
            'strict': _field(checks, 'strict', bool) if checks is not None else False,
            'approvals': _field(reviews, 'required_approving_review_count', int) if reviews is not None else 0,
            **{key: _field(reviews, key, bool) if reviews is not None else False for key in
               ('dismiss_stale_reviews', 'require_code_owner_reviews', 'require_last_push_approval')},
            'enforce_admins': admins,
            'allow_force_pushes': _field(value['allow_force_pushes'], 'enabled', bool),
            'allow_deletions': _field(value['allow_deletions'], 'enabled', bool),
            'conversation_resolution': _field(value.get('required_conversation_resolution',
                                                         {'enabled': False}), 'enabled', bool)}


    result['merge_queue'] = False
    for rule in _pages(f'repos/{_repo(repo)}/rules/branches/{quote(branch, safe="")}'):
        kind = _field(rule, 'type', str)
        if kind == 'merge_queue':
            result['merge_queue'] = True
        elif kind == 'non_fast_forward':
            result['allow_force_pushes'] = False
        elif kind == 'deletion':
            result['allow_deletions'] = False
        elif kind == 'required_status_checks':
            params = rule['parameters']
            result['strict'] |= _field(params, 'strict_required_status_checks_policy', bool)
            for check in _list(params['required_status_checks']):
                entry = {'name': _field(check, 'context', str),
                         'app_id': _field({'v': check.get('integration_id')}, 'v', int, nullable=True)}
                if entry not in required:
                    required.append(entry)
        elif kind == 'pull_request':
            params = rule['parameters']
            result['approvals'] = max(result['approvals'],
                _field(params, 'required_approving_review_count', int))
            for target, source in (
                ('dismiss_stale_reviews', 'dismiss_stale_reviews_on_push'),
                ('require_code_owner_reviews', 'require_code_owner_review'),
                ('require_last_push_approval', 'require_last_push_approval'),
                ('conversation_resolution', 'required_review_thread_resolution'),
            ):
                result[target] |= _field(params, source, bool)
    return result


def _files(values):
    return [{'path': _field(v, 'filename', str),
             'previous_path': v.get('previous_filename'),
             'status': _field(v, 'status', str),
             'additions': _field(v, 'additions', int),
             'deletions': _field(v, 'deletions', int), 'patch': v.get('patch')}
            for v in _list(values)]


@_operation
def files(ref, root=None):
    repo, number = _ref(ref)
    return _files(_pages(f'repos/{repo}/pulls/{number}/files'))


def _commit(repo, sha):
    pages = _list(_api(f'repos/{repo}/commits/{sha}?per_page=100', pages=True))
    if not pages or any(_sha(page['sha']) != sha for page in pages):
        raise ValueError('missing or mismatched commit page')
    value = pages[0]
    return {'sha': sha, 'parents': [_sha(v['sha']) for v in _list(value['parents'])],
            'at': _field(value['commit']['committer'], 'date', str),
            'message': _field(value['commit'], 'message', str),
            'files': _files([v for page in pages for v in _list(page['files'])])}


@_operation
def history(repo, start, branch, patches=True, root=None):
    repo, start = _repo(repo), _sha(start)
    if not isinstance(branch, str) or not branch:
        raise ValueError('missing base branch')
    end = _sha(_api(f'repos/{repo}/branches/{quote(branch, safe="")}')['commit']['sha'])
    original = _commit(repo, start) if patches else None
    value = _api(f'repos/{repo}/compare/{start}...{end}')
    commits = _list(value['commits'])
    # ponytail: bounded history; larger comparisons are unmeasured.
    if (value['status'] not in ('ahead', 'identical') or
            _field(value, 'total_commits', int) != len(commits)):
        raise ValueError('incomplete base history')
    if not patches:
        return {'commits': [{'sha': _sha(c['sha']),
                            'at': _field(c['commit']['committer'], 'date', str),
                            'message': _field(c['commit'], 'message', str)} for c in commits]}
    result, parent = [], start
    for commit in commits:
        value = _commit(repo, _sha(commit['sha']))
        if value['parents'] != [parent]:
            raise ValueError('nonlinear base history')
        result.append(value)
        parent = value['sha']
    if parent != end:
        raise ValueError('incomplete base history')
    return {'files': original['files'], 'commits': result}


@_operation
def author_login(repo, email, root=None):
    repo = _repo(repo)
    if not isinstance(email, str) or not re.fullmatch(r'[A-Za-z0-9_.+%-]+@[A-Za-z0-9.-]+', email):
        raise ValueError('invalid author email')
    endpoint = ('search/commits?q=author-email%3A' + quote(email, safe='') +
                '%20repo%3A' + quote(repo, safe='') + '&per_page=1')
    value = _api(endpoint)
    items = _list(value['items'])
    if _field(value, 'total_count', int) < 1 or not items:
        raise ValueError('author login unavailable')
    login = _login(items[0]['author'])
    if not login:
        raise ValueError('author login unavailable')
    return {'login': login}


@_operation
def create_pr(draft, root=None):
    repo = _repo(draft['repo'])
    payload = {key: _field(draft, key, str) for key in ('base', 'head', 'title', 'body')}
    if 'draft' in draft:
        payload['draft'] = _field(draft, 'draft', bool)
    value = _api(f'repos/{repo}/pulls', payload=payload)
    return {'number': _field(value, 'number', int), 'url': _field(value, 'html_url', str)}


@_operation
def request_reviewers(ref, logins, root=None):
    repo, number = _ref(ref)
    if not _list(logins) or any(not isinstance(login, str) or not re.fullmatch(
            r'[A-Za-z0-9][A-Za-z0-9-]*', login) for login in logins):
        raise ValueError('expected reviewer logins')
    value = _api(f'repos/{repo}/pulls/{number}/requested_reviewers', payload={'reviewers': logins})
    return {'requested': [_login(user) for user in _list(value['requested_reviewers'])]}


@outward_operation('code_host')
@_operation
def comment(ref, text, thread, root=None):
    repo, number = _ref(ref)
    if not isinstance(text, str):
        raise ValueError('expected comment text')
    if thread is None:
        endpoint = f'repos/{repo}/issues/{number}/comments'
    else:
        if type(thread) is not int or thread <= 0:
            raise ValueError('expected root comment ID')
        endpoint = f'repos/{repo}/pulls/{number}/comments/{thread}/replies'
    value = _api(endpoint, payload={'body': text})
    return {'id': _field(value, 'id', int), 'url': _field(value, 'html_url', str)}


@_operation
def merge(ref, sha, root=None):
    repo, number = _ref(ref)
    _run(['pr', 'merge', f'https://github.com/{repo}/pull/{number}',
          '--squash', '--match-head-commit', _sha(sha)], json_output=False)
    return {'accepted': True, 'sha': sha}


@_operation
def revert_pr(ref, root=None):
    repo, number = _ref(ref)
    original = _api(f'repos/{repo}/pulls/{number}')
    value = _run(['api', 'graphql', '--input', '-'],
                 {'query': _REVERT, 'variables': {'id': _field(original, 'node_id', str)}})
    created = value['data']['revertPullRequest']['revertPullRequest']
    return {'number': _field(created, 'number', int), 'url': _field(created, 'url', str)}


@_operation
def token_scopes(variable, root=None):
    if variable not in ('GH_TOKEN', 'GITHUB_TOKEN') or not os.environ.get(variable):
        raise ValueError('expected a set GH_TOKEN or GITHUB_TOKEN')
    # The child sees only the measured token, as GH_TOKEN, so gh reports exactly its scopes.
    child = {k: v for k, v in os.environ.items() if k not in ('GH_TOKEN', 'GITHUB_TOKEN')}
    child['GH_TOKEN'] = os.environ[variable]
    output = _run(['api', '--include', 'user'], json_output=False, env=child)
    headers = re.split(r'\r?\n\r?\n', output, maxsplit=1)[0]
    match = re.search(r'^x-oauth-scopes:(.*)$', headers, re.IGNORECASE | re.MULTILINE)
    scopes = [s.strip() for s in match[1].split(',') if s.strip()] if match else []
    if not scopes:
        raise ValueError('token scopes unmeasured')
    return {'scopes': scopes}


def auth_status(root=None):
    """Measure gh authentication without exposing account or token output."""
    try:
        code = _run(['auth', 'status', '--hostname', 'github.com'], json_output=False)
        if code == 0:
            return Result(0)
        if code == 1:
            return Result(1, reason='gh auth: missing')
        return Result(2, reason='gh auth: could not run')
    except (OSError, subprocess.SubprocessError, ValueError):
        return Result(2, reason='gh auth: could not run; check gh installation and authentication')
