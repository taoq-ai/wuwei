"""One tracker port contract, replayed per adapter from recorded responses; no network."""

import email.message
import importlib
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
import urllib.error

import pytest

from fakes.replay import NOW, SECONDARY, hms, install_clock, limits
from wuwei import outward

FIXTURES = Path(__file__).parent / 'fixtures/tracker'
CREDENTIALS = {
    'linear': {'LINEAR_API_KEY': 'private-linear-key'},
    'jira': {'JIRA_SITE': 'https://acme.atlassian.net', 'JIRA_EMAIL': 'bot@example.test',
             'JIRA_API_TOKEN': 'private-jira-token'},
    'github': {'GITHUB_TRACKER_TOKEN': 'private-github-token'},
}
SETTINGS = {'linear': 'project = "team-1"\n', 'jira': 'project = "PROJ"\n',
            'github': 'project = "acme/app"\n'}
ITEM = {'linear': 'ENG-1', 'jira': 'PROJ-1', 'github': 'acme/app#1'}


class Reply:
    def __init__(self, payload):
        self.payload = b'' if payload is None else json.dumps(payload).encode()
        self.status = 204 if payload is None else 200

    def __enter__(self):
        return self

    def __exit__(self, *unused):
        pass

    def read(self, *unused):
        return self.payload


def balanced(query):
    """#617: brackets close in order; a stray brace is a GraphQL parse error GitHub answers."""
    stack = []
    for char in query:
        if char in '({[':
            stack.append(')}]'['({['.index(char)])
        elif char in ')}]' and (not stack or stack.pop() != char):
            return False
    return not stack


def replay(monkeypatch, responses):
    calls = []
    responses = iter(responses)

    def urlopen(request, timeout=None):
        calls.append((request.get_method(), request.full_url, dict(request.header_items()),
                      json.loads(request.data) if request.data else None))
        answer = next(responses)
        if isinstance(answer, Exception):
            raise answer
        return Reply(answer)

    monkeypatch.setattr('urllib.request.urlopen', urlopen)
    return calls


@pytest.fixture
def workspace_root(tmp_path, monkeypatch):
    def make(name):
        (tmp_path / '.wuwei').mkdir(exist_ok=True)
        (tmp_path / '.wuwei/config.toml').write_text(
            f'[adapters]\ntracker = "{name}"\n[tracker]\n' + SETTINGS[name])
        monkeypatch.setattr(outward, 'check_call', lambda *args, **kwargs: (0, ''))
        for key, value in CREDENTIALS[name].items():
            monkeypatch.setenv(key, value)
        return tmp_path
    return make


