"""Guard tables inspect payloads in-process and never execute shell input."""

import io
import json
import shlex
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    root = tmp_path / 'workspace'
    (root / '.wuwei/days/2026-09-28').mkdir(parents=True)
    (root / 'inside').mkdir()
    (root / 'state.json').write_text('{}')
    day = root / '.wuwei/days/2026-09-28'
    (day / 'state.json').write_text('{}')
    (day / 'inside').mkdir()
    (day / 'alias').symlink_to(day / 'state.json')
    (root / 'alias').symlink_to(day / 'state.json')
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    monkeypatch.delenv('CDPATH', raising=False)
    from fakes.integrity import seed
    seed(root)
    (root / '.wuwei/config.toml').write_text('')
    return root


def payload(root, tool, **tool_input):
    return {'hook_event_name': 'PreToolUse', 'session_id': 'fixture',
            'transcript_path': str(root / 'transcript.jsonl'), 'cwd': str(root),
            'tool_name': tool, 'tool_input': tool_input}


@pytest.mark.parametrize('tool', ['Write', 'Edit'])
@pytest.mark.parametrize('path,code', [
    ('state.json', 0), ('events.jsonl', 0),
    ('.wuwei/days/2026-09-28/state.json', 1),
    ('.wuwei/days/2020-01-01/events.jsonl', 1),
    ('inside/../state.json', 0), ('alias', 1),
    ('notes.md', 0), ('state.json.bak', 0),
    ('', 2), (None, 2), (123, 2), ('bad\0path', 2),
])
def test_file_guard(workspace, tool, path, code):
    from wuwei.guards.protect_state import check_file
    result, reason = check_file(payload(workspace, tool, file_path=path))
    assert result == code
    if code:
        assert reason
    if code == 1:
        assert 'CLI' in reason


@pytest.mark.parametrize('script,code', [
    ('echo data > state.json', 1), ('>>events.jsonl', 1),
    ('cat <>state.json', 1), ('echo data &>>state.json', 1),
    ('echo data >alias', 1), ('(echo data) >events.jsonl', 1),
    ('tee state.json', 1), ('tee -a -- events.jsonl', 1),
    ('cp source state.json', 1), ('cp -- source events.jsonl', 1),
    ('cp state.json inside', 0), ('cp -t inside state.json', 0),
    ('cp --target-directory=inside state.json', 0), ('cp -tinside state.json', 0),
    ('mv state.json backup', 1), ('mv source events.jsonl', 1),
    ("sed -i 's/a/b/' state.json", 1), ("sed -i.bak 's/a/b/' events.jsonl", 1),
    ("sed -Ei 's/a/b/' state.json", 1), ("sed --in-place 's/a/b/' state.json", 1),
    ('dd if=input of=state.json', 1), ('truncate -s 0 state.json', 1),
    ('truncate --size=0 events.jsonl', 1),
    ('cat state.json', 0), ('cat <state.json', 0), ('cp state.json backup', 0),
    ("sed 's/a/b/' state.json", 0), ('dd if=state.json of=backup', 0),
    ('echo data >notes.md', 0), ('tee notes.md', 0), ('cp source notes.md', 0),
    ('mv notes.md backup', 0), ('truncate -s0 notes.md', 0),
    ('bin/wuwei state show', 0), ('python3 -P -m wuwei state show', 0),
    ('python3 -c \'open("state.json", "w")\'', 2),
    ('node -e \'writeFileSync("events.jsonl", "")\'', 2),
    ('tee "$FILE"', 2), ('cp source *.json', 1), ('xargs tee', 0),
    ('echo data >', 0), ('echo "unterminated', 0),
    ('cp --unknown source destination', 0), ('cp -r inside backup', 0),
    ('', 0), (None, 2), (42, 2),
])
def test_shell_state_guard(workspace, script, code):
    from wuwei.guards.protect_state import check_bash
    result, reason = check_bash(payload(workspace / '.wuwei/days/2026-09-28', 'Bash', command=script))
    assert result == code, reason
    if code:
        assert reason
    if code == 1:
        assert 'CLI' in reason


@pytest.mark.parametrize('wrapper', [
    '{}', 'command {}', 'exec {}', 'env MODE=test {}', 'MODE=test {}',
    'sh -c {}', 'bash -lc {}', 'zsh -c {}', '({})', 'echo input | {}',
])
@pytest.mark.parametrize('script', ['tee state.json', 'echo data >events.jsonl'])
def test_wrapped_state_writes(workspace, wrapper, script):
    from wuwei.guards.protect_state import check_bash
    script = script.replace('state.json', '.wuwei/days/2026-09-28/state.json').replace(
        'events.jsonl', '.wuwei/days/2026-09-28/events.jsonl')
    if '-c' in wrapper or '-lc' in wrapper:
        script = shlex.quote(script)
    code, reason = check_bash(payload(workspace, 'Bash', command=wrapper.format(script)))
    assert code == 1, reason


@pytest.mark.parametrize('tool_input', [None, [], {}, {'file_path': ''}])
def test_malformed_file_input(workspace, tool_input):
    from wuwei.guards.protect_state import check_file
    value = payload(workspace, 'Edit')
    value['tool_input'] = tool_input
    assert check_file(value)[0] == 2


@pytest.mark.parametrize('script,code', [
    ('cd {outside} && git status', 1), ('(cd {outside} && git status)', 0),
    ('cd inside && git status', 0), ('cd -- inside', 0), ('cd -P inside', 0),
    ('cd ..', 1), ('cd {root}', 0), ('cd {prefix}', 1),
    ('cd escape', 1), ('cd inside; cd ../..', 1),
    ('command cd {outside}', 1), ('exec cd {outside}', 1),
    ('env MODE=test cd {outside}', 1), ('eval "cd {outside}"', 1),
    ("sh -c 'cd {outside} && git status'", 0),
    ("bash -lc 'cd {outside} && git status'", 0),
    ('cd {outside} &', 0), ('(cd {outside}); cd inside', 0),
    ('git -C {outside} status', 0),
    ('cd', 1), ('HOME={root} cd', 0), ('HOME={outside} cd', 1),
    ('cd -', 1), ('OLDPWD={root} cd -', 0),
    ('CDPATH={outside} cd inside', 2), ('CDPATH={outside} cd ./inside', 0),
    ('WUWEI_WORKSPACE={outside} cd {outside}', 1),
    ('cd --unknown inside', 2), ('cd inside extra', 2), ('cd "$DEST"', 2),
])
def test_directory_guard(workspace, monkeypatch, script, code):
    from wuwei.guards.protect_state import check_bash
    outside = workspace.parent / 'other'
    outside.mkdir()
    (workspace / 'escape').symlink_to(outside, target_is_directory=True)
    monkeypatch.setenv('HOME', str(outside))
    monkeypatch.setenv('OLDPWD', str(outside))
    command = script.format(root=shlex.quote(str(workspace)),
                            outside=shlex.quote(str(outside)),
                            prefix=shlex.quote(str(workspace) + '-other'))
    result, reason = check_bash(payload(workspace, 'Bash', command=command))
    assert result == code, reason
    if code:
        assert reason
    if code == 1:
        assert 'git -C' in reason and 'subshell' in reason


