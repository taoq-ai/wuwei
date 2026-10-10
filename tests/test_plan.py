"""Morning proposal and approval contract."""

import json
from pathlib import Path

import pytest

from wuwei import discovery, plan, registry, state, workspace


@pytest.fixture
def root(tmp_path, monkeypatch):
    base = tmp_path / '.wuwei'
    (base / 'memory').mkdir(parents=True)
    (base / 'memory/goals.md').write_text('# Goals\n## G-1\noutcome: Ship a useful result\nmeasure: shipped\ntarget: 1\ndate: 2026-10-30\npriority: 1\n')
    (base / 'config.toml').write_text('')
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T09:00:00+02:00')
    return tmp_path


@pytest.fixture(autouse=True)
def host(monkeypatch):
    # #528: CAP derives from the host; pin it (8 GiB free, 4 cores) on every machine.
    import os
    from wuwei.guards import agent_launch
    monkeypatch.setattr(agent_launch, 'free_memory', lambda config, root: 8 * 1024**3)
    monkeypatch.setattr(os, 'cpu_count', lambda: 4)


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


def test_propose_keeps_derives_and_names_the_repository(root):
    # #603: with two repositories each candidate carries repo, derived from paths when unique.
    def configure(*names):
        (root / '.wuwei/config.toml').write_text(''.join(
            f'[[repos]]\nname = "acme/{name}"\npath = "{name}"\ndefault_branch = "main"\n' for name in names))
    configure('code', 'paper')
    (root / 'code/src').mkdir(parents=True)
    (root / 'code/src/a.py').write_text('')
    (root / 'paper').mkdir()
    base = proposal()['candidates'][0]
    rows = lambda: [{**base, 'id': 'K', 'repo': 'acme/paper'}, {**base, 'id': 'D', 'paths': ['src/a.py']},
                    {**base, 'id': 'N', 'paths': ['src/b.py']}, {**base, 'id': 'U', 'repo': 'acme/none'}]
    text = plan.propose({**proposal(), 'candidates': rows()}, root).read_text()
    saved = json.loads((root / '.wuwei/days/2026-09-28/proposal.json').read_text())['candidates']
    assert {row['id']: row.get('repo') for row in saved} == {
        'K': 'acme/paper', 'D': 'acme/code', 'N': None, 'U': None}
    assert 'Repository: acme/paper' in text and 'Repository: acme/code' in text
    assert text.count('Repository: not named') == 2 and 'acme/code, acme/paper' in text
    configure('code')
    text = plan.propose({**proposal(), 'candidates': rows()}, root).read_text()
    assert 'Repository:' not in text
    saved = json.loads((root / '.wuwei/days/2026-09-28/proposal.json').read_text())['candidates']
    assert [row['repo'] for row in saved if 'repo' in row] == ['acme/paper', 'acme/none']


def test_approve_selected_items_and_reserve_gate_fields(root):
    plan.propose(proposal(), root)
    plan.approve(['A'], root, goals_confirmed=True)
    data = state.read_state(root)
    assert data['gate_approved'] is True
    assert data['approved_items'] == ['A']
    assert data['goals'] == ['G-1']
    assert (data['cap'], data['cap_bound']) == (4, 'host.seats')  # derived; the lead's 2 is not used
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
    result = subprocess.run([*command, 'gate'], env=env, capture_output=True, text=True)
    assert json.loads(result.stdout)[0]['record'] == 'wuwei plan approve --items A --goals-confirmed --pace "<label>"'
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


def test_candidate_tier_is_optional_validated_and_copied(root):
    bad = proposal()
    bad['candidates'][0]['tier'] = 'medium'
    with pytest.raises(ValueError, match='tier must be light, standard or full'):
        plan.propose(bad, root)
    plan.propose(proposal(), root)
    plan.approve(['A'], root, goals_confirmed=True)
    assert 'tier' not in state.read_state(root)['items']['A']


def test_candidate_tier_is_copied_at_approve(root):
    good = proposal()
    good['candidates'][0]['tier'] = 'full'
    plan.propose(good, root)
    plan.approve(['A'], root, goals_confirmed=True)
    assert state.read_state(root)['items']['A']['tier'] == 'full'


def test_candidate_governed_by_is_checked(root):
    plan.propose(proposal(), root)
    plan.approve(['A'], root, goals_confirmed=True)
    assert 'governed_by' not in state.read_state(root)['items']['A']
    for bad in ('', 3):
        wrong = proposal()
        wrong['candidates'][0]['governed_by'] = bad
        with pytest.raises(ValueError, match='governed_by must be'):
            plan.propose(wrong, root)


def test_candidate_governed_by_is_copied_at_approve(root):
    good = proposal()
    good['candidates'][0]['governed_by'] = 'docs/prereg.md#Pre-registration'
    plan.propose(good, root)
    plan.approve(['A'], root, goals_confirmed=True)
    assert state.read_state(root)['items']['A']['governed_by'] == 'docs/prereg.md#Pre-registration'


SCANNER_CONFIG = '[adapters]\nscanner = "ziran"\n[[repos]]\nname = "acme/widget"\npath = "widget"\ndefault_branch = "main"\n'
REPORT = (Path(__file__).parent / 'fixtures/scanner/audit.json').read_text()


def fake_ziran(monkeypatch, code, stdout, version='0.39.0'):
    import subprocess
    from types import SimpleNamespace

    def run(argv, **kwargs):
        if argv == ['ziran', '--version']:
            return SimpleNamespace(returncode=0, stdout=f'ziran, version {version}', stderr='')
        assert argv[:2] == ['ziran', 'audit'] and argv[3:] == ['--format', 'json', '--severity', 'low']
        return SimpleNamespace(returncode=code, stdout=stdout, stderr='')

    monkeypatch.setattr(subprocess, 'run', run)


def propose_with_scanner(root, monkeypatch):
    from wuwei.__main__ import main

    (root / '.wuwei/config.toml').write_text(SCANNER_CONFIG)
    (root / 'widget').mkdir()
    monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
    source = root / 'lead.json'
    source.write_text(json.dumps(proposal()))
    assert main(['plan', 'propose', str(source)]) == 0
    day = root / '.wuwei/days/2026-09-28'
    return json.loads((day / 'proposal.json').read_text())['sweep']['discovery.scanner'], (day / 'plan.md').read_text()


