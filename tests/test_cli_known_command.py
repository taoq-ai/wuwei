"""Issue #348: the plugin's own CLI is a known command for every Bash guard."""

import argparse
from importlib import import_module
import io
import json
from pathlib import Path
import pkgutil
import shutil
import sys
from types import SimpleNamespace

import pytest

from wuwei import commands, shell


def _registered():
    parser = argparse.ArgumentParser(prog='wuwei')
    subparsers = parser.add_subparsers(dest='command', required=True)
    for module in pkgutil.iter_modules(commands.__path__, commands.__name__ + '.'):
        if not module.name.rsplit('.', 1)[-1].startswith('_'):
            import_module(module.name).register(subparsers)
    paths = set()

    def walk(parser, path):
        children = [action for action in parser._actions
                    if isinstance(action, argparse._SubParsersAction)]
        if children:
            for name, child in children[0].choices.items():
                walk(child, (*path, name))
            return
        verbs = [action for action in parser._actions if action.dest == 'action' and action.choices]
        if not verbs:
            paths.add(' '.join(path))
            return
        paths.update(' '.join((*path, choice)) for choice in verbs[0].choices)
        if verbs[0].nargs == '?':
            paths.add(' '.join(path))

    walk(parser, ())
    return paths


def test_every_registered_command_is_in_exactly_one_set():
    from wuwei.guards.protect_state import _OWNER_ACTIONS
    assert _registered() == commands.READ_ONLY | commands.WRITES
    assert not commands.READ_ONLY & commands.WRITES
    assert {' '.join(pair).strip() for pair in _OWNER_ACTIONS} <= commands.WRITES


@pytest.mark.parametrize('args, expected', [
    (['status', '--line'], True), (['why', 'last', 'refusal'], True), (['doctor'], True),
    (['doctor', '--json'], True), (['config', 'check'], True), (['mcp', 'check', '--widget'], True),
    (['integrity', 'check'], True), (['shadow', 'report'], True), (['board'], True),
    (['sessions'], True), (['heartbeat'], True), (['calibrate', '--questions'], True),
    (['calibrate', '--repo', 'x', '--questions'], True), (['--version'], True),
    (['mcp', 'decide', '--help'], True), (['config', 'set', '-h'], True),
    ([], False), (['doctor', '--fix'], False), (['calibrate'], False),
    (['calibrate', 'export', 'x', '--questions'], False), (['mcp', 'decide', 'D-1', 'proceed'], False),
    (['mcp', 'decide', '--', '--help'], False), (['config', 'show'], False),
    (['config', 'set', 'k', 'v'], False), (['integrity', 'reconfirm'], False), (['state', 'get'], False),
])
def test_read_only(args, expected):
    assert commands.read_only(args) is expected


POSTURES = ('observe', 'guarded', 'strict')
LAUNCHER = Path(__file__).resolve().parents[1] / 'bin/wuwei'
GREP = " | grep -n -A3 -i 'repos\\|\\[repo\\|tracker' | head -40"


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    root = tmp_path / 'workspace'
    (root / '.wuwei').mkdir(parents=True)
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    monkeypatch.delenv('CDPATH', raising=False)
    from fakes.integrity import seed
    seed(root)
    exe = tmp_path / 'plugin-cache/0.12.0/bin/wuwei'
    exe.parent.mkdir(parents=True)
    shutil.copy(LAUNCHER, exe)
    (root / '.wuwei/executable').write_text(f'{exe}\n')
    return SimpleNamespace(root=root, exe=str(exe), other=tmp_path / 'elsewhere/bin/wuwei')


def configure(root, posture):
    (root / '.wuwei/config.toml').write_text(f'[security]\nposture = "{posture}"\n')


