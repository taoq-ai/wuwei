"""Session identity, the planner registration and the Owner step card answer."""

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
    state._write_state(lambda data: None, tmp_path)
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
    sessions.record(data, 'A', hook='plan session', cwd='/other')
    assert data['sessions']['A'] == {'role': 'adhoc', 'started': NOW,
                                     'last_seen': '2026-09-30T10:05:00+00:00',
                                     'cwd': '/w', 'last_hook': 'plan session'}


@pytest.mark.parametrize('data,session_id,role', [
    ({}, 'A', 'bogus'), ({}, '', None), ({}, 3, None), ({'sessions': []}, 'A', None)])
def test_record_refuses_malformed_input(data, session_id, role):
    with pytest.raises(ValueError):
        sessions.record(data, session_id, hook='SessionStart', cwd='/w', role=role)


def hook(monkeypatch, event, session_id, cwd, **fields):
    from wuwei.commands.hook import run
    payload = {**json.loads(next((PAYLOADS / event).glob('*.json')).read_text()),
               'session_id': session_id, 'cwd': str(cwd), **fields}
    payload.pop('stop_hook_active', None)
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(payload)))
    return run(SimpleNamespace(event=event))


def test_session_start_writes_no_event(root, monkeypatch):
    # #847: no session registry; SessionStart only reads.
    before = len(events(root))
    hook(monkeypatch, 'SessionStart', 'A', root)
    assert events(root)[before:] == []


def test_session_start_exports_quoted_id(root, monkeypatch, tmp_path_factory):
    env_file = tmp_path_factory.mktemp('env') / 'env.sh'
    monkeypatch.setenv('CLAUDE_ENV_FILE', str(env_file))
    hook(monkeypatch, 'SessionStart', 'A', root)
    hook(monkeypatch, 'SessionStart', 'A B', root)
    assert env_file.read_text() == "export WUWEI_SESSION_ID=A\nexport WUWEI_SESSION_ID='A B'\n"


def test_session_start_reads_the_day_state_twice(root, monkeypatch):
    # #587, #847: one read of the day; no registry write.
    today, reads, read = workspace.day_dir(root), [], state.read_state
    def counting(root=None, *, directory=None):
        reads.append(Path(directory) if directory is not None else workspace.day_dir(root))
        return read(root, directory=directory)
    monkeypatch.setattr(state, 'read_state', counting)
    hook(monkeypatch, 'SessionStart', 'A', root)
    assert reads.count(today) == 1


def test_session_start_without_day_state_creates_none(root, monkeypatch, tmp_path_factory):
    env_file = tmp_path_factory.mktemp('env') / 'env.sh'
    monkeypatch.setenv('CLAUDE_ENV_FILE', str(env_file))
    monkeypatch.setenv('WUWEI_NOW', '2026-10-01T10:00:00+00:00')
    hook(monkeypatch, 'SessionStart', 'A', root)
    assert not (workspace.day_dir(root) / 'state.json').exists()
    assert env_file.read_text() == 'export WUWEI_SESSION_ID=A\n'


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


GOALS = ('# Goals\n\n## G-1\noutcome: Ship checkout v2\nmeasure: orders\ntarget: 3\n'
         'date: 2026-10-30\npriority: 1\n')
BRIEF = '.wuwei/days/2026-09-30/briefs/builder-1.md'


def test_owner_answer_reads_yes_no_or_none(root):
    """Part 14: the latest recorded answer on one Owner step card; needs_owner is None only on Yes."""
    from fakes import owner
    command = 'bin/wuwei dispatch next A'
    assert sessions.owner_answer(root, command, 'x', 't1') is None
    owner.answer(root, command, 't1', reply='No')
    assert sessions.owner_answer(root, command, 'x', 't1') == 'No'
    assert sessions.needs_owner(root, command, 'x', 't1') is not None
    owner.answer(root, command, 't1')
    assert sessions.owner_answer(root, command, 'x', 't1') == 'Yes'
    assert sessions.needs_owner(root, command, 'x', 't1') is None
    assert sessions.owner_answer(root, command, 'x', 't2') is None
    owner.answer(root, command, 't1', reply='Something else')
    assert sessions.owner_answer(root, command, 'x', 't1') is None
