"""Issue #222: owner-only actions are refused in indirect forms too; nothing is executed."""

import io
import json
import sys
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from wuwei.guards.protect_state import check_bash, check_file

LAUNCHER = Path(__file__).resolve().parents[1] / 'bin/wuwei'

ACTIONS = [('decision', 'outcome'), ('drafts', 'approve'), ('drafts', 'drop'),
           ('mcp', 'decide'), ('integrity', 'reconfirm'), ('state', 'recover'),
           ('watch', 'uninstall'), ('goals', 'edit'), ('voice', 'edit'), ('remote', 'ack'),
           ('config', 'promote'), ('config', 'set'), ('config', 'add-repo'), ('plan', 'set')]
# Ids stay free of owner verbs: pytest puts them in tmp_path, which reaches payloads.
IDS = [f'pair{index}' for index in range(len(ACTIONS))]


@pytest.fixture
def places(tmp_path, monkeypatch):
    root = tmp_path / 'workspace'
    (root / '.wuwei').mkdir(parents=True)
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    monkeypatch.delenv('CDPATH', raising=False)
    from fakes.integrity import seed
    seed(root)
    (root / '.wuwei/config.toml').write_text('')
    outside = tmp_path / 'outside'
    outside.mkdir()
    return root, outside


def bash(cwd, command):
    return check_bash({'cwd': str(cwd), 'tool_name': 'Bash', 'tool_input': {'command': command}})


def forms(group, verb):
    return [(f'X={group}; bin/wuwei $X {verb}', 2),
            (f'echo {verb} | xargs bin/wuwei {group}', 2),
            (f'bin/wuwei {group} -- {verb}', 1)]


@pytest.mark.parametrize('pair', ACTIONS, ids=IDS)
def test_indirect_forms_are_refused_inside_only(places, pair):
    root, outside = places
    for command, expected in forms(*pair):
        code, reason = bash(root, command)
        assert code == expected, (command, reason)
        assert ('host terminal' if expected == 2 else 'owner') in reason, (command, reason)
        assert bash(outside, command) == (0, ''), command


@pytest.mark.parametrize('pair', ACTIONS, ids=IDS)
def test_script_file_is_refused_inside_only(places, pair):
    for cwd, expected in zip(places, (1, 0)):
        (cwd / 'wrap.sh').write_text('#!/bin/sh\nbin/wuwei {} {}\n'.format(*pair))
        (cwd / 'wrap.sh').chmod(0o755)
        # Review F20: a prefix, list, subshell, wrapper or xargs still reaches the script.
        for command in ('./wrap.sh', 'sh wrap.sh', 'true && ./wrap.sh', '(./wrap.sh)',
                        'timeout 5 ./wrap.sh', 'echo . | xargs ./wrap.sh',
                        "bash -c 'sh wrap.sh'", 'ls; sh wrap.sh'):
            code, reason = bash(cwd, command)
            assert code == expected, (cwd, command, reason)
            assert expected or reason == ''


def test_plan_set_is_the_only_owner_plan_verb(places):
    root, _ = places
    code, reason = bash(root, 'bin/wuwei plan set A spec=skipped --reason x')
    assert code == 1 and 'Spec overrides are an owner action' in reason
    assert bash(root, 'bin/wuwei plan approve --items A --goals-confirmed') == (0, '')
    assert bash(root, 'bin/wuwei plan carry A') == (0, '')


def test_forwarding_script_and_plain_script(places):
    root, _ = places
    (root / 'fw.sh').write_text('#!/bin/sh\nbin/wuwei "$@"\n')
    (root / 'plain.sh').write_text('#!/bin/sh\nbin/wuwei state get\n')
    assert bash(root, './fw.sh drafts approve x')[0] == 2
    assert bash(root, './plain.sh') == (0, '')


