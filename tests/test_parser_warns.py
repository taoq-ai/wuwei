"""Issue #347 acceptance through the hook in process; no command is executed."""

import io
import json
import sys
from types import SimpleNamespace

import pytest

from wuwei import shell


S1 = 'cd .wuwei/ziran && for r in a b c; do cat $r/report.json; done'
S2 = 'ls; ls days/x; cat days/x/decisions/D-1.md; grep -n rm config.toml'
S3 = 'W=$(cat .wuwei/executable); $W plan session abc --take-over; $W mcp check'
S4 = ('python3 -P -c \'import subprocess;r=subprocess.run(["git","log","-1"]);'
      'print(open("config.toml").read())\'')
S5 = 'mkdir -p ../scratch && cd ../scratch && ls'
POSTURES = ('observe', 'guarded', 'strict')
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


def configure(root, posture):
    (root / '.wuwei/config.toml').write_text(f'[security]\nposture = "{posture}"\n')


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


@pytest.mark.parametrize('posture', POSTURES)
@pytest.mark.parametrize('name, command', [('S1', S1), ('S2', S2), ('S3', S3), ('S4', S4), ('S5', S5)])
def test_five_shapes(workspace, posture, name, command, monkeypatch, capsys):
    configure(workspace, posture)
    code, out, _ = hook(workspace, command, monkeypatch, capsys)
    warned = [event['payload']['reason'] for event in events(workspace, 'guard.would_refuse')]
    if name == 'S2':
        assert (code, warned) == (0, [])
    elif name in ('S1', 'S5'):
        assert code == 0, out
        assert len(warned) == 1 and warned[0].startswith('workspace guard'), warned
        assert '(cd <dir> && <command>)' in warned[0]
    elif posture == 'strict':
        assert code == 2
        assert out['permissionDecisionReason'] == shell.UNPARSED
        assert warned == []
    else:
        assert code == 0, out
        assert len(warned) == 1 and warned[0].startswith('unparsed'), warned


@pytest.mark.parametrize('posture', POSTURES)
@pytest.mark.parametrize('command', [
    'for r in a b; do git -C $r push origin main; done',
    'x=$(git push origin main)',
    'G=git; $G push origin main',
    'cat <(gh pr merge 17)',
    'diff <(git push origin main) x',
])
def test_publish_forms_still_refuse(workspace, posture, command, monkeypatch, capsys):
    configure(workspace, posture)
    code, out, _ = hook(workspace, command, monkeypatch, capsys)
    recorded = [json.loads(line)['payload'] for line in next(workspace.glob('.wuwei/days/*/events.jsonl')).read_text().splitlines()
                if json.loads(line)['kind'] == 'hook.refusal']
    assert code == 2 and 'deploy' in [row['guard'] for row in recorded[-1]['refusals']], out


@pytest.mark.parametrize('posture', POSTURES)
@pytest.mark.parametrize('command', [
    f'echo x > {STATE}',
    f'for r in a; do echo x > {STATE}; done',
    'echo x > .wuwei/days/$(date +%F)/state.json',
    'echo x | tee $(ls -d .wuwei/days/2026-10-03)/state.json',
    f'T="tee {STATE}"; echo x | $T',
    f'python3 -c \'open("{STATE}", "w").write("x")\'',
    'cd .wuwei && for i in 1; do sed -i s/a/b/ config.toml; done',
    'cd .wuwei && for i in 1; do echo x > config.toml; done',
    'cd .wuwei && for i in 1; do echo x > voice.md; done',
    f"for i in 1; do echo 'echo x > {STATE}'; done | sh",
])
def test_state_writes_still_refuse(workspace, posture, command, monkeypatch, capsys):
    configure(workspace, posture)
    code, out, _ = hook(workspace, command, monkeypatch, capsys)
    assert code == 2, out


@pytest.mark.parametrize('posture', POSTURES)
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


@pytest.mark.parametrize('posture', POSTURES)
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


@pytest.mark.parametrize('posture', POSTURES)
def test_issue_470_unknown_git(workspace, posture, monkeypatch, capsys):
    configure(workspace, posture)
    code, out, _ = hook(workspace, 'git -C ../widget frobnicate', monkeypatch, capsys)
    warned = [event['payload'] for event in events(workspace, 'guard.would_refuse')]
    prefix = 'unknown git subcommand frobnicate; if it publishes'
    if posture == 'strict':
        assert code == 2 and warned == []
        assert out['permissionDecisionReason'].startswith(prefix), out
    else:
        assert code == 0, out
        assert len(warned) == 1 and warned[0]['guard'] == 'deploy', warned
        assert warned[0]['reason'].startswith(prefix)


@pytest.mark.parametrize('posture', POSTURES)
def test_issue_470_commit_substitution(workspace, posture, monkeypatch, capsys):
    configure(workspace, posture)
    code, out, _ = hook(workspace, 'x=$(git commit -m y)', monkeypatch, capsys)
    warned = [event['payload']['guard'] for event in events(workspace, 'guard.would_refuse')]
    if posture == 'strict':
        assert code == 2, out
    else:  # #530: an opaque call that names no publish target warns below strict
        assert (code, len(warned)) == (0, 1), out


