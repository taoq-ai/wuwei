"""Issue #226 acceptance through PreToolUse in process; no command is executed."""

import io
import json
import sys
from types import SimpleNamespace

import pytest

from fakes.replay import install_replay

NOT_A_REPOSITORY = {'exit': 128, 'stderr': 'fatal: not a git repository '
                    '(or any of the parent directories): .git'}


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    root = tmp_path / 'workspace'
    (root / 'worktrees/ITEM-1').mkdir(parents=True)
    (root / '.wuwei').mkdir()
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    monkeypatch.delenv('CDPATH', raising=False)
    from fakes.integrity import seed
    seed(root)
    (root / '.wuwei/config.toml').write_text('')
    return root


def hook(cwd, command, monkeypatch, capsys):
    from wuwei.commands.hook import run
    event = {'hook_event_name': 'PreToolUse', 'session_id': 'fixture',
             'transcript_path': str(cwd / 'transcript.jsonl'), 'cwd': str(cwd),
             'tool_name': 'Bash', 'tool_input': {'command': command}}
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(event)))
    code = run(SimpleNamespace(event='PreToolUse'))
    out = capsys.readouterr().out
    return code, json.loads(out)['hookSpecificOutput'] if out.strip() else {}


@pytest.mark.parametrize('where', ['.', 'worktrees/ITEM-1'])
@pytest.mark.parametrize('command, code, words', [
    ('x=$(pwd); echo $x', 0, ()),
    ('python3 -m pytest -q && git status', 0, ()),
    ('git push $(cat remote) main', 2, ('commit/push guard', 'deploy')),
    ('git status | python3', 2, ('deploy', 'python3')),
    ('cd $(git rev-parse --show-toplevel) && ls', 2, ('workspace guard',)),
])
def test_seat_command_forms(workspace, where, command, code, words, monkeypatch, capsys):
    actual, output = hook(workspace / where, command, monkeypatch, capsys)
    assert actual == code, (command, output)
    if code:
        assert output['permissionDecision'] == 'deny'
        for word in words:
            assert word in output['permissionDecisionReason'], output


def test_commit_outside_a_repository_says_so(workspace, monkeypatch, capsys):
    install_replay(monkeypatch, 'git', [NOT_A_REPOSITORY] * 8)
    code, output = hook(workspace, 'git commit -m wip', monkeypatch, capsys)
    assert code == 2
    reason = output['permissionDecisionReason']
    assert 'commit/push guard' in reason and 'not a git repository' in reason


def events(root, kind):
    return [json.loads(line) for path in root.glob('.wuwei/days/*/events.jsonl')
            for line in path.read_text().splitlines() if json.loads(line)['kind'] == kind]


@pytest.mark.parametrize('command', [
    'for r in a b; do git -C $r remote get-url origin; done',
    'git -C "$(cat repo.txt)" log -1 | head -5',
    'git -C repo symbolic-ref refs/remotes/origin/HEAD',
])
def test_issue_330_read_only_forms_pass(workspace, command, monkeypatch, capsys):
    assert hook(workspace, command, monkeypatch, capsys) == (0, {})
    assert events(workspace, 'hook.refusal') == []


@pytest.mark.parametrize('mode', ['enforce', 'shadow'])
@pytest.mark.parametrize('command, words', [
    ('for r in a b; do git -C $r push origin main; done', ('deploy',)),
    ('x=$(cat f); gh pr merge $x', ('deploy', 'PR guard')),
])
def test_issue_330_effectful_forms_refuse(workspace, mode, command, words, monkeypatch, capsys):
    if mode == 'shadow':
        (workspace / '.wuwei/config.toml').write_text('[guards]\nmode = "shadow"\n')
    code, output = hook(workspace, command, monkeypatch, capsys)
    assert code == 2 and output['permissionDecision'] == 'deny'
    reason = output['permissionDecisionReason']
    if mode == 'shadow':
        assert [e['payload']['guard'] for e in events(workspace, 'guard.would_refuse')] == ['commit_push']
        assert all(word in reason for word in words) and 'commit/push guard' not in reason, reason


def test_issue_330_shadow_records_commit_loop(workspace, monkeypatch, capsys):
    (workspace / '.wuwei/config.toml').write_text('[guards]\nmode = "shadow"\n')
    command = 'for r in a b; do git -C $r commit -m wip; done'
    assert hook(workspace, command, monkeypatch, capsys) == (0, {})
    assert [e['payload']['guard'] for e in events(workspace, 'guard.would_refuse')] == ['commit_push']
