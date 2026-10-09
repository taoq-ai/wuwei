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
    state._write_state(lambda data: None, tmp_path, reserved=False)
    return tmp_path


def calibrated(root):
    (root / '.wuwei/config.toml').write_text(
        '[[repos]]\nname = "example/project"\npath = "project"\ndefault_branch = "main"\n')
    (root / '.wuwei/calibration.json').write_text('{"example/project": {}}')


def planned(root):
    calibrated(root)
    (workspace.day_dir(root) / 'plan.md').write_text('# Plan\n')


def day(root, **fields):
    """Write today's state as given; phases skip the transition checks a fixture does not need."""
    data = {**state.read_state(root), **fields}
    path = workspace.day_dir(root) / 'state.json'
    path.unlink()
    path.write_text(json.dumps(data))


def approved(root, items, cap=1, **extra):
    planned(root)
    day(root, gate_approved=True, approved_items=list(items), cap=cap, planner_session_id='S',
        items={name: {'phase': phase, **fields} for name, (phase, fields) in items.items()},
        **extra)
    seen(root, 'calibrate', 'telemetry')


def row(capsys, *args):
    capsys.readouterr()
    code = main(['next', '--json', *args])
    return code, json.loads(capsys.readouterr().out)


def coarse(root):
    """The hook-safe row before delegation."""
    return next_command.step(root)


SHAPE = {'state', 'action', 'command', 'why', 'then'}


# US1: wuwei next


def test_setup_rows(root, capsys):
    code, found = row(capsys)
    assert code == 0 and set(found) == SHAPE and found['action'] == 'card'
    assert (found['state'], found['command']) == ('setup', 'bin/wuwei setup')
    assert 'host terminal' in found['why'] and found['then'] == next_command.THEN['owner']
    (root / '.wuwei/config.toml').write_text(
        '[[repos]]\nname = "example/project"\npath = "project"\ndefault_branch = "main"\n')
    assert row(capsys)[1]['state'] == 'setup'


