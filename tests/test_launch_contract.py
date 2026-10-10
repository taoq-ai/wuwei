"""Generated Claude instructions pass the existing Agent launch boundary."""

import io
import json
import sys
from pathlib import Path

import pytest

from adapters.runtime import claude
from fakes.host import Fake as Host
from test_brief import day
from wuwei import brief, integrity, registry, state
from wuwei.__main__ import main
from wuwei.commands.agents import ROLES
from wuwei.guards import agent_launch


@pytest.fixture
def workspace(day, monkeypatch):
    root, directory, vcs, code_host = day
    host = Host()
    monkeypatch.setattr(integrity, 'cached', lambda root: registry.Result(0))
    monkeypatch.setattr(registry, 'load', lambda kind, config: {
        'runtime': claude, 'host': host, 'vcs': vcs, 'code_host': code_host}[kind])
    (root / 'tree').mkdir()
    monkeypatch.chdir(root)
    return root, directory


def assert_registered(root, job, capsys, monkeypatch):
    relative = str(Path(job['brief_path']).relative_to(root))
    payload = {'cwd': str(root), 'session_id': 'planner',
               'transcript_path': 'planner.jsonl', 'hook_event_name': 'PreToolUse',
               'tool_name': 'Agent', 'tool_input': {
                   'prompt': job['prompt'], 'subagent_type': job['agent_type'],
                   'description': 'Run the briefed seat'}}
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(payload)))
    assert main(['hook', 'PreToolUse']) == 0, capsys.readouterr()
    seat = state.read_state(root)['seats'][Path(relative).stem]
    assert seat['brief'] == relative
    assert seat['role'] == job['agent_type'].removeprefix('wuwei:')
    assert seat['status'] == 'running'
    assert job['prompt'].splitlines()[0] == 'WUWEI brief: ' + relative
    assert agent_launch.check(payload)[0] == 1  # A consumed brief cannot launch twice.


@pytest.mark.parametrize('role', ROLES)
@pytest.mark.parametrize('continue_seat', [False, True])
def test_runtime_prompt_passes_guard(workspace, monkeypatch, capsys, role, continue_seat):
    root, directory = workspace
    relative = brief.write(role, 'X', 'seat', 'Do the assigned work',
                           worktree='tree', root=root)
    assert main(['runtime', 'dispatch', role, relative, 'tree', '--write']) == 0
    job = json.loads(capsys.readouterr().out)
    if continue_seat:
        for feedback in ('Fix the failing check', 'Check the delta'):
            assert main(['runtime', 'continue', json.dumps(job), feedback]) == 0
            job = json.loads(capsys.readouterr().out)
            assert job['feedback'] == feedback
            assert feedback in job['prompt']
    assert job['agent_type'] == 'wuwei:' + role
    assert job['write'] is True
    assert job['worktree'] == str(root / 'tree')
    assert_registered(root, job, capsys, monkeypatch)


@pytest.mark.parametrize('gate', ['arch', 'quality', 'security'])
def test_runtime_dispatch_accepts_gate_names(workspace, monkeypatch, capsys, gate):
    root, _ = workspace
    relative = brief.write('sentinel-' + gate, 'X', 'seat', 'Review the change',
                           worktree='tree', root=root)
    assert main(['runtime', 'dispatch', gate, relative, 'tree']) == 0
    job = json.loads(capsys.readouterr().out)
    assert job['agent_type'] == 'wuwei:sentinel-' + gate
    assert_registered(root, job, capsys, monkeypatch)


def test_steward_close_prompt_passes_guard(workspace, monkeypatch, capsys):
    root, _ = workspace
    assert main(['steward', 'run', '--trigger', 'close']) == 0
    job = json.loads(capsys.readouterr().out)['steward_launch']
    assert job['agent_type'] == 'wuwei:steward'
    assert_registered(root, job, capsys, monkeypatch)


def test_missing_brief_line_names_the_brief_command(workspace):
    # #660: below strict a launch with no brief line registers as an adhoc seat and names the fix.
    root, _ = workspace
    code, message = agent_launch.check({'cwd': str(root), 'tool_input': {
        'subagent_type': 'wuwei:builder', 'description': 'Build', 'prompt': 'Do work'}})
    assert code == 1
    assert 'bin/wuwei brief builder <item> <name>' in message
    assert [seat['role'] for seat in state.read_state(root)['seats'].values()] == ['adhoc']


def test_brief_line_on_a_later_line_is_read(workspace):
    root, _ = workspace
    code, message = agent_launch.check({'cwd': str(root), 'tool_input': {
        'subagent_type': 'wuwei:builder', 'description': 'Build',
        'prompt': 'Instructions:\nWUWEI brief: brief.md'}})
    assert code == 2 and 'invalid brief path' in message
    assert state.read_state(root)['seats'] == {}


@pytest.mark.parametrize('case', ['missing-brief', 'missing-type', 'bad-type', 'missing-file'])
def test_invalid_continuation_fails_closed(workspace, case):
    root, _ = workspace
    relative = brief.write('builder', 'X', 'seat', 'Do work', root=root)
    job = claude.dispatch('builder', root / relative, root / 'tree', True, root=root).data
    if case == 'missing-brief':
        del job['brief_path']
    elif case == 'missing-type':
        del job['agent_type']
    elif case == 'bad-type':
        job['agent_type'] = None
    else:
        (root / relative).unlink()
    result = claude.continue_job(job, 'Fix the check', root=root)
    assert result.exit == 2
    assert result.reason
