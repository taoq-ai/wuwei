"""#529: an answer given on an Ask card is the confirmation of the config write it leads to."""

from argparse import Namespace
from hashlib import sha256
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


# Phase 1: the card answer is recorded.

def test_card_topic_normalises_and_hashes():
    topic = sessions.card_topic('CAP', ' 5 (Recommended) ')
    assert topic == sessions.card_topic('CAP', '5') == 'CAP=' + sha256(b'5').hexdigest()
    assert re.fullmatch(r'CAP=[0-9a-f]{64}', topic)


def test_card_answered_only_for_the_planner_outside_strict(ws, monkeypatch):
    state._write_state(lambda data: data['sessions']['planner-1'].update(
        gate_asked=[sessions.card_topic('CAP', '5')]), ws, reserved=False)
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


# Phase 2: interview cards.

def main(*args):
    from wuwei.__main__ import main as entry
    return entry(list(args))


def interview_card(root, qid, reply):
    """The planner asked the interview row's widget and the owner answered reply."""
    from wuwei import interview
    row = interview.question(qid)
    widget = next(w for w in interview.widgets(root, [], [qid]))
    assert answer(root, row['header'], widget['question'], reply) == (0, '')


def config(root):
    import tomllib
    return tomllib.loads((root / '.wuwei/config.toml').read_text())


def test_questions_with_ids_reprint_answered_rows(ws, capsys):
    (ws / 'widget').mkdir()
    with (ws / '.wuwei/config.toml').open('a') as stream:
        stream.write('[[repos]]\nname = "acme/widget"\npath = "widget"\ndefault_branch = "main"\n')
    earlier = ws / '.wuwei/days/2026-09-27/interview.json'
    earlier.parent.mkdir(parents=True)
    earlier.write_text(json.dumps({'cap': '2'}))
    assert main('calibrate', '--questions') == 0
    assert 'cap' not in [w['id'] for w in json.loads(capsys.readouterr().out)]
    assert main('calibrate', '--questions', 'cap', 'seats') == 0
    widgets = json.loads(capsys.readouterr().out)
    assert [(w['id'], w['header']) for w in widgets] == [('cap', 'At once'), ('seats', 'Agents')]
    assert [w['record'] for w in widgets] == ['wuwei calibrate --answer "cap=<label>"',
                                              'wuwei calibrate --answer "seats=<label>"']


@pytest.mark.parametrize('qid,reply,key,value', [
    ('cap', '5', ('cap',), 5), ('seats', '6', ('host', 'seats'), 6)])
def test_calibrate_answer_writes_the_card_answer(ws, monkeypatch, capsys, qid, reply, key, value):
    no_terminal(monkeypatch)
    interview_card(ws, qid, reply)
    monkeypatch.setenv('WUWEI_SESSION_ID', 'planner-1')
    assert main('calibrate', '--answer', f'{qid}={reply}') == 0, capsys.readouterr().err
    out = capsys.readouterr()
    assert f"replaced: {'.'.join(key)} = {value} (was " in out.out + out.err
    written = config(ws)
    for part in key:
        written = written[part]
    assert written == value
    assert events(ws, 'config.set') == [{'keys': ['.'.join(key)], 'card': qid}]
    assert json.loads((workspace.day_dir(ws) / 'interview.json').read_text())[qid] == reply
    assert 'Next:' not in capsys.readouterr().out


@pytest.mark.parametrize('case', ['other answer', 'strict', 'no session'])
def test_calibrate_answer_without_the_card_answer_keeps_promote(ws, monkeypatch, capsys, case):
    no_terminal(monkeypatch)
    interview_card(ws, 'cap', '3' if case == 'other answer' else '5')
    if case == 'strict':
        strict(ws)
    if case != 'no session':
        monkeypatch.setenv('WUWEI_SESSION_ID', 'planner-1')
    before = (ws / '.wuwei/config.toml').read_text()
    assert main('calibrate', '--answer', 'cap=5') == 0
    assert (ws / '.wuwei/config.toml').read_text() == before
    assert json.loads((workspace.day_dir(ws) / 'interview.json').read_text())['cap'] == '5'
    assert 'config.set' not in [json.loads(line)['kind'] for line in
                                (workspace.day_dir(ws) / 'events.jsonl').read_text().splitlines()]
    assert 'bin/wuwei config promote' in capsys.readouterr().out


