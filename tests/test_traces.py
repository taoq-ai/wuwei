"""Tool trace contracts, using in-process hooks and temporary workspaces."""

from concurrent.futures import ThreadPoolExecutor
import json
import os
import hashlib
import signal
from time import process_time

import pytest

from wuwei import state, workspace


@pytest.mark.parametrize('value', ['safe ' * 410, 'password=swordfish ' + 'x' * 2100],
                         ids=['ordinary', 'secret'])
def test_large_strings_are_truncated_before_redaction(value):
    from wuwei.redact import redact
    marker = f'[TRUNCATED {len(value)} chars sha256:{hashlib.sha256(value.encode()).hexdigest()}]'
    assert redact(value) == redact(value[:512]) + marker


@pytest.mark.parametrize('value', ['x' * (5 * 1024 * 1024), 'abcdef0123456789' * 6400],
                         ids=['5MB-Write', '100KB-hex'])
def test_large_arguments_record_under_50ms_cpu(trace_workspace, call_payload, value):
    check = recorder()
    call_payload.update(tool_name='Write', tool_input={'file_path': 'output.txt', 'content': value})

    def deadline(*args):
        raise TimeoutError('redaction exceeded CPU deadline')

    previous = signal.signal(signal.SIGPROF, deadline)
    started = process_time()
    signal.setitimer(signal.ITIMER_PROF, 0.25)
    try:
        result = check(call_payload)
    finally:
        signal.setitimer(signal.ITIMER_PROF, 0)
        signal.signal(signal.SIGPROF, previous)
    elapsed = process_time() - started
    assert result == (0, '')
    assert elapsed < 0.05
    span, = read_spans(trace_workspace)
    content = json.loads(span['attrs']['gen_ai.tool.arguments'])['content']
    assert content == value[:512] + f'[TRUNCATED {len(value)} chars sha256:{hashlib.sha256(value.encode()).hexdigest()}]'


@pytest.fixture
def trace_workspace(tmp_path, monkeypatch):
    (tmp_path / '.wuwei').mkdir()
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T12:34:56+02:00')
    return workspace.day_dir(tmp_path)


def test_shared_append_preserves_concurrent_records(trace_workspace):
    append = getattr(state, 'append_jsonl', None)
    assert callable(append), 'state needs a shared locked JSONL append helper'
    path = trace_workspace / 'traces.jsonl'
    append(path, {'first': True})
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda i: append(path, {'index': i, 'text': 'a\nb' * 5000}), range(24)))
    records = [json.loads(line) for line in path.read_text().splitlines()]
    assert records[0] == {'first': True}
    assert sorted(r['index'] for r in records[1:]) == list(range(24))
    assert path.stat().st_mode & 0o777 == 0o444


def test_shared_append_holds_lock_and_detects_short_write(trace_workspace, monkeypatch):
    append = getattr(state, 'append_jsonl', None)
    assert callable(append), 'state needs a shared locked JSONL append helper'

    def short_write(fd, encoded):
        with (trace_workspace / 'state.lock').open('a') as probe:
            with pytest.raises(BlockingIOError):
                state.fcntl.flock(probe, state.fcntl.LOCK_EX | state.fcntl.LOCK_NB)
        return len(encoded) - 1

    monkeypatch.setattr(state.os, 'write', short_write)
    with pytest.raises(OSError, match='short .*write'):
        append(trace_workspace / 'traces.jsonl', {'probe': True})


@pytest.fixture
def call_payload(trace_workspace):
    from uuid import uuid4
    return {'session_id': uuid4().hex, 'cwd': str(trace_workspace.parents[2]),
            'transcript_path': str(trace_workspace / 'unused.jsonl'),
            'hook_event_name': 'PostToolUse', 'tool_name': 'Read',
            'tool_input': {'file_path': 'README.md'}, 'agent_type': 'builder',
            'duration_ms': 12.5}


def recorder():
    from wuwei.guards import discover
    guards = [g for g in discover() if g.event == 'PostToolUse' and g.matcher is None]
    assert len(guards) == 1, 'PostToolUse must register the trace recorder for all tools'
    return guards[0].check


