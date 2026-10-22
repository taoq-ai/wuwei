"""The hook launcher finds a Python 3.11 or later on Windows, macOS and Linux (item launcher-python)."""

import ast
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import pytest

from wuwei import hook, setup, ws

PLUGIN = Path(__file__).resolve().parents[1]
SHELLS = [s for s in ('sh', 'dash', 'bash') if shutil.which(s)]  # bash stands in for Git Bash on Windows
REJECT = 'Unknown option: -P\\nusage: {name} [option] ... [-c cmd | -m mod | file | -] [arg] ...\\n'


def shim(folder, name, version):
    """An interpreter called name: it answers -V with version and, below 3.11, rejects -P the way 3.9 does;
    otherwise it notes its name in used.txt and runs this Python. A shim named py runs only after -3."""
    old = tuple(map(int, version.split('.')[:2])) < (3, 11)
    folder.mkdir(parents=True, exist_ok=True)
    text = ('#!/bin/sh\n' + ('[ "$1" = -3 ] || exit 9\nshift\n' if name == 'py' else '')
            + f'case "$1" in -V|--version) echo "Python {version}"; exit 0;; esac\n'
            + (f'for a; do [ "$a" = -P ] && {{ printf \'{REJECT.format(name=name)}\' >&2; exit 2; }}; done\n' if old else '')
            + f'echo "{name}" >> "{folder / "used.txt"}"\nexec "{sys.executable}" "$@"\n')
    (folder / name).write_text(text)
    (folder / name).chmod(0o755)
    return folder / name


def launch(tmp_path, shims, shell='sh', python=None, payload=None):
    """Runs the hook entry with only the shims (and dirname) on PATH, as a harness with a short PATH would."""
    tools = tmp_path / 'tools'
    tools.mkdir(exist_ok=True)
    if not (tools / 'dirname').exists():
        (tools / 'dirname').symlink_to(shutil.which('dirname'))
    env = {k: v for k, v in os.environ.items() if k not in ('WUWEI_PYTHON', 'CLAUDE_CODE_REMOTE')}
    env['PATH'] = os.pathsep.join([str(shims), str(tools)])
    if python:
        env['WUWEI_PYTHON'] = str(python)
    payload = payload or {'tool_name': 'Write', 'tool_input': {'file_path': str(tmp_path / ws.DIR / 'ledger' / 'x.jsonl'), 'content': 'x'}}
    return subprocess.run([shutil.which(shell), str(PLUGIN / 'bin' / 'wuwei'), 'hook', 'PreToolUse'],
                          input=json.dumps({'cwd': str(tmp_path), **payload}), capture_output=True, text=True, env=env, cwd=tmp_path)


def used(shims):
    path = shims / 'used.txt'
    return path.read_text().split() if path.is_file() else []


def judged(done):
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)['hookSpecificOutput']['permissionDecision']


@pytest.mark.parametrize('shell', SHELLS)
def test_an_old_python3_first_on_path_gives_way_to_python3_12(root, tmp_path, shell):
    shims = tmp_path / 'shims'
    shim(shims, 'python3', '3.9.6')
    shim(shims, 'python3.12', '3.12.4')
    assert judged(launch(root, shims, shell)) == 'deny'
    assert used(shims) == ['python3.12']


@pytest.mark.parametrize('shell', SHELLS)
def test_only_an_old_python3_exits_2_naming_it_and_the_version_wuwei_needs(root, tmp_path, shell):
    shims = tmp_path / 'shims'
    shim(shims, 'python3', '3.9.6')
    done = launch(root, shims, shell)
    assert done.returncode == 2 and done.stdout == '' and used(shims) == []
    assert len(done.stderr.splitlines()) == 1, done.stderr
    assert 'python3 3.9.6' in done.stderr and 'Python 3.11 or later' in done.stderr
    assert 'python3.13 not found' in done.stderr and 'py -3 not found' in done.stderr and 'Unknown option' not in done.stderr


def test_no_python_at_all_still_refuses_the_call_with_the_clear_line(root, tmp_path):
    done = launch(root, tmp_path / 'empty')
    assert done.returncode == 2 and 'Python 3.11 or later' in done.stderr and 'python3 not found' in done.stderr


@pytest.mark.parametrize('shell', SHELLS)
def test_wuwei_python_names_the_interpreter_when_it_is_3_11_or_later(root, tmp_path, shell):
    shims, own = tmp_path / 'shims', shim(tmp_path / 'own dir', 'mypython', '3.13.1')
    shim(shims, 'python3.12', '3.12.4')
    assert judged(launch(root, shims, shell, python=own)) == 'deny'
    assert used(own.parent) == ['mypython'] and used(shims) == []


