"""#473: a background seat's hand-back is its result, and no seat is left running."""

import hashlib
import json
from pathlib import Path

import pytest

from wuwei import brief

PAYLOADS = Path(__file__).resolve().parent / 'payloads/SubagentStop'
HANDBACK = (PAYLOADS / 'handback-transcript.jsonl').read_text()
REPORT = json.loads(HANDBACK.splitlines()[0])['message']['content'][0]['input']['message']


def write(path, *rows, raw=''):
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows) + raw)
    return path


def test_last_turn_shapes(tmp_path):
    user = {'type': 'user', 'message': {'content': 'WUWEI brief: x.md'}}
    path = write(tmp_path / 'handback.jsonl', user, raw=HANDBACK)
    completion, text, handback = brief.last_turn(path)
    line = path.read_text().splitlines()[1]
    assert (text, handback) == (REPORT, True)
    assert completion == [1, hashlib.sha256(line.encode()).hexdigest()]
    path = write(tmp_path / 'text.jsonl', user, {'type': 'assistant', 'message': {'content': [
        {'type': 'text', 'text': 'one'}, {'type': 'tool_use', 'name': 'Read', 'input': {}},
        {'type': 'text', 'text': 'two'}]}})
    assert brief.last_turn(path)[1:] == ('one\ntwo', False)
    path = write(tmp_path / 'string.jsonl', {'type': 'assistant', 'message': {'content': 'plain'}})
    assert brief.last_turn(path)[1:] == ('plain', False)
    with pytest.raises(ValueError):
        brief.last_turn(write(tmp_path / 'torn.jsonl', user, raw='{"type": "assist'))
    with pytest.raises(ValueError):
        brief.last_turn(write(tmp_path / 'none.jsonl', user))
    with pytest.raises(ValueError):
        brief.last_turn(write(tmp_path / 'bad.jsonl', {'type': 'assistant'}))
    with pytest.raises(OSError):
        brief.last_turn(tmp_path / 'missing.jsonl')


def test_stop_text(tmp_path):
    path = write(tmp_path / 'handback.jsonl', raw=HANDBACK)
    assert brief.stop_text({'last_assistant_message': 'said', 'agent_transcript_path': str(path)}) == 'said'
    for message in ({}, {'last_assistant_message': ''}, {'last_assistant_message': '  \n'}):
        assert brief.stop_text({**message, 'agent_transcript_path': str(path)}) == REPORT
    with pytest.raises(ValueError, match='agent_transcript_path'):
        brief.stop_text({})
    tool_only = write(tmp_path / 'tool.jsonl', {'type': 'assistant', 'message': {'content': [
        {'type': 'tool_use', 'name': 'Bash', 'input': {'command': 'ls'}}]}})
    with pytest.raises(ValueError, match='no report'):
        brief.stop_text({'agent_transcript_path': str(tool_only)})


def test_stop_text_reads_the_tail(tmp_path):
    # #516: a missing report is read from the transcript's end; the head is never decoded and
    # the window grows until the last assistant entry is in it.
    user = json.dumps({'type': 'user', 'message': {'content': 'x' * 1000}}) + '\n'
    path = tmp_path / 'head.jsonl'
    path.write_bytes(b'\xff\xfe not utf-8\n' + (user * 70).encode() + HANDBACK.encode())
    assert brief.stop_text({'agent_transcript_path': str(path)}) == REPORT
    with pytest.raises(ValueError):
        brief.last_turn(path)
    path = tmp_path / 'far.jsonl'
    path.write_text(json.dumps({'type': 'assistant', 'message': {'content': 'far back'}}) + '\n' + user * 300)
    assert brief.stop_text({'agent_transcript_path': str(path)}) == 'far back'


from test_build_next import launch, seat, stop  # noqa: E402,F401 (the seat fixture)
from test_build import events  # noqa: E402
from wuwei import state  # noqa: E402
from wuwei.commands import build  # noqa: E402
from wuwei.guards import agent_launch  # noqa: E402


