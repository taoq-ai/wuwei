"""wuwei next: the one next step for the day, and the SessionStart orientation block."""

import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from wuwei import integrity, state, workspace
from wuwei.__main__ import main
from wuwei.commands import next as next_command


NOW = '2026-09-30T10:00:00+00:00'
PAYLOADS = Path(__file__).parent / 'payloads'


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', NOW)
    monkeypatch.delenv('WUWEI_SEAT_ROLE', raising=False)
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('')
    state._write_state(lambda data: None, tmp_path)
    return tmp_path


def calibrated(root):
    (root / '.wuwei/config.toml').write_text(
        '[[repos]]\nname = "example/project"\npath = "project"\ndefault_branch = "main"\n')


def planned(root):
    calibrated(root)
    (workspace.day_dir(root) / 'plan.md').write_text('# Plan\n')


def day(root, **fields):
    """Set today's records as given (one patch event, #844); phases skip the transition checks a
    fixture does not need."""
    from fakes import records
    records.write(root, fields)


def approved(root, items, cap=1, **extra):
    planned(root)
    day(root, gate_approved=True, approved_items=list(items), cap=cap, planner_session_id='S',
        items={name: {'phase': phase, **fields} for name, (phase, fields) in items.items()},
        **extra)


def row(capsys, *args):
    capsys.readouterr()
    code = main(['next', '--json', *args])
    return code, json.loads(capsys.readouterr().out)


def coarse(root):
    """The hook-safe row before delegation."""
    return next_command.step(root)


def test_next_offers_unclaimed_pr_before_restarting_work(root):
    approved(root, {'A': ('planned', {})})
    state.append_event('pr.unclaimed', {
        'pr': 'example/project#950',
        'url': 'https://github.com/example/project/pull/950'}, root)
    found = coarse(root)
    assert found['command'] == 'wuwei pr claim https://github.com/example/project/pull/950'
    state.record_pr(root, 'A', 'example/project#950', raised=False)
    assert coarse(root)['state'] != 'pr-claim'


def test_unclaimed_pr_with_multiple_goals_names_choice(root):
    approved(root, {}, goals=['G-1', 'G-2'])
    state.append_event('pr.unclaimed', {
        'pr': 'example/project#8', 'url': 'https://github.com/example/project/pull/8'}, root)
    found = coarse(root)
    assert '--goal <one of G-1, G-2>' in found['command']
    assert found['action'] == 'owner'
    from wuwei import metrics
    assert any(metrics._matches('wuwei pr claim https://github.com/example/project/pull/8 --goal G-1',
                                pattern) for pattern in next_command.named(found))


def test_unclaimed_item_pr_uses_item_goal(root):
    approved(root, {'A': ('gate', {'goal': 'G-2'})}, goals=['G-1', 'G-2'])
    state.append_event('pr.unclaimed', {'pr': 'example/project#8', 'item': 'A',
        'url': 'https://github.com/example/project/pull/8',
        'reason': 'A: pre-PR gates not passed'}, root)
    found = coarse(root)
    assert found['command'] == 'wuwei pr claim https://github.com/example/project/pull/8 --item A --goal G-2'
    assert "Run A's gates first" in found['why']
    assert found['action'] == 'run'


@pytest.mark.parametrize('state_name', ['closed', 'merged'])
def test_next_does_not_offer_closed_or_merged_unclaimed_pr(root, state_name):
    approved(root, {})
    directory = workspace.day_dir(root)
    state.append_event('pr.unclaimed', {
        'pr': 'example/project#8', 'url': 'https://github.com/example/project/pull/8'}, root)
    (directory / 'prs.json').write_text(json.dumps({'fetched_at': NOW, 'repos': {
        'example/project': {'at': NOW}}, 'pulls': [{
        'ref': 'example/project#8', 'state': state_name}]}))
    assert coarse(root)['state'] != 'pr-claim'


def test_next_refreshes_unclaimed_repo_before_offering(root, monkeypatch, capsys):
    from wuwei import derive
    approved(root, {})
    directory = workspace.day_dir(root)
    state.append_event('pr.unclaimed', {
        'pr': 'example/project#8', 'url': 'https://github.com/example/project/pull/8'}, root)
    refreshed = []
    def refresh(root, config, names):
        refreshed.extend(names)
        (directory / 'prs.json').write_text(json.dumps({'fetched_at': NOW,
            'repos': {'example/project': {'at': NOW}}, 'pulls': []}))
    monkeypatch.setattr(derive, 'refresh', refresh)
    monkeypatch.setattr(next_command, '_supervise', lambda *args: None)
    assert row(capsys)[1]['state'] != 'pr-claim'
    assert refreshed == ['example/project']


def test_next_reuses_recent_listing_for_unclaimed_pr(root, monkeypatch, capsys):
    from wuwei import derive
    approved(root, {})
    directory = workspace.day_dir(root)
    state.append_event('pr.unclaimed', {
        'pr': 'example/project#8', 'url': 'https://github.com/example/project/pull/8'}, root)
    (directory / 'prs.json').write_text(json.dumps({'fetched_at': NOW,
        'repos': {'example/project': {'at': NOW}},
        'pulls': [{'ref': 'example/project#8', 'state': 'open'}]}))
    refreshed = []
    def refresh(root, config, names):
        refreshed.extend(names)
        (directory / 'prs.json').write_text(json.dumps({'fetched_at': NOW,
            'repos': {'example/project': {'at': NOW}}, 'pulls': []}))
    monkeypatch.setattr(derive, 'refresh', refresh)
    monkeypatch.setattr(next_command, '_supervise', lambda *args: None)
    assert row(capsys)[1]['state'] == 'pr-claim'
    assert refreshed == []


def test_next_refreshes_once_when_unclaimed_event_is_newer(root, monkeypatch, capsys):
    from wuwei import derive
    approved(root, {})
    directory = workspace.day_dir(root)
    (directory / 'prs.json').write_text(json.dumps({'fetched_at': '2026-09-30T09:59:00+00:00',
        'repos': {'example/project': {'at': '2026-09-30T09:59:00+00:00'}}, 'pulls': []}))
    state.append_event('pr.unclaimed', {
        'pr': 'example/project#8', 'url': 'https://github.com/example/project/pull/8'}, root)
    refreshed = []
    def refresh(root, config, names):
        refreshed.extend(names)
        (directory / 'prs.json').write_text(json.dumps({'fetched_at': NOW,
            'repos': {'example/project': {'at': NOW}},
            'pulls': [{'ref': 'example/project#8', 'state': 'open'}]}))
    monkeypatch.setattr(derive, 'refresh', refresh)
    monkeypatch.setattr(next_command, '_supervise', lambda *args: None)
    assert row(capsys)[1]['state'] == 'pr-claim'
    assert row(capsys)[1]['state'] == 'pr-claim'
    assert refreshed == ['example/project']


@pytest.mark.parametrize('status', ['claimed', 'dismissed', 'done', 'closed'])
def test_next_does_not_refresh_cleared_unclaimed_pr(root, monkeypatch, capsys, status):
    from wuwei import derive
    approved(root, {'A': ('planned', {})} if status == 'claimed' else {})
    ref = 'example/project#8'
    state.append_event('pr.unclaimed', {'pr': ref,
        'url': 'https://github.com/example/project/pull/8'}, root)
    if status == 'claimed':
        state.record_pr(root, 'A', ref, raised=False)
    elif status == 'dismissed':
        state.append_event('next.action', {'state': 'pr-claim', 'item': ref,
                                           'done': [['pr-claim', ref]]}, root)
    elif status == 'done':
        for _ in range(3):
            state.append_event('next.action', {'state': 'pr-claim', 'item': ref,
                                               'action': 'run'}, root)
    else:
        state.append_event('day.closed', {}, root)
    directory = workspace.day_dir(root)
    (directory / 'prs.json').write_text(json.dumps({'fetched_at': '2026-09-30T10:01:00+00:00',
        'repos': {'example/project': {'at': '2026-09-30T10:01:00+00:00'}}, 'pulls': []}))
    refreshed = []
    monkeypatch.setattr(derive, 'refresh', lambda root, config, names: refreshed.extend(names))
    monkeypatch.setattr(next_command, '_supervise', lambda *args: None)
    row(capsys)
    assert refreshed == []