def read_spans(directory):
    # Follow ZIRAN OTelIngestor._process_batch and _get_attribute traversal.
    spans = []
    for line in (directory / 'traces.jsonl').read_text().splitlines():
        batch = json.loads(line)
        resource, = batch['resourceSpans']
        scope, = resource['scopeSpans']
        span, = scope['spans']
        span['attrs'] = {a['key']: a['value']['stringValue'] for a in span['attributes']}
        span['service'] = {a['key']: a['value']['stringValue']
                           for a in resource['resource']['attributes']}['service.name']
        spans.append(span)
    return spans


def test_read_then_webfetch_same_session(trace_workspace, call_payload, monkeypatch):
    import re
    from uuid import uuid4
    check = recorder()
    assert check(call_payload) == (0, '')
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T12:34:57+02:00')
    second = {**call_payload, 'tool_name': 'WebFetch', 'duration_ms': 100,
              'tool_input': {'url': 'https://example.test/docs', 'prompt': 'Summarize'}}
    assert check(second) == (0, '')
    spans = read_spans(trace_workspace)
    assert [s['attrs']['gen_ai.tool.name'] for s in spans] == ['Read', 'WebFetch']
    assert [s['name'] for s in spans] == ['Read', 'WebFetch']
    assert len({s['traceId'] for s in spans}) == 1
    assert len({s['spanId'] for s in spans}) == 2
    for span, payload in zip(spans, [call_payload, second]):
        assert re.fullmatch('[0-9a-f]{32}', span['traceId'])
        assert re.fullmatch('[0-9a-f]{16}', span['spanId'])
        assert span['parentSpanId'] == ''
        assert span['attrs']['session.id'] == call_payload['session_id']
        assert span['attrs']['gen_ai.agent.name'] == span['service'] == 'builder'
        assert json.loads(span['attrs']['gen_ai.tool.arguments']) == payload['tool_input']
        assert int(span['endTimeUnixNano']) - int(span['startTimeUnixNano']) == int(payload['duration_ms'] * 1_000_000)
    assert int(spans[0]['endTimeUnixNano']) == 1790591696000000000
    assert int(spans[0]['startTimeUnixNano']) < int(spans[1]['startTimeUnixNano'])
    assert check({**second, 'session_id': uuid4().hex}) == (0, '')
    assert read_spans(trace_workspace)[-1]['traceId'] != spans[0]['traceId']


@pytest.mark.parametrize('tool', ['Bash', 'Agent', 'mcp__example__operation'])
def test_unknown_tools_defaults_and_parent(trace_workspace, call_payload, tool):
    from uuid import uuid4
    call_payload.pop('duration_ms')
    call_payload.pop('agent_type')
    call_payload.update(tool_name=tool, parent_span_id=uuid4().hex[:16], agent_role='invented')
    assert recorder()(call_payload) == (0, '')
    span, = read_spans(trace_workspace)
    assert span['startTimeUnixNano'] == span['endTimeUnixNano']
    assert span['attrs']['gen_ai.agent.name'] == 'unknown'
    assert span['attrs']['gen_ai.tool.name'] == tool
    assert span['parentSpanId'] == ''
    call_payload['agent_type'] = 'sentinel'
    assert recorder()(call_payload) == (0, '')
    assert read_spans(trace_workspace)[-1]['service'] == 'sentinel'


@pytest.mark.parametrize('field,value', [
    ('session_id', ''), ('session_id', 4), ('tool_name', ''), ('tool_name', []),
    ('tool_input', None), ('tool_input', []), ('duration_ms', -1),
    ('duration_ms', True), ('duration_ms', '12'), ('duration_ms', float('inf')),
    ('duration_ms', float('nan')), ('agent_type', 3),
])
def test_invalid_span_metadata_is_unrun_without_append(trace_workspace, call_payload, field, value):
    call_payload[field] = value
    code, reason = recorder()(call_payload)
    assert (code, reason) == (0, '')
    assert field in error_events(trace_workspace)[0]['payload']['reason']
    assert not (trace_workspace / 'traces.jsonl').exists()


