"""Chartered seat retro capture and fail-closed stop hooks."""

import io
import json
import sys

import pytest


NOTE = 'Blocked: none\nGap: none\nChange: none\n'


@pytest.fixture
def seat(tmp_path, monkeypatch):
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T12:00:00+00:00')
    (tmp_path / '.wuwei').mkdir()
    return {'cwd': str(tmp_path), 'agent_id': 'seat-one', 'agent_type': 'builder',
            'last_assistant_message': NOTE, 'hook_event_name': 'SubagentStop',
            'session_id': 'session', 'transcript_path': 'unused', 'stop_hook_active': False}


def events(seat):
    from pathlib import Path
    from wuwei.workspace import day_dir
    return [json.loads(line) for line in
            (day_dir(Path(seat['cwd'])) / 'events.jsonl').read_text().splitlines()]


@pytest.mark.parametrize('text,code,missing', [
    (NOTE, 0, []), ('', 1, ['Blocked', 'Gap', 'Change']),
    ('Blocked: none\nChange: none\n', 1, ['Gap']),
    (NOTE.replace('Gap: none', 'Gap:'), 1, ['Gap']),
    ('```\n' + NOTE + '```', 1, ['Blocked', 'Gap', 'Change']),
    ('> Blocked: none\n> Gap: none\n> Change: none\n', 1, ['Blocked', 'Gap', 'Change']),
    (NOTE.replace('Gap: none', '**Gap:** none'), 0, []),
])
@pytest.mark.parametrize('active', [False, True])
def test_retro_exit_and_gap_event(seat, text, code, missing, active):
    from wuwei.guards.verdict import check_retro
    seat.update(last_assistant_message=text, stop_hook_active=active)
    result, message = check_retro(seat)
    assert result == (0 if active else code)
    if result:
        assert all(key + ':' in message for key in missing)
    event, = events(seat)
    assert event['kind'] == ('retro.gap' if code else 'retro.captured')
    assert event['payload']['missing'] == missing
    assert event['payload']['agent_id'] == 'seat-one'
    assert event['ts'] == '2026-09-28T12:00:00+00:00'
    assert 'transcript_path' not in event['payload']


def test_duplicate_retro_is_a_finding(seat):
    from wuwei.guards.verdict import check_retro
    seat['last_assistant_message'] += 'Change: alter procedure\n'
    assert check_retro(seat)[0] == 1
    event, = events(seat)
    assert event['payload']['invalid'] == ['Change']
    assert 'proposal' not in event['payload']


def test_proposed_text_preserves_inline_markdown(seat, tmp_path):
    from wuwei.guards.verdict import check_retro
    change = 'Use `check()` and **retain validation**.'
    seat['last_assistant_message'] = NOTE.replace('Change: none', '**Change:** ' + change)
    assert check_retro(seat)[0] == 0
    payload = events(seat)[0]['payload']
    assert payload['fields']['Change'] == change
    assert json.loads((tmp_path / payload['evidence']).read_text())['fields']['Change'] == change
    assert 'proposal' not in payload


@pytest.mark.parametrize('complete', [False, True])
def test_change_stays_in_retro_for_steward(seat, tmp_path, complete):
    from wuwei.guards.verdict import check_retro
    charter = tmp_path / '.wuwei/charters/builder.md'
    charter.parent.mkdir()
    charter.write_text('Existing rule\n')
    note = NOTE.replace('Change: none', 'Change: run the focused test before handoff')
    seat['last_assistant_message'] = note if complete else note.replace('Gap: none\n', '')
    assert check_retro(seat)[0] == (0 if complete else 1)
    event, = events(seat)
    payload = event['payload']
    evidence = tmp_path / payload['evidence']
    assert json.loads(evidence.read_text())['fields']['Change'] == 'run the focused test before handoff'
    assert 'proposal' not in payload
    assert not list((tmp_path / '.wuwei/days').glob('*/proposals/*'))
    assert charter.read_text() == 'Existing rule\n'
    assert not (tmp_path / '.wuwei/memory').exists()
    assert not payload['evidence'].startswith('/')


@pytest.mark.parametrize('change', ['none', 'None', 'NONE'])
def test_no_change_makes_no_proposal(seat, tmp_path, change):
    from wuwei.guards.verdict import check_retro
    seat['last_assistant_message'] = NOTE.replace('Change: none', 'Change: ' + change)
    assert check_retro(seat)[0] == 0
    assert not list((tmp_path / '.wuwei/days').glob('*/proposals/*'))


