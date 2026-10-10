"""Production verdict refusals and the file-tool guard, exercised in-process."""

import pytest

import io
import json
import sys


RETRO = 'Blocked: none\nGap: none\nChange: none\n'
FINDING = '- P1 | cli/example.py:12 | fails when input is empty | blocks: yes\n'
VALID = 'Verdict: FIX\nHead: abc1234\n' + FINDING + 'Probe: not run\nVAL: PASS\n' + RETRO
PASS = 'Verdict: PASS\nHead: abc1234\nProbe: not run\nVAL: PASS\n' + RETRO


@pytest.fixture(autouse=True)
def workspace(tmp_path, monkeypatch):
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    (tmp_path / '.wuwei').mkdir()


@pytest.mark.parametrize('old,new,reason', [
    ('Verdict: FIX', 'Result: FIX', "missing a 'Verdict:"),
    ('cli/example.py:12', 'unknown', 'names no file:line'),
    ('blocks: yes', 'pending', 'no per-finding blocks yes/no'),
    ('fails when input is empty', 'unclear', 'no failure scenario'),
    ('Probe: not run\n', '', 'no mutation/probe line'),
    ('VAL: PASS\n', '', 'class-sweep line'),
    ('Blocked: none\n', '', "missing 'Blocked:'"),
    ('Gap: none\n', '', "missing 'Gap:'"),
    ('Change: none\n', '', "missing 'Change:'"),
    ('P1', 'unknown', 'severity'),
])
def test_source_refusals(old, new, reason):
    from wuwei.verdict import lint
    code, message = lint(VALID.replace(old, new), class_sweep=True)
    assert code == 1
    assert reason in message
    assert message.endswith('REJECT: send back to the seat')


def test_source_refusal_order():
    from wuwei.verdict import lint
    code, message = lint('Verdict: FIX\n', class_sweep=True)
    assert code == 1
    positions = [message.index(fragment) for fragment in (
        'file:line', 'blocks yes/no', 'failure scenario', 'mutation/probe',
        'class-sweep', "'Blocked:'", "'Gap:'", "'Change:'")]
    assert positions == sorted(positions)


@pytest.mark.parametrize('verdict', ['PASS', 'FIX', 'PARK', 'ESCALATE'])
@pytest.mark.parametrize('form', ['Verdict: {}', '## Verdict: {}', '- Verdict: {}',
                                  '**Verdict:** **{}**'])
def test_source_accepted_verdict_forms(verdict, form):
    from wuwei.verdict import lint
    text = VALID.replace('Verdict: FIX', form.format(verdict))
    code, message = lint(text if verdict == 'FIX' else text.replace('blocks: yes', 'blocks: no'))
    assert (code, message) == (0, f'OK: {verdict}')


@pytest.mark.parametrize('text', [PASS, VALID.replace('cli/example.py:12', 'L12'),
                                VALID.replace('Probe: not run', 'Mutation: unmeasured'),
                                VALID.replace('VAL: PASS', 'TEST: **N.A.**'),
                                VALID.replace('Blocked: none', '**Blocked:** none')])
def test_source_clean_cases(text):
    from wuwei.verdict import lint
    assert lint(text)[0] == 0


@pytest.mark.parametrize('rows,code,reason', [
    ('Simplicity: none, direct code\nDesign: none, clear names\n', 0, 'OK'),
    ('Design: none\n', 1, 'Simplicity:'),
    ('Simplicity: none\n', 1, 'Design:'),
    ('Simplicity:\nDesign: none\n', 1, 'Simplicity:'),
    ('Simplicity: none\nDesign: none\nDesign: none\n', 1, 'Design:'),
])
def test_quality_rows(rows, code, reason):
    from wuwei.verdict import lint
    result, message = lint(PASS + rows, quality=True)
    assert result == code
    assert reason in message


@pytest.mark.parametrize('text,reason', [
    (VALID + 'Verdict: PASS\n', 'Verdict:'),
    (PASS + 'Verdict: FAIL\n', 'Verdict:'),
    (PASS + 'Verdict: FIXED\n', 'Verdict:'),
    (VALID.replace('Verdict: FIX', 'Verdict: FIXED'), 'Verdict:'),
    (VALID.replace('Gap: none', 'Gap:'), 'Gap:'),
    (VALID + 'Gap: another\n', 'Gap:'),
    (VALID.replace(FINDING, FINDING + '- P2 | missing | breaks on retry | blocks: no\n'), 'file:line'),
    (PASS + FINDING.replace('blocks: yes', ''), 'blocks'),
    (PASS + FINDING.replace('fails when input is empty', ''), 'scenario'),
    (VALID.replace('blocks: yes', 'blocking'), 'blocks'),
])
def test_incomplete_or_conflicting_evidence(text, reason):
    from wuwei.verdict import lint
    code, message = lint(text)
    assert code == 1
    assert reason in message


@pytest.mark.parametrize('wrap', [lambda s: '```markdown\n' + s + '```\n',
                                  lambda s: '~~~\n' + s + '~~~\n',
                                  lambda s: '<!--\n' + s + '-->\n',
                                  lambda s: '\n'.join('> ' + line for line in s.splitlines())])