def test_unrelated_gate_question_with_the_header_confirms_nothing(ws, monkeypatch, capsys):
    no_terminal(monkeypatch)
    text = decision.gate(ws) + 'Should the deploy seat keep watching the logs today?'
    assert answer(ws, 'Autonomy', text, 'Autonomous') == (0, '')
    monkeypatch.setenv('WUWEI_SESSION_ID', 'planner-1')
    before = (ws / '.wuwei/config.toml').read_text()
    assert main('calibrate', '--answer', 'autonomy=Autonomous') == 0
    assert (ws / '.wuwei/config.toml').read_text() == before
    assert 'bin/wuwei config promote' in capsys.readouterr().out


@pytest.mark.parametrize('reply,values', [
    ('Autonomous', ('observe', 'send', 'today', 'auto', 'autonomous')),
    ('Supervised', ('guarded', 'ask', 'ask', 'card', 'supervised'))])
def test_one_autonomy_answer_writes_five_keys(ws, monkeypatch, capsys, reply, values):
    # #530 acceptance 1: one card answer writes the five keys through the #529 path.
    no_terminal(monkeypatch)
    interview_card(ws, 'autonomy', reply)
    monkeypatch.setenv('WUWEI_SESSION_ID', 'planner-1')
    assert main('calibrate', '--answer', f'autonomy={reply}') == 0, capsys.readouterr().err
    written = config(ws)
    assert (written['security']['posture'], written['outbound']['default_tier'], written['merge']['default_tier'],
            written['outbound']['learn'], written['autonomy']['mode']) == values
    assert not written.get('guards', {}).get('shadow_since')
    assert events(ws, 'config.set') == [{'keys': ['security.posture', 'outbound.default_tier', 'merge.default_tier',
                                                  'outbound.learn', 'autonomy.mode'], 'card': 'autonomy'}]
    assert 'Next:' not in capsys.readouterr().out


def test_allowlist_card_writes_exactly_the_proposed_rules(ws, monkeypatch, capsys):
    # #530 acceptance 3: the answered card writes settings.local.json and no config key.
    from wuwei.commands import init
    no_terminal(monkeypatch)
    (ws / '.wuwei/executable').write_text('bin/wuwei\n')
    before = (ws / '.wuwei/config.toml').read_text()
    interview_card(ws, 'allowlist', 'Allow')
    monkeypatch.setenv('WUWEI_SESSION_ID', 'planner-1')
    assert main('calibrate', '--answer', 'allowlist=Allow') == 0, capsys.readouterr().err
    rules = init.allow_rules(workspace.load_config(ws), 'bin/wuwei')
    assert json.loads((ws / '.claude/settings.local.json').read_text()) == {'permissions': {'allow': rules}}
    out = capsys.readouterr().out
    assert all(f'Wrote .claude/settings.local.json: {rule}' in out for rule in rules)
    assert 'config promote' not in out and (ws / '.wuwei/config.toml').read_text() == before
    assert 'config.set' not in [json.loads(line)['kind'] for line in
                                (workspace.day_dir(ws) / 'events.jsonl').read_text().splitlines()]


@pytest.mark.parametrize('case', ['not now', 'no card', 'strict'])
def test_allowlist_without_the_card_answer_writes_nothing(ws, monkeypatch, capsys, case):
    no_terminal(monkeypatch)
    (ws / '.wuwei/executable').write_text('bin/wuwei\n')
    reply = 'Not now' if case == 'not now' else 'Allow'
    if case != 'no card':
        interview_card(ws, 'allowlist', reply)
    if case == 'strict':
        strict(ws)
    monkeypatch.setenv('WUWEI_SESSION_ID', 'planner-1')
    assert main('calibrate', '--answer', f'allowlist={reply}') == 0, capsys.readouterr().err
    assert not (ws / '.claude/settings.local.json').exists()
    out = capsys.readouterr().out
    assert ('Next: run bin/wuwei calibrate --interview allowlist in a host terminal' in out) is (reply == 'Allow')
    assert 'config promote' not in out


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
    from wuwei.commands.setup import assignment
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
    assert json.loads(capsys.readouterr().out)[0]['record'] == 'wuwei decide D-2 "<label>"'