def test_setup_row_outside_workspace(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    monkeypatch.chdir(tmp_path)
    code, found = row(capsys)
    assert code == 0 and set(found) == SHAPE and found['action'] == 'card'
    assert (found['state'], found['command']) == ('no-workspace', 'bin/wuwei setup --shadow')
    capsys.readouterr()
    assert main(['next']) == 0
    assert capsys.readouterr().out == f"no-workspace: {found['why']} {found['then']}\nbin/wuwei setup --shadow\n"


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
    for command in ('wuwei doctor --section pr-flow', 'wuwei mcp check'):
        found = row(capsys)[1]
        seen_rows.append(found)
        assert (found['action'], found['command']) == ('run', command)
        payload = last_event(root)['payload']
        assert {key: payload[key] for key in ('state', 'action', 'item', 'named')} == {
            'state': found['state'], 'action': 'run', 'item': '', 'named': [command]}
        ran(root, command)  # done when its command ran, not when it was returned
    found = row(capsys)[1]
    seen_rows.append(found)
    assert found['state'] == 'lead' and found['command'].startswith('wuwei brief lead day lead --body ')
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


def test_cards_after_the_gate_come_once(root, capsys):
    planned(root)
    day(root, gate_approved=True, planner_session_id='S', decision_routes={'D-1': 'owner'})
    (workspace.day_dir(root) / 'goals.md').write_text('# Goals\n')
    from test_decision import VALID
    (workspace.day_dir(root) / 'decisions').mkdir()
    (workspace.day_dir(root) / 'decisions/D-1.md').write_text(VALID.replace('Decided-by: seat', 'Decided-by: owner'))
    found = row(capsys)[1]
    assert found['command'] == 'wuwei goals edit --file .wuwei/days/2026-09-30/goals.md'
    ran(root, found['command'])
    found = row(capsys)[1]
    # Calibration asks what setup did not cover, whatever the day (#530); this fixture has every
    # answer unasked, so the card carries the printed questions.
    assert (found['state'], found['action']) == ('calibrate', 'card') and found['widget']
    assert 'Next: line' in found['then'] and 'calibrate --interview allowlist' in found['then']
    ran(root, found['widget'][0]['record'].replace('<label>', 'x'))
    # Telemetry prints [] here: passed in the same call, so the decision comes next.
    found = row(capsys)[1]
    assert (found["state"], found["action"], found.get("item")) == ("decision", "card", "D-1"), found
    passed = [json.loads(line)['payload'] for line in
              (workspace.day_dir(root) / 'events.jsonl').read_text().splitlines()
              if json.loads(line)['kind'] == 'next.action']
    assert ('telemetry', 'pass') in [(row['state'], row['action']) for row in passed]
    assert row(capsys)[1]['state'] == 'decision'  # unanswered: asked again
    ran(root, found['widget'][0]['record'].replace('<label>', 'x'))
    assert row(capsys)[1]['state'] == 'close'


def test_next_records_only_with_day_state(root, capsys):
    calibrated(root)
    for name in ('state.json', 'state.snapshot.json'):
        (workspace.day_dir(root) / name).unlink(missing_ok=True)
    found = row(capsys)[1]
    assert found['state'] == 'session', found
    assert 'next.action' not in (workspace.day_dir(root) / 'events.jsonl').read_text()


@pytest.mark.parametrize('kind,producer', [('next.action', 'wuwei next'), ('day.closed', 'wuwei close')])
def test_path_events_are_reserved(root, capsys, kind, producer):
    capsys.readouterr()
    assert main(['event', kind, '{}']) == 1
    assert f'{kind}: reserved; written by {producer}' in capsys.readouterr().err


def test_decision_row(root, capsys):
    approved(root, {}, decision_routes={'D-1': 'owner'})
    found = coarse(root)
    assert (found['state'], found['command']) == ('decision', 'wuwei decision show D-1 --widget')
    seen(root, 'decision')
    assert coarse(root)['state'] == 'decision'  # once per D-n: the key is the record id
    state.append_event('next.action', {'state': 'x', 'item': '', 'done': [['decision', 'D-1']]}, root)
    assert coarse(root)['state'] != 'decision'
    state._write_state(lambda data: data.update(
        decision_outcomes={'D-1': {'option': 'A', 'decided_by': 'owner'}}), root, reserved=False)
    assert coarse(root)['state'] != 'decision'


@pytest.mark.parametrize('phase,fields,expected,command', [
    ('planned', {}, 'dispatch', 'wuwei dispatch next --all'),
    ('implement', {}, 'build', 'wuwei build next ITEM-1'),
    ('fix', {}, 'build', 'wuwei build next ITEM-1'),
    ('gate', {}, 'verdicts', 'wuwei dispatch next ITEM-1'),
    ('delta', {}, 'verdicts', 'wuwei dispatch next ITEM-1'),
    ('raised', {'pr': 'example/project#7'}, 'pr', 'wuwei pr act example/project#7'),
])
def test_item_rows(root, capsys, phase, fields, expected, command):
    approved(root, {'ITEM-1': (phase, fields)})
    found = coarse(root)
    assert (found['state'], found['command']) == (expected, command)
    if expected == 'dispatch':
        assert '1 planned item(s) can start, 0 of CAP 1 building' in found['why']
        assert found['action'] == 'set'


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
    assert (found['state'], found['command']) == ('dispatch', 'wuwei dispatch next --all')


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
    assert (found['state'], found['command']) == ('build', 'wuwei build next C')


def test_first_approved_item_wins_and_missing_is_skipped(root, capsys):
    approved(root, {'ITEM-2': ('gate', {}), 'ITEM-1': ('implement', {})})
    day(root, approved_items=['ITEM-0', 'ITEM-2', 'ITEM-1'])
    assert coarse(root)['command'] == 'wuwei dispatch next ITEM-2'


def test_end_of_day_rows(root, capsys, monkeypatch):
    approved(root, {})
    assert coarse(root)['command'] == 'wuwei close'
    approved(root, {'ITEM-1': ('merged', {}), 'ITEM-2': ('parked', {'resume_phase': 'implement'}),
                    'ITEM-3': ('escalated', {'resume_phase': 'implement'})})
    found = coarse(root)
    assert (found['state'], found['command']) == ('close', 'wuwei close')
    state.append_event('watch: clock', {}, root)
    monkeypatch.setenv('WUWEI_NOW', '2026-09-30T12:00:00+00:00')
    found = coarse(root)
    assert (found['state'], found['command']) == ('doctor', 'wuwei doctor')
    monkeypatch.setenv('WUWEI_NOW', '2026-09-30T10:01:00+00:00')
    state.append_event('heartbeat: clock', {'health': 'degraded', 'page': 'x'}, root)
    assert coarse(root)['state'] == 'doctor'
    state.append_event('heartbeat: clock', {'health': 'ok', 'page': ''}, root)
    seen(root, 'doctor')  # the doctor row comes once a day
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


@pytest.mark.parametrize('posture,phrases', [
    ('observe', ('Observe posture is on', 'bin/wuwei shadow report')),
    ('guarded', ('Posture guarded',)), ('strict', ('Posture strict',))])
def test_orientation_block(monkeypatch, posture, phrases):
    monkeypatch.delenv('WUWEI_SEAT_ROLE', raising=False)
    text = next_command.orientation(ROW, posture, 'speckit strict', 'S')
    assert text.startswith(next_command.HEADER) and len(text.splitlines()) < 30
    shown = next_command.text(ROW).replace('<session id>', 'S')
    for phrase in ('Next: ' + shown, next_command.LOOP, 'wuwei guide', '\nwuwei plan session S\n',
                   'docs/site/daily.md', 'first word of a plain command', *phrases):
        assert phrase in text
    for phrase in ('SKILL.md', 'Do this now.', 'docs/site/agent.md', 'Start or resume'):
        assert phrase not in text
    assert '<session id>' in next_command.orientation(ROW, posture)


def test_orientation_by_state(monkeypatch):
    monkeypatch.delenv('WUWEI_SEAT_ROLE', raising=False)
    close = next_command.orientation(next_command._row('close', 'Close.', 'wuwei close'), 'guarded')
    assert next_command.LOOP in close and '\nwuwei close\n' in close and 'plan session' not in close
    stuck = next_command.orientation(next_command._row(
        'stuck', 'Seat builder-1 ended with no recorded result.',
        'wuwei seat stop builder-1 --unmeasured "seat ended with no recorded result"'), 'guarded', None, 'S')
    assert 'wuwei seat stop' in stuck and 'wuwei guide' in stuck
    for phrase in ('/wuwei:', 'plan session', 'SKILL.md'):
        assert phrase not in stuck


@pytest.mark.parametrize('role,seat', [('shepherd', True), ('../x', False), ('nope', False),
                                       ('_common', False)])
def test_orientation_seat_entry(monkeypatch, role, seat):
    monkeypatch.setenv('WUWEI_SEAT_ROLE', role)
    text = next_command.orientation(ROW, 'guarded')
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
    assert 'wuwei guide' in text and 'wuwei plan session S' in lines and next_command.LOOP in lines
    reference = next(index for index, line in enumerate(lines) if line.startswith('Reference: wuwei guide'))
    assert reference < 30 and lines.index('Active constraints:') == reference + 1


def test_constraints_precede_a_long_week_digest(root, monkeypatch, capsys):
    calibrated(root)
    memory = root / '.wuwei/memory'
    (memory / 'notes').mkdir(parents=True)
    (memory / 'digests').mkdir()
    (memory / 'digests/2026-W40.md').write_text('# Week 2026-W40\n' + '- line\n' * 40)
    for name in ('spine.md', 'index.md', 'goals.md'):
        (memory / name).write_text('')
    capsys.readouterr()
    hook(monkeypatch, root)
    lines = context(capsys).splitlines()
    assert lines.index('Active constraints:') < 25
    assert lines.index('Active constraints:') < lines.index('Digests:')


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
             decision_routes={'D-1': {}, 'D-2': {}})
    memory = root / '.wuwei/memory'
    (memory / 'notes').mkdir(parents=True)
    for name in ('spine.md', 'index.md', 'goals.md'):
        shutil.copy(Path(__file__).parents[1] / 'templates/workspace/memory' / name, memory / name)
    capsys.readouterr()
    assert hook(monkeypatch, root) == 0
    text = context(capsys)
    assert len(text.encode('utf-8')) <= BUDGET
    for phrase in ('Next: decision: ', 'Open decisions: D-1, D-2', 'Goals: ', 'Plan: ',
                   'Full day state: wuwei state get'):
        assert phrase in text
    for phrase in ('LAUNCH-PROMPT', 'Today state:', '"approved_items"'):
        assert phrase not in text
