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
    topic = sessions.owner_topic(question, 'Yes')
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
    reconfirm = 'bin/wuwei doctor --fix --apply integrity-reconfirm (abc)'
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
    topic = sessions.owner_topic(card['question'], 'Yes')
    state.append_event('note', {'via': 'gate.asked', 'topics': [topic]}, ws)
    assert sessions.needs_owner(ws, command, 'x') is not None


# #924, #856: the card binds by its question; the owner's terminal applies.

def approvals(root):
    path = workspace.day_dir(root) / 'events.jsonl'
    return [json.loads(line)['payload']['command'] for line in path.read_text().splitlines()
            if json.loads(line)['kind'] == 'owner.approved']


def printed_card(err):
    card, _ = json.JSONDecoder().raw_decode(err[err.index('{"question"'):])
    return card


def test_issue_924_a_yes_on_the_shortened_field_card_applies_when_run_again(ws, capsys, monkeypatch):
    """#924 root cause: the planner asked the card with the Yes diff shortened (no hunk header, no
    context) and the owner answered Yes; the Yes was bound to the options as asked, so the
    owner's terminal run printed the same refusal. The answer binds the question now."""
    from fakes import owner
    for name in ('CLAUDECODE', 'WUWEI_SESSION_ID', 'WUWEI_SEAT_ROLE'):
        monkeypatch.delenv(name, raising=False)
    args = ('config', 'set', 'outward.allow', '["mcp__notion__notion-update-page"]', '--add')
    assert main(*args) == 1
    card = printed_card(capsys.readouterr().err)
    card['options'][0]['description'] = 'Apply the change:\n-allow = []\n+allow = ["mcp__notion__notion-update-page"]'
    owner._record(ws, card, 'Yes', 'planner-1', None)
    assert main(*args) == 0, capsys.readouterr().err  # the session, or the owner's own shell
    assert config(ws)['outward']['allow'] == ['mcp__notion__notion-update-page']
    assert len(approvals(ws)) == 1


def test_issue_856_a_shortened_option_counts(ws):
    """#856 (supersedes #831 F6 at the owner's call): the question binds, the options are for review."""
    from fakes import owner
    owner.answer(ws, OWNER_MERGE, detail='shortened')
    assert sessions.needs_owner(ws, OWNER_MERGE, 'x') is None


def test_issue_856_adjacent_keys_answer_in_one_round(ws, capsys):
    """#856 field comment: three keys whose hunks share context, answered in one round."""
    from fakes import owner
    from pathlib import Path
    template = Path(__file__).resolve().parents[1] / 'templates/workspace/config.toml'
    (ws / '.wuwei/config.toml').write_text(template.read_text())
    sets = [('codex.command', '["node", "c.mjs"]'), ('codex.timeout_seconds', '600'),
            ('gates.second_opinion', '"codex:gpt-5"')]
    refusals = []
    for key, value in sets:
        assert main('config', 'set', key, value) == 1
        refusals.append(capsys.readouterr().err)
    for err in refusals:
        owner.answer_card(ws, err)
    for key, value in sets:
        assert main('config', 'set', key, value) == 0, capsys.readouterr().err
    assert config(ws)['codex'] == {'command': ['node', 'c.mjs'], 'timeout_seconds': 600}
    assert config(ws)['gates']['second_opinion'] == 'codex:gpt-5'


def test_issue_856_a_reworded_question_names_the_mismatch(ws):
    from fakes import owner
    card = sessions.owner_card(OWNER_MERGE, 'x', 'abc123def456')
    assert 'did not match' not in sessions.needs_owner(ws, OWNER_MERGE, 'x', 'abc123def456')
    card['question'] = 'Owner step: release the merge hold on A (abc123def456)'
    owner._record(ws, card, 'Yes', 'planner-1', None)
    reason = sessions.needs_owner(ws, OWNER_MERGE, 'x', 'abc123def456')
    assert 'a card for this step was answered but did not match; ask it verbatim' in reason
    assert approvals(ws) == []


