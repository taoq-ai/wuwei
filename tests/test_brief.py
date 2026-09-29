"""Brief evidence, ruling resolution and protected-path refusals."""

import io
import json
import sys

import pytest

from fakes.code_host import Fake as CodeHost
from fakes.vcs import Fake as VCS
from wuwei import registry, state, workspace
from wuwei.__main__ import main


@pytest.fixture
def day(tmp_path, monkeypatch):
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T12:00:00+00:00')
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text(
        'cap = 3\n[brief]\n'
        "full_path_patterns = ['(^|/)(infra|infrastructure|terraform|migrations?|secrets?)(/|$)']\n")
    directory = workspace.day_dir(tmp_path)
    directory.mkdir(parents=True)
    state._write_state(lambda data: data.update(items={'X': {'phase': 'gate'}}, seats={}), tmp_path, reserved=False)
    (directory / 'decisions').mkdir()
    (directory / 'decisions/rulings.md').write_text('D-ABC-1 ruled: (a)\n')
    vcs, host = VCS(), CodeHost()
    vcs.results.update(status=registry.Result(0, []), branches=registry.Result(0, ['x-old']))
    monkeypatch.setattr(registry, 'load', lambda kind, config: {'vcs': vcs, 'code_host': host}[kind])
    return tmp_path, directory, vcs, host


def brief(monkeypatch, body='body', *args):
    monkeypatch.setattr(sys, 'stdin', io.StringIO(body))
    return main(['brief', *args])


def events(directory):
    return [json.loads(line) for line in (directory / 'events.jsonl').read_text().splitlines()]


def test_unresolved_ruling(day, monkeypatch, capsys):
    assert brief(monkeypatch, 'per D-ABC-9', 'builder', 'X', 'n1') == 1
    assert 'D-ABC-9' in capsys.readouterr().err
    assert not (day[1] / 'briefs/n1.md').exists()
    assert not any(e['kind'] == 'brief written' for e in events(day[1]))


def test_resolved_ruling(day, monkeypatch):
    assert brief(monkeypatch, 'per D-ABC-1', 'builder', 'X', 'n2') == 0
    assert 'Ruling D-ABC-1 [RULED]' in (day[1] / 'briefs/n2.md').read_text()


def test_declared_full_and_persisted(day, monkeypatch):
    args = ('builder', 'X')
    assert brief(monkeypatch, 'Paths: core/x.py, infrastructure/db.ts', *args, 'n3') == 1
    assert brief(monkeypatch, 'Paths: infrastructure/db.ts', *args, 'n4', '--track', 'FULL') == 0
    assert state.read_state(day[0])['items']['X']['track'] == 'FULL'
    assert brief(monkeypatch, 'Paths: infrastructure/db.ts', *args, 'n5') == 0


def test_untracked_protected_path(day, monkeypatch):
    day[2].results['status'] = registry.Result(0, [{'path': 'terraform/main.tf'}])
    assert brief(monkeypatch, 'body', 'builder', 'X', 'n6', '--worktree', 'tree') == 1


@pytest.mark.parametrize('body,options,code,hint', [
    ('Return inline', ['--gate'], 1, 'inline'),
    ('Return the verdict inline', ['--gate'], 1, 'inline'),
    ('no verdict file', ['--gate'], 1, 'inline'),
    ('retro note inline', ['--gate'], 1, 'inline'),
    ('decisions/gate-other.md', ['--gate'], 1, 'verdict path'),
    ('body', ['--track', 'OTHER'], 1, 'track'),
    ('body', [], 0, ''),
])
def test_source_refusals(day, monkeypatch, capsys, body, options, code, hint):
    assert brief(monkeypatch, body, 'builder', 'X', 'test', '--worktree', 'tree', *options) == code
    assert hint in capsys.readouterr().err


@pytest.mark.parametrize('phase', ['implement', 'spec', 'fix', 'planned', 'parked', 'escalated'])
def test_gate_phase_refused(day, monkeypatch, phase):
    data = state.read_state(day[0])
    data['items']['X']['phase'] = phase
    if phase in ('parked', 'escalated'):
        data['items']['X']['resume_phase'] = 'gate'
    (day[1] / 'state.json').chmod(0o600)
    (day[1] / 'state.json').write_text(json.dumps(data))
    assert brief(monkeypatch, 'body', 'sentinel-arch', 'X', 'gate', '--worktree', 'tree') == 1
    assert not (day[1] / 'briefs/gate.md').exists()