@pytest.mark.parametrize('posture', POSTURES)
@pytest.mark.parametrize('command', [
    'git -C ../widget grep -O\'sh -c "git push origin main"\' a',
    "git -C ../widget grep --open-files-in-pager='gh pr merge 1' a",
    "git -C ../widget fetch --upload-pack='gh pr merge 1' origin",
    "git -C ../widget grep --open='gh pr merge 1' a",
    "git -C ../widget fetch --upload='gh pr merge 1' origin",
    'git -C ../widget ls-remote -u \'sh -c "gh pr merge 1"\' origin',
    'R=widget; git -C $R push origin main',
    'R=widget; git -C $R push origin main; gh run list -R o/r',
])
def test_issue_470_run_options_and_variable_push_refuse(workspace, posture, command, monkeypatch, capsys):
    configure(workspace, posture)
    code, out, _ = hook(workspace, command, monkeypatch, capsys)
    assert code == 2, out


SIXTH = ("gh run list -R o/r --workflow ci.yml --limit 6 --json status | python3 -c 'import sys; "
         "print(sys.stdin.read())'; R=widget; git -C $R log --oneline HEAD..origin/main | head -20")


@pytest.mark.parametrize('posture', POSTURES)
@pytest.mark.parametrize('command', [
    SIXTH,
    'R=widget; git -C $R log --oneline; gh run list -R o/r',
])
def test_issue_470_sixth_row(workspace, posture, command, monkeypatch, capsys):
    configure(workspace, posture)
    code, out, _ = hook(workspace, command, monkeypatch, capsys)
    if posture != 'strict' or command != SIXTH:  # strict blocks the unparsed python -c read
        assert code == 0, out
    assert 'nonliteral guarded' not in json.dumps(out)


def test_decision_lint_warns_inline_snippet(workspace, monkeypatch, capsys):
    configure(workspace, 'observe')
    command = 'python3 -c \'print(open("days/x/decisions/D-1.md").read())\''
    code, _, _ = hook(workspace, command, monkeypatch, capsys, event='PostToolUse')
    warned = [event['payload']['reason'] for event in events(workspace, 'guard.would_refuse')]
    assert code == 0
    assert warned == [shell.UNPARSED]


@pytest.mark.parametrize('posture', POSTURES)
@pytest.mark.parametrize('command', ['for f in a b; do git push origin $f; done',
                                     'for f in a b; do git commit -m $f; done'])
def test_opaque_loop_without_publish_target_warns(workspace, posture, command, monkeypatch, capsys):
    # #530: below strict an opaque call naming no publish target runs with one warning.
    configure(workspace, posture)
    code, out, _ = hook(workspace, command, monkeypatch, capsys)
    warned = [event['payload'] for event in events(workspace, 'guard.would_refuse')]
    if posture == 'strict':
        assert code == 2 and warned == [], out
    else:
        assert code == 0 and len(warned) == 1 and warned[0]['reason'].startswith('opaque: '), (out, warned)


READ_LOOP = 'gh api repos/o/r/pulls/7/comments\ngh pr view 7 --json reviewRequests\n'


@pytest.mark.parametrize('posture', POSTURES)
@pytest.mark.parametrize('command,named', [
    ('bash loop.sh', 'loop.sh'),
    ('gh pr view $(git rev-parse --abbrev-ref HEAD)', 'substitution'),
    ('''python3 -c "import subprocess; print(subprocess.run(['gh','pr','view','7']).stdout)"''', 'inline'),
])
def test_opaque_read_warns_below_strict(workspace, posture, command, named, monkeypatch, capsys):
    # #530 US1.1, US1.2: one guard.would_refuse naming what was opaque; strict refuses as today.
    configure(workspace, posture)
    (workspace / 'loop.sh').write_text(READ_LOOP)
    code, out, _ = hook(workspace, command, monkeypatch, capsys)
    warned = [event['payload'] for event in events(workspace, 'guard.would_refuse')]
    if posture == 'strict':
        assert code == 2 and warned == [], out
        return
    assert code == 0, out
    [event] = warned
    assert event['reason'].startswith('opaque: ') and named in event['reason'], event
    assert (event['area'], event['level']) == ('publish', 'warn')


@pytest.mark.parametrize('posture', POSTURES)
@pytest.mark.parametrize('script,command', [
    ('git push origin main\n', 'bash loop.sh'),
    ('kubectl apply -f x\n', 'bash loop.sh'),
    ('gh release create v1\n', 'bash loop.sh'),
    ('gh pr review 7 --approve\n', 'bash loop.sh'),
    ('', '''python3 -c "import subprocess; subprocess.run(['gh','pr','comment','7','--body','x'])"'''),
    ('', '''python3 -c "import os; os.system('git push --force origin x')"'''),
])
def test_opaque_publish_target_still_refuses(workspace, posture, script, command, monkeypatch, capsys):
    # #530 US1.3: the literal text names a publish target, so every posture refuses it.
    configure(workspace, posture)
    (workspace / 'loop.sh').write_text(script)
    code, out, _ = hook(workspace, command, monkeypatch, capsys)
    assert code == 2, out
    assert not [event for event in events(workspace, 'guard.would_refuse')
                if event['payload']['reason'].startswith('opaque')]
