"""Tracker backlog and lifecycle calls with offline ports."""

import json
from pathlib import Path

import pytest

from adapters.tracker import linear, none
from fakes.tracker import Fake
from wuwei import discovery, dispatch, registry, state


@pytest.mark.parametrize('team', ['', 'team-1'])
def test_linear_backlog_recorded(monkeypatch, team):
    calls = []
    def query(query, variables):
        calls.append((query, variables))
        return json.loads((Path(__file__).parent / 'fixtures/tracker/backlog.json').read_text())['data']
    monkeypatch.setattr(linear, '_query', query)
    result = linear.backlog(team)
    assert result.exit == 0
    assert result.data == [{'id': 'ABC-1', 'title': 'Fix',
                            'url': 'https://linear.app/x/issue/ABC-1',
                            'updated': '2026-09-29T00:00:00Z', 'state': 'Todo'}]
    assert calls[0][1] == ({'team': team} if team else {})
    assert 'state:{type:{nin:["completed","canceled"]}}' in calls[0][0]
    assert ('team:{id:{eq:$team}}' in calls[0][0]) == bool(team)


def _case_linear_transition_resolves_team_state_once(monkeypatch):
    calls = []
    def query(query, variables):
        calls.append(variables)
        if 'issueUpdate' in query:
            return {'issueUpdate': {'success': True, 'issue': {'id': 'uuid-1'}}}
        if 'workflowStates' in query:
            return {'workflowStates': {'nodes': [{'id': 'state-1', 'name': 'In Review'}],
                                       'pageInfo': {'hasNextPage': False}}}
        return {'issue': {'team': {'id': 'team-1'}}}
    monkeypatch.setattr(linear, '_query', query)
    monkeypatch.setattr(linear, '_state_ids', {})
    assert linear.transition('ABC-1', 'In Review').exit == 0
    assert linear.transition('ABC-1', 'In Review').exit == 0
    assert calls.count({'team': 'team-1'}) == 1
    assert calls[-1]['input'] == {'stateId': 'state-1'}


def _case_linear_transition_resolves_name_starting_with_state(monkeypatch):
    calls = []
    def query(query, variables):
        calls.append((query, variables))
        if 'issueUpdate' in query:
            return {'issueUpdate': {'success': True, 'issue': {'id': 'uuid-1'}}}
        if 'workflowStates' in query:
            return {'workflowStates': {'nodes': [{'id': 'uuid-state', 'name': 'state-review'}],
                                       'pageInfo': {'hasNextPage': False}}}
        return {'issue': {'team': {'id': 'team-2'}}}
    monkeypatch.setattr(linear, '_query', query)
    monkeypatch.setattr(linear, '_state_ids', {})
    assert linear.transition('ABC-1', 'state-review').exit == 0
    assert calls[-1][1]['input'] == {'stateId': 'uuid-state'}


@pytest.mark.parametrize("scenario_fn", [
    _case_linear_transition_resolves_team_state_once,
    _case_linear_transition_resolves_name_starting_with_state,
])
def test_linear_transition_cases_30(monkeypatch, scenario_fn):
    scenario_fn(monkeypatch)


def test_discovery_tracker_candidates_and_none(tmp_path, monkeypatch):
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('[adapters]\ntracker = "linear"\n')
    state._write_state(lambda day: day['items'].update({'ABC-1': {}}), tmp_path)
    tracker = Fake({'backlog': registry.Result(0, [
        {'id': 'ABC-1', 'title': 'Already planned'},
        {'id': 'ABC-2', 'title': 'Candidate'}])})
    assert discovery.discover(tmp_path, ports={'tracker': tracker})['candidates'] == [
        {'id': 'ABC-2', 'title': 'Candidate', 'source': 'tracker'}]
    assert tracker.calls == [('backlog', ('',), tmp_path)]
    (tmp_path / '.wuwei/config.toml').write_text('')
    assert none.backlog('', root=tmp_path).reason == 'tracker adapter is none'