@pytest.mark.parametrize('decided_by', ['seat', 'owner'])
def test_carried_item_is_skipped(root, capsys, decided_by):
    approved(root, {'A': ('implement', {})}, decision_outcomes={'D-1': {
        'decided_by': decided_by, 'item_disposition': 'carried A', 'option': 'carry'}})
    found = coarse(root)
    if decided_by == 'seat':
        assert found['state'] == 'close' and 'carried' in found['why']
        assert found['command'] != 'wuwei build next A'
    else:
        assert (found['state'], found['command']) == ('build', 'wuwei build next A')


def test_orientation_shows_the_spec_engine_and_mode(monkeypatch):
    monkeypatch.delenv('WUWEI_SEAT_ROLE', raising=False)
    assert 'Spec: speckit strict' in next_command.orientation(ROW, 'guarded', 'speckit strict').splitlines()
    assert not any(line.startswith('Spec:') for line in next_command.orientation(ROW, 'guarded').splitlines())


@pytest.mark.parametrize('system,fields,expected', [
    ('notion', {'gates': {'tier': 'standard'}}, 'docs'),
    ('notion', {'gates': {'tier': 'standard'}, 'docs': {'value': 'new', 'reason': ''}}, 'verdicts'),
    ('notion', {'gates': {'tier': 'light'}}, 'verdicts'),
    ('none', {'gates': {'tier': 'standard'}}, 'verdicts'),
])
def test_docs_row(root, capsys, system, fields, expected):
    approved(root, {'ITEM-1': ('gate', fields)})
    with (root / '.wuwei/config.toml').open('a') as stream:
        stream.write(f'[docs]\nsystem = "{system}"\n')
    found = coarse(root)
    assert found['state'] == expected
    if expected == 'docs':
        assert found['command'].startswith('wuwei plan set ITEM-1 docs=')


