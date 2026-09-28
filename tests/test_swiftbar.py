"""SwiftBar renders the status command's measured JSON, or unknown."""

import os
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / 'templates/swiftbar/wuwei.1m.sh'
FIXTURES = Path(__file__).resolve().parent / 'fixtures/swiftbar'


def render(tmp_path, fixture, code=0, path=None, delay=None):
    workspace = tmp_path / 'workspace'
    pointer = workspace / '.wuwei/executable'
    pointer.parent.mkdir(parents=True)
    binary = tmp_path / 'bin/wuwei'
    binary.parent.mkdir()
    binary.write_text('#!/bin/sh\n[ "$1" = status ] && [ "$2" = --json ] || exit 2\n'
                      '[ -n "$WUWEI_STATUS_DELAY" ] && sleep "$WUWEI_STATUS_DELAY"\n'
                      'cat "$WUWEI_STATUS_FILE"\nexit "$WUWEI_STATUS_EXIT"\n')
    binary.chmod(0o755)
    pointer.write_text(str(binary) + '\n')
    return subprocess.run(['/bin/sh', str(PLUGIN)], cwd=tmp_path, text=True,
                          capture_output=True, env={**os.environ,
                          'WUWEI_WORKSPACE': str(workspace),
                          'WUWEI_STATUS_FILE': str(FIXTURES / fixture),
                          'WUWEI_STATUS_EXIT': str(code),
                          'WUWEI_STATUS_DELAY': str(delay) if delay is not None else '',
                          **({'PATH': str(path)} if path is not None else {})})


@pytest.mark.parametrize(('fixture', 'color', 'pages', 'nudges'), [
    ('page.json', 'red', 1, 2),
    ('nudge.json', 'orange', 0, 1),
    ('clean.json', 'green', 0, 0),
])
def test_measured_status_renders_counts(tmp_path, fixture, color, pages, nudges):
    result = render(tmp_path, fixture)
    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    assert lines[0].startswith('● | color=' + color)
    assert lines[1] == '---'
    assert f'Pages: {pages}' in lines
    assert f'Nudges: {nudges}' in lines


def test_unmeasured_never_green(tmp_path):
    result = render(tmp_path, 'unmeasured.json', 2)
    assert result.returncode == 2
    assert result.stdout.startswith('● | color=gray\n---\n')
    assert 'Unknown' in result.stdout
    assert 'green' not in result.stdout
    assert result.stderr.strip()


@pytest.mark.parametrize(('fixture', 'code'), [
    ('invalid.json', 0),
    ('missing.json', 0),
    ('clean.json', 2),
])
def test_invalid_or_failed_status_is_unknown(tmp_path, fixture, code):
    result = render(tmp_path, fixture, code)
    assert result.returncode == 2
    assert result.stdout.startswith('● | color=gray\n---\nUnknown\n')
    assert 'green' not in result.stdout
    assert result.stderr.strip()


def test_missing_workspace_is_unknown(tmp_path):
    result = subprocess.run(['sh', str(PLUGIN)], cwd=tmp_path, text=True,
                            capture_output=True,
                            env={key: value for key, value in os.environ.items()
                                 if key != 'WUWEI_WORKSPACE'})
    assert result.returncode == 2
    assert result.stdout.startswith('● | color=gray\n---\nUnknown\n')
    assert 'WUWEI_WORKSPACE' in result.stderr


def test_missing_python_is_unknown(tmp_path):
    tools = tmp_path / 'tools'
    tools.mkdir()
    (tools / 'cat').symlink_to('/bin/cat')
    result = render(tmp_path, 'clean.json', path=tools)
    assert result.returncode == 2
    assert result.stdout.startswith('● | color=gray\n---\nUnknown\n')
    assert 'python3' in result.stderr


def test_status_timeout_is_unknown(tmp_path):
    result = render(tmp_path, 'clean.json', delay=3)
    assert result.returncode == 2
    assert result.stdout.startswith('● | color=gray\n---\nUnknown\n')
    assert 'timed out' in result.stderr


def test_init_menu_bar_prints_mac_instructions_without_writes(tmp_path, monkeypatch, capsys):
    from wuwei.__main__ import main
    from wuwei.commands import init

    monkeypatch.setattr(init.sys, 'platform', 'darwin')
    assert main(['init', '--menu-bar', str(tmp_path)]) == 0
    output = capsys.readouterr().out
    assert 'templates/swiftbar/wuwei.1m.sh' in output
    assert 'WUWEI_WORKSPACE' in output
    assert 'SwiftBar' in output
    assert not list(tmp_path.iterdir())


def test_init_menu_bar_is_absent_off_mac(tmp_path, monkeypatch, capsys):
    from wuwei.__main__ import main
    from wuwei.commands import init

    monkeypatch.setattr(init.sys, 'platform', 'linux')
    assert main(['init', '--menu-bar', str(tmp_path)]) == 0
    output = capsys.readouterr().out
    assert 'macOS only' in output
    assert not list(tmp_path.iterdir())