def test_samples_cannot_supply_missing_evidence(wrap):
    from wuwei.verdict import lint
    assert lint(wrap(VALID))[0] == 1


def test_multiline_finding():
    from wuwei.verdict import lint
    text = VALID.replace(FINDING, '### P1: empty input\nSeverity: high\n'
                         'File: cli/example.py:12\nScenario: fails when input is empty\n'
                         'blocks: yes\n')
    assert lint(text)[0] == 0


def test_multiline_finding_with_bulleted_fields():
    from wuwei.verdict import lint
    finding = ('### P1: empty input\n- File: cli/example.py:12\n'
               '- Scenario: fails when input is empty\n- blocks: yes\n')
    assert lint(VALID.replace(FINDING, finding))[0] == 0


@pytest.mark.parametrize('extra,reason', [
    ('- unknown | cli/other.py:3 | fails when retried | blocks: no\n', 'severity'),
    ('Severity: P2\nScenario: fails when retried\nblocks: no\n', 'file:line'),
    ('| F2 | P2 | missing | fails when retried | no |\n', 'file:line'),
])
def test_findings_cannot_borrow_evidence(extra, reason):
    from wuwei.verdict import lint
    code, message = lint(VALID.replace(FINDING, FINDING + extra))
    assert code == 1
    assert reason in message


def test_table_with_id_before_severity():
    from wuwei.verdict import lint
    table = ('| ID | Severity | File | Scenario | Blocks |\n'
             '| --- | --- | --- | --- | --- |\n'
             '| F1 | P1 | cli/example.py:12 | fails when empty | yes |\n')
    assert lint(VALID.replace(FINDING, table))[0] == 0


@pytest.mark.parametrize('contents,code,reason', [
    (VALID.encode(), 0, 'OK: FIX'), (b'Verdict: FIX\n', 1, 'file:line'),
    (None, 2, 'could not read'), (b'\xff', 2, 'could not read'),
])
def test_file_exit_table(tmp_path, contents, code, reason):
    from wuwei.verdict import lint_file
    path = tmp_path / 'gate-arch.md'
    if contents is not None:
        path.write_bytes(contents)
    result, message = lint_file(path)
    assert result == code
    assert reason in message


@pytest.mark.parametrize('contents,role,code', [(PASS, '', 0),
                                             ('Verdict: FIX', '', 1),
                                             (None, '', 2), (PASS, 'sentinel-quality', 1)])
def test_cli(tmp_path, capsys, contents, role, code):
    from wuwei.__main__ import main
    path = tmp_path / 'verdict.md'
    if contents is not None:
        path.write_text(contents)
    assert main(['verdict', 'lint', str(path), *(['--role', role] if role else [])]) == code
    output = capsys.readouterr()
    assert output.err if code else output.out


@pytest.mark.parametrize('role,reason', [('sentinel-arch', 'class-sweep'),
                                       ('wuwei:sentinel-security', 'class-sweep'),
                                       ('plugin:wuwei:sentinel-quality', 'Simplicity:'),
                                       ('sentinel-goal', '')])
def test_cli_role_requirements_match_write_guard(tmp_path, capsys, role, reason):
    from wuwei.__main__ import main
    from wuwei.guards.verdict import check_write
    path = tmp_path / 'decisions/gate-item.md'
    path.parent.mkdir()
    path.write_text(PASS.replace('VAL: PASS\n', ''))
    payload = {'cwd': str(tmp_path), 'agent_type': role, 'tool_input': {'file_path': str(path)}}
    assert main(['verdict', 'lint', str(path), '--role', role]) == int(bool(reason))
    assert check_write(payload)[0] == int(bool(reason))
    if reason:
        assert reason in capsys.readouterr().err
    path.write_text(PASS + 'Simplicity: none\nDesign: none\n')
    assert main(['verdict', 'lint', str(path), '--role', role]) == 0
    assert check_write(payload)[0] == 0


@pytest.mark.parametrize('tool', ['Write', 'Edit', 'MultiEdit', 'NotebookEdit'])
@pytest.mark.parametrize('filename,text,code', [
    ('decisions/gate-arch.md', VALID, 0),
    ('decisions/gate-arch.md', 'Verdict: FIX', 1),
    ('decisions/gate-arch.md', None, 2),
    ('decisions/gate-quality.md', PASS, 1),
    ('decisions/gate-item-quality-delta.md', PASS, 1),
    ('decisions/other.md', None, 0),
    ('notes/gate-quality.md', None, 0),
])
@pytest.mark.parametrize('absolute', [False, True])
def test_write_guard_table(tmp_path, tool, filename, text, code, absolute):
    from wuwei.guards.verdict import check_write
    path = tmp_path / filename
    path.parent.mkdir()
    if text is not None:
        path.write_text(text)
    payload = {'cwd': str(tmp_path), 'tool_name': tool,
               'tool_input': {'file_path': str(path) if absolute else './' + filename,
                              'content': VALID, 'new_string': VALID}}
    assert check_write(payload)[0] == code


