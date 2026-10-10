"""Intraday admission and discovery routing."""

import json
import pathlib

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


def test_plan_add_copies_governed_by(root):
    save_candidate(root, {**candidate(), 'governed_by': 'docs/prereg.md'})
    assert plan.add('NEW', root)['action'] == 'build next'
    assert state.read_state(root)['items']['NEW']['governed_by'] == 'docs/prereg.md'


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


def test_plan_add_needs_a_ticket(root, monkeypatch, capsys):
    from wuwei.__main__ import main
    (root / '.wuwei/config.toml').write_text(
        '[discovery]\nautostart = "goal"\n[adapters]\ntracker = "linear"\n')
    monkeypatch.setattr(discovery, 'discover', lambda path: {
        'sources': {}, 'candidates': [candidate(), {**candidate('ENG-5'), 'source': 'tracker'}]})
    result = discovery.intake(root, trigger='sweep')
    assert result['owner'] == ['NEW'] and result['started'] == ['ENG-5']
    day = state.read_state(root)
    assert "the planner proposes one on the item's card" in day['intraday_proposals']['NEW']['reason']
    assert day['tickets'] == {'ENG-5': {'id': 'ENG-5', 'source': 'tracker'}}
    save_candidate(root, candidate('OTHER'))
    monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
    assert main(['plan', 'add', 'OTHER']) == 1
    assert 'OTHER has no ticket' in capsys.readouterr().err
    save_candidate(root, {**candidate('LATER'), 'ticket': 'ENG-6'})
    assert plan.add('LATER', root)['action'] == 'build next'
    assert state.read_state(root)['tickets']['LATER'] == {'id': 'ENG-6', 'source': 'candidate'}


def test_plan_add_admits_owner_named_item_under_a_goal(root):
    result = plan.add('OWN-1', root, goal='G-1', size=2)
    day = state.read_state(root)
    assert result['action'] == 'build next'
    assert day['items']['OWN-1']['goal'] == 'G-1'
    assert day['items']['OWN-1']['budget_size'] == 2
    assert day['items']['OWN-1']['status'] == 'queued'
    assert 'OWN-1' in day['approved_items']


def test_plan_add_records_an_adopted_source(root):
    plan.add('PR-8', root, goal='G-1', title='Fix login', source='adopted')
    plan.add('OWN-1', root, goal='G-1')
    day = state.read_state(root)
    assert {key: day['items']['PR-8'][key] for key in ('source', 'title')} == {
        'source': 'adopted', 'title': 'Fix login'}
    assert 'source' not in day['items']['OWN-1'] and 'title' not in day['items']['OWN-1']
    events = [json.loads(line) for line in
              (root / '.wuwei/days/2026-09-29/events.jsonl').read_text().splitlines()]
    added = [e['payload'] for e in events if e['kind'] == 'plan.added']
    assert [(row['item'], row['source']) for row in added] == [('PR-8', 'adopted'), ('OWN-1', 'owner')]


def test_plan_add_unknown_item_without_goal_names_the_form(root):
    with pytest.raises(state.StateError, match='plan add OWN-2 --goal G-n'):
        plan.add('OWN-2', root)
    with pytest.raises(state.StateError, match="not one of today's goals"):
        plan.add('OWN-2', root, goal='G-9')
    assert 'OWN-2' not in state.read_state(root)['items']


def test_owner_named_item_needs_a_ticket_when_a_tracker_is_set(root):
    (root / '.wuwei/config.toml').write_text(
        '[discovery]\nautostart = "goal"\n[adapters]\ntracker = "linear"\n'
        '[security]\nposture = "strict"\n')
    with pytest.raises(state.StateError, match='OWN-3 has no ticket'):
        plan.add('OWN-3', root, goal='G-1')
    assert not state.read_state(root).get('drafts')
    assert plan.add('OWN-3', root, goal='G-1', ticket='ENG-7')['action'] == 'build next'
    assert state.read_state(root)['tickets']['OWN-3'] == {'id': 'ENG-7', 'source': 'candidate'}