def test_item_row_shows_the_ticket(root, capsys):
    approved(root, {'ITEM-1': ('implement', {})}, tickets={'ITEM-1': {'id': 'ENG-1', 'source': 'set'}})
    found = coarse(root)
    assert 'ITEM-1 (ENG-1)' in found['why'] and found['command'] == 'wuwei build next ITEM-1'


def test_seats_at_cap_name_the_waiting_item_and_the_first_seat(root, capsys):
    items = {'ITEM-1': ('implement', {}), 'ITEM-2': ('implement', {}), 'ITEM-3': ('planned', {}),
             'ITEM-4': ('planned', {})}
    approved(root, items, cap=3)
    found = coarse(root)
    assert found['state'] == 'build'
    day(root, seats={name: {'status': 'running', 'role': 'builder', 'item': item, 'started_at': at}
                     for name, item, at in (('b-1', 'ITEM-1', '2026-09-29T11:00:00+00:00'),
                                            ('b-2', 'ITEM-2', '2026-09-29T10:00:00+00:00'))})
    found = coarse(root)
    assert (found['state'], found['command']) == ('dispatch', 'wuwei dispatch next --all')
    assert '1 planned item(s) can start, 2 of CAP 3 building' in found['why']
    approved(root, items, cap=2)
    day(root, seats={name: {'status': 'running', 'role': 'builder', 'item': item, 'started_at': at}
                     for name, item, at in (('b-1', 'ITEM-1', '2026-09-29T11:00:00+00:00'),
                                            ('b-2', 'ITEM-2', '2026-09-29T10:00:00+00:00'))})
    found = coarse(root)
    assert found['state'] == 'wait'
    assert 'ITEM-3 waits: 2 of CAP 2 building; b-2 started first' in found['why']


# #551 US1.2: next returns the delegate's own action