@pytest.mark.parametrize('script', ['cd .', 'cd inside'])
def test_missing_workspace_allows(tmp_path, monkeypatch, script):
    from wuwei.guards.protect_state import check_bash
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    assert check_bash(payload(tmp_path, 'Bash', command=script))[0] == 0


@pytest.mark.parametrize('script', ['cd inside; echo data >moved_alias',
                                    '(cd inside; tee moved_alias)',
                                    "sh -c 'cd inside; cp source moved_alias'"])
def test_writes_after_cd_resolve_aliases(workspace, script):
    from wuwei.guards.protect_state import check_bash
    (workspace / 'inside/moved_alias').symlink_to(workspace / '.wuwei/days/2026-09-28/state.json')
    code, reason = check_bash(payload(workspace, 'Bash', command=script))
    assert code == 1, reason


@pytest.mark.parametrize('tool,tool_input,expected', [
    ('Edit', {'file_path': '.wuwei/days/2026-09-28/state.json'}, 2),
    ('Write', {'file_path': 'notes.md'}, 0),
    ('Bash', {'command': 'tee .wuwei/days/2026-09-28/events.jsonl'}, 2),
    ('Bash', {'command': 'cd ..'}, 0),
    ('Bash', {'command': '(cd .. && git status)'}, 0),
    ('Bash', {'command': 'echo "unterminated'}, 0),
])
def test_discovered_guards_through_hook(workspace, monkeypatch, capsys, tool, tool_input, expected):
    from wuwei.commands.hook import run
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(payload(workspace, tool, **tool_input))))
    assert run(SimpleNamespace(event='PreToolUse')) == expected
    captured = capsys.readouterr()
    if expected:
        result = json.loads(captured.out)['hookSpecificOutput']
        assert result['permissionDecision'] == 'deny'
        assert result['permissionDecisionReason'] in captured.err
    else:
        assert not captured.out and not captured.err


@pytest.mark.parametrize('script', [
    'HOME=..; cd', 'export HOME=..; cd', 'CDPATH=..; cd other',
    "printf 'state.json' | xargs command tee",
    "printf 'state.json' | xargs -I SAFE sh -c 'tee SAFE'",
    "python3 -c 'open(__import__(\"sys\").argv[1], \"w\")' state.json",
])
def test_additional_bypasses_fail_closed(workspace, monkeypatch, script):
    from wuwei.guards.protect_state import check_bash
    monkeypatch.setenv('HOME', str(workspace))
    code, reason = check_bash(payload(workspace, 'Bash', command=script))
    assert code == 2, reason


@pytest.mark.parametrize('value', [None, '', 'relative', 42])
def test_invalid_cwd_fails_closed(workspace, value):
    from wuwei.guards.protect_state import check_bash, check_file
    for check, tool, fields in [(check_bash, 'Bash', {'command': 'pwd'}),
                                (check_file, 'Edit', {'file_path': 'notes.md'})]:
        item = payload(workspace, tool, **fields)
        item['cwd'] = value
        assert check(item)[0] == 2


@pytest.mark.parametrize('script,expected', [('t{e,e}e state.json', 2), ('c{d,d} ..', 0)])
def test_expanding_program_name_blocks(workspace, script, expected):
    from wuwei.guards.protect_state import check_bash
    assert check_bash(payload(workspace, 'Bash', command=script))[0] == expected


@pytest.mark.parametrize('path,expected', [
    ('state.json', 0), ('events.jsonl', 0), ('inside/state.json', 0),
    ('.wuwei/state.json', 0), ('.wuwei/days/day/sub/state.json', 0),
    ('.wuwei/archive/day/notes.md', 1),
    ('.WUWEI/DAYS/day/STATE.JSON', 1), ('.wuwei/days/day/EVENTS.JSONL', 1),
    ('.WUWEI/ARCHIVE/day/notes.md', 1),
])
def test_review_path_scope(workspace, path, expected):
    from wuwei.guards.protect_state import check_file
    assert check_file(payload(workspace, 'Write', file_path=path))[0] == expected


@pytest.mark.parametrize('tool', ['Write', 'Edit', 'MultiEdit', 'NotebookEdit', 'Bash'])
@pytest.mark.parametrize('protected', ['.wuwei/days/2026-09-28/state.json',
                                      '.wuwei/config.toml',
                                      '.wuwei/archive/day/notes.md'])
def test_review_hardlink_alias(workspace, tool, protected, monkeypatch, capsys):
    target = workspace / protected
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('{}')
    alias = workspace / 'hardlink'
    alias.hardlink_to(target)
    fields = ({'command': 'truncate -s0 hardlink'} if tool == 'Bash' else
              {'notebook_path' if tool == 'NotebookEdit' else 'file_path': 'hardlink'})
    from wuwei.commands.hook import run
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(payload(workspace, tool, **fields))))
    assert run(SimpleNamespace(event='PreToolUse')) == 2
    assert json.loads(capsys.readouterr().out)['hookSpecificOutput']['permissionDecision'] == 'deny'


@pytest.mark.parametrize('tool', ['Write', 'Edit', 'MultiEdit', 'NotebookEdit', 'Bash'])
@pytest.mark.parametrize('target', ['.wuwei/config.toml', 'inside/../.wuwei/config.toml', 'config-alias'])
def test_config_is_protected(workspace, tool, target):
    from wuwei.guards.protect_state import check_bash, check_file
    (workspace / 'config-alias').symlink_to(workspace / '.wuwei/config.toml')
    fields = ({'command': 'echo x >> ' + target} if tool == 'Bash' else
              {'notebook_path' if tool == 'NotebookEdit' else 'file_path': target})
    check = check_bash if tool == 'Bash' else check_file
    code, reason = check(payload(workspace, tool, **fields))
    assert code == 1
    assert 'owner' in reason and 'outside agent tools' in reason


