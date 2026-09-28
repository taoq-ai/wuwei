"""Decision evaluation, scoped hook checks and command outcomes, in process."""

import io
import json

import pytest


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
Reversibility: two-way
Blast radius: own branch
Pre-mortem: Regression returns.
Revisit: Regression returns.
Decided-by: seat
Outcome: pending
'''


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T12:00:00+00:00')
    root = tmp_path / 'workspace'
    (root / '.wuwei').mkdir(parents=True)
    (root / '.wuwei/config.toml').write_text('')
    return root


def save(root, text=VALID, name='D-3.md'):
    from wuwei.workspace import day_dir
    path = day_dir(root) / 'decisions' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if text is not None:
        path.write_text(text)
    return path


def events(root):
    from wuwei.workspace import day_dir
    return [json.loads(line) for line in (day_dir(root) / 'events.jsonl').read_text().splitlines()]


@pytest.mark.parametrize('old,new,reason', [
    ('Recommendation: A', 'Recommendation: B', 'B (30)'),
    ('Recommendation: A', 'Recommendation: C', 'Recommendation'),
    ('| Safe | pass | pass |', '| Safe | fail | pass |', 'must'),
    ('| Safe | pass | pass |', '| Safe | fail | fail |', 'passing'),
    ('| Safe | pass | pass |', '| Safe | yes | pass |', 'pass/fail'),
    ('| B | Defer until tomorrow |\n', '', 'two options'),
    ('Defer until tomorrow', 'Another fix', 'Do nothing or Defer'),
    ('| B | Defer until tomorrow |', '| A | Defer until tomorrow |', 'duplicate'),
    ('| 10 | 8 | 2 |', '| 11 | 8 | 2 |', 'weight'),
    ('| 10 | 8 | 2 |', '| 0 | 8 | 2 |', 'weight'),
    ('| 10 | 8 | 2 |', '| 10 | 11 | 2 |', 'score'),
    ('| 10 | 8 | 2 |', '| 10 | -1 | 2 |', 'score'),
    ('| 10 | 8 | 2 |', '| 10 | NaN | 2 |', 'score'),
    ('| 10 | 8 | 2 |', '| 10 | 8 | |', 'cell'),
    ('| Criterion | A | B |', '| Criterion | A | C |', 'columns'),
    ('Confidence: high', 'Confidence: certain', 'Confidence'),
    ('Decided-by: seat', 'Decided-by: anybody', 'Decided-by'),
    ('Reversibility: two-way', 'Reversibility: maybe', 'Reversibility'),
    ('Outcome: pending', 'Outcome: pending\nOutcome: done', 'duplicate'),
])
def test_lint_findings(old, new, reason):
    from wuwei.decision import lint
    code, message = lint(VALID.replace(old, new))
    assert code == 1
    assert reason in message
    if new == 'Recommendation: B':
        assert 'A (86)' in message


@pytest.mark.parametrize('field', ['Question', 'Context', 'Options', 'Musts', 'Wants',
    'Recommendation', 'Confidence', 'Reversibility', 'Blast radius', 'Pre-mortem',
    'Revisit', 'Decided-by', 'Outcome'])
def test_missing_fields(field):
    from wuwei.decision import lint
    code, message = lint(VALID.replace(field + ':', 'Omitted:'))
    assert code == 1 and field in message


@pytest.mark.parametrize('text', [VALID, VALID.replace('Defer until tomorrow', 'Do nothing'),
    VALID.replace('| 8 | 2 |', '| 2 | 2 |').replace('| 3 | 5 |', '| 5 | 5 |'),
    VALID.replace('| Safe | pass | pass |', '| Safe | fail | pass |').replace('Recommendation: A', 'Recommendation: B'),
    VALID.replace('Question:', '**Question:**'), VALID.replace('Reversibility: two-way', 'Reversibility: unsure')])
def test_valid_evaluation(text):
    from wuwei.decision import lint
    assert lint(text)[0] == 0


@pytest.mark.parametrize('wrap', [lambda s: '```\n' + s + '```',
    lambda s: '<!--\n' + s + '-->', lambda s: '\n'.join('> ' + line for line in s.splitlines())])
def test_examples_do_not_supply_fields(wrap):
    from wuwei.decision import lint
    assert lint(wrap(VALID))[0] == 1


@pytest.mark.parametrize('text,code', [(VALID, 0), ('Question: bad', 1), (None, 2)])
def test_file_and_cli_exits(ws, capsys, text, code):
    from wuwei.__main__ import main
    path = save(ws, text)
    assert main(['decision', 'lint', str(path)]) == code
    if code:
        assert events(ws)[-1]['kind'] == 'decision.rejected'
        assert events(ws)[-1]['payload']['reasons']


def test_unreadable_and_event_failure(ws, monkeypatch):
    from wuwei.decision import lint_file
    from wuwei import state
    path = save(ws)
    path.write_bytes(b'\xff')
    assert lint_file(path)[0] == 2
    def fail(*args, **kwargs):
        raise OSError('event unavailable')
    monkeypatch.setattr(state, 'append_event', fail)
    code, message = lint_file(path)
    assert code == 2 and 'event unavailable' in message


def write_payload(cwd, path, tool='Write'):
    return {'cwd': str(cwd), 'tool_name': tool, 'tool_input': {
        'notebook_path' if tool == 'NotebookEdit' else 'file_path': str(path)}}


@pytest.mark.parametrize('tool', ['Write', 'Edit', 'MultiEdit', 'NotebookEdit'])
@pytest.mark.parametrize('text,code', [(VALID, 0), ('Question: bad', 1), (None, 2)])
def test_write_guard(ws, tool, text, code):
    from wuwei.guards.decision import check_write
    path = save(ws, text)
    assert check_write(write_payload(ws, path, tool))[0] == code
    if code:
        assert events(ws)[-1]['kind'] == 'decision.rejected'


@pytest.mark.parametrize('command', ['cat > {path}', 'env X=1 sh -c "cat > {path}"',
    'command tee {path}', 'exec tee {path}', '(cat > {path})',
    'python script.py {path}', 'cd . && cat > {path}'])
def test_bash_scan(ws, command):
    from wuwei.guards.decision import check_write
    path = save(ws, 'Question: bad')
    payload = {'cwd': str(ws), 'tool_name': 'Bash',
               'tool_input': {'command': command.format(path=path)}}
    assert check_write(payload)[0] == 1
    path.write_text(VALID)
    assert check_write(payload)[0] == 0


@pytest.mark.parametrize('command', ['python -c "print(1)" # D-3',
    'xargs tee decisions/D-3.md', 'node --eval="1" # D-3', 'perl -e "1" # D-3', 'cat > "D-3',
    'for x in D-3; do echo x; done'])
def test_relevant_opaque_or_unparseable_bash(ws, command):
    from wuwei.guards.decision import check_write
    save(ws)
    code, message = check_write({'cwd': str(ws), 'tool_name': 'Bash',
        'tool_input': {'command': command}})
    assert code == 2 and message
    from wuwei.workspace import day_dir
    assert not (day_dir(ws) / 'events.jsonl').exists()


@pytest.mark.parametrize('command', ['python3 -m pytest -q', 'for x in a; do echo x; done',
                                    'export X=1', 'echo "unterminated'])
def test_irrelevant_bash_passes(ws, command):
    from wuwei.guards.decision import check_write
    save(ws, 'bad')
    assert check_write({'cwd': str(ws), 'tool_name': 'Bash',
        'tool_input': {'command': command}}) == (0, '')


def test_resolved_file_scope(ws, tmp_path, monkeypatch):
    from wuwei.guards.decision import check_write
    path = save(ws, 'bad')
    outside = tmp_path / 'unrelated'
    outside.mkdir()
    other = outside / 'decisions/D-3.md'
    other.parent.mkdir()
    other.write_text('bad')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(ws))
    assert check_write(write_payload(outside, other)) == (0, '')
    assert check_write(write_payload(ws, other)) == (0, '')
    assert check_write(write_payload(outside, path))[0] == 1
    alias = outside / 'alias.md'
    alias.symlink_to(path)
    assert check_write(write_payload(outside, alias))[0] == 1
    link = path.parent / 'D-4.md'
    link.symlink_to(other)
    assert check_write(write_payload(ws, link)) == (0, '')


def test_bash_target_from_outside(ws, tmp_path):
    from wuwei.guards.decision import check_write
    path = save(ws, 'bad')
    assert check_write({'cwd': str(tmp_path), 'tool_name': 'Bash',
        'tool_input': {'command': f'cat > {path}'}})[0] == 1
    assert check_write({'cwd': str(tmp_path), 'tool_name': 'Bash',
        'tool_input': {'command': 'python -c "bad" # D-3'}}) == (0, '')


def test_configured_repo_and_worktree(ws, tmp_path, monkeypatch):
    from wuwei.guards.decision import check_write
    from wuwei import registry
    from fakes.vcs import Fake
    repo, tree = tmp_path / 'repo', tmp_path / 'tree'
    repo.mkdir()
    tree.mkdir()
    (tree / '.git').write_text('gitdir: ignored; port resolves this')
    (ws / '.wuwei/config.toml').write_text(
        '[[repos]]\nname="org/repo"\npath="../repo"\ndefault_branch="main"\n')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(ws))
    fake = Fake({'commit_context': registry.Result(0, {'common_dir': str(repo / '.git')})})
    monkeypatch.setattr(registry, 'load', lambda kind, config: fake)
    for cwd in (repo, tree):
        path = cwd / 'decisions/D-3.md'
        path.parent.mkdir()
        path.write_text('bad')
        assert check_write(write_payload(cwd, path))[0] == 1
    assert len(fake.calls) == 2


def test_hook_translates_findings(ws, monkeypatch, capsys):
    from wuwei.__main__ import main
    path = save(ws, 'bad')
    payload = write_payload(ws, path)
    payload.update(session_id='test', transcript_path='transcript.jsonl',
                   hook_event_name='PostToolUse', tool_response={})
    monkeypatch.setattr('sys.stdin', io.StringIO(json.dumps(payload)))
    assert main(['hook', 'PostToolUse']) == 2
    assert 'missing fields' in capsys.readouterr().err


def question_payload(cwd, text='Choose for D-3?'):
    return {'cwd': str(cwd), 'tool_name': 'AskUserQuestion',
            'tool_input': {'questions': [{'question': text}]}}


@pytest.mark.parametrize('text,record,code', [('Choose?', VALID, 1),
    ('D-3?', VALID, 0), ('D-3?', None, 2), ('D-3?', 'bad', 1),
    ('XD-3suffix?', VALID, 1), ('D-0?', VALID, 1), ('D-3 and D-4?', VALID, 2)])
def test_question_table(ws, text, record, code):
    from wuwei.guards.decision import check_question
    save(ws, record)
    result, message = check_question(question_payload(ws, text))
    assert result == code
    if code:
        assert 'decision' in message.lower() and 'D-' in message


@pytest.mark.parametrize('tool_input', [None, {}, {'questions': []},
    {'questions': ['D-3']}, {'questions': [{'question': 3}]},
    {'questions': [{'header': 'D-3', 'question': 'Choose?'}]}])
def test_question_malformed_or_metadata(ws, tool_input):
    from wuwei.guards.decision import check_question
    save(ws)
    payload = question_payload(ws)
    payload['tool_input'] = tool_input
    assert check_question(payload)[0] != 0


def test_every_question_needs_its_own_citation(ws):
    from wuwei.guards.decision import check_question
    save(ws)
    payload = question_payload(ws)
    payload['tool_input']['questions'].append({'question': 'Unrelated choice?'})
    assert check_question(payload)[0] == 1


def test_question_today_and_symlink(ws, monkeypatch):
    from wuwei.guards.decision import check_question
    path = save(ws)
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00+00:00')
    assert check_question(question_payload(ws))[0] == 2
    today = save(ws, None)
    today.symlink_to(path)
    assert check_question(question_payload(ws))[0] == 2


def test_question_scope_and_escalation_input(ws, tmp_path, monkeypatch):
    from wuwei.guards.decision import check_question
    save(ws)
    monkeypatch.setenv('WUWEI_WORKSPACE', str(ws))
    assert check_question(question_payload(tmp_path, 'Choose?')) == (0, '')
    assert check_question({'cwd': str(ws), 'tool_input': {'question': 'D-3?'}})[0] == 0
    assert check_question({'cwd': str(ws), 'tool_input': {'question': 'Choose?'}})[0] == 1


def test_question_hook_exit_two(ws, monkeypatch, capsys):
    from wuwei.__main__ import main
    payload = question_payload(ws, 'Choose?')
    payload.update(session_id='test', transcript_path='transcript.jsonl', hook_event_name='PreToolUse')
    monkeypatch.setattr('sys.stdin', io.StringIO(json.dumps(payload)))
    assert main(['hook', 'PreToolUse']) == 2
    assert json.loads(capsys.readouterr().out)['hookSpecificOutput']['permissionDecision'] == 'deny'


@pytest.mark.parametrize('door,radius,expected', [('two-way', 'own branch', 'seat'),
    ('two-way', 'own PR', 'seat'), ('one-way', 'own branch', 'owner'),
    ('unsure', 'own branch', 'owner'), ('two-way', 'scope agreed with others', 'owner'),
    ('two-way', 'own branch and trust boundaries', 'owner'),
    ('two-way', 'goals', 'owner'), ('two-way', 'spend above budget', 'owner')])
def test_route(ws, monkeypatch, capsys, door, radius, expected):
    from wuwei.__main__ import main
    from wuwei import state
    monkeypatch.chdir(ws)
    save(ws, VALID.replace('Reversibility: two-way', 'Reversibility: ' + door)
         .replace('Blast radius: own branch', 'Blast radius: ' + radius))
    assert main(['decision', 'route', 'D-3']) == 0
    assert capsys.readouterr().out.strip() == expected
    recorded = state.read_state(ws).get('decision_outcomes', {})
    if expected == 'seat':
        assert recorded['D-3']['decided_by'] == 'seat'
        assert recorded['D-3']['option'] == 'A'
        assert events(ws)[-1]['kind'] == 'decision.decided'
    else:
        assert not recorded


@pytest.mark.parametrize('text,code', [('bad', 1), (None, 2)])
def test_route_invalid_record(ws, monkeypatch, text, code):
    from wuwei.__main__ import main
    from wuwei import state
    monkeypatch.chdir(ws)
    save(ws, text)
    assert main(['decision', 'route', 'D-3']) == code
    assert not state.read_state(ws).get('decision_outcomes')


@pytest.mark.parametrize('decision_id', ['../D-3', 'D-0', 'D-3.md', 'D-3/../../state'])
def test_route_invalid_id(ws, monkeypatch, decision_id):
    from wuwei.__main__ import main
    monkeypatch.chdir(ws)
    assert main(['decision', 'route', decision_id]) == 2


def test_outcome_command_cannot_record_owner_answer(ws, monkeypatch):
    from wuwei.__main__ import main
    from wuwei import state
    monkeypatch.chdir(ws)
    save(ws)
    with pytest.raises(SystemExit) as exc:
        main(['decision', 'outcome', 'D-3', 'Accepted', '--decided-by', 'owner'])
    assert exc.value.code == 2
    assert not state.read_state(ws).get('decision_outcomes')


@pytest.mark.parametrize('path,value', [('decision_outcomes', {}),
    ('decision_outcomes.D-3', {}), ('items.x.decision_outcomes', {}),
    ('items.x', {'decision_outcomes': {}})])
def test_reserved_outcomes(ws, path, value):
    from wuwei import state
    with pytest.raises(state.StateError, match='reserved'):
        state.set_state(path, value, ws)


def test_reserved_callback(ws):
    from wuwei import state
    with pytest.raises(state.StateError, match='reserved'):
        state.write_state(lambda data: data.update(decision_outcomes={'D-3': {}}), ws)


def test_citation_rejects_symlinked_decisions_directory(ws, monkeypatch):
    from wuwei.guards.decision import check_question
    from wuwei.workspace import day_dir
    yesterday = save(ws)
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00+00:00')
    day_dir(ws).mkdir()
    (day_dir(ws) / 'decisions').symlink_to(yesterday.parent, target_is_directory=True)
    assert check_question(question_payload(ws))[0] == 2


def test_bash_parse_error_target_with_workspace_anchor(ws, tmp_path, monkeypatch):
    from wuwei.guards.decision import check_write
    path = save(ws)
    monkeypatch.setenv('WUWEI_WORKSPACE', str(ws))
    code, message = check_write({'cwd': str(tmp_path), 'tool_name': 'Bash',
        'tool_input': {'command': f'for x in 1; do cat > {path}; done'}})
    assert code == 2 and 'decision record' in message and 'git/gh' not in message


def test_reserved_outcomes_inside_list(ws):
    from wuwei import state
    with pytest.raises(state.StateError, match='reserved'):
        state.set_state('metadata', [{'decision_outcomes': {'D-3': {}}}], ws)


@pytest.mark.parametrize('command', ['dd if=input of={path}', 'tool --output={path}',
    'cat > {quoted}'])
def test_bash_target_operand_and_obfuscated_relevance(ws, tmp_path, command):
    from wuwei.guards.decision import check_write
    path = save(ws, 'bad')
    raw = command.format(path=path, quoted=str(path).replace('D-3', "D''-3"))
    assert check_write({'cwd': str(tmp_path), 'tool_name': 'Bash',
                       'tool_input': {'command': raw}})[0] == 1


def test_reserved_outcomes_inside_tuple_callback(ws):
    from wuwei import state
    with pytest.raises(state.StateError, match='reserved'):
        state.write_state(lambda data: data.update(
            metadata=({'decision_outcomes': {'D-3': {}}},)), ws)


@pytest.mark.parametrize('kind', ['decision.decided', 'decision.rejected', 'decision.future'])
def test_generic_event_reserves_all_decision_kinds(ws, monkeypatch, kind):
    from wuwei.__main__ import main
    from wuwei.workspace import day_dir
    monkeypatch.chdir(ws)
    assert main(['event', kind, '{}']) == 1
    assert not (day_dir(ws) / 'events.jsonl').exists()


@pytest.mark.parametrize('field', ['Context', 'Blast radius', 'Pre-mortem', 'Revisit', 'Outcome'])
def test_prose_fields_allow_continuation(field):
    from wuwei.decision import lint
    lines = VALID.splitlines()
    index = next(i for i, line in enumerate(lines) if line.startswith(field + ':'))
    lines.insert(index + 1, 'More evidence and explanation.')
    assert lint('\n'.join(lines))[0] == 0


@pytest.mark.parametrize('field', ['Question', 'Recommendation', 'Confidence', 'Reversibility', 'Decided-by'])
def test_scalar_fields_reject_continuation(field):
    from wuwei.decision import lint
    lines = VALID.splitlines()
    index = next(i for i, line in enumerate(lines) if line.startswith(field + ':'))
    lines.insert(index + 1, 'Another value')
    assert lint('\n'.join(lines))[0] == 1


@pytest.mark.parametrize('suffix', ['\n## Consequences\nA longer explanation.\n## Notes\nEvidence.',
                                    '\nConsequences: A longer explanation.\nNotes: Evidence.'])
def test_trailing_madr_sections(suffix):
    from wuwei.decision import lint
    assert lint(VALID + suffix)[0] == 0
    assert lint(VALID.replace('Outcome: pending', '') + suffix)[0] == 1


@pytest.mark.parametrize('outer_pipes', [True, False])
def test_markdown_tables_and_case_insensitive_musts(outer_pipes):
    from wuwei.decision import evaluate
    text = VALID.replace('| Safe | pass | pass |', '| Safe | FAIL | Pass |').replace('Recommendation: A', 'Recommendation: B')
    if not outer_pipes:
        text = '\n'.join(line.strip('|') if line.startswith('|') else line for line in text.splitlines())
    assert evaluate(text)[1]['B'] == 30


@pytest.mark.parametrize('command,named', [('echo D-3', False), ('cat {path}', True)])
def test_bash_scan_records_only_named_rejections(ws, command, named):
    from wuwei.guards.decision import check_write
    from wuwei.workspace import day_dir
    path = save(ws, 'bad')
    save(ws, 'bad', 'D-4.md')
    code, message = check_write({'cwd': str(ws), 'tool_name': 'Bash',
        'tool_input': {'command': command.format(path=path)}})
    assert code == 1 and 'missing fields' in message
    if named:
        assert [event['payload']['file'] for event in events(ws)] == [str(path)]
    else:
        assert not (day_dir(ws) / 'events.jsonl').exists()


CLARIFICATION = '''Question: Which repository?
Context: The request names two repositories.
Options:
- A: service
- B: client
'''


@pytest.mark.parametrize('record,code', [(CLARIFICATION, 0),
    (CLARIFICATION.replace('Options:\n- A: service\n- B: client', 'Options: service\nOptions: client'), 0),
    (CLARIFICATION.replace('- B: client\n', ''), 1),
    (CLARIFICATION.replace('Context: The request names two repositories.\n', ''), 1),
    (CLARIFICATION + 'Wants:\n| Criterion | Weight | A | B |\n', 1),
    (VALID, 1), (None, 2)])
def test_clarification_question(ws, record, code):
    from wuwei.guards.decision import check_question
    save(ws, record, 'C-2.md')
    assert check_question(question_payload(ws, 'Clarify C-2?'))[0] == code


def test_clarification_cannot_replace_decision_or_another_question(ws):
    from wuwei.guards.decision import check_question
    save(ws, CLARIFICATION)
    save(ws, CLARIFICATION, 'C-2.md')
    assert check_question(question_payload(ws))[0] == 1
    payload = question_payload(ws, 'C-2?')
    payload['tool_input']['questions'].append({'question': 'Choose?'})
    assert check_question(payload)[0] == 1
    assert check_question(question_payload(ws, 'XC-2suffix?'))[0] == 1


def test_clarification_must_belong_to_today(ws, monkeypatch):
    from wuwei.guards.decision import check_question
    old = save(ws, CLARIFICATION, 'C-2.md')
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00+00:00')
    assert check_question(question_payload(ws, 'C-2?'))[0] == 2
    save(ws, None, 'C-2.md').symlink_to(old)
    assert check_question(question_payload(ws, 'C-2?'))[0] == 2


@pytest.mark.parametrize('header,text,code', [
    ('Morning gate', 'Approve {plan}?', 0),
    ('Plan', 'Morning gate: approve {plan}?', 0),
    ('Morning gate', 'Approve days/2026-09-28/plan.md?', 0),
    ('Morning gate', 'Approve?', 1),
    ('Plan', 'Approve {plan}?', 1),
    ('Morning gate', 'Approve days/2026-09-27/plan.md?', 1),
    ('Morning gate', 'Approve unrelated/days/2026-09-28/plan.md?', 1),
    ('Morning gate', 'Approve days/2026-09-28/plan.md.bak?', 1),
])
def test_morning_gate_requires_marker_and_current_plan(ws, header, text, code):
    from wuwei.guards.decision import check_question
    from wuwei.workspace import day_dir
    plan = day_dir(ws) / 'plan.md'
    plan.parent.mkdir(parents=True)
    plan.write_text('Today: fix the failing test.')
    payload = question_payload(ws, text.format(plan=plan))
    payload['tool_input']['questions'][0]['header'] = header
    assert check_question(payload)[0] == code
    if code == 0:
        payload['tool_input']['questions'].append({'question': 'Unrelated choice?'})
        assert check_question(payload)[0] == 1


def test_question_rejection_is_feedback_without_write_event(ws):
    from wuwei.guards.decision import check_question
    from wuwei.workspace import day_dir
    save(ws, 'bad')
    assert check_question(question_payload(ws))[0] == 1
    assert not (day_dir(ws) / 'events.jsonl').exists()