def test_an_old_wuwei_python_is_named_and_the_search_goes_on(root, tmp_path):
    shims, own = tmp_path / 'shims', shim(tmp_path / 'own', 'oldpython', '3.10.12')
    shim(shims, 'python3', '3.12.4')
    assert judged(launch(root, shims, python=own)) == 'deny' and used(shims) == ['python3'] and used(own.parent) == []
    shutil.rmtree(shims)
    done = launch(root, shims, python=own)
    assert done.returncode == 2 and f'{own} 3.10.12' in done.stderr


@pytest.mark.parametrize('shell', SHELLS)
def test_windows_with_only_the_py_launcher_runs_wuwei_with_py_3(root, tmp_path, shell):
    shims = tmp_path / 'shims'
    shim(shims, 'py', '3.12.4')
    assert judged(launch(root, shims, shell)) == 'deny'
    assert used(shims) == ['py']


def test_the_launcher_is_posix_sh():
    for shell in SHELLS:
        assert subprocess.run([shell, '-n', str(PLUGIN / 'bin' / 'wuwei')]).returncode == 0, shell
    text = (PLUGIN / 'bin' / 'wuwei').read_text()
    assert not re.search(r'\[\[|\bfunction\b|\blocal\b|\$\{\w+//|<<<|\bsource\b', text)
    assert '-I -P -S -c' in text and 'unset PYTHONEXECUTABLE' in text


def code(text, pattern):
    return ast.dump(ast.parse(re.search(pattern, text, re.S).group(1)))


def test_the_windows_entry_runs_the_same_bootstrap_and_tries_wuwei_python_then_py_3_then_python():
    cmd = (PLUGIN / 'bin' / 'wuwei.cmd').read_bytes().decode()
    assert '\n' not in cmd.replace('\r\n', '')  # cmd.exe reads labels reliably only from CRLF lines
    found = re.search(r'-c "exec\((.*?)\)"', cmd)
    assert found and '"' not in found.group(1) and '%' not in found.group(1)  # nothing cmd.exe would read
    assert ast.dump(ast.parse(ast.literal_eval(found.group(1)))) == code(
        (PLUGIN / 'bin' / 'wuwei').read_text(), r"-I -P -S -c '(.*?)' \"\$plugin_root/cli\"")
    order = [cmd.index(s) for s in ('call :fits "%WUWEI_PYTHON%"', 'call :fits py -3', 'call :fits python\r\n')]
    assert order == sorted(order) and '-I -P -S -c' in cmd and 'set "PYTHONEXECUTABLE="' in cmd
    assert 'Python 3.11 or later' in cmd and 'exit /b 2' in cmd


def test_the_windows_bootstrap_fails_closed_like_the_sh_one(root, tmp_path):
    entry = ast.literal_eval(re.search(r'-c "exec\((.*?)\)"', (PLUGIN / 'bin' / 'wuwei.cmd').read_text()).group(1))
    plugin = tmp_path / 'plugin'
    for name in ('cli', '.claude-plugin'):
        shutil.copytree(PLUGIN / name, plugin / name, ignore=shutil.ignore_patterns('__pycache__'))
    run = lambda: subprocess.run([sys.executable, '-I', '-P', '-S', '-c', entry, str(plugin / 'cli'), str(plugin), 'hook', 'PreToolUse'],  # noqa: E731
                                 input=json.dumps({'cwd': str(root), 'tool_name': 'Read', 'tool_input': {}}), capture_output=True, text=True, cwd=root)
    assert run().returncode == 0
    (plugin / 'cli' / 'wuwei' / 'ws.py').write_text("raise KeyError('broken')\n")
    done = run()
    assert done.returncode == 2 and done.stderr.startswith('wuwei hook PreToolUse: KeyError')


def test_hooks_json_names_the_windows_entry_for_codex():
    for event, entries in json.loads((PLUGIN / 'hooks' / 'hooks.json').read_text())['hooks'].items():
        assert entries[0]['hooks'][0]['commandWindows'] == f'"${{CLAUDE_PLUGIN_ROOT}}\\bin\\wuwei.cmd" hook {event}'


def test_the_doctor_names_the_interpreter_the_hooks_use(tmp_path, monkeypatch):
    monkeypatch.setattr(setup.guards, 'origin', lambda cwd: None)
    monkeypatch.setattr(setup.gh, 'run', lambda args, timeout=30: '')
    setup.init(tmp_path)
    rows = lambda: {name: detail for name, _, detail in setup.doctor(tmp_path)}  # noqa: E731
    assert sys.executable in rows()['python']
    hook.pre_tool(tmp_path, {'tool_name': 'Read', 'tool_input': {}})
    assert rows()['hooks'].endswith(f'under {sys.executable} {sys.version.split()[0]}')
