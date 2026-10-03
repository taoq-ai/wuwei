"""Commands from the owner DM: vocabulary, the remote-command guards, and one session per thread."""

import json

import pytest

from wuwei import state, workspace
from wuwei.registry import Result


OWNER = '[owner]\nname = "Robin Example"\n[control_plane]\nowner = "T1/U1"\n'


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
def ws(bare, monkeypatch):
    from wuwei.guards import agent_launch
    monkeypatch.setattr(agent_launch, 'free_memory', lambda config, root: 2**40)
    state._write_state(lambda data: None, bare, reserved=False)
    return bare


FRESH = 'D1/1790769590.000100'  # ten seconds before WUWEI_NOW


def event(ident, text, channel='D1', sender='T1/U1'):
    return {'id': ident, 'source': 'slack', 'channel': channel, 'thread': '', 'sender': sender,
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


def test_config_and_credential(bare):
    from wuwei import env
    (bare / '.wuwei/config.toml').write_text('[owner]\nname = "Robin Example"\n')
    assert workspace.load_config(bare)['control_plane']['owner'] == ''
    (bare / '.wuwei/config.toml').write_text(OWNER)
    assert workspace.load_config(bare)['control_plane']['owner'] == 'T1/U1'
    assert 'WUWEI_TOTP_SECRET' in env.CREDENTIALS


@pytest.mark.parametrize('text, parsed', [
    ('plan', ('plan', '')), ('Plan today.', ('plan', '')), ('status', ('status', '')),
    ('REPORT!', ('report', '')), ('stop all', ('stop', 'all')),
    ('stop 1a2b3c4d', ('stop', '1a2b3c4d')), ('run daily-brief', ('run', 'daily-brief')),
    ('ask What  changed Today?', ('ask', 'What changed Today?')),
    ('cloud repo fix it', ('cloud', '')),
    ('run rm -rf', None), ('planet', None), ('plan: x', None), ('ask', None),
    ('stop 1a2b', None), ('status please', None), ('rm -rf /', None), ('approve D-1', None),
    ('more d-3', ('more', 'D-3')), ('More D-3.', ('more', 'D-3')), ('more D-0', None),
])
def test_parse_vocabulary(text, parsed):
    assert remote().parse(text) == parsed


def test_fixed_lines_pass_the_outward_lint(ws):
    from wuwei import outward
    module, config = remote(), workspace.load_config(ws)
    for text in (module.VOCABULARY, module.UNAVAILABLE, module.FAILED, module.CONFIRM,
                 module.NOTHING, module.CHANGED, module.LOW_MEMORY,
                 module.ANSWERED.format(identifier='D-1', option='A'),
                 module.NOT_PENDING.format(identifier='D-1'), module.ON_HOST.format(identifier='D-1')):
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
    assert remote().dm('wuwei is busy.', root=ws).exit == 1
    assert chat == []


@pytest.mark.parametrize('owner', ['[control_plane]\nowner = "T1/U1"\n',
                                   '[owner]\nname = "Dry Run Operator"\n'])
def test_owner_dm_reply_needs_no_owner_name(ws, chat, owner):
    # Replies in the owner DM are addressed to the owner: no third-person owner rules.
    (ws / '.wuwei/config.toml').write_text(owner)
    assert remote().dm(remote().CONFIRM, root=ws).exit == 0
    assert remote().dm(remote().FAILED, root=ws).exit == 0
    assert chat == [remote().CONFIRM, remote().FAILED]


@pytest.mark.parametrize('channel', ['C0123ABC', 'G0123ABC'])
def test_owner_dm_channel_that_is_not_a_dm_gets_the_full_lint(ws, chat, monkeypatch, channel):
    (ws / '.wuwei/config.toml').write_text('[owner]\nname = "Dry Run Operator"\n')
    monkeypatch.setenv('SLACK_OWNER_DM_CHANNEL', channel)
    assert remote().dm('Dry Run Operator said she will look at it.', root=ws).exit == 1
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


def test_unmatched_channel_logs_and_is_not_a_command(ws, capsys):
    assert handled(ws, 'status', channel='C9', ident='C9/1790769590.000100') == (0, [])
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 1 and 'remote.unmatched' in lines[0]
    assert 'C9/1790769590.000100' in lines[0] and 'status' not in lines[0]


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
    (ws / '.wuwei/config.toml').write_text(OWNER + 'content = "none"\n')
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


@pytest.mark.parametrize('level', ['full', 'brief'])
def test_status_counts_draft_ai_tells_at_full_dm_verbosity(ws, level):
    from wuwei import registry
    (ws / '.wuwei/config.toml').write_text(OWNER + f'[owner.verbosity]\ndm = "{level}"\n')
    chat = registry.load('chat', workspace.load_config(ws))
    for text in ('This is not just a fix but a rewrite. We delve into it.', 'We delve into it.'):
        assert chat.post('C2', text, None, root=ws).exit == 1
    code, sent = handled(ws, 'status')
    assert code == 0
    assert sent[0].endswith(' | ai tells 3') == (level == 'full')
    assert ('ai tells' in sent[0]) == (level == 'full')


@pytest.mark.parametrize('text', ['plan today', 'plan today 000000', 'ask what changed'])
def test_issue_acceptance_plan_without_a_second_factor_starts_nothing(ws, text):
    runtime = Runtime()
    assert handled(ws, text, runtime=runtime, ident=FRESH) == (1, [remote().CONFIRM])
    assert runtime.calls == [] and state.read_state(ws).get('sessions', {}) == {}
    assert [row['payload'] for row in events(ws, 'remote.')] == [
        {'id': FRESH, 'command': text.split()[0]}]


def test_reply_without_a_remote_session_is_recorded_evidence(ws):
    identifier = routed(ws)
    assert handled(ws, 'option B on D-1') == (0, ['Recorded D-1 option B. Confirm it on the host.'])
    assert identifier == 'D-1'
    assert [row['payload'] for row in events(ws, 'decision.replied')] == [{'id': 'D-1', 'option': 'B'}]
    assert state.read_state(ws).get('decision_outcomes', {}) == {}


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
    return (control_plane.render(identifier, fields, 'summary', 'brief', root)
            + f'\nReply more {identifier} for the full record.\n' + control_plane.HELP)


@pytest.fixture
def open_gate(monkeypatch):
    """The second factor is satisfied: every code_step check returns a step."""
    module = remote()
    monkeypatch.setattr(module, 'code_step', lambda root, event, code: 1)
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
    assert payloads(ws, 'remote.') == [{'id': 'D1/1.000001', 'factor': 'code', 'step': 1},
                                       {'session': S, 'command': 'plan'}]
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


@pytest.mark.parametrize('kind', ['remote.pending', 'remote.started', 'remote.resumed', 'remote.stopped',
                                  'remote.ignored', 'remote.refused', 'remote.confirmed'])
def test_remote_kinds_are_reserved_to_the_listener(ws, kind, capsys):
    from wuwei import signal
    from wuwei.__main__ import main
    assert main(['event', kind]) == 1
    assert 'wuwei listen' in capsys.readouterr().err
    assert signal.classify({'kind': kind, 'payload': {}}, {})[0] == (
        'page' if kind == 'remote.refused' else 'silent')


@pytest.mark.parametrize('who, expected', [
    ('T1/U1', 'owner'), ('T9/U1', 'changed'), ('/U1', 'changed'), ('T1/U2', 'other'), ('U1', 'changed')])
def test_sender_compares_with_the_pin(who, expected):
    config = {'control_plane': {'owner': 'T1/U1'}}
    assert remote().sender(config, {'sender': who}) == expected


@pytest.mark.parametrize('pin', ['', 'U1', 'T1/', 't1/u1', 'T1/U1/U2'])
def test_sender_without_a_valid_pin_cannot_run(pin):
    with pytest.raises(ValueError, match=r'control_plane\.owner.*T1/U1'):
        remote().sender({'control_plane': {'owner': pin}}, {'sender': 'T1/U1'})


@pytest.mark.parametrize('text', ['plan today', 'status'])
def test_issue_acceptance_changed_identity_is_refused_and_alerted(ws, text):
    runtime, transport = Runtime(), Transport()
    assert remote().handle(ws, event('D1/1.000001', text, sender='T9/U1'),
                           transport=transport, runtime=runtime) == 1
    assert runtime.calls == [] and transport.sent == [remote().CHANGED]
    assert [(row['kind'], row['payload']) for row in events(ws, 'remote.')] == [
        ('remote.refused', {'id': 'D1/1.000001', 'pin': 'T1/U1'})]


def test_other_senders_are_logged_once_and_never_answered(ws):
    transport = Transport()
    for ident, who in (('D1/1.000001', 'T1/U2'), ('D1/2.000001', 'T1/U2'), ('D1/3.000001', 'T2/U3')):
        assert remote().handle(ws, event(ident, 'plan', sender=who), transport=transport) == 0
    assert transport.sent == []
    assert [(row['kind'], row['payload']) for row in events(ws, 'remote.')] == [
        ('remote.ignored', {'sender': 'T1/U2'}), ('remote.ignored', {'sender': 'T2/U3'})]


def test_no_pin_cannot_run(ws, capsys):
    (ws / '.wuwei/config.toml').write_text('[owner]\nname = "Robin Example"\n')
    assert handled(ws, 'status') == (2, [remote().FAILED])
    out = capsys.readouterr().out
    assert 'control_plane.owner' in out and 'T1/U1' in out


RFC_KEY = b'12345678901234567890'


@pytest.mark.parametrize('t, code', [(59, '287082'), (1111111109, '081804'), (1111111111, '050471'),
                                     (1234567890, '005924'), (2000000000, '279037')])
def test_totp_matches_the_rfc_6238_vectors(t, code):
    assert remote().totp(RFC_KEY, t // 30) == code


@pytest.mark.parametrize('text, parts', [
    ('plan today 123456', ('plan today', '123456')), ('plan', ('plan', '')),
    ('stop 12345678', ('stop 12345678', '')), ('ask about 123456?', ('ask about 123456?', '')),
    ('123456', ('123456', ''))])
def test_split_takes_a_trailing_code(text, parts):
    assert remote().split(text) == parts


def test_parse_confirm():
    assert remote().parse('Confirm.') == ('confirm', '')


def coded(ts):
    return remote().totp(RFC_KEY, int(float(ts)) // 30)


@pytest.fixture
def secret(monkeypatch):
    import base64
    monkeypatch.setenv('WUWEI_TOTP_SECRET', base64.b32encode(RFC_KEY).decode().lower())


def test_a_current_code_starts_the_session_once(ws, secret):
    stale = 'D1/1790769479.000100'
    runtime = Runtime(ran())
    assert handled(ws, f'plan today {coded(stale[3:])}', runtime=runtime, ident=stale) == (
        1, [remote().CONFIRM])
    code, sent = handled(ws, f'plan today {coded(FRESH[3:])}', runtime=runtime, ident=FRESH)
    assert code == 0 and runtime.calls == [(remote().PLAN_PROMPT, None, planner_tools())]
    rows = events(ws, 'remote.')
    assert [row['kind'] for row in rows] == ['remote.pending', 'remote.confirmed', 'remote.started']
    assert rows[1]['payload'] == {'id': FRESH, 'factor': 'code', 'step': 1790769590 // 30}
    again = 'D1/1790769591.000100'
    assert handled(ws, f'plan today {coded(FRESH[3:])}', runtime=runtime, ident=again) == (
        1, [remote().CONFIRM])
    assert len(runtime.calls) == 1


def test_a_secret_that_is_not_base32_cannot_run(ws, monkeypatch, capsys):
    monkeypatch.setenv('WUWEI_TOTP_SECRET', 'not-base32-1890')
    assert handled(ws, 'plan today 123456', ident=FRESH) == (2, [remote().FAILED])
    assert 'not-base32-1890' not in capsys.readouterr().out


@pytest.mark.parametrize('text, sent', [
    ('status', None), ('report', None), ('stop 0f8fad5b', ['Stopped 1 sessions.'])])
def test_read_and_stop_commands_need_no_factor(ws, text, sent):
    remote_row(ws, S, [])
    code, said = handled(ws, text)
    assert code == 0 and (sent is None or said == sent)
    assert events(ws, 'remote.pending') == []


def test_a_decision_reply_resumes_without_a_factor(ws):
    routed(ws)
    remote_row(ws, S, ['D-1'])
    runtime = Runtime(ran())
    assert handled(ws, 'option B on D-1', runtime=runtime)[0] == 0
    assert runtime.calls == [('Decision D-1: option B.', S, planner_tools())]
    assert events(ws, 'remote.pending') == []


def pending(root, ident, text):
    from wuwei import inbox
    assert inbox.store(root, workspace.load_config(root), [event(ident, text)]).exit == 0
    assert handled(root, text, ident=ident) == (1, [remote().CONFIRM])


def test_a_confirm_reply_runs_the_latest_pending_command_once(ws):
    pending(ws, 'D1/1790769580.000100', 'plan today')
    pending(ws, FRESH, 'ask what changed')
    runtime = Runtime(ran(result=''))
    code, sent = handled(ws, 'confirm', runtime=runtime, ident='D1/1790769595.000100')
    assert code == 0 and runtime.calls == [(remote().ASK_PROMPT + 'what changed', None, ['Read', 'Glob', 'Grep'])]
    assert state.read_state(ws)['sessions'][S]['thread'] == FRESH
    assert payloads(ws, 'remote.confirmed') == [{'id': FRESH, 'factor': 'reply'}]
    assert handled(ws, 'Confirm.', runtime=runtime, ident='D1/1790769596.000100') == (1, [remote().NOTHING])
    assert len(runtime.calls) == 1


def test_confirm_with_nothing_to_confirm_runs_nothing(ws, monkeypatch):
    runtime = Runtime()
    assert handled(ws, 'confirm', runtime=runtime) == (1, [remote().NOTHING])
    state.append_event('remote.pending', {'id': 'D1/0.000001', 'command': 'stop'}, root=ws)
    assert handled(ws, 'confirm', runtime=runtime) == (1, [remote().NOTHING])
    pending(ws, FRESH, 'plan today')
    monkeypatch.setenv('WUWEI_NOW', '2026-09-30T12:02:01+00:00')
    assert handled(ws, 'confirm', runtime=runtime, ident='D1/1790769720.000100') == (1, [remote().NOTHING])
    assert runtime.calls == [] and events(ws, 'remote.confirmed') == []


def test_stop_all_is_accepted_from_a_changed_identity(ws):
    remote_row(ws, S, [])
    remote_row(ws, T, [])
    transport = Transport()
    assert remote().handle(ws, event('D1/1.000001', 'stop all', sender='T9/U1'), transport=transport) == 0
    assert all('stopped' in row for row in state.read_state(ws)['sessions'].values())
    assert events(ws, 'remote.refused') == [] and transport.sent == ['Stopped 2 sessions.']
    remote_row(ws, 'ffffffff-d9cb-469f-a165-70867728950e', [])
    assert remote().handle(ws, event('D1/2.000001', 'stop ffffffff', sender='T9/U1'), transport=transport) == 1
    assert transport.sent[-1] == remote().CHANGED


def test_low_memory_starts_and_resumes_nothing(ws, monkeypatch):
    from wuwei.guards import agent_launch
    monkeypatch.setattr(agent_launch, 'free_memory', lambda config, root: 1)
    runtime, t = Runtime(), Transport()
    assert remote().start(ws, 'plan', FRESH, 'p', transport=t, runtime=runtime) == 1
    remote_row(ws, S, [])
    assert remote().resume(ws, S, 'D-1', 'B', transport=t, runtime=runtime) == 1
    assert runtime.calls == [] and t.sent == [remote().LOW_MEMORY] * 2
    assert list(state.read_state(ws)['sessions']) == [S] and events(ws, 'remote.') == []


def test_unmeasured_memory_cannot_run(ws, monkeypatch, open_gate):
    from wuwei.guards import agent_launch

    def unmeasured(config, root):
        raise ValueError('free memory unmeasured')
    monkeypatch.setattr(agent_launch, 'free_memory', unmeasured)
    runtime = Runtime()
    assert handled(ws, 'plan today', runtime=runtime) == (2, [remote().FAILED])
    assert runtime.calls == []


class SlackReply(__import__('io').BytesIO):
    status = 200


def test_runbook_hello_through_real_env(tmp_path, monkeypatch, capsys):
    # The runbook against a fake Slack: a fresh init, the real .wuwei/env, no patched module.
    import os
    import urllib.request
    from urllib.parse import urlsplit
    from wuwei import outward
    from wuwei.__main__ import main
    from wuwei.commands import init
    monkeypatch.setattr(os, 'environ', os.environ.copy())
    for name in ('SLACK_BOT_TOKEN', 'SLACK_USER_TOKEN', 'SLACK_API_BASE', 'WUWEI_TOTP_SECRET',
                 'WUWEI_WORKSPACE'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('WUWEI_NOW', '2026-09-30T12:00:00+00:00')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(init, '_register_mcp', lambda root: 0)
    assert main(['init', str(tmp_path)]) == 0
    path = tmp_path / '.wuwei/config.toml'
    assert 'chat = "none"' in path.read_text()
    path.write_text(path.read_text().replace('chat = "none"', 'chat = "slack"\ninbound = "slack"'))
    token, base = 'fake-bot-credential', 'http://127.0.0.1:9/fake/'
    secret = tmp_path / '.wuwei/env'
    secret.write_text(f'SLACK_BOT_TOKEN={token}\nSLACK_OWNER_DM_CHANNEL=D0123ABC\nSLACK_API_BASE={base}\n')
    secret.chmod(0o600)
    queued, posts = [], []

    def urlopen(request, timeout=None):
        assert request.full_url.startswith(base)
        method = urlsplit(request.full_url).path.rsplit('/', 1)[-1]
        if method == 'chat.postMessage':
            posts.append(json.loads(request.data)['text'])
            body = {'ok': True, 'channel': 'D0123ABC', 'ts': f'1790769595.00000{len(posts)}'}
        else:
            body = {'ok': True, 'messages': queued[:], 'response_metadata': {'next_cursor': ''}}
            queued.clear()
        return SlackReply(json.dumps(body).encode())
    monkeypatch.setattr(urllib.request, 'urlopen', urlopen)
    hello = {'user': 'U0123ABC', 'team': 'T0123ABC', 'text': 'hello'}
    queued.append({**hello, 'ts': '1790769590.000100'})
    assert main(['listen', '--once']) == 2
    output = capsys.readouterr()
    assert 'this message came from T0123ABC/U0123ABC' in output.out
    assert output.out.count(outward.OWNER_UNSET) == 1
    assert posts == [remote().FAILED]
    path.write_text(path.read_text().replace('owner = ""', 'owner = "T0123ABC/U0123ABC"', 1))
    assert workspace.load_config(tmp_path)['control_plane']['owner'] == 'T0123ABC/U0123ABC'
    queued.append({**hello, 'ts': '1790769591.000100'})
    assert main(['listen', '--once']) == 0
    assert posts[-1] == remote().VOCABULARY
    rows = [json.loads(line) for line in (tmp_path / '.wuwei/inbox/inbox.jsonl').read_text().splitlines()]
    assert {row['channel'] for row in rows} == {'D0123ABC'}
    assert all(row['id'].startswith('D0123ABC/') for row in rows)
    stored = ((tmp_path / '.wuwei/inbox/inbox.jsonl').read_text()
              + (workspace.day_dir(tmp_path) / 'events.jsonl').read_text())
    printed = output.out + output.err + str(capsys.readouterr())
    for value in (token, base, '127.0.0.1:9'):
        assert value not in stored + printed


def test_issue_acceptance_stop_all_drops_the_live_session_count(ws, capsys):
    from wuwei.__main__ import main
    remote_row(ws, S, [])
    remote_row(ws, T, [])
    state._write_state(lambda data: data['sessions'].update(A={**data['sessions'][T], 'role': 'adhoc'}),
                       ws, reserved=False)
    assert main(['status', '--line']) == 0
    assert 'sessions 3' in capsys.readouterr().out
    remote().stop(ws, 'all', transport=Transport())
    assert main(['status', '--line']) == 0
    assert 'sessions 1' in capsys.readouterr().out
    assert main(['status', '--json']) == 0
    assert json.loads(capsys.readouterr().out)['sessions'] == 1


class Down(Transport):
    def dm(self, text, *, root=None):
        return Result(2, None, 'slack down')


def test_escalate_new_sends_each_host_decision_once(ws):
    routed(ws)
    t = Transport()
    assert remote().escalate_new(ws, t) == 0
    assert t.sent == [escalation(ws, 'D-1')]
    assert payloads(ws, 'decision.escalated') == [{'id': 'D-1'}]
    assert remote().escalate_new(ws, t) == 0
    assert len(t.sent) == 1 and len(events(ws, 'decision.escalated')) == 1


def test_escalate_new_records_nothing_when_the_send_fails(ws):
    routed(ws)
    assert remote().escalate_new(ws, Down()) == 2
    assert events(ws, 'decision.escalated') == []
    t = Transport()
    assert remote().escalate_new(ws, t) == 0
    assert t.sent == [escalation(ws, 'D-1')]


def test_escalate_new_falls_back_to_the_id_when_the_lint_refuses(ws):
    routed(ws, VALID.replace('Which fix?', 'Which fix does Robin want?'))
    t = Transport()
    assert remote().escalate_new(ws, t) == 0
    assert t.sent == ['D-1 is waiting in the workspace.']
    assert payloads(ws, 'decision.escalated') == [{'id': 'D-1'}]


def test_a_turn_escalates_once_and_sends_host_decisions_first(ws):
    runtime = Runtime(ran(), effect=routed)
    t = Transport()
    assert remote().start(ws, 'plan', 'D1/1.000001', 'p', transport=t, runtime=runtime) == 0
    assert t.sent == [escalation(ws, 'D-1'), f'Session {S[:8]}: turn ended, 1 decisions waiting.']
    assert remote().escalate_new(ws, t) == 0 and len(t.sent) == 2
    routed(ws)
    t = Transport()
    runtime = Runtime(ran(session=T))
    assert remote().start(ws, 'plan', 'D1/2.000001', 'p', transport=t, runtime=runtime) == 0
    assert t.sent == [escalation(ws, 'D-2'), f'Session {T[:8]}: turn ended, 0 decisions waiting.']


def test_issue_acceptance_a_conflicting_second_answer_is_refused(ws):
    routed(ws)
    recorded = 'Recorded D-1 option A. Confirm it on the host.'
    refused = remote().ANSWERED.format(identifier='D-1', option='A')
    assert 'already has option A' in refused
    assert handled(ws, 'option A on D-1') == (0, [recorded])
    assert handled(ws, 'option B on D-1', ident='D1/2.000001') == (1, [refused])
    assert handled(ws, 'drop it', ident='D1/3.000001') == (1, [refused])
    assert handled(ws, 'option A on D-1', ident='D1/4.000001') == (0, [recorded])
    assert payloads(ws, 'decision.replied') == [{'id': 'D-1', 'option': 'A'}]


def test_a_second_answer_resumes_no_session(ws):
    routed(ws)
    remote_row(ws, S, ['D-1'])
    runtime = Runtime(ran())
    assert handled(ws, 'option A on D-1', runtime=runtime)[0] == 0
    assert len(runtime.calls) == 1
    for ident, text in (('D1/2.000001', 'option B on D-1'), ('D1/3.000001', 'option A on D-1')):
        handled(ws, text, runtime=runtime, ident=ident)
    assert len(runtime.calls) == 1


def refused_pages(capsys):
    from wuwei.__main__ import main
    capsys.readouterr()
    assert main(['nudges', '--json']) == 0
    return [row for row in json.loads(capsys.readouterr().out) if row['source'] == 'remote.refused']


def test_refused_page_clears_when_the_pin_is_edited(ws, capsys):
    from wuwei.__main__ import main
    remote().handle(ws, event('D1/1.000001', 'status', sender='T9/U1'), transport=Transport())
    assert [row['tier'] for row in refused_pages(capsys)] == ['page']
    assert len(refused_pages(capsys)) == 1
    (ws / '.wuwei/config.toml').write_text(OWNER.replace('T1/U1', 'T9/U1'))
    assert refused_pages(capsys) == []
    assert main(['status', '--json']) == 0
    assert json.loads(capsys.readouterr().out)['pages'] == 0
    state.append_event('remote.refused', {'id': 'D1/2.000001'}, ws)
    assert len(refused_pages(capsys)) == 1


def test_acknowledged_kind_is_reserved_and_silent(ws, capsys):
    from wuwei.__main__ import main
    from wuwei import signal
    assert main(['event', 'remote.acknowledged']) == 1
    assert 'wuwei remote ack' in capsys.readouterr().err
    assert signal.classify({'kind': 'remote.acknowledged', 'payload': {}}, {})[0] == 'silent'


def test_issue_acceptance_remote_ack_clears_a_refused_page(ws, capsys, monkeypatch):
    from hashlib import sha256
    from wuwei.__main__ import main
    from wuwei import integrity
    calls = []
    monkeypatch.setattr(integrity, '_host_confirm', lambda token, prompt: calls.append((token, prompt)) or True)
    capsys.readouterr()
    assert main(['remote', 'ack']) == 0
    assert capsys.readouterr().out == 'remote ack: no refused sender message today\n'
    assert calls == [] and payloads(ws, 'remote.') == []
    remote().handle(ws, event('D1/1.000001', 'status', sender='T9/U1'), transport=Transport())
    assert len(refused_pages(capsys)) == 1
    assert main(['remote', 'ack']) == 0
    assert calls[0][0] == sha256(b'D1/1.000001').hexdigest()[:12] and 'D1/1.000001' in calls[0][1]
    assert 'type:' not in calls[0][1]
    assert payloads(ws, 'remote.acknowledged') == [{'ids': ['D1/1.000001']}]
    assert refused_pages(capsys) == []
    assert main(['status', '--json']) == 0
    assert json.loads(capsys.readouterr().out)['pages'] == 0
    remote().handle(ws, event('D1/2.000001', 'status', sender='T9/U1'), transport=Transport())
    assert len(refused_pages(capsys)) == 1
    monkeypatch.setattr(integrity, '_host_confirm', lambda token, prompt: calls.append((token, prompt)) and False)
    assert main(['remote', 'ack']) == 1
    assert capsys.readouterr().err.startswith('remote ack: owner confirmation declined;')
    assert len(refused_pages(capsys)) == 1
    assert payloads(ws, 'remote.acknowledged') == [{'ids': ['D1/1.000001']}]
    monkeypatch.setattr(integrity, '_host_confirm', lambda token, prompt: calls.append((token, prompt)) or True)
    assert main(['remote', 'ack']) == 0
    assert calls[-1][0] == sha256(b'D1/2.000001').hexdigest()[:12]
    assert payloads(ws, 'remote.acknowledged')[-1] == {'ids': ['D1/2.000001']}
    assert refused_pages(capsys) == []


def test_issue_acceptance_remote_ack_without_a_terminal_is_an_owner_action(ws, capsys, monkeypatch):
    import builtins
    from wuwei.__main__ import main
    remote().handle(ws, event('D1/1.000001', 'status', sender='T9/U1'), transport=Transport())
    real_open = builtins.open
    def fake_open(name, *args, **kwargs):
        if name == '/dev/tty':
            raise OSError(6, 'Device not configured')
        return real_open(name, *args, **kwargs)
    monkeypatch.setattr(builtins, 'open', fake_open)
    capsys.readouterr()
    assert main(['remote', 'ack']) == 2
    assert capsys.readouterr().err == 'wuwei remote: this is an owner action: run it in a host terminal\n'
    assert payloads(ws, 'remote.acknowledged') == []
    assert len(refused_pages(capsys)) == 1


def test_more_returns_the_full_record_of_a_pending_decision(ws):
    from wuwei import decision
    assert 'more D-n' in remote().VOCABULARY
    text = (VALID.replace('test_example', 'test_fix')  # 'example' is the owner's name here.
            + '## Notes\nEvidence: probe.log\n')
    routed(ws, text)
    assert handled(ws, 'more D-1') == (0, [text.rstrip()])
    assert handled(ws, 'more D-9') == (1, ['D-9 is not waiting on you.'])
    assert events(ws, 'remote.') == []
    (ws / '.wuwei/config.toml').write_text(OWNER + 'content = "none"\n')
    assert handled(ws, 'more d-1.') == (0, ['D-1 options: A, B'])


def test_more_that_the_lint_refuses_points_to_the_host(ws):
    routed(ws, VALID.replace('Pre-mortem: Regression returns.', 'Pre-mortem: Robin rejects it.'))
    assert remote().escalate_new(ws, (t := Transport())) == 0 and 'Robin' not in t.sent[0]
    assert handled(ws, 'more D-1') == (0, ['The full record of D-1 is on the host.'])
