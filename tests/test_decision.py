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
    fake = Fake({'repo_context': registry.Result(0, {'common_dir': str(repo / '.git')})})
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


def test_seat_route_rejects_owner_decider(ws, monkeypatch, capsys):
    from wuwei.__main__ import main
    from wuwei import state
    monkeypatch.chdir(ws)
    save(ws, VALID.replace('Decided-by: seat', 'Decided-by: owner'))
    assert main(['decision', 'route', 'D-3']) == 1
    assert 'Decided-by must be seat for a seat-routed decision' in capsys.readouterr().err
    assert not state.read_state(ws).get('decision_outcomes')
    assert events(ws)[-1]['kind'] == 'decision.rejected'


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


@pytest.mark.parametrize('kind', ['decision.decided', 'decision.rejected', 'decision.future',
                                  'decision.replied'])
def test_generic_event_reserves_all_decision_kinds(ws, monkeypatch, capsys, kind):
    from wuwei.__main__ import main
    from wuwei.workspace import day_dir
    monkeypatch.chdir(ws)
    assert main(['event', kind, '{}']) == 1
    assert not (day_dir(ws) / 'events.jsonl').exists()
    if kind == 'decision.replied':
        assert 'wuwei control plane poll_replies' in capsys.readouterr().err


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


def test_owner_outcome_resumes_linked_item_and_report(ws, monkeypatch):
    from wuwei.__main__ import main
    from wuwei import state, report
    monkeypatch.chdir(ws)
    decision_path = save(ws, VALID.replace('Reversibility: two-way', 'Reversibility: one-way'))
    def park(data):
        data['items']['X'] = {'phase': 'parked', 'status': 'blocked', 'resume_phase': 'planned'}
        data.setdefault('builds', {})['X'] = {'action': {'decision': str(decision_path)}}
    state._write_state(park, ws, reserved=False)
    assert main(['decision', 'route', 'D-3']) == 0
    monkeypatch.setattr('wuwei.integrity._host_confirm', lambda value, **kwargs: True)
    assert main(['decision', 'outcome', 'D-3', 'A']) == 0
    data = state.read_state(ws)
    assert data['items']['X']['phase'] == 'planned'
    assert data['items']['X']['status'] == 'queued'
    assert data['decision_outcomes']['D-3']['outcome'] == 'A'
    assert '- D-3: A' in report.build(ws)
    text = decision_path.read_text()
    assert 'Outcome: A\n' in text and 'Outcome: pending' not in text
    from wuwei import decision
    assert decision.lint(text)[0] == 0


def test_owner_outcome_rejects_bad_choice_and_declined_confirmation(ws, monkeypatch):
    from wuwei.__main__ import main
    from wuwei import state
    monkeypatch.chdir(ws)
    path = save(ws, VALID.replace('Reversibility: two-way', 'Reversibility: one-way'))
    before = path.read_bytes()
    assert main(['decision', 'route', 'D-3']) == 0
    assert main(['decision', 'outcome', 'D-3', 'missing']) == 1
    assert path.read_bytes() == before
    monkeypatch.setattr('wuwei.integrity._host_confirm', lambda value, **kwargs: False)
    assert main(['decision', 'outcome', 'D-3', 'A']) == 1
    assert not state.read_state(ws).get('decision_outcomes')
    assert path.read_bytes() == before


def test_owner_outcome_takes_a_root_and_where(ws, monkeypatch, tmp_path):
    from types import SimpleNamespace
    from wuwei import decision, state
    from wuwei.commands.decision import owner_outcome
    elsewhere = tmp_path / 'elsewhere'
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    path = save(ws)
    decision.route_owner('D-3', decision.evaluate(VALID)[0], ws)

    def refuse(*args, **kwargs):
        raise AssertionError('the host terminal must not be asked')
    monkeypatch.setattr('wuwei.integrity._host_confirm', refuse)
    assert owner_outcome(SimpleNamespace(id='D-3', option='A'), root=ws, where='in the owner DM') == (0, 'A')
    assert state.read_state(ws)['decision_outcomes']['D-3']['decided_by'] == 'owner'
    text = path.read_text()
    assert 'Outcome: A\n' in text and ' in the owner DM.\n' in text


