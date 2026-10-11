"""#352: tool-sequence findings park item seats only; part 14: they page, with no record."""

import hashlib
import json
from types import SimpleNamespace

import pytest

from wuwei import registry, scanner, sessions, signal, state, workspace
from wuwei.__main__ import main
from wuwei.registry import Result


def digest(session):
    return hashlib.sha256(session.encode()).hexdigest()


def rows(*session_ids):
    return [{'chain': ['Bash', tool], 'risk_level': 'critical', 'session_id': session}
            for session in session_ids for tool in ('Write', 'Edit') for _ in range(2)]


@pytest.fixture
def day(tmp_path, monkeypatch):
    def make(enforce='true', findings=None):
        (tmp_path / '.wuwei').mkdir(exist_ok=True)
        (tmp_path / '.wuwei/config.toml').write_text(
            f'[adapters]\nscanner = "ziran"\n[guards]\nenforce = {enforce}\n')
        monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
        monkeypatch.setenv('WUWEI_NOW', '2026-10-03T12:00:00+00:00')
        state._write_state(lambda data: None, tmp_path, reserved=False)
        (workspace.day_dir(tmp_path) / 'traces.jsonl').write_text('{}\n')
        assert main(['plan', 'session', 'P']) == 0
        port = SimpleNamespace(traces=lambda file, root=None: Result(
            1, {'sessions_analyzed': 2, 'findings': rows('P', 'U') if findings is None else findings}))
        original = registry.load
        monkeypatch.setattr(registry, 'load', lambda kind, config:
                            port if kind == 'scanner' else original(kind, config))
        return tmp_path
    return make


def decisions(root):
    return sorted(path.name for path in (workspace.day_dir(root) / 'decisions').glob('D-*.md'))


def events(root, kind):
    path = workspace.day_dir(root) / 'events.jsonl'
    return [row['payload'] for row in map(json.loads, path.read_text().splitlines())
            if row['kind'] == kind]


def sweep(root):
    return scanner.trace_sweep(root, workspace.load_config(root))


def test_registered_roles():
    data = {'planner_session_id': 'P', 'sessions': {
        'S': {'role': 'shepherd'}, 'A': {'role': 'adhoc'}}}
    assert sessions.registered(data, 'P') == 'planner'
    assert sessions.registered(data, 'P:agent1') == 'planner'
    assert sessions.registered(data, 'S') == 'shepherd'
    assert sessions.registered(data, 'A') is None
    assert sessions.registered(data, 'X') is None
    assert sessions.registered({}, 'P') is None


@pytest.mark.parametrize('enforce', ['true', 'false'])
def test_seeded_day_decisions(day, enforce):
    root = day(enforce)
    for _ in range(2):
        counts = sweep(root)
        assert counts['scanner'] == 'measured'
        assert counts['scanner_owed'] == 0
    noted, = events(root, 'traces.noted')
    assert noted['role'] == 'planner' and noted['session_digest'] == digest('P')
    assert noted['summary'] == 'traces: planner session, chain noted'
    assert all(row['session_id'] != 'P' for row in events(root, 'scanner.finding'))
    assert decisions(root) == []
    unmatched, = events(root, 'traces.unmatched')
    assert unmatched == {'session_digest': digest('U'), 'chain': unmatched['chain']}
    assert not events(root, 'scanner.finding')


def test_planner_subagent_and_registered_roles(day):
    root = day(findings=rows('P:agent1', 'S', 'A'))
    state._write_state(lambda data: (
        sessions.record(data, 'S', hook='shepherd', cwd=str(root), role='shepherd'),
        sessions.record(data, 'A', hook='SessionStart', cwd=str(root))), root, reserved=False)
    sweep(root)
    assert sorted(row['role'] for row in events(root, 'traces.noted')) == ['planner', 'shepherd']
    assert [row['session_digest'] for row in events(root, 'traces.unmatched')] == [digest('A')]
    assert not events(root, 'scanner.finding') and decisions(root) == []


def test_adhoc_seat_keeps_its_launchers_session_rule(day):
    # #676: an adhoc seat is the audit record; tool-sequence decisions stay for item seats.
    root = day(findings=rows('P:a1'))
    state._write_state(lambda data: data['seats'].update({'adhoc-1': {
        'role': 'adhoc', 'item': 'adhoc-1', 'status': 'running', 'trace_sessions': ['P:a1']}}),
        root, reserved=False)
    sweep(root)
    noted, = events(root, 'traces.noted')
    assert noted['role'] == 'planner'
    assert not events(root, 'scanner.finding') and decisions(root) == []


def test_seat_wins_over_registration(day):
    root = day('false', findings=rows('P'))
    state._write_state(lambda data: data.update(
        items={'work': {'phase': 'planned', 'status': 'queued'}},
        seats={'builder': {'item': 'work', 'role': 'builder', 'status': 'stopped',
                           'brief': 'x', 'trace_sessions': ['P']}}), root, reserved=False)
    assert sweep(root)['scanner_owed'] == 4
    item = state.read_state(root)['items']['work']
    assert item['phase'] == 'parked' and item['disposition']['reason'].startswith('scanner chain Bash -> ')
    assert decisions(root) == []
    assert len(events(root, 'scanner.finding')) == 4
    assert not events(root, 'traces.noted')


def test_unreadable_events_are_unmeasured(day):
    root = day(findings=rows('U'))
    path = workspace.day_dir(root) / 'events.jsonl'
    path.chmod(0o644)
    with path.open('a') as stream:
        stream.write('{"partial"')
    counts = sweep(root)
    assert counts['scanner'] == 'unmeasured' and counts['unreadable'] == 1


def test_event_tiers(capsys):
    assert signal.classify({'kind': 'traces.noted', 'payload': {}}, {})[0] == 'silent'
    assert signal.classify({'kind': 'traces.unmatched', 'payload': {}}, {})[0] == 'warn'
    for kind in ('traces.noted', 'traces.unmatched'):
        assert main(['event', kind, '{}']) == 1
        assert 'wuwei sweep' in capsys.readouterr().err
