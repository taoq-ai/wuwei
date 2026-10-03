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
    day(root, gate_approved=True, approved_items=list(items), cap=cap,
        items={name: {'phase': phase, **fields} for name, (phase, fields) in items.items()},
        **extra)


def row(capsys, *args):
    capsys.readouterr()
    code = main(['next', '--json', *args])
    return code, json.loads(capsys.readouterr().out)


# US1: wuwei next


def test_setup_rows(root, capsys):
    code, found = row(capsys)
    assert code == 0 and set(found) == {'state', 'step', 'command'}
    assert (found['state'], found['command']) == ('setup', 'bin/wuwei setup')
    assert 'host terminal' in found['step']
    (root / '.wuwei/config.toml').write_text(
        '[[repos]]\nname = "example/project"\npath = "project"\ndefault_branch = "main"\n')
    assert row(capsys)[1]['state'] == 'setup'


def test_setup_row_outside_workspace(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    monkeypatch.chdir(tmp_path)
    code, found = row(capsys)
    assert code == 0 and set(found) == {'state', 'step', 'command'}
    assert (found['state'], found['command']) == ('no-workspace', 'bin/wuwei setup --shadow')


def test_morning_rows(root, capsys):
    calibrated(root)
    code, found = row(capsys)
    assert (code, found['state'], found['command']) == (0, 'plan', '/wuwei:wuwei-plan')
    assert 'start the day' in found['step']
    planned(root)
    found = row(capsys)[1]
    assert (found['state'], found['command']) == ('gate', '/wuwei:wuwei-plan')
    assert 'Morning gate' in found['step'] and 'days/2026-09-30/plan.md' in found['step']
    capsys.readouterr()
    assert main(['next']) == 0
    assert capsys.readouterr().out == f'gate: {found["step"]} Run: /wuwei:wuwei-plan\n'


def test_decision_row(root, capsys):
    approved(root, {}, decision_routes={'D-1': 'owner'})
    found = row(capsys)[1]
    assert (found['state'], found['command']) == ('decision', 'wuwei decision show D-1')
    state._write_state(lambda data: data.update(
        decision_outcomes={'D-1': {'option': 'A', 'decided_by': 'owner'}}), root, reserved=False)
    assert row(capsys)[1]['state'] != 'decision'


@pytest.mark.parametrize('phase,fields,expected,command', [
    ('planned', {}, 'dispatch', 'wuwei worktree add ITEM-1'),
    ('implement', {}, 'build', 'wuwei build next ITEM-1'),
    ('fix', {}, 'build', 'wuwei build next ITEM-1'),
    ('gate', {}, 'verdicts', 'wuwei dispatch next ITEM-1'),
    ('delta', {}, 'verdicts', 'wuwei dispatch next ITEM-1'),
    ('raised', {'pr': 'example/project#7'}, 'pr', 'wuwei pr act example/project#7'),
])
def test_item_rows(root, capsys, phase, fields, expected, command):
    approved(root, {'ITEM-1': (phase, fields)})
    found = row(capsys)[1]
    assert (found['state'], found['command']) == (expected, command)
    if expected == 'dispatch':
        assert 'brief builder' in found['step'] and 'build next' in found['step']


def seated(root):
    day(root, seats={'builder-1': {'status': 'running', 'role': 'builder', 'item': 'ITEM-1'}})


def test_cap_waits_on_running_seat(root, capsys):
    approved(root, {'ITEM-1': ('implement', {}), 'ITEM-2': ('planned', {})})
    seated(root)
    found = row(capsys)[1]
    assert (found['state'], found['command']) == ('wait', 'wuwei status --line')
    assert 'builder-1' in found['step']
    approved(root, {'ITEM-1': ('implement', {}), 'ITEM-2': ('planned', {})}, cap=2)
    seated(root)
    found = row(capsys)[1]
    assert (found['state'], found['command']) == ('dispatch', 'wuwei worktree add ITEM-2')


def test_first_approved_item_wins_and_missing_is_skipped(root, capsys):
    approved(root, {'ITEM-2': ('gate', {}), 'ITEM-1': ('implement', {})})
    day(root, approved_items=['ITEM-0', 'ITEM-2', 'ITEM-1'])
    assert row(capsys)[1]['command'] == 'wuwei dispatch next ITEM-2'


def test_end_of_day_rows(root, capsys, monkeypatch):
    approved(root, {})
    assert row(capsys)[1]['command'] == '/wuwei:wuwei-report'
    approved(root, {'ITEM-1': ('merged', {}), 'ITEM-2': ('parked', {'resume_phase': 'implement'}),
                    'ITEM-3': ('escalated', {'resume_phase': 'implement'})})
    found = row(capsys)[1]
    assert (found['state'], found['command']) == ('close', '/wuwei:wuwei-report')
    state.append_event('watch: clock', {}, root)
    monkeypatch.setenv('WUWEI_NOW', '2026-09-30T12:00:00+00:00')
    found = row(capsys)[1]
    assert (found['state'], found['command']) == ('doctor', 'wuwei doctor')
    monkeypatch.setenv('WUWEI_NOW', '2026-09-30T10:01:00+00:00')
    state.append_event('heartbeat: clock', {'health': 'degraded', 'page': 'x'}, root)
    assert row(capsys)[1]['state'] == 'doctor'
    state.append_event('heartbeat: clock', {'health': 'ok', 'page': ''}, root)
    (workspace.day_dir(root) / 'report.md').write_text('# Report\n')
    assert row(capsys)[1]['state'] == 'close'
    day(root, close_requested=True)
    found = row(capsys)[1]
    assert (found['state'], found['command']) == ('closed', 'wuwei close')


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
    assert found['step'] and 'wuwei next:' in err


# US2: SessionStart orientation


ROW = {'state': 'plan', 'step': 'No plan yet.', 'command': '/wuwei:wuwei-plan'}


@pytest.mark.parametrize('posture,phrases', [
    ('observe', ('Observe posture is on', 'bin/wuwei shadow report')),
    ('guarded', ('Posture guarded',)), ('strict', ('Posture strict',))])
def test_orientation_block(monkeypatch, posture, phrases):
    monkeypatch.delenv('WUWEI_SEAT_ROLE', raising=False)
    text = next_command.orientation(ROW, posture)
    assert text.startswith(next_command.HEADER) and len(text.splitlines()) < 25
    for phrase in ('Next: ' + next_command.line(ROW), '/wuwei:wuwei-plan',
                   str(integrity.PLUGIN / 'docs/site/agent.md'), 'skills/wuwei-plan/SKILL.md',
                   'docs/site/daily.md', *phrases):
        assert phrase in text


@pytest.mark.parametrize('role,seat', [('shepherd', True), ('../x', False), ('nope', False),
                                       ('_common', False)])
def test_orientation_seat_entry(monkeypatch, role, seat):
    monkeypatch.setenv('WUWEI_SEAT_ROLE', role)
    text = next_command.orientation(ROW, 'guarded')
    assert ('charters/shepherd.md' in text) is seat
    assert ('Start or resume the day with /wuwei:wuwei-plan' in text) is not seat


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
    assert any(line.startswith('Next: plan: ') and line.endswith('Run: /wuwei:wuwei-plan')
               for line in lines)
    assert str(integrity.PLUGIN / 'docs/site/agent.md') in text
    assert lines.index('Active constraints:') < 25


def test_orientation_precedes_integrity_line(root, monkeypatch, capsys):
    calibrated(root)
    from wuwei.integrity import Result
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
    assert 'Next: unmeasured: broken Run: wuwei doctor' in text


def test_issue_acceptance_silent_outside_workspace(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    outside = tmp_path / 'outside'
    outside.mkdir()
    monkeypatch.chdir(outside)
    capsys.readouterr()
    assert hook(monkeypatch, outside) == 0
    assert capsys.readouterr().out == ''


@pytest.mark.parametrize('decided_by', ['seat', 'owner'])
def test_carried_item_is_skipped(root, capsys, decided_by):
    approved(root, {'A': ('implement', {})}, decision_outcomes={'D-1': {
        'decided_by': decided_by, 'item_disposition': 'carried A', 'option': 'carry'}})
    found = row(capsys)[1]
    if decided_by == 'seat':
        assert found['state'] == 'close' and 'carried' in found['step']
        assert found['command'] != 'wuwei build next A'
    else:
        assert (found['state'], found['command']) == ('build', 'wuwei build next A')
