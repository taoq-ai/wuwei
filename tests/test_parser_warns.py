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
])
def test_state_writes_still_refuse(workspace, posture, command, monkeypatch, capsys):
    configure(workspace, posture)
    code, out, _ = hook(workspace, command, monkeypatch, capsys)
    assert code == 2, out


@pytest.mark.parametrize('posture', POSTURES)
def test_heartbeat_read_loop_exits_zero(workspace, posture, monkeypatch, capsys):
    from wuwei.commands.hook import HEARTBEAT_SESSION
    from wuwei.heartbeat import READ_LOOP
    configure(workspace, posture)
    assert hook(workspace / '.wuwei', READ_LOOP, monkeypatch, capsys,
                session=HEARTBEAT_SESSION) == (0, {}, '')


def test_decision_lint_warns_inline_snippet(workspace, monkeypatch, capsys):
    configure(workspace, 'observe')
    command = 'python3 -c \'print(open("days/x/decisions/D-1.md").read())\''
    code, _, _ = hook(workspace, command, monkeypatch, capsys, event='PostToolUse')
    warned = [event['payload']['reason'] for event in events(workspace, 'guard.would_refuse')]
    assert code == 0
    assert warned == [shell.UNPARSED]
