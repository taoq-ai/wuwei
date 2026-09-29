"""Goals, ranking, discovery and intraday decision contracts."""

import json
from pathlib import Path

import pytest

from wuwei import plan


GOALS = '''# Goals

## G-1
outcome: Ship
measure: completed work
 target: 3
 date: 2026-10-30
priority: 1

## G-2
outcome: Learn
measure: experiments
 target: 2
 date: 2026-11-30
priority: 2
'''


def candidate(name, goal='G-1', **score):
    values = {'value': 5, 'time_criticality': 3, 'risk_reduction': 2, 'job_size': 2,
              'reach': 10, 'impact': 1, 'confidence': .8, 'effort': 2}
    values.update(score)
    return {'id': name, 'goal': goal, 'score': values,
            'evidence_lines': {key: f'{key}: measured in issue' for key in values}}


def test_goal_blocks_and_line_error():
    from wuwei.goals import parse

    assert parse(GOALS)['G-1']['priority'] == 1
    with pytest.raises(ValueError, match='line 5'):
        parse(GOALS.replace('measure: completed work', 'measure:'))


def test_goal_file_is_protected_for_seat(tmp_path):
    from wuwei.guards.protect_state import check_file

    base = tmp_path / '.wuwei/memory'
    base.mkdir(parents=True)
    payload = {'cwd': str(tmp_path), 'tool_name': 'Write',
               'tool_input': {'file_path': '.wuwei/memory/goals.md'}}
    assert check_file(payload)[0] == 1


@pytest.mark.parametrize('framework,high,low', [
    ('wsjf', {'value': 8}, {'value': 3}),
    ('rice', {'reach': 20}, {'reach': 5}),
])
def test_rank_formula_and_goal_tie_break(framework, high, low):
    from wuwei.rank import rank

    goals = {'G-1': {'priority': 1}, 'G-2': {'priority': 2}}
    rows = [candidate('low', 'G-2', **low), candidate('high', 'G-1', **high)]
    assert [row['id'] for row in rank(rows, framework, goals)] == ['high', 'low']
    tied = [candidate('a', 'G-2'), candidate('b', 'G-1')]
    assert [row['id'] for row in rank(tied, framework, goals)] == ['b', 'a']


@pytest.mark.parametrize('value', [float('nan'), float('inf'), -float('inf')])
@pytest.mark.parametrize('component', ['reach', 'effort'])
def test_rice_rejects_nonfinite_components(component, value):
    from wuwei.rank import rank

    with pytest.raises(ValueError, match=component):
        rank([candidate('bad', **{component: value})], 'rice', {'G-1': {'priority': 1}})


def test_plan_lint_requires_goal_score_and_evidence(tmp_path):
    from wuwei.rank import validate

    goals = {'G-1': {'priority': 1}}
    item = candidate('a')
    item['goal'] = None
    with pytest.raises(ValueError, match='goal'):
        validate(item, 'wsjf', goals)
    item['goal'] = 'G-1'
    del item['score']['value']
    with pytest.raises(ValueError, match='value'):
        validate(item, 'wsjf', goals)
    item['score']['value'] = 5
    del item['evidence_lines']['value']
    with pytest.raises(ValueError, match='value.*evidence'):
        validate(item, 'wsjf', goals)


def test_plan_proposal_rejects_unplanned_missing_and_bad_score(tmp_path):
    from wuwei.plan import _proposal

    row = candidate('a')
    row.update(evidence='source', scope='one function', overlap='none', track='SLICE',
               flags={'trust_surface': False, 'boundary_relevant': False, 'agent_surface': False})
    data = {'goals': ['G-1'], 'cap': 1, 'seat_policy': {'builder': {'runtime': 'claude', 'model': 'sonnet'}},
            'envelope': {'start': '09:00', 'end': '17:00', 'net_build_hours': 5},
            'sweep': {'tracker': 'unmeasured'}, 'candidates': [row]}
    row['goal'] = None
    with pytest.raises(ValueError, match='goal'):
        _proposal(data, GOALS, 'wsjf')
    row['goal'] = 'G-1'
    del row['evidence_lines']['job_size']
    with pytest.raises(ValueError, match='job_size.*evidence'):
        _proposal(data, GOALS, 'wsjf')


