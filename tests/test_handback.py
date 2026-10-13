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


def _case_stop_text(tmp_path):
    path = write(tmp_path / 'handback.jsonl', raw=HANDBACK)
    assert brief.stop_text({'last_assistant_message': 'said', 'agent_transcript_path': str(path)}) == 'said'
    for message in ({}, {'last_assistant_message': ''}, {'last_assistant_message': '  \n'}):
        assert brief.stop_text({**message, 'agent_transcript_path': str(path)}) == REPORT
    with pytest.raises(ValueError, match='agent_transcript_path'):
        brief.stop_text({})
    with pytest.raises(ValueError, match='agent_transcript_path'):
        brief.stop_text({'transcript_path': str(path)})  # never read the planner as a seat
    tool_only = write(tmp_path / 'tool.jsonl', {'type': 'assistant', 'message': {'content': [
        {'type': 'tool_use', 'name': 'Bash', 'input': {'command': 'ls'}}]}})
    with pytest.raises(ValueError, match='no report'):
        brief.stop_text({'agent_transcript_path': str(tool_only)})


def _case_stop_text_reads_the_tail(tmp_path):
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


@pytest.mark.parametrize("scenario_fn", [
    _case_stop_text,
    _case_stop_text_reads_the_tail,
])
def test_stop_text_cases_44(tmp_path, scenario_fn):
    scenario_fn(tmp_path)


from test_build_next import launch, seat, stop  # noqa: E402,F401 (the seat fixture)
from test_build import events  # noqa: E402
from wuwei import registry, state  # noqa: E402
from wuwei.__main__ import main  # noqa: E402
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


def _case_mismatched_message_still_refused(seat):
    root, _, _, _, _ = seat
    launch(seat, build.next_action('A', root=root))
    code, reason = handback_stop(seat, last_assistant_message='something else')
    assert code == 2 and 'no matching assistant completion' in reason
    assert state.read_state(root)['builds']['A']['status'] == 'running'


def test_field_default_stop_waits_for_final_text_row(seat, monkeypatch, capsys):
    root = seat[0]
    launch(seat, build.next_action('A', root=root))
    path = root / 'agent.jsonl'
    with path.open('a') as stream:
        stream.write(json.dumps({'type': 'assistant', 'agentId': 'agent-builder', 'message': {
            'content': [{'type': 'thinking', 'thinking': 'Finishing the report'}]}}) + '\n')
    original = brief.last_turn
    reads = []

    def delayed_text(path):
        found = original(path)
        if not reads:
            with Path(path).open('a') as stream:
                stream.write(json.dumps({'type': 'assistant', 'agentId': 'agent-builder', 'message': {
                    'content': [{'type': 'text', 'text': REPORT}]}}) + '\n')
        reads.append(found)
        return found
    monkeypatch.setattr(brief, 'last_turn', delayed_text)
    payload = json.loads((PAYLOADS / 'plain-final.json').read_text())
    payload.update(cwd=str(root), agent_transcript_path=str(path), last_assistant_message=REPORT)
    code, reason = hook_stop(monkeypatch, capsys, **payload)
    assert code == 0, reason
    assert len(reads) >= 2 and reads[0][1] == ''
    assert state.read_state(root)['builds']['A']['result']['text'] == REPORT


@pytest.mark.parametrize('initially_torn', [False, True])
def test_stop_retries_a_partial_final_row(seat, monkeypatch, capsys, initially_torn):
    import threading
    import time
    root = seat[0]
    launch(seat, build.next_action('A', root=root))
    path = root / 'agent.jsonl'
    final = json.dumps({'type': 'assistant', 'message': {'content': REPORT}}) + '\n'
    with path.open('a') as stream:
        stream.write(json.dumps({'type': 'assistant', 'message': {'content': [
            {'type': 'thinking', 'thinking': 'Finishing'}]}}) + '\n')
        if initially_torn:
            stream.write(final[:20])

    def finish():
        if not initially_torn:
            time.sleep(0.1)
            with path.open('a') as stream:
                stream.write(final[:20])
        time.sleep(0.3)
        with path.open('a') as stream:
            stream.write(final[20:])
    writer = threading.Thread(target=finish)
    writer.start()
    try:
        code, reason = hook_stop(monkeypatch, capsys, cwd=str(root), session_id='abc123',
                                 agent_type='wuwei:builder', agent_id='agent-builder',
                                 agent_transcript_path=str(path), last_assistant_message=REPORT,
                                 permission_mode='default')
    finally:
        writer.join()
    assert code == 0, reason
    assert state.read_state(root)['builds']['A']['result']['text'] == REPORT