def test_owner_outcome_with_where_refuses_a_one_way_record(ws, monkeypatch):
    from types import SimpleNamespace
    from wuwei import decision, state
    from wuwei.commands.decision import owner_outcome
    one_way = VALID.replace('Reversibility: two-way', 'Reversibility: one-way')
    path = save(ws, one_way)
    decision.route_owner('D-3', decision.evaluate(one_way)[0], ws)
    before = path.read_bytes()
    assert owner_outcome(SimpleNamespace(id='D-3', option='A'), root=ws, where='in the owner DM') == (
        1, 'decision: only a two-way decision is decided from the DM; '
           'run bin/wuwei decide D-3 A in a host terminal')
    assert not state.read_state(ws).get('decision_outcomes')
    assert path.read_bytes() == before


def test_owner_outcome_without_a_terminal_names_the_owner_action(ws, monkeypatch, capsys):
    import builtins
    from wuwei.__main__ import main
    from wuwei import state
    monkeypatch.chdir(ws)
    path = save(ws, VALID.replace('Reversibility: two-way', 'Reversibility: one-way'))
    assert main(['decision', 'route', 'D-3']) == 0
    before = path.read_bytes()
    real_open = builtins.open
    def fake_open(name, *args, **kwargs):
        if name == '/dev/tty':
            raise OSError(6, 'Device not configured')
        return real_open(name, *args, **kwargs)
    monkeypatch.setattr(builtins, 'open', fake_open)
    capsys.readouterr()
    assert main(['decision', 'outcome', 'D-3', 'A']) == 2
    assert capsys.readouterr().err == 'wuwei decision: this is an owner action: run it in a host terminal\n'
    assert path.read_bytes() == before
    assert not state.read_state(ws).get('decision_outcomes')


def test_owner_reversal_is_recorded_once_and_measured(ws, monkeypatch):
    from wuwei.__main__ import main
    from wuwei import metrics
    monkeypatch.chdir(ws)
    save(ws)
    assert main(['decision', 'route', 'D-3']) == 0
    monkeypatch.setattr('wuwei.integrity._host_confirm', lambda value, **kwargs: True)
    assert metrics.collect(ws)['seat_decisions_owner_reversed'] == 0
    assert main(['decision', 'outcome', 'D-3', 'B']) == 0
    assert main(['decision', 'outcome', 'D-3', 'B']) == 1
    assert [row['kind'] for row in events(ws)].count('decision.reversed') == 1
    assert metrics.collect(ws)['seat_decisions_owner_reversed'] == 1


@pytest.mark.parametrize('command,expected', [
    ('bin/wuwei decision outcome D-3 A', 1),
    ('expect -c "spawn bin/wuwei decision outcome D-3 A"', 2),
    ('wuwei decision route D-2; expect -c "spawn wuwei decision outcome D-2 A"', 2),
    ('script -q /dev/null wuwei decision outcome D-2 A', 2),
    ('unbuffer wuwei decision outcome D-2 A', 2),
    ('python3 -mwuwei decision outcome D-3 A', 1),
    ('X=outcome; wuwei decision $X D-3 A', 2),
    ('wuwei decision route D-2', 0),
    ('python3 -m pytest -q', 0),
])
def test_agent_tool_cannot_invoke_owner_outcome(ws, command, expected):
    from wuwei.guards.protect_state import check_bash
    save(ws)
    payload = {'cwd': str(ws), 'tool_name': 'Bash',
               'tool_input': {'command': command}}
    assert check_bash(payload)[0] == expected


@pytest.mark.parametrize('data,expected', [
    ({}, None),
    ({'decision_outcomes': {}}, None),
    ({'decision_outcomes': {'D-1': {}}}, None),
    ({'decision_outcomes': {'D-1': {'option': 'A', 'decided_by': 'seat'}}}, None),
    ({'decision_outcomes': {'D-1': 'defer'}}, None),
    ({'decision_outcomes': {'D-1': {'option': 'defer', 'decided_by': 'owner'}}}, 'defer'),
])
def test_answered_reads_only_owner_outcomes(data, expected):
    from wuwei import decision
    assert decision.answered(data, 'D-1') == expected