def test_payload_cwd_workspace_discovery(trace_workspace, call_payload, monkeypatch):
    monkeypatch.delenv('WUWEI_WORKSPACE')
    nested = trace_workspace.parents[2] / 'project/subdirectory'
    nested.mkdir(parents=True)
    call_payload['cwd'] = str(nested)
    assert recorder()(call_payload) == (0, '')
    assert len(read_spans(trace_workspace)) == 1


@pytest.mark.parametrize('arguments', [{'file_path': 'README.md'}, None])
def test_no_workspace_is_quiet(tmp_path, call_payload, monkeypatch, capsys, arguments):
    monkeypatch.delenv('WUWEI_WORKSPACE')
    outside = tmp_path.parent / (tmp_path.name + '-outside')
    outside.mkdir()
    call_payload.update(cwd=str(outside), tool_input=arguments)
    assert recorder()(call_payload) == (0, '')
    output = capsys.readouterr()
    assert output.out == output.err == ''
    assert list(outside.iterdir()) == []


def test_external_worktree_uses_workspace_override(trace_workspace, call_payload):
    call_payload['cwd'] = '/external/worktree'
    assert recorder()(call_payload) == (0, '')
    assert len(read_spans(trace_workspace)) == 1


@pytest.mark.parametrize('previous', [b'{"before": true}', b'{"partial":'])
def test_append_separates_unterminated_record(trace_workspace, previous):
    trace_workspace.mkdir(parents=True)
    path = trace_workspace / 'traces.jsonl'
    path.write_bytes(previous)
    state.append_jsonl(path, {'after': True})
    assert path.read_bytes() == previous + b'\n{"after": true}\n'