def test_next_polls_pending_unclaimed_pr_after_poll_seconds(root, monkeypatch, capsys):
    from wuwei import derive
    approved(root, {})
    directory = workspace.day_dir(root)
    state.append_event('pr.unclaimed', {
        'pr': 'example/project#8', 'url': 'https://github.com/example/project/pull/8'}, root)
    (directory / 'prs.json').write_text(json.dumps({'fetched_at': NOW,
        'repos': {'example/project': {'at': NOW}},
        'pulls': [{'ref': 'example/project#8', 'state': 'open'}]}))
    monkeypatch.setenv('WUWEI_NOW', '2026-09-30T10:03:00+00:00')
    refreshed = []
    monkeypatch.setattr(derive, 'refresh', lambda root, config, names: refreshed.extend(names))
    monkeypatch.setattr(next_command, '_supervise', lambda *args: None)
    row(capsys)
    assert refreshed == ['example/project']


def test_stuck_seat_precedes_unclaimed_pr(root, monkeypatch):
    from wuwei import brief
    approved(root, {'A': ('planned', {})}, seats={'b': {
        'status': 'running', 'role': 'builder', 'item': 'A'}})
    monkeypatch.setattr(brief, 'stuck', lambda data: ['b'])
    state.append_event('pr.unclaimed', {
        'pr': 'example/project#8', 'url': 'https://github.com/example/project/pull/8'}, root)
    found = coarse(root)
    assert found['state'] == 'set'
    assert any(entry['kind'] == 'stop' for entry in found['launches'])


def test_refused_claim_is_dismissed_after_its_command_runs(root):
    approved(root, {})
    ref = 'example/project#8'
    state.append_event('pr.unclaimed', {'pr': ref,
        'url': 'https://github.com/example/project/pull/8', 'reason': 'item already links another PR'}, root)
    found = coarse(root)
    assert 'item already links another PR' in found['why']
    state.append_event('next.action', {'state': 'pr-claim', 'item': ref,
                                      'done': [['pr-claim', ref]]}, root)
    assert coarse(root)['state'] != 'pr-claim'


def test_next_ignores_old_unclaimed_event_for_unconfigured_repo(root):
    approved(root, {})
    state.append_event('pr.unclaimed', {'pr': 'acme/other#8',
        'url': 'https://github.com/acme/other/pull/8'}, root)
    assert coarse(root)['state'] != 'pr-claim'


SHAPE = {'state', 'action', 'command', 'why', 'then'}


# US1: wuwei next


def test_setup_rows(root, capsys):
    # #832: repositories are added in the session, each on its Owner step card; no host terminal.
    code, found = row(capsys)
    assert code == 0 and set(found) == SHAPE and found['action'] == 'run'
    assert (found['state'], found['command']) == (
        'setup', 'wuwei config add-repo --name <owner/repo> --path <path> --branch <branch>')
    assert found['then'] == next_command.THEN['setup'] and 'Owner step card' in found['then']
    assert 'host terminal' not in found['why'] + found['then']
    (root / '.wuwei/config.toml').write_text(
        '[[repos]]\nname = "example/project"\npath = "project"\ndefault_branch = "main"\n')
    # calibration.json is the drift baseline, not a day gate: doctor names config promote
    assert row(capsys)[1]['state'] == 'session'