@pytest.mark.parametrize('context', [' The merge needs your approval.', '\nThe merge needs your approval.'])
def test_issue_940_extended_question_binds_and_is_spent_once(ws, context):
    from fakes import owner
    command, token = 'bin/wuwei build next TIN-790-MERGE-MAIN', '15924e1a464b'
    card = sessions.owner_card(command, 'x', token)
    card['question'] += context
    owner._record(ws, card, 'Yes', 'planner-1', 'seat-1')
    assert sessions.owner_answer(ws, command, token) is None
    owner._record(ws, card, 'Yes', 'planner-1', None)
    assert sessions.owner_answer(ws, command, token) == 'Yes'
    assert sessions.needs_owner(ws, command, 'x', token) is None
    assert sessions.owner_answer(ws, command, token) is None
    assert sessions.needs_owner(ws, command, 'x', token) is not None
    assert len(approvals(ws)) == 1
    for reply, expected in [('Yes', 'Yes'), ('No', 'No'), ('Yes', 'Yes'), ('Later', None)]:
        owner._record(ws, card, reply, 'planner-1', None)
        assert sessions.owner_answer(ws, command, token) == expected
    assert context.strip() not in (workspace.day_dir(ws) / 'events.jsonl').read_text()


@pytest.mark.parametrize('changed', ['missing-token', 'wrong-token', 'wrong-command'])
def test_issue_940_mismatch_names_the_shared_identity(ws, changed):
    from fakes import owner
    command, token = 'bin/wuwei build next TIN-790-MERGE-MAIN', '15924e1a464b'
    card = sessions.owner_card(command, 'x', token)
    if changed == 'missing-token':
        card['question'] = f'Owner step: {command}'
    elif changed == 'wrong-token':
        card['question'] = card['question'].replace(token, '000000000000') + ' Context.'
    else:
        card['question'] = card['question'].replace('build next', 'dispatch next') + ' Context.'
    owner._record(ws, card, 'Yes', 'planner-1', None)
    reason = sessions.needs_owner(ws, command, 'x', token)
    assert 'did not match' in reason
    assert ('answered card matched token' if changed == 'wrong-command'
            else 'answered card matched command') in reason
    assert command in reason and token in reason
    assert approvals(ws) == []


@pytest.mark.parametrize('token,context', [('', ''), ('abc123def456', ''), ('abc123def456', ' Context.')])
def test_issue_940_token_text_inside_a_quoted_command_is_not_the_card_token(ws, token, context):
    from fakes import owner
    command = "bin/wuwei plan set A spec=skipped --reason 'Same as approved card (15924e1a464b)'"
    card = sessions.owner_card(command, 'x', token)
    card['question'] += context
    owner._record(ws, card, 'Yes', 'planner-1', None)
    assert sessions.owner_answer(ws, command, token) == 'Yes'
    assert sessions.needs_owner(ws, command, 'x', token) is None


@pytest.mark.parametrize('replies', [('Yes', 'No'), ('No', 'Yes')])
def test_issue_940_f1_contradictory_replies_do_not_approve(ws, replies):
    from fakes import owner
    from wuwei.guards.answers import record_gate
    token = '15924e1a464b'
    owner.answer(ws, OWNER_MERGE, token)
    card = sessions.owner_card(OWNER_MERGE, 'x', token)
    questions = [card, {**card, 'question': card['question'] + ' Context.'}]
    assert record_gate({'cwd': str(ws), 'session_id': 'planner-1', 'tool_name': 'AskUserQuestion',
                        'tool_input': {'questions': questions},
                        'tool_response': {'answers': {q['question']: reply for q, reply in zip(questions, replies)}}}) == (0, '')
    assert sessions.owner_answer(ws, OWNER_MERGE, token) is None
    assert sessions.needs_owner(ws, OWNER_MERGE, 'x', token) is not None
    assert approvals(ws) == []
    owner.answer(ws, OWNER_MERGE, token)
    assert sessions.needs_owner(ws, OWNER_MERGE, 'x', token) is None


def test_issue_940_f3_spent_answer_is_not_a_mismatch(ws):
    from fakes import owner
    old_token, new_token = 'aaaaaaaaaaaa', '15924e1a464b'
    owner.answer(ws, OWNER_MERGE, old_token)
    assert sessions.needs_owner(ws, OWNER_MERGE, 'x', old_token) is None
    assert 'did not match' not in sessions.needs_owner(ws, OWNER_MERGE, 'x', new_token)
    owner.answer(ws, OWNER_MERGE, old_token)
    assert 'did not match' in sessions.needs_owner(ws, OWNER_MERGE, 'x', new_token)
    other = 'bin/wuwei build next B'
    owner.answer(ws, other, old_token)
    assert sessions.needs_owner(ws, other, 'x', old_token) is None
    assert 'did not match' in sessions.needs_owner(ws, OWNER_MERGE, 'x', new_token)