@pytest.mark.parametrize('payload', [{}, {'cwd': '.', 'tool_input': {}},
                                      {'cwd': '.', 'tool_input': {'file_path': 7}},
                                      {'cwd': '.', 'tool_input': []}])
def test_write_invalid_payload(payload, tmp_path):
    if 'cwd' in payload:
        payload = dict(payload, cwd=str(tmp_path))
    from wuwei.guards.verdict import check_write
    code, message = check_write(payload)
    assert code == 2
    assert message


@pytest.mark.parametrize('alias_gate', [False, True])
def test_symlink_alias_cannot_hide_gate_or_quality(tmp_path, alias_gate):
    from wuwei.guards.verdict import check_write
    gate = tmp_path / 'decisions/gate-quality.md'
    gate.parent.mkdir()
    other = tmp_path / 'other.md'
    target, alias = (other, gate) if alias_gate else (gate, other)
    target.write_text(PASS)
    alias.symlink_to(target)
    assert check_write({'cwd': str(tmp_path), 'tool_input': {'file_path': str(alias)}})[0] == 1


@pytest.mark.parametrize('role', ['sentinel-quality', 'wuwei:sentinel-quality', 'plugin:wuwei:sentinel-quality'])
def test_quality_role_cannot_hide_behind_generic_filename(tmp_path, role):
    from wuwei.guards.verdict import check_write
    path = tmp_path / 'decisions/gate-item.md'
    path.parent.mkdir()
    path.write_text(PASS)
    assert check_write({'cwd': str(tmp_path), 'agent_type': role,
                        'tool_input': {'file_path': str(path)}})[0] == 1


def assert_hook_returns_verdict(tmp_path, monkeypatch, capsys):
    from wuwei.__main__ import main
    path = tmp_path / 'decisions/gate-arch.md'
    path.parent.mkdir(exist_ok=True)
    path.write_text(VALID.replace('cli/example.py:12', 'unknown'))
    payload = {'cwd': str(tmp_path), 'session_id': 'seat', 'transcript_path': 'unused',
               'hook_event_name': 'PostToolUse', 'tool_name': 'Edit',
               'tool_input': {'file_path': str(path)}}
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(payload)))
    assert main(['hook', 'PostToolUse']) == 2
    assert 'file:line' in capsys.readouterr().err


def test_hook_returns_verdict(tmp_path, monkeypatch, capsys):
    assert_hook_returns_verdict(tmp_path, monkeypatch, capsys)


def test_disabled_write_guard_is_caught(tmp_path, monkeypatch, capsys):
    from wuwei.commands import hook
    assert_hook_returns_verdict(tmp_path, monkeypatch, capsys)
    monkeypatch.setattr(hook, 'discover', lambda: [])
    with pytest.raises(AssertionError):
        assert_hook_returns_verdict(tmp_path, monkeypatch, capsys)


@pytest.mark.parametrize('finding', [FINDING, FINDING.replace('- P1', '1. P1'),
                                     '| F1 | P1 | cli/example.py:12 | fails when empty | yes |\n'])
def test_pass_cannot_carry_blocking_finding(finding):
    from wuwei.verdict import lint
    code, message = lint(PASS + finding)
    assert code == 1
    assert 'PASS verdict carries a blocking finding' in message
    assert lint(PASS + finding.replace('yes', 'no'))[0] == 0


@pytest.mark.parametrize('marker', ['1.', '1)', '[F2]', 'F2 (', 'F2:', 'F2.'])
def test_numbered_and_id_findings_need_their_own_citation(marker):
    from wuwei.verdict import lint
    extra = marker + ' P2 missing citation | fails when retried | blocks: no\n'
    code, message = lint(VALID.replace(FINDING, FINDING + extra))
    assert code == 1
    assert 'finding 2: missing file:line' in message
    assert lint(VALID.replace(FINDING, FINDING + extra.replace('missing citation', 'cli/other.py:3')))[0] == 0


@pytest.mark.parametrize('replacement', ['The probe was not run', 'Gap: probe unavailable',
                                        'Probe:', '- mention Mutation: not run'])
def test_probe_requires_a_nonempty_row(replacement):
    from wuwei.verdict import lint
    code, message = lint(PASS.replace('Probe: not run', replacement))
    assert code == 1
    assert 'no mutation/probe line' in message


@pytest.mark.parametrize('row', ['Probe: not run', 'Probes: unmeasured', 'Mutation: killed'])
def test_probe_row_forms(row):
    from wuwei.verdict import lint
    assert lint(PASS.replace('Probe: not run', row))[0] == 0


@pytest.mark.parametrize('head', ['', 'Head: abc123', 'Head: ' + 'a' * 41,
                                  'Head: ghijklm', 'Head: abc1234 extra',
                                  'Head: abc1234\nHead: abc1234',
                                  'Head: abc1234\nHead: invalid',
                                  '> Head: abc1234', '```\nHead: abc1234\n```'])
def test_exactly_one_hex_head_row(head):
    from wuwei.verdict import lint
    code, message = lint(PASS.replace('Head: abc1234', head))
    assert code == 1
    assert 'Head:' in message


