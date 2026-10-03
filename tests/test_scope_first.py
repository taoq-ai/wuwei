"""Outside a WUWEI workspace every hook returns 0 before any guard reads the call (#323)."""

import importlib
import io
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
PAYLOADS = sorted((ROOT / 'tests/payloads').glob('*/*.json'))

TRIAL = [
    "set -e; P=/tmp/x; cd $P && python3 - <<'PYEOF'\n"
    "import subprocess\n"
    "print(subprocess.run(['gh', 'pr', 'view', '7'], capture_output=True))\n"
    "print(subprocess.run(['git', 'status'], capture_output=True))\n"
    "PYEOF",
    'ls ~/x/wuwei/',
]

SHAPES = [
    'git push "', 'gh pr merge "', 'ls ~/x', 'cd ~nosuchuser/x && git push',
    'git push $(git rev-parse HEAD)', 'git push `git rev-parse HEAD`',
    'for r in a b; do git -C $r push origin main; done',
    'if true; then gh pr merge 9; fi',
    "cat <<'EOF'\ngit push --force\ngh pr merge 9\nEOF",
    'git symbolic-ref refs/remotes/origin/HEAD', 'gh foo bar',
    'echo x > .wuwei/days/2026-10-03/state.json', 'rm -rf .wuwei',
]

GUARD_TABLES = ('test_commit_push', 'test_pr_guards', 'test_deploy', 'test_protect_state',
                'test_owner_actions', 'test_seat_command_forms', 'test_pr_ownership',
                'test_shell')
COMMAND_ARGS = ('command', 'script', 'form', 'wrapper', 'operation')


@pytest.fixture
def outside(tmp_path, monkeypatch):
    return outside_dir(tmp_path, monkeypatch)


def outside_dir(tmp_path, monkeypatch):
    # Three levels deep: rows with .. or ../.. stay inside this test's directory.
    path = tmp_path / 'host/home/outside'
    path.mkdir(parents=True)
    monkeypatch.setenv('HOME', str(path))
    for name in ('WUWEI_WORKSPACE', 'GIT_DIR', 'GIT_WORK_TREE', 'WUWEI_SEAT_ROLE'):
        monkeypatch.delenv(name, raising=False)
    return path


def hook(event, payload):
    from wuwei.commands.hook import run
    stdin, stdout, stderr = sys.stdin, sys.stdout, sys.stderr
    sys.stdin, sys.stdout, sys.stderr = io.StringIO(json.dumps(payload)), io.StringIO(), io.StringIO()
    try:
        code = run(SimpleNamespace(event=event))
        return code, sys.stdout.getvalue(), sys.stderr.getvalue()
    finally:
        sys.stdin, sys.stdout, sys.stderr = stdin, stdout, stderr


def payload(event, cwd, tool_name='Bash', tool_input=None):
    return {'session_id': 's', 'transcript_path': str(cwd / 't.jsonl'), 'cwd': str(cwd),
            'hook_event_name': event, 'tool_name': tool_name, 'tool_input': tool_input or {}}


def assert_outside_clean(rows, outside, events=('PreToolUse', 'PostToolUse')):
    for row in rows:
        for event in events:
            result = hook(event, payload(event, outside, tool_input={'command': row}))
            assert result == (0, '', ''), (event, row, result)
    assert not list(outside.parent.parent.rglob('.wuwei'))


class Placeholder(dict):
    def __init__(self, outside):
        self.outside = outside

    def __missing__(self, key):
        return str(self.outside / key)


def harvested_rows(outside):
    rows = set()
    for name in GUARD_TABLES:
        module = importlib.import_module(name)
        for function in vars(module).values():
            for mark in getattr(function, 'pytestmark', ()):
                if mark.name != 'parametrize':
                    continue
                names, values = mark.args[0], mark.args[1]
                names = [n.strip() for n in names.split(',')] if isinstance(names, str) else list(names)
                for value in values:
                    value = value.values if hasattr(value, 'values') else value
                    value = (value,) if len(names) == 1 else value
                    for argname, item in zip(names, value):
                        if argname in COMMAND_ARGS and isinstance(item, str):
                            try:
                                rows.add(item.format_map(Placeholder(outside)))
                            except (ValueError, IndexError, KeyError, AttributeError):
                                rows.add(item)
    return sorted(rows)


def test_trial_commands_outside_are_clean(outside):
    assert_outside_clean(TRIAL, outside)