def template():
    from contextlib import redirect_stdout
    from argparse import Namespace
    from wuwei.commands.decision import run
    out = io.StringIO()
    with redirect_stdout(out):
        run(Namespace(action='template'))
    return out.getvalue()


THREE = VALID.replace('| B | Defer until tomorrow |', '| B | Defer until tomorrow |\n| C | Rewrite it |').replace(
    '| Criterion | A | B |\n| --- | --- | --- |\n| Safe | pass | pass |',
    '| Criterion | A | B | C |\n| --- | --- | --- | --- |\n| Safe | pass | pass | fail |').replace(
    '| Criterion | Weight | A | B |\n| --- | --- | --- | --- |\n| Correctness | 10 | 8 | 2 |\n| Speed | 2 | 3 | 5 |',
    '| Criterion | Weight | A | B | C |\n| --- | --- | --- | --- | --- |\n'
    '| Correctness | 10 | 8 | 2 | 9 |\n| Speed | 2 | 3 | 5 | 1 |')


def test_present_brief():
    from wuwei import decision
    fields, _ = decision.evaluate(template())
    assert decision.present('D-3', fields, 'brief').splitlines() == [
        'D-3: Which option should we take?', 'A: Make the scoped change (score 80)',
        'B: Defer until more evidence exists (score 20)', 'Recommended: A, ahead of B on Outcome.']
    fields, _ = decision.evaluate(THREE)
    assert decision.present('D-3', fields, 'brief').splitlines() == [
        'D-3: Which fix?', 'A: Implement fix (score 86)', 'B: Defer until tomorrow (score 30)',
        'C: Rewrite it (score 92, fails a must)', 'Recommended: A, ahead of B on Correctness.']
    only = VALID.replace('| Safe | pass | pass |', '| Safe | pass | fail |')
    assert decision.present('D-3', decision.evaluate(only)[0], 'brief').splitlines()[-1] == (
        'Recommended: A, the only option that passes every must.')
    tied = VALID.replace('| 8 | 2 |', '| 2 | 2 |').replace('| 3 | 5 |', '| 5 | 5 |')
    assert decision.present('D-3', decision.evaluate(tied)[0], 'brief').splitlines()[-1] == (
        'Recommended: A, tied with B on score.')


def test_present_standard():
    from wuwei import decision
    fields, _ = decision.evaluate(VALID.replace('Context: tests', 'Context:\n\ntests')
                                  + '\n## Notes\nOnly here.')
    brief = decision.present('D-3', fields, 'brief').splitlines()
    standard = decision.present('D-3', fields, 'standard').splitlines()
    assert standard == brief + [
        'Context: tests/test_example.py records the failure.',
        'Confidence: high. Reversibility: two-way.', 'Blast radius: own branch',
        'Pre-mortem: Regression returns.', 'Revisit: Regression returns.']