@pytest.mark.parametrize('name', ['linear', 'jira', 'github'])
def test_tracker_port_contract(name, workspace_root, monkeypatch):
    adapter = importlib.import_module(f'adapters.tracker.{name}')
    if hasattr(adapter, '_state_ids'):
        monkeypatch.setattr(adapter, '_state_ids', {})
    root = workspace_root(name)
    calls = replay(monkeypatch, json.loads((FIXTURES / f'{name}.json').read_text()))
    item = ITEM[name]
    draft = {'title': 'Export fails on empty rows', 'description': 'Evidence: cli/x.py:12',
             'item': 'item-1', 'category': 'bugs', 'parent': item}
    results = {
        'backlog': adapter.backlog('', root=root),
        'claim': adapter.claim(item, root=root),
        'transition': adapter.transition(item, 'In Review', root=root),
        'create': adapter.create(draft, root=root),
        'comment': adapter.comment(item, '[2026-09-29 item-1] Phase: gate.', 'progress', root=root),
        'history': adapter.history(item, root=root),
        'created': adapter.created(item, root=root),
    }
    requests = len(calls)
    results['labels'] = adapter.labels(False, root=root)
    assert {key: result.exit for key, result in results.items()} == dict.fromkeys(results, 0), results
    assert results['labels'].data == {'created': [], 'missing': []}
    assert len(calls) == requests + (name == 'github')
    row, = results['backlog'].data
    assert set(row) == {'id', 'title', 'url', 'updated', 'state'} and row['id'] == item
    assert set(results['create'].data) == {'id', 'url'}
    assert all({'createdAt', 'toState'} <= set(entry) and entry['toState']['name']
               for entry in results['history'].data)
    assert isinstance(results['created'].data, str)
    secret = list(CREDENTIALS[name].values())[-1]
    assert all(secret not in json.dumps(call[3]) for call in calls)
    queries = [call[3]['query'] for call in calls if name != 'jira']
    assert all(balanced(query) for query in queries), [q for q in queries if not balanced(q)]
    if name == 'linear':
        create = calls[7][3]['variables']['input']
        assert create['parentId'] == 'uuid-1' and create['teamId'] == 'team-1'
        assert results['create'].data == {'id': 'ENG-2', 'url': 'https://linear.app/acme/issue/ENG-2'}
    if name == 'jira':
        site = 'https://acme.atlassian.net/rest/api/3'
        assert [(method, url) for method, url, _, _ in calls] == [
            ('POST', f'{site}/search/jql'), ('GET', f'{site}/myself'),
            ('PUT', f'{site}/issue/PROJ-1/assignee'), ('GET', f'{site}/issue/PROJ-1/transitions'),
            ('POST', f'{site}/issue/PROJ-1/transitions'), ('POST', f'{site}/issue'),
            ('POST', f'{site}/issueLink'), ('POST', f'{site}/issue/PROJ-1/comment'),
            ('GET', f'{site}/issue/PROJ-1/changelog?maxResults=100'),
            ('GET', f'{site}/issue/PROJ-1?fields=created')]
        assert calls[4][3] == {'transition': {'id': '31'}}
        assert calls[5][3]['fields']['issuetype'] == {'name': 'Bug'}
        assert calls[0][2]['Authorization'].startswith('Basic ')
        assert results['create'].data == {'id': 'PROJ-2', 'url': 'https://acme.atlassian.net/browse/PROJ-2'}
        assert results['history'].data == [{'createdAt': '2026-09-28T11:00:00.000+0000',
                                            'toState': {'name': 'In Progress'}}]
    if name == 'github':
        assert all(url == 'https://api.github.com/graphql' for _, url, _, _ in calls)
        create = calls[6][3]['variables']
        assert create['body'].endswith('\n\nRelated: acme/app#1')
        assert create['labelIds'] == ['label-bug'] and create['repositoryId'] == 'repo-node-1'
        assert results['create'].data == {'id': 'acme/app#2', 'url': 'https://github.com/acme/app/issues/2'}
        assert results['history'].data == [{'createdAt': '2026-09-28T11:00:00Z',
                                            'toState': {'name': 'In Progress'}}]


@pytest.mark.parametrize('name', ['linear', 'jira', 'github'])
def test_missing_credential_makes_no_request(name, workspace_root, monkeypatch):
    adapter = importlib.import_module(f'adapters.tracker.{name}')
    root = workspace_root(name)
    missing = list(CREDENTIALS[name])[-1]
    monkeypatch.delenv(missing)
    calls = replay(monkeypatch, [])
    result = adapter.history(ITEM[name], root=root)
    assert result.exit == 2 and missing in result.reason and calls == []


@pytest.mark.parametrize('name', ['linear', 'jira', 'github'])
def test_malformed_credential_makes_no_request(name, workspace_root, monkeypatch):
    adapter = importlib.import_module(f'adapters.tracker.{name}')
    root = workspace_root(name)
    token = list(CREDENTIALS[name])[-1]
    monkeypatch.setenv(token, 'gh auth token private')
    calls = replay(monkeypatch, [])
    result = adapter.history(ITEM[name], root=root)
    assert result.exit == 2 and calls == []
    assert f'{token} is malformed (contains whitespace)' in result.reason and 'private' not in result.reason


