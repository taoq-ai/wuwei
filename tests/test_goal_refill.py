"""#949: exhausted client goals refill, and Stop wakes only a planner that can progress."""

import io
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from fakes import owner, records
from test_plan import proposal
from wuwei import discovery, plan, report, sessions, state, workspace
from wuwei.commands import hook, next as next_command


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', '2026-10-13T10:00:00+00:00')
    monkeypatch.delenv('WUWEI_SEAT_ROLE', raising=False)
    monkeypatch.chdir(tmp_path)
    base = tmp_path / '.wuwei'
    (base / 'memory').mkdir(parents=True)
    (base / 'config.toml').write_text('[[repos]]\nname="acme/client"\npath="client"\ndefault_branch="main"\n')
    (base / 'memory/goals.md').write_text(
        '# Goals\n## G-1\noutcome: Client directory, inventory, mapping and stakeholders\n'
        'measure: client coverage\ntarget: complete\ndate: 2026-10-30\npriority: 1\n')
    monkeypatch.setattr(discovery, 'discover', lambda *a, **kw: {'sources': {}, 'candidates': []})
    from wuwei import dispatch
    monkeypatch.setattr(dispatch, 'host', lambda *a, **kw: {'cap': 2, 'bound': '', 'text': '2', 'seats': 2})
    plan.propose(proposal(), tmp_path)
    plan.approve(['A'], tmp_path, goals_confirmed=True)
    plan.session('planner', tmp_path)
    records.write(tmp_path, {'items': {'A': {'phase': 'merged', 'status': 'done'}}})
    return tmp_path


def refill(root, candidates, number=1):
    data = {**proposal(), 'candidates': candidates}
    path = workspace.day_dir(root) / f'lead-{number}.json'
    path.write_text(json.dumps(data))
    return plan.propose(data, root, refill=number)


def candidate(name='inventory', **fields):
    return {**proposal()['candidates'][0], 'id': name, 'paths': ['src/inventory.py'], **fields}


def _case_field_case_refills_instead_of_close_and_briefs_existing_lead(root):
    from wuwei import brief, dispatch
    import shlex
    from wuwei.__main__ import main
    row = next_command.step(root)
    assert row['state'] == 'refill'
    assert 'lead-1' in row['command'] and next_command.LEAD_BODY in row['command']
    assert main(shlex.split(row['command'])[1:]) == 0
    text = (workspace.day_dir(root) / 'briefs/lead-1.md').read_text()
    assert 'memory/goals.md' in text and 'wuwei status' in text
    assert f'days/{workspace.day_dir(root).name}/goals.md' in text
    assert f'days/{workspace.day_dir(root).name}/state.json' in text
    assert 'wuwei status --line' in text
    row = next_command.step(root)
    assert row['state'] == 'refill' and row['action'] == 'launch'
    assert next_command.resolve(row, root)['agent_type'] == 'wuwei:lead'
    records.write(root, {'seats': {'lead-1': {'role': 'lead', 'item': 'day', 'status': 'running'}}})
    assert next_command.step(root)['state'] == 'wait'
    (workspace.day_dir(root) / 'lead-1.json').write_text(json.dumps(proposal()))
    assert next_command.step(root)['state'] == 'wait'  # do not race a running seat
    records.write(root, {'seats': {'lead-1': {'role': 'lead', 'item': 'day', 'status': 'stopped'}}})
    assert next_command.step(root)['state'] == 'propose'


def _case_safe_goal_work_joins_without_card_and_preserves_morning(root):
    from wuwei import dispatch
    morning = (workspace.day_dir(root) / 'proposal.json').read_bytes()
    refill(root, [candidate()])
    data = state.read_state(root)
    assert data['approved_items'] == ['A', 'inventory']
    assert dispatch.candidate(root, 'inventory')['scope'] == 'one function'
    assert (workspace.day_dir(root) / 'proposal.json').read_bytes() == morning
    assert not any(kind == 'owner.requested' for kind, _ in sessions._rows(root))
    assert next_command.step(root)['state'] == 'set'
    records.write(root, {'items': {'inventory': {'phase': 'merged', 'status': 'done'}}})
    assert 'lead-2' in next_command.step(root)['command']