def test_decision_show(ws, monkeypatch, capsys):
    from wuwei.__main__ import main
    from wuwei import decision
    from wuwei.workspace import day_dir
    monkeypatch.chdir(ws)
    path = save(ws)
    fields, _ = decision.evaluate(VALID)
    assert main(['decision', 'show', 'D-3']) == 0
    out = capsys.readouterr().out
    assert out == decision.present('D-3', fields, 'brief') + '\nFull record: wuwei decision show D-3 --full\n'
    assert len(out.splitlines()) < 12
    assert main(['decision', 'show', 'D-3', '--full']) == 0
    assert capsys.readouterr().out == VALID
    rich = VALID.replace('records the failure.', 'records the failure.\n```\nFAILED test_x\n```\n'
                         '> Reviewer said: **do not merge**') + '## Notes\nEvidence: probe.log\n'
    path.write_text(rich)
    assert main(['decision', 'show', 'D-3', '--full']) == 0
    assert capsys.readouterr().out == rich
    path.write_text(VALID)
    (ws / '.wuwei/config.toml').write_text('[owner.verbosity]\ndecisions = "standard"\n')
    assert main(['decision', 'show', 'D-3']) == 0
    assert capsys.readouterr().out.startswith(decision.present('D-3', fields, 'standard') + '\nFull record:')
    path.write_text('Question: bad')
    assert main(['decision', 'show', 'D-3']) == 1
    assert 'missing fields' in capsys.readouterr().err
    path.unlink()
    assert main(['decision', 'show', 'D-3']) == 0  # #362: a state answer
    assert 'No D-3 today' in capsys.readouterr().out
    path.symlink_to(save(ws, name='D-4.md'))
    assert main(['decision', 'show', 'D-3']) == 2
    assert 'must belong to today' in capsys.readouterr().err
    assert not (day_dir(ws) / 'events.jsonl').exists()


def test_lint_reports_style_without_rejecting(ws):
    from wuwei.decision import lint, lint_file
    text = VALID.replace('records the failure.', 'records the failure. It is not just a fix but a rewrite; we delve into it.')
    assert lint(text) == (0, 'OK: A (86)\nstyle: not-x-but-y, stock-word')
    assert lint_file(save(ws, text)) == (0, 'OK: A (86)\nstyle: not-x-but-y, stock-word')
    from wuwei.workspace import day_dir
    assert not (day_dir(ws) / 'events.jsonl').exists()
    assert lint(template()) == (0, 'OK: A (80)')


@pytest.mark.parametrize('config,expected', [
    ({}, {'approach': 2, 'retry': 2, 'park': 2, 'accept-residual': 2, 'defer': 0,
          'scope-cut': 0, 're-plan': 0, 'dependency-bump': 0, 'merge': 3, 'message': 0,
          'other': 0}),
    ({'approach': 1}, {'approach': 1}),
    ({'defer': 3}, {'defer': 0}),
])
def test_class_levels(config, expected):
    from wuwei import decision
    settings = {'decisions': {'cruise': {'enabled': True, 'levels': config}}}
    assert {name: decision.level(settings, name) for name in expected} == expected
    settings['decisions']['cruise']['enabled'] = False
    assert {decision.level(settings, name) for name in decision.CLASSES} == {0}


@pytest.mark.parametrize('text,record,code', [
    ('Done.\nBlocked: none', VALID, 0),
    ('Should I add a cache?', VALID, 1),
    ('Should I take D-3?', VALID, 0),
    ('Should I take D-9?', VALID, 2),
    ('```\nWhy?\n```\n> Really?\nDone.', VALID, 0),
])
def test_unrecorded_question(ws, text, record, code):
    from wuwei.guards.decision import unrecorded
    save(ws, record)
    result, message = unrecorded(text, ws)
    assert result == code
    if code:
        assert 'Cite a decision D-n' in message


def stop_payload(cwd, **changes):
    return {'cwd': str(cwd), 'agent_id': 'a1', 'agent_type': 'wuwei:builder',
            'stop_hook_active': False, 'agent_transcript_path': str(cwd / 'none.jsonl'),
            'last_assistant_message': 'Should I add a cache?', **changes}


@pytest.mark.parametrize('changes,code', [
    ({}, 1), ({'stop_hook_active': True}, 0), ({'agent_type': 'general-purpose'}, 0),
    ({'last_assistant_message': 'Done.'}, 0)])
def test_check_stop(ws, changes, code):
    from wuwei import state
    from wuwei.guards.decision import check_stop
    result, message = check_stop(stop_payload(ws, **changes))
    assert result == code
    assert not state.read_state(ws).get('steward_notes')


def test_check_stop_outside_workspace(ws, tmp_path):
    from wuwei.guards.decision import check_stop
    outside = tmp_path / 'outside'
    outside.mkdir()
    assert check_stop(stop_payload(outside)) == (0, '')


