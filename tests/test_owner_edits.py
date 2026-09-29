"""Owner memory edit history and seat boundary."""

import os
from pathlib import Path
import subprocess
import sys

import pytest

from wuwei import integrity, registry, state
from wuwei.guards.protect_state import check_bash, check_file

ROOT = Path(__file__).resolve().parents[1]
GOALS = '# Goals\n## G-1\noutcome: Ship\nmeasure: shipped\ntarget: 1\ndate: 2026-10-30\npriority: 1\n'


def workspace(tmp_path):
    base = tmp_path / '.wuwei'
    (base / 'memory').mkdir(parents=True)
    (base / 'config.toml').write_text('')
    (base / 'memory/goals.md').write_text(GOALS)
    (base / 'memory/voice.md').write_text('## internal\n- max_length: 80\n')
    vcs = registry.load('vcs', {'adapters': {'vcs': 'git'}})
    assert vcs.workspace_init(base).exit == 0
    return base


def cli(root, *args):
    return subprocess.run([sys.executable, '-P', '-m', 'wuwei', *args],
                          env={**os.environ, 'PYTHONPATH': str(ROOT / 'cli'),
                               'WUWEI_WORKSPACE': str(root)},
                          capture_output=True, text=True)


def history(base):
    return subprocess.run(['git', '-C', str(base), 'log', '-1', '--format=%B'],
                          check=True, capture_output=True, text=True).stdout


def test_goals_edit_commits_owner_history_and_clears_integrity(tmp_path):
    base = workspace(tmp_path)
    source = tmp_path / 'new-goals.md'
    source.write_text(GOALS.replace('target: 1', 'target: 2'))
    result = cli(tmp_path, 'goals', 'edit', '--file', str(source))
    assert result.returncode == 0, result.stderr
    assert (base / 'memory/goals.md').read_text() == source.read_text()
    assert 'Promoted-by: wuwei' in history(base)
    assert 'Edited-by: owner' in history(base)
    assert integrity.workspace_check(tmp_path).exit == 0


def test_goals_edit_commits_existing_hand_edit(tmp_path):
    base = workspace(tmp_path)
    target = base / 'memory/goals.md'
    target.write_text(GOALS.replace('target: 1', 'target: 2'))
    assert integrity.workspace_check(tmp_path).exit == 1
    result = cli(tmp_path, 'goals', 'edit', '--file', str(target))
    assert result.returncode == 0, result.stderr
    assert 'Edited-by: owner' in history(base)
    assert integrity.workspace_check(tmp_path).exit == 0


def test_invalid_goals_leave_history_and_target_unchanged(tmp_path):
    base = workspace(tmp_path)
    source = tmp_path / 'bad.md'
    source.write_text('## G-1\noutcome:\n')
    before = history(base)
    result = cli(tmp_path, 'goals', 'edit', '--file', str(source))
    assert result.returncode == 1 and 'goals' in result.stderr
    assert (base / 'memory/goals.md').read_text() == GOALS
    assert history(base) == before


def test_seat_cannot_edit_goals(tmp_path, monkeypatch):
    workspace(tmp_path)
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    assert check_file({'cwd': str(tmp_path), 'tool_name': 'Write',
                       'tool_input': {'file_path': '.wuwei/memory/goals.md'}})[0] == 1
    state._write_state(lambda data: data['seats'].update({'builder': {
        'role': 'builder', 'item': 'ticket', 'status': 'running',
        'trace_sessions': ['seat-session']}}), tmp_path, reserved=False)
    payload = {'cwd': str(tmp_path), 'session_id': 'seat-session',
               'tool_input': {'command': f'bin/wuwei goals edit --file {tmp_path / "goals.md"}'}}
    denial = (1, 'Owner memory edits are an owner action on the host, outside agent tools.')
    assert check_bash(payload) == denial
    assert check_bash({**payload, 'session_id': 'unregistered-session'}) == denial
    opaque = {'cwd': str(tmp_path), 'session_id': 'seat-session',
              'tool_input': {'command': "python3 -P -c 'from wuwei.promotion import owner_edit; owner_edit(\".\", \"goals\", \"text\")'"}}
    assert check_bash(opaque)[0] == 2
    assert (tmp_path / '.wuwei/memory/goals.md').read_text() == GOALS


def test_editor_flow_uses_selected_editor(tmp_path, monkeypatch):
    base = workspace(tmp_path)
    editor = tmp_path / 'editor'
    editor.write_text('#!/bin/sh\nsed "s/target: 1/target: 2/" "$1" > "$1.next"\nmv "$1.next" "$1"\n')
    editor.chmod(0o755)
    monkeypatch.setenv('EDITOR', str(editor))
    assert cli(tmp_path, 'goals', 'edit').returncode == 0
    assert 'target: 2' in (base / 'memory/goals.md').read_text()
    assert integrity.workspace_check(tmp_path).exit == 0


def test_first_seat_tool_uses_transcript_registration(tmp_path, monkeypatch):
    workspace(tmp_path)
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    brief = '.wuwei/days/2026-09-29/briefs/builder.md'
    state._write_state(lambda data: data['seats'].update({'builder': {
        'role': 'builder', 'item': 'ticket', 'status': 'running', 'brief': brief}}),
        tmp_path, reserved=False)
    transcript = tmp_path / 'transcript.jsonl'
    transcript.write_text('{"type":"user","message":{"content":"WUWEI brief: '
                          + brief + '\\nRead it."}}\n')
    payload = {'cwd': str(tmp_path), 'session_id': 'new-seat-session',
               'transcript_path': str(transcript),
               'tool_input': {'command': f'bin/wuwei goals edit --file {tmp_path / "goals.md"}'}}
    assert check_bash(payload) == (1, 'Owner memory edits are an owner action on the host, outside agent tools.')
    assert check_bash({**payload, 'session_id': 'new-seat-session', 'agent_id': 'A'}) == (
        1, 'Owner memory edits are an owner action on the host, outside agent tools.')


def test_voice_edit_commits_owner_history_and_clears_integrity(tmp_path):
    base = workspace(tmp_path)
    source = tmp_path / 'voice.md'
    source.write_text('## internal\n- max_length: 100\n')
    result = cli(tmp_path, 'voice', 'edit', '--file', str(source))
    assert result.returncode == 0, result.stderr
    assert (base / 'memory/voice.md').read_text() == source.read_text()
    assert 'Promoted-by: wuwei' in history(base)
    assert 'Edited-by: owner' in history(base)
    assert integrity.workspace_check(tmp_path).exit == 0
