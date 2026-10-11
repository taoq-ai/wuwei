"""Issue #226 acceptance through PreToolUse in process; no command is executed."""

import io
import json
import sys
from types import SimpleNamespace

import pytest


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
    ('git push $(cat remote) main', 0, ()),  # #839: not a force push or a default branch
    ('git push --force $(cat remote) main', 2, ('force-push is refused',)),
    ('git status | python3', 0, ()),  # #530: an unparsed read warns
    ('cd $(git rev-parse --show-toplevel) && ls', 0, ()),
])
def test_seat_command_forms(workspace, where, command, code, words, monkeypatch, capsys):
    actual, output = hook(workspace / where, command, monkeypatch, capsys)
    assert actual == code, (command, output)
    if code:
        assert output['permissionDecision'] == 'deny'
        for word in words:
            assert word in refused(workspace), output


def refused(root):
    """Every guard reason the hook.refusal events recorded; the hook prints one (#362)."""
    import glob
    return ' '.join(row['reason'] for path in glob.glob(str(root / '.wuwei/days/*/events.jsonl'))
                    for line in open(path).read().splitlines() if json.loads(line)['kind'] == 'hook.refusal'
                    for row in json.loads(line)['payload'].get('refusals', []))


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


@pytest.mark.parametrize('mode', ['enforce', 'log'])
def test_issue_330_effectful_forms(workspace, mode, monkeypatch, capsys):
    # #839: a merge is refused by its argv in both settings; a force push in a loop is read too.
    if mode == 'log':
        (workspace / '.wuwei/config.toml').write_text('[guards]\nenforce = false\n')
    code, output = hook(workspace, 'x=$(cat f); gh pr merge $x', monkeypatch, capsys)
    assert code == 2 and output['permissionDecisionReason'].startswith('merge policy')
    assert hook(workspace, 'for r in a b; do git -C $r commit -m wip; done', monkeypatch, capsys) == (0, {})
    code, _ = hook(workspace, 'for r in a b; do git -C $r push --force origin x; done', monkeypatch, capsys)
    assert code == (0 if mode == 'log' else 2)
    assert len(events(workspace, 'guard.would_refuse')) == (1 if mode == 'log' else 0)