@pytest.mark.parametrize('manual', [False, True])
def test_field_sendmessage_continuation_records_same_agent_stop(seat, monkeypatch, capsys, manual):
    root = seat[0]
    monkeypatch.delenv('WUWEI_SESSION_ID', raising=False)
    launch(seat, build.next_action('A', root=root))
    assert handback_stop(seat) == (0, '')

    def continued(data):
        record = data['builds']['A']
        record.update(status='ready', answered='Proceed with the committed work',
                      action=build._continue(root, record, 'Owner answered Yes'))
        data['seats']['builder']['transcript'] = str(root / 'agent.jsonl')
    state._write_state(continued, root)
    payload = {'cwd': str(root), 'agent_type': 'wuwei:builder', 'agent_id': 'agent-builder',
               'agent_transcript_path': str(root / 'agent.jsonl')}
    assert agent_launch.stop(payload) == (0, '')  # duplicate completion is not a continued round
    assert build.step('A', root)['action'] == 'continue'
    if manual:
        before = state.read_state(root)['builds']['A']
        report = root / 'forged.md'
        report.write_text('Another seat wrote this.\nBlocked: none\nGap: none\nChange: none\n')
        assert seat_stop(capsys, 'builder', '--verdict', report)[0] == 1
        assert state.read_state(root)['builds']['A'] == before
        assert seat_stop(capsys, 'builder', '--verdict')[0] == 1  # no new completion
        assert state.read_state(root)['builds']['A'] == before
    # SendMessage delivers the continuation without an Agent launch hook.
    with (root / 'agent.jsonl').open('a') as stream:
        stream.write(json.dumps({'type': 'user', 'message': {'content': 'Owner answered Yes'}}) + '\n')
    if manual:
        with (root / 'agent.jsonl').open('a') as stream:
            stream.write(HANDBACK)
        code, out = seat_stop(capsys, 'builder', '--verdict')
        assert code == 0, out.err
        assert state.read_state(root)['builds']['A']['completion'] == brief.last_turn(root / 'agent.jsonl')[0]
    else:
        assert handback_stop(seat) == (0, '')
        assert agent_launch.stop(payload) == (0, '')
    assert build.step('A', root)['action'] == 'check'
    assert build.step('A', root)['action'] == 'check'
    assert state.read_state(root)['builds']['A']['iteration'] == 2


def add_seat(root, name, role, status='running'):
    """A reserved seat and its agent transcript holding the brief reference."""
    relative = f'.wuwei/days/{state.workspace.day_dir(root).name}/briefs/{name}.md'
    state._write_state(lambda data: data['seats'].update({name: {
        'id': name, 'role': role, 'item': 'A', 'brief': relative, 'status': status}}),
        root)
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
                       root)
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


def test_unmatched_seat_stop_is_recorded(seat, monkeypatch, capsys):
    # #847: a stop that matches no reservation is recorded; no session registry row.
    root, _, _, day, _ = seat
    transcript = write(root / 'stray.jsonl',
                       {'type': 'user', 'message': {'content': brief.REFERENCE_PREFIX + 'elsewhere.md'}})
    code, err = hook_stop(monkeypatch, capsys, cwd=str(root), agent_type='wuwei:builder', agent_id='agent-stray',
                          agent_transcript_path=str(transcript),
                          last_assistant_message='Blocked: none\nGap: none\nChange: none')
    assert code == 0, err
    rows = events(day)
    assert 'seat stop unmatched' in [row['kind'] for row in rows]
    assert 'abc123' not in state.read_state(root).get('sessions', {})
    assert 'session.seen' not in [row['kind'] for row in rows]