def test_autostart_strict_full_and_safety():
    from wuwei.discovery import start_decision

    row = {'goal': 'G-1', 'track': 'FULL', 'flags': {}, 'paths': []}
    config = {'discovery': {'autostart': 'strict'}, 'repos': [{'merge': {'never_auto_paths': ['infra/*']}}]}
    assert start_decision(row, config, {'G-1'}, within_budget=True, above_cut=True) == 'owner'
    config['discovery']['autostart'] = 'goal'
    assert start_decision(row, config, {'G-1'}, within_budget=True, above_cut=True) == 'start'
    row['paths'] = ['infra/main.tf']
    assert start_decision(row, config, {'G-1'}, within_budget=True, above_cut=True) == 'owner'
    row['paths'] = []
    row['flags'] = {'risk': True}
    assert start_decision(row, config, {'G-1'}, within_budget=True, above_cut=True) == 'owner'
    row['flags'] = {}
    assert start_decision(row, config, {'G-1'}, within_budget=False, above_cut=True) == 'owner'


def test_discovery_deduplicates_and_marks_unmeasured():
    from wuwei.discovery import dedupe

    sources = {'tracker': None, 'scanner': [{'id': 'A', 'evidence': 'finding'}],
               'review_bot': [{'id': 'B', 'evidence': 'review'}]}
    result = dedupe(sources, tracker_ids={'A'}, day_ids={'B'})
    assert result['candidates'] == []
    assert result['sources']['tracker'] == 'unmeasured'
    assert result['sources']['scanner'] == 'measured: 1'


def test_rank_cli_returns_order_and_bad_goals_line(tmp_path, monkeypatch, capsys):
    from wuwei.__main__ import main

    base = tmp_path / '.wuwei'
    (base / 'memory').mkdir(parents=True)
    (base / 'memory/goals.md').write_text(GOALS)
    (base / 'config.toml').write_text('[prioritisation]\nframework = "rice"\n')
    source = tmp_path / 'candidates.json'
    source.write_text(json.dumps([candidate('low', reach=5), candidate('high', reach=20)]))
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    assert main(['rank', str(source)]) == 0
    assert [row['id'] for row in json.loads(capsys.readouterr().out)] == ['high', 'low']
    (base / 'memory/goals.md').write_text('## G-1\noutcome:\n')
    assert main(['rank', str(source)]) == 2
    assert 'line 2' in capsys.readouterr().err


def test_discover_reads_ports_and_skips_day_items(tmp_path, monkeypatch):
    from wuwei.discovery import discover
    from wuwei import state
    from wuwei.registry import Result

    base = tmp_path / '.wuwei'
    base.mkdir()
    (base / 'config.toml').write_text('[[repos]]\nname = "x/y"\npath = "repo"\ndefault_branch = "main"\n'
                                      '[adapters]\nreview_bot = "greptile"\nscanner = "none"\n')
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T09:00:00+02:00')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    state._write_state(lambda value: value.update(raised_prs=['x/y#1'], items={'x/y#1:bot:1': {'goal': 'G-1'}}),
                       tmp_path, reserved=False)

    class Bot:
        def open_findings(self, ref, *, root):
            return Result(0, [{'id': 1, 'body': 'fix test'}])

    class Host:
        def threads(self, ref, *, root):
            return Result(0, {'threads': [{'id': 't1', 'resolved': False}]})

    result = discover(tmp_path, ports={'review_bot': Bot(), 'code_host': Host()})
    assert [row['id'] for row in result['candidates']] == ['x/y#1:thread:t1']
    assert result['sources']['tracker'] == 'unmeasured'
    assert result['sources']['scanner'] == 'unmeasured'


def test_morning_plan_reports_discovery_sources(tmp_path, monkeypatch):
    from wuwei import discovery

    base = tmp_path / '.wuwei/memory'
    base.mkdir(parents=True)
    (base / 'goals.md').write_text(GOALS)
    (base.parent / 'config.toml').write_text('')
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T09:00:00+02:00')
    monkeypatch.setattr(discovery, 'discover', lambda root: {'sources': {'tracker': 'unmeasured'}, 'candidates': []})
    row = candidate('a')
    row.update(evidence='source', scope='one function', overlap='none', track='SLICE',
               flags={'trust_surface': False, 'boundary_relevant': False, 'agent_surface': False})
    data = {'goals': ['G-1'], 'cap': 1, 'seat_policy': {'builder': {'runtime': 'claude', 'model': 'sonnet'}},
            'envelope': {'start': '09:00', 'end': '17:00', 'net_build_hours': 5},
            'sweep': {'processes': 'measured: none'}, 'candidates': [row]}
    path = plan.propose(data, tmp_path)
    assert 'discovery.tracker: unmeasured' in path.read_text()