def external(ws, monkeypatch, *, reversibility='two-way', goal='G-1', trust=False, when='09:00'):
    from wuwei import state
    from wuwei.__main__ import main
    monkeypatch.chdir(ws)
    monkeypatch.setenv('WUWEI_NOW', f'2026-09-28T{when}:00+00:00')
    (ws / '.wuwei/config.toml').write_text(
        '[owner]\ntimezone = "UTC"\n[decisions]\nwait_hours = 2\n')
    state._write_state(lambda data: data['items'].update(alpha={
        'goal': goal, 'flags': {'trust_surface': trust, 'boundary_relevant': False,
                                'agent_surface': False}}), ws, reserved=False)
    save(ws, VALID.replace('Reversibility: two-way', 'Reversibility: ' + reversibility),
         name='D-1.md')
    return main(['decision', 'route', 'D-1', '--external', 'alpha'])


def test_route_external_marks_the_item(ws, monkeypatch, capsys):
    from wuwei import dispatch, state
    from wuwei.__main__ import main
    assert external(ws, monkeypatch) == 0
    assert capsys.readouterr().out.strip() == 'owner'
    data = state.read_state(ws)
    assert 'D-1' in data['decision_routes'] and 'D-1' not in data.get('decision_outcomes', {})
    assert data['items']['alpha']['assumption'] == {
        'kind': 'external', 'decision': 'D-1', 'day': '2026-09-28',
        'since': '2026-09-28T09:00:00+00:00', 'status': 'waiting'}
    routed = [row for row in events(ws) if row['kind'] == 'decision.routed']
    assert routed[-1]['payload']['item'] == 'alpha'
    count = len(events(ws))
    assert main(['decision', 'route', 'D-1', '--external', 'alpha']) == 0
    assert len(events(ws)) == count
    with pytest.raises(dispatch.Refused) as refused:
        dispatch.next_step('alpha', ws)
    assert 'D-1' not in str(refused.value) and 'steward' not in str(refused.value)
    assert main(['decision', 'route', 'D-1', '--external', 'beta']) == 1
    assert len(events(ws)) == count


@pytest.mark.parametrize('start,end,zone,hours', [
    ('2026-09-25T12:00:00+02:00', '2026-09-28T12:00:00+02:00', 'Europe/Amsterdam', 24),
    ('2026-09-28T09:00:00+02:00', '2026-09-29T08:00:00+02:00', 'Europe/Amsterdam', 23),
    ('2026-10-23T12:00:00+02:00', '2026-10-26T12:00:00+01:00', 'Europe/Amsterdam', 24),
])
def test_weekday_hours(start, end, zone, hours):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from wuwei import decision
    assert decision.weekday_hours(datetime.fromisoformat(start), datetime.fromisoformat(end),
                                  ZoneInfo(zone)) == hours


def waited(ws):
    return [{key: value for key, value in row['payload'].items() if key != 'prs_seen'}
            for row in events(ws) if row['kind'] == 'decision.waited']


def test_two_way_external_wait_confirms(ws, monkeypatch):
    from wuwei import decision, state
    assert external(ws, monkeypatch) == 0
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T12:00:00+00:00')
    assert decision.waits(ws) == 1
    item = state.read_state(ws)['items']['alpha']
    assert item['assumption']['status'] == 'confirmed' and item['phase'] == 'planned'
    assert waited(ws) == [{'item': 'alpha', 'id': 'D-1', 'outcome': 'confirmed',
                           'recommendation': 'A'}]
    assert decision.answered(state.read_state(ws), 'D-1') is None
    assert decision.waits(ws) == 0 and len(waited(ws)) == 1


@pytest.mark.parametrize('options', [{'reversibility': 'one-way'}, {'reversibility': 'unsure'},
                                     {'goal': 'unplanned'}, {'trust': True}])
def test_one_way_external_wait_parks(ws, monkeypatch, options):
    from wuwei import decision, state
    assert external(ws, monkeypatch, **options) == 0
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T12:00:00+00:00')
    assert decision.waits(ws) == 1
    item = state.read_state(ws)['items']['alpha']
    assert (item['phase'], item['status'], item['decision']) == ('parked', 'blocked', 'D-1')
    assert item['assumption']['status'] == 'parked'
    assert waited(ws)[0]['outcome'] == 'parked'
    assert decision.waits(ws) == 0