def stuck_day(root):
    """A builder seat running with a recorded transcript that ends in the hand-back."""
    transcript = add_seat(root, 'stuck', 'builder')
    with transcript.open('a') as stream:
        stream.write(HANDBACK)
    state._write_state(lambda data: data['seats']['stuck'].update(transcript=str(transcript)),
                       root)
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
    assert brief.stuck({'seats': seats}) == ['b-handback']


def test_next_names_stuck_seat(seat):
    from wuwei.commands import next as next_command
    root, _, _, day, _ = seat
    (root / '.wuwei/calibration.json').write_text('{"calibrated": true}')
    (day / 'plan.md').write_text('# Plan\n')
    state._write_state(lambda data: data.update(gate_approved=True, approved_items=['A'],
                                                planner_session_id='S'), root)
    state.append_event('next.action', {'state': 'x', 'done': [['calibrate', '']]}, root)  # #551: done
    assert [launch['kind'] for launch in next_command.step(root)['launches']] == ['build']
    stuck_day(root)
    launch = next_command.step(root)['launches'][0]
    assert launch['kind'] == 'stop'
    assert launch['command'] == 'wuwei seat stop stuck --verdict'  # #905: its hand-back is recorded first


def test_doctor_seats_probe(seat):
    from wuwei.commands import doctor
    root = seat[0]
    assert doctor._seats(root) == ('ok', 'none stuck')
    stuck_day(root)
    result, value = doctor._seats(root)
    assert result == 'failed' and value.startswith('dead: stuck;') and 'wuwei seat stop stuck --verdict' in value
    assert '--unmeasured' not in value


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


def _case_seat_stop_verdict_builder(seat, monkeypatch, capsys):
    root, report = stuck_builder(seat, monkeypatch)
    code, out = seat_stop(capsys, 'builder', '--verdict', report)
    assert code == 0, out.err
    data = state.read_state(root)
    assert data['seats']['builder']['status'] == 'stopped'
    assert data['builds']['A']['status'] == 'check' and data['builds']['A']['result']['text'] == REPORT_FILE
    assert kinds(seat[3]) == ['seat.usage', 'seat stopped']


def _case_seat_stop_verdict_after_unmeasured(seat, monkeypatch, capsys):
    root, report = stuck_builder(seat, monkeypatch)
    (root / 'agent.jsonl').write_text((root / 'agent.jsonl').read_text().replace(HANDBACK, ''))
    assert torn_stop(root, 'builder', 'builder', root / 'agent.jsonl')[0] == 2
    assert brief.stuck(state.read_state(root)) == []
    code, out = seat_stop(capsys, 'builder', '--verdict', report)
    assert code == 0, out.err
    data = state.read_state(root)
    assert data['seats']['builder']['status'] == 'stopped' and 'reason' not in data['seats']['builder']
    assert data['builds']['A']['result']['text'] == REPORT_FILE
    assert brief.stuck(data) == []


def _case_seat_stop_verdict_sentinel_lint(seat, monkeypatch, capsys):
    root = seat[0]
    monkeypatch.delenv('WUWEI_SESSION_ID', raising=False)
    add_seat(root, 'quality', 'sentinel-quality')
    report = root / 'verdict.md'
    report.write_text('No verdict here.\n')
    before = state.read_state(root)['seats']
    code, out = seat_stop(capsys, 'quality', '--verdict', report)
    assert code == 1 and 'Verdict' in out.err
    assert state.read_state(root)['seats'] == before


def _case_seat_stop_unmeasured_parks_builder(seat, monkeypatch, capsys):
    root, _ = stuck_builder(seat, monkeypatch)
    code, out = seat_stop(capsys, 'builder', '--unmeasured', 'seat process gone')
    assert code == 0, out.err
    data = state.read_state(root)
    record = data['seats']['builder']
    assert (record['status'], record['reason'], record['by']) == ('unmeasured', 'seat process gone', 'owner')
    assert data['builds']['A']['status'] == 'parked'
    assert 'seat process gone' in data['builds']['A']['action']['reason']
    assert brief.stuck(data) == []