@pytest.mark.parametrize('arguments', [
    {'password': 'swordfish'}, {'API_KEY': 'swordfish'}, {'apiKey': 'swordfish'},
    {'nested': [{'Access-Token': 'swordfish'}]},
    {'authorization': {'scheme': 'Bearer', 'value': 'swordfish'}},
    {'command': 'env API_KEY=swordfish bash -c "echo done"'},
    {'command': 'sh -c \'curl -H "Authorization: Bearer swordfish" example.test\''},
    {'command': 'python -c "print(\'password=swordfish\')"'},
    {'command': 'curl --api-key swordfish example.test'},
    {'url': 'https://example.test/?token=swordfish'},
    {'url': 'https://example.test/?api%5Fkey=swordfish'},
    {'url': 'https://user:swordfish@example.test/'},
    {'value': 'Basic c3dvcmRmaXNo'},
    {'value': 'ghp_' + 'a' * 36}, {'value': 'github_pat_' + 'a' * 50},
    {'value': 'sk-proj-' + 'b' * 30}, {'value': 'sk-ant-' + 'c' * 30},
    {'value': 'xoxb-' + '1234567890-' * 2 + 'abcd'},
    {'value': 'AKIA' + 'A' * 16}, {'value': 'ASIA' + 'B' * 16},
    {'value': 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0In0.signature'},
    {'value': '-----BEGIN RSA PRIVATE KEY-----\nprivate material\n-----END RSA PRIVATE KEY-----'},
    {'phone_number': '+31 20 555 0100'}, {'recipient': '+31 20 555 0100'},
    {'message': 'private message'}, {'messageBody': 'private message'},
    {'body': {'text': 'private message'}}, {'text': 'private message'},
])
def test_redacts_sensitive_arguments_before_append(trace_workspace, call_payload, monkeypatch, arguments):
    from copy import deepcopy
    original = deepcopy(arguments)
    call_payload['tool_input'] = {'safe': {'count': 3, 'flags': [True, None], 'path': 'README.md'},
                                  'nested': arguments}
    call_payload['tool_response'] = {'secret': 'response must not be recorded'}
    appended = []
    append = state.append_jsonl

    def inspect(path, record):
        appended.append(json.dumps(record))
        append(path, record)

    monkeypatch.setattr(state, 'append_jsonl', inspect)
    assert recorder()(call_payload) == (0, '')
    span, = read_spans(trace_workspace)
    actual = json.loads(span['attrs']['gen_ai.tool.arguments'])
    assert actual['safe'] == call_payload['tool_input']['safe']
    assert '[REDACTED]' in json.dumps(actual['nested'])
    assert actual['nested'] != original
    assert arguments == original
    assert 'response must not be recorded' not in appended[0]
    assert 'swordfish' not in appended[0]


def test_redacts_secret_keys_and_metadata(trace_workspace, call_payload):
    secret = 'ghp_' + 'd' * 36
    call_payload.update(session_id=secret, agent_type=secret, tool_name=secret,
                        tool_input={secret: 'value', 'safe': 'ordinary'})
    assert recorder()(call_payload) == (0, '')
    raw = (trace_workspace / 'traces.jsonl').read_text()
    assert secret not in raw
    assert '[REDACTED]' in raw


def run_hook(payload, monkeypatch, capsys):
    import io
    import sys
    from types import SimpleNamespace
    from wuwei.commands.hook import run
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    monkeypatch.setattr(sys, 'stdin', io.StringIO(raw))
    code = run(SimpleNamespace(event='PostToolUse'))
    return code, capsys.readouterr()


def error_events(directory):
    return [json.loads(line) for line in (directory / 'events.jsonl').read_text().splitlines()]


def test_hook_records_sequence(trace_workspace, call_payload, monkeypatch, capsys):
    for tool in ('Read', 'WebFetch'):
        call_payload['tool_name'] = tool
        code, output = run_hook(call_payload, monkeypatch, capsys)
        assert code == 0 and output.out == output.err == ''
    assert [s['name'] for s in read_spans(trace_workspace)] == ['Read', 'WebFetch']


@pytest.mark.parametrize('result', [0, 1, 2])
def test_post_tool_policy_results_reach_seat(trace_workspace, call_payload, monkeypatch, capsys, result):
    from wuwei.commands import hook
    from wuwei.guards import Guard
    monkeypatch.setattr(hook, 'discover', lambda: [Guard('PostToolUse', None,
                        lambda p: (result, 'test finding' if result else ''))])
    code, output = run_hook(call_payload, monkeypatch, capsys)
    assert code == (2 if result else 0) and output.out == ''
    assert not (trace_workspace / 'events.jsonl').exists()
    if result:
        assert 'test finding' in output.err
    else:
        assert output.err == ''
        assert not (trace_workspace / 'events.jsonl').exists()


@pytest.mark.parametrize('failure', ['trace', 'both', 'workspace', 'exception', 'registry', 'malformed', 'input'])
def test_post_tool_failures_report_without_refusing(trace_workspace, call_payload, monkeypatch, capsys, failure):
    from wuwei.commands import hook
    from wuwei.guards import Guard
    trace_workspace.mkdir(parents=True)
    secret = 'unstructured private failure details'

    def broken(*args):
        raise OSError(secret)

    if failure in ('trace', 'both'):
        (trace_workspace / 'traces.jsonl').mkdir()
    if failure == 'both':
        (trace_workspace / 'events.jsonl').mkdir()
    if failure == 'workspace':
        monkeypatch.setenv('WUWEI_WORKSPACE', str(trace_workspace / 'missing'))
    if failure == 'exception':
        monkeypatch.setattr(hook, 'discover', lambda: [Guard('PostToolUse', None, broken)])
    if failure == 'registry':
        monkeypatch.setattr(hook, 'discover', broken)
    if failure == 'malformed':
        call_payload = '{'
    if failure == 'input':
        call_payload['tool_input'] = []
    code, output = run_hook(call_payload, monkeypatch, capsys)
    assert code == (2 if failure in ('exception', 'registry', 'malformed') else 0)
    assert output.out == ''
    assert output.err and 'Traceback' not in output.err
    assert secret not in output.err
    if failure in ('exception', 'registry', 'malformed'):
        assert not (trace_workspace / 'events.jsonl').exists()
    elif failure not in ('both', 'workspace'):
        event, = error_events(trace_workspace)
        assert event['kind'] == 'hook.post_tool_use_error'
        assert secret not in json.dumps(event)
        assert event['payload']['reason'] in output.err
    else:
        assert 'could not log' in output.err


def test_error_logging_uses_payload_workspace(trace_workspace, call_payload, monkeypatch, capsys):
    monkeypatch.delenv('WUWEI_WORKSPACE')
    call_payload['tool_input'] = None
    code, output = run_hook(call_payload, monkeypatch, capsys)
    assert code == 0 and output.err
    assert error_events(trace_workspace)[0]['kind'] == 'hook.post_tool_use_error'


@pytest.mark.parametrize('error', [OSError, SystemExit, KeyboardInterrupt])
def test_recorder_owns_failures(trace_workspace, call_payload, monkeypatch, capsys, error):
    def broken(*args):
        raise error('private details')

    monkeypatch.setattr(state, 'append_jsonl', broken)
    code, output = run_hook(call_payload, monkeypatch, capsys)
    assert code == 0 and output.out == ''
    event, = error_events(trace_workspace)
    assert event['kind'] == 'hook.post_tool_use_error'
    assert error.__name__ in output.err
    assert 'private details' not in output.err + json.dumps(event)


@pytest.mark.parametrize('command', [
    'signal-cli send --message "private details" recipient',
    'curl --data "private details" https://example.test',
    'curl -d "private details" https://example.test',
    'curl --json \'{"text": "private details"}\' https://example.test',
    'curl --data \'{"text": "private details"}\' https://example.test',
    'tool --private-key "private details"',
    'tool --authorization "private details"',
    'tool --cookie "private details"',
    'tool \'{"text": "private details"}\'',
    r'tool "{\"text\": \"private details\"}"',
])
def test_redacts_messages_and_credential_flags_in_strings(trace_workspace, call_payload, command):
    call_payload.update(tool_name='Bash', tool_input={'command': command})
    assert recorder()(call_payload) == (0, '')
    assert 'private details' not in (trace_workspace / 'traces.jsonl').read_text()


@pytest.mark.parametrize('arguments', [
    {'file_path': '.env', 'content': 'private details'},
    {'file_path': '/repo/.env.local', 'new_string': 'private details'},
    {'file_path': 'cert.pem', 'content': 'private details'},
    {'file_path': 'server.key', 'new_string': 'private details'},
    {'file_path': '/repo/credentials.json', 'content': 'private details'},
    {'file_path': '/repo/secrets/config', 'new_string': 'private details'},
    {'pass': 'private details'}, {'db_pass': 'private details'},
    {'pwd': 'private details'}, {'auth': 'private details'},
    {'encryption_key': 'private details'}, {'signing-key': 'private details'},
    {'command': 'tool --pwd "private details"'},
    {'command': 'db_pass="private details" tool'},
    {'value': 'sk_live_private-details'}, {'value': 'sk_test_private-details'},
    {'value': 'rk_live_private-details'}, {'value': 'rk_test_private-details'},
    {'value': 'glpat-private-details'}, {'value': 'AIzaPrivateDetails'},
    {'value': 'npm_private-details'}, {'value': 'hf_private-details'},
    {'url': 'https://hooks.slack.com/services/private/details'},
    {'recipient': '020 555 0100'}, {'recipient': '(212) 555-0123'},
    {'recipient': '06-12345678'},
])
def test_review_redaction_cases(trace_workspace, call_payload, arguments):
    call_payload['tool_input'] = arguments
    assert recorder()(call_payload) == (0, '')
    span, = read_spans(trace_workspace)
    actual = json.loads(span['attrs']['gen_ai.tool.arguments'])
    for key, value in arguments.items():
        if key != 'file_path':
            assert actual[key] == '[REDACTED]'


@pytest.mark.parametrize('command', [
    'git commit -m "private details"',
    "git commit -m 'private details'",
    'git commit -m"private details"',
    'gh pr comment -b "private details"',
    'gh pr comment 12 --body "private details"',
    "gh pr comment 12 --body='private details'",
    "cat <<EOF\nprivate details\nEOF",
    "cat <<'EOF'\nprivate details\nEOF",
    'cat <<-EOF\nprivate details\nEOF',
])
def test_review_command_bodies(trace_workspace, call_payload, command):
    call_payload.update(tool_name='Bash', tool_input={'command': command})
    assert recorder()(call_payload) == (0, '')
    span, = read_spans(trace_workspace)
    actual = json.loads(span['attrs']['gen_ai.tool.arguments'])['command']
    digest = hashlib.sha256(b'private details').hexdigest()
    assert f'[BODY 15 chars sha256:{digest}]' in actual
    assert 'private details' not in actual


@pytest.mark.parametrize('prefix,quote', [('git commit -m ', '"'), ('gh pr comment --body ', "'")])
def test_truncated_command_body_stays_private(prefix, quote):
    from wuwei.redact import redact
    command = prefix + quote + 'private details ' * 200 + quote
    actual = redact(command)
    assert '[BODY ' in actual and '[TRUNCATED ' in actual
    assert 'private' not in actual and 'details' not in actual


def test_input_read_exception_never_logs_raw_details(trace_workspace, monkeypatch, capsys):
    import sys
    from types import SimpleNamespace
    from wuwei.commands.hook import run

    def broken_read():
        raise OSError('private details from input')

    monkeypatch.setattr(sys, 'stdin', SimpleNamespace(read=broken_read))
    assert run(SimpleNamespace(event='PostToolUse')) == 2
    output = capsys.readouterr()
    assert 'OSError' in output.err
    assert 'private details' not in output.err
    assert not (trace_workspace / 'events.jsonl').exists()


@pytest.mark.parametrize('duration', [10**1000, 1e16, 1e308])
def test_unrepresentable_duration_does_not_append(trace_workspace, call_payload, duration):
    call_payload['duration_ms'] = duration
    code, reason = recorder()(call_payload)
    assert (code, reason) == (0, '')
    assert 'duration_ms' in error_events(trace_workspace)[0]['payload']['reason']
    assert not (trace_workspace / 'traces.jsonl').exists()


@pytest.mark.parametrize('name', ['events.jsonl', 'traces.jsonl'])
@pytest.mark.parametrize('previous', [b'', b'{"before": true}', b'{"before": true}\n'])
@pytest.mark.parametrize('failure', ['short', 'error'])
def test_partial_write_does_not_corrupt_next_record(trace_workspace, monkeypatch,
                                                  name, previous, failure):
    trace_workspace.mkdir(parents=True)
    path = trace_workspace / name
    path.write_bytes(previous)
    path.chmod(0o444)
    original = path.read_bytes()
    write = os.write

    def short_write(fd, encoded):
        count = write(fd, encoded[:8])
        if failure == 'error':
            raise OSError('interrupted write')
        return count

    with monkeypatch.context() as patch:
        patch.setattr(state.os, 'write', short_write)
        with pytest.raises(OSError, match='write'):
            state.append_jsonl(path, {'incomplete': True})
    assert path.read_bytes() == original
    assert path.stat().st_mode & 0o777 == 0o444
    state.append_jsonl(path, {'after': True})
    assert path.stat().st_mode & 0o777 == 0o444
    assert [json.loads(line) for line in path.read_text().splitlines()] == [
        *([{'before': True}] if previous else []), {'after': True}]


def test_fractional_duration_cannot_round_before_epoch(trace_workspace, call_payload, monkeypatch):
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T12:34:56.000001+00:00')
    call_payload['duration_ms'] = 1790598896000.001
    code, reason = recorder()(call_payload)
    assert (code, reason) == (0, '')
    assert 'duration_ms' in error_events(trace_workspace)[0]['payload']['reason']
    assert not (trace_workspace / 'traces.jsonl').exists()