@pytest.mark.parametrize('command', [
    'python3 -m pytest -q', 'for x in a b; do echo "$x"; done', 'export X=1',
    'bin/wuwei state get', 'grep -rn uninstall docs/', "rg 'wuwei mcp decide' cli",
    'git remote -v', 'bin/wuwei steward ack remote-fix-3',
    'bin/wuwei promote', 'bin/wuwei config check', 'bin/wuwei calibrate',
    'bin/wuwei state transition "$i" review',
    # Review F1: a path segment or commit message is not the CLI.
    'git commit -m "wuwei: drop stale drafts"',
    'git add cli/wuwei/commands/drafts.py && git commit -m "drafts: approve path"',
    'cat cli/wuwei/commands/edit.py', 'sed -n 1,20p cli/wuwei/guards/protect_state.py | grep decide',
    'ls .wuwei | grep drop', 'ls cli/wuwei/commands | grep edit', 'git log -S recover -- cli/wuwei',
    'python3 -m pytest -q cli/wuwei -k recover', 'python3 cli/wuwei/tools/x.py --mode edit',
    'diff <(cat cli/wuwei/a.py) <(cat cli/wuwei/edit.py)',
    # Review F6: a commit message naming an owner action is not a wuwei action.
    'git commit -m "fix wuwei mcp decide"',
    # Review F8: research commands without the CLI word, or naming it only as text.
    "python3 -m pytest -q 2>&1 | grep 'decision outcome'",
    "python3 -m pytest tests/test_decision.py -q | grep -i 'mcp decide'",
    "python3 -m json.tool data.json | grep 'drafts approve'",
    "python3 -m pytest -q; git log --oneline | grep 'state recover'",
    "perl -pe 's/foo/bar/' README.md | grep 'decision outcome'",
    "git log --oneline --grep='wuwei mcp decide'", "printf '%s\\n' 'bin/wuwei mcp decide'",
    # The r3 reviewer's allow list.
    "python3 -m pytest -q -k 'decision and outcome'",
    'python3 -m pytest tests/test_owner_actions.py -k outcome',
    "grep -rn 'decision outcome' docs", "rg 'decision outcome'", "git log --grep 'drafts approve'",
    'git commit -m "mcp decide docs"', 'git stash -m "wuwei mcp decide"',
    'cat docs/site/reference.md', 'sed -n 1,20p cli/wuwei/decision.py', '/bin/ls -la',
    'ls specs | xargs bin/wuwei lint',
    "find . -name '*.py' | xargs grep -l outcome; bin/wuwei state get",
    "printf 'bin/wuwei mcp decide' | grep mcp",
    # Review F15: the package directory cli/wuwei is not the CLI.
    "git log -G'drafts approve' -- cli/wuwei", 'git ls-files cli/wuwei | xargs wc -l',
    "find cli/wuwei -name '*.py' | xargs grep -n 'def outcome'",
    # Filters that cannot run or write anything keep a search inert.
    "rg 'wuwei mcp decide' cli | head -5", "grep -rn 'bin/wuwei decision outcome' docs | wc -l",
    # Review F21: a source file named by an unparsed command is not a script it runs.
    'for f in cli/wuwei/decision.py; do wc -l "$f"; done',
    'for f in cli/wuwei/shell.py; do wc -l "$f"; done',
    'while read f; do wc -l "$f"; done < files.txt; ls cli/wuwei/decision.py'])
def test_ordinary_work_passes(places, command):
    (places[0] / 'cli/wuwei').mkdir(parents=True, exist_ok=True)
    for name in ('decision.py', 'shell.py'):
        shutil.copy(LAUNCHER.parents[1] / 'cli/wuwei' / name, places[0] / 'cli/wuwei' / name)
    assert bash(places[0], command) == (0, '')


@pytest.mark.parametrize('command, expected', [
    ('bin/wuwei mcp $ACTION', 2),
    ('find . -exec bin/wuwei drafts approve {} \\;', 2),
    ('bin/wuwei drafts approve "$ID"', 1)])
def test_edge_rows(places, command, expected):
    assert bash(places[0], command)[0] == expected


# Review F5: an interpreter passing the CLI an argument list is opaque.
INTERPRETER_PROBES = [
    *('python3 -c "import subprocess; subprocess.run([\'bin/wuwei\',\'%s\',\'%s\',\'x\'])"' % pair
      for pair in [('decision', 'outcome'), ('drafts', 'approve'), ('mcp', 'decide'),
                   ('watch', 'uninstall'), ('voice', 'edit')]),
    'python3 -c "import os; os.execvp(\'bin/wuwei\', [\'wuwei\',\'state\',\'recover\'])"',
    'node -e "require(\'child_process\').execFileSync(\'bin/wuwei\',[\'decision\',\'outcome\',\'x\'])"',
    'perl -e \'system("bin/wuwei","integrity","reconfirm")\'']


@pytest.mark.parametrize('command', INTERPRETER_PROBES)
def test_interpreter_argument_list_is_opaque_inside_only(places, command):
    root, outside = places
    assert bash(root, command)[0] == 2, command
    assert bash(outside, command) == (0, ''), command


