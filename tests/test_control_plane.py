"""Control-plane interface: content policy, reply parser, escalate, notify and replies."""

import json

import pytest

from wuwei.registry import Result


VALID = '''Question: Which fix?
Context: tests/test_example.py records the failure.
Options:
| Option | Description |
| --- | --- |
| A | Implement fix |
| B | Defer until tomorrow |
Musts:
| Criterion | A | B |
| --- | --- | --- |
| Safe | pass | pass |
Wants:
| Criterion | Weight | A | B |
| --- | --- | --- | --- |
| Correctness | 10 | 8 | 2 |
| Speed | 2 | 3 | 5 |
Recommendation: A
Confidence: high
Reversibility: one-way
Blast radius: own branch
Pre-mortem: Regression returns.
Revisit: Regression returns.
Decided-by: owner
Outcome: pending
'''


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T12:00:00+00:00')
    root = tmp_path / 'workspace'
    (root / '.wuwei').mkdir(parents=True)
    (root / '.wuwei/config.toml').write_text('')
    monkeypatch.chdir(root)
    return root


def config(root, text):
    (root / '.wuwei/config.toml').write_text(text)


def routed(root, name='D-3'):
    from wuwei.__main__ import main
    from wuwei.workspace import day_dir
    path = day_dir(root) / 'decisions' / f'{name}.md'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(VALID)
    assert main(['decision', 'route', name]) == 0
    return path


def events(root):
    from wuwei.workspace import day_dir
    path = day_dir(root) / 'events.jsonl'
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


class Fake:
    def __init__(self, replies=(), exit=0, reason='', dm_exit=0, data=None):
        self.sent, self.exit, self.reason, self.dm_exit = [], exit, reason, dm_exit
        self.data = [{'id': str(n), 'text': t} for n, t in enumerate(replies)] if data is None else data

    def dm(self, text, *, root=None):
        self.sent.append(text)
        return Result(self.dm_exit, {}, 'dm failed' if self.dm_exit else '')

    def poll(self, since, *, root=None):
        return Result(self.exit, self.data, self.reason)


def test_config_content_policy(ws):
    from wuwei import workspace
    assert workspace.load_config(ws)['control_plane']['content'] == 'summary'
    config(ws, '[control_plane]\ncontent = "none"\n')
    assert workspace.load_config(ws)['control_plane']['content'] == 'none'
    config(ws, '[control_plane]\ncontent = "all"\n')
    with pytest.raises(workspace.ConfigError, match='control_plane.content'):
        workspace.load_config(ws)


@pytest.mark.parametrize('text,expected', [
    ('option B on D-3', ('D-3', 'B')),
    ('  Option b   on d-3.', ('D-3', 'B')),
    ('approve D-3!', ('D-3', 'A')),
    ('approve D-3', ('D-3', 'A')),
    ('drop it', ('D-3', 'B')),
    ('Drop it.', ('D-3', 'B')),
    ('approve something', None),
    ('approve D-9', None),
    ('option Z on D-3', None),
    ('approve D-3 please', None),
    ('approve D-3..', None),
    ('', None),
])
def test_parse_replies(text, expected):
    from wuwei import control_plane, decision
    fields, _ = decision.evaluate(VALID)
    assert control_plane.parse(text, {'D-3': fields}) == expected


def test_parse_drop_it_needs_one_pending():
    from wuwei import control_plane, decision
    fields, _ = decision.evaluate(VALID)
    assert control_plane.parse('drop it', {'D-3': fields, 'D-4': fields}) is None
    assert control_plane.parse('drop it', {}) is None


def test_pending_lists_unanswered_owner_routes(ws):
    from wuwei import control_plane, state
    assert control_plane.pending(ws) == {}
    routed(ws)
    assert list(control_plane.pending(ws)) == ['D-3']
    assert control_plane.pending(ws)['D-3']['Question'] == 'Which fix?'
    state._write_state(lambda data: data.setdefault('decision_outcomes', {}).update(
        {'D-3': {'option': 'A', 'decided_by': 'owner'}}), ws, reserved=False)
    assert control_plane.pending(ws) == {}


def test_escalate_sends_summary(ws):
    from wuwei import control_plane
    routed(ws)
    fake = Fake()
    assert control_plane.escalate('D-3', root=ws, transport=fake).exit == 0
    [text] = fake.sent
    for phrase in ('D-3: Which fix?', 'A: Implement fix', 'B: Defer until tomorrow', control_plane.HELP):
        assert phrase in text, phrase
    for phrase in ('Context', 'tests/test_example.py', 'Pre-mortem'):
        assert phrase not in text, phrase


def test_escalate_content_none_sends_ids_only(ws):
    from wuwei import control_plane
    routed(ws)
    config(ws, '[control_plane]\ncontent = "none"\n')
    fake = Fake()
    assert control_plane.escalate('D-3', root=ws, transport=fake).exit == 0
    assert fake.sent == ['D-3 options: A, B\n' + control_plane.HELP]


def test_escalate_default_returns_widget_text_that_passes_the_question_guard(ws):
    from wuwei import control_plane
    from wuwei.guards.decision import check_question
    routed(ws)
    result = control_plane.escalate('D-3', root=ws)
    assert result.exit == 0 and result.data.startswith('D-3: Which fix?')
    payload = {'cwd': str(ws), 'tool_name': 'AskUserQuestion',
               'tool_input': {'questions': [{'question': result.data}]}}
    assert check_question(payload) == (0, '')