@pytest.mark.parametrize('tool', ['Write', 'Bash'])
def test_calibration_snapshot_is_protected(workspace, tool):
    from wuwei.guards.protect_state import check_bash, check_file
    target = '.wuwei/calibration.json'
    if tool == 'Bash':
        code, reason = check_bash(payload(workspace, tool, command='echo {} | tee ' + target))
    else:
        code, reason = check_file(payload(workspace, tool, file_path=target))
    assert code == 1 and 'outside agent tools' in reason


@pytest.mark.parametrize('script,expected', [
    ("sed -i 's/a/b/' .wuwei/config.toml", 1),
    ("sh -c 'echo x >> .wuwei/config.toml'", 1),
    ('cd .wuwei; tee -a config.toml', 1),
    ('cat .wuwei/config.toml', 0),
    ('echo x >> config.toml', 0),
])
def test_config_shell_writes(workspace, script, expected):
    from wuwei.guards.protect_state import check_bash
    assert check_bash(payload(workspace, 'Bash', command=script))[0] == expected


@pytest.mark.parametrize('script,expected', [
    ('npm run build > events.jsonl', 0), ('echo x > state.json', 0),
    ('echo x >! {state}', 1), ('echo x >>! {state}', 1),
    ('rm {state}', 1), ('chmod 777 {state}', 1), ('touch {state}', 1),
    ('custom-writer --output={state}', 1), ('rsync source {state}', 1),
    ('rsync --remove-source-files {state} backup', 1),
    ('cat {state}', 0), ('head {state}', 0), ('tail {state}', 0),
    ('less {state}', 0), ('jq . {state}', 0), ('grep x {state}', 0), ('wc {state}', 0),
    ("sed 's/a/b/' {state}", 0), ('cp -a {state} backup', 0),
    ('dd if={state} of=backup', 0), ('rsync -a {state} backup', 0),
    ('rm .wuwei/archive/day/notes.md', 1),
    ('pushd ..', 1), ('echo x | cd ..', 1), ('echo x | pushd ..', 1),
    ('echo x | popd', 2), ('popd', 2), ('(pushd ..)', 0), ('(popd)', 0),
    ('cd .. | cat', 0),
])
def test_review_shell_policy(workspace, script, expected):
    from wuwei.guards.protect_state import check_bash
    script = script.format(state='.wuwei/days/2026-09-28/state.json')
    code, reason = check_bash(payload(workspace, 'Bash', command=script))
    assert code == expected, reason


@pytest.mark.parametrize('script', [
    'python3 -m pytest -q', 'python -m pip install x',
    'for f in a b; do echo $f; done', 'export FOO=1',
    'source .venv/bin/activate', 'echo $(date)', 'cp -a x y', 'cd ~',
])
def test_review_ordinary_commands_through_shim(workspace, monkeypatch, tmp_path, script):
    import os
    from pathlib import Path
    import subprocess
    monkeypatch.setenv('HOME', str(workspace))
    shim_path = tmp_path / 'bin'
    shim_path.mkdir()
    (shim_path / 'python3').symlink_to(sys.executable)
    monkeypatch.setenv('PATH', str(shim_path) + os.pathsep + os.environ['PATH'])
    result = subprocess.run([str(Path(__file__).resolve().parents[1] / 'bin/wuwei'),
                             'hook', 'PreToolUse'], text=True, capture_output=True,
                            input=json.dumps(payload(workspace, 'Bash', command=script)))
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('tool,fields,expected', [
    ('Write', {'file_path': 'state.json'}, 0),
    ('Bash', {'command': 'cd ..'}, 0), ('Bash', {'command': 'popd'}, 0),
    ('Bash', {'command': 'echo "unterminated state.json'}, 2),
])
@pytest.mark.parametrize('override', [False, True])
def test_review_outside_workspace(workspace, monkeypatch, tool, fields, expected, override):
    from wuwei.guards.protect_state import check_bash, check_file
    if override:
        monkeypatch.setenv('WUWEI_WORKSPACE', str(workspace))
    check = check_bash if tool == 'Bash' else check_file
    assert check(payload(workspace.parent, tool, **fields))[0] == expected


@pytest.mark.parametrize('program', ['cp', 'mv', 'rsync'])
def test_copy_into_day_directory_is_a_protected_write(workspace, program):
    from wuwei.guards.protect_state import check_bash
    assert check_bash(payload(workspace, 'Bash', command=(
        program + ' state.json .wuwei/days/2026-09-28')))[0] == 1


@pytest.mark.parametrize('script', [
    'echo $(date) > .wuwei/days/day/state.json',
    'for f in a b; do echo x > .wuwei/days/day/state.json; done',
    'echo "unterminated STATE.JSON', 'pushd "$DEST"',
])
def test_relevant_parse_errors_still_refuse(workspace, script):
    from wuwei.guards.protect_state import check_bash
    assert check_bash(payload(workspace, 'Bash', command=script))[0] == 2


@pytest.mark.parametrize('script', [
    'rsync -t source .wuwei/days/2026-09-28/state.json',
    'cp --backup state.json .wuwei/days/2026-09-28',
    'rm .wuwei/days/name=value/state.json',
])
def test_reader_exceptions_do_not_hide_write_targets(workspace, script):
    from wuwei.guards.protect_state import check_bash
    assert check_bash(payload(workspace, 'Bash', command=script))[0] != 0


@pytest.mark.parametrize('script', ['pushd', 'pushd +1',
    'rsync --remove-source-files state.json .wuwei/days/2026-09-28'])
def test_unresolved_stack_and_destructive_copy_refuse(workspace, monkeypatch, script):
    from wuwei.guards.protect_state import check_bash
    monkeypatch.setenv('HOME', str(workspace))
    assert check_bash(payload(workspace, 'Bash', command=script))[0] != 0


@pytest.mark.parametrize('override', [False, True])
@pytest.mark.parametrize('tool', ['Write', 'Edit', 'MultiEdit', 'NotebookEdit', 'Bash'])
@pytest.mark.parametrize('target', ['absolute', 'relative', 'symlink', 'future'])
def test_f8_protection_follows_target(workspace, monkeypatch, override, tool, target):
    from wuwei.guards.protect_state import check_bash, check_file
    cwd = workspace.parent
    state = workspace / '.wuwei/days/2026-09-28/state.json'
    (cwd / 'alias').symlink_to(state)
    paths = {'absolute': str(state), 'relative': 'workspace/.wuwei/days/2026-09-28/state.json',
             'symlink': 'alias', 'future': 'future/.wuwei/days/day/events.jsonl'}
    if override:
        monkeypatch.setenv('WUWEI_WORKSPACE', str(workspace))
    fields = ({'command': 'echo x > ' + shlex.quote(paths[target])} if tool == 'Bash' else
              {'notebook_path' if tool == 'NotebookEdit' else 'file_path': paths[target]})
    check = check_bash if tool == 'Bash' else check_file
    assert check(payload(cwd, tool, **fields))[0] == 1


