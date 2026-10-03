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


def gated(tmp_path, monkeypatch, posture='guarded', topics=('goals',)):
    """A planner session that proposed provisional goals and asked the gate question."""
    from test_decision import gate
    from test_plan import TEMPLATE, lead
    from wuwei import plan, workspace as ws
    from wuwei.guards.decision import record_gate

    base = workspace(tmp_path)
    (base / 'config.toml').write_text(f'[security]\nposture = "{posture}"\n')
    (base / 'memory/goals.md').write_text(TEMPLATE.read_text(encoding='utf-8'))
    (base / 'executable').write_text(str(tmp_path / 'bin/wuwei') + '\n')  # the planner's CLI
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T09:00:00+02:00')
    plan.propose(lead(), tmp_path)
    plan.session('planner-1', tmp_path)
    for topic in topics:
        assert record_gate(gate(tmp_path, header=topic.title())) == (0, '')
    draft = ws.day_dir(tmp_path).relative_to(tmp_path) / 'goals.md'
    return base, draft.as_posix()


def edit(tmp_path, command, **extra):
    return check_bash({'cwd': str(tmp_path), 'session_id': 'planner-1',
                       'tool_input': {'command': command}, **extra})


OLD = 'Owner memory edits are an owner action on the host, outside agent tools.'


@pytest.mark.parametrize('posture', ['observe', 'guarded'])
def test_planner_records_gate_approved_goals(tmp_path, monkeypatch, posture):
    from wuwei import plan
    base, draft = gated(tmp_path, monkeypatch, posture)
    assert edit(tmp_path, f'bin/wuwei goals edit --file {draft}') == (0, '')
    result = cli(tmp_path, 'goals', 'edit', '--file', str(tmp_path / draft))
    assert result.returncode == 0, result.stderr
    assert (base / 'memory/goals.md').read_text() == (tmp_path / draft).read_text()
    plan.approve(['A'], tmp_path, goals_confirmed=True)


def test_strict_prints_host_terminal_command(tmp_path, monkeypatch):
    _, draft = gated(tmp_path, monkeypatch, 'strict')
    code, reason = edit(tmp_path, f'bin/wuwei goals edit --file {draft}')
    assert code == 1 and reason.startswith(OLD)
    assert reason.endswith(f'Run it in a host terminal: bin/wuwei goals edit --file {draft}')


def test_gate_allowance_needs_question_file_and_planner(tmp_path, monkeypatch):
    _, draft = gated(tmp_path, monkeypatch, topics=())
    command = f'bin/wuwei goals edit --file {draft}'
    code, reason = edit(tmp_path, command)
    assert code == 1 and reason.endswith(f'Run it in a host terminal: {command}')
    from test_decision import gate
    from wuwei.guards.decision import record_gate
    record_gate(gate(tmp_path))
    assert edit(tmp_path, 'bin/wuwei goals edit')[0] == 1
    assert edit(tmp_path, f'bin/wuwei voice edit --file {draft}')[0] == 1
    assert edit(tmp_path, command, agent_id='a1') == (1, OLD)
    assert check_bash({'cwd': str(tmp_path), 'session_id': 'other',
                       'tool_input': {'command': command}}) == (1, OLD)
    script = tmp_path / 'record.sh'
    script.write_text(command + '\n')
    script.chmod(0o755)
    assert edit(tmp_path, 'bash record.sh')[0] == 1


def test_queue_question_naming_a_goal_does_not_unlock_edit(tmp_path, monkeypatch):
    from test_decision import gate
    from wuwei.guards.decision import record_gate
    _, draft = gated(tmp_path, monkeypatch, topics=())
    payload = gate(tmp_path, header='Queue')
    question = payload['tool_input']['questions'][0]
    question['question'] = question['question'].replace(
        'confirm goals G-1 and G-2', 'approve the queue serving the goal G-1 in my voice')
    assert record_gate(payload) == (0, '')
    assert edit(tmp_path, f'bin/wuwei goals edit --file {draft}')[0] == 1
    assert edit(tmp_path, 'bin/wuwei voice edit --file voice-draft.md')[0] == 1


def test_voice_edit_after_voice_gate(tmp_path, monkeypatch):
    gated(tmp_path, monkeypatch, topics=('voice',))
    assert edit(tmp_path, 'bin/wuwei voice edit --file voice-draft.md') == (0, '')


DECIDE = 'Decisions require the owner terminal, outside agent tools.'


def asked_decision(tmp_path, monkeypatch, posture='guarded', ask=True):
    """The planner asked the owner about today's D-3 record through the gate (#354)."""
    from test_decision import VALID, save
    from wuwei.guards.decision import record_gate
    gated(tmp_path, monkeypatch, posture, topics=())
    save(tmp_path, VALID.replace('Reversibility: two-way', 'Reversibility: one-way'))
    if ask:
        assert record_gate({'cwd': str(tmp_path), 'session_id': 'planner-1', 'tool_name': 'AskUserQuestion',
                            'tool_input': {'questions': [{'question': 'D-3: Which fix?', 'header': 'D-3'}]}}) == (0, '')


@pytest.mark.parametrize('posture', ['observe', 'guarded'])
def test_planner_records_asked_decision(tmp_path, monkeypatch, posture):
    asked_decision(tmp_path, monkeypatch, posture)
    assert edit(tmp_path, 'bin/wuwei decide D-3 B') == (0, '')
    assert edit(tmp_path, 'bin/wuwei mcp decide D-3 B') == (0, '')
    for command, reason in (('bin/wuwei decide D-3 B --note D-4', DECIDE), ('bin/wuwei decide D-4 B', DECIDE),
                            ('bin/wuwei mcp decide proceed-unmeasured aws',
                             'MCP decisions require the owner terminal, outside agent tools.')):
        assert edit(tmp_path, command) == (1, f'{reason} Run it in a host terminal: {command}')
    assert edit(tmp_path, 'bin/wuwei decide D-3 B', agent_id='a1') == (1, DECIDE)


def test_unasked_or_strict_decision_prints_host_terminal_command(tmp_path, monkeypatch):
    asked_decision(tmp_path, monkeypatch, ask=False)
    assert edit(tmp_path, 'bin/wuwei decide D-3 B') == (
        1, f'{DECIDE} Run it in a host terminal: bin/wuwei decide D-3 B')


def test_strict_asked_decision_prints_host_terminal_command(tmp_path, monkeypatch):
    asked_decision(tmp_path, monkeypatch, 'strict')
    assert edit(tmp_path, 'bin/wuwei decide D-3 B') == (
        1, f'{DECIDE} Run it in a host terminal: bin/wuwei decide D-3 B')
