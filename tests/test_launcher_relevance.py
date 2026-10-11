"""Issue #205 acceptance through PreToolUse in process; no command is executed."""

import io
import json
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace

import pytest

LAUNCHER = Path(__file__).resolve().parents[1] / 'bin/wuwei'


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
    recorded = tmp_path / 'previous-plugin/bin/wuwei'
    recorded.parent.mkdir(parents=True)
    shutil.copy(LAUNCHER, recorded)
    (root / '.wuwei/executable').write_text(f'{recorded}\n')
    return root, recorded


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
def test_launcher_and_irrelevant_script_pass(workspace, where, monkeypatch, capsys):
    root, recorded = workspace
    cwd = root / where
    (cwd / 'sub.sh').write_text('x=$(pwd)\n')
    (cwd / 'sub.sh').chmod(0o755)
    (cwd / 'strict.sh').write_text('#!/usr/bin/env bash\nset -euo pipefail\n'
                                   "IFS=$'\\n\\t'\npython3 -m pytest -q\n")
    (cwd / 'strict.sh').chmod(0o755)
    for command in (f'{LAUNCHER} state get', f'{recorded} build check ITEM-1',
                    'wuwei state get', './sub.sh', './strict.sh'):
        code, output = hook(cwd, command, monkeypatch, capsys)
        assert code == 0, (command, output)


@pytest.mark.parametrize('where', ['.', 'worktrees/ITEM-1'])
def test_force_push_script_is_not_read(workspace, where, monkeypatch, capsys):
    # #839: a script's text is a ceiling the code host's protected refs hold (design 9.1).
    root, _ = workspace
    cwd = root / where
    (cwd / 'push.sh').write_text('git push --force origin main\n')
    (cwd / 'push.sh').chmod(0o755)
    assert hook(cwd, './push.sh', monkeypatch, capsys)[0] == 0