def test_owner_answer_resumes_a_parked_wait(ws, monkeypatch):
    from wuwei import decision, state
    from wuwei.__main__ import main
    assert external(ws, monkeypatch, reversibility='one-way') == 0
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T12:00:00+00:00')
    decision.waits(ws)
    monkeypatch.setattr('wuwei.integrity._host_confirm', lambda *args, **kwargs: True)
    assert main(['decision', 'outcome', 'D-1', 'A']) == 0
    assert state.read_state(ws)['items']['alpha']['phase'] == 'planned'


def test_external_wait_holds_before_the_time_box_or_after_an_answer(ws, monkeypatch):
    from wuwei import decision, state
    assert external(ws, monkeypatch, when='11:00') == 0
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T12:00:00+00:00')
    assert decision.waits(ws) == 0
    state._write_state(lambda data: data.setdefault('decision_outcomes', {}).update(
        {'D-1': {'option': 'B', 'decided_by': 'owner'}}), ws, reserved=False)
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T15:00:00+00:00')
    assert decision.waits(ws) == 0 and not waited(ws)


def test_unreadable_external_record_fails_closed(ws, monkeypatch):
    from wuwei import decision
    assert external(ws, monkeypatch) == 0
    save(ws, 'bad', name='D-1.md')
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T12:00:00+00:00')
    with pytest.raises(ValueError):
        decision.waits(ws)


def ask(cwd, widget):
    """The four AskUserQuestion keys of a widget through the question guard."""
    from wuwei.guards.decision import check_question
    return check_question({'cwd': str(cwd), 'tool_name': 'AskUserQuestion', 'tool_input': {'questions': [
        {key: widget[key] for key in ('question', 'header', 'options', 'multiSelect')}]}})


def test_widget_shape():
    from wuwei.decision import widget
    built = widget('Q?', 'Head', [('a', 'one'), ('b', 'two')], 'wuwei x <label>')
    assert built == {'question': 'Q?', 'header': 'Head', 'multiSelect': False, 'record': 'wuwei x <label>',
                     'options': [{'label': 'a', 'description': 'one'}, {'label': 'b', 'description': 'two'}]}
    for header, options in (('x' * 13, [('a', '1'), ('b', '2')]), ('H', [('a', '1')]),
                            ('H', [(str(n), 'd') for n in range(5)])):
        with pytest.raises(ValueError):
            widget('Q?', header, options, 'r')


FIVE = '''Question: Which fix?
Context: tests/test_example.py records the failure.
Options:
| Option | Description |
| --- | --- |
| A | Fix one |
| B | Defer until tomorrow |
| C | Fix three |
| D | Fix four |
| E | Fix five |
Musts:
| Criterion | A | B | C | D | E |
| --- | --- | --- | --- | --- | --- |
| Safe | pass | pass | pass | pass | pass |
Wants:
| Criterion | Weight | A | B | C | D | E |
| --- | --- | --- | --- | --- | --- | --- |
| Correctness | 10 | 5 | 2 | 9 | 4 | 3 |
Recommendation: C
Confidence: high
Reversibility: two-way
Blast radius: own branch
Pre-mortem: Regression returns.
Revisit: Regression returns.
Decided-by: seat
Outcome: pending
'''