@pytest.mark.parametrize('fields', [
    {'goal': 'unplanned'}, {'track': 'FULL'}, {'tier': 'full'},
    {'flags': {'trust_surface': True, 'boundary_relevant': False, 'agent_surface': False}},
    {'score': {**proposal()['candidates'][0]['score'], 'job_size': 5}},
    {'owner_actions': [{'action': 'deploy', 'target': 'repo:acme/client'}]},
    {'paths': []}, {'paths': ['']}, {'kind': 'measure', 'paths': []},
    {'kind': 'review', 'paths': [], 'pr': 'acme/client#1', 'review_role': 'quality'},
])
def test_exceptions_share_one_content_bound_card_and_retry(root, fields):
    rows = [candidate(), candidate('risky', **fields), candidate('outside', goal='unplanned')]
    with pytest.raises(state.StateError, match='Owner step card') as error:
        refill(root, rows)
    assert state.read_state(root)['approved_items'] == ['A', 'inventory']
    assert state.read_state(root)['refills'][-1]['pending']
    question = str(error.value)
    assert 'risky' in question and 'outside' in question
    owner.answer_card(root, question)
    refill(root, rows)
    from wuwei import goals, rank
    ordered = rank.rank(rows[1:], 'wsjf', goals.parse((root / '.wuwei/memory/goals.md').read_text()))
    assert state.read_state(root)['approved_items'] == ['A', 'inventory', *[row['id'] for row in ordered]]
    refill(root, rows)
    assert state.read_state(root)['approved_items'].count('risky') == 1
    assert not any(kind == 'owner.requested' for kind, _ in sessions._rows(root))


@pytest.mark.parametrize('case', ['empty refill', 'last refill has work'])
def test_report_uses_last_refill(root, case):
    if case == 'empty refill':
        refill(root, [])
        assert next_command.step(root)['state'] == 'close'
        assert next_command.step(root)['state'] == 'close'
        text = report.build(root)
        assert 'Goals with no work found' in text and 'G-1: Client directory' in text
        # Fold the authoritative events again after removing only the disposable cache.
        (workspace.day_dir(root) / 'state.json').unlink()
        assert next_command.step(root)['state'] == 'close'
        path = root / '.wuwei/memory/goals.md'
        path.write_text(path.read_text().replace('complete', 'complete including vendors'))
        assert next_command.step(root)['state'] == 'close'
    else:
        from wuwei import goals
        opened = goals.parse((root / '.wuwei/memory/goals.md').read_text())
        records.write(root, {'refills': [
            {'number': 1, 'goals': opened, 'admitted': ['first'], 'no_work': ['G-1'], 'pending': False},
            {'number': 2, 'goals': opened, 'admitted': ['second'], 'no_work': [], 'pending': False}]})
        assert 'Goals with no work found' not in report.build(root)


def _case_duplicate_finished_items_and_declined_exceptions_do_not_repeat(root):
    with pytest.raises(state.StateError) as error:
        refill(root, [candidate('A'), candidate('outside', goal='unplanned')])
    owner.answer_card(root, str(error.value), reply='No')
    refill(root, [candidate('A'), candidate('outside', goal='unplanned')])
    assert state.read_state(root)['approved_items'] == ['A']
    assert next_command.step(root)['state'] == 'close'


def stop(root, monkeypatch, capsys, **fields):
    payload = {'session_id': 'planner', 'transcript_path': str(root / 'transcript.jsonl'),
               'cwd': str(root), 'hook_event_name': 'Stop', 'stop_hook_active': False, **fields}
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(payload)))
    capsys.readouterr()
    assert hook.run(SimpleNamespace(event='Stop')) == 0
    output = capsys.readouterr()
    return json.loads(output.out) if output.out else None