def test_setup_row_outside_workspace(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    monkeypatch.chdir(tmp_path)
    code, found = row(capsys)
    assert code == 0 and set(found) == SHAPE and found['action'] == 'run'
    assert (found['state'], found['command']) == ('no-workspace', 'bin/wuwei init --shadow')
    assert found['then'] == next_command.THEN['run'] and 'host terminal' not in found['why'] + found['then']
    capsys.readouterr()
    assert main(['next']) == 0
    assert capsys.readouterr().out == f"no-workspace: {found['why']} {found['then']}\nbin/wuwei init --shadow\n"


def seen(root, *states):
    """The once-a-day rows whose command already ran today."""
    for name in states:
        state.append_event('next.action', {'state': 'x', 'action': 'run', 'item': '', 'named': [],
                                           'traces': 0, 'done': [[name, '']]}, root)


def last_event(root):
    return json.loads((workspace.day_dir(root) / 'events.jsonl').read_text().splitlines()[-1])


def no_skill(found):
    text = json.dumps(found)
    assert '/wuwei:' not in text and 'SKILL.md' not in text and 'skill' not in text.lower(), found


def proposed(root, capsys):
    """A real proposal from the lead JSON template, as the lead would answer."""
    (root / '.wuwei/memory').mkdir(exist_ok=True)
    (root / '.wuwei/memory/goals.md').write_text(
        '# Goals\n## G-1\noutcome: Ship\nmeasure: shipped\ntarget: 1\ndate: 2026-10-30\npriority: 1\n')
    capsys.readouterr()
    assert main(['plan', 'template']) == 0
    (workspace.day_dir(root) / 'lead.json').write_text(capsys.readouterr().out)
    assert main(['plan', 'propose', '.wuwei/days/2026-09-30/lead.json']) == 0


def test_morning_path(root, capsys, monkeypatch):
    import shlex
    from wuwei import brief
    calibrated(root)
    monkeypatch.chdir(root)
    monkeypatch.setenv('WUWEI_SESSION_ID', 'S')
    seen_rows = []
    code, found = row(capsys)
    seen_rows.append(found)
    assert (code, found['state'], found['action'], found['command']) == (
        0, 'session', 'run', 'wuwei plan session S')
    monkeypatch.delenv('WUWEI_SESSION_ID')
    assert row(capsys)[1]['command'] == 'wuwei plan session <session id>'
    assert main(['plan', 'session', 'S']) == 0
    for command in ('wuwei doctor --section pr-flow',):
        found = row(capsys)[1]
        seen_rows.append(found)
        assert (found['action'], found['command']) == ('run', command)
        payload = last_event(root)['payload']
        assert {key: payload[key] for key in ('state', 'action', 'item', 'named')} == {
            'state': found['state'], 'action': 'run', 'item': '', 'named': [command]}
        ran(root, command)  # done when its command ran, not when it was returned
    found = row(capsys)[1]
    seen_rows.append(found)
    assert found['state'] == 'lead' and found['command'].startswith('wuwei seat brief lead day lead --body ')
    assert '<' not in found['command']
    capsys.readouterr()
    assert main(shlex.split(found['command'])[1:]) == 0
    found = row(capsys)[1]
    seen_rows.append(found)
    expected = brief.seat_action('lead', workspace.day_dir(root) / 'briefs/lead.md', root, root)
    assert found['action'] == 'launch' and {key: found[key] for key in expected} == expected
    assert '.wuwei/days/2026-09-30/lead.json with the Write tool' in found['then']
    assert next_command.text(found).endswith('\nAgent wuwei:lead')
    day(root, seats={'lead': {'status': 'running', 'role': 'lead', 'item': 'day'}})
    found = row(capsys)[1]
    assert (found['action'], found['command']) == ('wait', 'wuwei status --line')
    day(root, seats={'lead': {'status': 'stopped', 'role': 'lead', 'item': 'day'}})
    found = row(capsys)[1]
    seen_rows.append(found)
    assert found['command'] == 'wuwei plan propose .wuwei/days/2026-09-30/lead.json'
    proposed(root, capsys)
    capsys.readouterr()
    assert main(['plan', 'gate']) == 0
    widget = json.loads(capsys.readouterr().out)
    for _ in range(2):  # the gate is the one card that repeats until approved
        found = row(capsys)[1]
        seen_rows.append(found)
        assert (found['state'], found['action'], found['widget']) == ('gate', 'card', widget)
        assert 'wuwei plan propose .wuwei/days/2026-09-30/lead.json' in last_event(root)['payload']['named']
        assert widget[0]['record'] in last_event(root)['payload']['named']
    capsys.readouterr()
    assert main(['next']) == 0
    assert capsys.readouterr().out == f"gate: {found['why']} {found['then']}\nwuwei plan gate\n"
    for found in seen_rows:
        assert set(found) >= {'state', 'action', 'why', 'then'} and 'step' not in found
        no_skill(found)


def test_next_records_only_with_day_state(root, capsys):
    calibrated(root)
    for name in ('state.json',):
        (workspace.day_dir(root) / name).unlink(missing_ok=True)
    found = row(capsys)[1]
    assert found['state'] == 'session', found
    assert 'next.action' not in (workspace.day_dir(root) / 'events.jsonl').read_text()


def test_no_decision_row(root, capsys):
    # Part 14: an owner decision comes from the command that needs it; no record row asks one.
    approved(root, {}, decision_routes={'D-1': {'reversibility': 'one-way'}})
    assert coarse(root)['state'] == 'close'


@pytest.mark.parametrize('phase,fields,expected,command', [
    ('planned', {}, 'build', 'wuwei dispatch next --all'),
    ('implement', {}, 'build', 'wuwei build next ITEM-1'),
    ('fix', {}, 'fix', 'wuwei build next ITEM-1'),
    ('gate', {}, 'gates', 'wuwei dispatch next ITEM-1'),
    ('delta', {}, 'gates', 'wuwei dispatch next ITEM-1'),
    ('raised', {'pr': 'example/project#7'}, 'pr', 'wuwei pr act example/project#7'),
])
def test_item_rows(root, capsys, phase, fields, expected, command):
    # #844: after the gate next returns the set: every launch with the command that resolves it
    approved(root, {'ITEM-1': (phase, fields)})
    found = coarse(root)
    assert (found['state'], found['action']) == ('set', 'set')
    assert [(launch['kind'], launch['command']) for launch in found['launches']] == [(expected, command)]


def seated(root):
    day(root, seats={'builder-1': {'status': 'running', 'role': 'builder', 'item': 'ITEM-1'}})


def test_cap_waits_on_running_seat(root, capsys):
    approved(root, {'ITEM-1': ('implement', {}), 'ITEM-2': ('planned', {})})
    seated(root)
    found = coarse(root)
    assert (found['state'], found['command']) == ('wait', 'wuwei status --line')
    assert 'builder ITEM-1' in found['why']
    approved(root, {'ITEM-1': ('implement', {}), 'ITEM-2': ('planned', {})}, cap=2)
    seated(root)
    found = coarse(root)
    assert [(launch['kind'], launch['item']) for launch in found['launches']] == [('build', 'ITEM-2')]


def running_day(root, pid):
    """Builders on A and B, a fast check on C: the day of issue #477 Acceptance 3."""
    approved(root, {name: ('implement', {}) for name in 'ABC'}, cap=2)
    day(root, seats={
        'builder-1': {'status': 'running', 'role': 'builder', 'item': 'A',
                      'started_at': '2026-09-30T09:10:00+00:00'},
        'builder-2': {'status': 'running', 'role': 'builder', 'item': 'B',
                      'started_at': '2026-09-30T09:20:00+00:00'}},
        builds={'C': {'status': 'check', 'check': {
            'started_at': '2026-09-30T09:25:00+00:00', 'pid': pid}}})


def test_running_names_seats_and_checks_with_start_times(root, capsys):
    import subprocess
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
    try:
        running_day(root, child.pid)
        found = coarse(root)
    finally:
        child.kill()
        child.wait()
    assert (found['state'], found['command']) == ('wait', 'wuwei status --line')
    assert 'Running: builder A 09:10, builder B 09:20, checks C 09:25' in found['why']
    found = coarse(root)
    assert [(launch['kind'], launch['command']) for launch in found['launches']] == [
        ('build', 'wuwei build next C')]


def test_every_approved_item_is_offered_in_plan_order_and_missing_is_skipped(root, capsys):
    approved(root, {'ITEM-2': ('gate', {}), 'ITEM-1': ('implement', {})})
    day(root, approved_items=['ITEM-0', 'ITEM-2', 'ITEM-1'])
    assert [launch['command'] for launch in coarse(root)['launches']] == [
        'wuwei dispatch next ITEM-2', 'wuwei build next ITEM-1']


def test_end_of_day_rows(root, capsys, monkeypatch):
    # #844: no doctor row; doctor stays a command
    approved(root, {})
    assert coarse(root)['command'] == 'wuwei close'
    approved(root, {'ITEM-1': ('merged', {}), 'ITEM-2': ('parked', {'resume_phase': 'implement'}),
                    'ITEM-3': ('escalated', {'resume_phase': 'implement'})})
    found = coarse(root)
    assert (found['state'], found['command']) == ('close', 'wuwei close')
    state.append_event('heartbeat: clock', {'health': 'degraded', 'page': 'x'}, root)
    assert coarse(root)['state'] == 'close'


@pytest.mark.parametrize('name,text', [('config.toml', 'repos = ['), ('state', '{not json')])
def test_unreadable_input_is_unmeasured(root, capsys, name, text):
    planned(root)
    path = (root / '.wuwei/config.toml' if name == 'config.toml'
            else workspace.day_dir(root) / 'state.json')
    path.unlink()
    path.write_text(text)
    capsys.readouterr()
    assert main(['next', '--json']) == 2
    out, err = capsys.readouterr()
    found = json.loads(out)
    assert (found['state'], found['command']) == ('unmeasured', 'wuwei doctor')
    assert found['why'] and 'wuwei next:' in err


# US2: SessionStart orientation


ROW = next_command._row('session', "Register this session as today's planner.",
                       'wuwei plan session <session id>')


@pytest.mark.parametrize('enforce,phrases', [
    (False, ('Guards log only (guards.enforce = false)', "The day report's ## Shadow section",
             'merges and approvals stay owner-only')),
    (True, ('Guards enforce:', 'merges and approvals stay owner-only'))])
def test_orientation_block(monkeypatch, enforce, phrases):
    monkeypatch.delenv('WUWEI_SEAT_ROLE', raising=False)
    text = next_command.orientation(ROW, enforce, 'speckit strict', 'S')
    assert text.startswith(next_command.HEADER) and len(text.splitlines()) < 30
    shown = next_command.text(ROW).replace('<session id>', 'S')
    for phrase in ('Next: ' + shown, next_command.LOOP, 'wuwei --help', '\nwuwei plan session S\n',
                   'docs/site/daily.md', 'first word of a plain command', *phrases):
        assert phrase in text
    for phrase in ('SKILL.md', 'Do this now.', 'docs/site/agent.md', 'Start or resume'):
        assert phrase not in text
    assert '<session id>' in next_command.orientation(ROW, enforce)


def test_orientation_by_state(monkeypatch):
    monkeypatch.delenv('WUWEI_SEAT_ROLE', raising=False)
    close = next_command.orientation(next_command._row('close', 'Close.', 'wuwei close'), True)
    assert next_command.LOOP in close and '\nwuwei close\n' in close and 'plan session' not in close
    stuck = next_command.orientation(next_command._row(
        'stuck', 'Seat builder-1 ended with no recorded result.',
        'wuwei seat stop builder-1 --unmeasured "seat ended with no recorded result"'), True, None, 'S')
    assert 'wuwei seat stop' in stuck and 'wuwei --help' in stuck
    for phrase in ('/wuwei:', 'plan session', 'SKILL.md'):
        assert phrase not in stuck


@pytest.mark.parametrize('role,seat', [('shepherd', True), ('../x', False), ('nope', False),
                                       ('_common', False)])
def test_orientation_seat_entry(monkeypatch, role, seat):
    monkeypatch.setenv('WUWEI_SEAT_ROLE', role)
    text = next_command.orientation(ROW, True)
    assert ('charters/shepherd.md' in text) is seat
    assert (next_command.LOOP in text) is not seat


def hook(monkeypatch, cwd):
    from wuwei.commands.hook import run
    payload = {**json.loads((PAYLOADS / 'SessionStart/recorded.json').read_text()),
               'session_id': 'S', 'cwd': str(cwd)}
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(payload)))
    return run(SimpleNamespace(event='SessionStart'))