def test_seat_free_queue_threshold(tmp_path, monkeypatch):
    from wuwei import discovery

    base = tmp_path / '.wuwei'
    base.mkdir()
    (base / 'config.toml').write_text('[discovery]\nmin_queue = 2\n')
    calls = []
    monkeypatch.setattr(discovery, 'discover', lambda root: calls.append(root) or {'candidates': []})
    assert discovery.when_seat_frees(tmp_path, queue_size=2) is None
    assert discovery.when_seat_frees(tmp_path, queue_size=1) == {'candidates': []}
    assert calls == [tmp_path]


def test_failed_discovery_port_is_unmeasured(tmp_path, monkeypatch):
    from wuwei.discovery import discover
    from wuwei import state
    from wuwei.registry import Result

    base = tmp_path / '.wuwei'
    base.mkdir()
    (base / 'config.toml').write_text('[adapters]\nreview_bot = "greptile"\ncode_host = "none"\n')
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T09:00:00+02:00')
    state._write_state(lambda value: value.update(raised_prs=['x/y#1']), tmp_path, reserved=False)

    class Bot:
        def open_findings(self, ref, *, root):
            return Result(2, None, 'timeout')

    result = discover(tmp_path, ports={'review_bot': Bot()})
    assert result['sources']['review_bot'] == 'unmeasured'


def test_sweep_records_discovery_measurement(tmp_path, monkeypatch):
    from wuwei import discovery, watch

    root = tmp_path
    (root / '.wuwei').mkdir()
    (root / '.wuwei/config.toml').write_text('')
    monkeypatch.setattr(discovery, 'discover', lambda path: {'sources': {'tracker': 'unmeasured'}, 'candidates': []})
    monkeypatch.setattr(watch.obligations, 'evaluate', lambda path: {})
    monkeypatch.setattr(watch, 'activity', lambda path: (0, {'stale': [], 'unreadable': 0}))
    watch.sweep(root, watch_health=(0, ''))
    events = list((root / '.wuwei/days').glob('*/events.jsonl'))
    assert events and 'discovery.tracker' in events[0].read_text()


@pytest.mark.parametrize('code', [0, 1, 2])
def test_build_returns_loop_status_without_discovery(monkeypatch, code):
    from argparse import Namespace
    from wuwei.commands import build
    from wuwei import discovery

    monkeypatch.setattr(build, 'run_loop', lambda *args: code)
    monkeypatch.setattr(discovery, 'when_seat_frees',
                        lambda *args, **kwargs: pytest.fail('build called discovery'))
    assert build.run(Namespace(operation='A', arguments=['brief', 'tree'])) == code


def test_discovery_red_base_checks_from_code_host_port(tmp_path, monkeypatch):
    from wuwei.discovery import discover
    from wuwei import state
    from wuwei.registry import Result

    base = tmp_path / '.wuwei'
    base.mkdir()
    (base / 'config.toml').write_text('')
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T09:00:00+02:00')
    state._write_state(lambda value: value.update(raised_prs=['x/y#1']), tmp_path, reserved=False)

    class Host:
        def pr(self, ref, *, root):
            return Result(0, {'base_sha': 'a' * 40})
        def checks(self, ref, sha, *, root):
            return Result(0, [{'name': 'tests', 'conclusion': 'failure', 'url': 'https://example.test/check'}])
        def threads(self, ref, *, root):
            return Result(0, {'threads': []})

    result = discover(tmp_path, ports={'code_host': Host()})
    assert result['sources']['base_checks'] == 'measured: 1'
    assert result['candidates'][0]['id'] == 'x/y#1:base:tests'


def test_unplanned_mark_allows_candidate_without_goal():
    from wuwei.rank import rank

    item = candidate('incident')
    item.pop('goal')
    item['unplanned'] = True
    assert rank([item], 'wsjf', {}) == [item]