@pytest.mark.parametrize('script,expected', [
    ('echo "unterminated .wuwei', 2),
    ('cd workspace; tee .wuwei/days/2026-09-28/state.json', 1),
    ('cd ..', 0), ('popd', 0), ('echo x > ordinary.json', 0),
])
def test_f8_bash_without_workspace(workspace, script, expected):
    from wuwei.guards.protect_state import check_bash
    assert check_bash(payload(workspace.parent, 'Bash', command=script))[0] == expected


@pytest.mark.parametrize('override,expected', [(False, 0), (True, 1)])
def test_f8_hardlink_scan_requires_known_root(workspace, monkeypatch, override, expected):
    from wuwei.guards.protect_state import check_file
    (workspace.parent / 'hardlink').hardlink_to(workspace / '.wuwei/days/2026-09-28/state.json')
    if override:
        monkeypatch.setenv('WUWEI_WORKSPACE', str(workspace))
    assert check_file(payload(workspace.parent, 'Write', file_path='hardlink'))[0] == expected


@pytest.mark.parametrize('outside', [False, True])
@pytest.mark.parametrize('script', [
    'echo x > "$FILE"', 'echo x > "$git"', 'echo x > "$gh"',
    'tee "$FILE"', 'cp source "$FILE"',
    'mv "$FILE" backup', 'dd of="$FILE"', 'truncate -s0 "$FILE"',
    'sed -i s/a/b/ "$FILE"', 'cp source *.json', 'mv *.json backup',
    'echo x > *.json',
    'echo x > $(printf alias)', 'echo x > `printf alias`',
    'echo $(date) | tee alias', 'cp $(printf source) alias',
    'mv `printf source` alias', 'dd of=$(printf alias)',
    'truncate -s0 $(printf alias)', 'sed -i s/a/b/ $(printf alias)',
    'ln -f $(printf source) alias', 'install $(printf source) alias',
    'rsync $(printf source) alias', 'rm $(printf alias)',
    'patch $(printf alias) patchfile',
    'for f in *.json; do echo x > "$f"; done',
    'for f in *.json; do tee "$f"; done',
    'for f in *.json; do cp source "$f"; done',
    'for f in *.json; do mv "$f" backup; done',
    'for f in *.json; do dd of="$f"; done',
    'for f in *.json; do truncate -s0 "$f"; done',
    'for f in *.json; do sed -i s/a/b/ "$f"; done',
    'for f in *.json; do ln -f source "$f"; done',
    'for f in *.json; do install source "$f"; done',
    'for f in *.json; do rsync source "$f"; done',
    'for f in *.json; do rm "$f"; done',
    'for f in *.json; do patch "$f" patchfile; done',
])
def test_f9_dynamic_writes_fail_closed(workspace, outside, script):
    from wuwei.guards.protect_state import check_bash
    cwd = workspace.parent if outside else workspace / '.wuwei/days/2026-09-28'
    expected = 0 if outside else (1 if script in ('cp source *.json', 'mv *.json backup') else 2)
    assert check_bash(payload(cwd, 'Bash', command=script))[0] == expected


@pytest.mark.parametrize('script,expected', [
    ('ln -f source *.json', 1), ('install source *.json', 1),
    ('rsync source *.json', 1), ('rm *.json', 1),
    ("cp source '*.json'", 1), ("mv '*.json' backup", 1),
    ('rm st?te.js[oa]n', 1), ('rm no-match*', 0),
    ('rsync *.json backup', 0), ("cp '*.json' backup", 0),
])
def test_f9_parsed_globs_check_protected_matches(workspace, script, expected):
    from wuwei.guards.protect_state import check_bash
    cwd = workspace / '.wuwei/days/2026-09-28'
    assert check_bash(payload(cwd, 'Bash', command=script))[0] == expected


@pytest.mark.parametrize('script', ['rm -rf .wuwei/days', 'rm -rf .wuwei/days/2026-09-28',
                                    'mv .wuwei/days backup', 'mv .wuwei/days/2026-09-28 backup'])
def test_f10_refuse_day_directory_removal(workspace, script):
    from wuwei.guards.protect_state import check_bash
    assert check_bash(payload(workspace, 'Bash', command=script))[0] == 1


@pytest.mark.parametrize('directory,expected', [('.', 1), ('.wuwei', 1),
                                                ('.wuwei/days/2026-09-28', 1)])
@pytest.mark.parametrize('script', ['git apply changes.patch', 'git -c core.bare=false apply changes.patch'])
def test_f10_git_apply_scope(workspace, directory, expected, script):
    from wuwei.guards.protect_state import check_bash
    assert check_bash(payload(workspace / directory, 'Bash', command=script))[0] == expected


@pytest.mark.parametrize('location', ['temporary', 'worktree', 'workspace'])
@pytest.mark.parametrize('script', [
    'cp *.py sub/', 'mv build/*.whl dist/', 'tee "$LOG"',
    'echo $(date) > out.txt', 'git rev-parse HEAD > $(mktemp)',
    'for f in *.log; do echo > $f; done',
    'tee *.log', 'truncate -s0 *.log', 'sed -i s/a/b/ *.log', 'dd of=*.log',
])
def test_f11_ordinary_writers_through_shim(workspace, tmp_path, monkeypatch, location, script):
    import os
    from pathlib import Path
    import subprocess
    cwd = {'temporary': Path('/tmp'), 'worktree': Path(__file__).resolve().parents[1],
           'workspace': workspace}[location]
    shim_path = tmp_path / 'bin'
    shim_path.mkdir()
    (shim_path / 'python3').symlink_to(sys.executable)
    monkeypatch.setenv('PATH', str(shim_path) + os.pathsep + os.environ['PATH'])
    result = subprocess.run([str(Path(__file__).resolve().parents[1] / 'bin/wuwei'),
                             'hook', 'PreToolUse'], cwd=cwd, text=True, capture_output=True,
                            input=json.dumps(payload(cwd, 'Bash', command=script)))
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('script', [
    'cp source .w*/days/*/state.*', 'mv .w*/days/*/state.* backup',
    'tee .w*/days/*/state.*', 'truncate -s0 .w*/days/*/state.*',
    'sed -i s/a/b/ .w*/days/*/state.*', 'dd of=.w*/days/*/state.*',
])
def test_f11_writer_globs_still_protect_state(workspace, script):
    from wuwei.guards.protect_state import check_bash
    assert check_bash(payload(workspace, 'Bash', command=script))[0] == 1