# Review F7: any executor handed the CLI and an owner action fails closed.
EXECUTOR_PROBES = [
    'echo "import subprocess; subprocess.run([\'bin/wuwei\',\'decision\',\'outcome\',\'x\'])" | python3',
    "python3 - <<'EOF'\nimport subprocess\nsubprocess.run(['bin/wuwei','decision','outcome','x'])\nEOF",
    "python3 <<'EOF'\nimport os\nos.execvp('bin/wuwei', ['wuwei','mcp','decide'])\nEOF",
    "node <<'EOF'\nrequire('child_process').execFileSync('bin/wuwei', ['drafts','approve','x'])\nEOF",
    "perl <<'EOF'\nsystem('bin/wuwei','state','recover');\nEOF",
    'deno eval "new Deno.Command(\'bin/wuwei\', {args: [\'decision\',\'outcome\',\'x\']}).outputSync()"',
    'bun -e "Bun.spawnSync([\'bin/wuwei\',\'watch\',\'uninstall\'])"',
    "tclsh <<'EOF'\nexec bin/wuwei decision outcome x\nEOF",
    'parallel bin/wuwei ::: decision ::: outcome ::: x',
    'bin/wuwei mcp $(printf dec%s ide)', 'bin/wuwei drafts $(printf app%s rove) x',
    'bin/wuwei $(cat args.txt)',
    # Review F11: xargs feeding the CLI an argument list from a file or stdin.
    'xargs bin/wuwei < args.txt', 'xargs -a args.txt bin/wuwei',
    "printf 'decision\\noutcome\\nx\\n' | xargs bin/wuwei",
    'echo x | xargs -I{} sh -c "true; bin/wuwei drafts {}"',
    'echo decision | xargs -I{} bin/wuwei {} outcome',
    './s.py', './xa.sh',
    # Review F13: a reader piped into an executor is not inert.
    "echo 'exec bin/wuwei decision outcome x' | tclsh",
    "echo 'do shell script \"bin/wuwei decision outcome x\"' | osascript",
    "echo 'bin/wuwei decision outcome x' | at now", "echo 'bin/wuwei decision outcome x' | batch",
    "echo 'bin/wuwei decision outcome x' | ssh localhost",
    "echo 'bin/wuwei decision outcome x' | script -q /dev/null",
    "echo 'bin/wuwei decision outcome x' | xargs -I{} sh -c {}",
    "echo 'bin/wuwei decision outcome x' | grep bin | tclsh",
    # Review F17: a reader redirected to a file that an executor runs.
    "echo 'exec bin/wuwei decision outcome x' > x.tcl; tclsh x.tcl",
    "echo 'exec bin/wuwei decision outcome x' > x.tcl && tclsh < x.tcl",
    "echo 'system(\"bin/wuwei\",\"state\",\"recover\")' > x.pl; perl x.pl",
    "echo 'import subprocess; subprocess.run([\"bin/wuwei\",\"decision\",\"outcome\",\"x\"])' > x.py; python3 x.py",
    "echo 'bin/wuwei decision outcome x' > x.sh; chmod +x x.sh; ./x.sh",
    "echo 'exec bin/wuwei decision outcome x' | grep . > x.tcl; tclsh x.tcl",
    # Review F18: a reader inside a piped subshell.
    "(echo 'exec bin/wuwei decision outcome x'; echo) | tclsh",
    # sort and uniq can write a file, so they are not readers.
    "echo 'exec bin/wuwei decision outcome x' | sort -o x.tcl; tclsh x.tcl",
    "echo 'exec bin/wuwei decision outcome x' | uniq - x.tcl; tclsh x.tcl"]


@pytest.mark.parametrize('command', EXECUTOR_PROBES)
def test_executor_forms_fail_closed_inside_only(places, command):
    for cwd in places:
        (cwd / 's.py').write_text("#!/usr/bin/env python3\nimport subprocess\n"
                                  "subprocess.run(['bin/wuwei', 'decision', 'outcome', 'x'])\n")
        (cwd / 'xa.sh').write_text('#!/bin/sh\nxargs bin/wuwei < args.txt\n')
    root, outside = places
    assert bash(root, command)[0] == 2, command
    assert bash(outside, command) == (0, ''), command


# Review F19: a bare wuwei is the CLI on PATH even when cwd holds a wuwei directory.
def test_bare_cli_word_beside_a_wuwei_directory(places):
    for cwd in places:
        (cwd / 'wuwei').mkdir()
    root, outside = places
    for command in ("find . -maxdepth 0 -exec wuwei decision outcome x \\;",
                    'parallel wuwei ::: decision ::: outcome ::: x'):
        assert bash(root, command)[0] == 2, command
        assert bash(outside, command) == (0, ''), command


# Review F14: a quote- or backslash-split name in a script body is still parsed.
def test_split_name_in_script_body(places):
    for cwd, expected in zip(places, (1, 0)):
        (cwd / 'q.sh').write_text('#!/bin/sh\nbin/wu""wei decision outcome x\n')
        (cwd / 'q2.sh').write_text('#!/bin/sh\nbin/wu\\wei mcp decide\n')
        for command in ('./q.sh', './q2.sh'):
            assert bash(cwd, command)[0] == expected, (cwd, command)


