"""Commands from the owner DM: vocabulary, the read-only gate, and one session per thread."""

import json

import pytest

from wuwei import state, workspace
from wuwei.registry import Result


OWNER = '[owner]\nname = "Robin Example"\n'


class Transport:
    def __init__(self):
        self.sent = []

    def dm(self, text, *, root=None):
        from wuwei import outward
        code, reason = outward.lint(text, 'D1', workspace.load_config(root))
        if code:
            return Result(code, None, reason)
        self.sent.append(text)
        return Result(0, {})


class Runtime:
    def __init__(self, *results, effect=None):
        self.results, self.effect, self.calls = list(results), effect, []

    def headless(self, prompt, session, tools, *, root=None):
        self.calls.append((prompt, session, tools))
        if self.effect:
            self.effect(root)
        return self.results.pop(0)


@pytest.fixture
def bare(tmp_path, monkeypatch):
    (tmp_path / '.wuwei/memory/notes').mkdir(parents=True)
    (tmp_path / '.wuwei/memory/spine.md').write_text('Memory spine\n')
    (tmp_path / '.wuwei/memory/index.md').write_text('Index\n')
    (tmp_path / '.wuwei/config.toml').write_text(OWNER)
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', '2026-09-30T12:00:00+00:00')
    monkeypatch.setenv('SLACK_OWNER_DM_CHANNEL', 'D1')
    return tmp_path


@pytest.fixture
def ws(bare):
    state._write_state(lambda data: None, bare, reserved=False)
    return bare


def event(ident, text, channel='D1'):
    return {'id': ident, 'source': 'slack', 'channel': channel, 'thread': '', 'sender': 'U1',
            'text': text, 'ts': ident.rsplit('/', 1)[-1]}


def events(root, prefix=''):
    path = workspace.day_dir(root) / 'events.jsonl'
    return [row for row in map(json.loads, path.read_text().splitlines())
            if row['kind'].startswith(prefix)]


def payloads(root, prefix):
    """Event payloads without the state writer's own prs_seen flag."""
    return [{key: value for key, value in row['payload'].items() if key != 'prs_seen'}
            for row in events(root, prefix)]


def remote():
    from wuwei import remote
    return remote


@pytest.mark.parametrize('text, parsed', [
    ('plan', ('plan', '')), ('Plan today.', ('plan', '')), ('status', ('status', '')),
    ('REPORT!', ('report', '')), ('stop all', ('stop', 'all')),
    ('stop 1a2b3c4d', ('stop', '1a2b3c4d')), ('run daily-brief', ('run', 'daily-brief')),
    ('ask What  changed Today?', ('ask', 'What changed Today?')),
    ('cloud repo fix it', ('cloud', '')),
    ('run rm -rf', None), ('planet', None), ('plan: x', None), ('ask', None),
    ('stop 1a2b', None), ('status please', None), ('rm -rf /', None), ('approve D-1', None),
])
def test_parse_vocabulary(text, parsed):
    assert remote().parse(text) == parsed


def test_fixed_lines_pass_the_outward_lint(ws):
    from wuwei import outward
    module, config = remote(), workspace.load_config(ws)
    for text in (module.VOCABULARY, module.UNAVAILABLE, module.GUARDED, module.FAILED):
        assert outward.lint(text, 'D1', config) == (0, ''), text


@pytest.fixture
def chat(ws, monkeypatch):
    from types import SimpleNamespace
    from wuwei import registry
    calls = []

    def dm(text, *, root=None):
        raise AssertionError('the drafting wrapper must not run')

    def send(text, *, root=None):
        calls.append(text)
        return Result(0, {'ts': '1'})
    dm.__wrapped__ = send
    real = registry.load
    monkeypatch.setattr(registry, 'load', lambda kind, config: SimpleNamespace(dm=dm)
                        if kind == 'chat' else real(kind, config))
    return calls


def test_dm_sends_through_the_undecorated_chat_operation(ws, chat):
    assert remote().dm('Report ready.', root=ws) == Result(0, {'ts': '1'})
    assert chat == ['Report ready.']
    assert 'drafts' not in state.read_state(ws)


def test_dm_lint_finding_sends_nothing(ws, chat):
    assert remote().dm('Robin should look.', root=ws).exit == 1
    assert chat == []


def test_dm_security_finding_sends_nothing(ws, chat, monkeypatch):
    from wuwei import security
    monkeypatch.setattr(security, 'outbound', lambda value, root=None: (1, 'outward: security.canary'))
    assert remote().dm('Report ready.', root=ws).exit == 1
    assert chat == []