def test_retry_and_hostile_seat_name(seat, tmp_path):
    from wuwei.guards.verdict import check_retro
    seat['agent_id'] = '../../outside'
    seat['last_assistant_message'] = NOTE.replace('Change: none', 'Change: improve checks')
    assert check_retro(seat)[0] == 0
    assert check_retro(seat)[0] == 0
    assert len(events(seat)) == 2
    assert len(list((tmp_path / '.wuwei/days').glob('*/retro/*.json'))) == 1
    assert len(list((tmp_path / '.wuwei/days').glob('*/proposals/*.json'))) == 0


@pytest.mark.parametrize('field,value', [('cwd', None), ('agent_id', ''),
                                        ('last_assistant_message', None)])
def test_invalid_capture_payload(seat, field, value):
    from wuwei.guards.verdict import check_retro
    seat[field] = value
    code, message = check_retro(seat)
    assert code == 2
    assert field in message


@pytest.mark.parametrize('failed', ['retro', 'event'])
def test_capture_failure_is_not_clean(seat, tmp_path, monkeypatch, failed):
    from wuwei.guards import verdict
    from wuwei import workspace, state
    seat['last_assistant_message'] = NOTE.replace('Change: none', 'Change: improve checks')
    if failed == 'event':
        def fail(*args, **kwargs):
            raise OSError('event unavailable')
        monkeypatch.setattr(state, 'append_event', fail)
    else:
        write = workspace.atomic_write

        def fail(path, *args, **kwargs):
            if path.parent.name == 'retro':
                raise OSError('write unavailable')
            return write(path, *args, **kwargs)

        monkeypatch.setattr(workspace, 'atomic_write', fail)
    code, message = verdict.check_retro(seat)
    assert code == 2
    assert message


def assert_missing_retro_blocks(seat, monkeypatch, capsys):
    from wuwei.__main__ import main
    seat['last_assistant_message'] = 'Done.'
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(seat)))
    assert main(['hook', 'SubagentStop']) == 2
    out = capsys.readouterr()
    assert json.loads(out.out)['decision'] == 'block'
    assert 'Change:' in out.err
    assert events(seat)[-1]['kind'] == 'retro.gap'


def test_missing_retro_hook(seat, monkeypatch, capsys):
    assert_missing_retro_blocks(seat, monkeypatch, capsys)


def test_disabled_retro_guard_is_caught(seat, monkeypatch, capsys):
    from wuwei.commands import hook
    assert_missing_retro_blocks(seat, monkeypatch, capsys)
    monkeypatch.setattr(hook, 'discover', lambda: [])
    with pytest.raises(AssertionError):
        assert_missing_retro_blocks(seat, monkeypatch, capsys)


@pytest.mark.parametrize('role', ['Explore', 'general-purpose', '', None, [], 'wuwei:unknown'])
def test_non_charter_stop_is_irrelevant(seat, tmp_path, role):
    from wuwei.guards.verdict import check_retro
    seat['agent_type'] = role
    del seat['agent_id']
    del seat['last_assistant_message']
    assert check_retro(seat) == (0, '')
    assert not (tmp_path / '.wuwei/days').exists()


def test_prefixed_charter_role_is_captured(seat):
    from wuwei.guards.verdict import check_retro
    seat['agent_type'] = 'wuwei:builder'
    seat['last_assistant_message'] = ''
    assert check_retro(seat)[0] == 1
    assert events(seat)[0]['kind'] == 'retro.gap'


def test_retro_outside_workspace_is_irrelevant(seat, tmp_path):
    from wuwei.guards.verdict import check_retro
    (tmp_path / '.wuwei').rmdir()
    del seat['last_assistant_message']
    assert check_retro(seat) == (0, '')


@pytest.mark.parametrize('role', ['sentinel-arch', 'wuwei:sentinel-quality',
                                 'plugin:wuwei:sentinel-security', 'wuwei:sentinel-goal',
                                 'wuwei:sentinel-custom', 'builder'])
@pytest.mark.parametrize('active', [False, True])
def test_sentinel_stop_lints_daily_gates(seat, tmp_path, monkeypatch, capsys, role, active):
    from wuwei.__main__ import main
    from wuwei.workspace import day_dir
    directory = day_dir(tmp_path) / 'decisions'
    directory.mkdir(parents=True)
    for name in ('gate-first.md', 'GaTe-second.MD'):
        (directory / name).write_text('Verdict: FIX')
    seat.update(agent_type=role, stop_hook_active=active)
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(seat)))
    sentinel = role.rsplit(':', 1)[-1].startswith('sentinel-')
    assert main(['hook', 'SubagentStop']) == (2 if sentinel and not active else 0)
    output = capsys.readouterr()
    if sentinel and not active:
        assert json.loads(output.out)['decision'] == 'block'
        assert 'file:line' in output.err
    rejected = [event for event in events(seat) if event['kind'] == 'verdict.rejected']
    assert {event['payload']['file'] for event in rejected} == (
        {str(path) for path in directory.iterdir()} if sentinel else set())