@pytest.mark.parametrize('row', ['set', 'refill', 'lead', 'propose'])
def test_stop_blocks_only_changed_active_rows(root, monkeypatch, capsys, row):
    action = {'state': row, 'why': 'Work ready', 'command': 'wuwei next --json',
              'then': '', 'commands': ['wuwei plan set A owner_merge=true']}
    monkeypatch.setattr(next_command, 'step', lambda root: action)
    assert stop(root, monkeypatch, capsys)['decision'] == 'block'
    assert stop(root, monkeypatch, capsys, stop_hook_active=True) is None
    state.append_event('next.action', {'state': row}, root)
    assert stop(root, monkeypatch, capsys, stop_hook_active=True) is None
    action['commands'] = ['wuwei plan set A owner_merge=false']
    assert row in stop(root, monkeypatch, capsys, stop_hook_active=True)['reason']
    last = [data for kind, data in sessions._rows(root) if kind == 'hook.stop_blocked'][-1]
    assert isinstance(last['signature'], str) and len(last['signature']) == 64
    assert action['commands'][0] not in json.dumps(last)
    assert stop(root, monkeypatch, capsys, stop_hook_active=True) is None
    assert stop(root, monkeypatch, capsys, stop_hook_active=False)['decision'] == 'block'


def test_stop_wakes_planner_for_missing_pr_watcher(root, monkeypatch, capsys):
    records.write(root, {'items': {'A': {'phase': 'raised', 'status': 'queued',
                                         'pr': 'acme/client#7'}},
                         'raised_prs': ['acme/client#7']})
    directory = workspace.day_dir(root)
    (directory / 'prs.json').write_text(json.dumps({'fetched_at': workspace.now().isoformat(),
        'pulls': [{'ref': 'acme/client#7', 'state': 'open', 'checks': 'pending', 'labels': []}]}))
    assert any(launch['kind'] == 'pr-wait' for launch in next_command.step(root)['launches'])
    wake = stop(root, monkeypatch, capsys)
    assert wake['decision'] == 'block' and 'wuwei next' in wake['reason']


@pytest.mark.parametrize('case', [
    'wait', 'owner', 'closed', 'closing', 'unstarted', 'seat', 'agent', 'role', 'error',
    'live pr wait', 'live pr wait without queue row',
])
def test_stop_exemptions(root, monkeypatch, capsys, case):
    fields = {}
    if case.startswith('live pr wait'):
        from fakes.host import Fake
        from wuwei import registry
        monkeypatch.setenv('WUWEI_SESSION_ID', 'planner')
        assert next_command.step(root)['state'] == 'refill'
        directory = workspace.day_dir(root)
        if case == 'live pr wait without queue row':
            records.write(root, {'raised_prs': ['acme/client#7']},
                          directory=directory.parent / '2026-10-12')
        else:
            records.write(root, {'items': {'A': {'phase': 'raised', 'status': 'queued',
                                               'pr': 'acme/client#7'}}})
            (directory / 'prs.json').write_text(json.dumps({'fetched_at': workspace.now().isoformat(),
                'pulls': [{'ref': 'acme/client#7', 'state': 'open', 'checks': 'pending', 'labels': []}]}))
        process = {'pid': 41001, 'ppid': 42, 'command': 'python next --background',
                   'identity': 'recorded start'}
        state.append_event('process.started', {**process, 'purpose': 'pr-wait',
                           'session_id': 'planner', 'day': directory.name}, root)
        host = Fake({'processes': registry.Result(0, {41001: process})})
        load = registry.load
        monkeypatch.setattr(registry, 'load', lambda port, config:
                            host if port == 'host' else load(port, config))
        before = list(sessions._rows(root))
        for active in (False, True):
            row = next_command.step(root)
            assert (row['state'], row['action'], row['command']) == ('wait', 'wait', 'wuwei status --line')
            assert stop(root, monkeypatch, capsys, stop_hook_active=active) is None
        assert list(sessions._rows(root)) == before
    elif case == 'error':
        def broken(root):
            raise ValueError('broken data')
        monkeypatch.setattr(next_command, 'step', broken)
    else:
        monkeypatch.setattr(next_command, 'step', lambda root: {'state': 'wait' if case == 'wait' else 'set',
                                                              'then': '', 'decision': case == 'owner'})
    if case == 'owner':
        sessions.needs_owner(root, 'bin/wuwei plan set A owner_merge=true', 'Owner decides')
    elif case == 'closed':
        state.append_event('day.closed', {}, root)
    elif case == 'closing':
        records.write(root, {'close_requested': True})
    elif case == 'unstarted':
        (workspace.day_dir(root) / 'state.json').unlink()
        (workspace.day_dir(root) / 'events.jsonl').unlink()
    elif case == 'seat':
        fields['session_id'] = 'seat-session'
    elif case == 'agent':
        fields['agent_id'] = 'seat-1'
    elif case == 'role':
        monkeypatch.setenv('WUWEI_SEAT_ROLE', 'builder')
    assert stop(root, monkeypatch, capsys, **fields) is None
    if case == 'error':
        assert any(kind == 'hook.stop_error' for kind, _ in sessions._rows(root))