@pytest.mark.parametrize('findings,code,count', [(True, 1, 'measured: 1'), (False, 0, 'measured: 0')])
def test_plan_propose_lists_scanner_findings(root, monkeypatch, findings, code, count):
    report = json.loads(REPORT)
    if not findings:
        report['findings'] = []
    fake_ziran(monkeypatch, code, json.dumps(report))
    measured, text = propose_with_scanner(root, monkeypatch)
    assert measured == count
    if findings:
        assert ('- acme/widget:scanner:SA003:vulnerable.py:5: high SA003 vulnerable.py:5: '
                'Untrusted input reaches eval') in text


@pytest.mark.parametrize('version,code,stdout', [('0.38.9', 1, REPORT), ('0.39.0', 3, REPORT),
                                                 ('0.39.0', 1, 'not json')])
def test_plan_propose_with_unrunnable_scanner(root, monkeypatch, version, code, stdout):
    fake_ziran(monkeypatch, code, stdout, version)
    measured, _ = propose_with_scanner(root, monkeypatch)
    assert measured.startswith('unmeasured: acme/widget: ziran audit: unmeasured')


@pytest.mark.parametrize('result', [registry.Result(0, []), registry.Result(1, {'files_analyzed': 1}),
                                    registry.Result(0, {'files_analyzed': 1, 'findings': ['x']}),
                                    registry.Result(5, None), None])
def test_discover_marks_out_of_contract_scanner_unmeasured(root, result):
    from types import SimpleNamespace

    (root / '.wuwei/config.toml').write_text(SCANNER_CONFIG)
    (root / 'widget').mkdir()
    found = discovery.discover(root, ports={'scanner': SimpleNamespace(audit=lambda path, root=None: result)})
    assert found['sources']['scanner'] == 'unmeasured: acme/widget: invalid scanner result'
    assert not [row for row in found['candidates'] if row['source'] == 'scanner']
TEMPLATE = Path(__file__).resolve().parents[1] / 'templates/workspace/memory/goals.md'
LEAD_GOALS = [
    {'id': 'G-1', 'outcome': 'Ship the widget', 'measure': 'widgets shipped', 'target': '1',
     'date': '2026-10-30', 'priority': 1},
    {'id': 'G-2', 'outcome': 'Document the widget', 'measure': 'widgets shipped',
     'target': '1', 'date': '2026-10-30', 'priority': 2},
]


@pytest.fixture
def empty(root):
    (root / '.wuwei/memory/goals.md').write_text(TEMPLATE.read_text(encoding='utf-8'))
    return root


def lead():
    return {**proposal(), 'goals': LEAD_GOALS}


def test_propose_runs_on_provisional_goals(empty):
    from wuwei import goals

    before = (empty / '.wuwei/memory/goals.md').read_text()
    text = plan.propose(lead(), empty).read_text()
    assert 'G-1 (provisional)' in text and 'G-2 (provisional)' in text
    assert 'Ship the widget' in text
    day = empty / '.wuwei/days/2026-09-28'
    assert list(goals.parse((day / 'goals.md').read_text())) == ['G-1', 'G-2']
    assert json.loads((day / 'proposal.json').read_text())['goals'] == ['G-1', 'G-2']
    assert (empty / '.wuwei/memory/goals.md').read_text() == before


def test_propose_refuses_ids_only_goals(empty):
    with pytest.raises(ValueError, match='the lead JSON names G-1 without its block'):
        plan.propose({**proposal(), 'goals': ['G-1']}, empty)
    assert not (empty / '.wuwei/days/2026-09-28/plan.md').exists()


def test_propose_refuses_goal_objects_once_goals_exist(root):
    with pytest.raises(ValueError, match='goals must cite identifiers'):
        plan.propose(lead(), root)


def test_repropose_on_confirmed_goals_removes_draft(empty):
    plan.propose(lead(), empty)
    (empty / '.wuwei/memory/goals.md').write_text(
        (empty / '.wuwei/days/2026-09-28/goals.md').read_text())
    plan.propose({**proposal(), 'goals': ['G-1', 'G-2']}, empty)
    assert not (empty / '.wuwei/days/2026-09-28/goals.md').exists()


def test_approve_reads_the_proposed_goals(empty):
    # #603: the gate-confirmed draft approves; memory stays written only by goals edit.
    plan.propose(lead(), empty)
    before = (empty / '.wuwei/memory/goals.md').read_bytes()
    plan.approve(['A'], empty, goals_confirmed=True)
    assert state.read_state(empty)['goals'] == ['G-1', 'G-2']
    assert (empty / '.wuwei/memory/goals.md').read_bytes() == before


def test_approve_without_goals_or_draft_fails(empty):
    plan.propose(lead(), empty)
    (empty / '.wuwei/days/2026-09-28/goals.md').unlink()
    with pytest.raises(ValueError, match='no goals'):
        plan.approve(['A'], empty, goals_confirmed=True)