# The r3 reviewer's regression list: (command, inside).
@pytest.mark.parametrize('command, expected', [
    ('env -S "bin/wuwei decision outcome x"', 2), ('exec bin/wuwei decision outcome x', 1),
    ('eval "bin/wuwei decision outcome x"', 1), ('bash <<EOF\nbin/wuwei decision outcome x\nEOF', 2),
    ('command bin/wuwei decision outcome x', 1), ('bin/wuwei decision \\\noutcome x', 1),
    ('python3 -P -m wu""wei decision outcome x', 1),
    ('bash -c "bash -c \'bin/wuwei decision outcome x\'"', 1),
    ('time bin/wuwei decision outcome x', 1), ('nice bin/wuwei drafts approve x', 1),
    ('nohup bin/wuwei mcp decide', 1), ('timeout 5 bin/wuwei state recover', 1),
    ('awk \'BEGIN { system("bin/wuwei decision outcome x") }\'', 2),
    ("git -c alias.x='!bin/wuwei mcp decide' x", 2),
    ("echo 'bin/wuwei decision outcome' > notes.md", 2)])
def test_regression_list(places, command, expected):
    root, outside = places
    assert bash(root, command)[0] == expected, command
    assert bash(outside, command) == (0, ''), command


def test_write_and_edit_to_the_table_pass(places):
    path = str(places[0] / 'tests/test_owner_actions.py')
    for tool, tool_input in (('Write', {'file_path': path, 'content': 'bin/wuwei decision outcome x'}),
                             ('Edit', {'file_path': path, 'old_string': 'a', 'new_string': 'bin/wuwei mcp decide'})):
        assert check_file({'cwd': str(places[0]), 'tool_name': tool, 'tool_input': tool_input}) == (0, '')


# Review F10: a renamed launcher is still the CLI; a copy forwards "$@" and is opaque.
def test_renamed_launcher(places):
    for cwd in places:
        (cwd / 'w').symlink_to(LAUNCHER)
        shutil.copy(LAUNCHER, cwd / 'w2')
    root, outside = places
    for command, expected in (('./w decision outcome x', 1), ('./w drafts approve x', 1),
                              ('./w mcp decide', 1), ('./w2 decision outcome x', 2)):
        assert bash(root, command)[0] == expected, command
        assert bash(outside, command) == (0, ''), command


# Review F9: a script without the CLI word is never parsed.
def test_script_without_cli_word_is_not_parsed(places, monkeypatch):
    import wuwei.shell
    root = places[0]
    body = '#!/bin/sh\n' + 'echo "building the project"\n' * 2000
    (root / 'big.sh').write_text(body)
    real = wuwei.shell.normalize

    def normalize(command, **kwargs):
        assert command != body, 'script body parsed'
        return real(command, **kwargs)
    monkeypatch.setattr(wuwei.shell, 'normalize', normalize)
    assert bash(root, './big.sh') == (0, '')


def hook(cwd, command, monkeypatch, capsys):
    from wuwei.commands.hook import run
    event = {'hook_event_name': 'PreToolUse', 'session_id': 'fixture',
             'transcript_path': str(cwd / 'transcript.jsonl'), 'cwd': str(cwd),
             'tool_name': 'Bash', 'tool_input': {'command': command}}
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(event)))
    code = run(SimpleNamespace(event='PreToolUse'))
    out = capsys.readouterr().out
    return code, json.loads(out)['hookSpecificOutput'] if out.strip() else {}


def test_hook_refuses_inside_only(places, monkeypatch, capsys):
    for cwd, inside in zip(places, (True, False)):
        (cwd / 'wrap.sh').write_text('#!/bin/sh\nbin/wuwei watch uninstall\n')
        (cwd / 'wrap.sh').chmod(0o755)
        for command in ('./wrap.sh', 'W=watch; bin/wuwei $W uninstall'):
            code, output = hook(cwd, command, monkeypatch, capsys)
            if inside:
                assert (code, output.get('permissionDecision')) == (2, 'deny'), (command, output)
            else:
                assert code == 0, (command, output)


def test_cli_hidden_beside_a_visible_mention_is_refused(places):
    command = "echo bin/wuwei; tclsh <<'EOF'\nexec bin/wuwei decision outcome x\nEOF"
    assert bash(places[0], command)[0] == 2
    assert bash(places[1], command) == (0, '')


def test_whole_group_owner_command(places, monkeypatch, capsys):
    root, outside = places
    for command in ('bin/wuwei setup --shadow', 'bin/wuwei setup --repos src --posture cli-tool',
                    'bin/wuwei setup'):
        code, reason = bash(root, command)
        assert code == 1 and 'owner' in reason, (command, reason)
        assert bash(outside, command) == (0, ''), command
    for cwd, inside in zip(places, (True, False)):
        code, output = hook(cwd, "bin/wuwei config set owner.name '\"Pat\"'", monkeypatch, capsys)
        assert (code, output.get('permissionDecision')) == ((2, 'deny') if inside else (0, None)), output
