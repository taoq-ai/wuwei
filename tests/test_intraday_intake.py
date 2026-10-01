"""Intraday admission and discovery routing."""

import json

import pytest

from wuwei import discovery, plan, state


@pytest.fixture
def root(tmp_path, monkeypatch):
    base = tmp_path / '.wuwei'
    (base / 'memory').mkdir(parents=True)
    (base / 'memory/goals.md').write_text(
        '# Goals\n## G-1\noutcome: Ship\nmeasure: shipped\n'
        'target: 1\ndate: 2026-10-30\npriority: 1\n')
    (base / 'config.toml').write_text('[discovery]\nautostart = "goal"\n')
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T10:00:00+02:00')
    plan_data = {
        'goals': ['G-1'], 'cap': 2,
        'seat_policy': {'builder': {'runtime': 'claude', 'model': 'sonnet'}},
        'envelope': {'start': '09:00', 'end': '17:00', 'net_build_hours': 5},
        'sweep': {'manual': 'measured: none'}, 'candidates': [],
    }
    plan.propose(plan_data, tmp_path)
    plan.approve([], tmp_path, goals_confirmed=True)
    return tmp_path


def candidate(name='NEW', track='SLICE'):
    return {
        'id': name, 'goal': 'G-1', 'track': track, 'evidence': 'tracker item',
        'scope': 'one function', 'overlap': 'none', 'paths': ['src/file.py'],
        'flags': {'trust_surface': False, 'boundary_relevant': False,
                  'agent_surface': False},
        'estimated_hours': 2,
        'score': {'value': 5, 'time_criticality': 3,
                  'risk_reduction': 2, 'job_size': 2},
        'evidence_lines': {key: 'tracker evidence' for key in
                           ('value', 'time_criticality', 'risk_reduction', 'job_size')},
    }


def save_candidate(root, row):
    state._write_state(
        lambda data: data.setdefault('discovery_candidates', {}).update({row['id']: row}),
        root, reserved=False)


def test_plan_add_admits_goal_slice_after_gate(root):
    save_candidate(root, candidate())
    result = plan.add('NEW', root)
    day = state.read_state(root)
    assert result['action'] == 'build next'
    assert day['items']['NEW']['status'] == 'queued'
    assert 'NEW' in day['approved_items']


def test_plan_add_sends_strict_full_to_owner(root):
    (root / '.wuwei/config.toml').write_text('[discovery]\nautostart = "strict"\n')
    save_candidate(root, candidate(track='FULL'))
    result = plan.add('NEW', root)
    assert result['action'] == 'owner'
    assert 'NEW' not in state.read_state(root)['items']
    assert state.read_state(root)['intraday_proposals']['NEW']['decision'] == 'owner'


def test_plan_add_rejects_missing_score_evidence(root):
    row = candidate()
    del row['evidence_lines']['job_size']
    save_candidate(root, row)
    with pytest.raises(ValueError, match='job_size.*evidence'):
        plan.add('NEW', root)
    assert 'NEW' not in state.read_state(root)['items']


def test_discovery_intake_saves_candidates_and_applies_policy(root, monkeypatch):
    monkeypatch.setattr(discovery, 'discover', lambda path: {
        'sources': {'tracker': 'measured: 1'}, 'candidates': [candidate()]})
    result = discovery.intake(root, trigger='sweep')
    assert result['started'] == ['NEW']
    assert state.read_state(root)['items']['NEW']['phase'] == 'planned'
    events = [json.loads(line) for line in
              (root / '.wuwei/days/2026-09-29/events.jsonl').read_text().splitlines()]
    assert any(row['kind'] == 'plan.added' for row in events)


def test_strict_full_appears_in_owner_decision_batch(root):
    from wuwei import steward
    (root / '.wuwei/config.toml').write_text('[discovery]\nautostart = "strict"\n')
    save_candidate(root, candidate(track='FULL'))
    assert plan.add('NEW', root)['action'] == 'owner'
    queue = steward.decision_queue(root)
    assert any(row['id'] == 'NEW' and row['recommendation'] == 'defer'
               for row in queue)


def test_incomplete_discovery_candidate_goes_to_owner(root, monkeypatch):
    monkeypatch.setattr(discovery, 'discover', lambda path: {
        'sources': {'tracker': 'measured: 1'},
        'candidates': [{'id': 'PARTIAL', 'title': 'Needs triage'}]})
    result = discovery.intake(root, trigger='sweep')
    assert result['owner'] == ['PARTIAL']
    assert 'PARTIAL' not in state.read_state(root)['items']


def test_intake_skips_candidates_the_steward_cannot_lint(root, monkeypatch):
    from wuwei import steward
    unsafe = 'org/repo#1:thread:PRRT_1'
    monkeypatch.setattr(discovery, 'discover', lambda path: {
        'sources': {'tracker': 'measured: 1'},
        'candidates': [{'id': unsafe, 'title': 'Reply'}, {'id': 'PARTIAL', 'title': 'Needs triage'}]})
    assert discovery.intake(root, trigger='sweep')['owner'] == ['PARTIAL']
    assert list(state.read_state(root)['intraday_proposals']) == ['PARTIAL']
    events = [json.loads(line) for line in
              (root / '.wuwei/days/2026-09-29/events.jsonl').read_text().splitlines()]
    assert not any(row['kind'] == 'plan.proposed' and row['payload']['item'] == unsafe
                   for row in events)
    assert [row['id'] for row in steward.decision_queue(root)] == ['PARTIAL']