GITHUB = '[discovery]\nautostart = "goal"\n[adapters]\ntracker = "github"\n[security]\nposture = "strict"\n'
REPO = '[[repos]]\nname = "{}"\npath = "{}"\ndefault_branch = "main"\n'


@pytest.mark.parametrize('settings,stored', [
    (REPO.format('acme/app', 'app'), 'acme/app#24'),
    ('[tracker]\nproject = "acme/tracker"\n' + REPO.format('acme/app', 'app'), 'acme/tracker#24'),
    (REPO.format('acme/app', 'app') + REPO.format('acme/lib', 'lib'), 'acme/app#24'),
])
def test_owner_named_bare_ticket_is_stored_in_full_and_claimed(root, monkeypatch, settings, stored):
    """#741: plan add --ticket 24 stores <repo>#24, and build next claims that id."""
    from fakes.tracker import Fake
    from wuwei import dispatch, registry
    (root / '.wuwei/config.toml').write_text(GITHUB + settings)
    fake = Fake({'claim': registry.Result(0, {})})
    load = registry.load
    monkeypatch.setattr(registry, 'load', lambda kind, config: fake if kind == 'tracker'
                        else load(kind, config))
    assert plan.add('OWN-3', root, goal='G-1', ticket='24')['action'] == 'build next'
    assert state.read_state(root)['tickets']['OWN-3'] == {'id': stored, 'source': 'candidate'}
    assert dispatch.tracker_call('OWN-3', 'claim', root).exit == 0
    assert fake.calls[-1][:2] == ('claim', (stored,))
    lines = (root / '.wuwei/days/2026-09-29/events.jsonl').read_text().splitlines()
    call, = [row for row in map(json.loads, lines) if row['kind'] == 'tracker.call']
    assert call['payload']['ticket'] == stored


def test_owner_named_bare_ticket_without_a_repository_is_refused(root, monkeypatch):
    from wuwei.__main__ import main
    (root / '.wuwei/config.toml').write_text(GITHUB)
    with pytest.raises(ValueError, match='owner/repo#24'):
        plan.add('OWN-4', root, goal='G-1', ticket='24')
    day = state.read_state(root)
    assert 'OWN-4' not in day['items'] and 'OWN-4' not in day.get('tickets', {})
    assert 'OWN-4' not in day.get('intraday_proposals', {}) and not day.get('drafts')
    assert 'OWN-4' not in (root / '.wuwei/days/2026-09-29/events.jsonl').read_text()
    monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
    monkeypatch.chdir(root)
    assert main(['plan', 'add', 'OWN-4', '--goal', 'G-1', '--ticket', '24']) == 2


def test_owner_named_item_gets_a_ticket_draft_for_its_card(root, monkeypatch):
    """#636: below strict plan add drafts the owner item's ticket; its Send card opens it."""
    from fakes.tracker import Fake, ported
    from wuwei import drafts, registry
    (root / '.wuwei/config.toml').write_text(
        '[owner]\nname = "Pat Example"\n[discovery]\nautostart = "goal"\n'
        '[adapters]\ntracker = "linear"\n')
    fake = Fake({'create': registry.Result(0, {'id': 'ENG-9', 'url': 'https://example.test/ENG-9'})})
    port = ported(fake)
    load = registry.load
    monkeypatch.setattr(registry, 'load', lambda kind, config: port if kind == 'tracker'
                        else load(kind, config))
    with pytest.raises(state.StateError) as refused:
        plan.add('OWN-3', root, goal='G-1', title='Fix the export')
    assert 'drafts show draft-' in str(refused.value) and 'host terminal' not in str(refused.value)
    day = state.read_state(root)
    (key, row), = day['drafts'].items()
    assert row['status'] == 'pending' and row['inputs']['draft']['title'] == 'Fix the export'
    assert row['inputs']['draft']['item'] == 'OWN-3'
    assert fake.calls == [] and 'OWN-3' not in day['items']
    assert drafts.approve(root, key).exit == 0
    assert plan.add('OWN-3', root, goal='G-1', title='Fix the export')['action'] == 'build next'
    day = state.read_state(root)
    assert day['tickets']['OWN-3']['source'] == 'create' and len(day['drafts']) == 1