def test_build_rows_return_the_build_loop_action(root, capsys, monkeypatch):
    from wuwei.commands import build
    approved(root, {'A': ('implement', {})})
    launch = {'action': 'launch', 'prompt': 'WUWEI brief: x', 'agent_type': 'wuwei:builder', 'brief': 'b'}
    monkeypatch.setattr(build, 'next_action', lambda item, root=None: launch)
    code, found = row(capsys)
    assert code == 0 and found == {'state': 'build', 'item': 'A', **launch,
                                   'why': coarse(root)['why'], 'then': next_command.THEN['agent']}
    check = {'action': 'check', 'command': 'wuwei build check A'}
    monkeypatch.setattr(build, 'next_action', lambda item, root=None: check)
    found = row(capsys)[1]
    assert (found['command'], found['then']) == ('wuwei build check A', next_command.THEN['background'])
    # #614: a continue is a fresh Agent with the returned prompt; resume only where offered
    resume = {**launch, 'action': 'continue', 'resume': 'agent-1', 'feedback': 'f'}
    monkeypatch.setattr(build, 'next_action', lambda item, root=None: resume)
    found = row(capsys)[1]
    assert found['then'] == next_command.THEN['continue']
    assert 'fresh Agent' in found['then'] and 'resume' in found['then']
    assert 'fresh Agent' in next_command.THEN['set']
    # done moves the item on: the day is asked again in the same call
    answers = iter([{'action': 'done'}])

    def done(item, root=None):
        day(root, items={'A': {'phase': 'merged'}})
        return next(answers)
    monkeypatch.setattr(build, 'next_action', done)
    found = row(capsys)[1]
    assert found['state'] == 'close'


@pytest.mark.parametrize('answer,expected', [
    ({'action': 'gates', 'roles': ['arch'], 'seats': [], 'commands': ['wuwei brief arch A arch-A']},
     ('verdicts', 'gates', None)),
    ({'action': 'escalate', 'reason': 'fix round already used'},
     ('verdicts', 'run', "wuwei plan park A --reason 'fix round already used'")),
    ({'action': 'raise', 'notes': ['n1']}, ('raise', 'run', None)),
])
def test_verdict_rows_return_the_gate_action(root, capsys, monkeypatch, answer, expected):
    from wuwei import dispatch
    approved(root, {'A': ('gate', {'worktree': str(root)})})
    monkeypatch.setattr(dispatch, 'next_step', lambda item, root=None: answer)
    found = row(capsys)[1]
    assert (found['state'], found['action']) == expected[:2]
    if expected[2]:
        assert found['command'] == expected[2]
    if answer['action'] == 'gates':
        assert found['then'] == next_command.THEN['set']
        assert 'wuwei brief arch A arch-A' in last_event(root)['payload']['named']
    if answer['action'] == 'raise':
        assert found['command'].startswith(f'wuwei brief shepherd A shepherd-A --worktree {root} --body ')
        assert 'Review note: n1' in found['command']


def test_shepherd_launch_then_card(root, capsys, monkeypatch):
    from wuwei import brief, dispatch
    approved(root, {'A': ('gate', {'worktree': str(root)})})
    monkeypatch.setattr(dispatch, 'next_step', lambda item, root=None: {'action': 'raise', 'notes': []})
    path = workspace.day_dir(root) / 'briefs/shepherd-A.md'
    path.parent.mkdir()
    path.write_text('brief\n')
    found = row(capsys)[1]
    expected = brief.seat_action('shepherd', path, str(root), root)
    assert found['action'] == 'launch' and {key: found[key] for key in expected} == expected
    day(root, seats={'shepherd-A': {'status': 'stopped', 'role': 'shepherd', 'item': 'A'}})
    found = row(capsys)[1]
    assert (found['action'], found['command']) == ('card', 'wuwei why A')


def test_fix_asks_the_day_again_and_refusal_exits_one(root, capsys, monkeypatch):
    from wuwei import dispatch

    def refuse(item, root=None):
        raise dispatch.Refused('builder must stand down before gates')
    approved(root, {'A': ('gate', {})})
    monkeypatch.setattr(dispatch, 'next_step', refuse)
    code, found = row(capsys)
    assert (code, found['state'], found['why']) == (1, 'verdicts', 'builder must stand down before gates')