def test_jira_site_must_be_https(workspace_root, monkeypatch):
    from adapters.tracker import jira
    root = workspace_root('jira')
    monkeypatch.setenv('JIRA_SITE', 'http://acme.atlassian.net')
    calls = replay(monkeypatch, [])
    result = jira.created('PROJ-1', root=root)
    assert result.exit == 2 and 'JIRA_SITE' in result.reason and calls == []


def test_jira_create_checks_parent_before_creating(workspace_root, monkeypatch):
    from adapters.tracker import jira
    root = workspace_root('jira')
    calls = replay(monkeypatch, [{'key': 'PROJ-2'}])
    result = jira.create({'title': 'Bug', 'parent': 'proj-12'}, root=root)
    assert result.exit == 2 and calls == []


def test_jira_create_link_failure_still_returns_the_issue(workspace_root, monkeypatch):
    from adapters.tracker import jira
    root = workspace_root('jira')
    calls = replay(monkeypatch, [{'key': 'PROJ-2'}, ['not an object']])
    result = jira.create({'title': 'Bug', 'parent': 'PROJ-1'}, root=root)
    assert result.exit == 0 and result.data['id'] == 'PROJ-2' and len(calls) == 2


def test_github_board_moves_the_project_status(workspace_root, monkeypatch):
    from adapters.tracker import github
    root = workspace_root('github')
    with (root / '.wuwei/config.toml').open('a') as stream:
        stream.write('board = "acme/3"\n')
    calls = replay(monkeypatch, [
        {'data': {'repositoryOwner': {'projectV2': {'id': 'project-1', 'field': {
            'id': 'field-1', 'options': [{'id': 'option-1', 'name': 'In Review'}]}}},
            'repository': {'issue': {'projectItems': {'nodes': [
                {'id': 'item-node-1', 'project': {'id': 'project-1'}}]}}}}},
        {'data': {'updateProjectV2ItemFieldValue': {'projectV2Item': {'id': 'item-node-1'}}}}])
    assert github.transition('acme/app#1', 'In Review', root=root).exit == 0
    assert calls[1][3]['variables'] == {'project': 'project-1', 'item': 'item-node-1',
                                        'field': 'field-1', 'option': 'option-1'}
    assert all(balanced(call[3]['query']) for call in calls)


def test_github_done_without_board_closes_the_issue(workspace_root, monkeypatch):
    from adapters.tracker import github
    root = workspace_root('github')
    calls = replay(monkeypatch, [{'data': {'repository': {'issue': {'id': 'issue-node-1'}}}},
                                 {'data': {'closeIssue': {'issue': {'id': 'issue-node-1'}}}}])
    assert github.transition('acme/app#1', 'Done', root=root).exit == 0
    assert 'closeIssue' in calls[1][3]['query']
    assert all(balanced(call[3]['query']) for call in calls)


MISSING = {'data': {'repository': {'id': 'repo-node-1', 'label': None}}}


def test_github_labels_reads_then_creates(workspace_root, monkeypatch):
    """#670: without a board, in review is a label; labels(create) reads it and creates it."""
    from adapters.tracker import github
    root = workspace_root('github')
    calls = replay(monkeypatch, [MISSING])
    result = github.labels(False, root=root)
    assert (result.exit, result.data) == (0, {'created': [], 'missing': ['In Review']})
    assert len(calls) == 1 and calls[0][3]['variables'] == {
        'owner': 'acme', 'name': 'app', 'label': 'In Review'}
    calls = replay(monkeypatch, [MISSING, {'data': {'createLabel': {'label': {'id': 'label-1'}}}}])
    result = github.labels(True, root=root)
    assert (result.exit, result.data) == (0, {'created': ['In Review'], 'missing': []})
    variables = calls[1][3]['variables']
    assert 'createLabel' in calls[1][3]['query'] and variables['repositoryId'] == 'repo-node-1'
    assert variables['name'] == 'In Review' and variables['color']
    assert all(balanced(call[3]['query']) for call in calls)