@pytest.mark.parametrize('head', ['abc1234', 'A' * 40])
def test_valid_head_row(head):
    from wuwei.verdict import lint
    assert lint(PASS.replace('abc1234', head))[0] == 0


@pytest.mark.parametrize('role,required', [('arch', True), ('quality', True), ('security', True),
                                         ('goal', False), ('item', False)])
def test_class_sweep_only_for_engineering_verdicts(tmp_path, role, required):
    from wuwei.verdict import lint_file
    path = tmp_path / f'gate-{role}.md'
    path.write_text(PASS.replace('VAL: PASS\n', '') + 'Simplicity: none\nDesign: none\n')
    code, message = lint_file(path)
    assert code == int(required)
    if required:
        assert 'class-sweep' in message


@pytest.mark.parametrize('tool', ['Write', 'Edit', 'MultiEdit', 'NotebookEdit', 'Bash'])
def test_write_outside_workspace_is_irrelevant(tmp_path, tool):
    from wuwei.guards.verdict import check_write
    (tmp_path / '.wuwei').rmdir()
    assert check_write({'cwd': str(tmp_path), 'tool_name': tool, 'tool_input': []}) == (0, '')


@pytest.mark.parametrize('tool,key', [('Write', 'file_path'), ('Edit', 'file_path'),
                                    ('MultiEdit', 'file_path'), ('NotebookEdit', 'notebook_path')])
@pytest.mark.parametrize('filename,code', [('DECISIONS/GATE-item.MD', 1), ('notes/other.md', 0)])
def test_gate_target_finds_workspace_outside_cwd(tmp_path, tool, key, filename, code):
    from wuwei.guards.verdict import check_write
    from wuwei.workspace import day_dir
    path = tmp_path / filename
    path.parent.mkdir()
    path.write_text('Verdict: FIX')
    result, message = check_write({'cwd': str(tmp_path.parent), 'tool_name': tool,
                                   'tool_input': {key: str(path)}})
    assert result == code
    if code:
        assert 'file:line' in message
        event, = (day_dir(tmp_path) / 'events.jsonl').read_text().splitlines()
        assert json.loads(event)['payload']['file'] == str(path)


@pytest.mark.parametrize('filename', ['DECISIONS/GATE-ARCH.MD', 'Decisions/Gate-Item.md'])
def test_gate_path_matching_ignores_case(tmp_path, filename):
    from wuwei.guards.verdict import check_write
    path = tmp_path / filename
    path.parent.mkdir()
    path.write_text('Verdict: FIX')
    assert check_write({'cwd': str(tmp_path), 'tool_input': {'file_path': str(path)}})[0] == 1


def test_notebook_path_is_linted(tmp_path):
    from wuwei.guards.verdict import check_write
    path = tmp_path / 'decisions/gate-arch.md'
    path.parent.mkdir()
    path.write_text('Verdict: FIX')
    assert check_write({'cwd': str(tmp_path), 'tool_name': 'NotebookEdit',
                        'tool_input': {'notebook_path': str(path)}})[0] == 1


@pytest.mark.parametrize('command', [
    'cat > decisions/gate-arch.md',
    'cp source decisions/gate-arch.md',
    "bash -c 'cat > decisions/gate-arch.md'",
    '(cat > decisions/gate-arch.md)',
    'env command cp source decisions/gate-arch.md',
    'cat > DECISIONS/GATE-ARCH.MD',
    'cd {day}/decisions && cat > gate-arch.md',
    '(cd {day} && cat > decisions/gate-arch.md)',
    'd={day}/decisions; cat > "$d/gate-arch.md"',
    'f={day}/decisions/gate-arch.md; cat > "$f"',
])
def test_bash_gate_writes_reach_lint(tmp_path, monkeypatch, capsys, command):
    from wuwei.__main__ import main
    from wuwei.workspace import day_dir
    command = command.format(day=day_dir(tmp_path))
    path = day_dir(tmp_path) / 'decisions/GaTe-ARCH.Md'
    path.parent.mkdir(parents=True)
    path.write_text('Verdict: FIX')
    payload = {'cwd': str(tmp_path), 'tool_name': 'Bash', 'tool_input': {'command': command},
               'hook_event_name': 'PostToolUse', 'session_id': 'seat', 'transcript_path': 'unused'}
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(payload)))
    assert main(['hook', 'PostToolUse']) == 2
    assert 'file:line' in capsys.readouterr().err


