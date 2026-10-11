"""#831: the owner answers an Owner step card in the session; the command reads the answer."""

from hashlib import sha256
import json
import re

import pytest

from wuwei import sessions, state, workspace


@pytest.fixture
def ws(tmp_path, monkeypatch):
    from wuwei import plan
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T12:00:00+00:00')
    root = tmp_path / 'workspace'
    (root / '.wuwei').mkdir(parents=True)
    (root / '.wuwei/config.toml').write_text('')
    workspace.day_dir(root).mkdir(parents=True)
    (workspace.day_dir(root) / 'plan.md').write_text('# Morning plan\n')
    plan.session('planner-1', root)
    monkeypatch.chdir(root)
    return root


def test_card_topic_normalises_and_hashes():
    topic = sessions.card_topic('CAP', ' 5 (Recommended) ')
    assert topic == sessions.card_topic('CAP', '5') == 'CAP=' + sha256(b'5').hexdigest()
    assert re.fullmatch(r'CAP=[0-9a-f]{64}', topic)


def main(*args):
    from wuwei.__main__ import main as entry
    return entry(list(args))


def config(root):
    import tomllib
    return tomllib.loads((root / '.wuwei/config.toml').read_text())


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


def test_owner_answer_counts_with_enforce_off(ws):
    from fakes import owner
    (ws / '.wuwei/config.toml').write_text('[guards]\nenforce = false\n')
    assert owner.answer(ws, OWNER_MERGE) == (0, '')
    assert sessions.needs_owner(ws, OWNER_MERGE, 'x') is None


def test_only_a_recorded_gate_asked_row_counts(ws):
    """#831 F1: a note whose payload names gate.asked, or a damaged row, is not an answer."""
    question = f'Owner step: {OWNER_MERGE}'
    card = sessions.owner_card(OWNER_MERGE, 'x')
    topic = sessions.owner_topic(question, card['options'], 'Yes')
    state.append_event('note', {'via': 'gate.asked', 'topics': [topic]}, ws)
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


def test_no_question_is_refused_for_a_missing_record(ws, monkeypatch):
    """Part 14: an Owner step card, or any other question, asks without a decision record."""
    from fakes.integrity import seed
    seed(ws)
    for text in (f'Owner step: {OWNER_MERGE}', 'Shall I merge everything?'):
        inputs = {'questions': [{'header': 'Owner step', 'question': text}]}
        assert hook_call(monkeypatch, 'PreToolUse', ws, 'AskUserQuestion', inputs) == 0


def test_a_failed_integrity_verdict_leaves_the_reconfirm_card_reachable(ws, monkeypatch, capsys):
    """#831 F2, #839: integrity refuses no tool call; its Owner step card and command run."""
    (ws / '.wuwei/integrity').mkdir(exist_ok=True)
    (ws / '.wuwei/integrity/verdict.json').write_text(json.dumps(
        {'exit': 1, 'reason': 'page: plugin integrity: dirty development checkout', 'plugin': None}))
    reconfirm = 'bin/wuwei integrity reconfirm (abc)'
    assert hook_call(monkeypatch, 'PreToolUse', ws, 'AskUserQuestion', owner_question(reconfirm)) == 0
    plugin, recorded = launchers(ws)
    for command in (f'{plugin} integrity reconfirm', f'{recorded} integrity reconfirm',
                    f'{plugin} doctor --fix --apply integrity-reconfirm', 'ls'):
        assert hook_call(monkeypatch, 'PreToolUse', ws, 'Bash', {'command': command}) == 0, command


def test_a_config_that_does_not_load_is_repaired_in_the_session(ws, monkeypatch, capsys):
    """#831 F3: with a broken config.toml, config set and its Owner step card still run."""
    import tomllib
    from fakes.integrity import seed
    seed(ws)
    (ws / '.wuwei/config.toml').write_text('cap = "five"\n[guards]\nenforce = true\n')
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
    """The reviewer's probe: a note with the answer's topic is not an answer."""
    command = 'bin/wuwei plan set A-1 owner_merge=false'
    card = sessions.owner_card(command, 'x')
    topic = sessions.owner_topic(card['question'], card['options'], 'Yes')
    state.append_event('note', {'via': 'gate.asked', 'topics': [topic]}, ws)
    assert sessions.needs_owner(ws, command, 'x') is not None
