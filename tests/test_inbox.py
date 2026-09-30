"""Inbound text is redacted by the redactor port before the inbox stores it."""

import pytest

from adapters.redactor import builtin


@pytest.mark.parametrize('text,expected,kinds', [
    ('call me on +44 20 7946 0958 today', 'call me on [REDACTED] today', ['phone']),
    ('ring 07700900123', 'ring [REDACTED]', ['phone']),
    ('mail a.b@example.com', 'mail [REDACTED]', ['email']),
    ('token: xoxb-123-abc rest', '[REDACTED] rest', ['secret']),
    ('password=hunter2 ok', '[REDACTED] ok', ['secret']),
    ('approve D-3', 'approve D-3', []),
    ('PR 1234 at 10:30', 'PR 1234 at 10:30', []),
    ('ring 07700900123 or 07700900456', 'ring [REDACTED] or [REDACTED]', ['phone', 'phone']),
    ('tok xoxb-1234567890-1234567890123-AbCdEfGhIjKlMnOpQrStUvWx end', 'tok [REDACTED] end',
     ['secret']),
    ('xoxp-123456789-abc', '[REDACTED]', ['secret']),
    ('mail a.123456789@example.com', 'mail [REDACTED]', ['email']),
])
def test_builtin_redactor(text, expected, kinds):
    result = builtin.redact(text)
    assert (result.exit, result.data['text'], [f['kind'] for f in result.data['findings']]) == (
        1 if kinds else 0, expected, kinds)


def test_builtin_redactor_rejects_non_string():
    result = builtin.redact(None)
    assert (result.exit, result.data) == (2, None)
    assert result.reason


@pytest.fixture
def root(tmp_path, monkeypatch):
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', '2026-09-30T12:00:00Z')
    return tmp_path


def event(**changes):
    return {'id': 'm1', 'source': 'slack', 'channel': 'D1', 'thread': '', 'sender': 'U1',
            'text': 'hello', 'ts': '1727697600.000100', **changes}


def stored(root):
    import json
    path = root / '.wuwei/inbox/inbox.jsonl'
    return [json.loads(line) for line in path.read_text().splitlines()]


def redacted_events(root):
    import json
    path = root / '.wuwei/days/2026-09-30/events.jsonl'
    lines = path.read_text().splitlines() if path.exists() else []
    return [line for line in map(json.loads, lines) if line['kind'] == 'inbox.redacted']


def store(root, events):
    from wuwei import inbox
    from wuwei.workspace import load_config
    return inbox.store(root, load_config(root), events)


def test_store_redacts_before_writing(root):
    result = store(root, [event(text='call me on 07700900123 please')])
    assert result.exit == 1
    assert stored(root) == [event(text='call me on [REDACTED] please')]
    [record] = redacted_events(root)
    assert record['payload'] == {'id': 'm1', 'source': 'slack', 'findings': ['phone']}
    for path in (root / '.wuwei').rglob('*.jsonl'):
        assert '07700900123' not in path.read_text()


def test_store_drops_loaded_credential_values(root, monkeypatch):
    from wuwei import redact
    monkeypatch.setattr(redact, 'VALUES', {'Zq9opaqueSecretValue'})
    store(root, [event(text='here Zq9opaqueSecretValue there')])
    assert stored(root)[0]['text'] == 'here [REDACTED] there'
    for path in (root / '.wuwei').rglob('*.jsonl'):
        assert 'Zq9opaqueSecretValue' not in path.read_text()


def test_store_clean_text(root):
    result = store(root, [event()])
    assert result.exit == 0
    assert stored(root) == [event()]
    assert redacted_events(root) == []


@pytest.mark.parametrize('events', [
    event(), [{k: v for k, v in event().items() if k != 'thread'}], [event(extra='x')],
    [event(text=None)], [event(id='')], [event(), 'text'],
])
def test_store_rejects_malformed(root, events):
    result = store(root, events)
    assert (result.exit, result.data) == (2, None)
    assert result.reason
    assert not (root / '.wuwei/inbox/inbox.jsonl').exists()


@pytest.mark.parametrize('answer,reason', [
    ((2, None, 'down'), 'down'),
    ((0, {'text': 'hello'}, ''), 'malformed'),
    ((1, {'text': 'x', 'findings': [{}]}, ''), 'malformed'),
])
def test_store_fails_closed_on_redactor(root, monkeypatch, answer, reason):
    from types import SimpleNamespace
    from wuwei import registry
    fake = SimpleNamespace(redact=lambda text, root=None: registry.Result(*answer))
    monkeypatch.setattr(registry, 'load', lambda kind, config: fake)
    result = store(root, [event()])
    assert (result.exit, result.data) == (2, None)
    assert reason in result.reason
    assert not (root / '.wuwei/inbox/inbox.jsonl').exists()


def test_inbox_is_protected(root, monkeypatch):
    from fakes.integrity import seed
    from wuwei.guards.protect_state import check_bash, check_file
    monkeypatch.delenv('WUWEI_WORKSPACE')
    seed(root)

    def payload(tool, **tool_input):
        return {'hook_event_name': 'PreToolUse', 'session_id': 'fixture',
                'transcript_path': str(root / 'transcript.jsonl'), 'cwd': str(root),
                'tool_name': tool, 'tool_input': tool_input}

    assert check_file(payload('Write', file_path='.wuwei/inbox/inbox.jsonl'))[0] == 1
    assert check_bash(payload('Bash', command='echo x >> .wuwei/inbox/inbox.jsonl'))[0] == 1