def context(capsys):
    return json.loads(capsys.readouterr().out)['hookSpecificOutput']['additionalContext']


def test_issue_acceptance_session_start_orients(root, monkeypatch, capsys):
    calibrated(root)
    memory = root / '.wuwei/memory'
    (memory / 'notes').mkdir(parents=True)
    for name in ('spine.md', 'index.md', 'goals.md'):
        (memory / name).write_text('')
    capsys.readouterr()
    assert hook(monkeypatch, root) == 0
    text = context(capsys)
    lines = text.splitlines()
    assert text.startswith(next_command.HEADER)
    assert any(line.startswith('Next: session: ') for line in lines)
    assert 'wuwei --help' in text and 'wuwei plan session S' in lines and next_command.LOOP in lines
    reference = next(index for index, line in enumerate(lines) if line.startswith('Reference: '))
    assert reference < 30 and lines.index('Active constraints:') == reference + 1


def test_constraints_precede_a_long_spine(root, monkeypatch, capsys):
    calibrated(root)
    memory = root / '.wuwei/memory'
    memory.mkdir(parents=True, exist_ok=True)
    for name in ('index.md', 'goals.md'):
        (memory / name).write_text('')
    (memory / 'spine.md').write_text('# Spine\n' + '- line\n' * 40)
    capsys.readouterr()
    hook(monkeypatch, root)
    lines = context(capsys).splitlines()
    assert lines.index('Active constraints:') < 25
    assert lines.index('Active constraints:') < lines.index('Rules:')


def test_orientation_precedes_integrity_line(root, monkeypatch, capsys):
    calibrated(root)
    from wuwei.registry import Result
    owner = 'plugin integrity: owner-confirmed content (local evidence)'
    monkeypatch.setattr(integrity, 'check', lambda *args, **kwargs: Result(0, None, owner))
    monkeypatch.setattr(integrity, 'workspace_check', lambda *args, **kwargs: Result(0))
    capsys.readouterr()
    assert hook(monkeypatch, root) == 0
    text = context(capsys)
    assert text.startswith(next_command.HEADER)
    assert text.index(owner) > text.index('Next: ')


def test_unmeasured_row_still_prints_block(root, monkeypatch, capsys):
    calibrated(root)

    def broken(root):
        raise ValueError('broken')
    monkeypatch.setattr(next_command, 'step', broken)
    capsys.readouterr()
    assert hook(monkeypatch, root) == 0
    text = context(capsys)
    assert text.startswith(next_command.HEADER)
    assert 'Next: unmeasured: broken ' + next_command.THEN['run'] + '\nwuwei doctor' in text