def test_decision_widget_passes_the_question_guard(ws):
    from wuwei import decision
    save(ws)
    built = decision.record_widget('D-3', decision.evaluate(VALID)[0])
    assert built['question'] == 'D-3: Which fix?' and built['header'] == 'D-3'
    assert [o['label'] for o in built['options']] == ['A', 'B'] and built['multiSelect'] is False
    assert built['options'][0]['description'] == 'Recommended. Implement fix'
    assert built['record'] == 'wuwei decide D-3 <label>'
    assert ask(ws, built) == (0, '')
    swapped = VALID.replace('| 10 | 8 | 2 |', '| 10 | 2 | 8 |').replace('Recommendation: A', 'Recommendation: B')
    built = decision.record_widget('D-3', decision.evaluate(swapped)[0])
    assert [o['label'] for o in built['options']] == ['B', 'A']
    assert built['options'][0]['description'] == 'Recommended. Defer until tomorrow'
    save(ws, FIVE)
    built = decision.record_widget('D-3', decision.evaluate(FIVE)[0])
    assert [o['label'] for o in built['options']] == ['C', 'A', 'B', 'D']
    assert ask(ws, built) == (0, '')


def test_decision_show_widget(ws, monkeypatch, capsys):
    from wuwei.__main__ import main
    from wuwei import decision
    monkeypatch.chdir(ws)
    path = save(ws)
    assert main(['decision', 'show', 'D-3', '--widget']) == 0
    assert json.loads(capsys.readouterr().out) == [decision.record_widget('D-3', decision.evaluate(VALID)[0])]
    path.write_text('Question: bad')
    assert main(['decision', 'show', 'D-3', '--widget']) == 1
    assert 'missing fields' in capsys.readouterr().err
    path.unlink()
    assert main(['decision', 'show', 'D-3', '--widget']) == 1
    with pytest.raises(SystemExit, match='2'):
        main(['decision', 'show', 'D-3', '--widget', '--full'])
@pytest.mark.parametrize('command, expected', [
    ('python3 -P -c \'import subprocess;r=subprocess.run(["git","log","-1"]);'
     'print(open("days/x/decisions/D-1.md").read())\'', 'unparsed'),
    ('for f in days/x/decisions/D-1.md days/x/decisions/D-2.md; do cat $f; done', 'clean'),
    ('for f in a; do echo x > days/x/decisions/D-1.md; done', 'kept'),
])
def test_issue_347_unparsed_decision_commands(ws, command, expected):
    from wuwei.guards.decision import check_write
    from wuwei.shell import UNPARSED
    result = check_write({'cwd': str(ws), 'tool_name': 'Bash', 'tool_input': {'command': command}})
    assert result == {'unparsed': (2, UNPARSED), 'clean': (0, ''),
                      'kept': (2, 'decision lint: could not inspect decision record; '
                               'use a plain file write')}[expected]


def test_issue_347_inline_snippet_still_lints_the_day(ws):
    from wuwei.guards.decision import check_write
    from wuwei.shell import UNPARSED
    save(ws, 'Question: bad')
    code, message = check_write({'cwd': str(ws), 'tool_name': 'Bash', 'tool_input': {
        'command': 'python3 -c \'print(open("decisions/D-3.md").read())\''}})
    assert code == 2 and message.splitlines()[0] == UNPARSED and len(message.splitlines()) > 1
def gate(ws, session='planner-1', header='Goals', **extra):
    from wuwei.workspace import day_dir
    text = f'Morning gate ({day_dir(ws).relative_to(ws / ".wuwei").as_posix()}/plan.md): confirm goals G-1 and G-2?'
    return {'cwd': str(ws), 'session_id': session, 'tool_name': 'AskUserQuestion',
            'tool_input': {'questions': [{'question': text, 'header': header}]}, **extra}


@pytest.fixture
def planner(ws):
    from wuwei import plan
    from wuwei.workspace import day_dir
    day_dir(ws).mkdir(parents=True, exist_ok=True)
    (day_dir(ws) / 'plan.md').write_text('# Morning plan\n')
    plan.session('planner-1', ws)
    return ws


def test_record_gate_notes_planner_topics(planner):
    from wuwei import state
    from wuwei.guards.decision import record_gate
    assert record_gate(gate(planner)) == (0, '')
    assert state.read_state(planner)['sessions']['planner-1']['gate_asked'] == ['goals']
    assert [e['kind'] for e in events(planner)].count('gate.asked') == 1