def handback_stop(seat, **fields):
    root = seat[0]
    with (root / 'agent.jsonl').open('a') as stream:
        stream.write(HANDBACK)
    return agent_launch.stop({'cwd': str(root), 'agent_type': 'wuwei:builder', 'agent_id': 'agent-builder',
                              'agent_transcript_path': str(root / 'agent.jsonl'), **fields})


def kinds(day):
    rows = [row['kind'] for row in events(day)]
    return [kind for kind in rows[rows.index('seat launched') + 1:] if kind.startswith('seat')]


@pytest.mark.parametrize('ending', ['handback', 'text'])
def test_builder_handback_records_result(seat, ending):
    root, _, _, day, _ = seat
    launch(seat, build.next_action('A', root=root))
    assert (handback_stop(seat) if ending == 'handback' else stop(seat)) == (0, '')
    data = state.read_state(root)
    assert data['seats']['builder']['status'] == 'stopped'
    assert data['builds']['A']['status'] == 'check'
    assert data['builds']['A']['result']['text'] == (
        REPORT if ending == 'handback' else 'Blocked: none\nGap: none\nChange: none')
    assert kinds(day) == ['seat.usage', 'seat stopped']


def test_mismatched_message_still_refused(seat):
    root, _, _, _, _ = seat
    launch(seat, build.next_action('A', root=root))
    code, reason = handback_stop(seat, last_assistant_message='something else')
    assert code == 2 and 'no matching assistant completion' in reason
    assert state.read_state(root)['builds']['A']['status'] == 'running'


def add_seat(root, name, role, status='running'):
    """A reserved seat and its agent transcript holding the brief reference."""
    relative = f'.wuwei/days/{state.workspace.day_dir(root).name}/briefs/{name}.md'
    state._write_state(lambda data: data['seats'].update({name: {
        'id': name, 'role': role, 'item': 'A', 'brief': relative, 'status': status}}),
        root, reserved=False)
    return write(root / f'{name}.jsonl', {'type': 'user', 'message': {'content': brief.REFERENCE_PREFIX + relative}})


def torn_stop(root, name, role, transcript):
    with transcript.open('a') as stream:
        stream.write('{"type": "assistant", "message": {"content": [{"type": "te')
    return agent_launch.stop({'cwd': str(root), 'agent_type': 'wuwei:' + role, 'agent_id': 'agent-' + name,
                              'agent_transcript_path': str(transcript)})


def assert_unmeasured(root, day, name, code, reason):
    from wuwei.__main__ import main
    from wuwei.commands import next as next_command
    assert code == 2 and f'seat {name} stopped unmeasured:' in reason and 'wuwei seat stop' in reason
    seat = state.read_state(root)['seats'][name]
    assert seat['status'] == 'unmeasured' and seat['reason']
    stops = [row['payload'] for row in events(day) if row['kind'] == 'seat stopped']
    assert len(stops) == 1
    assert stops[0].items() >= {'name': name, 'status': 'unmeasured', 'reason': seat['reason']}.items()
    assert next_command.step(root)['state'] != 'wait'
    assert main(['status', '--line']) == 0


def test_unreadable_transcript_stops_unmeasured(seat):
    root, _, _, day, _ = seat
    launch(seat, build.next_action('A', root=root))
    assert_unmeasured(root, day, 'builder', *torn_stop(root, 'builder', 'builder', root / 'agent.jsonl'))
    assert state.read_state(root)['builds']['A']['status'] == 'running'  # the hook never parks (A6)


def test_sentinel_unreadable_report(seat):
    root, _, _, day, _ = seat
    transcript = add_seat(root, 'quality', 'sentinel-quality')
    assert_unmeasured(root, day, 'quality', *torn_stop(root, 'quality', 'sentinel-quality', transcript))