def test_escalate_refuses_what_is_not_pending(ws):
    from wuwei import control_plane, state
    routed(ws)
    fake = Fake()
    assert control_plane.escalate('D-9', root=ws, transport=fake).exit == 1
    state._write_state(lambda data: data.setdefault('decision_outcomes', {}).update(
        {'D-3': {'option': 'A', 'decided_by': 'owner'}}), ws, reserved=False)
    assert control_plane.escalate('D-3', root=ws, transport=fake).exit == 1
    assert fake.sent == []


def test_escalate_invalid_record_cannot_run(ws):
    from wuwei import control_plane
    routed(ws).write_text('bad')
    fake = Fake()
    result = control_plane.escalate('D-3', root=ws, transport=fake)
    assert result.exit == 2 and 'missing fields' in result.reason
    assert fake.sent == []


def test_reply_records_a_parsed_answer_without_an_owner_outcome(ws):
    from wuwei import control_plane, state
    from wuwei.workspace import day_dir
    routed(ws)
    fake = Fake(['option B on D-3'])
    result = control_plane.poll_replies(None, root=ws, transport=fake)
    assert (result.exit, result.data) == (0, [{'id': 'D-3', 'option': 'B'}])
    last = events(ws)[-1]
    assert last['kind'] == 'decision.replied' and last['payload'] == {'id': 'D-3', 'option': 'B'}
    assert fake.sent == []
    assert 'D-3' not in state.read_state(ws).get('decision_outcomes', {})
    assert 'option B on D-3' not in (day_dir(ws) / 'events.jsonl').read_text()


def test_reply_unparseable_echoes_options_and_records_nothing(ws):
    from wuwei import control_plane
    routed(ws)
    fake = Fake(['approve something'])
    result = control_plane.poll_replies(None, root=ws, transport=fake)
    assert (result.exit, result.data) == (1, [])
    assert not any(event['kind'] == 'decision.replied' for event in events(ws))
    [echo] = fake.sent
    for phrase in (control_plane.HELP, 'D-3', 'A: Implement fix', 'B: Defer until tomorrow'):
        assert phrase in echo, phrase


def test_reply_echo_respects_content_none_and_empty_pending(ws):
    from wuwei import control_plane
    fake = Fake(['hello'])
    assert control_plane.poll_replies(None, root=ws, transport=fake).exit == 1
    assert fake.sent == [control_plane.HELP + '\nNo pending decisions.']
    routed(ws)
    config(ws, '[control_plane]\ncontent = "none"\n')
    fake = Fake(['hello'])
    assert control_plane.poll_replies(None, root=ws, transport=fake).exit == 1
    assert fake.sent == [control_plane.HELP + '\nD-3 options: A, B']


@pytest.mark.parametrize('fake', [
    Fake(['option B on D-3'], exit=2, reason='poll: unreachable'),
    Fake(data={'text': 'option B on D-3'}),
    Fake(data=[{'id': '1', 'text': 'option B on D-3'}, {'id': '2'}]),
    Fake(data=[{'id': '1', 'text': 'option B on D-3'}, 'bad']),
])
def test_reply_bad_poll_cannot_run_and_records_nothing(ws, fake):
    from wuwei import control_plane
    routed(ws)
    assert control_plane.poll_replies(None, root=ws, transport=fake).exit == 2
    assert not any(event['kind'] == 'decision.replied' for event in events(ws))
    assert fake.sent == []


def test_reply_echo_send_failure_cannot_run(ws):
    from wuwei import control_plane
    routed(ws)
    assert control_plane.poll_replies(None, root=ws, transport=Fake(['huh'], dm_exit=2)).exit == 2


def test_reply_default_has_nothing_to_poll(ws):
    from wuwei import control_plane
    result = control_plane.poll_replies(None, root=ws)
    assert (result.exit, result.data) == (0, [])


def test_replied_event_is_silent():
    from wuwei import signal
    assert signal.classify({'kind': 'decision.replied', 'payload': {'id': 'D-3', 'option': 'B'}}, {})[0] == 'silent'


def test_notify_sends_by_content_policy(ws):
    from wuwei import control_plane
    fake = Fake(dm_exit=2)
    assert control_plane.notify('PR 12 merged.', root=ws, transport=fake).exit == 2
    assert fake.sent == ['PR 12 merged.']
    config(ws, '[control_plane]\ncontent = "none"\n')
    fake = Fake()
    assert control_plane.notify('PR 12 merged.', root=ws, transport=fake).exit == 0
    assert fake.sent == ['An update is waiting in the workspace.']


def test_notify_default_sends_nothing(ws):
    from wuwei import control_plane
    result = control_plane.notify('PR 12 merged.', root=ws)
    assert (result.exit, result.data) == (0, 'PR 12 merged.')


def test_escalate_follows_the_dm_verbosity(ws):
    from wuwei import control_plane, decision
    routed(ws)
    fields, _ = decision.evaluate(VALID)
    fake = Fake()
    assert control_plane.escalate('D-3', root=ws, transport=fake).exit == 0
    assert fake.sent == [decision.present('D-3', fields, 'brief')
                         + '\nReply more D-3 for the full record.\n' + control_plane.HELP]
    assert 'score 86' in fake.sent[0]
    assert control_plane.escalate('D-3', root=ws).data == decision.present('D-3', fields, 'brief')
    config(ws, '[owner.verbosity]\ndm = "full"\n')
    fake = Fake(['hello'])
    assert control_plane.escalate('D-3', root=ws, transport=fake).exit == 0
    assert fake.sent == [VALID.rstrip() + '\n' + control_plane.HELP]
    assert control_plane.poll_replies(None, root=ws, transport=fake).exit == 1
    assert fake.sent[-1] == control_plane.HELP + '\n' + VALID.rstrip()