@pytest.mark.parametrize('token', ['', '15924e1a464b'])
def test_issue_940_f2_tokenless_first_line_is_only_a_mismatch_hint(ws, token):
    from fakes import owner
    card = sessions.owner_card(OWNER_MERGE, 'x')
    card['question'] += '\nThe merge needs approval.'
    owner._record(ws, card, 'Yes', 'planner-1', None)
    assert sessions.owner_answer(ws, OWNER_MERGE, token) is None
    assert 'answered card matched command' in sessions.needs_owner(ws, OWNER_MERGE, 'x', token)
    assert approvals(ws) == []


def test_every_refusal_says_where_the_answered_command_applies(ws):
    reason = sessions.needs_owner(ws, OWNER_MERGE, 'Release the owner merge hold on A')
    assert 'once it is answered Yes, the same command applies from here or from your own terminal' in reason
    assert '\n' not in reason and 'config.toml by hand' not in reason
    assert 'edit .wuwei/config.toml by hand' in sessions.needs_owner(ws, 'bin/wuwei config set cap 5', 'x')


def test_a_yes_is_spent_once(ws):
    """#856 F2: an owner.approved row after the Yes spends it; a rerun asks again."""
    from fakes import owner
    owner.answer(ws, OWNER_MERGE)
    assert sessions.needs_owner(ws, OWNER_MERGE, 'x') is None
    assert sessions.owner_answer(ws, OWNER_MERGE) is None
    assert sessions.needs_owner(ws, OWNER_MERGE, 'x') is not None
    owner.answer(ws, OWNER_MERGE)
    assert sessions.needs_owner(ws, OWNER_MERGE, 'x') is None
    assert len(approvals(ws)) == 2


def test_a_config_yes_never_undoes_a_later_owner_change(ws, capsys):
    """#856 F2 scenario: an old Yes does not apply the same command again after it applied."""
    from fakes import owner
    args = ('config', 'set', 'cap', '5')
    assert main(*args) == 1
    owner.answer_card(ws, capsys.readouterr().err)
    assert main(*args) == 0 and config(ws)['cap'] == 5
    (ws / '.wuwei/config.toml').write_text('cap = 6\n')
    assert main(*args) == 1 and config(ws)['cap'] == 6


def test_issue_856_a_reworded_card_without_a_token_names_the_mismatch(ws):
    """#856 F4: the hint matches the command part of the question, token or not."""
    from fakes import owner
    command = 'bin/wuwei plan park A --reason x'
    card = sessions.owner_card(command, 'x')
    card['question'] = f'Owner step: {command} (park it)'
    owner._record(ws, card, 'Yes', 'planner-1', None)
    assert 'did not match; ask it verbatim' in sessions.needs_owner(ws, command, 'x')
    card = sessions.owner_card(OWNER_MERGE, 'x', 'abc123def456')
    card['question'] = f'Owner step: {OWNER_MERGE}'  # the token dropped
    assert 'did not match' not in sessions.needs_owner(ws, OWNER_MERGE, 'x', 'abc123def456')
    owner._record(ws, card, 'Yes', 'planner-1', None)
    assert 'did not match; ask it verbatim' in sessions.needs_owner(ws, OWNER_MERGE, 'x', 'abc123def456')


def test_a_pty_wrapped_run_without_an_answered_card_is_refused(ws):
    """#924 review F1: a session that wraps the command in a pseudo-terminal, strips its
    environment and types y gets the refusal; nothing reads a terminal answer."""
    import os
    import subprocess
    import sys
    from pathlib import Path
    master, slave = os.openpty()
    env = {name: value for name, value in os.environ.items()
           if not name.startswith(('CLAUDE', 'CODEX')) and name not in ('WUWEI_SESSION_ID', 'WUWEI_SEAT_ROLE')}
    env.update(PYTHONPATH=str(Path(__file__).resolve().parents[1] / 'cli'), WUWEI_WORKSPACE=str(ws))
    child = subprocess.Popen([sys.executable, '-m', 'wuwei', 'config', 'set', 'cap', '7'], cwd=ws, env=env,
                             stdin=slave, stdout=slave, stderr=slave)
    os.close(slave)
    os.write(master, b'y\n')
    out = b''
    while True:
        try:
            chunk = os.read(master, 4096)
        except OSError:
            break
        if not chunk:
            break
        out += chunk
    os.close(master)
    assert child.wait(timeout=60) == 1 and b'waits for the owner' in out
    assert 'cap' not in config(ws) and approvals(ws) == []