def test_the_listeners_own_send_read_back_is_not_a_command(ws, monkeypatch):
    # A reply posted with SLACK_USER_TOKEN comes back from the poll as an owner message.
    from types import SimpleNamespace
    from wuwei import registry
    sent = []

    def send(text, *, root=None):
        sent.append(text)
        return Result(0, {'channel': 'D1', 'ts': '2.000001'})
    real = registry.load
    monkeypatch.setattr(registry, 'load', lambda kind, config: SimpleNamespace(dm=send)
                        if kind == 'chat' else real(kind, config))
    assert remote().handle(ws, event('D1/1.000001', 'hi')) == 1
    assert remote().handle(ws, event('D1/2.000001', sent[0])) == 0
    assert sent == [remote().VOCABULARY]


def test_dm_without_a_chat_adapter_is_unrun(ws):
    assert remote().dm('Report ready.', root=ws).exit == 2


def handled(root, text, *, channel='D1', runtime=None, ident='D1/1.000001'):
    transport = Transport()
    code = remote().handle(root, event(ident, text, channel), transport=transport, runtime=runtime)
    return code, transport.sent


def test_issue_acceptance_run_rm_rf_returns_the_vocabulary(ws):
    before = (workspace.day_dir(ws) / 'state.json').read_text()
    runtime = Runtime()
    assert handled(ws, 'run rm -rf', runtime=runtime) == (1, [remote().VOCABULARY])
    assert runtime.calls == [] and events(ws, 'remote.') == []
    assert (workspace.day_dir(ws) / 'state.json').read_text() == before


def test_anything_else_returns_the_vocabulary(ws):
    assert handled(ws, 'hello there') == (1, [remote().VOCABULARY])


@pytest.mark.parametrize('text', ['run daily-brief', 'cloud repo fix it'])
def test_routines_and_cloud_are_unavailable(ws, text):
    runtime = Runtime()
    assert handled(ws, text, runtime=runtime) == (1, [remote().UNAVAILABLE])
    assert runtime.calls == []


def test_other_channels_are_not_commands(ws):
    assert handled(ws, 'status', channel='C9') == (0, [])