@pytest.mark.parametrize('case,code,hint', [
    ('dirty', 1, 'dirty'), ('live', 1, 'builder'), ('missing-pid', 1, 'builder'),
    ('status-error', 2, 'unavailable'), ('head-error', 2, 'unavailable'),
    ('pr-error', 2, 'unavailable'), ('missing-tree', 2, 'worktree'),
    ('unknown-item', 2, 'item'), ('missing-state', 2, 'state'),
])
def test_gate_fail_closed(day, monkeypatch, capsys, case, code, hint):
    root, directory, vcs, host = day
    opts = ['--worktree', 'tree']
    if case == 'dirty':
        vcs.results['status'] = registry.Result(0, [{'path': 'x'}])
    if case in ('live', 'missing-pid'):
        seat = {'role': 'builder', 'item': 'X', 'status': 'running'}
        if case == 'live':
            seat['pid'] = 123
        set_seats({'builder': seat}, root)
    if case in ('status-error', 'head-error'):
        vcs.results[case.split('-')[0]] = registry.Result(2, None, 'unavailable')
    if case == 'pr-error':
        host.results['pr'] = registry.Result(2, None, 'unavailable')
        opts += ['--pr', 'example/repo#7']
    if case == 'missing-tree':
        opts = []
    if case == 'unknown-item':
        data = state.read_state(root)
        data['items'] = {}
        (directory / 'state.json').chmod(0o600)
        (directory / 'state.json').write_text(json.dumps(data))
    if case == 'missing-state':
        (directory / 'state.json').unlink()
    assert brief(monkeypatch, 'body', 'sentinel-arch', 'X', 'gate', *opts) == code
    assert hint in capsys.readouterr().err
    assert not (directory / 'briefs/gate.md').exists()


def test_stamped_header_and_fresh_pr(day, monkeypatch):
    root, directory, vcs, host = day
    for name in ('one', 'two'):
        assert brief(monkeypatch, 'per D-ABC-1', 'sentinel-arch', 'X', name,
                     '--worktree', 'tree', '--pr', 'example/repo#7') == 0
    text = (directory / 'briefs/one.md').read_text()
    for field in ('charters/sentinel-arch.md', '2026-09-28T12:00:00+00:00',
                  'Seat policy:', 'Status:', 'HEAD:', 'Merge-base:', 'Prior branches:',
                  'PR head (no-cache):', 'Gate row:', 'Verdict file:'):
        assert field in text
    assert [c[0] for c in host.calls] == ['pr', 'pr']
    written = [e for e in events(directory) if e['kind'] == 'brief written']
    assert len(written) == 2
    assert written[0]['payload']['name'] == 'one'
    assert written[0]['payload']['head'] == vcs.results['head'].data['sha']
    assert written[0]['payload']['gate'] is True
    assert len(written[0]['payload']['sha256']) == 64
    assert brief(monkeypatch, 'replacement', 'builder', 'X', 'one') == 1
    assert (directory / 'briefs/one.md').read_text() == text


@pytest.mark.parametrize('name', ['../escape', '/escape', '.', 'a/b'])
def test_unsafe_name(day, monkeypatch, name):
    assert brief(monkeypatch, 'body', 'builder', 'X', name) == 2


@pytest.mark.parametrize('source', ['past', 'spec', 'policy', 'range', 'gate-only'])
def test_ruling_sources(day, monkeypatch, source):
    root, directory, _, _ = day
    opts = []
    if source == 'past':
        path = directory.parent / '2026-09-27/decisions/ruling.md'
    elif source == 'spec':
        path = root / 'tree/specs/feature/spec.md'
        opts = ['--worktree', 'tree']
    elif source == 'gate-only':
        path = directory / 'decisions/gate-old.md'
    else:
        path = directory / 'decisions/other.md'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('D-ABC-2..6 accepted\n' if source == 'range' else 'D-ABC-3 pending\n')
    if source == 'policy':
        path.unlink()
        state._write_state(lambda data: data.update(gate_policy='D-ABC-3 ruled'), root, reserved=False)
    assert brief(monkeypatch, 'per D-ABC-3', 'builder', 'X', 'ruling', *opts) == (1 if source == 'gate-only' else 0)


def test_configured_paths_and_branches(day, monkeypatch):
    (day[0] / '.wuwei/config.toml').write_text(
        '[brief]\nfull_path_patterns = ["sensitive/"]\nprior_branch_pattern = "team/{item}-*"\n')
    assert brief(monkeypatch, 'Paths: sensitive/a', 'builder', 'X', 'blocked') == 1
    assert brief(monkeypatch, 'body', 'builder', 'X', 'ok', '--worktree', 'tree') == 0
    assert any(c[0] == 'branches' and c[1][1] == 'team/x-*' for c in day[2].calls)