def _case_seat_stop_refusals(seat, monkeypatch, capsys):
    root, report = stuck_builder(seat, monkeypatch)
    add_seat(root, 'done', 'sentinel-arch', status='stopped')
    before = (state.workspace.day_dir(root) / 'state.json').read_text()
    assert seat_stop(capsys, 'done', '--unmeasured', 'x')[0] == 1
    assert seat_stop(capsys, 'nobody', '--unmeasured', 'x')[0] == 1
    assert seat_stop(capsys, 'builder', '--unmeasured', ' ')[0] == 2
    assert seat_stop(capsys, 'builder', '--unmeasured', 'one\ntwo')[0] == 2
    monkeypatch.setenv('WUWEI_SESSION_ID', 'some-seat')
    code, out = seat_stop(capsys, 'builder', '--verdict', report)
    assert code == 1 and 'planner session' in out.err
    assert (state.workspace.day_dir(root) / 'state.json').read_text() == before
    monkeypatch.delenv('WUWEI_SESSION_ID')
    assert seat_stop(capsys, 'builder', '--unmeasured', 'x')[0] == 0


def _case_seat_stop_planner_session_allowed(seat, monkeypatch, capsys):
    root, report = stuck_builder(seat, monkeypatch)
    state._write_state(lambda data: data.update(planner_session_id='planner-1'), root)
    monkeypatch.setenv('WUWEI_SESSION_ID', 'planner-1')
    code, out = seat_stop(capsys, 'builder', '--verdict', report)
    assert code == 0, out.err


@pytest.mark.parametrize("scenario_fn", [
    _case_seat_stop_verdict_builder,
    _case_seat_stop_verdict_after_unmeasured,
    _case_seat_stop_verdict_sentinel_lint,
    _case_seat_stop_unmeasured_parks_builder,
    _case_seat_stop_refusals,
    _case_seat_stop_planner_session_allowed,
])
def test_seat_stop_cases_413(seat, monkeypatch, capsys, scenario_fn):
    scenario_fn(seat, monkeypatch, capsys)


def stop_offers(root):
    """The stuck-seat commands wuwei next offers on an approved day."""
    from wuwei.commands import next as next_command
    day = state.workspace.day_dir(root)
    (root / '.wuwei/calibration.json').write_text('{"calibrated": true}')
    (day / 'plan.md').write_text('# Plan\n')
    state._write_state(lambda data: data.update(gate_approved=True, approved_items=['A'],
                                                planner_session_id='S'), root)
    state.append_event('next.action', {'state': 'x', 'done': [['calibrate', '']]}, root)
    return [launch['command'] for launch in next_command.step(root).get('launches', []) if launch['kind'] == 'stop']


def stop_kinds(day):
    return [row['kind'] for row in events(day) if row['kind'] in ('seat.usage', 'seat stopped')]


@pytest.mark.parametrize('usage', [{'usage': {'input_tokens': -1}}, {'usage': 'many'}, {'duration_ms': 'x'}])
def test_malformed_usage_keeps_the_result(seat, usage):
    # #905: usage metadata the runtime got wrong is unmeasured; the finished build still counts.
    root, _, _, day, _ = seat
    launch(seat, build.next_action('A', root=root))
    assert handback_stop(seat, **usage) == (0, '')
    data = state.read_state(root)
    assert data['seats']['builder']['status'] == 'stopped'
    assert data['builds']['A']['status'] == 'check' and data['builds']['A']['result']['text'] == REPORT
    recorded = next(row['payload']['usage'] for row in events(day) if row['kind'] == 'seat.usage')
    assert recorded['input_tokens'] == recorded['duration'] == 'unmeasured'