def test_github_labels_follow_the_state_name_and_board(workspace_root, monkeypatch):
    from adapters.tracker import github
    root = workspace_root('github')
    with (root / '.wuwei/config.toml').open('a') as stream:
        stream.write('[tracker.states]\nin_review = "Review"\n')
    calls = replay(monkeypatch, [MISSING])
    assert github.labels(False, root=root).data == {'created': [], 'missing': ['Review']}
    assert calls[0][3]['variables']['label'] == 'Review'
    root = workspace_root('github')
    with (root / '.wuwei/config.toml').open('a') as stream:
        stream.write('board = "acme/1"\n')
    calls = replay(monkeypatch, [])
    result = github.labels(True, root=root)
    assert (result.exit, result.data, calls) == (0, {'created': [], 'missing': []}, [])


def test_github_label_create_failure_names_the_label(workspace_root, monkeypatch):
    from adapters.tracker import github
    root = workspace_root('github')
    replay(monkeypatch, [MISSING, {'errors': [{'message': 'Resource not accessible'}], 'data': None}])
    result = github.labels(True, root=root)
    assert result.exit == 2 and '"In Review"' in result.reason and 'acme/app' in result.reason


@pytest.mark.parametrize('message, expected', [
    ('Could not resolve to an Issue\n  with the number of 9.',
     'GitHub error response for acme/app#9: Could not resolve to an Issue with the number of 9.'),
    ('x' * 500, 'GitHub error response for acme/app#9: ' + 'x' * 160),
    ('Bad token=private-github-token', 'GitHub error response for acme/app#9: [REDACTED]'),
    (None, 'GitHub error response for acme/app#9'),
], ids=['one-line', 'capped', 'redacted', 'no-message'])
def test_github_error_names_the_ticket_and_the_first_message(workspace_root, monkeypatch,
                                                             message, expected):
    from adapters.tracker import github
    root = workspace_root('github')
    replay(monkeypatch, [{'errors': [{'message': message}, {'message': 'second'}], 'data': None}])
    result = github.created('acme/app#9', root=root)
    assert result.exit == 2 and result.reason.endswith(expected), result.reason
    assert '\n' not in result.reason and 'second' not in result.reason and 'private' not in result.reason


def gh_replay(monkeypatch, responses):
    """Each answer is a JSON body, or (returncode, stderr) for a failed gh."""
    calls = []
    responses = iter(responses)

    def run(argv, **kwargs):
        calls.append((argv, json.loads(kwargs['input'])))
        assert kwargs['timeout'] == 30 and kwargs['capture_output'] and kwargs['text']
        answer = next(responses)
        if isinstance(answer, tuple):
            body = ('{"errors": [{"message": "Could not resolve to an Issue with the number of 1."}]}'
                    if 'resolve' in answer[1] else '')
            return SimpleNamespace(returncode=answer[0], stdout=body, stderr=answer[1])
        return SimpleNamespace(returncode=0, stdout=json.dumps(answer), stderr='')

    monkeypatch.setattr(subprocess, 'run', run)
    return calls


@pytest.fixture
def gh_root(workspace_root, monkeypatch):
    root = workspace_root('github')
    monkeypatch.delenv('GITHUB_TRACKER_TOKEN')
    with (root / '.wuwei/config.toml').open('a') as stream:
        stream.write('auth = "gh"\n')
    return root