def hook(cwd, command, monkeypatch, capsys):
    from wuwei.commands.hook import run
    payload = {'hook_event_name': 'PreToolUse', 'session_id': 'fixture',
               'transcript_path': str(cwd / 'transcript.jsonl'), 'cwd': str(cwd),
               'tool_name': 'Bash', 'tool_input': {'command': command}}
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(payload)))
    code = run(SimpleNamespace(event='PreToolUse'))
    captured = capsys.readouterr()
    out = json.loads(captured.out)['hookSpecificOutput'] if captured.out.strip() else {}
    return code, out


def events(root, *kinds):
    return [json.loads(line) for path in root.glob('.wuwei/days/*/events.jsonl')
            for line in path.read_text().splitlines() if json.loads(line)['kind'] in kinds]


def passes(workspace, command, posture, monkeypatch, capsys):
    configure(workspace.root, posture)
    code, out = hook(workspace.root, command, monkeypatch, capsys)
    assert code == 0, out
    assert events(workspace.root, 'hook.refusal', 'guard.would_refuse') == []


def test_classify_knows_the_cli(workspace):
    p1 = f'{workspace.exe} config check' + GREP
    cwd = str(workspace.root)
    assert shell.classify(p1, cwd=cwd).readonly
    assert not shell.classify(p1).readonly
    assert shell.classify('wuwei status --line | head -5').readonly
    assert not shell.classify(f'{workspace.exe} status --line > out.txt', cwd=cwd).readonly
    assert not shell.classify(f'{workspace.exe} config set k v | head -1', cwd=cwd).readonly
    assert shell.unread(p1, cwd=cwd) == (0, '')


@pytest.mark.parametrize('posture', POSTURES)
@pytest.mark.parametrize('form', ['{exe} mcp check','{exe} config show', '{exe} config check' + GREP,
                                  '{exe} mcp check' + GREP, '{launcher} config check' + GREP,
                                  'wuwei config check' + GREP])
def test_read_commands_pass(workspace, posture, form, monkeypatch, capsys):
    passes(workspace, form.format(exe=workspace.exe, launcher=LAUNCHER), posture, monkeypatch, capsys)


@pytest.mark.parametrize('posture', POSTURES)
@pytest.mark.parametrize('form', ['{exe} mcp decide --help', '{exe} config set --help'])
def test_help_passes(workspace, posture, form, monkeypatch, capsys):
    passes(workspace, form.format(exe=workspace.exe), posture, monkeypatch, capsys)


@pytest.mark.parametrize('posture', POSTURES)
@pytest.mark.parametrize('form', ['{exe} mcp decide D-1 proceed', '{exe} mcp decide -- --help'])
def test_owner_actions_keep_the_host_terminal_rule(workspace, posture, form, monkeypatch, capsys):
    configure(workspace.root, posture)
    code, out = hook(workspace.root, form.format(exe=workspace.exe), monkeypatch, capsys)
    assert code == 2
    assert 'MCP decisions require the owner terminal' in out['permissionDecisionReason']


@pytest.mark.parametrize('posture', POSTURES)
def test_writer_subcommand_is_not_opaque(workspace, posture, monkeypatch, capsys):
    configure(workspace.root, posture)
    code, out = hook(workspace.root, f'{workspace.exe} note add --body "rm the stale config"',
                     monkeypatch, capsys)
    assert code == 0, out
    assert events(workspace.root, 'guard.would_refuse') == []


@pytest.mark.parametrize('posture', POSTURES)
def test_unrecognised_copy_stays_opaque(workspace, posture, monkeypatch, capsys):
    workspace.other.parent.mkdir(parents=True)
    shutil.copy(LAUNCHER, workspace.other)
    configure(workspace.root, posture)
    code, out = hook(workspace.root, f'{workspace.other} config check' + GREP, monkeypatch, capsys)
    warned = [event['payload']['reason'] for event in events(workspace.root, 'guard.would_refuse')]
    if posture != 'observe':
        assert code == 2
        assert 'opaque interpreter command' in out['permissionDecisionReason']
    else:
        assert code == 0, out
        assert len(warned) == 1 and 'opaque interpreter command' in warned[0], warned