def test_unrecorded_result_ends_the_seat_and_keeps_its_report(seat, monkeypatch, capsys):
    # #905: a result that cannot be recorded never leaves a dead seat running; the report is
    # kept for explicit recovery, and the result is recorded once.
    root, _, _, day, _ = seat
    monkeypatch.delenv('WUWEI_SESSION_ID', raising=False)
    launch(seat, build.next_action('A', root=root))
    original = build.record_result

    def broken(*args, **kwargs):
        raise OSError('state write failed')
    monkeypatch.setattr(build, 'record_result', broken)
    code, reason = handback_stop(seat)
    assert code == 2 and 'seat builder stopped unmeasured: state write failed' in reason
    assert 'wuwei seat stop builder --verdict,' in reason
    data = state.read_state(root)
    record = data['seats']['builder']
    assert record['status'] == 'unmeasured' and (root / record['report']).read_text() == REPORT
    assert data['builds']['A']['status'] == 'running'
    assert brief.stuck(data) == []  # no recorded terminal evidence; the task may still be alive
    assert stop_offers(root) == []
    monkeypatch.setattr(build, 'record_result', original)
    code, out = seat_stop(capsys, 'builder', '--verdict')
    assert code == 0, out.err
    data = state.read_state(root)
    assert data['seats']['builder']['status'] == 'stopped' and 'report' not in data['seats']['builder']
    assert data['builds']['A']['status'] == 'check' and data['builds']['A']['result']['text'] == REPORT
    assert stop_kinds(day) == ['seat stopped', 'seat.usage', 'seat stopped']
    assert handback_stop(seat) == (0, '')  # the seat's own late stop records nothing more
    assert stop_kinds(day) == ['seat stopped', 'seat.usage', 'seat stopped']


def test_stuck_seat_offers_its_transcript_report(seat, monkeypatch, capsys):
    # #905: a running seat whose transcript ends in the hand-back is offered --verdict, and
    # the report its transcript holds is recorded through the stop guards.
    root, _, _, day, _ = seat
    monkeypatch.delenv('WUWEI_SESSION_ID', raising=False)
    transcript = add_seat(root, 'quality', 'sentinel-quality')
    with transcript.open('a') as stream:
        stream.write(HANDBACK)
    state._write_state(lambda data: data['seats']['quality'].update(transcript=str(transcript)), root)
    assert stop_offers(root)[0] == 'wuwei seat stop quality --verdict'
    code, out = seat_stop(capsys, 'quality', '--verdict')
    assert code == 1 and 'Verdict' in out.err  # the sentinel's report goes through the verdict lint
    assert (state.workspace.day_dir(root) / 'reports/quality.md').read_text() == REPORT


def test_unreadable_report_never_offers_an_automatic_stop(seat):
    root, _, _, _, _ = seat
    transcript = add_seat(root, 'quality', 'sentinel-quality')
    assert torn_stop(root, 'quality', 'sentinel-quality', transcript)[0] == 2
    assert 'report' not in state.read_state(root)['seats']['quality']
    assert stop_offers(root) == []


def test_duplicate_stop_records_once(seat):
    # #905: a stop the retro guard sent back for repair stops again; the seat's end counts once.
    root, _, _, day, _ = seat
    transcript = add_seat(root, 'quality', 'sentinel-quality')
    with transcript.open('a') as stream:
        stream.write(HANDBACK)
    payload = {'cwd': str(root), 'agent_type': 'wuwei:sentinel-quality', 'agent_id': 'agent-quality',
               'agent_transcript_path': str(transcript)}
    assert agent_launch.stop(payload) == (0, '')
    assert agent_launch.stop({**payload, 'stop_hook_active': True}) == (0, '')
    assert [row['payload']['name'] for row in events(day) if row['kind'] == 'seat stopped'] == ['quality']