def test_unexpected_error_is_unrun(ws, monkeypatch, capsys):
    from wuwei import control_plane

    def broken(root):
        raise ValueError('invalid decision ledger')
    monkeypatch.setattr(control_plane, 'pending', broken)
    assert handled(ws, 'approve D-1') == (2, [remote().FAILED])
    assert 'listen remote unmeasured' in capsys.readouterr().out


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
Recommendation: A
Confidence: high
Reversibility: one-way
Blast radius: own branch
Pre-mortem: Regression returns.
Revisit: Regression returns.
Decided-by: owner
Outcome: pending
'''


def routed(root, text=VALID):
    from wuwei import decision
    path = decision.write(text, root)
    decision.route_owner(path.stem, decision.evaluate(text)[0], root)
    return path.stem


def remote_row(root, session, decisions, **extra):
    def update(data):
        data.setdefault('sessions', {})[session] = {
            'role': 'remote', 'started': '2026-09-30T12:00:00+00:00',
            'last_seen': '2026-09-30T12:00:00+00:00', 'cwd': str(root), 'thread': 'D1/0.1',
            'command': 'plan', 'decisions': decisions, **extra}
    state._write_state(update, root, reserved=False)


def test_status_sends_the_status_line_without_the_prefix(ws, monkeypatch):
    from wuwei.commands import status
    expected = status.line(status.snapshot(workspace.day_dir(ws))).removeprefix('WUWEI ')
    assert 'WUWEI' not in expected
    assert handled(ws, 'status') == (0, [expected])
    (ws / '.wuwei/config.toml').write_text(OWNER + '[control_plane]\ncontent = "none"\n')
    assert handled(ws, 'Status.') == (0, ['An update is waiting in the workspace.'])


def test_report_writes_the_report_and_sends_counts(ws):
    assert handled(ws, 'report') == (
        0, ['Report 2026-09-30: merged 0, open 0, parked 0, decisions answered 0.'])
    assert (workspace.day_dir(ws) / 'report.md').is_file()


def test_report_counts_merged_items(bare):
    (bare / '.wuwei/config.toml').write_text(OWNER + '[adapters]\ncode_host = "none"\n')
    state._write_state(lambda data: data.update(items={
        'fix': {**state.ITEM_DEFAULTS, 'phase': 'merged', 'pr': 'org/repo#1'}}), bare, reserved=False)
    assert handled(bare, 'report')[1] == [
        'Report 2026-09-30: merged 1, open 0, parked 0, decisions answered 0.']


@pytest.mark.parametrize('text, verb', [
    ('plan today', 'plan'), ('ask what changed', 'ask'), ('stop all', 'stop'),
    ('stop 1a2b3c4d', 'stop')])
def test_gate_records_guarded_commands_as_pending(ws, text, verb):
    runtime = Runtime()
    assert handled(ws, text, runtime=runtime) == (1, [remote().GUARDED])
    assert runtime.calls == []
    assert [row['payload'] for row in events(ws, 'remote.')] == [{'id': 'D1/1.000001', 'command': verb}]
    assert 'changed' not in (workspace.day_dir(ws) / 'events.jsonl').read_text()


def test_reply_without_a_remote_session_is_recorded_evidence(ws):
    identifier = routed(ws)
    assert handled(ws, 'option B on D-1') == (0, ['Recorded D-1 option B. Confirm it on the host.'])
    assert identifier == 'D-1'
    assert [row['payload'] for row in events(ws, 'decision.replied')] == [{'id': 'D-1', 'option': 'B'}]
    assert state.read_state(ws).get('decision_outcomes', {}) == {}


def test_gate_records_a_reply_that_would_resume_a_session(ws):
    routed(ws)
    remote_row(ws, 'S1', ['D-1'])
    runtime = Runtime()
    assert handled(ws, 'option B on D-1', runtime=runtime) == (1, [remote().GUARDED])
    assert runtime.calls == []
    assert [row['payload'] for row in events(ws, 'decision.replied')] == [{'id': 'D-1', 'option': 'B'}]
    assert [row['payload'] for row in events(ws, 'remote.')] == [{'id': 'D1/1.000001', 'command': 'reply'}]


S = '0f8fad5b-d9cb-469f-a165-70867728950e'
T = '7c9e6679-7425-40de-944b-e07fc1f90ae7'


def ran(session=S, denials=(), result='Turn done.', exit=0):
    return Result(exit, {'session_id': session, 'result': result, 'denials': list(denials)})


def planner_tools():
    from wuwei import registry
    path = registry.ADAPTERS.parent / 'agents/allowlist.json'
    return [*json.loads(path.read_text())['planner'], 'Skill']


def escalation(root, identifier):
    from wuwei import control_plane
    fields = control_plane.pending(root)[identifier]
    return control_plane.render(identifier, fields, 'summary') + '\n' + control_plane.HELP


@pytest.fixture
def open_gate(monkeypatch):
    module = remote()
    monkeypatch.setattr(module, 'EXECUTABLE', module.EXECUTABLE | {'plan', 'reply', 'ask'})
    return module


def test_denial_template_is_a_valid_owner_decision(ws):
    from wuwei import control_plane, decision
    text = remote().DENIAL.format(session='1a2b3c4d', tool='Bash')
    fields, _ = decision.evaluate(text)
    assert fields['Recommendation'] == 'A' and decision.route(fields) == 'owner'
    assert any(row[1].startswith('Do nothing') for row in control_plane.options(fields))


@pytest.mark.parametrize('tool, named', [('Bash', 'Bash'), ('Bash\nQuestion: x', 'a tool'),
                                         ('a|b', 'a tool')])
def test_deny_writes_and_routes_the_next_decision(ws, tool, named):
    routed(ws)
    remote().deny(ws, S, tool)
    from wuwei import control_plane
    fields = control_plane.pending(ws)['D-2']
    assert fields['Question'] == f'Session {S[:8]} was refused {named}. How should it continue?'
    assert 'D-2' in state.read_state(ws)['decision_routes']


def test_issue_acceptance_plan_starts_a_session_and_a_reply_resumes_it(ws, open_gate):
    runtime = Runtime(ran(), ran(), effect=lambda root: routed(root) if not runtime.calls[1:] else None)
    code, sent = handled(ws, 'plan today', runtime=runtime)
    assert code == 0
    assert runtime.calls == [(open_gate.PLAN_PROMPT, None, planner_tools())]
    row = state.read_state(ws)['sessions'][S]
    assert (row['role'], row['thread'], row['command'], row['decisions']) == (
        'remote', 'D1/1.000001', 'plan', ['D-1'])
    assert payloads(ws, 'remote.') == [{'session': S, 'command': 'plan'}]
    assert sent == [escalation(ws, 'D-1'), f'Session {S[:8]}: turn ended, 1 decisions waiting.']
    code, sent = handled(ws, 'option B on D-1', runtime=runtime, ident='D1/2.000001')
    assert code == 0
    assert runtime.calls[1] == ('Decision D-1: option B.', S, planner_tools())
    assert [row['payload'] for row in events(ws, 'decision.replied')] == [{'id': 'D-1', 'option': 'B'}]
    assert payloads(ws, 'remote.')[-1] == {'session': S}
    assert events(ws, 'remote.')[-1]['kind'] == 'remote.resumed'
    row = state.read_state(ws)['sessions'][S]
    assert (row['thread'], row['decisions']) == ('D1/1.000001', ['D-1'])
    assert sent == [f'Session {S[:8]}: turn ended, 0 decisions waiting.']


def test_a_decision_the_lint_refuses_is_announced_by_id_only(ws):
    runtime = Runtime(ran(), effect=lambda root: routed(root, VALID.replace('Which fix?', 'Which fix does Robin want?')))
    assert remote().start(ws, 'plan', 'D1/1.000001', 'p', transport=(t := Transport()), runtime=runtime) == 0
    assert t.sent == ['D-1 is waiting in the workspace.', f'Session {S[:8]}: turn ended, 1 decisions waiting.']


def test_issue_acceptance_a_refused_tool_surfaces_as_a_decision(ws, open_gate):
    runtime = Runtime(ran(denials=['Bash']), ran())
    code, sent = handled(ws, 'plan today', runtime=runtime)
    assert code == 0
    from wuwei import control_plane
    assert 'Bash' in control_plane.pending(ws)['D-1']['Question']
    assert state.read_state(ws)['sessions'][S]['decisions'] == ['D-1']
    assert sent[0] == escalation(ws, 'D-1')
    handled(ws, 'option A on D-1', runtime=runtime, ident='D1/2.000001')
    assert runtime.calls[1] == ('Decision D-1: option A.', S, planner_tools())


def test_a_turn_that_cannot_run_registers_nothing(ws, capsys):
    t = Transport()
    assert remote().start(ws, 'plan', 'D1/1.000001', 'p', transport=t,
                          runtime=Runtime(Result(2, None, 'claude missing'))) == 2
    assert 'sessions' not in state.read_state(ws) or state.read_state(ws)['sessions'] == {}
    assert events(ws, 'remote.') == [] and t.sent == [remote().FAILED]
    assert 'claude missing' in capsys.readouterr().out


def test_an_error_turn_is_still_registered(ws):
    assert remote().start(ws, 'plan', 'D1/1.000001', 'p', transport=Transport(),
                          runtime=Runtime(ran(exit=1))) == 1
    assert S in state.read_state(ws)['sessions']


def test_ask_sends_the_answer_or_holds_it(ws, open_gate):
    runtime = Runtime(ran(result='Two PRs merged.'), ran(session=T, result='Robin merged two.'))
    assert handled(ws, 'ask what changed', runtime=runtime) == (
        0, ['Two PRs merged.', f'Session {S[:8]}: turn ended, 0 decisions waiting.'])
    assert runtime.calls[0] == (open_gate.ASK_PROMPT + 'what changed', None, ['Read', 'Glob', 'Grep'])
    code, sent = handled(ws, 'ask what changed', runtime=runtime, ident='D1/2.000001')
    assert sent == [f'The answer is held in session {T[:8]}; open it on the host.',
                    f'Session {T[:8]}: turn ended, 0 decisions waiting.']
    assert state.read_state(ws)['sessions'][T]['command'] == 'ask'


def test_stop_marks_remote_sessions_and_blocks_resumes(ws, open_gate):
    routed(ws)
    remote_row(ws, S, ['D-1'])
    remote_row(ws, T, [])
    state._write_state(lambda data: data['sessions'].update(A={**data['sessions'][T], 'role': 'adhoc'}),
                       ws, reserved=False)
    t = Transport()
    assert remote().stop(ws, S[:8], transport=t) == 0
    assert 'stopped' in state.read_state(ws)['sessions'][S]
    assert payloads(ws, 'remote.stopped') == [{'sessions': [S]}]
    for prefix in ('0f8fad5', 'ffffffff'):
        assert remote().stop(ws, prefix, transport=t) == 1
    assert len(events(ws, 'remote.stopped')) == 1
    assert remote().stop(ws, 'all', transport=t) == 0
    sessions = state.read_state(ws)['sessions']
    assert 'stopped' in sessions[T] and 'stopped' not in sessions['A']
    assert t.sent == ['Stopped 1 sessions.', 'No single session matches 0f8fad5.',
                      'No single session matches ffffffff.', 'Stopped 1 sessions.']
    runtime = Runtime()
    assert handled(ws, 'option B on D-1', runtime=runtime) == (
        0, ['Recorded D-1 option B. Confirm it on the host.'])
    assert runtime.calls == []


@pytest.mark.parametrize('kind', ['remote.pending', 'remote.started', 'remote.resumed', 'remote.stopped'])
def test_remote_kinds_are_reserved_to_the_listener_and_silent(ws, kind, capsys):
    from wuwei import signal
    from wuwei.__main__ import main
    assert main(['event', kind]) == 1
    assert 'wuwei listen' in capsys.readouterr().err
    assert kind in signal.SILENT