@pytest.mark.parametrize('script', ['tee "$FILE" # state.json', 'rm $(printf .w*)'])
def test_f11_dynamic_state_mentions_outside_workspace(workspace, script):
    from wuwei.guards.protect_state import check_bash
    assert check_bash(payload(workspace.parent, 'Bash', command=script))[0] == 2


@pytest.mark.parametrize('operation', ['rm -rf {target}', 'mv {target} /tmp/backup'])
@pytest.mark.parametrize('location,target', [
    ('.', '.wuwei'), ('.', '.'), ('inside', '..'),
    ('outside', '{root}'), ('outside', '{parent}'),
    ('.', 'workspace-link'), ('.', 'control-link'),
])
def test_f12_workspace_container_removal(workspace, operation, location, target):
    from pathlib import Path
    from wuwei.guards.protect_state import check_bash
    (workspace / 'workspace-link').symlink_to(workspace, target_is_directory=True)
    (workspace / 'control-link').symlink_to(workspace / '.wuwei', target_is_directory=True)
    cwd = Path('/tmp') if location == 'outside' else workspace / location
    target = target.format(root=shlex.quote(str(workspace)), parent=shlex.quote(str(workspace.parent)))
    assert check_bash(payload(cwd, 'Bash', command=operation.format(target=target)))[0] == 1


def test_directory_removal_never_walks_the_tree(tmp_path, monkeypatch):
    # rm -rf / outside a workspace hung the hook: the container check walked the whole disk.
    import os
    import pathlib
    from wuwei.guards.protect_state import check_bash
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    def walk(*args, **kwargs):
        raise AssertionError('recursive directory walk in a PreToolUse guard')
    monkeypatch.setattr(pathlib.Path, 'rglob', walk)
    monkeypatch.setattr(os, 'walk', walk)
    assert check_bash(payload(tmp_path, 'Bash', command='rm -rf /')) == (0, '')


@pytest.mark.parametrize('operation', ['rm -rf {target}', 'mv {target} /tmp/backup'])
def test_anchored_worktree_protects_distant_workspace_ancestors(tmp_path, monkeypatch, operation):
    from wuwei.guards.protect_state import check_bash
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    root = tmp_path / 'a/b/workspace'
    (root / '.wuwei').mkdir(parents=True)
    worktree, gitdir = tmp_path / 'worktree', tmp_path / 'gitdir'
    worktree.mkdir()
    gitdir.mkdir()
    (worktree / '.git').write_text(f'gitdir: {gitdir}\n')
    (gitdir / 'wuwei-workspace').write_text(f'{root}\n')
    command = operation.format(target=shlex.quote(str(tmp_path / 'a')))
    assert check_bash(payload(worktree, 'Bash', command=command))[0] == 1


@pytest.mark.parametrize('script', ['rm -rf inside', 'mv inside backup',
                                    'mv notes.md .', 'mv -t . notes.md', 'cp notes.md .'])
def test_f12_ordinary_directory_operations(workspace, script):
    from wuwei.guards.protect_state import check_bash
    assert check_bash(payload(workspace, 'Bash', command=script))[0] == 0


@pytest.mark.parametrize('script', [
    'rm -rf .wuwei/memory',
    'rm -rf .wuwei/memory/notes',
    'rm -rf .wuwei/charters',
    'mv .wuwei/memory /tmp/m',
    'rm .wuwei/memory/archive/x.md',
])
def test_promotion_state_containers_are_protected(workspace, script):
    from wuwei.guards.protect_state import check_bash
    (workspace / '.wuwei/memory/notes').mkdir(parents=True)
    (workspace / '.wuwei/memory/archive').mkdir()
    (workspace / '.wuwei/memory/archive/x.md').write_text('Archived note\n')
    (workspace / '.wuwei/charters').mkdir()
    assert check_bash(payload(workspace, 'Bash', command=script))[0] == 1


@pytest.mark.parametrize('script,expected', [
    ('git apply changes.patch', 0), ('git -C {root} apply changes.patch', 1),
    ('git -C{root}/inside apply changes.patch', 1),
    ('git -c core.bare=false -C {root} -C inside apply changes.patch', 1),
    ('git -C {root} -C .. apply changes.patch', 0),
    ('git -C {root} diff', 0), ('git -C {root} status', 0),
    ('git -C {root} show apply', 0),
    ('git -C {root} -c alias.name=apply status', 0),
    ('git -C {root} -C "" apply changes.patch', 1),
])
def test_f13_git_apply_directory(workspace, script, expected):
    from wuwei.guards.protect_state import check_bash
    assert check_bash(payload(workspace.parent, 'Bash', command=script.format(
        root=shlex.quote(str(workspace)))))[0] == expected


@pytest.mark.parametrize('operation', ['chmod -R u+w', 'chown -R nobody'])
@pytest.mark.parametrize('target,expected', [('.wuwei', 1), ('.wuwei/days', 1),
                                           ('.', 1), ('inside', 0), ('notes.md', 0)])
def test_f13_permissions_on_containers(workspace, operation, target, expected):
    from wuwei.guards.protect_state import check_bash
    assert check_bash(payload(workspace, 'Bash', command=f'{operation} {target}'))[0] == expected


@pytest.mark.parametrize('path', [
    '.wuwei/days/2026-09-28/traces.jsonl',
    '.wuwei/memory/ledger.jsonl',
])
def test_memory_lint_evidence_is_cli_owned(workspace, path):
    from wuwei.guards.protect_state import check_bash, check_file
    assert check_file(payload(workspace, 'Write', file_path=path))[0] == 1
    assert check_bash(payload(workspace, 'Bash', command=f'echo forged > {path}'))[0] == 1


@pytest.mark.parametrize('tool,fields', [
    ('Write', {'file_path': '.wuwei/executable'}), ('Edit', {'file_path': '.wuwei/executable'}),
    ('Bash', {'command': 'echo x > .wuwei/executable'}), ('Bash', {'command': 'cp other .wuwei/executable'}),
])
def test_recorded_executable_is_protected(workspace, tool, fields):
    from wuwei.guards.protect_state import check_bash, check_file
    check = check_bash if tool == 'Bash' else check_file
    assert check(payload(workspace, tool, **fields))[0] == 1


