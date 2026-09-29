"""Morning proposal and approval contract."""

import json
from pathlib import Path

import pytest

from wuwei import plan, state


@pytest.fixture
def root(tmp_path, monkeypatch):
    base = tmp_path / '.wuwei'
    (base / 'memory').mkdir(parents=True)
    (base / 'memory/goals.md').write_text('# Goals\n## G-1\noutcome: Ship a useful result\nmeasure: shipped\ntarget: 1\ndate: 2026-10-30\npriority: 1\n')
    (base / 'config.toml').write_text('')
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T09:00:00+02:00')
    return tmp_path


def proposal():
    return {
        'goals': ['G-1'], 'cap': 2,
        'seat_policy': {'builder': {'runtime': 'claude', 'model': 'sonnet'}},
        'envelope': {'start': '09:00', 'end': '17:00', 'net_build_hours': 5},
        'sweep': {'processes': 'measured: none', 'tracker': 'unmeasured: absent'},
        'candidates': [{'id': 'A', 'goal': 'G-1', 'evidence': 'tracker A',
                        'scope': 'one function', 'overlap': 'none', 'track': 'SLICE',
                        'flags': {'trust_surface': False, 'boundary_relevant': False,
                                  'agent_surface': False},
                        'score': {'value': 5, 'time_criticality': 3, 'risk_reduction': 2, 'job_size': 2},
                        'evidence_lines': {key: 'tracker A' for key in ('value', 'time_criticality', 'risk_reduction', 'job_size')}}],
    }


def test_propose_writes_plan_without_state_or_worktree(root):
    path = plan.propose(proposal(), root)
    assert path == root / '.wuwei/days/2026-09-28/plan.md'
    assert 'tracker A' in path.read_text()
    assert 'unmeasured: absent' in path.read_text()
    assert not (path.parent / 'state.json').exists()
    assert not list(root.glob('**/.git'))


def test_approve_selected_items_and_reserve_gate_fields(root):
    plan.propose(proposal(), root)
    plan.approve(['A'], root, goals_confirmed=True)
    data = state.read_state(root)
    assert data['gate_approved'] is True
    assert data['approved_items'] == ['A']
    assert data['goals'] == ['G-1']
    assert data['cap'] == 2
    assert data['envelope']['net_build_hours'] == 5
    assert data['seat_policy']['builder']['runtime'] == 'claude'
    assert data['items']['A']['phase'] == 'planned'
    with pytest.raises(state.StateError):
        state.set_state('cap', 5, root)
    with pytest.raises(state.StateError):
        state.set_state('approved_items', ['B'], root)
    assert not list(root.glob('**/.git'))


def test_intraday_budget_counts_morning_rank_size(root):
    plan.propose(proposal(), root)
    plan.approve(['A'], root, goals_confirmed=True)
    candidate = {**proposal()['candidates'][0], 'id': 'B', 'paths': ['src/file.py']}
    candidate['score'] = {**candidate['score'], 'job_size': 5}
    state._write_state(lambda day: day.setdefault('discovery_candidates', {}).update(B=candidate),
                       root, reserved=False)
    assert plan.add('B', root)['action'] == 'owner'


def test_import_requires_explicit_approval(root):
    yesterday = root / '.wuwei/days/2026-09-27'
    yesterday.mkdir(parents=True)
    (yesterday / 'state.json').write_text(json.dumps({'items': {'OLD': {'phase': 'implement', 'status': 'running'},
                                                             'DONE': {'phase': 'merged'}}}))
    plan.propose(proposal(), root)
    plan.approve(['A'], root, goals_confirmed=True, import_yesterday=True)
    data = state.read_state(root)
    assert data['items']['OLD']['phase'] == 'planned'
    assert data['items']['OLD']['status'] == 'queued'
    assert 'DONE' not in data['items']
    events = [json.loads(line) for line in (root / '.wuwei/days/2026-09-28/events.jsonl').read_text().splitlines()]
    assert events[-1]['kind'] == 'state.import'
    assert events[-1]['payload']['items'] == ['OLD']


def test_bad_proposal_does_not_write(root):
    bad = proposal()
    bad['candidates'][0]['evidence'] = ''
    with pytest.raises(ValueError, match='evidence'):
        plan.propose(bad, root)
    assert not (root / '.wuwei/days').exists()


def test_prior_items_are_not_imported_without_explicit_option(root):
    yesterday = root / '.wuwei/days/2026-09-27'
    yesterday.mkdir(parents=True)
    (yesterday / 'state.json').write_text(json.dumps({'items': {'OLD': {'phase': 'planned'}}}))
    plan.propose(proposal(), root)
    plan.approve(['A'], root, goals_confirmed=True)
    assert set(state.read_state(root)['items']) == {'A'}
    events = [json.loads(line) for line in (root / '.wuwei/days/2026-09-28/events.jsonl').read_text().splitlines()]
    assert all(event['kind'] != 'state.import' for event in events)


def test_cli_propose_and_approve(root, monkeypatch):
    import os
    import subprocess
    import sys

    source = root / 'lead.json'
    source.write_text(json.dumps(proposal()))
    monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
    env = {**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[1] / 'cli')}
    command = [sys.executable, '-P', '-m', 'wuwei', 'plan']
    result = subprocess.run([*command, 'propose', str(source)], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert 'unmeasured' in next((root / '.wuwei/days').glob('*/plan.md')).read_text()
    result = subprocess.run([*command, 'approve', '--items', 'A', '--goals-confirmed'],
                            env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert state.read_state(root)['approved_items'] == ['A']


def test_worktree_creation_refuses_before_gate(root):
    from wuwei import workspace

    class Fake:
        def worktree_add(self, *args, **kwargs):
            raise AssertionError('VCS must not be called before approval')

    with pytest.raises(state.StateError, match='morning gate'):
        workspace.create_worktree(root / 'repo', 'item', root / 'tree', root, Fake())