def test_stop_executable_shim(root):
    plugin = Path(__file__).resolve().parents[1]
    payload = {'session_id': 'planner', 'transcript_path': str(root / 'transcript.jsonl'),
               'cwd': str(root), 'hook_event_name': 'Stop', 'stop_hook_active': False}
    result = subprocess.run([str(plugin / 'bin/wuwei'), 'hook', 'Stop'], input=json.dumps(payload),
                            text=True, capture_output=True, cwd=root)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['decision'] == 'block'


@pytest.mark.parametrize('paths', [
    ['infra/main.tf'], ['nested/requirements.txt'], ['.github/workflows/ci.yml'], None,
])
def test_unsafe_or_missing_paths_require_owner(root, paths):
    if paths is None:
        row = candidate()
        del row['paths']
    else:
        row = candidate(paths=paths)
    with pytest.raises(state.StateError, match='Owner step card'):
        refill(root, [row])
    assert state.read_state(root)['approved_items'] == ['A']


def _case_card_cannot_approve_changed_candidate(root):
    rows = [candidate('outside', goal='unplanned')]
    with pytest.raises(state.StateError) as error:
        refill(root, rows)
    owner.answer_card(root, str(error.value))
    rows[0]['scope'] = 'different work'
    with pytest.raises(state.StateError, match='changed'):
        refill(root, rows)
    assert state.read_state(root)['approved_items'] == ['A']


@pytest.mark.parametrize('blocked_by', ['active queue', 'close_requested', 'day.closed'])
def test_refill_requires_exhausted_unclosed_day(root, blocked_by):
    if blocked_by == 'active queue':
        records.write(root, {'items': {'A': {'phase': 'planned'}}})
    elif blocked_by == 'day.closed':
        state.append_event(blocked_by, {}, root)
    else:
        records.write(root, {blocked_by: True})
    with pytest.raises(state.StateError, match='exhausted' if blocked_by == 'active queue' else 'unclosed'):
        refill(root, [candidate()] if blocked_by == 'active queue' else [])
    if blocked_by != 'active queue':
        assert next_command.step(root)['state'] != 'refill'


@pytest.mark.parametrize('case', ['refill proposal', 'symlink proposal'])
def test_tracker_candidate_uses_safe_proposal(root, case):
    from wuwei import tracker
    if case == 'refill proposal':
        refill(root, [candidate()])
        assert tracker._candidate(root, state.read_state(root), 'inventory')['scope'] == 'one function'
    else:
        path = workspace.day_dir(root) / 'proposal.json'
        elsewhere = root / 'foreign.json'
        elsewhere.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(elsewhere)
        assert tracker._candidate(root, state.read_state(root), 'A') is None


