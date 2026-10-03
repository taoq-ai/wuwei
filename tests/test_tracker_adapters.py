"""One tracker port contract, replayed per adapter from recorded responses; no network."""

import importlib
import json
from pathlib import Path

import pytest

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


def replay(monkeypatch, responses):
    calls = []
    responses = iter(responses)

    def urlopen(request, timeout=None):
        calls.append((request.get_method(), request.full_url, dict(request.header_items()),
                      json.loads(request.data) if request.data else None))
        return Reply(next(responses))

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
    assert {key: result.exit for key, result in results.items()} == dict.fromkeys(results, 0), results
    row, = results['backlog'].data
    assert set(row) == {'id', 'title', 'url', 'updated', 'state'} and row['id'] == item
    assert set(results['create'].data) == {'id', 'url'}
    assert all({'createdAt', 'toState'} <= set(entry) and entry['toState']['name']
               for entry in results['history'].data)
    assert isinstance(results['created'].data, str)
    secret = list(CREDENTIALS[name].values())[-1]
    assert all(secret not in json.dumps(call[3]) for call in calls)
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


def test_github_done_without_board_closes_the_issue(workspace_root, monkeypatch):
    from adapters.tracker import github
    root = workspace_root('github')
    calls = replay(monkeypatch, [{'data': {'repository': {'issue': {'id': 'issue-node-1'}}}},
                                 {'data': {'closeIssue': {'issue': {'id': 'issue-node-1'}}}}])
    assert github.transition('acme/app#1', 'Done', root=root).exit == 0
    assert 'closeIssue' in calls[1][3]['query']