def test_dispatch_and_stuck_rows(root, capsys, monkeypatch):
    from wuwei import dispatch
    approved(root, {'A': ('planned', {})})
    value = {'action': 'set', 'entries': [{'item': 'A', 'action': 'start', 'commands': ['wuwei worktree add A']}]}
    monkeypatch.setattr(dispatch, 'launch_set', lambda root=None: value)
    found = row(capsys)[1]
    assert (found['state'], found['action'], found['entries']) == ('dispatch', 'set', value['entries'])
    assert last_event(root)['payload']['named'] == ['wuwei worktree add A']
    day(root, seats={'b': {'status': 'unmeasured', 'role': 'builder', 'item': 'A'}})
    assert coarse(root)['command'] == 'wuwei seat stop b --unmeasured "seat ended with no recorded result"'


# #551: steward and close


def test_steward_rows(root, capsys):
    approved(root, {})
    state.append_event('steward.due', {'tool_calls': 200}, root)
    found = coarse(root)
    assert (found['command'], found['then']) == ('wuwei steward run --trigger tool-calls',
                                                 next_command.THEN['background'])
    brief_path = '.wuwei/days/2026-09-30/briefs/steward-abc.md'
    state.append_event('steward.run', {'trigger': 'tool-calls', 'brief': brief_path, 'tool_calls': 200}, root)
    found = coarse(root)
    assert (found['state'], found['action'], found['brief']) == ('steward', 'launch', brief_path)
    day(root, seats={'steward-abc': {'status': 'stopped', 'role': 'steward', 'item': 'day'}})
    assert coarse(root)['state'] == 'close'


def test_steward_launches_only_the_newest_brief_and_never_beside_a_running_one(root):
    """#617: stale briefs are never launched and one steward runs at a time."""
    approved(root, {})
    briefs = '.wuwei/days/2026-09-30/briefs'
    for name, count in (('steward-old', 50), ('steward-new', 100)):
        state.append_event('steward.run', {'trigger': 'tool-calls', 'brief': f'{briefs}/{name}.md',
                                           'tool_calls': count}, root)
    found = coarse(root)
    assert (found['state'], found['action'], found['brief']) == ('steward', 'launch', f'{briefs}/steward-new.md')
    day(root, seats={'steward-new': {'status': 'running', 'role': 'steward', 'item': 'day'}})
    assert coarse(root)['state'] != 'steward'  # the old brief is never offered
    state.append_event('steward.due', {'tool_calls': 150}, root)
    assert coarse(root)['state'] != 'steward'  # due waits while the steward runs
    state.append_event('steward.run', {'trigger': 'tool-calls', 'brief': f'{briefs}/steward-next.md',
                                       'tool_calls': 150}, root)
    assert coarse(root)['state'] != 'steward'  # an unlaunched brief waits too
    state.append_event('steward.due', {'tool_calls': 200}, root)
    day(root, seats={'steward-new': {'status': 'stopped', 'role': 'steward', 'item': 'day'}})
    found = coarse(root)
    assert (found['state'], found['command']) == ('steward', 'wuwei steward run --trigger tool-calls')