@pytest.mark.parametrize('effort, asks', [(1, False), (2, True)])
def test_rice_auto_start_bar(root, effort, asks):
    with (root / '.wuwei/config.toml').open('a') as stream:
        stream.write('\n[prioritisation]\nframework="rice"\n')
    row = candidate(score={'reach': 10, 'impact': 1, 'confidence': .8, 'effort': effort},
                    evidence_lines={key: 'client inventory' for key in ('reach', 'impact', 'confidence', 'effort')})
    if asks:
        with pytest.raises(state.StateError, match='Owner step card'):
            refill(root, [row])
    else:
        refill(root, [row])
    assert ('inventory' in state.read_state(root)['approved_items']) is not asks


def _case_refill_candidate_overrides_unapproved_morning_proposal(root):
    from wuwei import dispatch
    path = workspace.day_dir(root) / 'proposal.json'
    morning = json.loads(path.read_text())
    morning['candidates'].append(candidate('inventory', scope='Old unapproved scope', paths=['old.py']))
    path.write_text(json.dumps(morning))
    refill(root, [candidate(scope='New admitted scope', paths=['new.py'])])
    found = dispatch.candidate(root, 'inventory')
    assert found['scope'] == 'New admitted scope' and found['paths'] == ['new.py']


def _case_refill_preserves_shared_admission_evidence(root):
    from wuwei import merge, metrics
    refill(root, [candidate()])
    assert merge.risk_evidence(root, 'inventory') == [candidate()['flags']]
    workspace_day = state.read_state(root)
    workspace_day['items']['inventory'].update(phase='merged', status='done')
    records.write(root, {'items': workspace_day['items']})
    state.append_event('state.transition', {'phase_changes': {'inventory': 'merged'}}, root)
    assert any(row['item'] == 'inventory' for row in metrics.cycles(root))


def test_abandoned_owner_request_does_not_hide_work(root, monkeypatch, capsys):
    before = list(sessions._rows(root))
    assert sessions.needs_owner(root, 'bin/wuwei plan set A owner_merge=true', 'Owner decides')
    assert list(sessions._rows(root)) == before
    assert stop(root, monkeypatch, capsys)['decision'] == 'block'
    assert stop(root, monkeypatch, capsys, stop_hook_active=True) is None


@pytest.mark.parametrize('case, limit', [
    ('changing commands', 0), ('changing commands', 2), ('changing commands', 20),
    ('warning', 0), ('warning', 2),
])
def test_stop_daily_cap(root, monkeypatch, capsys, case, limit):
    if case == 'changing commands':
        if limit != 20:
            with (root / '.wuwei/config.toml').open('a') as stream:
                stream.write(f'\n[guards]\nstop_max_blocks={limit}\n')
        action = {'state': 'set', 'then': ''}
        monkeypatch.setattr(next_command, 'step', lambda root: action)
        for index in range(limit + 1):
            action['command'] = f'wuwei plan set A attempt={index}'
            state.append_event('next.action', {'state': 'set'}, root)
            result = stop(root, monkeypatch, capsys, stop_hook_active=True)
            assert (result is not None) == (index < limit)
        assert sum(kind == 'hook.stop_blocked' for kind, _ in sessions._rows(root)) == limit
    else:
        from wuwei.commands import status
        with (root / '.wuwei/config.toml').open('a') as stream:
            stream.write(f'\n[guards]\nstop_max_blocks={limit}\n')
        for _ in range(limit):
            assert stop(root, monkeypatch, capsys)['decision'] == 'block'
        for _ in range(2):
            assert stop(root, monkeypatch, capsys) is None
        warnings = [row for kind, row in sessions._rows(root) if kind == 'hook.stop_capped']
        assert len(warnings) == 1 and warnings[0]['limit'] == limit
        shown = [row for row in status.attention(workspace.day_dir(root)) if row['source'] == 'hook.stop_capped']
        assert len(shown) == 1 and shown[0]['tier'] == 'warn'
        assert 'wake is off' in shown[0]['reason']
        plan.session('new-planner', root, take_over=True)
        assert stop(root, monkeypatch, capsys, session_id='new-planner') is None
        assert sum(kind == 'hook.stop_capped' for kind, _ in sessions._rows(root)) == 1