def test_issue_acceptance_silent_outside_workspace(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    outside = tmp_path / 'outside'
    outside.mkdir()
    monkeypatch.chdir(outside)
    capsys.readouterr()
    assert hook(monkeypatch, outside) == 0
    assert capsys.readouterr().out == ''


BUDGET = 4096  # The issue's fixed SessionStart budget in UTF-8 bytes for a busy day.


def test_issue_acceptance_session_start_budget(root, monkeypatch, capsys):
    import shutil
    build = {'status': 'ready', 'brief': 'briefs/b.md',
             'action': {'action': 'launch', 'prompt': 'LAUNCH-PROMPT ' + 'x' * 4000}}
    approved(root, {f'ITEM-{n}': ('implement', {}) for n in (1, 2, 3)}, cap=3,
             builds={f'ITEM-{n}': build for n in (1, 2, 3)},
             seats={'b1': {'role': 'builder', 'item': 'ITEM-1', 'status': 'running', 'brief': 'briefs/b1.md'}},
             )
    memory = root / '.wuwei/memory'
    (memory / 'notes').mkdir(parents=True)
    for name in ('spine.md', 'index.md', 'goals.md'):
        shutil.copy(Path(__file__).parents[1] / 'templates/workspace/memory' / name, memory / name)
    capsys.readouterr()
    assert hook(monkeypatch, root) == 0
    text = context(capsys)
    assert len(text.encode('utf-8')) <= BUDGET
    for phrase in ('Next: set: ', 'build ITEM-2: wuwei build next ITEM-2', 'Goals: ', 'Plan: ',
                   'Full day state: wuwei why <item>'):
        assert phrase in text
    for phrase in ('LAUNCH-PROMPT', 'Today state:', '"approved_items"'):
        assert phrase not in text
@pytest.mark.parametrize('kind', ['carried', 'parked'])
def test_carried_item_is_skipped(root, capsys, kind):
    approved(root, {'A': ('implement', {'disposition': {'kind': kind, 'reason': 'r'}})})
    found = coarse(root)
    assert found['state'] == 'close' and 'carried' in found['why']
    assert found['command'] != 'wuwei build next A'


def test_resumed_item_whose_build_finished_goes_to_its_gates(root, capsys):
    # #872: parked after its builder finished, resumed: the next round offers its gates.
    from fakes import owner
    from wuwei import plan
    approved(root, {'A': ('implement', {'gates': {'tier': 'standard'}})},
             builds={'A': {'status': 'done', 'action': {'action': 'done'}}})
    plan.park('A', 'scanner chain a -> b', root)
    assert main(['plan', 'resume', 'A']) == 1
    owner.answer_card(root, capsys.readouterr().err)
    assert main(['plan', 'resume', 'A']) == 0
    assert [(launch['kind'], launch['command']) for launch in coarse(root)['launches']] == [
        ('gates', 'wuwei dispatch next A')]


def test_orientation_shows_the_spec_engine_and_mode(monkeypatch):
    monkeypatch.delenv('WUWEI_SEAT_ROLE', raising=False)
    assert 'Spec: speckit strict' in next_command.orientation(ROW, True, 'speckit strict').splitlines()
    assert not any(line.startswith('Spec:') for line in next_command.orientation(ROW, True).splitlines())


def test_item_at_the_gate_gets_verdicts(root, capsys):
    # #841: no docs row, even under a former [docs] config.
    approved(root, {'ITEM-1': ('gate', {'gates': {'tier': 'standard'}})})
    with (root / '.wuwei/config.toml').open('a') as stream:
        stream.write('[docs]\nsystem = "notion"\n')
    assert [launch['kind'] for launch in coarse(root)['launches']] == ['gates']


def test_item_row_shows_the_ticket(root, capsys):
    approved(root, {'ITEM-1': ('implement', {})}, tickets={'ITEM-1': {'id': 'ENG-1', 'source': 'set'}})
    [launch] = coarse(root)['launches']
    assert 'ITEM-1 (ENG-1)' in launch['why'] and launch['command'] == 'wuwei build next ITEM-1'


def test_seats_at_cap_name_the_waiting_item_and_the_first_seat(root, capsys):
    items = {'ITEM-1': ('implement', {}), 'ITEM-2': ('implement', {}), 'ITEM-3': ('planned', {}),
             'ITEM-4': ('planned', {})}
    approved(root, items, cap=3)
    found = coarse(root)
    assert [(launch['kind'], launch['item']) for launch in found['launches']] == [
        ('build', 'ITEM-1'), ('build', 'ITEM-2'), ('build', 'ITEM-3')]
    day(root, seats={name: {'status': 'running', 'role': 'builder', 'item': item, 'started_at': at}
                     for name, item, at in (('b-1', 'ITEM-1', '2026-09-29T11:00:00+00:00'),
                                            ('b-2', 'ITEM-2', '2026-09-29T10:00:00+00:00'))})
    found = coarse(root)
    assert [(launch['kind'], launch['item']) for launch in found['launches']] == [('build', 'ITEM-3')]
    approved(root, items, cap=2)
    day(root, seats={name: {'status': 'running', 'role': 'builder', 'item': item, 'started_at': at}
                     for name, item, at in (('b-1', 'ITEM-1', '2026-09-29T11:00:00+00:00'),
                                            ('b-2', 'ITEM-2', '2026-09-29T10:00:00+00:00'))})
    found = coarse(root)
    assert found['state'] == 'wait'
    assert 'ITEM-3 waits: 2 of CAP 2 building; b-2 started first' in found['why']


# #551 US1.2: next returns the delegate's own action


def test_build_launches_return_the_build_loop_action(root, capsys, monkeypatch):
    from wuwei.commands import build
    approved(root, {'A': ('implement', {})})
    launch = {'action': 'launch', 'prompt': 'WUWEI brief: x', 'agent_type': 'wuwei:builder', 'brief': 'b'}
    monkeypatch.setattr(build, 'next_action', lambda item, root=None: launch)
    code, found = row(capsys)
    assert code == 0 and (found['state'], found['then']) == ('set', next_command.THEN['set'])
    assert found['launches'] == [{'kind': 'build', 'item': 'A', 'goal': 'unplanned', **launch}]
    # #614: a continue is a fresh Agent with the returned prompt; resume only where offered
    assert 'fresh Agent' in next_command.THEN['set'] and 'resume' in next_command.THEN['set']
    # #902: the build loop's done is no launch and no retry line; the next derivation reads it
    monkeypatch.setattr(build, 'next_action', lambda item, root=None: {'action': 'done'})
    code, found = row(capsys)
    assert code == 0 and found['launches'] == []


@pytest.mark.parametrize('answer,action', [
    ({'action': 'gates', 'roles': ['arch'], 'seats': [], 'commands': ['wuwei seat brief arch A arch-A']}, 'gates'),
    ({'action': 'escalate', 'reason': 'gate quality ESCALATE: - P1', 'command': 'wuwei dispatch next A'},
     'decision'),  # #844, #902: an owner decision is the set's decision, never a launch
    ({'action': 'polish', 'gate': 'quality', 'notes': ['n1'], 'command': 'wuwei dispatch polish A',
      'skip': 'wuwei dispatch skip-polish A'}, 'polish'),
])
def test_gate_launches_resolve_through_dispatch_next(root, capsys, monkeypatch, answer, action):
    from wuwei import dispatch
    approved(root, {'A': ('gate', {'worktree': str(root)})})
    monkeypatch.setattr(dispatch, 'next_step', lambda item, root=None: answer)
    found = row(capsys)[1]
    if action == 'decision':
        assert found['launches'] == [] and found['decision']['command'] == answer['command']
        assert answer['reason'] in found['decision']['why']
        return
    [entry] = found['launches']
    assert (entry['kind'], entry['action']) == ('gates', action)
    if action == 'gates':
        assert 'wuwei seat brief arch A arch-A' in last_event(root)['payload']['named']
    if action == 'polish':  # #723
        assert (entry['command'], entry['skip']) == ('wuwei dispatch polish A', 'wuwei dispatch skip-polish A')


def test_an_owner_step_behind_the_sets_decision_is_not_a_launch(root, capsys, monkeypatch):
    # #902 review F4: with a decision already in the set, a launch that resolved to a park for the
    # owner's resume is not left as a command to run; the next derivation asks it.
    from wuwei import dispatch
    approved(root, {'A': ('gate', {'worktree': str(root)}),
                    'B': ('parked', {'status': 'blocked', 'resume_phase': 'delta',
                                     'disposition': {'kind': 'parked', 'reason': 'round cap 2 reached: x'}})})
    monkeypatch.setattr(dispatch, 'next_step', lambda item, root=None: {
        'action': 'escalate', 'reason': 'round cap 2 reached: y', 'command': 'wuwei plan resume A'})
    found = row(capsys)[1]
    assert found['decision']['item'] == 'B' and found['launches'] == []
    assert 'wuwei plan resume A' not in json.dumps(found['launches'])


def test_shepherd_launch_then_its_reason(root, capsys, monkeypatch):
    from wuwei import brief, dispatch
    approved(root, {'A': ('gate', {'worktree': str(root)})})
    monkeypatch.setattr(dispatch, 'next_step', lambda item, root=None: dispatch.raise_action(
        root, state.read_state(root), item, []))
    path = workspace.day_dir(root) / 'briefs/shepherd-A.md'
    path.parent.mkdir()
    path.write_text('brief\n')
    [entry] = row(capsys)[1]['launches']
    assert entry['action'] == 'raise' and entry['seats'] == [brief.seat_action('shepherd', path, str(root), root)]
    day(root, seats={'shepherd-A': {'status': 'stopped', 'role': 'shepherd', 'item': 'A'}})
    [entry] = row(capsys)[1]['launches']  # #902: stopped with no PR: a fresh shepherd seat
    assert entry['action'] == 'raise' and 'shepherd-A-2' in entry['commands'][0]


def test_a_parked_verdict_asks_the_day_again(root, capsys, monkeypatch):
    # Part 14: a PARK verdict or the owner's No parks in code; next moves on to the day.
    from wuwei import dispatch

    def parked(item, root=None):
        day(root, items={'A': {'phase': 'parked', 'status': 'blocked', 'resume_phase': 'gate'}})
        return {'action': 'parked', 'reason': 'gate quality PARK: - P1', 'command': 'wuwei plan resume A'}
    approved(root, {'A': ('gate', {})})
    monkeypatch.setattr(dispatch, 'next_step', parked)
    assert row(capsys)[1]['launches'] == []  # #902: a park is no launch, and no retry line
    assert row(capsys)[1]['state'] == 'close'


def test_a_refused_launch_names_its_reason_and_exits_one(root, capsys, monkeypatch):
    from wuwei import dispatch

    def refuse(item, root=None):
        raise dispatch.Refused('builder must stand down before gates')
    approved(root, {'A': ('gate', {})})
    monkeypatch.setattr(dispatch, 'next_step', refuse)
    code, found = row(capsys)
    [entry] = found['launches']
    assert (code, entry['action'], entry['reason']) == (1, 'refused', 'builder must stand down before gates')


def test_dispatch_and_stuck_launches(root, capsys, monkeypatch):
    from wuwei import dispatch
    approved(root, {'A': ('planned', {})})
    value = {'action': 'set', 'entries': [{'item': 'A', 'action': 'start', 'commands': ['wuwei worktree add A']}]}
    monkeypatch.setattr(dispatch, 'launch_set', lambda root=None: value)
    found = row(capsys)[1]
    assert (found['state'], found['launches']) == ('set', value['entries'])
    assert last_event(root)['payload']['named'] == ['wuwei worktree add A']
    day(root, seats={'b': {'status': 'unmeasured', 'role': 'builder', 'item': 'A'}})
    assert not any(entry.get('kind') == 'stop' or 'seat stop' in entry.get('command', '')
                   for entry in coarse(root).get('launches', []))


# #551: steward and close


def test_no_steward_row_after_tool_calls(root):
    # Part 14: the steward runs at sweep and close only; no tool-call row.
    approved(root, {})
    state.append_event('steward.due', {'tool_calls': 200}, root)
    assert coarse(root)['state'] == 'close'


def test_steward_launches_only_the_newest_brief_and_never_beside_a_running_one(root):
    """#617: stale briefs are never launched and one steward runs at a time."""
    approved(root, {})
    briefs = '.wuwei/days/2026-09-30/briefs'
    for name in ('steward-old', 'steward-new'):
        state.append_event('steward.run', {'trigger': 'sweep', 'brief': f'{briefs}/{name}.md'}, root)
    found = coarse(root)
    assert (found['state'], found['action'], found['brief']) == ('steward', 'launch', f'{briefs}/steward-new.md')
    day(root, seats={'steward-new': {'status': 'running', 'role': 'steward', 'item': 'day'}})
    assert coarse(root)['state'] != 'steward'  # the old brief is never offered
    state.append_event('steward.run', {'trigger': 'sweep', 'brief': f'{briefs}/steward-next.md'}, root)
    assert coarse(root)['state'] != 'steward'  # an unlaunched brief waits while one runs


def test_steward_rows_wait_for_the_fix_round(root):
    """#624: no steward launch while an item is in fix or delta."""
    approved(root, {'A': ('fix', {})}, seats={'b': {'status': 'running', 'role': 'builder', 'item': 'A'}})
    state.append_event('steward.run', {'trigger': 'sweep', 'brief': 'b/steward-s.md', 'tool_calls': 0}, root)
    assert coarse(root)['state'] != 'steward'  # no launch row
    day(root, items={'A': {'phase': 'delta'}},
        seats={'g': {'status': 'running', 'role': 'gate', 'item': 'A'}})
    assert coarse(root)['state'] != 'steward'
    day(root, items={'A': {'phase': 'merged'}})
    assert (coarse(root)['state'], coarse(root)['brief']) == ('steward', 'b/steward-s.md')


def test_close_path(root, capsys):
    approved(root, {'A': ('merged', {})}, decision_routes={'D-1': 'owner'})
    states = []

    def expect(name, command, action='run'):
        found = coarse(root)
        assert (found['state'], found['action'], found.get('command')) == (name, action, command), found
        states.append(found)
        state.append_event('next.action', {'state': name, 'item': found.get('item', ''),
                                           'done': [[name, found.get('item', '')]]}, root)
    expect('close', 'wuwei close')
    day(root, close_requested=True)
    expect('close', 'wuwei close')  # part 14: no decision record holds the close
    state.append_event('steward.run', {'trigger': 'close', 'brief': 'b/steward-c.md'}, root)
    day(root, seats={'steward-c': {'status': 'stopped', 'role': 'steward', 'item': 'day'}})
    expect('retro', 'wuwei retro')
    (workspace.day_dir(root) / 'retro').mkdir()
    (workspace.day_dir(root) / 'retro/2026-09-30.md').write_text('# Retro\n')
    expect('promote', 'wuwei retro --promote')
    expect('retro-applied', 'wuwei retro')
    with (root / '.wuwei/config.toml').open('a') as stream:
        stream.write('[outbound]\nowner_channel = "dm"\n[outbound.owner.slack]\nuser = "U1"\ndm = "D9"\n')
    expect('report', 'wuwei report')
    assert "owner's DM D9" in states[-1]['then']
    (workspace.day_dir(root) / 'report.md').write_text('# Report\n')
    found = coarse(root)  # #844: the summary duty to the owner's DM comes due with the report
    assert [(row['duty'], row['item']) for row in found['duties']] == [('summary', 'day')]
    state.append_event('duty.done', {'item': 'day', 'duty': 'summary', 'evidence': 'dm'}, root)
    expect('closed', 'wuwei close')
    state.append_event('day.closed', {}, root)
    expect('done', None, 'done')


def ran(root, command):
    """The planner's Bash span for a command it ran, as the PostToolUse trace guard writes it."""
    from wuwei.guards import traces
    traces._record({'session_id': 'S', 'cwd': str(root), 'tool_name': 'Bash',
                    'tool_input': {'command': command}}, root)


def test_a_once_row_is_done_when_its_command_ran_not_when_returned(root, capsys):
    calibrated(root)
    day(root, planner_session_id='S')
    for _ in range(2):  # asking again is not doing it
        assert row(capsys)[1]['state'] == 'pr-flow'
    events = (workspace.day_dir(root) / 'events.jsonl').read_text()
    capsys.readouterr()
    assert main(['next']) == 0  # a person's look-up records nothing
    assert (workspace.day_dir(root) / 'events.jsonl').read_text() == events
    ran(root, '/opt/wuwei/bin/wuwei doctor --section pr-flow')
    assert row(capsys)[1]['state'] == 'lead'
    assert last_event(root)['payload']['done'] == [['pr-flow', '']]


def test_pr_flow_compound_run_explains_standalone_requirement(root, capsys):
    calibrated(root)
    day(root, planner_session_id='S')
    found = row(capsys)[1]
    assert found['state'] == 'pr-flow'
    ran(root, 'cd project; wuwei doctor --section pr-flow')
    repeated = row(capsys)[1]
    assert repeated['state'] == 'pr-flow'
    assert 'as its own command' in repeated['then']
    ran(root, 'wuwei doctor --section pr-flow')
    assert row(capsys)[1]['state'] == 'lead'


def test_pr_flow_doctor_in_compound_command_records_completion(root, capsys, monkeypatch):
    from wuwei.commands import doctor
    calibrated(root)
    day(root, planner_session_id='S')
    assert row(capsys)[1]['state'] == 'pr-flow'
    monkeypatch.setattr(doctor, '_hand_over', lambda args: [])
    main(['doctor', '--section', 'pr-flow'])
    ran(root, 'cd project && wuwei doctor --section pr-flow')
    assert row(capsys)[1]['state'] == 'lead'


def test_a_once_row_returned_three_times_is_done(root, capsys):
    calibrated(root)
    day(root, planner_session_id='S')
    # ponytail: a once-row returned three times counts as done, so a refused or failed command
    # (no PostToolUse span) never holds the day.
    for _ in range(3):
        assert row(capsys)[1]['state'] == 'pr-flow'
    assert row(capsys)[1]['state'] == 'lead'


def test_gate_imports_yesterday_when_it_left_unfinished_items(root, capsys):
    proposed_day = workspace.day_dir(root)
    planned(root)
    day(root, planner_session_id='S')
    prior = root / '.wuwei/days/2026-09-29'
    prior.mkdir()
    (prior / 'state.json').write_text(json.dumps({**state.read_state(root), 'items': {
        'OLD-1': {'phase': 'implement', 'status': 'running'}, 'OLD-2': {'phase': 'merged', 'status': 'done'}}}))
    (proposed_day / 'proposal.json').write_text(json.dumps({'candidates': [{'id': 'A'}]}))
    assert coarse(root)['command'] == 'wuwei plan gate --import-yesterday'
    (proposed_day / 'proposal.json').write_text(json.dumps({'candidates': [{'id': 'OLD-1'}]}))
    assert coarse(root)['command'] == 'wuwei plan gate'  # the lead proposed it again: no import


# #666: a PR waiting on people never hides work that can run now


QUEUE = [('build', 'A', 'wuwei build next A'), ('verdicts', 'B', 'wuwei dispatch next B'),
         ('pr', 'P', 'wuwei pr act example/project#7')]


def waiting_pr_day(root):
    approved(root, {'P': ('raised', {'pr': 'example/project#7'}), 'A': ('fix', {}), 'B': ('delta', {})}, cap=2)


def test_issue_acceptance_runnable_rounds_beside_a_pr(root):
    waiting_pr_day(root)
    for _ in range(3):  # the state is read fresh each call, and the answer stays put
        found = coarse(root)
        assert [(launch['kind'], launch['item']) for launch in found['launches']] == [
            ('pr', 'P'), ('fix', 'A'), ('gates', 'B')]
        assert [(r['state'], r['item'], r['command']) for r in found['rows']] == QUEUE


def test_text_mode_names_every_launch(root, capsys):
    waiting_pr_day(root)
    text = next_command.text(coarse(root))
    assert 'fix A: wuwei build next A' in text and 'gates B: wuwei dispatch next B' in text


@pytest.mark.parametrize('later,row', [(None, 'merge'), ('intent', 'pr'), ('wait', 'pr')])
def test_an_owner_merge_block_is_one_owner_decision(root, later, row):
    # #816: the merge policy does not clear the PR; the owner decides on its Owner step card.
    approved(root, {'P': ('raised', {'pr': 'example/project#7'})})
    state.append_event('merge.policy_blocked', {'pr': 'example/project#7', 'exit': 1, 'owner': True,
                                                'reason': 'merge policy: owner decides: merge.auto is off'}, root)
    if later == 'intent':
        state.append_event('merge.intent', {'pr': 'example/project#7'}, root)
    elif later == 'wait':
        state.append_event('merge.policy_blocked', {'pr': 'example/project#7', 'exit': 1, 'owner': False,
                                                    'reason': 'merge policy: waits: quiet hours'}, root)
    found = coarse(root)
    if row == 'merge':
        assert found['launches'] == [] and found['decision']['command'] == 'wuwei merge example/project#7'
        assert 'wuwei plan park P --reason "the owner keeps the merge of example/project#7"' in found['decision']['then']
    else:
        assert found['decision'] is None
        assert [(launch['kind'], launch['item']) for launch in found['launches']] == [('pr', 'P')]


def test_a_pr_waiting_on_people_comes_after_the_steward(root):
    approved(root, {'P': ('raised', {'pr': 'example/project#7'})})
    (workspace.day_dir(root) / 'prs.json').write_text(json.dumps({'fetched_at': NOW, 'pulls': [
        {'ref': 'example/project#7', 'state': 'open', 'checks': 'pending', 'labels': []}]}))
    found = coarse(root)
    # #887: only PRs wait: next names the blocking pr wait, run in the background
    assert (found['state'], found['command'], found['action']) == ('wait', 'wuwei pr wait', 'background')
    assert 'P' in found['why'] and 'in the background' in found['then']
    state.append_event('steward.run', {'trigger': 'sweep', 'brief': 'b/steward-s.md'}, root)
    assert coarse(root)['state'] == 'steward'


def test_a_fix_round_with_due_review_activity_is_a_wait_not_a_duty_row(root):
    # #906 D1: during a fix round (builder running) the shepherd duty is no row to run; next waits.
    approved(root, {'P': ('fix', {'pr': 'example/project#7', 'worktree': str(root)})},
             raised_prs=['example/project#7'])
    (workspace.day_dir(root) / 'prs.json').write_text(json.dumps({'fetched_at': NOW, 'pulls': [
        {'ref': 'example/project#7', 'state': 'open', 'checks': 'pending', 'labels': [], 'head': 'abc1234def',
         'activity_at': '2026-09-30T09:30:00Z'}]}))
    day(root, seats={'b': {'status': 'running', 'role': 'builder', 'item': 'P'}}, builds={'P': {'status': 'running'}})
    found = coarse(root)
    assert found['state'] == 'wait' and 'duties' not in found


def test_review_activity_launches_one_shepherd_seat_per_revision(root, capsys):
    # #906: repeated next calls give the brief command, then the seat launch, then nothing more for
    # that revision; the shepherd duty is never a record to write by hand.
    import shlex
    from wuwei import brief
    approved(root, {'P': ('raised', {'pr': 'example/project#7', 'worktree': str(root)})},
             raised_prs=['example/project#7'])
    (workspace.day_dir(root) / 'prs.json').write_text(json.dumps({'fetched_at': NOW, 'pulls': [
        {'ref': 'example/project#7', 'state': 'open', 'checks': 'pending', 'labels': [],
         'activity_at': '2026-09-30T09:30:00Z'}]}))
    found = coarse(root)
    assert [(launch['kind'], launch['item']) for launch in found['launches']] == [('shepherd', 'P')]
    assert found['duties'] == []
    [entry] = row(capsys)[1]['launches']
    [command] = entry['commands']
    assert entry['action'] == 'shepherd' and entry['seats'] == []
    assert command.startswith('wuwei seat brief shepherd P shepherd-P-20260930093000 ')  # no head listed
    body = shlex.split(command)[-1]
    assert '--thread <id> --reply' in body and '--fix' in body and '--scope' in body
    path = workspace.day_dir(root) / 'briefs/shepherd-P-20260930093000.md'
    path.parent.mkdir()
    path.write_text(body + '\n')  # the brief command needs a git worktree; its body is checked above
    [entry] = row(capsys)[1]['launches']
    assert entry['seats'] == [brief.seat_action('shepherd', path, str(root), root)]
    day(root, seats={'shepherd-P-20260930093000': {'status': 'running', 'role': 'shepherd', 'item': 'P'}})
    found = coarse(root)
    assert found['state'] == 'wait' and 'duties' not in found  # the running seat answers it
    # F1: a seat that stopped with a reply still owed (after --fix, a scope No, or a dead seat)
    # leaves the duty on next's list, with pr act as its step, never a silent wait
    day(root, seats={'shepherd-P-20260930093000': {'status': 'stopped', 'role': 'shepherd', 'item': 'P'}})
    found = coarse(root)
    assert found['launches'] == [] and [(duty['item'], duty['duty'], duty['record']) for duty in found['duties']] == [
        ('P', 'shepherd', 'wuwei pr act example/project#7')]


def test_json_rows_survive_resolution(root, capsys, monkeypatch):
    from wuwei.commands import build
    waiting_pr_day(root)
    launch = {'action': 'launch', 'prompt': 'WUWEI brief: x', 'agent_type': 'wuwei:builder', 'brief': 'b'}
    monkeypatch.setattr(build, 'next_action', lambda item, root=None: launch)
    found = row(capsys)[1]
    assert found['state'] == 'set' and found['rows'] == coarse(root)['rows']


def test_finding_launch(root, capsys):
    """#646: a seat's finding is proposed once as a small item."""
    approved(root, {})
    before = coarse(root)
    assert before['state'] != 'set'
    assert main(['seat', 'note', '--fix', 'Pin ruff in CI']) == 0
    [launch] = coarse(root)['launches']
    assert (launch['kind'], launch['item'], launch['command']) == (
        'finding', 'fix-pin-ruff-in-ci', 'wuwei plan add fix-pin-ruff-in-ci --from-finding')
    assert 'Pin ruff in CI' in launch['why']
    day(root, items={'fix-pin-ruff-in-ci': {'phase': 'merged'}})
    assert coarse(root) == before
    assert main(['seat', 'note', '--fix', 'Pin black']) == 0
    assert coarse(root)['launches'][0]['item'] == 'fix-pin-black'
    state.append_event('next.action', {'state': 'x', 'item': '',
                                       'done': [['finding', 'fix-pin-black']]}, root)
    assert coarse(root) == before


def test_a_finding_launch_names_the_selection_it_needs(root, capsys):
    # #908 F3: with several goals and repositories a finding that names neither is offered with
    # both selections, so the planner never runs a step plan add refuses.
    approved(root, {'A': ('implement', {'goal': 'G-2', 'repo': 'acme/web'})}, goals=['G-1', 'G-2'])
    (root / '.wuwei/config.toml').write_text(''.join(
        f'[[repos]]\nname = "acme/{name}"\npath = "{name}"\ndefault_branch = "main"\n' for name in ('app', 'web')))
    assert main(['seat', 'note', '--fix', 'Pin ruff in CI']) == 0
    assert main(['seat', 'note', '--fix', 'Pin black', '--item', 'A']) == 0
    commands = {launch['item']: launch['command'] for launch in coarse(root)['launches'] if launch['kind'] == 'finding'}
    assert commands == {
        'fix-pin-ruff-in-ci': 'wuwei plan add fix-pin-ruff-in-ci --from-finding --goal <one of G-1, G-2> '
                              '--repo <one of acme/app, acme/web>',
        'fix-pin-black': 'wuwei plan add fix-pin-black --from-finding'}


def due(root, item, action, then=None):
    payload = {'item': item, 'duty': f'tracker.{action}', 'ticket': 'ENG-7'}
    state.append_event('duty.due', {**payload, 'command': f'wuwei tracker move {item} {action}'}, root)
    if then:
        state.append_event(then, {**payload, **({'pr': None} if then == 'duty.done' else {'error': 'x'})}, root)


def test_an_open_tracker_duty_is_listed_beside_the_launches(root):
    """#842: a due tracker update is a duty, also for a merged item, and holds close."""
    (root / '.wuwei/config.toml').write_text(
        '[adapters]\ntracker = "linear"\n[[repos]]\nname = "example/project"\npath = "project"\n'
        'default_branch = "main"\n')
    (workspace.day_dir(root) / 'plan.md').write_text('# Plan\n')
    day(root, gate_approved=True, approved_items=['A', 'M'], cap=2, planner_session_id='S',
        items={'A': {'phase': 'fix'}, 'M': {'phase': 'merged', 'pr': 'example/project#7'}},
        tickets={'M': {'id': 'ENG-7', 'source': 'set'}})
    due(root, 'M', 'done')
    due(root, 'A', 'claim', 'duty.done')
    due(root, 'M', 'in_review', 'duty.skipped')
    found = coarse(root)
    assert [(launch['kind'], launch['item']) for launch in found['launches']] == [('fix', 'A')]
    duty = [('tracker.done', 'M', 'wuwei tracker move M done')]
    assert [(row['duty'], row['item'], row['record']) for row in found['duties']] == duty
    day(root, items={'M': {'phase': 'merged', 'pr': 'example/project#7'}}, approved_items=['M'])
    found = coarse(root)
    assert found['launches'] == [] and [(row['duty'], row['item'], row['record']) for row in found['duties']] == duty
    config = root / '.wuwei/config.toml'
    config.write_text(config.read_text().replace('tracker = "linear"', 'tracker = "none"'))
    assert coarse(root)['state'] == 'close'

def test_waits_next_to_a_window_hold_still_give_the_timed_wait(root, capsys, monkeypatch):
    # #845 F1: a CAP or gate wait without until beside a window hold is no dead end.
    from wuwei import dispatch
    approved(root, {'ITEM-2': ('planned', {})}, cap=2)
    monkeypatch.setattr(dispatch, 'launch_set', lambda root: {'capacity': '', 'entries': [
        {'kind': 'build', 'item': 'A', 'action': 'wait', 'reason': 'claude window', 'until': '2026-09-30T13:00:00+00:00'},
        {'kind': 'build', 'item': 'B', 'action': 'wait', 'reason': 'CAP 1 reached'}]})
    code, found = row(capsys)
    assert (found['state'], found['action'], found['until']) == ('wait', 'background', '2026-09-30T13:00:00+00:00')


def test_a_set_held_by_the_memory_floor_is_a_timed_wait(root, capsys, monkeypatch):
    # #898: below host.min_free_memory_pct next sleeps briefly, then offers the launch again
    from wuwei.guards import agent_launch
    approved(root, {'ITEM-2': ('planned', {})}, cap=2)
    with (root / '.wuwei/config.toml').open('a') as stream:
        stream.write('[host]\nmin_free_memory_pct = 40\n')
    monkeypatch.setattr(agent_launch, 'free_percent', lambda config, root: 38)
    code, found = row(capsys)
    assert (code, found['state'], found['action']) == (0, 'wait', 'background'), found
    assert found['until'] == '2026-09-30T10:01:00+00:00' and found['command'] == 'sleep 121'
    assert 'held: free memory 38% < 40%' in found['why']
    monkeypatch.setattr(agent_launch, 'free_percent', lambda config, root: 41)
    code, found = row(capsys)
    assert found['state'] == 'set' and [launch['action'] for launch in found['launches']] == ['start']


def test_a_set_held_only_by_a_spent_window_is_a_timed_wait(root, capsys, monkeypatch):
    # #845 US1: no launch fits the window, nothing else is due: next sleeps past the reset.
    from wuwei import derive
    approved(root, {'ITEM-2': ('planned', {})}, cap=2)
    (root / '.wuwei/windows.json').write_text(json.dumps({'claude': {'five_hour': {
        'used_percent': 100, 'resets_at': '2026-09-30T13:00:00+00:00'}}}))
    code, found = row(capsys)
    assert (code, found['state'], found['action']) == (0, 'wait', 'background'), found
    assert found['until'] == '2026-09-30T13:00:00+00:00' and found['then'] == next_command.THEN['background']
    assert found['command'].startswith('sleep ') and int(found['command'].split()[1]) >= 3 * 3600
    assert 'claude' in found['why'] and 'wuwei next' in found['why']
    duty = {'duty': 'ping', 'item': 'ITEM-2', 'prompt': 'Ping.', 'record': 'wuwei duty done ITEM-2 ping'}
    monkeypatch.setattr(derive, 'duties', lambda *args, **kwargs: [duty])
    code, found = row(capsys)
    assert found['state'] == 'set' and found['duties'] == [duty]
    assert [launch.get('until') for launch in found['launches']] == ['2026-09-30T13:00:00+00:00']
    monkeypatch.undo()
    monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
    monkeypatch.setenv('WUWEI_NOW', '2026-09-30T13:30:00+00:00')
    code, found = row(capsys)
    assert found['state'] == 'set' and [launch['action'] for launch in found['launches']] == ['start']


def test_issue_acceptance_907_an_unchanged_next_makes_no_remote_call(root, capsys, monkeypatch):
    # #907, #900: a three-repository day with thirteen PR lanes. The first next reads each
    # repository's listing once; one repository fails (HTTP 502) and the other two stay usable.
    # An unchanged next inside pr.poll_seconds calls nothing; the failed repository's PR rows are
    # unmeasured and next names it and when it reads it again.
    from wuwei import registry
    from wuwei.registry import Result
    repos = ('example/one', 'example/two', 'example/three')
    calls = []

    class Host:
        def __getattr__(self, name):
            def call(*args, **kwargs):
                calls.append((name, args[0]))
                if name == 'pulls' and args[0] != 'example/two':
                    return Result(0, [{'number': n, 'state': 'open', 'head': 'a' * 40, 'checks': 'pending',
                                       'mergeable': 'mergeable', 'labels': []} for n in range(1, 6)])
                return Result(2, None, 'gh: HTTP 502')
            return call
    monkeypatch.setattr(registry, 'load', lambda kind, config: Host())
    approved(root, {f'I{i}': ('raised', {'pr': f'{repos[i % 3]}#{i // 3 + 1}'}) for i in range(13)}, cap=13)
    (root / '.wuwei/config.toml').write_text(''.join(
        f'[[repos]]\nname = "{name}"\npath = "{name[8:]}"\ndefault_branch = "main"\n' for name in repos))
    (workspace.day_dir(root) / 'prs.json').write_text(json.dumps({  # an hour old, written before #907
        'fetched_at': '2026-09-30T09:00:00+00:00', 'pulls': [
            {'ref': f'{name}#{n}', 'number': n, 'state': 'open', 'head': 'a' * 40, 'checks': 'red',
             'mergeable': 'mergeable', 'labels': []} for name in repos for n in range(1, 6)]}))
    code, found = row(capsys)
    assert sorted(calls) == sorted(('pulls', name) for name in repos)
    assert found['state'] == 'wait'
    unmeasured = [entry['item'] for entry in found['rows'] if entry['state'] == 'unmeasured']
    assert unmeasured == ['I1', 'I4', 'I7', 'I10']
    assert 'example/two' in found['why'] and 'HTTP 502' in found['why'] and '10:02:00' in found['why']
    shown = next_command.text({**found, 'state': 'set', 'launches': [], 'duties': [], 'decision': None})
    assert 'unmeasured I1: PR example/two#1 is unmeasured' in shown
    calls.clear()
    for _ in range(3):
        assert row(capsys)[1] == found
    assert calls == []
