"""Issue #347 acceptance through the hook in process; no command is executed."""

import io
import json
import sys
from types import SimpleNamespace

import pytest

from wuwei import shell


S1 = 'cd .wuwei/ziran && for r in a b c; do cat $r/report.json; done'
S2 = 'ls; ls days/x; cat days/x/decisions/D-1.md; grep -n rm config.toml'
S3 = 'W=$(cat .wuwei/executable); $W plan session abc --take-over; $W next'
S4 = ('python3 -P -c \'import subprocess;r=subprocess.run(["git","log","-1"]);'
      'print(open("config.toml").read())\'')
S5 = 'mkdir -p ../scratch && cd ../scratch && ls'
ENFORCE = ('false', 'true')
STATE = '.wuwei/days/2026-10-03/state.json'


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    root = tmp_path / 'workspace'
    (root / '.wuwei/ziran').mkdir(parents=True)
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    monkeypatch.delenv('CDPATH', raising=False)
    from fakes.integrity import seed
    seed(root)
    return root


def configure(root, enforce):
    (root / '.wuwei/config.toml').write_text(f'[guards]\nenforce = {enforce}\n')


def hook(cwd, command, monkeypatch, capsys, event='PreToolUse', session='fixture'):
    from wuwei.commands.hook import run
    payload = {'hook_event_name': event, 'session_id': session,
               'transcript_path': str(cwd / 'transcript.jsonl'), 'cwd': str(cwd),
               'tool_name': 'Bash', 'tool_input': {'command': command}}
    if event == 'PostToolUse':
        payload['tool_response'] = {}
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(payload)))
    code = run(SimpleNamespace(event=event))
    captured = capsys.readouterr()
    out = json.loads(captured.out)['hookSpecificOutput'] if captured.out.strip() else {}
    return code, out, captured.out + captured.err


def events(root, kind):
    return [json.loads(line) for path in root.glob('.wuwei/days/*/events.jsonl')
            for line in path.read_text().splitlines() if json.loads(line)['kind'] == kind]


@pytest.mark.parametrize('posture', ENFORCE)
@pytest.mark.parametrize('name, command', [('S1', S1), ('S2', S2), ('S3', S3), ('S4', S4), ('S5', S5)])
def test_five_shapes(workspace, posture, name, command, monkeypatch, capsys):
    configure(workspace, posture)
    code, out, _ = hook(workspace, command, monkeypatch, capsys)
    warned = [event['payload']['reason'] for event in events(workspace, 'guard.would_refuse')]
    if name in ('S1', 'S5'):
        assert code == 0, out
        assert len(warned) == 1 and warned[0].startswith('workspace guard'), warned
        assert '(cd <dir> && <command>)' in warned[0]
    elif name == 'S3':  # the state guard cannot read it and it names .wuwei: logged once
        assert code == 0, out
        assert len(warned) == 1 and warned[0].startswith('unparsed'), warned
    else:  # #839: no guard reads an interpreter snippet
        assert (code, warned) == (0, []), out


@pytest.mark.parametrize('posture', ENFORCE)
@pytest.mark.parametrize('command,code', [
    (f'echo x > {STATE}', 2),
    (f'python3 -c \'open("{STATE}", "w").write("x")\'', 2),
    # #839: a state write the parser cannot read is logged; mode 0444 and the CLI hold it.
    (f'for r in a; do echo x > {STATE}; done', 0),
    ('echo x > .wuwei/days/$(date +%F)/state.json', 0),
    ('echo x | tee $(ls -d .wuwei/days/2026-10-03)/state.json', 0),
    (f'T="tee {STATE}"; echo x | $T', 0),
    (f"for i in 1; do echo 'echo x > {STATE}'; done | sh", 0),
])
def test_state_writes_still_refuse(workspace, posture, command, code, monkeypatch, capsys):
    configure(workspace, posture)
    found, out, _ = hook(workspace, command, monkeypatch, capsys)
    assert found == code, out
    if not code:
        assert [row['payload']['reason'] for row in events(workspace, 'guard.would_refuse')] == [
            shell.UNPARSED]


@pytest.mark.parametrize('posture', ENFORCE)
@pytest.mark.parametrize('probe', ['READ_LOOP', 'GIT_READ'])
def test_heartbeat_read_loop_exits_zero(workspace, posture, probe, monkeypatch, capsys):
    from wuwei import heartbeat
    from wuwei.commands.hook import HEARTBEAT_SESSION
    configure(workspace, posture)
    assert hook(workspace / '.wuwei', getattr(heartbeat, probe), monkeypatch, capsys,
                session=HEARTBEAT_SESSION) == (0, {}, '')


DAY = STATE.split('/')[2]
OWNER_LOOP = (f'cd .wuwei; for f in days/{DAY}/decisions/D-*.md; do echo "### $f"; cat $f; done; '
              f'cat days/{DAY}/state.json')


