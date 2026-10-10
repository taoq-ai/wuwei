"""Tool trace contracts, using in-process hooks and temporary workspaces."""

from concurrent.futures import ThreadPoolExecutor
import json
import os
import hashlib
import signal
from time import process_time

import pytest

from wuwei import state, workspace


def test_reply_keeps_a_known_api_message():
    # #738: GitHub's JSON error reply keeps its message; redact still runs on that message.
    from wuwei.redact import redact, reply
    known = '{"message":"%s","documentation_url":"https://docs.github.com/rest"}'
    assert reply(known % 'Resource not accessible by integration') == 'Resource not accessible by integration'
    assert reply(known % ('token ghp_' + 'a' * 36)) == '[REDACTED]'
    for line in ('{"message":"x: 1"}', 'not json', 'password=hunter2'):
        assert reply(line) == redact(line)


@pytest.mark.parametrize('value', ['safe ' * 410, 'password=swordfish ' + 'x' * 2100],
                         ids=['ordinary', 'secret'])
def test_large_strings_are_truncated_before_redaction(value):
    from wuwei.redact import redact
    marker = f'[TRUNCATED {len(value)} chars sha256:{hashlib.sha256(value.encode()).hexdigest()}]'
    assert redact(value) == redact(value[:512]) + marker


@pytest.mark.xdist_group('timing')
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
    (tmp_path / '.wuwei/config.toml').write_text('')
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
    external = trace_workspace.parents[2].parent / 'external-worktree'
    external.mkdir(exist_ok=True)
    config = trace_workspace.parents[1] / 'config.toml'
    config.write_text('[[repos]]\nname = "example"\npath = ' + json.dumps(str(external))
                      + '\ndefault_branch = "main"\n')
    call_payload['cwd'] = str(external)
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
    assert code == (2 if failure in ('exception', 'registry', 'malformed', 'workspace') else 0)
    assert output.out == ''
    assert output.err and 'Traceback' not in output.err
    assert secret not in output.err
    if failure in ('exception', 'registry', 'malformed', 'workspace'):
        assert not (trace_workspace / 'events.jsonl').exists()
    elif failure not in ('both', 'workspace'):
        event, = error_events(trace_workspace)
        assert event['kind'] == 'traces.gap'
        assert event['payload'].keys() >= {'reason', 'span', 'session'}
        assert event['payload']['span'] == 'Read' and event['payload']['session'] == call_payload['session_id']
        assert secret not in json.dumps(event)
        assert event['payload']['reason'] in output.err
    else:
        assert 'could not log' in output.err


def test_error_logging_uses_payload_workspace(trace_workspace, call_payload, monkeypatch, capsys):
    monkeypatch.delenv('WUWEI_WORKSPACE')
    call_payload['tool_input'] = None
    code, output = run_hook(call_payload, monkeypatch, capsys)
    assert code == 0 and output.err
    assert error_events(trace_workspace)[0]['kind'] == 'traces.gap'


@pytest.mark.parametrize('error', [OSError, SystemExit, KeyboardInterrupt])
def test_recorder_owns_failures(trace_workspace, call_payload, monkeypatch, capsys, error):
    def broken(*args):
        raise error('private details')

    monkeypatch.setattr(state, 'append_jsonl', broken)
    code, output = run_hook(call_payload, monkeypatch, capsys)
    assert code == 0 and output.out == ''
    event, = error_events(trace_workspace)
    assert event['kind'] == 'traces.gap'
    assert (event['payload']['span'], event['payload']['session']) == ('Read', call_payload['session_id'])
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
        if key in ('command', 'url', 'recipient'):  # #473: the text before the first credential stays
            assert actual[key].endswith('[REDACTED]') and len(actual[key]) <= len('https://[REDACTED]')
            assert 'private' not in actual[key] and '555' not in actual[key] and '1234' not in actual[key]
        elif key != 'file_path':
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