def test_missing_transcript_stops_unmeasured(seat):
    # #473 review F1: a transcript path that does not exist still binds through the recorded transcript.
    root, _, _, day, _ = seat
    transcript = add_seat(root, 'quality', 'sentinel-quality')
    state._write_state(lambda data: data['seats']['quality'].update({'transcript': str(transcript)}),
                       root, reserved=False)
    transcript.unlink()
    assert_unmeasured(root, day, 'quality', *agent_launch.stop({
        'cwd': str(root), 'agent_type': 'wuwei:sentinel-quality', 'agent_id': 'agent-quality',
        'agent_transcript_path': str(transcript)}))


def test_stop_seat_reason(seat):
    root, _, _, day, _ = seat
    add_seat(root, 'quality', 'sentinel-quality')
    state.stop_seat('quality', root, reason='no report', by='owner')
    record = state.read_state(root)['seats']['quality']
    assert (record['status'], record['reason'], record['by']) == ('unmeasured', 'no report', 'owner')
    assert events(day)[-1]['payload'].items() >= {'name': 'quality', 'status': 'unmeasured',
                                                  'reason': 'no report', 'by': 'owner'}.items()
    state.stop_seat('quality', root)
    record = state.read_state(root)['seats']['quality']
    assert record['status'] == 'stopped' and 'reason' not in record and 'by' not in record
    assert 'reason' not in events(day)[-1]['payload'] and 'status' not in events(day)[-1]['payload']


def hook_stop(monkeypatch, capsys, **fields):
    import io
    import sys
    from wuwei.__main__ import main
    payload = {**json.loads((PAYLOADS / 'handback.json').read_text()), **fields}
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(payload)))
    code = main(['hook', 'SubagentStop'])
    return code, capsys.readouterr().err


def test_hook_fills_message_for_every_guard(seat, monkeypatch, capsys):
    root, _, _, day, _ = seat
    launch(seat, build.next_action('A', root=root))
    with (root / 'agent.jsonl').open('a') as stream:
        stream.write(HANDBACK)
    code, err = hook_stop(monkeypatch, capsys, cwd=str(root), agent_type='wuwei:builder',
                          agent_id='agent-builder', agent_transcript_path=str(root / 'agent.jsonl'))
    assert code == 0, err
    assert 'decision question:' not in err and 'retro capture:' not in err
    captured = [row['payload'] for row in events(day) if row['kind'] == 'retro.captured']
    assert captured and captured[-1]['fields'] == {'Blocked': 'none', 'Gap': 'none', 'Change': 'none'}
    assert state.read_state(root)['seats']['builder']['status'] == 'stopped'


def test_hook_reads_nothing_for_other_agents(seat, monkeypatch, capsys):
    def unread(path):
        raise AssertionError('transcript read for a non-WUWEI subagent')
    monkeypatch.setattr(brief, 'last_turn', unread)
    monkeypatch.setattr(brief, 'tail_turn', unread)
    root = seat[0]
    code, err = hook_stop(monkeypatch, capsys, cwd=str(root),
                          agent_transcript_path=str(root / 'missing.jsonl'))
    assert code == 0, err


def test_unmatched_seat_stop_still_records_session(seat, monkeypatch, capsys):
    # #516: the seat stop folds the session row into its own write; a stop that matches no
    # reservation leaves the registry write to lifecycle, as before.
    root, _, _, day, _ = seat
    transcript = write(root / 'stray.jsonl',
                       {'type': 'user', 'message': {'content': brief.REFERENCE_PREFIX + 'elsewhere.md'}})
    code, err = hook_stop(monkeypatch, capsys, cwd=str(root), agent_type='wuwei:builder', agent_id='agent-stray',
                          agent_transcript_path=str(transcript),
                          last_assistant_message='Blocked: none\nGap: none\nChange: none')
    assert code == 0, err
    rows = events(day)
    assert 'seat stop unmatched' in [row['kind'] for row in rows]
    assert state.read_state(root)['sessions']['abc123']['last_hook'] == 'SubagentStop:wuwei:builder'
    assert [row['kind'] for row in rows].count('session.seen') == 1


