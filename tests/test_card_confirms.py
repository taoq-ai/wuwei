"""#529: an answer given on an Ask card is the confirmation of the config write it leads to."""

from hashlib import sha256
import io
import json
import re

import pytest

from wuwei import decision, sessions, state, workspace
from wuwei.guards.decision import record_gate


@pytest.fixture
def ws(tmp_path, monkeypatch):
    from wuwei import plan
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T12:00:00+00:00')
    root = tmp_path / 'workspace'
    (root / '.wuwei').mkdir(parents=True)
    (root / '.wuwei/config.toml').write_text('[security]\nposture = "guarded"\n')
    workspace.day_dir(root).mkdir(parents=True)
    (workspace.day_dir(root) / 'plan.md').write_text('# Morning plan\n')
    plan.session('planner-1', root)
    monkeypatch.chdir(root)
    return root


def strict(root):
    (root / '.wuwei/config.toml').write_text('[security]\nposture = "strict"\n')


def answer(root, header, text, reply, session='planner-1', **extra):
    """The PostToolUse payload of one answered card, fed to record_gate."""
    return record_gate({'cwd': str(root), 'session_id': session, 'tool_name': 'AskUserQuestion',
                        'tool_input': {'questions': [{'question': text, 'header': header}]},
                        'tool_response': {'answers': {text: reply}}, **extra})


def asked(root):
    return state.read_state(root)['sessions']['planner-1'].get('gate_asked', [])


def events(root, kind):
    path = workspace.day_dir(root) / 'events.jsonl'
    return [row['payload'] for row in map(json.loads, path.read_text().splitlines()) if row['kind'] == kind]