def test_span_contract_types(trace_workspace, call_payload):
    import re
    assert recorder()(call_payload) == (0, '')
    batch = json.loads((trace_workspace / 'traces.jsonl').read_text().splitlines()[0])
    assert isinstance(batch['resourceSpans'], list)
    resource, = batch['resourceSpans']
    attrs = resource['resource']['attributes']
    assert any(a['key'] == 'service.name' and isinstance(a['value']['stringValue'], str) for a in attrs)
    span, = resource['scopeSpans'][0]['spans']
    for key, pattern in [('traceId', r'[0-9a-f]{32}'), ('spanId', r'[0-9a-f]{16}'),
                         ('startTimeUnixNano', r'[0-9]+'), ('endTimeUnixNano', r'[0-9]+')]:
        assert isinstance(span[key], str) and re.fullmatch(pattern, span[key])
    assert span['name'] == call_payload['tool_name']
    attrs = {a['key']: a['value']['stringValue'] for a in span['attributes']}
    assert all(isinstance(attrs[key], str) for key in ('session.id', 'gen_ai.tool.name', 'gen_ai.tool.arguments'))
    assert attrs['gen_ai.tool.name'] == call_payload['tool_name']
    assert json.loads(attrs['gen_ai.tool.arguments']) == call_payload['tool_input']


def test_redacted_sessions_remain_distinct_and_bind_reservations(trace_workspace, call_payload):
    from uuid import uuid4
    from wuwei import workspace
    root = trace_workspace.parents[2]
    identities = ['ghp_' + uuid4().hex, 'ghp_' + uuid4().hex]
    relative = str((trace_workspace / 'briefs/builder.md').relative_to(root))
    state._write_state(lambda data: data.update(items={'work': {}}, seats={'builder': {
        'item': 'work', 'role': 'builder', 'status': 'running', 'brief': relative}}), root, reserved=False)
    transcript = root / 'session.jsonl'
    transcript.write_text(json.dumps({'type': 'user', 'message': {'content': 'WUWEI brief: ' + relative}}) + '\n')
    for identity in [*identities, identities[0]]:
        assert recorder()({**call_payload, 'session_id': identity, 'transcript_path': str(transcript)}) == (0, '')
    spans = read_spans(trace_workspace)
    ids = [span['attrs']['session.id'] for span in spans]
    assert ids[0] != ids[1] and ids[0] == ids[2]
    assert set(state.read_state(root)['seats']['builder']['trace_sessions']) == set(ids)
    assert all(identity not in (trace_workspace / 'traces.jsonl').read_text() for identity in identities)


def test_unmatched_transcript_does_not_infer_item(trace_workspace, call_payload):
    root = trace_workspace.parents[2]
    state._write_state(lambda data: data.update(items={'work': {}}, seats={'builder': {
        'item': 'work', 'role': 'builder', 'status': 'running', 'brief': 'unrelated'}}), root, reserved=False)
    transcript = root / 'session.jsonl'
    transcript.write_text(json.dumps({'type': 'user', 'message': {'content': 'ordinary request'}}) + '\n')
    assert recorder()({**call_payload, 'transcript_path': str(transcript)}) == (0, '')
    assert 'trace_sessions' not in state.read_state(root)['seats']['builder']


@pytest.mark.parametrize('content', ['{"type": "us', '{"type": "user"}',
                                   '{"type": "user", "message": null}', None])
def test_unreadable_transcript_binding_does_not_fail_recorded_span(trace_workspace, call_payload, content, capsys):
    transcript = trace_workspace / 'partial.jsonl'
    transcript.parent.mkdir(parents=True, exist_ok=True)
    if content is None:
        transcript.mkdir()
    else:
        transcript.write_text(content)
    assert recorder()({**call_payload, 'transcript_path': str(transcript)}) == (0, '')
    assert len(read_spans(trace_workspace)) == 1
    assert not (trace_workspace / 'events.jsonl').exists()
    assert not capsys.readouterr().err