def test_late_or_foreign_stop_never_ends_the_bound_seat(seat):
    # #905: identity is checked before the report is read; a replaced agent's late stop, even
    # with an unreadable report, and a stop from another agent leave the bound seat running.
    root, _, _, day, results = seat
    launch(seat, build.next_action('A', root=root))
    assert handback_stop(seat) == (0, '')
    results.append(registry.Result(1, {'test_ids': ['test_one'], 'error': 'failure'}))
    assert main(['build', 'check', 'A']) == 1
    action = build.next_action('A', root=root)
    launch(seat, action)  # a fresh agent: agent-builder is replaced
    late = write(root / 'late.jsonl', {'type': 'user', 'message': {'content': action['prompt']}},
                 raw='{"type": "assistant", "message": {"content": [{"type": "te')
    payload = {'cwd': str(root), 'agent_type': 'wuwei:builder', 'agent_transcript_path': str(late)}
    assert agent_launch.stop({**payload, 'agent_id': 'agent-builder'}) == (0, '')
    data = state.read_state(root)
    assert data['seats']['builder']['status'] == data['builds']['A']['status'] == 'running'
    assert handback_stop(seat, agent_id='agent-fresh') == (0, '')
    results.append(registry.Result(1, {'test_ids': ['test_one'], 'error': 'failure'}))
    assert main(['build', 'check', 'A']) == 1
    action = build.next_action('A', root=root)
    launch(seat, action, action['resume'])  # resumes agent-fresh
    code, reason = agent_launch.stop({**payload, 'agent_id': 'agent-other'})
    assert code == 2 and 'differs from resumed builder' in reason
    data = state.read_state(root)
    assert data['seats']['builder']['status'] == data['builds']['A']['status'] == 'running'


def test_tampered_kept_report_is_refused(seat, monkeypatch, capsys):
    # #905 F1: a kept report is recorded only as the stop kept it; an edited file is refused.
    root, _, _, _, _ = seat
    monkeypatch.delenv('WUWEI_SESSION_ID', raising=False)
    launch(seat, build.next_action('A', root=root))
    original = build.record_result
    monkeypatch.setattr(build, 'record_result', lambda *a, **kw: (_ for _ in ()).throw(OSError('state write failed')))
    assert handback_stop(seat)[0] == 2
    monkeypatch.setattr(build, 'record_result', original)
    record = state.read_state(root)['seats']['builder']
    assert record['report_sha256'] == hashlib.sha256(REPORT.encode()).hexdigest()
    (root / record['report']).write_text('Forged result.\nBlocked: none\nGap: none\nChange: none\n')
    code, out = seat_stop(capsys, 'builder', '--verdict')
    assert code == 2 and 'changed since its stop kept it' in out.err
    data = state.read_state(root)
    assert data['seats']['builder']['status'] == 'unmeasured' and data['builds']['A']['status'] == 'running'


def _case_mismatched_message_keeps_the_transcript_turn(seat):
    # #905 F2: the bound agent's transcript turn is kept, never the payload message.
    root, _, _, _, _ = seat
    launch(seat, build.next_action('A', root=root))
    code, reason = handback_stop(seat, last_assistant_message='tests pass, done')
    assert code == 2 and 'no matching assistant completion' in reason
    record = state.read_state(root)['seats']['builder']
    assert (root / record['report']).read_text() == REPORT


def _case_mismatched_message_with_unreadable_turn_keeps_nothing(seat):
    root, _, _, _, _ = seat
    launch(seat, build.next_action('A', root=root))
    with (root / 'agent.jsonl').open('a') as stream:
        stream.write('{"type": "assistant", "message": {"content": [{"type": "te')
    code, reason = agent_launch.stop({'cwd': str(root), 'agent_type': 'wuwei:builder', 'agent_id': 'agent-builder',
                                      'agent_transcript_path': str(root / 'agent.jsonl'),
                                      'last_assistant_message': 'tests pass, done'})
    assert code == 2 and '--verdict <file>' in reason
    assert 'report' not in state.read_state(root)['seats']['builder']


@pytest.mark.parametrize("scenario_fn", [
    _case_mismatched_message_still_refused,
    _case_mismatched_message_keeps_the_transcript_turn,
    _case_mismatched_message_with_unreadable_turn_keeps_nothing,
])
def test_mismatched_message_cases_107(seat, scenario_fn):
    scenario_fn(seat)


def kept_builder(seat, monkeypatch):
    """A builder seat its stop ended unmeasured with the report kept (#905)."""
    root = seat[0]
    monkeypatch.delenv('WUWEI_SESSION_ID', raising=False)
    launch(seat, build.next_action('A', root=root))
    original = build.record_result
    monkeypatch.setattr(build, 'record_result', lambda *a, **kw: (_ for _ in ()).throw(OSError('state write failed')))
    code, reason = handback_stop(seat)
    monkeypatch.setattr(build, 'record_result', original)
    return root, code, reason