@pytest.mark.parametrize('limit', [0, 1, 3])
def test_refill_daily_cap_and_report(root, limit):
    if limit != 3:
        with (root / '.wuwei/config.toml').open('a') as stream:
            stream.write(f'\n[plan]\nmax_refills={limit}\n')
    for index in range(1, limit + 1):
        name = f'inventory-{index}'
        refill(root, [candidate(name)], index)
        records.write(root, {'items': {name: {'phase': 'merged', 'status': 'done'}}})
    assert next_command.step(root)['state'] == 'close'
    assert f'Refill limit reached ({limit})' in report.build(root)
    with pytest.raises(state.StateError, match='limit'):
        refill(root, [candidate('too-late')], limit + 1)


@pytest.mark.parametrize('now, expected', [
    ('14:59:59', 'refill'), ('15:00:00', 'close'), ('18:00:00', 'close'),
    ('slow discovery', 'envelope.end'),
])
def test_refill_honors_approved_envelope_in_owner_timezone(root, monkeypatch, now, expected):
    timezone = 'UTC' if now == 'slow discovery' else 'Europe/Amsterdam'
    with (root / '.wuwei/config.toml').open('a') as stream:
        stream.write(f'\n[owner]\ntimezone="{timezone}"\n')
    if now == 'slow discovery':
        monkeypatch.setenv('WUWEI_NOW', '2026-10-13T16:59:59+00:00')
        def slow_discovery(*args, **kwargs):
            monkeypatch.setenv('WUWEI_NOW', '2026-10-13T17:00:01+00:00')
            return {'sources': {}, 'candidates': []}
        monkeypatch.setattr(discovery, 'discover', slow_discovery)
        with pytest.raises(state.StateError, match='envelope.end'):
            refill(root, [candidate('late')])
        assert state.read_state(root)['approved_items'] == ['A']
        return
    monkeypatch.setenv('WUWEI_NOW', f'2026-10-13T{now}+00:00')
    assert next_command.step(root)['state'] == expected
    if expected == 'close':
        assert 'envelope.end (17:00)' in report.build(root)
        with pytest.raises(state.StateError, match='envelope.end'):
            refill(root, [candidate()])


@pytest.mark.parametrize('case', ['after end', 'another pass'])
def test_pending_refill_respects_cap_and_end(root, monkeypatch, case):
    with (root / '.wuwei/config.toml').open('a') as stream:
        stream.write('\n[plan]\nmax_refills=1\n' + ('[owner]\ntimezone="UTC"\n' if case == 'after end' else ''))
    rows = [candidate(goal='unplanned')]
    with pytest.raises(state.StateError, match='Owner step card' if case == 'another pass' else None) as error:
        refill(root, rows)
    if case == 'after end':
        assert next_command.step(root)['state'] == 'propose'
        owner.answer_card(root, str(error.value))
        monkeypatch.setenv('WUWEI_NOW', '2026-10-13T17:00:00+00:00')
        assert next_command.step(root)['state'] == 'close'
        with pytest.raises(state.StateError, match='envelope.end'):
            refill(root, rows)
        assert state.read_state(root)['approved_items'] == ['A']
    else:
        with pytest.raises(state.StateError, match='pending refill'):
            refill(root, [candidate('beyond-cap')], 2)
        assert state.read_state(root)['approved_items'] == ['A']
        assert len(state.read_state(root)['refills']) == 1


def _case_refill_command_stays_compact_for_large_goals_and_item_scope(root):
    path = workspace.day_dir(root) / 'goals.md'
    path.write_text((root / '.wuwei/memory/goals.md').read_text().replace('complete', 'complete ' * 3000))
    records.write(root, {'items': {'A': {'phase': 'merged', 'status': 'done', 'approved_as': 'inventory ' * 3000}}})
    row = next_command.step(root)
    assert len(row['command']) < 2500
    assert 'memory/goals.md' in row['command'] and 'wuwei status' in row['command']