def test_plan_proposal_orders_queue_by_score(tmp_path, monkeypatch):
    from wuwei import discovery

    base = tmp_path / '.wuwei/memory'
    base.mkdir(parents=True)
    (base / 'goals.md').write_text(GOALS)
    (base.parent / 'config.toml').write_text('')
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T09:00:00+02:00')
    monkeypatch.setattr(discovery, 'discover', lambda root: {'sources': {'tracker': 'unmeasured'}, 'candidates': []})
    rows = [candidate('low', value=2), candidate('high', value=8)]
    for row in rows:
        row.update(evidence='source', scope='one function', overlap='none', track='SLICE',
                   flags={'trust_surface': False, 'boundary_relevant': False, 'agent_surface': False})
    data = {'goals': ['G-1'], 'cap': 1, 'seat_policy': {'builder': {'runtime': 'claude', 'model': 'sonnet'}},
            'envelope': {'start': '09:00', 'end': '17:00', 'net_build_hours': 5},
            'sweep': {'tracker': 'unmeasured'}, 'candidates': rows}
    path = plan.propose(data, tmp_path)
    assert path.read_text().index('high (SLICE)') < path.read_text().index('low (SLICE)')


def test_goal_guard_blocks_outside_workspace(tmp_path):
    from wuwei.guards.protect_state import check_file

    payload = {'cwd': str(tmp_path), 'tool_name': 'Write',
               'tool_input': {'file_path': '.wuwei/memory/goals.md'}}
    assert check_file(payload)[0] == 1


@pytest.mark.parametrize('name', ['proposal.json', 'plan.md'])
def test_plan_producer_files_are_protected(tmp_path, name):
    from wuwei.guards.protect_state import check_file

    (tmp_path / '.wuwei').mkdir()
    payload = {'cwd': str(tmp_path), 'tool_name': 'Write',
               'tool_input': {'file_path': f'.wuwei/days/2026-09-28/{name}'}}
    assert check_file(payload)[0] == 1


def test_autostart_unknown_risk_or_paths_goes_to_owner():
    from wuwei.discovery import start_decision

    config = {'discovery': {'autostart': 'goal'}, 'repos': []}
    assert start_decision({'goal': 'G-1', 'track': 'SLICE'}, config, {'G-1'},
                          within_budget=True, above_cut=True) == 'owner'


def test_goal_guard_override_still_protects_other_workspace(tmp_path, monkeypatch):
    from wuwei.guards.protect_state import check_file

    root = tmp_path / 'workspace'
    (root / '.wuwei').mkdir(parents=True)
    outside = tmp_path / 'outside'
    outside.mkdir()
    monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
    payload = {'cwd': str(outside), 'tool_name': 'Write',
               'tool_input': {'file_path': '.wuwei/memory/goals.md'}}
    assert check_file(payload)[0] == 1


def test_plan_cli_writes_proposal_when_discovery_is_unmeasured(tmp_path, monkeypatch):
    from argparse import Namespace
    from wuwei.commands.plan import run
    from wuwei import discovery

    base = tmp_path / '.wuwei/memory'
    base.mkdir(parents=True)
    (base / 'goals.md').write_text(GOALS)
    (base.parent / 'config.toml').write_text('')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T09:00:00+02:00')
    monkeypatch.setattr(discovery, 'discover', lambda root: {'sources': {'tracker': 'unmeasured'}, 'candidates': []})
    row = candidate('a')
    row.update(evidence='source', scope='one function', overlap='none', track='SLICE',
               flags={'trust_surface': False, 'boundary_relevant': False, 'agent_surface': False})
    data = {'goals': ['G-1'], 'cap': 1, 'seat_policy': {'builder': {'runtime': 'claude', 'model': 'sonnet'}},
            'envelope': {'start': '09:00', 'end': '17:00', 'net_build_hours': 5},
            'sweep': {'processes': 'measured'}, 'candidates': [row]}
    source = tmp_path / 'input.json'
    source.write_text(json.dumps(data))
    assert run(Namespace(action='propose', input=source)) == 0
    assert 'unmeasured' in next((base.parent / 'days').glob('*/plan.md')).read_text()


def test_discovery_pr_comment_follow_up(tmp_path, monkeypatch):
    from wuwei.discovery import discover
    from wuwei import state
    from wuwei.registry import Result

    base = tmp_path / '.wuwei'
    base.mkdir()
    (base / 'config.toml').write_text('')
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T09:00:00+02:00')
    state._write_state(lambda value: value.update(raised_prs=['x/y#1']), tmp_path, reserved=False)

    class Host:
        def threads(self, ref, *, root):
            return Result(0, {'threads': [], 'comments': [{'id': 2, 'body': 'Follow up on docs'}]})

    result = discover(tmp_path, ports={'code_host': Host()})
    assert result['sources']['pr_follow_ups'] == 'measured: 1'
    assert result['candidates'][0]['id'] == 'x/y#1:followup:2'