def test_close_path(root, capsys):
    approved(root, {'A': ('merged', {})}, decision_routes={'D-1': 'owner'})
    state.append_event('next.action', {'state': 'x', 'item': '', 'done': [['decision', 'D-1']]}, root)
    states = []

    def expect(name, command, action='run'):
        found = coarse(root)
        assert (found['state'], found['action'], found.get('command')) == (name, action, command), found
        states.append(found)
        state.append_event('next.action', {'state': name, 'item': found.get('item', ''),
                                           'done': [[name, found.get('item', '')]]}, root)
    expect('close', 'wuwei close')
    day(root, close_requested=True)
    expect('close', 'wuwei decision show D-1 --widget', 'card')
    expect('close', 'wuwei decision show D-1 --widget', 'card')  # it holds the close: asked again
    day(root, decision_outcomes={'D-1': {'option': 'A', 'decided_by': 'owner'}})
    expect('close', 'wuwei close')
    state.append_event('steward.run', {'trigger': 'close', 'brief': 'b/steward-c.md'}, root)
    day(root, seats={'steward-c': {'status': 'stopped', 'role': 'steward', 'item': 'day'}})
    expect('retro', 'wuwei retro')
    (workspace.day_dir(root) / 'retro').mkdir()
    (workspace.day_dir(root) / 'retro/2026-09-30.md').write_text('# Retro\n')
    expect('promote', 'wuwei promote')
    expect('retro-applied', 'wuwei retro')
    with (root / '.wuwei/config.toml').open('a') as stream:
        stream.write('[outbound]\nowner_channel = "dm"\n[outbound.owner.slack]\nuser = "U1"\ndm = "D9"\n')
    expect('report', 'wuwei report')
    assert "owner's DM D9" in states[-1]['then']
    (workspace.day_dir(root) / 'report.md').write_text('# Report\n')
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
    assert row(capsys)[1]['state'] == 'mcp'
    assert last_event(root)['payload']['done'] == [['pr-flow', '']]
    assert row(capsys)[1]['state'] == 'mcp'
    # ponytail: a once-row returned three times counts as done, so a refused or failed command
    # (no PostToolUse span) never holds the day.
    assert row(capsys)[1]['state'] == 'mcp'
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


def test_an_empty_close_card_does_not_hold_next(root, capsys):
    approved(root, {'A': ('merged', {})}, decision_routes={'D-1': 'owner'}, close_requested=True)
    seen(root, 'decision')
    state.append_event('next.action', {'state': 'decision', 'item': 'D-1', 'action': 'pass'}, root)
    code, found = row(capsys)
    assert (code, found['state'], found['command']) == (0, 'close', 'wuwei close'), found


def test_unrehearsed_undos_are_run_rows_before_the_cards(root, capsys, rehearsed_undo, monkeypatch):
    # #557: two-way records of an unrehearsed kind go to the owner until the planner rehearses it.
    from wuwei import undo
    monkeypatch.setattr(undo, 'ledger', rehearsed_undo)
    approved(root, {}, decision_routes={'D-1': 'owner'})
    found = coarse(root)
    assert (found['state'], found['action'], found['command'], found['item']) == (
        'rehearse', 'run', 'wuwei undo rehearse commit', 'commit')
    assert 'come to you as cards until it runs' in found['why']
    assert next_command.step(root, [('rehearse', 'commit')])['command'] == 'wuwei undo rehearse decision'
    assert next_command.step(root, [('rehearse', 'commit'), ('rehearse', 'decision')])['state'] == 'decision'
    undo.record(root, 'commit', 'rehearsal')
    undo.record(root, 'decision', 'rehearsal')
    assert coarse(root)['state'] == 'decision'

    def unread(root):
        raise AssertionError('the ledger is not read once both rows are done')
    monkeypatch.setattr(undo, 'ledger', unread)
    assert next_command.step(root, [('rehearse', 'commit'), ('rehearse', 'decision')])['state'] == 'decision'


@pytest.mark.parametrize('answered', [False, True])
def test_unanswered_setup_questions_are_asked_on_any_day(root, capsys, answered):
    # #530: a workspace on day 5 that never answered the interview gets the cards at the next plan.
    from wuwei import interview
    for name in ('2026-09-26', '2026-09-27', '2026-09-28', '2026-09-29'):
        (root / '.wuwei/days' / name).mkdir(parents=True)
    if answered:
        (root / '.wuwei/days/2026-09-29/interview.json').write_text(json.dumps({
            row['id']: ({'example/project': row['choices'][0][0]} if row['scope'] == 'repo' else row['choices'][0][0])
            for row in interview.QUESTIONS}))
    planned(root)
    day(root, gate_approved=True, planner_session_id='S')
    found = row(capsys)[1]
    if answered:  # the list is []: the row passes in the same call, as the telemetry row does
        assert found['state'] != 'calibrate'
        return
    assert (found['state'], found['action'], found['command']) == ('calibrate', 'card', 'wuwei calibrate --questions')
    assert found['widget'][0]['id'] == 'autonomy'
    ran(root, found['widget'][0]['record'].replace('<label>', 'Autonomous'))
    assert row(capsys)[1]['state'] != 'calibrate'