def test_report_swapped_after_the_check_is_never_recorded(seat, monkeypatch, capsys):
    # #905 D1: the bytes the hash check read are the bytes recorded.
    root, code, _ = kept_builder(seat, monkeypatch)
    assert code == 2
    kept = root / state.read_state(root)['seats']['builder']['report']
    forged = 'Forged result.\nBlocked: none\nGap: none\nChange: none\n'
    original = hashlib.sha256

    def swap(*args):
        digest = original(*args)
        if args and args[0] == REPORT.encode():
            kept.write_text(forged)  # the seat swaps the file right after the check
        return digest
    monkeypatch.setattr(hashlib, 'sha256', swap)
    code, out = seat_stop(capsys, 'builder', '--verdict')
    assert code == 0, out.err
    assert state.read_state(root)['builds']['A']['result']['text'] == REPORT


def test_symlinked_reports_directory_keeps_nothing(seat, monkeypatch, tmp_path_factory):
    # #905 D1: a reports directory a seat pointed elsewhere is never written or read.
    elsewhere = tmp_path_factory.mktemp('elsewhere')
    (state.workspace.day_dir(seat[0]) / 'reports').symlink_to(elsewhere, target_is_directory=True)
    root, code, reason = kept_builder(seat, monkeypatch)
    assert code == 2 and '--verdict <file>' in reason
    assert 'report' not in state.read_state(root)['seats']['builder']
    assert not list(elsewhere.iterdir())


@pytest.mark.parametrize('ending', ['pending', 'refused', 'unrelated'])
def test_live_task_with_attempted_handback_has_no_stop_offer(seat, ending):
    root = seat[0]
    transcript = add_seat(root, 'builder', 'builder')
    rows = [json.loads(line) for line in HANDBACK.splitlines()]
    if ending == 'pending':
        rows = rows[:1]
    elif ending == 'refused':
        rows[1]['message']['content'][0].update(is_error=True, content='Session is not in auto mode')
        rows[1]['toolUseResult'] = 'Error: Only the auto-mode classifier can allow SubagentHandback'
        rows[1]['toolDenialKind'] = 'permission'
        rows[1]['toolEndsTurn'] = False
    else:
        rows[1]['message']['content'][0]['tool_use_id'] = 'another-call'
    with transcript.open('a') as stream:
        stream.write(''.join(json.dumps(row) + '\n' for row in rows))
    state._write_state(lambda data: data['seats']['builder'].update(transcript=str(transcript)), root)
    assert stop_offers(root) == []
    assert state.read_state(root)['seats']['builder']['status'] == 'running'


def test_resumed_task_and_non_object_rows_are_not_stuck(seat):
    root = seat[0]
    transcript = stuck_day(root)
    with transcript.open('a') as stream:
        stream.write(json.dumps({'type': 'user', 'message': {'content': 'Continue with the remaining work'}}) + '\n')
        stream.write('null\n[]\n')
    assert stop_offers(root) == []


def test_rejected_unreadable_stop_is_not_completion_evidence(seat, monkeypatch, capsys):
    root = seat[0]
    launch(seat, build.next_action('A', root=root))
    code, _ = hook_stop(monkeypatch, capsys, cwd=str(root), agent_type='wuwei:builder',
                       agent_id='agent-builder', agent_transcript_path=str(root / 'agent.jsonl'))
    assert code == 2  # the runtime continues after the hook blocks its attempted stop
    assert stop_offers(root) == []


def test_unreadable_stop_records_a_result_gap(seat):
    root, _, _, day, _ = seat
    transcript = add_seat(root, 'quality', 'sentinel-quality')
    assert torn_stop(root, 'quality', 'sentinel-quality', transcript)[0] == 2
    gap = [row['payload'] for row in events(day) if row['kind'] == 'seat.result_gap'][-1]
    assert gap['name'] == 'quality' and gap['reason']