def test_cli_propose_on_provisional_goals(empty):
    import os
    import subprocess
    import sys

    source = empty / 'lead.json'
    source.write_text(json.dumps(lead()))
    env = {**os.environ, 'WUWEI_WORKSPACE': str(empty),
           'PYTHONPATH': str(Path(__file__).resolve().parents[1] / 'cli')}
    result = subprocess.run([sys.executable, '-P', '-m', 'wuwei', 'plan', 'propose', str(source)],
                            env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_template_proposes_goal_on_empty_goals(empty):
    import os
    import subprocess
    import sys

    env = {**os.environ, 'WUWEI_WORKSPACE': str(empty),
           'PYTHONPATH': str(Path(__file__).resolve().parents[1] / 'cli')}
    command = [sys.executable, '-P', '-m', 'wuwei', 'plan']
    result = subprocess.run([*command, 'template'], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert isinstance(json.loads(result.stdout)['goals'][0], dict)
    result = subprocess.run([*command, 'propose', '-'], env=env, input=result.stdout,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_propose_sweep_has_pr_flow(root):
    shepherd = '[shepherd]\nlead_login = "ada"\n\n[shepherd.authors]\n"ada@example.com" = {login = "ada"}\n'
    (root / '.wuwei/config.toml').write_text(shepherd)
    text = plan.propose(proposal(), root).read_text()
    assert '- pr-flow: measured: 1 warn (owner.handles); wuwei doctor --section pr-flow\n' in text
    (root / '.wuwei/config.toml').write_text('[owner]\nhandles = ["ada"]\n\n' + shepherd)
    (root / '.wuwei/days/2026-09-28/plan.md').unlink()
    assert '- pr-flow: measured: ok\n' in plan.propose(proposal(), root).read_text()


def test_owner_open_prs_are_proposed_and_claimed_at_the_gate(root, monkeypatch):
    # #510: the sweep lists the owner's open PRs; approving the gate claims them.
    from fakes.code_host import Fake
    from wuwei import shepherd
    (root / '.wuwei/config.toml').write_text(
        '[owner]\nhandles = ["U1", "Builder"]\n[[repos]]\nname = "acme/widget"\npath = "."\ndefault_branch = "main"\n')
    host = Fake()
    load = registry.load
    monkeypatch.setattr(registry, 'load', lambda kind, config: host if kind == 'code_host' else load(kind, config))
    text = plan.propose(proposal(), root).read_text()
    assert ('open_prs', ('acme/widget',), root) in host.calls
    assert '- open-prs: measured: 1 open PR by the owner\n' in text
    assert '## Open PRs to claim\n- PR-12: acme/widget#12 Add a cache (claimed under G-1)\n' in text
    assert 'PR-13' not in text
    widget = plan.gate_widget(root)
    assert widget['record'] == 'wuwei plan approve --items A PR-12 --goals-confirmed --pace "<label>"'
    assert 'Claims PR-12 (acme/widget#12)' in widget['options'][0]['description']
    claimed = []
    monkeypatch.setattr(shepherd, 'claim_pr', lambda *args: claimed.append(args) or 0)
    plan.approve(['A', 'PR-12'], root, goals_confirmed=True)
    assert state.read_state(root)['approved_items'] == ['A']
    assert claimed == [(root, 'acme/widget#12', 'PR-12', 'G-1')]
    host.results['open_prs'] = registry.Result(2, None, 'github.open_prs: could not run')
    from wuwei import workspace
    assert plan._owner_prs(workspace.load_config(root), root, []) == (
        [], 'unmeasured: github.open_prs: could not run')


def test_one_pr_number_in_two_repositories_gives_two_ids(root, monkeypatch):
    # #603 review: with two repositories the claim id names the repository, so approve takes both.
    from fakes.code_host import Fake
    from wuwei import shepherd
    (root / '.wuwei/config.toml').write_text('[owner]\nhandles = ["Builder"]\n' + ''.join(
        f'[[repos]]\nname = "acme/{name}"\npath = "{name}"\ndefault_branch = "main"\n' for name in ('widget', 'paper')))
    host = Fake()
    load = registry.load
    monkeypatch.setattr(registry, 'load', lambda kind, config: host if kind == 'code_host' else load(kind, config))
    plan.propose(proposal(), root)
    widget = plan.gate_widget(root)
    assert widget['record'] == ('wuwei plan approve --items A PR-widget-12 PR-paper-12 --goals-confirmed '
                                '--pace "<label>"')
    claimed = []
    monkeypatch.setattr(shepherd, 'claim_pr', lambda *args: claimed.append(args) or 0)
    plan.approve(['A', 'PR-widget-12', 'PR-paper-12'], root, goals_confirmed=True)
    assert [args[1:3] for args in claimed] == [('acme/widget#12', 'PR-widget-12'), ('acme/paper#12', 'PR-paper-12')]


def test_gate_widget_is_the_one_approval_question(root):
    # #365: the CLI prints the one gate question, its header and the approve command.
    from wuwei.guards.decision import gate_question

    data = proposal()
    data['candidates'].append({**data['candidates'][0], 'id': 'B'})
    plan.propose(data, root)
    widget = plan.gate_widget(root)
    assert widget['question'] == ("Morning gate (days/2026-09-28/plan.md): "
                                  "Approve today's plan as proposed?")
    assert gate_question(widget, root)
    assert widget['header'] == 'Plan'
    assert [row['label'] for row in widget['options']] == [
        'Approve', 'Approve at careful', 'Approve at fast', 'Change something']  # #579: pace rows
    approve = widget['options'][0]['description']
    assert all(part in approve for part in ('G-1', 'A, B', 'CAP 4', 'claude', '09:00',
                                            'Cap 4 (host.seats): subagent runtime, free memory not read'))
    assert 'carry' not in approve.lower()
    assert widget['record'] == 'wuwei plan approve --items A B --goals-confirmed --pace "<label>"'
    carry = plan.gate_widget(root, import_yesterday=True)
    assert 'carry-over' in carry['options'][0]['description'].lower()
    assert carry['record'].endswith(' --goals-confirmed --import-yesterday --pace "<label>"')
    (root / '.wuwei/memory/goals.md').write_text(TEMPLATE.read_text(encoding='utf-8'))
    plan.propose(lead(), root)
    assert plan.gate_widget(root)['header'] == 'Goals'


def test_plan_set_spec_override(root, capsys, monkeypatch):
    from wuwei.__main__ import main
    monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
    state._write_state(lambda data: data['items'].update(A={'phase': 'planned', 'status': 'queued'}),
                       root, reserved=False)
    events = root / '.wuwei/days/2026-09-28/events.jsonl'

    def overrides():
        return [{key: json.loads(line)['payload'][key] for key in ('item', 'value', 'reason')}
                for line in events.read_text().splitlines() if json.loads(line)['kind'] == 'spec.override']
    assert main(['plan', 'set', 'A', 'spec=skipped']) == 2
    assert 'reason' in capsys.readouterr().err
    assert main(['plan', 'set', 'A', 'spec=maybe']) == 2
    assert main(['plan', 'set', 'A', 'tier=light']) == 2
    assert main(['plan', 'set', 'Z', 'spec=required']) == 1
    assert 'spec' not in state.read_state(root)['items']['A']
    assert main(['plan', 'set', 'A', 'spec=skipped', '--reason', 'typo\nfix']) == 0
    assert 'A: spec skipped' in capsys.readouterr().out
    assert state.read_state(root)['items']['A']['spec'] == {'value': 'skipped', 'reason': 'typo fix'}
    assert main(['plan', 'set', 'A', 'spec=required']) == 0
    assert state.read_state(root)['items']['A']['spec'] == {'value': 'required', 'reason': ''}
    assert overrides() == [{'item': 'A', 'value': 'skipped', 'reason': 'typo fix'},
                           {'item': 'A', 'value': 'required', 'reason': ''}]
    with pytest.raises(state.StateError, match='wuwei plan set'):
        state.set_state('items.A.spec', '{"value": "skipped"}', root)
    assert main(['event', 'spec.override', '{}']) == 1
    assert 'wuwei plan set' in capsys.readouterr().err



def test_plan_set_owner_merge(root, capsys, monkeypatch):
    # #678: the owner keeps an item's merge; the record says who set it and when.
    from wuwei.__main__ import main
    monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
    monkeypatch.delenv('WUWEI_SESSION_ID', raising=False)
    monkeypatch.delenv('WUWEI_SEAT_ROLE', raising=False)
    state._write_state(lambda data: data['items'].update(A={'phase': 'planned', 'status': 'queued'}),
                       root, reserved=False)
    assert main(['plan', 'set', 'A', 'owner_merge=maybe']) == 2
    assert 'owner_merge=true|false' in capsys.readouterr().err
    assert main(['plan', 'set', 'Z', 'owner_merge=true']) == 1
    assert 'owner_merge' not in state.read_state(root)['items']['A']
    assert main(['plan', 'set', 'A', 'owner_merge=true']) == 0
    assert 'A: owner_merge true' in capsys.readouterr().out
    at = '2026-09-28T09:00:00+02:00'
    assert state.read_state(root)['items']['A']['owner_merge'] == {'value': True, 'by': 'owner', 'at': at}
    monkeypatch.setenv('WUWEI_SESSION_ID', 'planner-1')
    assert main(['plan', 'set', 'A', 'owner_merge=false']) == 0
    assert state.read_state(root)['items']['A']['owner_merge'] == {'value': False, 'by': 'planner', 'at': at}
    monkeypatch.setenv('WUWEI_SEAT_ROLE', 'builder')
    assert main(['plan', 'set', 'A', 'owner_merge=true']) == 0
    assert state.read_state(root)['items']['A']['owner_merge']['by'] == 'builder'
    assert [e['payload'] for e in events(root) if e['kind'] == 'plan.set'] == [
        {'item': 'A', 'owner_merge': value, 'by': by, 'prs_seen': False}
        for value, by in ((True, 'owner'), (False, 'planner'), (True, 'builder'))]
    with pytest.raises(state.StateError, match='reserved; written by wuwei plan set'):
        state.set_state('items.A.owner_merge', '{"value": false}', root)


def test_gate_card_names_the_owner_merge_route(root):
    plan.propose(proposal(), root)
    change = plan.gate_widget(root)['options'][-1]
    assert change['label'] == 'Change something'
    assert 'wuwei plan set <item> owner_merge=true' in change['description']

def two(**extra):
    data = proposal()
    data['candidates'].append({**data['candidates'][0], 'id': 'B'})
    for candidate in data['candidates']:
        candidate.update(extra.get(candidate['id'], {}))
    return data


def tracked(root, settings=''):
    (root / '.wuwei/config.toml').write_text('[adapters]\ntracker = "linear"\n' + settings)


def events(root):
    return [json.loads(line) for line in
            (root / '.wuwei/days/2026-09-28/events.jsonl').read_text().splitlines()]


def test_approve_refuses_every_candidate_without_a_ticket(root, monkeypatch, capsys):
    from wuwei.__main__ import main
    plan.propose(two(), root)
    tracked(root, '[security]\nposture = "strict"\n')  # #636: below strict Approve opens them
    monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
    assert main(['plan', 'approve', '--items', 'A', 'B', '--goals-confirmed']) == 1
    err = capsys.readouterr().err
    assert 'A has no ticket' in err and 'B has no ticket' in err
    assert not state.read_state(root)['approved_items']


def test_approve_records_candidate_and_tracker_tickets(root):
    data = two(A={'ticket': 'ENG-3'})
    plan.propose(data, root)
    path = root / '.wuwei/days/2026-09-28/proposal.json'
    stored = json.loads(path.read_text())
    stored['discovered'] = [{'id': 'B', 'title': 'x', 'source': 'tracker'}]
    path.write_text(json.dumps(stored))
    tracked(root)
    plan.approve(['A', 'B'], root, goals_confirmed=True)
    assert state.read_state(root)['tickets'] == {
        'A': {'id': 'ENG-3', 'source': 'candidate'}, 'B': {'id': 'B', 'source': 'tracker'}}


def test_invalid_candidate_ticket_is_unrun(root):
    with pytest.raises(ValueError, match='A: invalid ticket'):
        plan.propose(two(A={'ticket': 'has space'}), root)


def three(**extra):
    data = two(**extra)
    data['candidates'].append({**proposal()['candidates'][0], 'id': 'C',
                               'scope': 'Add the export\n  button', **extra.get('C', {})})
    return data


def ticket_lines(root):
    return [line for line in (root / '.wuwei/days/2026-09-28/plan.md').read_text().splitlines()
            if line.startswith('Ticket:')]


def test_plan_and_gate_card_show_each_ticket(root):
    """#636: the plan and the Approve description name an existing ticket or a new one."""
    tracked(root)
    plan.propose(three(A={'ticket': 'ENG-1'}, B={'ticket': 'ENG-2'}), root)
    assert ticket_lines(root) == ['Ticket: ENG-1 (existing)', 'Ticket: ENG-2 (existing)',
                                  'Ticket: new Add the export button']
    widget = plan.gate_widget(root)
    assert ('Tickets A ENG-1 (existing), B ENG-2 (existing), C new Add the export button'
            in widget['options'][0]['description'])
    assert 'tickets' in widget['options'][-1]['description']
    plan.propose(three(A={'ticket': None}), root)
    assert ticket_lines(root)[0] == 'Ticket: none'
    tracked(root, '[tracker]\nskip_tiers = ["light"]\n')
    plan.propose(three(A={'tier': 'light'}), root)
    assert len(ticket_lines(root)) == 2
    (root / '.wuwei/config.toml').write_text('')
    plan.propose(three(), root)
    assert ticket_lines(root) == []
    assert 'Tickets' not in plan.gate_widget(root)['options'][0]['description']


def opening(root, monkeypatch, posture, created=None, **extra):
    """#636: A and B link existing tickets, C gets a new one; the fake tracker opens it."""
    from fakes.tracker import Fake, ported
    tracked(root, f'[owner]\nname = "Pat Example"\n[security]\nposture = "{posture}"\n')
    plan.propose(three(**{'A': {'ticket': 'ENG-1'}, 'B': {'ticket': 'ENG-2'}, **extra}), root)
    fake = Fake({'create': created or registry.Result(0, {'id': 'ENG-9',
                                                           'url': 'https://example.test/ENG-9'})})
    port = ported(fake)
    load = registry.load
    monkeypatch.setattr(registry, 'load', lambda kind, config: port if kind == 'tracker'
                        else load(kind, config))
    return fake


@pytest.mark.parametrize('posture', ['observe', 'guarded'])
def test_approve_links_and_opens_the_proposed_tickets(root, monkeypatch, posture):
    """#636 acceptance 1: two links and one new ticket, no terminal command."""
    from wuwei import tracker
    fake = opening(root, monkeypatch, posture)
    plan.approve(['A', 'B', 'C'], root, goals_confirmed=True)
    day = state.read_state(root)
    assert day['tickets'] == {'A': {'id': 'ENG-1', 'source': 'candidate'},
                              'B': {'id': 'ENG-2', 'source': 'candidate'},
                              'C': {'id': 'ENG-9', 'source': 'create'}}
    assert [call[0] for call in fake.calls] == ['create']
    assert fake.calls[0][1][0]['item'] == 'C'
    assert [row['status'] for row in day.get('drafts', {}).values()] in ([], ['sent'])
    config = workspace.load_config(root)
    assert all(tracker.check(day, config, name)[0] == 'ticket' for name in 'ABC')
    with pytest.raises(state.StateError, match='already approved'):
        plan.approve(['A', 'B', 'C'], root, goals_confirmed=True)
    assert len(fake.calls) == 1


def test_strict_approve_prints_the_commands(root, monkeypatch, capsys):
    """#636 acceptance 2: under strict nothing is opened and the commands are printed."""
    from wuwei.__main__ import main
    fake = opening(root, monkeypatch, 'strict')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
    assert main(['plan', 'approve', '--items', 'A', 'B', 'C', '--goals-confirmed']) == 1
    err = capsys.readouterr().err
    assert 'bin/wuwei tracker create C' in err and 'host terminal' in err
    assert fake.calls == []
    day = state.read_state(root)
    assert not day.get('drafts') and not day['approved_items']


def test_owners_none_is_approved_without_a_ticket(root, monkeypatch):
    fake = opening(root, monkeypatch, 'guarded', A={'ticket': None}, C={'ticket': 'ENG-3'})
    plan.approve(['A'], root, goals_confirmed=True)
    assert fake.calls == []
    assert state.read_state(root)['tickets'] == {'A': {'id': None, 'source': 'none'}}
    skipped = [event['payload'] for event in events(root) if event['kind'] == 'tracker.skipped']
    assert skipped == [{'item': 'A', 'ticket': 'none'}]


def test_a_failed_open_refuses_the_approval(root, monkeypatch):
    opening(root, monkeypatch, 'guarded', created=registry.Result(2, reason='linear: unreachable'))
    with pytest.raises(state.StateError, match='C: drafts: adapter did not confirm send'):
        plan.approve(['A', 'B', 'C'], root, goals_confirmed=True)
    assert not state.read_state(root)['approved_items']


def test_import_yesterday_carries_tickets(root):
    yesterday = root / '.wuwei/days/2026-09-27'
    yesterday.mkdir(parents=True)
    (yesterday / 'state.json').write_text(json.dumps({
        'items': {'OLD': {'phase': 'implement', 'status': 'running'}},
        'tickets': {'OLD': {'id': 'ENG-1', 'source': 'create'}}}))
    data = proposal()
    data['candidates'][0]['ticket'] = 'ENG-2'
    plan.propose(data, root)
    tracked(root)
    plan.approve(['A'], root, goals_confirmed=True, import_yesterday=True)
    assert state.read_state(root)['tickets'] == {
        'OLD': {'id': 'ENG-1', 'source': 'yesterday'}, 'A': {'id': 'ENG-2', 'source': 'candidate'}}


def test_light_candidate_is_approved_without_a_ticket(root):
    plan.propose(two(A={'tier': 'light'}, B={'ticket': 'ENG-4'}), root)
    tracked(root, '[tracker]\nskip_tiers = ["light"]\n')
    plan.approve(['A', 'B'], root, goals_confirmed=True)
    assert state.read_state(root)['tickets'] == {'B': {'id': 'ENG-4', 'source': 'candidate'}}
    skipped = [event['payload'] for event in events(root) if event['kind'] == 'tracker.skipped']
    assert skipped == [{'item': 'A', 'tier': 'light'}]


def test_plan_set_records_a_confirmed_ticket(root, monkeypatch, capsys):
    from fakes.tracker import Fake
    from wuwei.__main__ import main
    plan.propose(proposal(), root)
    tracked(root)
    monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
    fake = Fake({'created': registry.Result(2, reason='LINEAR_API_KEY is missing')})
    monkeypatch.setattr(registry, 'load', lambda kind, config: fake)
    assert main(['plan', 'set', 'A', 'ticket=ENG-4']) == 2
    assert 'tickets' not in state.read_state(root)
    fake.results['created'] = registry.Result(0, '2026-09-27T10:00:00Z')
    assert main(['plan', 'set', 'A', 'ticket=ENG-4']) == 0
    assert fake.calls[-1][:2] == ('created', ('ENG-4',))
    assert state.read_state(root)['tickets'] == {'A': {'id': 'ENG-4', 'source': 'set'}}
    assert [e['payload']['item'] for e in events(root) if e['kind'] == 'plan.set'] == ['A']
    assert main(['plan', 'set', 'UNKNOWN', 'ticket=ENG-4']) == 1
    assert main(['plan', 'set', 'A', 'owner=pat']) == 2
    assert main(['plan', 'set', 'A', 'ticket=bad id']) == 2
    fake.results['created'] = registry.Result(1, reason='not found')
    assert main(['plan', 'set', 'A', 'ticket=ENG-5']) == 1
    assert 'owner=pat is not a spec, docs, ticket or owner_merge value' in capsys.readouterr().err


def four(seats=None):
    data = proposal()
    data.update(goals=['G-1', 'G-2'], cap=3, **({'seats': seats} if seats is not None else {}))
    base = data['candidates'][0]
    data['candidates'] = [{**base, 'id': name, 'goal': goal,
                           'score': {**base['score'], 'job_size': value}}
                          for name, goal, value in (('A', 'G-1', 1), ('B', 'G-2', 2),
                                                    ('C', 'G-1', 3), ('D', 'G-2', 5))]
    return data


@pytest.fixture
def goals2(root):
    path = root / '.wuwei/memory/goals.md'
    path.write_text(path.read_text() + '## G-2\noutcome: Second\nmeasure: shipped\ntarget: 1\ndate: 2026-10-30\npriority: 2\n')
    (root / '.wuwei/config.toml').write_text('cap = 3\n')  # the owner's CAP
    return root


def test_seats_per_goal_in_plan_gate_and_state(goals2):
    root = goals2
    text = plan.propose(four(), root).read_text()
    assert 'Seats per goal: 3 seats: G-1 2, G-2 1 (CAP 3)' in text
    proposal_json = json.loads((root / '.wuwei/days/2026-09-28/proposal.json').read_text())
    assert proposal_json['seats'] == {'G-1': 2, 'G-2': 1}
    widget = plan.gate_widget(root)
    assert '3 seats: G-1 2, G-2 1 (CAP 3)' in widget['options'][0]['description']
    assert 'seats per goal' in widget['options'][-1]['description']
    plan.approve(['A', 'B', 'C', 'D'], root, goals_confirmed=True)
    assert state.read_state(root)['goal_seats'] == {'G-1': 2, 'G-2': 1}
    with pytest.raises(state.StateError, match='wuwei plan approve'):
        state.set_state('goal_seats', {'G-1': 3}, root)


def test_lead_seats_map_is_validated_and_shown(goals2):
    root = goals2
    text = plan.propose(four({'G-1': 1, 'G-2': 2}), root).read_text()
    assert 'Seats per goal: 3 seats: G-1 1, G-2 2 (CAP 3)' in text
    assert '3 seats: G-1 1, G-2 2 (CAP 3)' in plan.gate_widget(root)['options'][0]['description']
    (root / '.wuwei/days/2026-09-28/plan.md').unlink()
    for seats in ({'G-9': 1}, {'G-1': 0}, {'G-1': True}, {'G-1': 2, 'G-2': 2}, ['G-1']):
        with pytest.raises(ValueError, match='seats'):
            plan.propose(four(seats), root)
    data = four()
    data['candidates'] = []
    assert 'Seats per goal: 0 seats (CAP 3)' in plan.propose(data, root).read_text()


def test_template_cap_is_the_configured_cap(root, monkeypatch, capsys):
    from wuwei.__main__ import main
    monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
    (root / '.wuwei/config.toml').write_text('cap = 3\n')
    assert main(['plan', 'template']) == 0
    assert json.loads(capsys.readouterr().out)['cap'] == 3


DEPLOY_ACTION = [{'action': 'deploy', 'target': 'repo:fixture-org/app'}]


def deploying():
    data = proposal()
    data['candidates'][0]['owner_actions'] = DEPLOY_ACTION
    return data


def test_propose_writes_one_planned_card(root, monkeypatch, capsys):
    # #478: an owner-only action the lead lists becomes one card the gate question carries.
    from wuwei.__main__ import main
    text = plan.propose(deploying(), root).read_text()
    assert 'Owner-only: deploy repo:fixture-org/app (D-1)\n' in text
    day = root / '.wuwei/days/2026-09-28'
    row = state.read_state(root)['grants']['D-1']
    assert (row['item'], row['planned'], row['answered']) == ('A', True, None)
    plan.propose(deploying(), root)
    assert sorted(path.name for path in (day / 'decisions').glob('D-*.md')) == ['D-1.md']
    monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
    capsys.readouterr()
    assert main(['plan', 'gate']) == 0
    gate, card = json.loads(capsys.readouterr().out)
    assert gate == plan.gate_widget(root)
    assert card['question'].startswith('D-1: G-1 A deploys fixture-org/app: allow today, ask when it happens, '
                                       'or keep owner-only? ')
    assert [option['label'] for option in card['options']] == [
        'Allow today (Recommended)', 'Ask when it happens', 'Keep owner-only']


def test_plan_gate_without_owner_actions_is_one_question(root, monkeypatch, capsys):
    from wuwei.__main__ import main
    plan.propose(proposal(), root)
    monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
    capsys.readouterr()
    assert main(['plan', 'gate']) == 0
    assert json.loads(capsys.readouterr().out) == [plan.gate_widget(root)]


def test_owner_actions_must_be_a_list(root):
    data = proposal()
    data['candidates'][0]['owner_actions'] = 'deploy'
    with pytest.raises(ValueError, match='owner_actions must be a list'):
        plan.propose(data, root)


@pytest.mark.parametrize('entry,line', [
    ({'action': 'message', 'target': 'channel:C1'}, 'Owner-only: message channel:C1 (owner step)'),
    ({'action': 'secret-set', 'target': 'secret:fixture-org/app/API_KEY'},
     'Owner-only: secret-set secret:fixture-org/app/API_KEY (owner step)'),
    ({'action': 'deploy', 'target': 'fixture-org/app'},
     'Owner-only: {"action": "deploy", "target": "fixture-org/app"} (not understood: target fixture-org/app '
     'is not in the shape for deploy; the gate asks for it as written)'),
    ({'action': 'frobnicate', 'target': 'repo:fixture-org/app'},
     'Owner-only: {"action": "frobnicate", "target": "repo:fixture-org/app"} (not understood: action '
     'frobnicate not understood; known: deploy, release, publish, merge, message, secret-set; '
     'the gate asks for it as written)'),
    ({'action': 'deploy', 'target': 'repo:fixture-org/app', 'when': 'now'},
     '(not understood: needs exactly action and target as strings; the gate asks for it as written)'),
])
def test_owner_actions_beyond_grants_never_stop_the_gate(root, entry, line):
    # #518: the lead's vocabulary (message, secret-set) and anything malformed are lines on
    # the plan; deploy, release, publish and (#524) merge become grant cards.
    data = proposal()
    data['candidates'][0]['owner_actions'] = [entry]
    text = plan.propose(data, root).read_text()
    assert line in text
    assert not (root / '.wuwei/days/2026-09-28/decisions').exists()


def test_planned_merges_are_gate_cards(root, monkeypatch, capsys):
    # #524: a merge the lead lists is a planned card like a deploy, per repository or per PR.
    from wuwei.__main__ import main
    data = proposal()
    data['candidates'][0]['owner_actions'] = [{'action': 'merge', 'target': 'repo:fixture-org/app'},
                                              {'action': 'merge', 'target': 'pr:fixture-org/app#7'}]
    text = plan.propose(data, root).read_text()
    assert 'Owner-only: merge repo:fixture-org/app (D-1)\n' in text
    assert 'Owner-only: merge pr:fixture-org/app#7 (D-2)\n' in text and '(owner step)' not in text
    rows = state.read_state(root)['grants']
    assert [(rows[key]['action'], rows[key]['target']) for key in ('D-1', 'D-2')] == [
        ('merge', 'repo:fixture-org/app'), ('merge', 'pr:fixture-org/app#7')]
    monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
    capsys.readouterr()
    assert main(['plan', 'gate']) == 0
    _, first, second = json.loads(capsys.readouterr().out)
    assert first['question'].startswith('D-1: G-1 A merges fixture-org/app: allow today')
    assert second['question'].startswith('D-2: G-1 A merges fixture-org/app#7: allow today')


def test_lead_charter_names_every_owner_action():
    from pathlib import Path
    from wuwei import grants
    text = (Path(__file__).parents[1] / 'charters/lead.md').read_text()
    for name in grants.OWNER_ACTIONS:
        assert f'`{name}`' in text, name


def test_the_overnight_report_leads_the_next_morning_plan(root, monkeypatch):
    """#511: the newest earlier approved day's producer-only shepherd events, before the goals;
    review F2: an unapproved day with watch clock state in between does not hide them."""
    yesterday = root / '.wuwei/days/2026-09-26'
    without = plan.propose(proposal(), root).read_text()
    assert '## Overnight' not in without
    state._write_state(lambda data: data.update(gate_approved=True), directory=yesterday, reserved=False)
    state._write_state(lambda data: None, directory=root / '.wuwei/days/2026-09-27')
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T02:00:00+02:00')
    state.append_event('shepherd.overnight', {'pr': 'acme/widget#7', 'state': 'threads_unanswered',
        'outcome': 'queued', 'reason': 'triage review threads',
        'evidence': ['thread T17 by bob on src/app.py: Why this name?']}, directory=yesterday)
    state.append_event('shepherd.swept', {'exit': 1}, directory=yesterday)
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T09:00:00+02:00')
    text = plan.propose(proposal(), root).read_text()
    assert text.index('Status: PROPOSED') < text.index('## Overnight (days/2026-09-26') < text.index('## Goals to confirm')
    assert ('1. acme/widget#7 threads_unanswered: triage review threads. Run: bin/wuwei pr act acme/widget#7\n'
            '   - thread T17 by bob on src/app.py: Why this name?\n') in text


def test_propose_writes_the_cruise_raise_card_the_gate_carries(root, monkeypatch, capsys):
    # #283: ten agreements in a class make plan propose write a raise card; plan gate asks it.
    from wuwei.__main__ import main
    rows = {f'D-{100 + index}': {'option': 'A', 'outcome': 'A', 'decided_by': 'owner', 'class': 'defer',
                                 'recommendation': 'A', 'at': workspace.now().isoformat()} for index in range(10)}
    state._write_state(lambda data: data.setdefault('decision_outcomes', {}).update(rows), root, reserved=False)
    for number in range(300, 310):  # #559: the class is calibrated
        state.append_event('decision.decided', {'id': f'D-{number}', 'option': 'A', 'class': 'defer',
                                                'decided_by': 'mandate', 'confidence': 'high'}, root)
    plan.propose(proposal(), root)
    assert state.read_state(root)['cruise_cards']['D-1']['kind'] == 'raise'
    monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
    capsys.readouterr()
    assert main(['plan', 'gate']) == 0
    gate, card = json.loads(capsys.readouterr().out)
    assert card['header'] == 'D-1' and card['options'][0]['label'] == 'Raise defer to L1 (Recommended)'


# #579: the day pace at the morning gate.

def test_candidate_paths_are_validated(root):
    data = proposal()
    data['candidates'][0]['paths'] = ['cli/wuwei/report.py']
    assert plan._proposal(data, (root / '.wuwei/memory/goals.md').read_text())
    data['candidates'][0]['paths'] = 'cli/wuwei/report.py'
    with pytest.raises(ValueError, match='paths must be a list of strings'):
        plan._proposal(data, (root / '.wuwei/memory/goals.md').read_text())


def test_propose_records_the_pace_advice_and_the_gate_offers_each_pace(root):
    path = plan.propose(proposal(), root)
    data = json.loads((path.parent / 'proposal.json').read_text())
    assert data['pace'] == 'steady' and data['pace_advice']['pace'] == 'steady'
    assert data['pace_reasoning'] == data['pace_advice']['lines'] and len(data['pace_reasoning']) == 2
    text = path.read_text()
    assert 'Pace: steady (recommended)' in text and data['pace_reasoning'][0] in text
    widget = plan.gate_widget(root)
    approve, careful = widget['options'][0]['description'], widget['options'][1]['description']
    assert 'Pace steady.' in approve and data['pace_reasoning'][1] in approve
    assert 'Pace careful.' in careful and data['pace_reasoning'][0] not in careful


def pace_events(root, kind):
    return [row['payload'] for row in events(root) if row['kind'] == kind]


@pytest.mark.parametrize('label,expected', [('Approve', 'steady'), ('Approve (Recommended)', 'steady'),
                                            ('Approve at careful', 'careful'), (None, 'steady')])
def test_approve_records_the_chosen_pace(root, label, expected):
    plan.propose(proposal(), root)
    plan.approve(['A'], root, goals_confirmed=True, pace_label=label)
    assert state.read_state(root)['pace'] == expected
    [payload] = pace_events(root, 'plan.approved')
    assert (payload['pace'], payload['recommended'], payload['wish']) == (expected, 'steady', 'steady')


def test_approve_refuses_change_something_and_old_proposals_take_the_default(root):
    plan.propose(proposal(), root)
    with pytest.raises(ValueError, match='Change something asks the separate questions'):
        plan.approve(['A'], root, goals_confirmed=True, pace_label='Change something')
    assert not state.read_state(root)['gate_approved']
    proposal_path = root / '.wuwei/days/2026-09-28/proposal.json'
    data = json.loads(proposal_path.read_text())
    del data['pace']
    proposal_path.write_text(json.dumps(data))
    (root / '.wuwei/config.toml').write_text('[pace]\ndefault = "careful"\n')
    plan.approve(['A'], root, goals_confirmed=True)
    assert state.read_state(root)['pace'] == 'careful'


def test_plan_set_pace(root, capsys, monkeypatch):
    from wuwei.__main__ import main
    monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
    plan.propose(proposal(), root)
    assert main(['plan', 'approve', '--items', 'A', '--goals-confirmed', '--pace', 'Approve at fast']) == 0
    assert main(['plan', 'set', 'pace=careful']) == 0
    assert 'pace careful (was fast)' in capsys.readouterr().out
    assert state.read_state(root)['pace'] == 'careful'
    assert [{key: row[key] for key in ('pace', 'previous')} for row in pace_events(root, 'pace.set')] == [
        {'pace': 'careful', 'previous': 'fast'}]
    assert main(['plan', 'set', 'pace=quick']) == 2
    assert 'careful, steady or fast' in capsys.readouterr().err
    assert main(['plan', 'set', 'A', 'spec=required']) == 0
    assert main(['event', 'pace.set', '{}']) == 1


def test_merge_default_today_writes_no_planned_merge_card(root):
    # #530: a planned merge on a configured repository the merge default covers asks nothing.
    (root / '.wuwei/config.toml').write_text(
        '[[repos]]\nname = "fixture-org/app"\npath = "."\ndefault_branch = "main"\n'
        '[merge]\ndefault_tier = "today"\n')
    data = proposal()
    data['candidates'][0]['owner_actions'] = [{'action': 'merge', 'target': 'repo:fixture-org/app'},
                                              *DEPLOY_ACTION]
    text = plan.propose(data, root).read_text()
    assert 'Owner-only: merge repo:fixture-org/app (merge.default_tier)\n' in text
    assert 'Owner-only: deploy repo:fixture-org/app (D-1)\n' in text
    assert [row['action'] for row in state.read_state(root)['grants'].values()] == ['deploy']


def test_empty_optional_fields_are_absent(root):
    # #640: an empty ticket, tier or docs (or a null tier or docs) is absent, not a refused
    # proposal; a null ticket is the owner's none (#636) and keeps its key.
    plan.propose(two(A={'ticket': '', 'tier': None, 'docs': ''}, B={'ticket': '  ', 'tier': '  '}), root)
    saved = json.loads((root / '.wuwei/days/2026-09-28/proposal.json').read_text())['candidates']
    assert not any(key in row for row in saved for key in ('ticket', 'tier', 'docs'))
    plan.approve(['A', 'B'], root, goals_confirmed=True)
    data = state.read_state(root)
    assert data.get('tickets', {}) == {}
    assert not any('tier' in data['items'][name] for name in ('A', 'B'))


def test_add_discovery_candidate_with_empty_ticket(root):
    plan.propose(proposal(), root)
    plan.approve(['A'], root, goals_confirmed=True)
    candidate = {**proposal()['candidates'][0], 'id': 'B', 'ticket': '', 'paths': ['src/file.py']}
    candidate['score'] = {**candidate['score'], 'job_size': 1}  # ranks above A, so it starts
    state._write_state(lambda day: day.setdefault('discovery_candidates', {}).update(B=candidate),
                       root, reserved=False)
    assert plan.add('B', root)['action'] == 'build next'
    data = state.read_state(root)
    assert 'B' in data['items'] and 'B' not in data.get('tickets', {})


def test_invalid_ticket_names_item_field_and_form(root):
    with pytest.raises(ValueError) as error:
        plan.propose(two(A={'ticket': 'not a ticket!'}), root)
    assert "A: invalid ticket 'not a ticket!'" in str(error.value)
    assert plan.TICKET in str(error.value) and 'owner/repo#12' in str(error.value)
    assert not (root / '.wuwei/days').exists()
