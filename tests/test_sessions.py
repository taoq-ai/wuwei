"""Session registry: several sessions in one workspace, with one planner."""

import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from wuwei import sessions, state, workspace
from wuwei.__main__ import main


NOW = '2026-09-30T10:00:00+00:00'
PAYLOADS = Path(__file__).parent / 'payloads'


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', NOW)
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('')
    state._write_state(lambda data: None, tmp_path, reserved=False)
    return tmp_path


def events(root, kind=None):
    rows = [json.loads(line) for line in
            (workspace.day_dir(root) / 'events.jsonl').read_text().splitlines()]
    return [row for row in rows if kind is None or row['kind'] == kind]


def test_record_inserts_then_moves_only_last_seen(root, monkeypatch):
    data = {}
    sessions.record(data, 'A', hook='SessionStart', cwd='/w')
    assert data['sessions']['A'] == {'role': 'adhoc', 'started': NOW, 'last_seen': NOW,
                                     'cwd': '/w', 'last_hook': 'SessionStart'}
    monkeypatch.setenv('WUWEI_NOW', '2026-09-30T10:05:00+00:00')
    sessions.record(data, 'A', hook='Stop', cwd='/other')
    assert data['sessions']['A'] == {'role': 'adhoc', 'started': NOW,
                                     'last_seen': '2026-09-30T10:05:00+00:00',
                                     'cwd': '/w', 'last_hook': 'Stop'}


@pytest.mark.parametrize('data,session_id,role', [
    ({}, 'A', 'bogus'), ({}, '', None), ({}, 3, None), ({'sessions': []}, 'A', None)])
def test_record_refuses_malformed_input(data, session_id, role):
    with pytest.raises(ValueError):
        sessions.record(data, session_id, hook='SessionStart', cwd='/w', role=role)


def test_rows_derive_planner_idle_stale_and_items(root):
    data = {'planner_session_id': 'A', 'claims': {'X': 'B', 'W': 'B', 'Y': 'A'},
            'sessions': {'A': {'role': 'adhoc', 'started': '2026-09-30T09:00:00+00:00',
                               'last_seen': '2026-09-30T09:59:00+00:00', 'cwd': '/w',
                               'last_hook': 'Stop'},
                         'B': {'role': 'remote', 'started': '2026-09-30T08:00:00+00:00',
                               'last_seen': '2026-09-30T08:00:00+00:00', 'cwd': '/w',
                               'last_hook': 'remote start', 'thread': 'slack:D1/1'}}}
    now = workspace.now()
    rows = sessions.rows(data, now, 3600)
    assert [row['session_id'] for row in rows] == ['B', 'A']
    b, a = rows
    assert (a['role'], a['age_seconds'], a['idle_seconds'], a['stale'], a['items']) == (
        'planner', 3600, 60, False, ['Y'])
    assert (b['role'], b['idle_seconds'], b['stale'], b['items'], b['thread']) == (
        'remote', 7200, True, ['W', 'X'], 'slack:D1/1')
    with pytest.raises(ValueError):
        sessions.rows({'claims': []}, now, 3600)


def test_touch_writes_only_when_day_state_exists(root, monkeypatch):
    monkeypatch.setenv('WUWEI_NOW', '2026-10-01T10:00:00+00:00')
    assert sessions.touch(root, 'A', hook='Stop', cwd=str(root)) is None
    assert not workspace.day_dir(root).exists()
    monkeypatch.setenv('WUWEI_NOW', NOW)
    before = len(events(root))
    data = sessions.touch(root, 'A', hook='Stop', cwd=str(root))
    assert data['sessions']['A']['last_hook'] == 'Stop'
    assert [row['kind'] for row in events(root)[before:]] == ['session.seen']


def test_stale_seconds_config_and_default(root):
    assert sessions.stale_seconds(root) == 3600
    (root / '.wuwei/config.toml').write_text('[sessions]\nstale_seconds = 60\n')
    assert sessions.stale_seconds(root) == 60


def hook(monkeypatch, event, session_id, cwd, **fields):
    from wuwei.commands.hook import run
    payload = {**json.loads(next((PAYLOADS / event).glob('*.json')).read_text()),
               'session_id': session_id, 'cwd': str(cwd), **fields}
    payload.pop('stop_hook_active', None)
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(payload)))
    return run(SimpleNamespace(event=event))


def listed(capsys):
    capsys.readouterr()
    assert main(['sessions']) == 0
    return {row['session_id']: row for row in json.loads(capsys.readouterr().out)}


def test_two_sessions_listed_and_planner_role(root, monkeypatch, capsys):
    hook(monkeypatch, 'SessionStart', 'A', root)
    hook(monkeypatch, 'SessionStart', 'B', root, source='resume')
    rows = listed(capsys)
    assert [(rows[key]['role'], rows[key]['last_hook']) for key in 'AB'] == [
        ('adhoc', 'SessionStart:startup'), ('adhoc', 'SessionStart:resume')]
    assert main(['plan', 'session', 'A']) == 0
    assert listed(capsys)['A']['role'] == 'planner'