def no_terminal(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError('the host terminal was opened')
    monkeypatch.setattr('wuwei.integrity._host_confirm', fail)


class Terminal(io.StringIO):
    def isatty(self):
        return True


# Phase 1: the card answer is recorded.

def test_card_topic_normalises_and_hashes():
    topic = sessions.card_topic('CAP', ' 5 (Recommended) ')
    assert topic == sessions.card_topic('CAP', '5') == 'CAP=' + sha256(b'5').hexdigest()
    assert re.fullmatch(r'CAP=[0-9a-f]{64}', topic)


def test_card_answered_only_for_the_planner_outside_strict(ws, monkeypatch):
    state._write_state(lambda data: data['sessions']['planner-1'].update(
        gate_asked=[sessions.card_topic('CAP', '5')]), ws, reserved=False)
    monkeypatch.setattr('sys.stdin', Terminal())
    assert not sessions.card_answered(ws, 'CAP', '5')  # no session id: a host terminal
    monkeypatch.setenv('WUWEI_SESSION_ID', 'other')
    assert not sessions.card_answered(ws, 'CAP', '5')
    monkeypatch.setenv('WUWEI_SESSION_ID', 'planner-1')
    assert sessions.card_answered(ws, 'CAP', '5') and not sessions.card_answered(ws, 'CAP', '3')
    strict(ws)
    assert not sessions.card_answered(ws, 'CAP', '5')


def test_record_gate_records_the_answer_of_a_gate_card(ws):
    text = decision.gate(ws) + 'How many items may build at once by default? (CAP)'
    assert answer(ws, 'CAP', text, '5') == (0, '')
    assert asked(ws) == [sessions.card_topic('CAP\n' + text, '5')]


def test_record_gate_records_the_answer_of_a_decision_card(ws):
    from test_decision import save
    save(ws, name='D-1.md')
    assert answer(ws, 'D-1', 'D-1: Which cap?', 'cap = 5 (Recommended)') == (0, '')
    assert asked(ws) == sorted(['D-1', sessions.card_topic('D-1', 'cap = 5')])


def test_record_gate_records_a_decision_card_that_cites_the_gate(ws):
    from test_decision import save
    save(ws, name='D-1.md')
    text = decision.gate(ws) + 'D-1: Which cap?'
    assert answer(ws, 'D-1', text, 'cap = 5') == (0, '')
    assert asked(ws) == sorted(['D-1', sessions.card_topic('D-1', 'cap = 5')])


def test_record_gate_records_no_answer_for_others(ws):
    text = decision.gate(ws) + 'How many items may build at once by default? (CAP)'
    unanswered = {'cwd': str(ws), 'session_id': 'planner-1', 'tool_name': 'AskUserQuestion',
                  'tool_input': {'questions': [{'question': text, 'header': 'CAP'}]}}
    assert record_gate(unanswered) == (0, '')
    assert answer(ws, 'CAP', text, '5', agent_id='a1') == (0, '')
    assert answer(ws, 'CAP', text, '5', session='other') == (0, '')
    assert answer(ws, 'CAP', 'How many? (CAP)', '5') == (0, '')  # not a gate card
    assert asked(ws) == []
    goals = decision.gate(ws) + 'confirm goals G-1?'
    assert answer(ws, 'Goals', goals, 'Yes') == (0, '')
    assert asked(ws) == sorted(['goals', sessions.card_topic('Goals\n' + goals, 'Yes')])


# Phase 2: config cards.

def main(*args):
    from wuwei.__main__ import main as entry
    return entry(list(args))


def config(root):
    import tomllib
    return tomllib.loads((root / '.wuwei/config.toml').read_text())


# Phase 3: decision cards.

CONFIG_RECORD = '''Question: How many items may build at once by default?
Class: other
Context: .wuwei/config.toml sets cap = 1 today.
Options:
| Option | Title | Rationale | Consequence |
| --- | --- | --- | --- |
| A | cap = 5 | Passes every must and scores 8 on Throughput. | Five items build at once. |
| B | cap = 3 | Passes every must and scores 5 on Throughput. | Three items build at once. |
| C | Keep the current cap | Passes every must but scores 1 on Throughput. | One item builds at once. |
Musts:
| Criterion | A | B | C |
| --- | --- | --- | --- |
| Safe | pass | pass | pass |
Wants:
| Criterion | Weight | A | B | C |
| --- | --- | --- | --- | --- |
| Throughput | 10 | 8 | 5 | 1 |
Recommendation: A
Reasoning: Throughput decided it. A slow host would flip it to B.
Confidence: high
Reversibility: two-way
Blast radius: workspace config
Pre-mortem: The host runs out of memory.
Revisit: The host runs out of memory.
Decided-by: owner
Outcome: pending
'''
QUESTION = 'D-1: How many items may build at once by default?'


def config_card(root, reply='cap = 5 (Recommended)', route=True):
    from test_decision import save
    save(root, CONFIG_RECORD, 'D-1.md')
    if route:
        assert main('decision', 'route', 'D-1') == 0
    if reply:
        assert answer(root, 'D-1', QUESTION, reply) == (0, '')


def set_from_card(key='cap', value='5', card='D-1'):
    return main('config', 'set', key, value, '--from-card', card)


def test_assignment_titles():
    from wuwei.commands.config import assignment
    assert assignment('cap = 5') == ('cap', 5)
    assert assignment('outbound.default_tier = "ask"') == ('outbound.default_tier', 'ask')
    for title in ('Keep', 'cap = five', 'repos.0 = 1', 'cap 5', 'Keep the current cap'):
        assert assignment(title) is None, title


def test_config_set_from_a_decision_card(ws, monkeypatch, capsys):
    no_terminal(monkeypatch)
    config_card(ws)
    capsys.readouterr()
    monkeypatch.setenv('WUWEI_SESSION_ID', 'planner-1')
    assert set_from_card() == 0, capsys.readouterr().err
    assert 'replaced: cap = 5 (was ' in capsys.readouterr().out
    assert config(ws)['cap'] == 5
    data = state.read_state(ws)
    assert data['decision_outcomes']['D-1']['decided_by'] == 'owner'
    assert decision.answered(data, 'D-1') == 'A'
    assert [row['id'] for row in events(ws, 'decision.decided')] == ['D-1']
    assert events(ws, 'config.set') == [{'keys': ['cap'], 'card': 'D-1'}]
    capsys.readouterr()
    assert set_from_card() == 0
    out = capsys.readouterr().out
    assert 'No config.toml changes' in out and 'replaced' not in out
    assert len(events(ws, 'decision.decided')) == 1


@pytest.mark.parametrize('reply,value,card', [
    ('cap = 3', '5', 'D-1'),   # another answer
    ('cap = 5', '7', 'D-1'),   # no option cap = 7
    ('7', '7', 'D-1'),         # an Other text is not an option title
    (None, '5', 'D-1'),        # never answered
    ('cap = 5', '5', 'D-2'),   # no such card
    ('cap = 5', '5', 'D-x'),   # not a record id
])
def test_config_set_from_card_mismatch_writes_nothing(ws, monkeypatch, capsys, reply, value, card):
    no_terminal(monkeypatch)
    config_card(ws, reply)
    monkeypatch.setenv('WUWEI_SESSION_ID', 'planner-1')
    before = (ws / '.wuwei/config.toml').read_text()
    capsys.readouterr()
    assert set_from_card(value=value, card=card) == 1
    err = capsys.readouterr().err
    assert (ws / '.wuwei/config.toml').read_text() == before
    assert 'decision show' in err and ('D-x' in err or f'bin/wuwei decision show {card} --widget' in err)
    assert not state.read_state(ws).get('decision_outcomes')


def test_config_set_from_card_before_route_completes_on_rerun(ws, monkeypatch, capsys):
    no_terminal(monkeypatch)
    config_card(ws, route=False)
    monkeypatch.setenv('WUWEI_SESSION_ID', 'planner-1')
    assert set_from_card() == 1
    assert 'route this pending owner decision first' in capsys.readouterr().err
    assert config(ws)['cap'] == 5
    assert main('decision', 'route', 'D-1') == 0
    assert set_from_card() == 0
    assert decision.answered(state.read_state(ws), 'D-1') == 'A'


def test_widget_of_a_config_record_prints_the_config_command(ws, capsys):
    from test_decision import VALID, save
    save(ws, CONFIG_RECORD, 'D-1.md')
    save(ws, VALID, 'D-2.md')
    assert main('decision', 'show', 'D-1', '--widget') == 0
    assert json.loads(capsys.readouterr().out)[0]['record'] == 'wuwei config set --from-card D-1'
    assert main('decision', 'show', 'D-2', '--widget') == 0
    card = decision.card_hash('D-2', decision.evaluate(VALID)[0])
    assert json.loads(capsys.readouterr().out)[0]['record'] == (
        f'{workspace.owner_cli(ws)} decide D-2 "<label>" --card {card}')


# Phase 4 (#831): config set asks its own Owner step card, under every posture.

def test_strict_from_card_asks_the_owner_step_card(ws, monkeypatch, capsys):
    from fakes import owner
    no_terminal(monkeypatch)
    config_card(ws)
    strict(ws)
    before = (ws / '.wuwei/config.toml').read_text()
    monkeypatch.setenv('WUWEI_SESSION_ID', 'planner-1')
    capsys.readouterr()
    assert main('config', 'set', '--from-card', 'D-1') == 1
    assert 'bin/wuwei config set <key> <value>' in capsys.readouterr().err
    assert set_from_card() == 1
    err = capsys.readouterr().err
    assert 'Owner step: bin/wuwei config set cap 5 (' in err and 'host terminal' not in err
    assert (ws / '.wuwei/config.toml').read_text() == before
    owner.answer_card(ws, err)
    assert set_from_card() == 0 and config(ws)['cap'] == 5
    assert not state.read_state(ws).get('decision_outcomes')


# Phase 5: no empty answer in a session.

@pytest.mark.parametrize('posture', ['guarded', 'strict'])
@pytest.mark.parametrize('session', ['planner-1', None])
@pytest.mark.parametrize('key,value,read', [('cap', '5', 5), ('owner.name', '"Pat"', 'Pat')])
def test_config_set_without_an_answer_names_the_owner_step_card(ws, monkeypatch, capsys, posture, session,
                                                                 key, value, read):
    from fakes import owner
    no_terminal(monkeypatch)
    if posture == 'strict':
        strict(ws)
    if session:
        monkeypatch.setenv('WUWEI_SESSION_ID', session)
    before = (ws / '.wuwei/config.toml').read_text()
    assert main('config', 'set', key, value) == 1
    err = capsys.readouterr().err
    assert f'Owner step: bin/wuwei config set {key} ' in err and f'"record": "bin/wuwei config set {key} ' in err
    assert 'host terminal' not in err and 'empty answer' not in err
    assert (ws / '.wuwei/config.toml').read_text() == before
    owner.answer_card(ws, err, reply='No')
    assert main('config', 'set', key, value) == 1
    owner.answer_card(ws, capsys.readouterr().err)
    assert main('config', 'set', key, value) == 0
    loaded = workspace.load_config(ws)
    assert (loaded['owner']['name'] if key == 'owner.name' else loaded['cap']) == read


# Phase 4: the hook lets the planner run the card's record command.

# Phase 6: config.set is a CLI-only, silent event kind.

def test_config_set_event_is_reserved_and_silent(ws, capsys):
    from wuwei.signal import classify
    assert main('event', 'config.set', '{}') == 1
    assert 'wuwei config set --from-card' in capsys.readouterr().err
    assert classify({'kind': 'config.set', 'payload': {'keys': ['cap'], 'card': 'cap'}}, {})[0] == 'silent'


# #600: a config card carries its values in Value rows; --from-card alone reads the answer.

PAPER = '[[repos]]\nname = "acme/paper"\npath = "paper"\ndefault_branch = "main"\nfast_checks = []\n'
CHECKS_QUESTION = 'D-1: Which fast checks gate every change in repo:acme/paper?'


def value_card(root, reply='Detected (Recommended)'):
    from test_decision import CHECKS_RECORD, save
    (root / 'paper').mkdir(exist_ok=True)
    with (root / '.wuwei/config.toml').open('a') as stream:
        stream.write(PAPER)
    save(root, CHECKS_RECORD, 'D-1.md')
    assert main('decision', 'route', 'D-1') == 0
    if reply:
        assert answer(root, 'D-1', CHECKS_QUESTION, reply) == (0, '')


def test_config_set_from_a_value_card(ws, monkeypatch, capsys):
    no_terminal(monkeypatch)
    value_card(ws)
    monkeypatch.setenv('WUWEI_SESSION_ID', 'planner-1')
    assert main('config', 'set', '--from-card', 'D-1') == 0, capsys.readouterr().err
    assert config(ws)['repos'][0]['fast_checks'] == ['make test', 'markdownlint .']
    assert decision.answered(state.read_state(ws), 'D-1') == 'A'
    assert events(ws, 'config.set') == [{'keys': ['repos.0.fast_checks'], 'card': 'D-1'}]


@pytest.mark.parametrize('value,code', [('["make test", "markdownlint ."]', 0), ('["make test"]', 1)])
def test_config_set_from_a_value_card_with_key_and_value(ws, monkeypatch, capsys, value, code):
    no_terminal(monkeypatch)
    value_card(ws)
    monkeypatch.setenv('WUWEI_SESSION_ID', 'planner-1')
    before = config(ws)
    assert main('config', 'set', 'repos.0.fast_checks', value, '--from-card', 'D-1') == code
    assert (config(ws) != before) == (code == 0)


@pytest.mark.parametrize('card,reply,option', [('value', 'Defer', 'C'), ('title', 'Keep the current cap', 'C')])
def test_config_set_from_a_card_answered_with_nothing_to_set(ws, monkeypatch, capsys, card, reply, option):
    no_terminal(monkeypatch)
    value_card(ws, reply) if card == 'value' else config_card(ws, reply)
    monkeypatch.setenv('WUWEI_SESSION_ID', 'planner-1')
    before = (ws / '.wuwei/config.toml').read_text()
    capsys.readouterr()
    assert main('config', 'set', '--from-card', 'D-1') == 0, capsys.readouterr().err
    assert 'No config.toml changes' in capsys.readouterr().out
    assert (ws / '.wuwei/config.toml').read_text() == before
    assert decision.answered(state.read_state(ws), 'D-1') == option
    assert not events(ws, 'config.set')


def test_config_set_from_a_title_card_without_key(ws, monkeypatch, capsys):
    no_terminal(monkeypatch)
    config_card(ws)
    monkeypatch.setenv('WUWEI_SESSION_ID', 'planner-1')
    assert main('config', 'set', '--from-card', 'D-1') == 0, capsys.readouterr().err
    assert config(ws)['cap'] == 5


def test_config_set_without_key_or_card_names_both_forms(ws, capsys):
    assert main('config', 'set') == 2
    err = capsys.readouterr().err
    assert 'KEY VALUE' in err and '--from-card D-n' in err


def test_widget_of_a_value_card_prints_the_config_command(ws, capsys):
    value_card(ws, reply=None)
    capsys.readouterr()
    assert main('decision', 'show', 'D-1', '--widget') == 0
    assert json.loads(capsys.readouterr().out)[0]['record'] == 'wuwei config set --from-card D-1'


# #599: the card answer confirms without WUWEI_SESSION_ID in the environment.

def record_text(root, identifier='D-1'):
    return (workspace.day_dir(root) / 'decisions' / f'{identifier}.md').read_text()


def planner_bash(monkeypatch):
    """The planner's Bash call: no session id in the environment, no terminal on stdin."""
    no_terminal(monkeypatch)
    monkeypatch.delenv('WUWEI_SESSION_ID', raising=False)
    monkeypatch.setattr('sys.stdin', io.StringIO())


def test_decide_records_an_asked_card_without_the_session_id(ws, monkeypatch, capsys):
    config_card(ws)
    planner_bash(monkeypatch)
    assert main('decide', 'D-1', 'cap = 5') == 0, capsys.readouterr().err
    assert 'Decided-by: owner' in record_text(ws) and 'in the planner session' in record_text(ws)


def host_prompt(monkeypatch):
    calls = []
    monkeypatch.setattr('wuwei.integrity._host_confirm', lambda digest, **kwargs: calls.append(digest) or True)
    monkeypatch.delenv('WUWEI_SESSION_ID', raising=False)
    monkeypatch.setattr('sys.stdin', Terminal())
    return calls


@pytest.mark.parametrize('reply', [None, 'cap = 5'])
def test_host_terminal_prompts(ws, monkeypatch, capsys, reply):
    config_card(ws, reply)
    calls = host_prompt(monkeypatch)
    assert main('decide', 'D-1', 'A') == 0, capsys.readouterr().err
    assert len(calls) == 1 and 'at the host terminal' in record_text(ws)


def test_config_set_from_card_without_the_session_id(ws, monkeypatch, capsys):
    config_card(ws)
    planner_bash(monkeypatch)
    assert set_from_card() == 0, capsys.readouterr().err
    assert config(ws)['cap'] == 5


def card_of(root, identifier='D-1'):
    return decision.card_hash(identifier, decision.evaluate(record_text(root, identifier))[0])


@pytest.mark.parametrize('case', ['asked', 'edited', 'other hash', 'not asked', 'strict'])
def test_decide_with_card_never_prompts(ws, monkeypatch, capsys, case):
    config_card(ws, None if case == 'not asked' else 'cap = 5')
    card = '000000000000' if case == 'other hash' else card_of(ws)
    if case == 'edited':  # the record changed after its card was asked
        path = workspace.day_dir(ws) / 'decisions/D-1.md'
        path.write_text(path.read_text().replace('Five items build at once.', 'Five items build at once, more memory.'))
    if case == 'strict':
        strict(ws)
    calls = host_prompt(monkeypatch)
    capsys.readouterr()
    code = main('decide', 'D-1', 'A', '--card', card)
    err = capsys.readouterr().err
    assert calls == []
    if case == 'asked':
        assert code == 0 and 'in the planner session' in record_text(ws)
        return
    assert code == 1 and 'Outcome: pending' in record_text(ws)
    assert 'bin/wuwei decision show D-1 --widget' in err
    assert (f'{workspace.owner_cli(ws)} decide D-1 A in a host terminal' in err) is (case == 'strict')


# #831: the Owner step card replaces the host terminal.

OWNER_MERGE = 'bin/wuwei plan set A owner_merge=false'


def test_needs_owner_names_the_card(ws):
    reason = sessions.needs_owner(ws, OWNER_MERGE, 'Release the owner merge hold on A')
    assert f'Owner step: {OWNER_MERGE}' in reason and 'host terminal' not in reason
    card = json.loads(reason[reason.index('{'):])
    assert card['header'] == 'Owner step' and card['record'] == OWNER_MERGE
    assert [option['label'] for option in card['options']] == ['Yes', 'No']


def test_needs_owner_reads_the_recorded_yes(ws):
    from fakes import owner
    assert owner.answer(ws, OWNER_MERGE, reply='No') == (0, '')
    assert owner.answer(ws, 'bin/wuwei plan set B owner_merge=false') == (0, '')
    assert owner.answer(ws, OWNER_MERGE, token='abc') == (0, '')
    assert sessions.needs_owner(ws, OWNER_MERGE, 'x') is not None
    assert owner.answer(ws, OWNER_MERGE) == (0, '')
    assert sessions.needs_owner(ws, OWNER_MERGE, 'x') is None
    assert sessions.needs_owner(ws, OWNER_MERGE, 'x', token='abc') is None
    assert sessions.needs_owner(ws, OWNER_MERGE, 'x', token='abd') is not None


def test_a_seat_answer_records_nothing(ws):
    from fakes import owner
    assert owner.answer(ws, OWNER_MERGE, agent='a1') == (0, '')
    assert sessions.needs_owner(ws, OWNER_MERGE, 'x') is not None


def test_owner_answer_records_without_reading_state(ws):
    from fakes import owner
    path = workspace.day_dir(ws) / 'state.json'
    path.chmod(0o644)
    path.write_text('{')
    assert owner.answer(ws, 'bin/wuwei state recover', token='abc', session='any') == (0, '')
    assert sessions.needs_owner(ws, 'bin/wuwei state recover', 'x', token='abc') is None


def test_owner_answer_counts_under_strict(ws):
    from fakes import owner
    strict(ws)
    assert owner.answer(ws, OWNER_MERGE) == (0, '')
    assert sessions.needs_owner(ws, OWNER_MERGE, 'x') is None


def test_gate_asked_is_reserved(ws):
    assert main('event', 'gate.asked', '{}') == 1


def test_owner_step_question_needs_no_citation(ws):
    from wuwei.guards.decision import check_question
    assert check_question({'cwd': str(ws), 'tool_name': 'AskUserQuestion', 'tool_input': {'questions': [
        {'header': 'Owner step', 'question': f'Owner step: {OWNER_MERGE}'}]}}) == (0, '')


def test_only_a_recorded_gate_asked_row_counts(ws):
    """#831 F1: a note whose payload names gate.asked, or a damaged row, is not an answer."""
    question = f'Owner step: {OWNER_MERGE}'
    card = sessions.owner_card(OWNER_MERGE, 'x')
    topic = sessions.owner_topic(question, card['options'], 'Yes')
    assert main('event', 'note', json.dumps({'via': 'gate.asked', 'topics': [topic]})) == 0
    path = workspace.day_dir(ws) / 'events.jsonl'
    path.chmod(0o644)
    with path.open('a') as stream:
        stream.write(json.dumps({'kind': 'gate.asked', 'payload': {'topics': topic}}) + '\n')
        stream.write(json.dumps({'kind': 'gate.asked', 'payload': None}) + '\n' + '{"kind": "gate.asked"\n')
    assert sessions.needs_owner(ws, OWNER_MERGE, 'x') is not None


def test_the_latest_answer_decides(ws):
    """#831 F4: a later No revokes an earlier Yes on the same card."""
    from fakes import owner
    owner.answer(ws, OWNER_MERGE)
    owner.answer(ws, OWNER_MERGE, reply='No')
    assert sessions.needs_owner(ws, OWNER_MERGE, 'x') is not None
    owner.answer(ws, OWNER_MERGE)
    assert sessions.needs_owner(ws, OWNER_MERGE, 'x') is None


def test_a_swapped_description_does_not_count(ws):
    """#831 F6: the answer binds the options the card printed, not only the question."""
    from fakes import owner
    owner.answer(ws, OWNER_MERGE, detail='something harmless')
    assert sessions.needs_owner(ws, OWNER_MERGE, 'x') is not None
    owner.answer(ws, OWNER_MERGE, detail='x')
    assert sessions.needs_owner(ws, OWNER_MERGE, 'x') is None


def test_only_an_owner_step_question_skips_the_citation(ws):
    from wuwei.guards.decision import check_question
    code, _ = check_question({'cwd': str(ws), 'tool_name': 'AskUserQuestion', 'tool_input': {'questions': [
        {'header': 'Owner step', 'question': 'Shall I merge everything?'}]}})
    assert code == 1


def hook_call(monkeypatch, event, root, tool, inputs, **extra):
    import io
    from types import SimpleNamespace
    from wuwei.commands import hook
    payload = {'session_id': 'planner-1', 'transcript_path': '/dev/null', 'cwd': str(root),
               'hook_event_name': event, 'tool_name': tool, 'tool_input': inputs, **extra}
    monkeypatch.setattr('sys.stdin', io.StringIO(json.dumps(payload)))
    return hook.run(SimpleNamespace(event=event, command='hook'))


def launchers(root):
    """The plugin's own bin/wuwei and the one .wuwei/executable names."""
    from wuwei import integrity
    (root / '.wuwei/executable').write_text('/opt/wuwei/bin/wuwei\n')
    return str(integrity.PLUGIN / 'bin/wuwei'), '/opt/wuwei/bin/wuwei'


def outside_launchers(root, action):
    """#831 D1: forms the pass-throughs refuse: another program named wuwei, the module, a
    relative bin/wuwei outside the plugin, a redirect to a protected file, an environment prefix."""
    plugin = launchers(root)[0]
    state_file = workspace.day_dir(root).relative_to(root) / 'state.json'
    return (f'/tmp/evil/wuwei {action}', f'python3 -m wuwei {action}', f'bin/wuwei {action}',
            f'{plugin} {action} > {state_file}', f'PYTHONPATH=/tmp/evil {plugin} {action}')


def owner_question(command):
    return {'questions': [{key: value for key, value in sessions.owner_card(command, 'x').items() if key != 'record'}]}


def test_a_failed_integrity_verdict_leaves_the_reconfirm_card_reachable(ws, monkeypatch, capsys):
    """#831 F2: the integrity gate lets its own Owner step card and command through."""
    (ws / '.wuwei/integrity').mkdir(exist_ok=True)
    (ws / '.wuwei/integrity/verdict.json').write_text(json.dumps(
        {'exit': 1, 'reason': 'page: plugin integrity: dirty development checkout', 'plugin': None}))
    reconfirm = 'bin/wuwei integrity reconfirm (abc)'
    assert hook_call(monkeypatch, 'PreToolUse', ws, 'AskUserQuestion', owner_question(reconfirm)) == 0
    plugin, recorded = launchers(ws)
    for command in (f'{plugin} integrity reconfirm', f'{recorded} integrity reconfirm',
                    f'{plugin} doctor --fix --apply integrity-reconfirm'):
        assert hook_call(monkeypatch, 'PreToolUse', ws, 'Bash', {'command': command}) == 0, command
    for command in ('ls', f'{plugin} integrity reconfirm; ls', f'{plugin} doctor --fix',
                    *outside_launchers(ws, 'integrity reconfirm')):
        assert hook_call(monkeypatch, 'PreToolUse', ws, 'Bash', {'command': command}) == 2, command
    assert hook_call(monkeypatch, 'PreToolUse', ws, 'AskUserQuestion', owner_question('bin/wuwei state recover')) == 2


def test_a_config_that_does_not_load_is_repaired_in_the_session(ws, monkeypatch, capsys):
    """#831 F3: with a broken config.toml, config set and its Owner step card still run."""
    import tomllib
    from fakes.integrity import seed
    seed(ws)
    (ws / '.wuwei/config.toml').write_text('cap = "five"\n[security]\nposture = "guarded"\n')
    plugin, recorded = launchers(ws)
    assert hook_call(monkeypatch, 'PreToolUse', ws, 'Bash', {'command': 'ls'}) == 2
    for command in (f'{plugin} config set cap 5', f'{recorded} config set cap 5'):
        assert hook_call(monkeypatch, 'PreToolUse', ws, 'Bash', {'command': command}) == 0, command
    for command in outside_launchers(ws, 'config set cap 5'):  # #831 D1: only the launcher, no redirect
        assert hook_call(monkeypatch, 'PreToolUse', ws, 'Bash', {'command': command}) == 2, command
    capsys.readouterr()
    assert main('config', 'set', 'cap', '5') == 1
    err = capsys.readouterr().err
    card, _ = json.JSONDecoder().raw_decode(err[err.index('{"question"'):])
    asked = {'questions': [{key: value for key, value in card.items() if key != 'record'}]}
    assert hook_call(monkeypatch, 'PreToolUse', ws, 'AskUserQuestion', asked) == 0
    assert hook_call(monkeypatch, 'PostToolUse', ws, 'AskUserQuestion', asked,
                     tool_response={'answers': {card['question']: 'Yes'}}) in (0, 2)
    assert main('config', 'set', 'cap', '5') == 0, capsys.readouterr().err
    assert tomllib.loads((ws / '.wuwei/config.toml').read_text())['cap'] == 5


def test_add_repo_card_names_the_full_command(ws, capsys):
    """#831 F8: the card's record is the exact command to run again."""
    from fakes import owner
    args = ['config', 'add-repo', '--name', 'acme/x', '--path', 'x', '--branch', 'main', '--identity', 'A B <a@b.c>']
    assert main(*args) == 1
    err = capsys.readouterr().err
    record = "bin/wuwei config add-repo --name acme/x --path x --branch main --identity 'A B <a@b.c>'"
    assert json.dumps(record) in err
    owner.answer_card(ws, err)
    assert main(*args) == 0 and config(ws)['repos'][0]['name'] == 'acme/x'


def test_state_recover_card_runs_through_the_hooks_with_state_unreadable(ws, monkeypatch, capsys):
    """The reviewer's probe: with today's state.json broken, the card is asked and recorded."""
    from fakes.integrity import seed
    seed(ws)
    path = workspace.day_dir(ws) / 'state.json'
    path.chmod(0o644)
    path.write_text('{broken')
    asked = owner_question('bin/wuwei state recover (abc)')
    card = asked['questions'][0]
    assert hook_call(monkeypatch, 'PreToolUse', ws, 'AskUserQuestion', asked) == 0
    hook_call(monkeypatch, 'PostToolUse', ws, 'AskUserQuestion', asked,
              tool_response={'answers': {card['question']: 'Yes'}})
    assert sessions.needs_owner(ws, 'bin/wuwei state recover', 'x', 'abc') is None


def test_a_forged_note_never_answers_for_the_owner(ws):
    """The reviewer's probe: wuwei event note with the answer's topic is not an answer."""
    command = 'bin/wuwei plan set A-1 owner_merge=false'
    card = sessions.owner_card(command, 'x')
    topic = sessions.owner_topic(card['question'], card['options'], 'Yes')
    assert main('event', 'note', json.dumps({'via': 'gate.asked', 'topics': [topic]})) == 0
    assert sessions.needs_owner(ws, command, 'x') is not None