@pytest.mark.parametrize('command,code', [
    ("echo 'unclosed", 0),
    ('python -c "print(42)"', 0),
    ('cat > decisions/gate-missing.md', 0),
    ('cat > decisions/gate-arch.md', 0),
    ("python -c \"open('decisions/gate-arch.md', 'w')\"", 1),
    ("env python3 -c \"open('decisions/gate-arch.md', 'w')\"", 1),
    ("node -e \"write('decisions/gate-arch.md')\"", 1),
    ("perl -e \"print 'decisions/gate-arch.md'\"", 1),
    ("echo 'decisions/gate-arch.md", 0),
    ("python -c \"open('gate-arch.md', 'w')\"", 1),
])
def test_bash_relevance_and_opaque_commands(tmp_path, command, code):
    from wuwei.guards.verdict import check_write
    path = tmp_path / 'decisions/gate-arch.md'
    path.parent.mkdir()
    path.write_text(VALID)
    result, message = check_write({'cwd': str(tmp_path), 'tool_name': 'Bash',
                                   'tool_input': {'command': command}})
    assert result == code
    if code == 1:
        assert 'opaque' in message


def test_bash_lints_every_daily_gate_even_when_not_named(tmp_path):
    from wuwei.guards.verdict import check_write
    from wuwei.workspace import day_dir
    directory = day_dir(tmp_path) / 'decisions'
    directory.mkdir(parents=True)
    for name, text in [('gate-first.md', 'Verdict: FIX'), ('gate-second.md', 'Verdict: FIX'),
                       ('gate-clean.md', VALID)]:
        (directory / name).write_text(text)
    (directory / 'other.md').write_text('not a verdict')
    command = 'echo GATE-unrelated > out.txt'  # #616: a bare echo is a read
    assert check_write({'cwd': str(tmp_path), 'tool_name': 'Bash',
                        'tool_input': {'command': command}})[0] == 1
    records = [json.loads(line) for line in (day_dir(tmp_path) / 'events.jsonl').read_text().splitlines()]
    assert [r['payload']['file'] for r in records] == [str(directory / 'gate-first.md'),
                                                     str(directory / 'gate-second.md')]


@pytest.mark.parametrize('command', ['echo gate-item > out.txt', 'python -c "print(\'gate-item\')"'])
def test_daily_gate_scan_records_findings_and_unreadable_files(tmp_path, command):
    from wuwei.guards.verdict import check_write
    from wuwei.workspace import day_dir
    directory = day_dir(tmp_path) / 'decisions'
    directory.mkdir(parents=True)
    (directory / 'gate-bad.md').write_text('Verdict: FIX')
    (directory / 'gate-unreadable.md').write_bytes(b'\xff')
    code, message = check_write({'cwd': str(tmp_path), 'tool_name': 'Bash',
                                 'tool_input': {'command': command}})
    assert code == 2
    assert 'file:line' in message and 'could not read' in message
    records = [json.loads(line) for line in (day_dir(tmp_path) / 'events.jsonl').read_text().splitlines()]
    assert {str(path) for path in directory.iterdir()} <= {r['payload']['file'] for r in records}


@pytest.mark.parametrize('entry', ['cli', 'hook'])
@pytest.mark.parametrize('contents', ['Verdict: FIX', None])
def test_lint_rejections_append_events(tmp_path, monkeypatch, entry, contents):
    from wuwei.__main__ import main
    from wuwei.guards.verdict import check_write
    from wuwei.workspace import day_dir
    path = tmp_path / 'decisions/gate-arch.md'
    path.parent.mkdir()
    if contents is not None:
        path.write_text(contents)
    if entry == 'cli':
        assert main(['verdict', 'lint', str(path)]) != 0
    else:
        assert check_write({'cwd': str(tmp_path), 'tool_input': {'file_path': str(path)}})[0] != 0
    event, = [json.loads(line) for line in (day_dir(tmp_path) / 'events.jsonl').read_text().splitlines()]
    assert event['kind'] == 'verdict.rejected'
    assert event['payload']['file'] == str(path)
    assert event['payload']['reasons']


def test_rejection_event_failure_is_unrun(tmp_path, monkeypatch):
    from wuwei import state
    from wuwei.verdict import lint_file
    path = tmp_path / 'gate-arch.md'
    path.write_text('Verdict: FIX')
    def fail(*args, **kwargs):
        raise OSError('event unavailable')
    monkeypatch.setattr(state, 'append_event', fail)
    code, message = lint_file(path)
    assert code == 2
    assert 'event unavailable' in message


@pytest.mark.parametrize('marker', ['1.', '1)', '[F2]', 'F2 (', 'F2:', 'F2.'])
def test_finding_marker_with_separate_severity_row(marker):
    from wuwei.verdict import lint
    extra = (marker + ' second finding\nSeverity: P2\nFile: cli/other.py:3\n'
             'Scenario: fails when retried\nblocks: no\n')
    assert lint(VALID.replace(FINDING, FINDING + extra))[0] == 0
    code, message = lint(VALID.replace(FINDING, FINDING + extra.replace('cli/other.py:3', 'missing')))
    assert code == 1
    assert 'finding 2: missing file:line' in message


def test_python_script_with_named_gate_is_linted(tmp_path):
    from wuwei.guards.verdict import check_write
    from wuwei.workspace import day_dir
    path = day_dir(tmp_path) / 'decisions/gate-arch.md'
    path.parent.mkdir(parents=True)
    path.write_text(VALID)
    payload = {'cwd': str(tmp_path), 'tool_name': 'Bash',
               'tool_input': {'command': 'python script.py decisions/gate-arch.md'}}
    assert check_write(payload)[0] == 0
    path.write_text('Verdict: FIX')
    code, message = check_write(payload)
    assert code == 1
    assert 'file:line' in message