def test_github_port_contract_through_gh(gh_root, monkeypatch):
    from adapters.tracker import github
    http = replay(monkeypatch, [])
    responses = json.loads((FIXTURES / 'github.json').read_text())
    calls = gh_replay(monkeypatch, responses)
    item = ITEM['github']
    draft = {'title': 'Export fails on empty rows', 'description': 'Evidence: cli/x.py:12',
             'item': 'item-1', 'category': 'bugs', 'parent': item}
    results = [github.backlog('', root=gh_root), github.claim(item, root=gh_root),
               github.transition(item, 'In Review', root=gh_root), github.create(draft, root=gh_root),
               github.comment(item, '[2026-09-29 item-1] Phase: gate.', 'progress', root=gh_root),
               github.history(item, root=gh_root), github.created(item, root=gh_root),
               github.labels(False, root=gh_root)]
    assert [result.exit for result in results] == [0] * 8, results
    assert http == [] and len(calls) == len(responses)
    assert all(argv == ['gh', 'api', 'graphql', '--hostname', 'github.com', '--input', '-']
               and set(payload) == {'query', 'variables'} for argv, payload in calls)
    assert all(balanced(payload['query']) for _, payload in calls)
    assert results[3].data == {'id': 'acme/app#2', 'url': 'https://github.com/acme/app/issues/2'}


def test_github_token_wins_over_gh(gh_root, monkeypatch):
    from adapters.tracker import github
    monkeypatch.setenv('GITHUB_TRACKER_TOKEN', 'private-github-token')
    calls = gh_replay(monkeypatch, [])
    http = replay(monkeypatch, [{'data': {'repository': {'issue': {'createdAt': '2026-09-28T10:00:00Z'}}}}])
    assert github.created('acme/app#1', root=gh_root).exit == 0
    assert calls == [] and len(http) == 1


def test_github_default_without_token_names_the_opt_in(workspace_root, monkeypatch):
    from adapters.tracker import github
    root = workspace_root('github')
    monkeypatch.delenv('GITHUB_TRACKER_TOKEN')
    calls, http = gh_replay(monkeypatch, []), replay(monkeypatch, [])
    result = github.created('acme/app#1', root=root)
    assert result.exit == 2 and calls == [] and http == []
    assert 'GITHUB_TRACKER_TOKEN is missing' in result.reason and 'tracker.auth = "gh"' in result.reason


@pytest.mark.parametrize('answer, expected', [
    ((1, 'gh: Bad credentials private (HTTP 401)'),
     'gh api graphql exited 1: HTTP 401: credential rejected'),
    ((1, "gh: Your token has not been granted the required scopes private ['project']"),
     'gh api graphql exited 1: run gh auth refresh -s project'),
    ((4, 'To get started with GitHub CLI, please run:  gh auth login private'),
     'gh api graphql exited 4: run gh auth status'),
    ((1, 'gh: Could not resolve to a Repository with the name private.'),
     'gh api graphql exited 1: GitHub error response for acme/app#1: Could not resolve to an '
     'Issue with the number of 1.'),
    (FileNotFoundError('gh'), 'gh is not on PATH; install the GitHub CLI and run gh auth login'),
    (subprocess.TimeoutExpired(['gh'], 30, stderr='private'), 'gh api graphql timed out after 30 s'),
])
def test_github_gh_failure_names_the_cause_not_the_text(gh_root, monkeypatch, answer, expected):
    from adapters.tracker import github
    if isinstance(answer, Exception):
        monkeypatch.setattr(subprocess, 'run', lambda *a, **k: (_ for _ in ()).throw(answer))
    else:
        gh_replay(monkeypatch, [answer])
    result = github.created('acme/app#1', root=gh_root)
    assert result.exit == 2 and expected in result.reason, result.reason
    assert 'private' not in result.reason


def test_github_gh_error_body_is_a_failure(gh_root, monkeypatch):
    from adapters.tracker import github
    gh_replay(monkeypatch, [{'errors': [{'message': 'private'}], 'data': None}])
    result = github.created('acme/app#1', root=gh_root)
    assert result.exit == 2 and 'GitHub error response' in result.reason


def test_tracker_auth_takes_token_or_gh(workspace_root):
    root = workspace_root('github')
    from wuwei import workspace
    assert workspace.load_config(root)['tracker']['auth'] == 'token'
    with (root / '.wuwei/config.toml').open('a') as stream:
        stream.write('auth = "keychain"\n')
    with pytest.raises(workspace.ConfigError):
        workspace.load_config(root)