def stuck_day(root):
    """A builder seat running with a recorded transcript that ends in the hand-back."""
    transcript = add_seat(root, 'stuck', 'builder')
    with transcript.open('a') as stream:
        stream.write(HANDBACK)
    state._write_state(lambda data: data['seats']['stuck'].update(transcript=str(transcript)),
                       root, reserved=False)
    return transcript


def test_stuck(tmp_path):
    def seat(status, ending=None, **fields):
        record = {'role': 'builder', 'item': 'A', 'status': status, **fields}
        if ending is not None:
            path = tmp_path / f'{len(seats)}.jsonl'
            path.write_text(ending)
            record['transcript'] = str(path)
        return record
    text = json.dumps({'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': 'done'}]}}) + '\n'
    seats = {}
    seats['b-handback'] = seat('running', HANDBACK)
    seats['a-hook'] = seat('unmeasured', reason='unreadable')
    seats['text'] = seat('running', text)
    seats['none'] = seat('running')
    seats['missing'] = {**seat('running'), 'transcript': str(tmp_path / 'absent.jsonl')}
    seats['torn'] = seat('running', HANDBACK + '{"type": "assist')
    seats['owner'] = seat('unmeasured', reason='gone', by='owner')
    seats['stopped'] = seat('stopped', HANDBACK)
    assert brief.stuck({'seats': seats}) == ['a-hook', 'b-handback']


def test_next_names_stuck_seat(seat):
    from wuwei.commands import next as next_command
    root, _, _, day, _ = seat
    (root / '.wuwei/calibration.json').write_text('{"calibrated": true}')
    (day / 'plan.md').write_text('# Plan\n')
    state._write_state(lambda data: data.update(gate_approved=True, approved_items=['A']), root, reserved=False)
    assert next_command.step(root)['state'] == 'build'
    stuck_day(root)
    row = next_command.step(root)
    assert row['state'] == 'stuck' and row['command'] == 'wuwei seat stop stuck --verdict <file>'


def test_heartbeat_seats_probe(seat):
    from wuwei import heartbeat
    root = seat[0]
    assert heartbeat._seats(root) == ('ok', 'none stuck')
    stuck_day(root)
    result, value = heartbeat._seats(root)
    assert result == 'failed' and value.startswith('dead: stuck;') and 'wuwei seat stop stuck --verdict' in value


REPORT_FILE = 'Built it.\nBlocked: none\nGap: none\nChange: none\n'


def stuck_builder(seat, monkeypatch):
    root = seat[0]
    monkeypatch.delenv('WUWEI_SESSION_ID', raising=False)
    launch(seat, build.next_action('A', root=root))
    with (root / 'agent.jsonl').open('a') as stream:
        stream.write(HANDBACK)
    report = root / 'report.md'
    report.write_text(REPORT_FILE)
    return root, report


def seat_stop(capsys, *args):
    from wuwei.__main__ import main
    code = main(['seat', 'stop', *map(str, args)])
    return code, capsys.readouterr()


def test_seat_stop_verdict_builder(seat, monkeypatch, capsys):
    root, report = stuck_builder(seat, monkeypatch)
    code, out = seat_stop(capsys, 'builder', '--verdict', report)
    assert code == 0, out.err
    data = state.read_state(root)
    assert data['seats']['builder']['status'] == 'stopped'
    assert data['builds']['A']['status'] == 'check' and data['builds']['A']['result']['text'] == REPORT_FILE
    assert kinds(seat[3]) == ['seat.usage', 'seat stopped']