def test_discover_marks_the_tracker_unmeasured_when_it_fails(tmp_path, monkeypatch):
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('[adapters]\ntracker = "linear"\n')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    tracker = Fake({'backlog': registry.Result(2, reason='LINEAR_API_KEY is missing')})
    monkeypatch.setattr(registry, 'load', lambda kind, config: tracker)
    assert discovery.discover()['sources']['tracker'].startswith('unmeasured')


def test_tracker_calls_record_order_and_failures(tmp_path, monkeypatch):
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text(
        '[adapters]\ntracker = "linear"\n[tracker.states]\nin_review = "In Review"\ndone = "Done"\n')
    tracker = Fake({'claim': registry.Result(0, {}),
                    'transition': registry.Result(0, {})})
    monkeypatch.setattr(registry, 'load', lambda kind, config: tracker)
    dispatch.tracker_call('ABC-1', 'claim', tmp_path)
    dispatch.tracker_call('ABC-1', 'in_review', tmp_path)
    dispatch.tracker_call('ABC-1', 'done', tmp_path)
    assert tracker.calls == [('claim', ('ABC-1',), tmp_path),
                             ('transition', ('ABC-1', 'In Review'), tmp_path),
                             ('transition', ('ABC-1', 'Done'), tmp_path)]
    event_file, = (tmp_path / '.wuwei/days').glob('*/events.jsonl')
    events = [json.loads(line) for line in event_file.read_text().splitlines()]
    assert [(event['payload']['action'], event['payload']['exit']) for event in events
            if event['kind'] == 'tracker.call'] == [
                ('claim', 0), ('in_review', 0), ('done', 0)]


def test_no_tracker_lifecycle_is_unmeasured(tmp_path):
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('')
    result = dispatch.tracker_call('ABC-1', 'claim', tmp_path)
    assert result.exit == 2 and result.reason.startswith('tracker adapter is none, so tracker updates are skipped;')


def test_discover_lists_every_repository_and_narrows_with_repo(tmp_path, monkeypatch, capsys):
    # #601: candidates name their source repository; --repo narrows to one configured repository.
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('[adapters]\ntracker = "linear"\n' + ''.join(
        f'[[repos]]\nname = "{name}"\npath = "{name}"\ndefault_branch = "main"\n'
        for name in ('acme/app', 'acme/app-docs')))
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    tracker = Fake({'backlog': registry.Result(0, [{'id': 'acme/app#1', 'title': 'A'},
                                                   {'id': 'acme/app-docs#2', 'title': 'B'},
                                                   {'id': 'ENG-3', 'title': 'C'}])})
    monkeypatch.setattr(registry, 'load', lambda kind, config: tracker)
    assert discovery.discover()['candidates'] == [
        {'id': 'acme/app#1', 'title': 'A', 'source': 'tracker', 'repo': 'acme/app'},
        {'id': 'acme/app-docs#2', 'title': 'B', 'source': 'tracker', 'repo': 'acme/app-docs'},
        {'id': 'ENG-3', 'title': 'C', 'source': 'tracker'}]
    assert [row['id'] for row in discovery.discover(repo='acme/app-docs')['candidates']] == ['acme/app-docs#2', 'ENG-3']
    with pytest.raises(ValueError, match='acme/unknown is not a configured repository.*acme/app, acme/app-docs'):
        discovery.discover(repo='acme/unknown')


def test_discover_repo_counts_a_github_tracker_project(tmp_path, monkeypatch, capsys):
    # #601 review F3: a GitHub tracker.project outside [[repos]] is tagged and selectable.
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text(
        '[adapters]\ntracker = "github"\n[tracker]\nproject = "acme/app-docs"\n'
        '[[repos]]\nname = "acme/app"\npath = "app"\ndefault_branch = "main"\n')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    tracker = Fake({'backlog': registry.Result(0, [{'id': 'acme/app#1', 'title': 'A'},
                                                   {'id': 'acme/app-docs#2', 'title': 'B'}])})
    monkeypatch.setattr(registry, 'load', lambda kind, config: tracker)
    assert [row['id'] for row in discovery.discover(repo='acme/app')['candidates']] == ['acme/app#1']
    assert [row['id'] for row in discovery.discover(repo='acme/app-docs')['candidates']] == ['acme/app-docs#2']