def _case_unknown_repository_goes_to_card_without_aborting_safe_candidates(root):
    with (root / '.wuwei/config.toml').open('a') as stream:
        stream.write('\n[[repos]]\nname="acme/other"\npath="other"\ndefault_branch="main"\n')
    rows = [candidate(repo='acme/client'), candidate('unknown', repo='missing/repo')]
    with pytest.raises(state.StateError, match='Owner step card') as error:
        refill(root, rows)
    assert 'unknown' in str(error.value) and 'repository' in str(error.value).lower()
    assert state.read_state(root)['approved_items'] == ['A', 'inventory']


@pytest.mark.parametrize('snapshot', ['saved', 'missing'])
def test_refill_uses_gate_goal_snapshot(root, snapshot):
    if snapshot == 'saved':
        original = (root / '.wuwei/memory/goals.md').read_text()
        assert (workspace.day_dir(root) / 'goals.md').read_text() == original
        (root / '.wuwei/memory/goals.md').write_text(original.replace('Client directory', 'Changed memory'))
        refill(root, [])
        assert state.read_state(root)['refills'][-1]['goals']['G-1']['outcome'].startswith('Client directory')
    else:
        (workspace.day_dir(root) / 'goals.md').unlink(missing_ok=True)
        assert next_command.step(root)['state'] == 'close'


def _case_only_gate_approved_goal_ids_are_automatic(root):
    path = workspace.day_dir(root) / 'goals.md'
    text = (root / '.wuwei/memory/goals.md').read_text()
    path.write_text(text + text.replace('# Goals\n', '').replace('G-1', 'G-2'))
    rows = [candidate(goal='G-2')]
    with pytest.raises(state.StateError, match='Owner step card') as error:
        refill(root, rows)
    assert state.read_state(root)['approved_items'] == ['A']
    owner.answer_card(root, str(error.value))
    refill(root, rows)
    assert state.read_state(root)['goals'] == ['G-1']


def test_completed_refill_retry_is_idempotent_at_cap_and_after_end(root, monkeypatch):
    with (root / '.wuwei/config.toml').open('a') as stream:
        stream.write('\n[plan]\nmax_refills=1\n[owner]\ntimezone="UTC"\n')
    refill(root, [candidate()])
    monkeypatch.setenv('WUWEI_NOW', '2026-10-13T18:00:00+00:00')
    before = list(sessions._rows(root))
    refill(root, [candidate()])
    assert list(sessions._rows(root)) == before


@pytest.mark.parametrize('end, closed', [
    ('2026-10-13T20:00:00+02:00', True),
    ('2026-10-13T20:00:00+00:00', False),
    ('2026-10-13T20:00:00', True),
    ('20:00', True), ('not a deadline', False), (123, False),
])
@pytest.mark.parametrize('consumer', ['next', 'report'])
def test_refill_and_report_accept_envelope_end_formats(root, monkeypatch, end, closed, consumer):
    with (root / '.wuwei/config.toml').open('a') as stream:
        stream.write('\n[owner]\ntimezone="Europe/Amsterdam"\n')
    monkeypatch.setenv('WUWEI_NOW', '2026-10-13T18:00:00+00:00')
    data = state.read_state(root)
    records.write(root, {'envelope': {**data['envelope'], 'end': end}})
    if consumer == 'next':
        assert next_command.step(root)['state'] == ('close' if closed else 'refill')
    else:
        assert ('Refill stopped at envelope.end' in report.build(root)) == closed


@pytest.mark.parametrize("scenario_fn", [
    _case_field_case_refills_instead_of_close_and_briefs_existing_lead,
    _case_safe_goal_work_joins_without_card_and_preserves_morning,
    _case_duplicate_finished_items_and_declined_exceptions_do_not_repeat,
    _case_card_cannot_approve_changed_candidate,
    _case_refill_candidate_overrides_unapproved_morning_proposal,
    _case_refill_preserves_shared_admission_evidence,
    _case_refill_command_stays_compact_for_large_goals_and_item_scope,
    _case_unknown_repository_goes_to_card_without_aborting_safe_candidates,
    _case_only_gate_approved_goal_ids_are_automatic,
])
def test_refill_evidence_cases(root, scenario_fn):
    scenario_fn(root)