def test_record_gate_ignores_seats_and_others(planner):
    from wuwei import state
    from wuwei.guards.decision import record_gate
    plain = gate(planner)
    plain['tool_input']['questions'][0]['question'] = 'Morning gate: confirm goals?'
    other = gate(planner, header='Pick')
    other['tool_input']['questions'][0]['question'] = 'Choose D-3 for the build?'
    for payload in (gate(planner, agent_id='a1'), gate(planner, 'other'), plain, other):
        assert record_gate(payload) == (0, '')
    assert 'gate_asked' not in state.read_state(planner)['sessions']['planner-1']
    assert 'gate.asked' not in [e['kind'] for e in events(planner)]


def test_record_gate_voice_topic(planner):
    from wuwei import state
    from wuwei.guards.decision import record_gate
    payload = gate(planner, header='Voice')
    payload['tool_input']['questions'][0]['question'] = payload['tool_input']['questions'][0]['question'].replace('goals G-1 and G-2', 'these lines')
    assert record_gate(payload) == (0, '')
    assert state.read_state(planner)['sessions']['planner-1']['gate_asked'] == ['voice']


def test_set_outcome_rewrites_first_outcome():
    from wuwei import decision
    text = 'Question: Q?\n## Outcome: pending\nNotes: kept\nOutcome: pending\n'
    assert decision.set_outcome(text, 'proceed') == 'Question: Q?\n## Outcome: proceed\nNotes: kept\nOutcome: pending\n'


def test_owner_record_writes_outcome_owner_and_notes(ws):
    from wuwei import decision
    text = decision.owner_record(VALID, 'B', 'at the host terminal', 'phone answer')
    fields, _ = decision.evaluate(text)
    assert fields['Outcome'] == 'B' and fields['Decided-by'] == 'owner'
    assert text.endswith('\nNotes: Decided at 2026-09-28T12:00:00+00:00 at the host terminal. phone answer\n')
    assert decision.owner_record(VALID, 'A', 'at the host terminal').endswith(
        '\nNotes: Decided at 2026-09-28T12:00:00+00:00 at the host terminal.\n')


def test_decide_command_records_routed_decision(ws, monkeypatch, capsys):
    from wuwei.__main__ import main
    from wuwei import decision, state
    monkeypatch.chdir(ws)
    path = save(ws, VALID.replace('Reversibility: two-way', 'Reversibility: one-way'))
    assert main(['decision', 'route', 'D-3']) == 0
    before = path.read_bytes()
    monkeypatch.setattr('wuwei.integrity._host_confirm', lambda value, **kwargs: True)
    assert main(['decide', 'D-3', 'B', '--note', 'a\nb']) == 2
    assert path.read_bytes() == before
    assert main(['decide', 'D-3', 'B', '--note', 'phone answer']) == 0
    text = path.read_text()
    fields, _ = decision.evaluate(text)
    assert fields['Outcome'] == 'B' and fields['Decided-by'] == 'owner'
    assert text.endswith('at the host terminal. phone answer\n')
    assert state.read_state(ws)['decision_outcomes']['D-3']['decided_by'] == 'owner'
    assert [row['kind'] for row in events(ws)].count('decision.decided') == 1


def test_record_gate_notes_asked_decisions(planner):
    from wuwei import state
    from wuwei.guards.decision import record_gate
    save(planner)

    def asked(header, text, session='planner-1', **extra):
        return {'cwd': str(planner), 'session_id': session, 'tool_name': 'AskUserQuestion',
                'tool_input': {'questions': [{'question': text, 'header': header}]}, **extra}
    for payload in (asked('D-3', 'Which option?'), asked('D-9', 'D-9: Which option?'),
                    asked('D-3', 'D-3: Which option?', agent_id='a1'),
                    asked('D-3', 'D-3: Which option?', 'other'), asked('D-3', 'D-30: Which option?')):
        assert record_gate(payload) == (0, '')
    assert 'gate_asked' not in state.read_state(planner)['sessions']['planner-1']
    assert record_gate(asked('D-3', 'D-3: Which option?')) == (0, '')
    assert state.read_state(planner)['sessions']['planner-1']['gate_asked'] == ['D-3']