def test_bash_quoted_gate_path_with_spaces(tmp_path):
    from wuwei.guards.verdict import check_write
    from wuwei.workspace import day_dir
    path = day_dir(tmp_path) / 'decisions/gate-an item-arch.md'
    path.parent.mkdir(parents=True)
    path.write_text('Verdict: FIX')
    code, message = check_write({'cwd': str(tmp_path), 'tool_name': 'Bash',
                                'tool_input': {'command': f'cat > "{path}"'}})
    assert code == 1
    assert 'file:line' in message


def bash_post(tmp_path, command, role=''):
    """A recorded PostToolUse Bash payload through check_write, with the events it appended."""
    from wuwei.guards.verdict import check_write
    from wuwei.workspace import day_dir
    events = day_dir(tmp_path) / 'events.jsonl'
    before = events.read_text().splitlines() if events.exists() else []
    result = check_write({'cwd': str(tmp_path), 'tool_name': 'Bash', 'hook_event_name': 'PostToolUse',
                          'agent_type': role, 'tool_input': {'command': command}})
    after = events.read_text().splitlines() if events.exists() else []
    return result, [json.loads(line) for line in after[len(before):]]


@pytest.mark.parametrize('command', ['cat {gate}', 'grep -n Verdict {gate}', 'shasum -a 256 {gate}',
                                     'cd {day} && sha256sum decisions/gate-a-quality.md | head -1'])
def test_invariant_read_only_bash_never_lints(tmp_path, command):
    # #616 (proposed design 9.2 I26): a Bash call that only reads a gate file is not a gate
    # write: it is not linted and records no verdict.rejected event.
    from wuwei.workspace import day_dir
    gate = day_dir(tmp_path) / 'decisions/gate-a-quality.md'
    gate.parent.mkdir(parents=True)
    gate.write_text('Verdict: FIX')
    assert bash_post(tmp_path, command.format(gate=gate, day=day_dir(tmp_path)),
                     'wuwei:sentinel-quality') == ((0, ''), [])


def test_invariant_bash_write_lints_by_file_name(tmp_path):
    # #616 (proposed design 9.2 I26): a Bash call that can write lints each gate file with the
    # role its own name implies, never the caller's.
    from wuwei.verdict import lint_file
    from wuwei.workspace import day_dir
    directory = day_dir(tmp_path) / 'decisions'
    directory.mkdir(parents=True)
    quality, security = directory / 'gate-a-quality.md', directory / 'gate-a-security.md'
    quality.write_text('Verdict: FIX')
    for command in (f'cp x {quality}', f'cat x > {quality}'):
        (code, message), events = bash_post(tmp_path, command)
        assert code == 1 and 'file:line' in message
        assert [e['payload']['file'] for e in events if e['kind'] == 'verdict.rejected'] == [str(quality)]
    quality.write_text(VALID + 'Simplicity: none\nDesign: none\n')
    security.write_text(PASS)
    assert lint_file(security, role='sentinel-quality')[0] == 1  # the quality rules would refuse it
    assert bash_post(tmp_path, f'cp x {security}', 'wuwei:sentinel-quality') == ((0, ''), [])
    (code, message), _ = bash_post(tmp_path, "python3 -c \"open('gate-a-security.md', 'w')\"")
    assert code == 1 and 'opaque' in message


@pytest.fixture
def registered_stop(tmp_path):
    (tmp_path / '.wuwei/config.toml').write_text('')
    from wuwei import state
    from wuwei.workspace import day_dir
    directory = day_dir(tmp_path)
    relative = (directory / 'briefs/review-1.md').relative_to(tmp_path).as_posix()
    state._write_state(lambda data: data.update(seats={'review-1': {
        'id': 'review-1', 'role': 'sentinel-quality', 'item': 'X',
        'brief': relative, 'status': 'stopped'}}), tmp_path, reserved=False)
    transcript = tmp_path / 'agent.jsonl'
    transcript.write_text(json.dumps({'type': 'user', 'message': {
        'content': [{'type': 'text', 'text': 'WUWEI brief: ' + relative}]}}) + '\n')
    path = directory / 'decisions/gate-review-1.md'
    path.parent.mkdir()
    path.write_text(PASS + 'Simplicity: none\nDesign: none\n')
    return {'cwd': str(tmp_path), 'hook_event_name': 'SubagentStop',
            'agent_id': 'runtime-id', 'agent_type': 'wuwei:sentinel-quality',
            'agent_transcript_path': str(transcript), 'stop_hook_active': False}, path