def test_seat_stop_verdict_after_unmeasured(seat, monkeypatch, capsys):
    root, report = stuck_builder(seat, monkeypatch)
    (root / 'agent.jsonl').write_text((root / 'agent.jsonl').read_text().replace(HANDBACK, ''))
    assert torn_stop(root, 'builder', 'builder', root / 'agent.jsonl')[0] == 2
    assert brief.stuck(state.read_state(root)) == ['builder']
    code, out = seat_stop(capsys, 'builder', '--verdict', report)
    assert code == 0, out.err
    data = state.read_state(root)
    assert data['seats']['builder']['status'] == 'stopped' and 'reason' not in data['seats']['builder']
    assert data['builds']['A']['result']['text'] == REPORT_FILE
    assert brief.stuck(data) == []


def test_seat_stop_verdict_sentinel_lint(seat, monkeypatch, capsys):
    root = seat[0]
    monkeypatch.delenv('WUWEI_SESSION_ID', raising=False)
    add_seat(root, 'quality', 'sentinel-quality')
    report = root / 'verdict.md'
    report.write_text('No verdict here.\n')
    before = state.read_state(root)['seats']
    code, out = seat_stop(capsys, 'quality', '--verdict', report)
    assert code == 1 and 'Verdict' in out.err
    assert state.read_state(root)['seats'] == before


def test_seat_stop_unmeasured_parks_builder(seat, monkeypatch, capsys):
    root, _ = stuck_builder(seat, monkeypatch)
    code, out = seat_stop(capsys, 'builder', '--unmeasured', 'seat process gone')
    assert code == 0, out.err
    data = state.read_state(root)
    record = data['seats']['builder']
    assert (record['status'], record['reason'], record['by']) == ('unmeasured', 'seat process gone', 'owner')
    assert data['builds']['A']['status'] == 'parked'
    assert 'seat process gone' in data['builds']['A']['action']['reason']
    assert brief.stuck(data) == []


def test_seat_stop_refusals(seat, monkeypatch, capsys):
    from wuwei import integrity, workspace
    root, report = stuck_builder(seat, monkeypatch)
    add_seat(root, 'done', 'sentinel-arch', status='stopped')
    before = (state.workspace.day_dir(root) / 'state.json').read_text()
    assert seat_stop(capsys, 'done', '--unmeasured', 'x')[0] == 1
    assert seat_stop(capsys, 'nobody', '--unmeasured', 'x')[0] == 1
    assert seat_stop(capsys, 'builder', '--unmeasured', ' ')[0] == 2
    assert seat_stop(capsys, 'builder', '--unmeasured', 'one\ntwo')[0] == 2
    monkeypatch.setattr(workspace, 'posture', lambda config: ('guarded', {}))
    monkeypatch.setenv('WUWEI_SESSION_ID', 'some-seat')
    code, out = seat_stop(capsys, 'builder', '--verdict', report)
    assert code == 1 and 'planner session' in out.err
    monkeypatch.delenv('WUWEI_SESSION_ID')
    monkeypatch.setattr(workspace, 'posture', lambda config: ('strict', {}))

    def no_terminal(name, prompt=None):
        raise OSError(integrity.HOST_TERMINAL)
    monkeypatch.setattr(integrity, '_host_confirm', no_terminal)
    code, out = seat_stop(capsys, 'builder', '--unmeasured', 'x')
    assert code == 2 and 'host terminal' in out.err
    monkeypatch.setattr(integrity, '_host_confirm', lambda name, prompt=None: False)
    assert seat_stop(capsys, 'builder', '--unmeasured', 'x')[0] == 1
    assert (state.workspace.day_dir(root) / 'state.json').read_text() == before


def test_seat_stop_planner_session_allowed(seat, monkeypatch, capsys):
    from wuwei import workspace
    root, report = stuck_builder(seat, monkeypatch)
    state._write_state(lambda data: data.update(planner_session_id='planner-1'), root, reserved=False)
    monkeypatch.setattr(workspace, 'posture', lambda config: ('guarded', {}))
    monkeypatch.setenv('WUWEI_SESSION_ID', 'planner-1')
    code, out = seat_stop(capsys, 'builder', '--verdict', report)
    assert code == 0, out.err