def test_phase_changed_during_evidence_read_refuses(day, monkeypatch):
    original = day[2].head
    def head(*args, **kwargs):
        state.transition('X', 'fix', day[0])
        return original(*args, **kwargs)
    monkeypatch.setattr(day[2], 'head', head)
    assert brief(monkeypatch, 'body', 'sentinel-arch', 'X', 'race', '--worktree', 'tree') == 1
    assert not (day[1] / 'briefs/race.md').exists()


def test_repository_protected_path_refuses(day, monkeypatch):
    assert brief(monkeypatch, 'body', 'builder', 'X', 'infra', '--worktree', 'infrastructure') == 1


def test_failed_event_write_removes_brief(day, monkeypatch):
    def fail(*args):
        raise OSError('event disk failure')
    monkeypatch.setattr(state, '_append_event', fail)
    assert brief(monkeypatch, 'body', 'builder', 'X', 'fail') == 2
    assert not (day[1] / 'briefs/fail.md').exists()


def test_refusal_order(day, monkeypatch, capsys):
    day[2].results['status'] = registry.Result(0, [{'path': 'infrastructure/a'}])
    state.transition('X', 'fix', day[0])
    args = ('sentinel-arch', 'X', 'ordered', '--worktree', 'tree')
    assert brief(monkeypatch, 'Return inline\nPaths: infrastructure/a\nD-ABC-9', *args) == 1
    assert 'inline' in capsys.readouterr().err
    assert day[2].calls == []
    assert brief(monkeypatch, 'Paths: infrastructure/a\nD-ABC-9', *args) == 1
    assert 'dirty' in capsys.readouterr().err
    day[2].results['status'] = registry.Result(0, [])
    assert brief(monkeypatch, 'Paths: infrastructure/a\nD-ABC-9', *args) == 1
    assert 'SLICE' in capsys.readouterr().err
    assert brief(monkeypatch, 'D-ABC-9', *args, '--track', 'FULL') == 1
    assert 'phase' in capsys.readouterr().err


def test_changed_paths_require_full(day, monkeypatch):
    day[2].results['diff_stat'] = registry.Result(0, [{'path': 'migrations/001.sql'}])
    assert brief(monkeypatch, 'body', 'builder', 'X', 'changed', '--worktree', 'tree') == 1


def test_renamed_protected_path_requires_full(day, monkeypatch):
    day[2].results['status'] = registry.Result(0, [{'path': 'core/db.ts', 'original_path': 'infrastructure/db.ts'}])
    assert brief(monkeypatch, 'body', 'builder', 'X', 'rename', '--worktree', 'tree') == 1


def test_concurrent_track_change_is_not_overwritten(day, monkeypatch):
    original = day[2].head
    def head(*args, **kwargs):
        state._write_state(lambda data: data['items']['X'].update(track='FULL'), day[0], reserved=False)
        return original(*args, **kwargs)
    monkeypatch.setattr(day[2], 'head', head)
    assert brief(monkeypatch, 'body', 'builder', 'X', 'race-track', '--worktree', 'tree') == 2
    assert state.read_state(day[0])['items']['X']['track'] == 'FULL'
    assert not (day[1] / 'briefs/race-track.md').exists()


def test_gate_becomes_dirty_during_pr_read(day, monkeypatch):
    original = day[3].pr
    def pr(*args, **kwargs):
        day[2].results['status'] = registry.Result(0, [{'path': 'changed'}])
        return original(*args, **kwargs)
    monkeypatch.setattr(day[3], 'pr', pr)
    assert brief(monkeypatch, 'body', 'sentinel-arch', 'X', 'race-dirty', '--worktree', 'tree',
                 '--pr', 'example/repo#7') == 1
    assert not (day[1] / 'briefs/race-dirty.md').exists()


def test_repo_default_branch(day, monkeypatch):
    (day[0] / '.wuwei/config.toml').write_text(
        '[[repos]]\nname = "example"\npath = "tree"\ndefault_branch = "trunk"\n')
    assert brief(monkeypatch, 'body', 'builder', 'X', 'branch', '--worktree', 'tree') == 0
    assert any(call[0] == 'merge_base' and call[1][1] == 'origin/trunk' for call in day[2].calls)


def set_seats(seats, root):
    state._write_state(lambda data: data.update(seats=seats), root, reserved=False)