def limited_gh(monkeypatch, answers, reset):
    """#738: gh api rate_limit answers from limits(); each graphql call takes the next answer."""
    calls = []
    answers = iter(answers)

    def run(argv, **kwargs):
        calls.append(argv)
        if argv[:3] == ['gh', 'api', 'rate_limit']:
            return SimpleNamespace(returncode=0, stdout=limits(4990, 0, reset), stderr='')
        answer = next(answers)
        if isinstance(answer, tuple):
            return SimpleNamespace(returncode=answer[0], stdout='', stderr=answer[1])
        return SimpleNamespace(returncode=0, stdout=json.dumps(answer), stderr='')

    monkeypatch.setattr(subprocess, 'run', run)
    return calls


CREATED = {'data': {'repository': {'issue': {'createdAt': '2026-09-28T10:00:00Z'}}}}


def no_wait(root):
    with (root / '.wuwei/config.toml').open('a') as stream:
        stream.write('[host]\nrate_limit_wait_seconds = 0\n')


def test_github_gh_rate_limit_is_named_and_retried(gh_root, monkeypatch):
    from adapters.tracker import github
    slept = install_clock(monkeypatch)
    calls = limited_gh(monkeypatch, [(1, SECONDARY), CREATED], NOW + 20)
    result = github.created('acme/app#1', root=gh_root)
    assert (result.exit, result.data) == (0, '2026-09-28T10:00:00Z')
    assert slept == [20] and len(calls) == 3
    no_wait(gh_root)
    limited_gh(monkeypatch, [(1, SECONDARY)], NOW + 20)
    result = github.created('acme/app#1', root=gh_root)
    assert result.exit == 2 and result.reason == (
        f'github.created: could not run: GitHub rate limit until {hms(NOW + 20)} UTC '
        '(0 of 5000 graphql calls left); retry after it')


def limited(code, headers, url='https://api.github.com/graphql'):
    message = email.message.Message()
    for key, value in headers.items():
        message[key] = value
    return urllib.error.HTTPError(url, code, 'error', message, None)


PRIMARY = {'X-RateLimit-Remaining': '0', 'X-RateLimit-Limit': '5000',
           'X-RateLimit-Resource': 'graphql', 'X-RateLimit-Reset': str(NOW + 10)}


@pytest.mark.parametrize('code,headers,reason', [
    (403, PRIMARY, f'GitHub rate limit until {hms(NOW + 10)} UTC (0 of 5000 graphql calls left); retry after it'),
    (429, {'Retry-After': '30'}, f'GitHub rate limit until {hms(NOW + 30)} UTC; retry after it'),
    (429, {}, f'GitHub rate limit until {hms(NOW + 60)} UTC; retry after it'),
    (403, {}, 'HTTP 403: credential has no access'),
])
def test_github_token_rate_limit_reads_the_headers(code, headers, reason, workspace_root, monkeypatch):
    from adapters.tracker import github
    root = workspace_root('github')
    no_wait(root)
    slept = install_clock(monkeypatch)
    replay(monkeypatch, [limited(code, headers)])
    result = github.created('acme/app#1', root=root)
    assert result.exit == 2 and reason in result.reason and slept == []


def test_github_token_rate_limit_waits_and_retries(workspace_root, monkeypatch):
    from adapters.tracker import github
    root = workspace_root('github')
    slept = install_clock(monkeypatch)
    calls = replay(monkeypatch, [limited(403, PRIMARY), CREATED])
    result = github.created('acme/app#1', root=root)
    assert (result.exit, result.data) == (0, '2026-09-28T10:00:00Z')
    assert slept == [10] and len(calls) == 2


def test_other_hosts_keep_the_429_hint(monkeypatch):
    from adapters import _http
    replay(monkeypatch, [limited(429, {'Retry-After': '30'}, 'https://example.test/api')])
    with pytest.raises(_http.Failure) as error:
        _http.request('https://example.test/api', 'token', {})
    assert str(error.value) == 'HTTP 429: rate limited; retry later'
    assert not isinstance(error.value, _http.RateLimited)