@pytest.mark.parametrize('case,code,hint', [
    ('security', 0, ''), ('same-role', 0, ''), ('prefix', 0, ''),
    ('missing-row', 1, 'Design:'), ('unreadable', 2, 'could not read'),
    ('missing-file', 0, ''), ('missing-transcript', 2, 'agent_transcript_path'),
    ('bad-transcript', 2, 'verdict lint'), ('no-reservation', 2, 'reservation'),
    ('wrong-role', 2, 'role'), ('next-day', 0, ''), ('outside', 0, ''),
    ('builder', 0, ''), ('active', 0, ''), ('outside-override', 0, ''),
    ('worktree', 1, 'Design:'),
])
def test_stop_lints_only_registered_seat(registered_stop, tmp_path, monkeypatch, case, code, hint):
    from pathlib import Path
    from wuwei import state
    from wuwei.guards.verdict import check_write
    payload, path = registered_stop
    if case == 'security':
        (path.parent / 'gate-security.md').write_text(PASS)
    if case == 'same-role':
        (path.parent / 'gate-other-quality.md').write_text(PASS)
    if case == 'prefix':
        (path.parent / 'gate-review-10.md').write_text('invalid')
    if case in ('missing-row', 'active'):
        path.write_text(PASS + 'Simplicity: none\n')
    if case == 'unreadable':
        path.write_bytes(b'\xff')
    if case == 'missing-file':
        path.unlink()
    if case == 'missing-transcript':
        del payload['agent_transcript_path']
    if case == 'bad-transcript':
        Path(payload['agent_transcript_path']).write_text('{}\n{broken')
    if case == 'no-reservation':
        state._write_state(lambda data: data.update(seats={}), tmp_path, reserved=False)
    if case == 'wrong-role':
        payload['agent_type'] = 'sentinel-security'
    if case == 'next-day':
        monkeypatch.setenv('WUWEI_NOW', '2099-01-01T00:01:00+00:00')
        other = tmp_path / '.wuwei/days/2099-01-01/decisions/gate-review-1.md'
        other.parent.mkdir(parents=True)
        other.write_text('invalid')
    if case in ('outside', 'outside-override', 'worktree'):
        outside = tmp_path.parent / (tmp_path.name + '-outside')
        outside.mkdir()
        payload['cwd'] = str(outside)
        if case == 'worktree':
            (outside / '.git').mkdir()
            (outside / '.git/wuwei-workspace').write_text(str(tmp_path))
            path.write_text(PASS + 'Simplicity: none\n')
        else:
            del payload['agent_transcript_path']
        if case == 'outside-override':
            monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    if case == 'builder':
        payload['agent_type'] = 'builder'
        del payload['agent_transcript_path']
    if case == 'active':
        payload['stop_hook_active'] = True
    result, message = check_write(payload)
    assert result == code, message
    assert hint in message
    if case in ('missing-row', 'unreadable', 'worktree'):
        assert path.name in message
    records = [json.loads(line) for line in
               (path.parent.parent / 'events.jsonl').read_text().splitlines()]
    rejected = [row['payload']['file'] for row in records if row['kind'] == 'verdict.rejected']
    if case in ('missing-row', 'unreadable', 'active', 'worktree'):
        assert rejected == [str(path)]
    elif not code:
        assert rejected == []


ASSUMPTION = ('Assumption: medium specs/x/spec.md:12 assumed one process; '
              'would break when two processes share it; blocks: no\n')
ASSUMED = 'Verdict: FIX\nHead: abc1234\n' + ASSUMPTION + 'Probe: not run\nVAL: PASS\n' + RETRO


def test_assumption_is_a_finding_kind():
    from wuwei.verdict import lint
    code, message = lint(ASSUMED)
    assert code == 1 and 'FIX verdict but no blocking finding parsed' in message
    assert lint(ASSUMED.replace('FIX', 'PASS')) == (0, 'OK: PASS')
    code, message = lint(ASSUMED.replace('would break when two processes share it; ', ''))
    assert code == 1 and 'finding 1: missing failure scenario' in message
    code, message = lint('Verdict: FIX\nHead: abc1234\nAssumptions: reviewed\nProbe: not run\n' + RETRO)
    assert code == 1 and 'no finding with severity' in message


def reproduced(first, second):
    """#677: the shape of a real quality verdict, ids before the severity."""
    return ('Verdict: FIX\nHead: abc1234\n\n## Blocking findings\n\n'
            f'{first} Severity: medium. File: src/a.py:80. blocks: yes.\n'
            'The retry loop never stops.\nFailure scenario: a dropped socket would hang.\n\n'
            f'{second} Severity: high. File: src/b.py:9. blocks: yes.\n'
            'Failure scenario: an empty file would crash the reader.\n\n'
            '## Non-blocking findings\n\n'
            'N1. Severity: low. File: src/c.py:5. blocks: no.\nFailure scenario: would log twice.\n\n'
            + ASSUMPTION + '\nProbe: not run\nVAL: PASS\n' + RETRO
            + 'Simplicity: none\nDesign: none\n')


@pytest.mark.parametrize('role,first,second', [
    ('sentinel-arch', 'A1.', 'A2.'), ('sentinel-quality', 'Q1.', 'Q2.'),
    ('sentinel-security', 'S1.', 'S2.'), ('sentinel-goal', 'G1.', 'G2.'),
    ('sentinel-quality', 'F1.', 'F2.'), ('sentinel-quality', '[Q1]', '[Q2]'),
    ('sentinel-quality', 'Finding 1.', 'Finding 2.')])