@pytest.mark.parametrize('posture', ENFORCE)
@pytest.mark.parametrize('command', [
    "git -C ../widget grep -n -E 'foo|bar' origin/main -- a.py b.py",
    'git -C ../widget blame -L 1,5 a.py',
    *(f'git -C ../widget {verb}' for verb in ('log', 'show HEAD', 'diff', 'ls-files',
                                               'rev-parse HEAD', 'fetch origin main')),
    OWNER_LOOP,
    f"cd .wuwei; cat days/{DAY}/lead.json; echo; echo '====='; cat config.toml; ls days/{DAY}",
])
def test_issue_470_owner_rows(workspace, posture, command, monkeypatch, capsys):
    configure(workspace, posture)
    code, out, _ = hook(workspace, command, monkeypatch, capsys)
    warned = [event['payload']['reason'] for event in events(workspace, 'guard.would_refuse')]
    assert code == 0, out
    if command == OWNER_LOOP:
        assert len(warned) == 1 and warned[0].startswith('workspace guard'), warned
    else:
        assert warned == []


SIXTH = ("gh run list -R o/r --workflow ci.yml --limit 6 --json status | python3 -c 'import sys; "
         "print(sys.stdin.read())'; R=widget; git -C $R log --oneline HEAD..origin/main | head -20")


@pytest.mark.parametrize('posture', ENFORCE)
@pytest.mark.parametrize('command', [
    SIXTH,
    'R=widget; git -C $R log --oneline; gh run list -R o/r',
])
def test_issue_470_sixth_row(workspace, posture, command, monkeypatch, capsys):
    configure(workspace, posture)
    code, out, _ = hook(workspace, command, monkeypatch, capsys)
    assert code == 0, out
    assert 'nonliteral guarded' not in json.dumps(out)


READ_LOOP = 'gh api repos/o/r/pulls/7/comments\ngh pr view 7 --json reviewRequests\n'


@pytest.mark.parametrize('posture', ENFORCE)
def test_issue_508_git_in_path(tmp_path, posture, monkeypatch, capsys):
    from pathlib import Path
    from fakes.integrity import seed
    base = tmp_path / '508-git-in' / 'gh' / 'github'
    root = base / 'workspace'
    (root / '.wuwei').mkdir(parents=True)
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    monkeypatch.delenv('CDPATH', raising=False)
    seed(root)
    configure(root, posture)
    (base / 'git-tools/bin').mkdir(parents=True)
    launcher = base / 'git-tools/bin/wuwei'
    launcher.symlink_to(Path(__file__).resolve().parents[1] / 'bin/wuwei')
    for command in (f'{launcher} state get', f'{launcher} plan approve --items A',
                    'pytest -q', f'ls {root}'):
        code, out, _ = hook(root, command, monkeypatch, capsys)
        assert code == 0, (command, out)
    assert events(root, 'guard.would_refuse') == []
    code, out, _ = hook(root, 'gh</dev/null pr merge 1 --admin', monkeypatch, capsys)
    assert code == 2, out  # review F1: a glued redirect is still a mention
    for command in ('git push --force origin main', 'git</dev/null push --force origin main'):
        code, out, _ = hook(root, command, monkeypatch, capsys)
        if posture == 'false':  # #839: a force push is logged with guards.enforce = false
            assert code == 0 and events(root, 'guard.would_refuse'), command
        else:
            assert code == 2, (command, out)


BRIEF = ("cat > brief.md <<'EOF'\nThe shepherd falls back to gh.\n"
         "Raise the PR with gh pr create; then git push.\nEOF")


@pytest.mark.parametrize('posture', ENFORCE)
def test_prose_heredoc_passes(workspace, posture, monkeypatch, capsys):
    # #671: git and gh words in a brief written by a reader are text.
    configure(workspace, posture)
    code, out, _ = hook(workspace, BRIEF, monkeypatch, capsys)
    assert (code, events(workspace, 'guard.would_refuse')) == (0, []), out


@pytest.mark.parametrize('posture', ENFORCE)
@pytest.mark.parametrize('command', ['sh -c "gi""t push --force"', 'g""it push --force'])
def test_quoted_name_is_judged_as_the_plain_command(workspace, posture, command, monkeypatch, capsys):
    # #671, #839: shlex joins the quoted name; the refusal adds no resolved: line.
    configure(workspace, posture)
    expected, _, _ = hook(workspace, 'git push --force', monkeypatch, capsys)
    code, out, _ = hook(workspace, command, monkeypatch, capsys)
    assert code == expected
    if code:
        assert 'resolved:' not in out['permissionDecisionReason']
    warned = [event['payload']['reason'] for event in events(workspace, 'guard.would_refuse')]
    assert not any(reason.startswith('opaque:') for reason in warned), warned


@pytest.mark.parametrize('posture', ENFORCE)
def test_continued_admin_merge_is_named(workspace, posture, monkeypatch, capsys):
    configure(workspace, posture)
    code, out, _ = hook(workspace, 'g\\\nh pr merge 5 --admin', monkeypatch, capsys)
    reason = out['permissionDecisionReason']
    assert code == 2
    assert 'admin merge is refused' in reason and 'resolved:' not in reason