# Phase 4: strict keeps the host terminal.

def test_strict_session_names_the_host_terminal(ws, monkeypatch, capsys):
    no_terminal(monkeypatch)
    config_card(ws)
    strict(ws)
    before = (ws / '.wuwei/config.toml').read_text()
    monkeypatch.setenv('WUWEI_SESSION_ID', 'planner-1')
    capsys.readouterr()
    assert set_from_card() == 1
    assert 'bin/wuwei config set cap 5' in capsys.readouterr().err
    assert (ws / '.wuwei/config.toml').read_text() == before


def test_strict_host_terminal_ignores_the_card_and_prompts(ws, monkeypatch):
    from wuwei.commands.setup import set_value
    config_card(ws)
    strict(ws)
    calls = []
    args = Namespace(key='cap', value='5', replace=False, from_card='D-1')
    assert set_value(args, confirm=lambda digest, **kwargs: calls.append(digest) or True) == 0
    assert len(calls) == 1 and config(ws)['cap'] == 5
    assert not state.read_state(ws).get('decision_outcomes')


# Phase 5: no empty answer in a session.

@pytest.mark.parametrize('posture,key,value,named', [
    ('guarded', 'cap', '5', 'bin/wuwei calibrate --questions cap'),
    ('guarded', 'owner.name', '"Pat"', '--from-card D-n'),
    ('strict', 'cap', '5', 'bin/wuwei config set cap 5'),
])
def test_config_set_in_a_session_without_a_card_names_the_card(ws, monkeypatch, capsys, posture, key, value, named):
    no_terminal(monkeypatch)
    if posture == 'strict':
        strict(ws)
    before = (ws / '.wuwei/config.toml').read_text()
    monkeypatch.setenv('WUWEI_SESSION_ID', 'planner-1')
    assert main('config', 'set', key, value) == 1
    err = capsys.readouterr().err
    assert named in err and 'empty answer' not in err and 'run it again' not in err
    assert (ws / '.wuwei/config.toml').read_text() == before


def test_config_set_in_a_host_terminal_prompts_as_today(ws):
    from wuwei.commands.setup import set_value
    calls = []
    args = Namespace(key='cap', value='5', replace=False)
    assert set_value(args, confirm=lambda digest, **kwargs: calls.append(digest) or True) == 0
    assert len(calls) == 1 and config(ws)['cap'] == 5


# Phase 4: the hook lets the planner run the card's record command.

def hook(root, command, **extra):
    from wuwei.guards.protect_state import check_bash
    return check_bash({'cwd': str(root), 'session_id': 'planner-1', 'tool_input': {'command': command}, **extra})


def test_hook_passes_config_set_from_an_asked_card(ws):
    config_card(ws)
    for command in ('bin/wuwei config set cap 5 --from-card D-1', 'bin/wuwei config set cap 5 --from-card=D-1',
                    "bin/wuwei config set outbound.default_tier '\"ask\"' --from-card D-1"):
        assert hook(ws, command) == (0, ''), command
    for command in ('bin/wuwei config set cap 5', 'bin/wuwei config set cap 5 --from-card D-2',
                    'echo D-1 | xargs bin/wuwei config set cap 5 --from-card'):
        assert hook(ws, command)[0] in (1, 2), command
    code, reason = hook(ws, 'bin/wuwei config set cap 5 --from-card D-1', agent_id='a1')
    assert code == 1 and 'calibrate --questions' in reason
    assert hook(ws, 'bin/wuwei config set cap 5 --from-card D-1', session_id='other')[0] == 1


def test_hook_config_set_below_strict_keeps_its_reason_without_a_command(ws):
    """#661: below strict the planner gets the card-first table reason, no command to paste."""
    from wuwei.guards.protect_state import _OWNER_ACTIONS
    config_card(ws)
    assert hook(ws, 'bin/wuwei config set cap 5') == (1, _OWNER_ACTIONS[('config', 'set')])

def test_hook_under_strict_prints_the_host_terminal_command(ws):
    config_card(ws)
    strict(ws)
    code, reason = hook(ws, 'bin/wuwei config set cap 5 --from-card D-1')
    assert code == 1
    assert reason.endswith('Run it in a host terminal: bin/wuwei config set cap 5 --from-card D-1')