@pytest.mark.parametrize('secret_field', [None, 'session_id', 'agent_id'])
def test_subagents_bind_separately_from_shared_planner_session(trace_workspace, call_payload, secret_field):
    from pathlib import Path
    from uuid import uuid4

    root = trace_workspace.parents[2]
    recorded = json.loads((Path(__file__).parent / 'payloads/SubagentStop/example.json').read_text())
    payload = {**call_payload, 'session_id': recorded['session_id']}
    if secret_field == 'session_id':
        payload['session_id'] = 'ghp_' + uuid4().hex
    main = root / 'session.jsonl'
    main.write_text(json.dumps({'type': 'user', 'message': {'content': 'plan my day'}}) + '\n')
    payload['transcript_path'] = str(main)
    assert recorder()(payload) == (0, '')
    seats = {}
    identities = []
    for name in ('builder', 'fixer'):
        agent_id = recorded['agent_id'] + name if secret_field != 'agent_id' else 'ghp_' + uuid4().hex
        identities.append(payload['session_id'] + ':' + agent_id)
        relative = str((trace_workspace / 'briefs' / (name + '.md')).relative_to(root))
        seats[name] = {'item': name, 'role': name, 'status': 'running', 'brief': relative}
        state._write_state(lambda data: data['seats'].update({name: seats[name]}), root, reserved=False)
        transcript = main.parent / payload['session_id'] / 'subagents' / f'agent-{agent_id}.jsonl'
        transcript.parent.mkdir(parents=True, exist_ok=True)
        transcript.write_text(json.dumps({'type': 'user', 'message': {'content': 'WUWEI brief: ' + relative}}) + '\n')
        for tool in ('Read', 'WebFetch'):
            assert recorder()({**payload, 'agent_id': agent_id, 'tool_name': tool}) == (0, '')
    spans = read_spans(trace_workspace)
    ids = [span['attrs']['session.id'] for span in spans]
    assert len(set(ids)) == len({span['traceId'] for span in spans}) == 3
    assert ids[1] == ids[2] and ids[3] == ids[4]
    stored = state.read_state(root)['seats']
    assert stored['builder']['trace_sessions'] == [ids[1]]
    assert stored['fixer']['trace_sessions'] == [ids[3]]
    if secret_field is None:
        assert ids[1::2] == identities
    else:
        assert ids[1::2] == [hashlib.sha256(identity.encode()).hexdigest() for identity in identities]


def test_bind_records_seat_transcript(trace_workspace, call_payload):
    # #473: the seat's own transcript, so a hand-back with no stop can be found.
    root = trace_workspace.parents[2]
    relative = str((trace_workspace / 'briefs/builder.md').relative_to(root))
    state._write_state(lambda data: data['seats'].update({'builder': {
        'item': 'A', 'role': 'builder', 'status': 'running', 'brief': relative}}), root, reserved=False)
    main = root / 'session.jsonl'
    transcript = root / call_payload['session_id'] / 'subagents/agent-seat.jsonl'
    transcript.parent.mkdir(parents=True)
    transcript.write_text(json.dumps({'type': 'user', 'message': {'content': 'WUWEI brief: ' + relative}}) + '\n')
    assert recorder()({**call_payload, 'transcript_path': str(main), 'agent_id': 'seat'}) == (0, '')
    assert state.read_state(root)['seats']['builder']['transcript'] == str(transcript)