def test_gate_precedes_discovery(outside, monkeypatch):
    from wuwei.commands import hook as module

    def never():
        raise AssertionError('discover called outside a workspace')

    monkeypatch.setattr(module, 'discover', never)
    assert_outside_clean(TRIAL + SHAPES, outside)


def test_reaches_workspace(tmp_path, outside, monkeypatch):
    from wuwei.commands.hook import reaches_workspace
    host = tmp_path / 'host2'
    ws = host / 'ws'
    (ws / '.wuwei').mkdir(parents=True)
    (ws / '.wuwei/config.toml').write_text('')
    (ws / 'repo/.git').mkdir(parents=True)
    managed = tmp_path / 'managed'
    gitdir = tmp_path / 'gitdir'
    gitdir.mkdir()
    (gitdir / 'wuwei-workspace').write_text(str(ws))
    managed.mkdir()
    (managed / '.git').write_text(f'gitdir: {gitdir}')
    linked = tmp_path / 'linked'
    linked.mkdir()
    (linked / '.wuwei').symlink_to(ws / '.wuwei')

    def bash(command, cwd=outside):
        return payload('PreToolUse', cwd, tool_input={'command': command})

    assert reaches_workspace(bash('ls'), ws)
    assert reaches_workspace(payload('PreToolUse', outside, 'NotebookEdit',
                                     {'notebook_path': str(ws / 'repo/n.ipynb')}), None)
    for command in (f'git -C {ws}/repo push --force origin main',
                    f'git --git-dir={ws}/repo/.git push', f'git -C{ws}/repo push',
                    f'GIT_DIR={ws}/repo/.git git push', f"sh -c 'cd {ws}/repo && git push'",
                    f'eval "cd {ws}"', f'rm -rf {host}', f'git -C {managed} push',
                    f'ls {linked}/x'):
        assert reaches_workspace(bash(command), None), command
    assert reaches_workspace(bash('cd ws && git push', cwd=host), None)
    for command in (*TRIAL, 'cd $P && git push --force', 'ls ~nosuchuser/x',
                    'cd /tmp/x && git push'):
        assert not reaches_workspace(bash(command), None), command
    assert not reaches_workspace(payload('PreToolUse', outside, 'Write',
                                         {'file_path': str(outside / 'f')}), None)
    monkeypatch.setenv('HOME', str(host))
    monkeypatch.setenv('WS', str(ws))
    for command in ('rm -rf "$HOME/ws/.wuwei"', 'rm -rf ${WS}/.wuwei', 'cat ~/ws/.wuwei/config.toml'):
        assert reaches_workspace(bash(command), None), command
    monkeypatch.setenv('GIT_DIR', str(ws / 'repo/.git'))
    assert reaches_workspace(bash('git push'), None)
    monkeypatch.delenv('GIT_DIR')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(ws))
    assert reaches_workspace(bash('ls'), None)


def test_every_table_row_outside_is_clean(outside):
    rows = harvested_rows(outside)
    assert len(rows) >= 500
    assert_outside_clean(rows, outside)


def test_recorded_payloads_and_probes_outside_are_clean(outside):
    from test_guard_mutation import PROBES
    calls = [(path.parent.name, {**json.loads(path.read_text()), 'cwd': str(outside)})
             for path in PAYLOADS if path.suffix == '.json']
    calls += [(event, payload(event, outside, tool, tool_input))
              for (_, event, _, _), (tool, tool_input, _) in PROBES.items()]
    for event, call in calls:
        assert hook(event, call) == (0, '', ''), (event, call)
    assert not list(outside.parent.parent.rglob('.wuwei'))


def test_inside_verdicts_unchanged(tmp_path, outside, monkeypatch):
    from fakes.integrity import seed
    ws = tmp_path / 'host2/ws'
    (ws / '.wuwei').mkdir(parents=True)
    (ws / '.wuwei/config.toml').write_text('')
    seed(ws)
    code, _, err = hook('PreToolUse', payload('PreToolUse', ws, tool_input={'command': TRIAL[0]}))
    assert code == 2
    assert 'commit/push guard could not run' in err and 'PR guard could not run' in err
    monkeypatch.setenv('WS', str(ws))
    for command in (f'rm -rf {ws}/.wuwei/days', f'rm -rf {ws.parent}', 'rm -rf "$WS/.wuwei"'):
        code, _, err = hook('PreToolUse', payload('PreToolUse', outside, tool_input={'command': command}))
        assert code == 2 and 'protect' in err.lower(), (command, err)