@pytest.mark.parametrize('command', ['bin/wuwei state recover', 'python3 -P -m wuwei state recover',
                                     "bin/wuwei 'state' recover > out"])
def test_seat_cannot_recover_state(workspace, tmp_path, command):
    from wuwei.guards.protect_state import check_bash
    assert check_bash(payload(workspace, 'Bash', command=command)) == (
        1, 'State recovery is an owner action on the host, outside agent tools.')
    outside = tmp_path / 'outside'
    outside.mkdir()
    assert check_bash(payload(outside, 'Bash', command=command)) == (0, '')


@pytest.mark.parametrize('command', ['bin/wuwei remote ack', 'python3 -P -m wuwei remote ack'])
def test_seat_cannot_acknowledge_refusals(workspace, tmp_path, command):
    from wuwei.guards.protect_state import check_bash
    assert check_bash(payload(workspace, 'Bash', command=command)) == (
        1, 'Remote acknowledgements require the owner terminal, outside agent tools.')
    outside = tmp_path / 'outside'
    outside.mkdir()
    assert check_bash(payload(outside, 'Bash', command=command)) == (0, '')


@pytest.mark.parametrize('command', ['python3 -m pytest -q -k recover', 'grep -rn recover cli/',
                                     'bin/wuwei state get'])
def test_unrelated_recover_mentions_are_allowed(workspace, command):
    from wuwei.guards.protect_state import check_bash
    assert check_bash(payload(workspace, 'Bash', command=command)) == (0, '')


@pytest.mark.parametrize('tool', ['Write', 'Edit'])
def test_state_snapshot_is_protected(workspace, tool):
    from wuwei.guards.protect_state import check_bash, check_file
    path = '.wuwei/days/2026-09-28/state.snapshot.json'
    assert check_file(payload(workspace, tool, file_path=path))[0] == 1
    assert check_bash(payload(workspace, 'Bash', command='echo {} > ' + path))[0] == 1


def test_unresolvable_cd_refusal_names_the_workspace_guard(workspace):
    from wuwei.guards.protect_state import check_bash
    code, reason = check_bash(payload(workspace, 'Bash',
                                      command='cd $(git rev-parse --show-toplevel) && ls'))
    assert code == 2 and 'workspace guard' in reason and 'cd' in reason
    assert 'git or gh' not in reason


def _continue_job(root):
    agents = root / '.wuwei/generated/agents'
    agents.mkdir(parents=True, exist_ok=True)
    (agents / 'sentinel-quality.md').write_text('charter\n')
    job = {'agent_type': 'wuwei:sentinel-quality',
           'prompt': (f'WUWEI brief: A\nRead instructions {agents}/sentinel-quality.md '
                      'and brief .wuwei/briefs/A.md')}
    return shlex.quote(json.dumps(job))


def test_runtime_continue_passes_through_hook(workspace, monkeypatch, capsys):
    from wuwei.commands.hook import run
    command = f"wuwei runtime continue {_continue_job(workspace)} 'Recheck Q1.'"
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(payload(workspace, 'Bash', command=command))))
    assert run(SimpleNamespace(event='PreToolUse')) == 0
    assert not capsys.readouterr().out


@pytest.mark.parametrize('command', [
    'wuwei verdict lint .wuwei/generated/agents/x.md',
    '{plugin}/bin/wuwei verdict lint .wuwei/generated/agents/x.md',
    'python3 -P -m wuwei runtime continue {job} x',
])
def test_wuwei_cli_arguments_are_data(workspace, command):
    from wuwei.guards.protect_state import check_bash
    plugin = shlex.quote(str(Path(__file__).resolve().parents[1]))
    command = command.format(job=_continue_job(workspace), plugin=plugin)
    assert check_bash(payload(workspace, 'Bash', command=command)) == (0, '')


@pytest.mark.parametrize('tool', ['Write', 'Edit'])
def test_config_cache_is_producer_only(workspace, tool):
    # #346: the parsed copy of config.toml decides like the file itself, so seats never write it.
    from wuwei.guards.protect_state import check_bash, check_file
    target = '.wuwei/generated/config.cache.json'
    assert check_file(payload(workspace, tool, file_path=target))[0] == 1
    assert check_bash(payload(workspace, 'Bash', command=f'echo {{}} > {target}'))[0] != 0


@pytest.mark.parametrize('command', [
    'bin/wuwei state get > .wuwei/config.toml',
    'cp /dev/null .wuwei/generated/agents/a.md',
    'echo x | tee .wuwei/config.toml',
    './wuwei .wuwei/config.toml',
    'x/wuwei .wuwei/generated/agents/a.md',
])
def test_writes_beside_the_cli_stay_refused(workspace, command):
    from wuwei.guards.protect_state import check_bash
    assert check_bash(payload(workspace, 'Bash', command=command))[0] != 0


@pytest.mark.parametrize('command,expected', [
    ("echo 'see .wuwei/generated/agents/arch.md'", 0),
    ('echo .wuwei/generated/agents/arch.md', 0),
    ("echo 'Read instructions {root}/.wuwei/generated/agents/arch.md'", 0),
    ("printf '%s\\n' .wuwei/generated/agents/arch.md", 0),
    ('cut -c1 .wuwei/config.toml', 0),
    ('tr a b .wuwei/config.toml', 0),
    ('rg -n x .wuwei/config.toml', 0),
    ('rg --pre rm x .wuwei/config.toml', 2),
    ('rg --pre=rm x .wuwei/config.toml', 2),
    ('rg --pre rm x .wuwei/days/2026-09-28/state.json', 2),
    ('echo x > .wuwei/generated/agents/arch.md', 2),
    ('printf x >> .wuwei/config.toml', 2),
    ('echo x | tee .wuwei/config.toml', 2),
    ('echo .wuwei/config.toml | xargs rm', 2),
    ('echo .wuwei/config.toml | sh', 2),
])
def test_reader_mentions_are_not_writes(workspace, monkeypatch, capsys, command, expected):
    from wuwei.commands.hook import run
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(
        payload(workspace, 'Bash', command=command.format(root=workspace)))))
    assert run(SimpleNamespace(event='PreToolUse')) == expected, capsys.readouterr().err
    capsys.readouterr()