def test_plan_skill_and_charter_say_how_an_item_joins_an_approved_plan():
    top = pathlib.Path(__file__).resolve().parents[1]
    for path in ('skills/wuwei-plan/SKILL.md', 'agents/planner.md', 'docs/site/daily.md'):
        assert 'wuwei plan add <item> --goal G-n' in (top / path).read_text(encoding='utf-8'), path


def added_events(root):
    return [e['payload'] for e in map(json.loads, (root / '.wuwei/days/2026-09-29/events.jsonl')
                                      .read_text().splitlines()) if e['kind'] == 'plan.added']


def test_plan_add_records_the_risk_flags_merge_check_reads(root):
    # #615: plan.added carries flags in the plan.approved shape, so merge check finds evidence.
    save_candidate(root, candidate())
    plan.add('NEW', root)
    plan.add('OWN-1', root, goal='G-1')
    flags = {key: False for key in plan.FLAGS}
    assert [row['flags'] for row in added_events(root)] == [{'NEW': flags}, {'OWN-1': flags}]


def test_plan_add_backfills_missing_risk_evidence_once(root):
    # #615: an item admitted before the fix recovers with the command merge check names.
    flags = {key: False for key in plan.FLAGS}
    state._write_state(lambda d: d['items'].update({'OLD': {'goal': 'G-1', 'flags': flags}})
                       or d['approved_items'].append('OLD'), root, reserved=False,
                       kind='plan.added', payload={'item': 'OLD', 'source': 'owner'})
    assert plan.add('OLD', root) == {'action': 'risk recorded', 'item': 'OLD'}
    assert added_events(root)[-1] == {'item': 'OLD', 'source': 'replan', 'flags': {'OLD': flags}}
    with pytest.raises(state.StateError, match='already in the plan'):
        plan.add('OLD', root)
    assert len(added_events(root)) == 2


def test_plan_add_from_a_seat_finding(root, monkeypatch, capsys):
    """#646: a seat's finding joins as a small item with no ticket, even with a tracker required."""
    from fakes.tracker import Fake, ported
    from wuwei import registry, tracker, workspace
    from wuwei.__main__ import main
    (root / '.wuwei/config.toml').write_text(
        '[discovery]\nautostart = "goal"\n[adapters]\ntracker = "linear"\n')
    fake = Fake({'create': registry.Result(0, {'id': 'ENG-9'})})
    port = ported(fake)
    load = registry.load
    monkeypatch.setattr(registry, 'load', lambda kind, config: port if kind == 'tracker'
                        else load(kind, config))
    monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
    assert main(['plan', 'add', '--from-finding', 'fix-pin-ruff-in-ci']) == 1
    assert 'wuwei next' in capsys.readouterr().err
    assert main(['note', '--fix', 'Pin ruff in CI']) == 0
    capsys.readouterr()
    with pytest.raises(state.StateError, match="not one of today's goals"):
        plan.add('fix-pin-ruff-in-ci', root, goal='G-9', source='finding')
    assert main(['plan', 'add', 'fix-pin-ruff-in-ci', '--from-finding']) == 0
    assert json.loads(capsys.readouterr().out) == {'action': 'build next', 'item': 'fix-pin-ruff-in-ci'}
    day = state.read_state(root)
    row = day['items']['fix-pin-ruff-in-ci']
    assert {key: row[key] for key in ('goal', 'track', 'tier', 'source', 'title', 'budget_size')} == {
        'goal': 'G-1', 'track': 'SLICE', 'tier': 'light', 'source': 'finding',
        'title': 'Pin ruff in CI', 'budget_size': 1}
    assert not any(row['flags'].values()) and 'fix-pin-ruff-in-ci' in day['approved_items']
    assert fake.calls == [] and not day.get('drafts') and not day.get('tickets')
    assert added_events(root)[-1]['source'] == 'finding'
    config = workspace.load_config(root)
    assert tracker.check(day, config, 'fix-pin-ruff-in-ci', row) == ('later', '')