def test_session_start_adds_one_state_event(root, monkeypatch):
    before = len(events(root))
    hook(monkeypatch, 'SessionStart', 'A', root)
    assert [row['kind'] for row in events(root)[before:]] == ['session.seen']


def test_session_start_exports_quoted_id(root, monkeypatch, tmp_path_factory):
    env_file = tmp_path_factory.mktemp('env') / 'env.sh'
    monkeypatch.setenv('CLAUDE_ENV_FILE', str(env_file))
    hook(monkeypatch, 'SessionStart', 'A', root)
    hook(monkeypatch, 'SessionStart', 'A B', root)
    assert env_file.read_text() == "export WUWEI_SESSION_ID=A\nexport WUWEI_SESSION_ID='A B'\n"


def test_session_start_without_day_state_creates_none(root, monkeypatch, tmp_path_factory):
    env_file = tmp_path_factory.mktemp('env') / 'env.sh'
    monkeypatch.setenv('CLAUDE_ENV_FILE', str(env_file))
    monkeypatch.setenv('WUWEI_NOW', '2026-10-01T10:00:00+00:00')
    hook(monkeypatch, 'SessionStart', 'A', root)
    assert not (workspace.day_dir(root) / 'state.json').exists()
    assert env_file.read_text() == 'export WUWEI_SESSION_ID=A\n'


def test_stop_and_subagent_stop_touch_only_the_registry(root, monkeypatch):
    hook(monkeypatch, 'SessionStart', 'A', root)
    before = state.read_state(root)
    monkeypatch.setenv('WUWEI_NOW', '2026-09-30T10:01:00+00:00')
    assert hook(monkeypatch, 'Stop', 'A', root) == 0
    after = state.read_state(root)
    assert after['sessions']['A']['last_hook'] == 'Stop'
    assert after['sessions']['A']['last_seen'] == '2026-09-30T10:01:00+00:00'
    monkeypatch.setenv('WUWEI_NOW', '2026-09-30T10:02:00+00:00')
    assert hook(monkeypatch, 'SubagentStop', 'A', root, agent_type='Explore') == 0
    final = state.read_state(root)
    assert final['sessions']['A']['last_hook'] == 'SubagentStop:Explore'
    assert final['sessions']['A']['last_seen'] == '2026-09-30T10:02:00+00:00'
    assert {k: v for k, v in final.items() if k != 'sessions'} == {
        k: v for k, v in before.items() if k != 'sessions'}


def test_stop_outside_workspace_writes_nothing(root, monkeypatch, tmp_path_factory):
    outside = tmp_path_factory.mktemp('outside')
    monkeypatch.delenv('WUWEI_WORKSPACE')
    before = (workspace.day_dir(root) / 'state.json').read_text()
    from wuwei.guards import lifecycle
    assert lifecycle.stop({'cwd': str(outside), 'session_id': 'A'}) == (0, '')
    assert lifecycle.subagent_stop({'cwd': str(outside), 'session_id': 'A'}) == (0, '')
    assert (workspace.day_dir(root) / 'state.json').read_text() == before


def test_sessions_command_empty_and_unreadable(root, monkeypatch, capsys):
    monkeypatch.setenv('WUWEI_NOW', '2026-10-01T10:00:00+00:00')
    assert main(['sessions']) == 0
    assert json.loads(capsys.readouterr().out) == []
    directory = workspace.day_dir(root)
    directory.mkdir()
    (directory / 'state.json').write_text('{')
    assert main(['sessions']) == 2
    assert 'wuwei sessions' in capsys.readouterr().err


def test_status_counts_live_sessions(root, monkeypatch, capsys):
    assert main(['status', '--line']) == 0
    assert 'sessions' not in capsys.readouterr().out
    hook(monkeypatch, 'SessionStart', 'A', root)
    monkeypatch.setenv('WUWEI_NOW', '2026-09-30T10:30:00+00:00')
    hook(monkeypatch, 'SessionStart', 'B', root)
    capsys.readouterr()
    assert main(['status', '--line']) == 0
    assert 'sessions 2' in capsys.readouterr().out
    assert main(['status', '--json']) == 0
    assert json.loads(capsys.readouterr().out)['sessions'] == 2
    monkeypatch.setenv('WUWEI_NOW', '2026-09-30T11:00:00+00:00')
    assert main(['status', '--line']) == 0
    assert 'sessions 1' in capsys.readouterr().out
    assert listed(capsys)['A']['stale'] is True