def test_every_role_id_starts_a_finding(tmp_path, role, first, second):
    from wuwei.verdict import active_text, finding_blocks, lint_file
    text = reproduced(first, second)
    blocks = finding_blocks(active_text(text))
    for block, start in zip(blocks, (first, second, 'N1.', 'Assumption:')):
        assert block.startswith(start)
    assert len(blocks) == 4
    assert all('blocks: yes' in block for block in blocks[:2])
    path = tmp_path / 'decisions/gate-item.md'
    path.parent.mkdir()
    path.write_text(text)
    assert lint_file(path, role=role) == (0, 'OK: FIX')


HEADING_FIX = ('Verdict: FIX\nHead: abc1234\n### Q1 high\n'
               'The cache in src/a.py:80 is never cleared, so a reload would serve stale data; blocks: yes\n'
               + ASSUMPTION + 'Probe: not run\nVAL: PASS\n' + RETRO)


def test_fix_without_parsed_blocking_finding_is_refused():
    from wuwei.verdict import lint
    code, message = lint(HEADING_FIX)
    assert code == 1
    assert ('FIX verdict but no blocking finding parsed; the lines that look like findings are: '
            'The cache in src/a.py:80') in message
    code, message = lint(VALID.replace('blocks: yes', 'blocks: no'))
    assert code == 1 and 'findings are: none' in message and 'Verdict: PASS' in message
    fenced = HEADING_FIX.replace('Probe:', '```\n- P1 | x.py:1 | example | blocks: yes\n```\nProbe:')
    assert 'x.py:1' not in lint(fenced)[1]
    for other in ('PARK', 'ESCALATE'):
        assert 'FIX verdict' not in lint(HEADING_FIX.replace('FIX', other))[1]
    assert 'FIX verdict' not in lint(VALID.replace('FIX', 'PASS').replace('yes', 'no'))[1]


def test_write_guard_refuses_fix_without_parsed_blocker(tmp_path):
    from wuwei.guards.verdict import check_write
    path = tmp_path / 'decisions/gate-arch.md'
    path.parent.mkdir()
    path.write_text(HEADING_FIX)
    code, message = check_write({'cwd': str(tmp_path), 'tool_name': 'Write',
                                 'tool_input': {'file_path': str(path), 'content': HEADING_FIX}})
    assert code == 1 and 'FIX verdict but no blocking finding parsed' in message
QUALITY_FIX = VALID + 'Simplicity: none\nDesign: none\n'
DOCS_REJECTED = ['the docs value is missing', 'Docs value: missing', 'docs path not recorded',
                 'no docs value was set', 'DOC: required; value missing']
DOCS_ACCEPTED = ['the docs path docs/x.md is missing the --json flag',
                 'docs value none is wrong for a changed command', 'the return value missing a zone']


def docs_finding(text):
    return QUALITY_FIX.replace('fails when input is empty', f'{text}; fails when input is empty')


@pytest.mark.parametrize('text,code', [(text, 1) for text in DOCS_REJECTED] + [(text, 0) for text in DOCS_ACCEPTED])
def test_lint_refuses_a_recorded_docs_value_called_missing(text, code):
    # #667: a gate never calls a recorded docs value missing.
    from wuwei.verdict import lint
    result, message = lint(docs_finding(text), quality=True, class_sweep=True, docs=('X', 'docs/x.md'))
    assert result == code, message
    if code:
        assert ('finding 1: says the docs value is missing, but X records docs docs/x.md '
                '(bin/wuwei why X --json)') in message
    assert lint(docs_finding(text), quality=True, class_sweep=True)[0] == 0


def test_lint_file_reads_the_docs_value_at_lint_time(tmp_path, monkeypatch):
    from wuwei import state, verdict, workspace
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00Z')
    config = tmp_path / '.wuwei/config.toml'
    config.write_text('[docs]\nsystem = "notion"\n')
    state._write_state(lambda data: data.update(
        items={'A': {'phase': 'gate', 'status': 'running', 'gates': {'tier': 'standard'}}},
        seats={'quality-1': {'item': 'A', 'role': 'sentinel-quality', 'status': 'stopped'}}),
        tmp_path, reserved=False)
    decisions = workspace.day_dir(tmp_path) / 'decisions'
    decisions.mkdir()
    path, unknown = decisions / 'gate-quality-1.md', decisions / 'gate-unknown-1.md'
    for file in (path, unknown):
        file.write_text(docs_finding('the docs value is missing'))
    lint = lambda file: verdict.lint_file(file, role='sentinel-quality', root=tmp_path)
    assert lint(path)[0] == 0
    state._write_state(lambda data: data['items']['A'].update(docs={'value': 'docs/a.md', 'reason': ''}),
                       tmp_path, reserved=False)
    code, message = lint(path)
    assert code == 1 and 'A records docs docs/a.md' in message
    assert lint(unknown)[0] == 0
    config.write_text('[docs]\nsystem = "none"\n')
    assert lint(path)[0] == 0