@pytest.mark.parametrize('tool', ['Write', 'Bash'])
@pytest.mark.parametrize('name', ['interview.json', 'profile.json'])
def test_interview_answers_are_protected(workspace, tool, name):
    from wuwei.guards.protect_state import check_bash, check_file
    target = f'.wuwei/days/2026-10-01/{name}'
    if tool == 'Bash':
        code, reason = check_bash(payload(workspace, tool, command='echo {} | tee ' + target))
    else:
        code, reason = check_file(payload(workspace, tool, file_path=target))
    assert code == 1 and 'outside agent tools' in reason


@pytest.mark.parametrize('script, expected', [
    ('for r in a b; do cat .wuwei/$r/report.json; done', (0, '')),
    ('W=$(cat .wuwei/executable); $W plan session abc --take-over; $W mcp check', 'unparsed'),
    ('cd .wuwei/ziran && for r in a b c; do cat $r/report.json; done', (2, 'root')),
    ('mkdir -p ../scratch && cd ../scratch && ls', (1, 'root')),
    ('cd ..', (1, 'root')),
    ('pushd', (2, 'root')),
    ('cd "$DEST"', (2, 'root')),
    ('W=$(cat .wuwei/executable); $W drafts approve x', 'kept'),
    ('echo x > .wuwei/days/2026-09-28/state.json', 'kept'),
    ('for r in a; do echo x > .wuwei/days/2026-09-28/state.json; done', 'kept'),
    ('echo x > .wuwei/days/$(date +%F)/state.json', 'kept'),
    ('echo x | tee $(ls -d .wuwei/days/2026-09-28)/state.json', 'kept'),
    ('T="tee .wuwei/days/2026-09-28/state.json"; echo x | $T', 'kept'),
    ('python3 -c \'open(".wuwei/days/2026-09-28/state.json", "w").write("x")\'', 'kept'),
])
def test_issue_347_reads_warns_and_writes(workspace, script, expected):
    from wuwei.guards.protect_state import check_bash
    from wuwei.shell import UNPARSED, WORKSPACE_ROOT
    result = check_bash(payload(workspace, 'Bash', command=script))
    if expected == 'kept':
        assert result[0] and result[1] not in (UNPARSED, WORKSPACE_ROOT), result
    elif expected == 'unparsed':
        assert result == (2, UNPARSED)
    elif expected[1] == 'root':
        assert result == (expected[0], WORKSPACE_ROOT)
    else:
        assert result == expected


@pytest.mark.parametrize('argv, expected', [
    (['cat', 'x'], True), (['less', 'x'], True), (['ls', 'd'], True),
    (['find', 'd', '-name', 'x'], True), (['diff', 'a', 'b'], True),
    (['sed', '-n', '1,5p', 'x'], True), (['jq', '.', 'x'], True), (['wuwei', 'status'], True),
    ([], False), (['sed', '-i', 's/a/b/', 'x'], False), (['find', 'd', '-delete'], False),
    (['awk', '1', 'x'], False), (['python3', 'x.py'], False),
    (['python3', '-m', 'json.tool', 'x'], True), (['python3', '-m', 'json.tool', 'x', 'y'], False),
    (['wuwei', 'config', 'set', 'k', 'v'], False),
])
def test_issue_349_shared_read_predicate(argv, expected):
    from wuwei import shell
    assert shell.reads(argv) is expected


def test_issue_349_classify_less_and_redirect_only():
    from wuwei import shell
    assert shell.classify('less x').readonly
    assert shell.classify('for f in a; do cat $f; done > out.txt').readonly is False


@pytest.mark.parametrize('argv, expected', [
    (['python3', '-c', 'x'], True), (['python3', '-Bc', 'x'], True), (['node', '-e', 'x'], True),
    (['node', '--eval=x'], True), (['perl', '-pe', 'x'], True),
    (['python3', 'x.py'], False), (['python3', '-m', 'json.tool', 'f'], False),
    (['python3', '-P', 'x.py'], False), (['cat', '-c'], False), ([], False),
])
def test_issue_349_inline_code(argv, expected):
    from wuwei import shell
    assert shell.inline_code(argv) is expected


DAY_349 = '.wuwei/days/2026-09-28'


@pytest.fixture
def records(workspace):
    for name, text in [(f'{DAY_349}/decisions/D-1.md', '# D-1\n'), (f'{DAY_349}/events.jsonl', ''),
                       ('.wuwei/ziran/a/report.json', '{}\n'), ('.wuwei/charters/a.md', 'a\n'),
                       ('.wuwei/charters/b.md', 'b\n'), ('.wuwei/memory/goals.md', 'goals\n')]:
        (workspace / name).parent.mkdir(parents=True, exist_ok=True)
        (workspace / name).write_text(text)
    (workspace / 'read_reports.py').write_text(
        'import glob\nfor path in glob.glob(".wuwei/ziran/*/report.json"):\n'
        '    print(open(path).read())\n')
    return workspace


def _posture(root, name):
    (root / '.wuwei/config.toml').write_text(f'[security]\nposture = "{name}"\n')


def _hook(cwd, tool, monkeypatch, capsys, **tool_input):
    from wuwei.commands.hook import run
    data = {**payload(cwd, tool, **tool_input)}
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(data)))
    code = run(SimpleNamespace(event='PreToolUse'))
    capsys.readouterr()
    return code


def _events(root):
    return [line for path in root.glob('.wuwei/days/*/events.jsonl')
            for line in path.read_text().splitlines()
            if json.loads(line)['kind'] in ('hook.refusal', 'guard.would_refuse')]


@pytest.mark.parametrize('posture', ['observe', 'guarded', 'strict'])
@pytest.mark.parametrize('where, command', [
    ('', 'grep posture .wuwei/config.toml'), ('', 'grep -n posture .wuwei/config.toml'),
    ('', f'cat {DAY_349}/decisions/D-1.md'), ('', 'python3 read_reports.py'),
    ('', 'python3 -m json.tool .wuwei/ziran/a/report.json'), ('', 'head -5 .wuwei/config.toml'),
    ('', f'tail -5 {DAY_349}/events.jsonl'), ('', 'sed -n 1,5p .wuwei/config.toml'),
    ('', 'less .wuwei/config.toml'), ('', f'wc -l {DAY_349}/state.json'),
    ('', 'jq . .wuwei/ziran/a/report.json'), ('', 'ls .wuwei/ziran'),
    ('', 'find .wuwei/ziran -name report.json'),
    ('', 'diff .wuwei/charters/a.md .wuwei/charters/b.md'), ('', 'cat .wuwei/memory/goals.md'),
    ('.wuwei', 'ls ziran'), ('.wuwei', 'find ziran -name report.json'),
    ('.wuwei', 'for f in ziran/*/report.json; do cat $f 2>/dev/null; done'),
])
def test_issue_349_reads_pass(records, posture, where, command, monkeypatch, capsys):
    _posture(records, posture)
    assert _hook(records / where, 'Bash', monkeypatch, capsys, command=command) == 0
    assert _events(records) == []