def test_second_planner_refused_without_take_over(root, capsys):
    assert main(['plan', 'session', 'A']) == 0
    before = events(root)
    assert main(['plan', 'session', 'B']) == 2
    err = capsys.readouterr().err
    assert 'A' in err and 'wuwei plan session B --take-over' in err
    assert state.read_state(root)['planner_session_id'] == 'A'
    assert events(root) == before
    assert main(['plan', 'session', 'A']) == 0
    assert 'previous' not in events(root, 'plan.session')[-1]['payload']
    assert main(['plan', 'session', 'B', '--take-over']) == 0
    assert state.read_state(root)['planner_session_id'] == 'B'
    payload = events(root, 'plan.session')[-1]['payload']
    assert (payload['session_id'], payload['previous']) == ('B', 'A')


def test_take_over_without_planner_is_plain_registration(root):
    assert main(['plan', 'session', 'B', '--take-over']) == 0
    assert 'previous' not in events(root, 'plan.session')[-1]['payload']


def test_wake_goes_to_the_new_planner(root, monkeypatch):
    from wuwei import watch
    from wuwei.guards import lifecycle
    assert main(['plan', 'session', 'A']) == 0
    assert main(['plan', 'session', 'B', '--take-over']) == 0
    monkeypatch.setattr(watch, 'wake', lambda root, consume=False: 'wake' if consume else '')
    assert lifecycle.stop({'cwd': str(root), 'session_id': 'A'}) == (0, '')
    assert lifecycle.stop({'cwd': str(root), 'session_id': 'B'}) == (1, 'wake')


def nudges(capsys, source=None):
    capsys.readouterr()
    assert main(['nudges']) == 0
    rows = json.loads(capsys.readouterr().out)
    return [row for row in rows if source is None or row['source'] == source]


def test_stale_planner_nudge_names_take_over(root, monkeypatch, capsys):
    state._write_state(lambda data: data.update(planner_session_id='A'), root, reserved=False)
    assert nudges(capsys, 'session.planner_stale') == []
    assert main(['plan', 'session', 'A']) == 0
    assert nudges(capsys, 'session.planner_stale') == []
    monkeypatch.setenv('WUWEI_NOW', '2026-09-30T11:00:00+00:00')
    row, = nudges(capsys, 'session.planner_stale')
    assert row['tier'] == 'nudge'
    assert 'A' in row['reason'] and 'wuwei plan session <session id> --take-over' in row['reason']
    assert main(['status', '--json']) == 0
    assert json.loads(capsys.readouterr().out)['nudges'] >= 1


def test_remote_row_survives_stop_and_planner_role_is_refused(root, monkeypatch, capsys):
    sessions.touch(root, 'R', hook='remote start', cwd=str(root), role='remote', thread='slack:D1/1')
    assert hook(monkeypatch, 'Stop', 'R', root) == 0
    row = listed(capsys)['R']
    assert (row['role'], row['thread'], row['last_hook']) == ('remote', 'slack:D1/1', 'Stop')
    directory = workspace.day_dir(root)
    before = [(directory / name).read_text() for name in ('state.json', 'events.jsonl')]
    with pytest.raises(ValueError):
        sessions.touch(root, 'R', hook='x', cwd=str(root), role='planner')
    assert [(directory / name).read_text() for name in ('state.json', 'events.jsonl')] == before


def test_registry_events_are_silent(root, monkeypatch, capsys):
    before = nudges(capsys)
    hook(monkeypatch, 'SessionStart', 'A', root)
    hook(monkeypatch, 'Stop', 'A', root)
    monkeypatch.setenv('WUWEI_SESSION_ID', 'A')
    sessions.claim_item(root, 'X')
    assert nudges(capsys) == before


def test_registry_fault_keeps_session_start_code_two(root, monkeypatch):
    from wuwei import memory, watch
    from wuwei.guards import lifecycle
    monkeypatch.setattr(memory, 'session_payload', lambda root: ('ctx', 3, 1))
    monkeypatch.setattr(memory, 'lint', lambda root: [])
    monkeypatch.setattr(watch, 'health', lambda root, name='watch': (0, ''))

    def broken(*args, **kwargs):
        raise ValueError('registry broken')
    monkeypatch.setattr(sessions, 'touch', broken)
    code, text = lifecycle.session_start({'cwd': str(root), 'session_id': 'A'})
    assert code == 2
    assert 'session registry unmeasured: registry broken' in text


def test_rows_carry_stopped(root, monkeypatch, capsys):
    sessions.touch(root, 'R', hook='remote start', cwd=str(root), role='remote', thread='slack:D1/1')
    sessions.touch(root, 'A', hook='SessionStart', cwd=str(root))
    state._write_state(lambda data: data['sessions']['R'].update(stopped=NOW), root, reserved=False)
    rows = listed(capsys)
    assert rows['R']['stopped'] == NOW and 'stopped' not in rows['A']