ORDINARY = [
    'gh pr view 12 --json state,title,body', 'gh pr list --json number,title --limit 20',
    'gh issue view 473', 'gh api repos/acme/widget/pulls/12/comments', 'gh pr checks 12',
    'gh auth status', 'gh run list --limit 5', 'gh pr merge 12 --squash --auto',
    'gh issue list --json number,title,labels', 'git status --short', 'git log --oneline -5',
    'git diff --stat main...HEAD', 'git push origin 473-handback-traces', 'git branch -d old-branch',
    'git rev-parse HEAD', 'python -m pytest -q tests/test_traces.py',
    'python -m pytest -q -k "text and redact"', 'curl -s https://example.com/api/status',
    'curl -sSf -o out.json https://example.com/releases/latest', 'ls -la .wuwei/days/2026-10-04',
]
SECRETS = [
    'curl -H "Authorization: Bearer abc123secretvalue" https://example.com',
    'export GH_TOKEN=ghp_abcdefghijklmnopqrstuvwxyz0123456789',
    'git clone https://user:pa55word@example.com/repo.git',
    'aws configure set aws_access_key_id AKIAABCDEFGHIJKLMNOP',
    'run --key sk-abcdefghijklmnopqrstuvwxyz012345',
    'curl -X POST https://hooks.slack.com/services/T000/B000/XXXXSECRET',
    'deploy --token s3cr3tvalue123',
    'slack send xoxb-1234567890-abcdefghij',
    'glab auth login glpat-abcdefghijklmnopqrst',
    'call eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0In0.c2lnbmF0dXJlc2VjcmV0',
]
SECRET_TEXT = ['abc123secretvalue', 'ghp_abcdefghijklmnopqrstuvwxyz0123456789', 'pa55word',
               'AKIAABCDEFGHIJKLMNOP', 'sk-abcdefghijklmnopqrstuvwxyz012345', 'XXXXSECRET',
               's3cr3tvalue123', 'xoxb-1234567890-abcdefghij', 'glpat-abcdefghijklmnopqrst',
               'c2lnbmF0dXJlc2VjcmV0']


def test_redaction_corpus():
    # #473: ordinary commands stay readable in the traces; credentials do not.
    from wuwei.redact import redact
    assert len(ORDINARY) == 20 and len(SECRETS) == 10
    assert [redact(command, prefix=True) for command in ORDINARY] == ORDINARY
    for command, secret in zip(SECRETS, SECRET_TEXT):
        assert secret not in redact(command, prefix=True), command
        assert redact(command) == '[REDACTED]'  # outside the traces a credential takes the whole string


def test_prose_names_credentials_without_holding_one():
    # #662: prose that names a credential kind passes; a credential value is still redacted.
    from wuwei.redact import redact
    for text in ('the collector masks the bearer token in its logs', 'use a bearer token, not a password',
                 'Basic authentication is off', 'the token is rotated weekly',
                 'the password field is masked', 'the secret stays in the env file'):
        assert redact(text) == text and redact(text, prefix=True) == text, text
    for text in ('Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abc',
                 'send Bearer abc123XYZ789def456 with the request', 'the header is Basic dXNlcjpwYXNz here',
                 "token = 'abc123XYZ789'", 'set password=hunter2 then restart'):
        assert redact(text) == '[REDACTED]', text


def test_unquoted_curl_body_redacted():
    # #473 review F3: the -d narrowing keeps unquoted key=value bodies redacted for every caller.
    from wuwei.redact import redact
    for command in ('curl -d user=bob&pw=ZZZSECRET https://x', 'curl -d refresh=ZZZSECRET https://x',
                    'curl -d otp=123456 https://x', 'curl -d sig=ZZZSECRET https://x',
                    'curl --json a:ZZZSECRET https://x'):
        assert redact(command) == '[REDACTED]', command
    assert redact('git branch -d old-branch') == 'git branch -d old-branch'
    assert redact('gh pr list --json number,title') == 'gh pr list --json number,title'


def test_body_keeps_command_words():
    from wuwei.redact import redact
    assert redact('gh pr comment 12 --body "looks good"').startswith('gh pr comment 12 --body [BODY ')