def test_intake_does_not_repeat_owner_proposals(root, monkeypatch):
    monkeypatch.setattr(discovery, 'discover', lambda path: {
        'sources': {'tracker': 'measured: 1'},
        'candidates': [{'id': 'PARTIAL', 'title': 'Needs triage'}]})
    assert discovery.intake(root, trigger='sweep')['owner'] == ['PARTIAL']
    assert discovery.intake(root, trigger='seat-free')['owner'] == []
    events = [json.loads(line) for line in
              (root / '.wuwei/days/2026-09-29/events.jsonl').read_text().splitlines()]
    assert sum(row['kind'] == 'plan.proposed' for row in events) == 1


def test_plan_add_uses_rank_size_without_estimated_hours(root):
    row = candidate()
    del row['estimated_hours']
    save_candidate(root, row)
    assert plan.add('NEW', root)['action'] == 'build next'


def test_repeated_discovery_does_not_admit_twice(root, monkeypatch):
    monkeypatch.setattr(discovery, 'discover', lambda path: {
        'sources': {'tracker': 'measured: 1'}, 'candidates': [candidate()]})
    discovery.intake(root, trigger='sweep')
    discovery.intake(root, trigger='sweep')
    assert state.read_state(root)['approved_items'] == ['NEW']


def test_off_candidate_is_visible_in_next_morning_proposal(root, monkeypatch):
    (root / '.wuwei/config.toml').write_text('[discovery]\nautostart = "off"\n')
    save_candidate(root, candidate())
    assert plan.add('NEW', root)['action'] == 'tomorrow'
    monkeypatch.setenv('WUWEI_NOW', '2026-09-30T09:00:00+02:00')
    monkeypatch.setattr(discovery, 'discover', lambda path: {
        'sources': {'tracker': 'measured: 0'}, 'candidates': []})
    path = plan.propose({
        'goals': ['G-1'], 'cap': 2,
        'seat_policy': {'builder': {'runtime': 'claude', 'model': 'sonnet'}},
        'envelope': {'start': '09:00', 'end': '17:00', 'net_build_hours': 5},
        'sweep': {'manual': 'measured: none'}, 'candidates': [],
    }, root)
    assert 'NEW' in path.read_text()


def test_plan_add_cli_reports_build_request(root, monkeypatch, capsys):
    from wuwei.__main__ import main
    monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
    save_candidate(root, candidate())
    assert main(['plan', 'add', 'NEW']) == 0
    assert json.loads(capsys.readouterr().out)['action'] == 'build next'


def test_off_risk_flag_goes_to_owner_now(root):
    (root / '.wuwei/config.toml').write_text('[discovery]\nautostart = "off"\n')
    row = candidate()
    row['flags']['trust_surface'] = True
    save_candidate(root, row)
    assert plan.add('NEW', root)['action'] == 'owner'


def test_off_safe_full_waits_for_morning(root):
    (root / '.wuwei/config.toml').write_text('[discovery]\nautostart = "off"\n')
    save_candidate(root, candidate(track='FULL'))
    assert plan.add('NEW', root)['action'] == 'tomorrow'


def test_admitted_candidate_uses_build_next(root, monkeypatch):
    from wuwei.commands import build
    monkeypatch.setattr(discovery, 'discover', lambda path: {
        'sources': {'tracker': 'measured: 1'}, 'candidates': [candidate()]})
    calls = []
    monkeypatch.setattr(build, 'next_action',
                        lambda item, *, root: calls.append(item) or {'action': 'launch'})
    discovery.intake(root, trigger='seat-free')
    assert calls == ['NEW']


def test_strict_slice_below_approved_cut_goes_to_owner(root):
    (root / '.wuwei/config.toml').write_text('[discovery]\nautostart = "strict"\n')
    approved = candidate('CUT')
    approved['score']['value'] = 20
    path = root / '.wuwei/days/2026-09-29/proposal.json'
    data = json.loads(path.read_text())
    data['candidates'] = [approved]
    path.write_text(json.dumps(data))
    state._write_state(lambda day: day['approved_items'].append('CUT'), root,
                       reserved=False)
    save_candidate(root, candidate())
    assert plan.add('NEW', root)['action'] == 'owner'


def test_sweep_reports_intake_failure_as_unmeasured(root, monkeypatch, capsys):
    from wuwei import dispatch, watch
    monkeypatch.setattr(discovery, 'discover', lambda path: {
        'sources': {'tracker': 'measured: 1'}, 'candidates': []})
    monkeypatch.setattr(dispatch, 'discovery',
                        lambda *args: (_ for _ in ()).throw(ValueError('intake failed')))
    monkeypatch.setattr(watch, 'health', lambda path: (0, ''))
    assert watch.sweep(root) == 2
    assert 'intake failed' in capsys.readouterr().out


def test_plan_add_copies_candidate_tier(root):
    save_candidate(root, {**candidate(), 'tier': 'full'})
    assert plan.add('NEW', root)['action'] == 'build next'
    assert state.read_state(root)['items']['NEW']['tier'] == 'full'