# Phase 6: config.set is a CLI-only, silent event kind.

def test_config_set_event_is_reserved_and_silent(ws, capsys):
    from wuwei.signal import classify
    assert main('event', 'config.set', '{}') == 1
    assert 'wuwei config set --from-card or wuwei calibrate --answer' in capsys.readouterr().err
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


def test_session_hint_names_value_rows_and_the_previous_line(ws, monkeypatch, capsys):
    no_terminal(monkeypatch)
    monkeypatch.setenv('WUWEI_SESSION_ID', 'planner-1')
    assert main('config', 'set', 'owner.name', '"Pat"') == 1
    err = capsys.readouterr().err
    assert 'Value:' in err and 'Previous: owner.name = ""' in err
    assert 'bin/wuwei config set --from-card D-n' in err


def test_hook_passes_the_short_form_from_the_planner_only(ws):
    value_card(ws)
    assert hook(ws, 'bin/wuwei config set --from-card D-1') == (0, '')
    assert hook(ws, 'bin/wuwei config set --from-card D-1', agent_id='a1')[0] == 1


# #600: calibrate --questions proposes the fast checks of a repository with none configured.

def paper(root, mode='autonomous', makefile='test:\n\ttrue\n'):
    (root / '.wuwei/config.toml').write_text(
        f'[security]\nposture = "observe"\n[autonomy]\nmode = "{mode}"\n' + PAPER)
    (root / 'paper').mkdir(exist_ok=True)
    if makefile:
        (root / 'paper/Makefile').write_text(makefile)


def proposed(capsys, *ids):
    assert main('calibrate', '--questions', *ids) == 0
    out = capsys.readouterr()
    return json.loads(out.out), out.err


def test_calibrate_takes_the_detected_checks_under_mandate(ws, capsys):
    paper(ws)
    widgets, err = proposed(capsys)
    assert 'calibrate: D-1 taken under mandate (Routine): repos.0.fast_checks = ["make test"]' in err
    assert 'replaced: repos.0.fast_checks = ["make test"] (was [])' in err
    assert 'D-1' not in [widget.get('header') for widget in widgets]
    assert config(ws)['repos'][0]['fast_checks'] == ['make test']
    assert state.read_state(ws)['decision_outcomes']['D-1']['decided_by'] == 'mandate'
    text = (workspace.day_dir(ws) / 'decisions/D-1.md').read_text()
    assert 'Outcome: A' in text and 'Decided-by: mandate' in text  # the digest lists it
    assert events(ws, 'config.set') == [{'keys': ['repos.0.fast_checks'], 'card': 'D-1'}]


def test_calibrate_records_none_with_the_reason_and_asks_once(ws, capsys):
    from wuwei import calibrate
    paper(ws, makefile=None)
    before = (ws / '.wuwei/config.toml').read_text()
    _, err = proposed(capsys)
    assert 'repos.0.fast_checks = []' in err
    assert (ws / '.wuwei/config.toml').read_text() == before
    assert calibrate.NOTHING in (workspace.day_dir(ws) / 'decisions/D-1.md').read_text()
    proposed(capsys)
    assert not (workspace.day_dir(ws) / 'decisions/D-2.md').exists()


def test_calibrate_asks_the_card_under_supervised(ws, capsys):
    paper(ws, mode='supervised')
    before = (ws / '.wuwei/config.toml').read_text()
    widgets, _ = proposed(capsys)
    card = next(widget for widget in widgets if widget.get('header') == 'D-1')
    assert card['record'] == 'wuwei config set --from-card D-1'
    assert card['options'][0]['label'] == 'Detected (Recommended)'
    assert 'D-1' in state.read_state(ws)['decision_routes']
    assert (ws / '.wuwei/config.toml').read_text() == before


def test_calibrate_with_question_ids_or_no_checkout_writes_no_record(ws, capsys):
    paper(ws)
    proposed(capsys, 'cap')
    assert not (workspace.day_dir(ws) / 'decisions').exists()
    (ws / 'paper/Makefile').unlink()
    (ws / 'paper').rmdir()
    widgets, err = proposed(capsys)
    assert 'acme/paper' in err and 'paper' in err and widgets
    assert not (workspace.day_dir(ws) / 'decisions').exists()