def test_trace_gap_on_status_line_and_doctor(trace_workspace, call_payload, monkeypatch, capsys):
    # #473: a span that cannot be written is one traces.gap event, counted on the owner surfaces.
    from wuwei.__main__ import main
    from wuwei.commands import doctor, event, status

    def broken(*args):
        raise OSError('disk full')

    with monkeypatch.context() as patch:
        patch.setattr(state, 'append_jsonl', broken)
        code, _ = run_hook(call_payload, monkeypatch, capsys)
    assert code == 0
    assert [row['kind'] for row in error_events(trace_workspace)] == ['traces.gap']
    state._write_state(lambda data: None, trace_workspace.parents[2], reserved=False)
    assert 'traces: 1 gaps' in status.full(status.snapshot(trace_workspace))
    probes = {'state': {'result': 'ok', 'value': 'ok'}, 'planner': {'result': 'ok', 'value': 'ok'},
              'seats': {'result': 'ok', 'value': 'none stuck'}}
    config = workspace.load_config(trace_workspace.parents[2])
    found, = [row for row in doctor._day(trace_workspace.parents[2], config, probes) if row['name'] == 'traces']
    assert (found['status'], found['value']) == ('warn', '1 gaps today')
    assert 'traces.gap' in event.EVENT_PRODUCERS
    assert main(['event', 'traces.gap', '{}']) == 1


def test_subagent_transcript_and_seat_of(tmp_path):
    """#647: one derivation of a subagent's transcript, shared by traces and the scratch guard."""
    from wuwei import brief
    base = {'session_id': 's1', 'transcript_path': str(tmp_path / 'main.jsonl')}
    assert brief.subagent_transcript(base) is None
    assert brief.subagent_transcript({**base, 'agent_id': 'a', 'transcript_path': ''}) is None
    with pytest.raises(ValueError, match='invalid agent_id'):
        brief.subagent_transcript({**base, 'agent_id': ''})
    path = tmp_path / 's1/subagents/agent-a.jsonl'
    assert brief.subagent_transcript({**base, 'agent_id': 'a'}) == path
    reference = '.wuwei/days/2026-09-28/briefs/b-a.md'
    data = {'seats': {'b-a': {'role': 'builder', 'item': 'A', 'status': 'running', 'brief': reference},
                      'b-b': {'role': 'builder', 'item': 'B', 'status': 'running', 'brief': 'other.md'}}}
    assert brief.seat_of({**base, 'agent_id': 'a'}, data) is None
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'type': 'user', 'message': {'content': f'WUWEI brief: {reference}\nRead.'}}) + '\n')
    assert brief.seat_of({**base, 'agent_id': 'a'}, data) is data['seats']['b-a']


@pytest.mark.parametrize('case', ['match', 'no-seat', 'no-day'])
def test_untyped_subagent_binds_to_its_adhoc_seat(trace_workspace, call_payload, case):
    # #676: an untyped subagent's calls bind to its adhoc seat by its launch prompt.
    from wuwei import brief
    root = trace_workspace.parents[2]
    prompt = 'Review PR 16\nRead only.'
    if case != 'no-day':
        seat = {'id': 'adhoc-1', 'role': 'adhoc', 'item': 'adhoc-1', 'type': 'general-purpose',
                'status': 'running', 'prompt_sha256': brief.prompt_digest(
                    prompt if case == 'match' else 'another prompt')}
        state._write_state(lambda data: data['seats'].update({'adhoc-1': seat}), root, reserved=False)
    before = {name: (trace_workspace / name).read_text()
              for name in ('state.json', 'events.jsonl') if (trace_workspace / name).exists()}
    main = root / 'session.jsonl'
    transcript = root / call_payload['session_id'] / 'subagents/agent-a1.jsonl'
    transcript.parent.mkdir(parents=True)
    transcript.write_text(json.dumps({'type': 'user', 'message': {'content': prompt}}) + '\n')
    payload = {**call_payload, 'transcript_path': str(main), 'agent_id': 'a1',
               'agent_type': 'general-purpose'}
    assert recorder()(payload) == (0, '')
    assert len(read_spans(trace_workspace)) == 1
    if case == 'match':
        stored = state.read_state(root)['seats']['adhoc-1']
        assert stored['trace_sessions'] == [call_payload['session_id'] + ':a1']
        assert stored['transcript'] == str(transcript)
    else:
        assert before == {name: (trace_workspace / name).read_text()
                          for name in ('state.json', 'events.jsonl') if (trace_workspace / name).exists()}