@pytest.mark.parametrize('tool, field', [('Read', 'file_path'), ('Grep', 'path'), ('Glob', 'path')])
def test_issue_349_read_tools_pass(records, tool, field, monkeypatch, capsys):
    _posture(records, 'strict')
    extra = {'pattern': 'posture'} if tool != 'Read' else {}
    assert _hook(records, tool, monkeypatch, capsys, **{field: '.wuwei/config.toml'}, **extra) == 0
    assert _events(records) == []


_CONFIG = '.wuwei/config.toml'
_STATE = f'{DAY_349}/state.json'
_EVENTS = f'{DAY_349}/events.jsonl'
_REPORT = '.wuwei/ziran/a/report.json'
_GOALS = '.wuwei/memory/goals.md'


@pytest.mark.parametrize('tool, value, expected', [
    ('Edit', _CONFIG, 'wuwei config set'), ('Bash', f"sed -i 's/a/b/' {_CONFIG}", 'wuwei config set'),
    ('Bash', f'echo x | tee {_CONFIG}', 'wuwei config set'),
    ('Bash', f'echo x > {_CONFIG}', 'wuwei config set'),
    ('Write', _STATE, 'wuwei state set'), ('Bash', f'echo x >> {_STATE}', 'wuwei state set'),
    ('Write', _EVENTS, 'wuwei event'), ('Bash', f'echo x >> {_EVENTS}', 'wuwei event'),
    ('Edit', _REPORT, 'wuwei mcp decide'), ('Bash', f'echo x >> {_REPORT}', 'wuwei mcp decide'),
    ('Edit', _GOALS, 'wuwei goals edit --file'), ('Bash', f'cp /dev/null {_GOALS}', 'wuwei goals edit --file'),
    ('Write', '.wuwei/integrity/verdict.json', 'wuwei integrity reconfirm'),
    ('Write', '.wuwei/charters/a.md', 'use the wuwei CLI'),
    ('Write', 'credentials', 'use the wuwei CLI'), ('Bash', 'credentials', 'use the wuwei CLI'),
])
def test_issue_349_write_reasons(records, tool, value, expected):
    from wuwei import security
    from wuwei.guards.protect_state import check_bash, check_file
    if value == 'credentials':
        security.initialize(records / '.wuwei', security.DEFAULT_HONEYTOKEN_PATH)
        value = f'.wuwei/{security.DEFAULT_HONEYTOKEN_PATH}'
        value = f'echo x > {value}' if tool == 'Bash' else value
    if tool == 'Bash':
        code, reason = check_bash(payload(records, 'Bash', command=value))
    else:
        code, reason = check_file(payload(records, tool, file_path=value))
    assert code == 1
    assert expected in reason
    assert '\n' not in reason


@pytest.mark.parametrize('posture', ['observe', 'guarded', 'strict'])
def test_issue_349_writes_refused_in_every_posture(records, posture, monkeypatch, capsys):
    from wuwei.guards.protect_state import check_bash
    _posture(records, posture)
    for tool, value in [('Bash', f"sed -i 's/a/b/' {_CONFIG}"), ('Bash', f'echo x > {_CONFIG}'),
                        ('Edit', _CONFIG)]:
        before = len(_events(records))
        field = {'command': value} if tool == 'Bash' else {'file_path': value}
        assert _hook(records, tool, monkeypatch, capsys, **field) == 2
        assert [json.loads(line)['kind'] for line in _events(records)[before:]] == ['hook.refusal']
    command = f'python3 -c \'open("{_STATE}", "w")\''
    assert check_bash(payload(records, 'Bash', command=command)) == (
        2, 'Opaque interpreter; use the wuwei CLI for state changes.')
    assert check_bash(payload(records, 'Bash', command=f'python3 tool.py > {_CONFIG}'))[0] == 1


@pytest.mark.parametrize('posture', ['observe', 'strict'])
@pytest.mark.parametrize('command', [
    f'python3 -m json.tool /tmp/x.json {_CONFIG}', f'python3 -m json.tool /tmp/x.json {_STATE}',
    'python3 -m zipfile -e a.zip .wuwei', 'python3 -m tarfile -e a.tar .wuwei/days',
    f'python3 w.py {_CONFIG}', f'node w.js {_CONFIG}', f'python3 read_reports.py {_REPORT}',
])
def test_issue_349_interpreter_operands_stay_refused(records, posture, command, monkeypatch, capsys):
    _posture(records, posture)
    assert _hook(records, 'Bash', monkeypatch, capsys, command=command) == 2


@pytest.mark.parametrize('path', ['.wuwei/memory/digests/2026-W40.md', '.wuwei/memory/forget.json'])
def test_memory_tier_records_are_producer_only(workspace, path):
    from wuwei.guards.protect_state import check_bash, check_file
    assert check_file(payload(workspace, 'Write', file_path=path))[0] == 1
    for command in (f'cp other {path}', f'mv other {path}', f'rm {path}'):
        assert check_bash(payload(workspace, 'Bash', command=command))[0] == 1, command
    # forget.json names the owner group and verb, so a redirect into it reads as opaque (exit 2).
    assert check_bash(payload(workspace, 'Bash', command=f'echo forged > {path}'))[0] in (1, 2)
    assert check_bash(payload(workspace, 'Bash', command=f'cat {path}')) == (0, '')
    assert check_bash(payload(workspace, 'Bash', command='rm -rf .wuwei/memory/digests'))[0] == 1


@pytest.mark.parametrize('command,expected', [
    ('bin/wuwei memory forget F-1 apply',
     (1, 'Forgetting memory is an owner action on the host, outside agent tools.')),
    ('python3 -P -m wuwei memory forget F-1 keep',
     (1, 'Forgetting memory is an owner action on the host, outside agent tools.')),
    ('bin/wuwei memory show 2026-08-01', (0, '')), ('bin/wuwei memory status', (0, '')),
    ('bin/wuwei consolidate --widget', (0, '')), ('bin/wuwei memory lint', (0, '')),
])
def test_memory_forget_is_an_owner_action(workspace, command, expected):
    from wuwei.guards.protect_state import check_bash
    assert check_bash(payload(workspace, 'Bash', command=command)) == expected
