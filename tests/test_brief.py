"""Brief evidence, ruling resolution and protected-path refusals."""

import io
import json
import sys

import pytest

from fakes.code_host import Fake as CodeHost
from fakes.vcs import Fake as VCS
from wuwei import brief as brief_module, registry, state, workspace
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
    state._write_state(lambda data: data.update(items={'X': {'phase': 'gate'}}, seats={}), tmp_path)
    (directory / 'decisions').mkdir()
    (directory / 'decisions/rulings.md').write_text('D-ABC-1 ruled: (a)\n')
    vcs, host = VCS(), CodeHost()
    vcs.results.update(status=registry.Result(0, []), branches=registry.Result(0, ['x-old']))
    monkeypatch.setattr(registry, 'load', lambda kind, config: {'vcs': vcs, 'code_host': host}[kind])
    return tmp_path, directory, vcs, host


def brief(monkeypatch, body='body', *args):
    monkeypatch.setattr(sys, 'stdin', io.StringIO(body))
    return main(['seat', 'brief', *args, '--file', '-'])


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


def test_item_and_worktree_name_are_not_rulings(day, monkeypatch):
    item = 'CID-MAPPING-VIEW-API'
    state._write_state(lambda data: data['items'].update({item: {'phase': 'planned'}}), day[0])
    body = f'Implement {item}: inspect worktrees/WS-READ-ROUTE-4734.'
    assert brief(monkeypatch, body, 'builder', item, 'mapping') == 0
    assert body in (day[1] / 'briefs/mapping.md').read_text()


def test_brief_records_item_worktree(day, monkeypatch):
    assert brief(monkeypatch, 'body', 'builder', 'X', 'tree-brief', '--worktree', 'tree') == 0
    assert state.read_state(day[0])['items']['X']['worktree'] == str((day[0] / 'tree').resolve())


def test_lead_and_steward_briefs_create_no_item(day, monkeypatch):
    from wuwei import brief as brief_module
    assert brief(monkeypatch, 'body', 'lead', 'DISCOVERY', 'lead-1') == 0
    brief_module.write('steward', 'day', 'steward-1', 'body', root=day[0])
    assert (day[1] / 'briefs/lead-1.md').is_file() and (day[1] / 'briefs/steward-1.md').is_file()
    assert set(state.read_state(day[0])['items']) == {'X'}


def test_lead_brief_carries_the_discovered_candidates(day, monkeypatch):
    # #848: the lead reads the candidates in its brief; an unreachable source stays named.
    from wuwei import discovery
    found = {'sources': {'tracker': [{'id': 'ISSUE-1'}], 'scanner': 'unmeasured: scanner down'},
             'candidates': [{'id': 'ISSUE-1', 'source': 'tracker'}]}
    monkeypatch.setattr(discovery, 'discover', lambda root=None: found)
    assert brief(monkeypatch, 'body', 'lead', 'DISCOVERY', 'lead-2') == 0
    text = (day[1] / 'briefs/lead-2.md').read_text()
    assert 'Source scanner: unmeasured: scanner down' in text
    assert 'Candidate: {"id": "ISSUE-1", "source": "tracker"}' in text

    def broken(root=None):
        raise ValueError('tracker adapter broken')
    monkeypatch.setattr(discovery, 'discover', broken)
    assert brief(monkeypatch, 'body', 'lead', 'DISCOVERY', 'lead-3') == 0
    assert 'Candidates: unmeasured: tracker adapter broken' in (day[1] / 'briefs/lead-3.md').read_text()


def test_lead_brief_discovers_outside_the_brief_lock(day, monkeypatch):
    # S5: a slow scanner audit no longer holds brief.lock, so a parallel brief is not refused.
    import fcntl
    from wuwei import discovery

    def discover(root=None):
        with (day[1] / 'brief.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)  # BlockingIOError while held
            fcntl.flock(lock, fcntl.LOCK_UN)
        return {'sources': {}, 'candidates': []}
    monkeypatch.setattr(discovery, 'discover', discover)
    assert brief(monkeypatch, 'body', 'lead', 'DISCOVERY', 'lead-4') == 0
    assert 'Candidates: unmeasured' not in (day[1] / 'briefs/lead-4.md').read_text()


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
    from fakes import records  # #844: the log holds the records
    records.write(day[0], {'items': data['items']})
    assert brief(monkeypatch, 'body', 'sentinel-arch', 'X', 'gate', '--worktree', 'tree') == 1
    assert not (day[1] / 'briefs/gate.md').exists()


@pytest.mark.parametrize('case,code,hint', [
    ('dirty', 1, 'dirty'), ('live', 1, 'builder'), ('missing-pid', 1, 'builder'),
    ('status-error', 2, 'unavailable'), ('head-error', 2, 'unavailable'),
    ('pr-error', 2, 'unavailable'), ('missing-tree', 2, 'worktree'),
    ('unknown-item', 2, 'item'),  # #844: a missing state.json is no case: it is a cache
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
        from fakes import records  # #844: the log holds the records
        records.write(root, {'items': data['items']})
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
    verdict_line, = [line for line in text.splitlines() if line.startswith('Verdict file:')]
    assert 'the only file you write' in verdict_line and 'tracker create --bug' in verdict_line  # #644
    assert 'your only write' not in verdict_line
    assert [c[0] for c in host.calls] == ['pr', 'pr']
    written = [e for e in events(directory) if e['kind'] == 'brief written']
    assert len(written) == 2
    assert written[0]['payload']['name'] == 'one'
    assert written[0]['payload']['head'] == vcs.results['head'].data['sha']
    assert written[0]['payload']['gate'] is True
    assert len(written[0]['payload']['sha256']) == 64
    assert brief(monkeypatch, 'replacement', 'builder', 'X', 'one') == 1
    assert (directory / 'briefs/one.md').read_text() == text


def test_review_brief_is_a_gate_at_the_existing_pr_head_without_spec(day, monkeypatch, capsys):
    root, directory, vcs, host = day
    head = 'a' * 40
    vcs.results['head'] = registry.Result(0, {'sha': head})
    host.results['pr'] = registry.Result(0, {'head': head, 'state': 'open'})
    state._write_state(lambda data: data['items']['X'].update(
        phase='gate', kind='review', pr='example/repo#7', review_role='arch'), root)
    assert brief(monkeypatch, 'Arch PASS or a named finding', 'arch', 'X', 'arch-X',
                 '--worktree', 'tree', '--pr', 'example/repo#7', '--gate') == 0
    text = (directory / 'briefs/arch-X.md').read_text()
    assert f'HEAD: {head}' in text
    assert 'Spec:' not in text
    host.results['pr'] = registry.Result(0, {'head': 'b' * 40, 'state': 'open'})
    assert brief(monkeypatch, 'Arch PASS or a named finding', 'arch', 'X', 'stale-X',
                 '--worktree', 'tree', '--pr', 'example/repo#7', '--gate') == 1
    assert 'not open at worktree HEAD' in capsys.readouterr().err


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
        state._write_state(lambda data: data.update(gate_policy='D-ABC-3 ruled'), root)
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
        state._write_state(lambda data: data['items']['X'].update(track='FULL'), day[0])
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


def test_item_worktree_uses_repository_default_branch(tmp_path, monkeypatch):
    import subprocess

    def git(*args, cwd=tmp_path):
        return subprocess.run(['git', *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()

    git('init', '-q', '--bare', '-b', 'master', 'origin.git')
    git('init', '-q', '-b', 'master', 'widget')
    widget = tmp_path / 'widget'
    git('-c', 'user.name=Example', '-c', 'user.email=dev@example.test', 'commit', '-q', '--allow-empty',
        '-m', 'start', cwd=widget)
    git('remote', 'add', 'origin', str(tmp_path / 'origin.git'), cwd=widget)
    git('push', '-q', 'origin', 'master', cwd=widget)
    git('fetch', '-q', 'origin', cwd=widget)
    git('worktree', 'add', '-q', '-b', 'x-work', str(tmp_path / 'worktrees/X'), cwd=widget)
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text(
        '[[repos]]\nname = "acme/widget"\npath = "widget"\ndefault_branch = "master"\n')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T12:00:00+00:00')
    workspace.day_dir(tmp_path).mkdir(parents=True)
    state._write_state(lambda data: data.update(items={'X': {'phase': 'implement'}}, seats={}), tmp_path)
    assert brief(monkeypatch, 'body', 'builder', 'X', 'b1', '--worktree', 'worktrees/X') == 0
    sha = git('rev-parse', 'origin/master', cwd=widget)
    assert f'Merge-base: {sha} (origin/master)' in (workspace.day_dir(tmp_path) / 'briefs/b1.md').read_text()


def test_missing_remote_branch_says_fetch(day, monkeypatch, capsys):
    (day[0] / '.wuwei/config.toml').write_text(
        '[[repos]]\nname = "example"\npath = "tree"\ndefault_branch = "master"\n')
    day[2].results['merge_base'] = registry.Result(2, None, 'git.merge_base: could not run: git exited 128')
    assert brief(monkeypatch, 'body', 'builder', 'X', 'nomerge', '--worktree', 'tree') == 2
    err = capsys.readouterr().err
    assert 'no merge base with origin/master in example' in err
    assert 'git.merge_base: could not run: git exited 128' in err
    assert f'git -C {(day[0] / "tree").resolve()} fetch origin, then write the brief again' in err
    assert not (day[1] / 'briefs/nomerge.md').exists()
    assert not any(e['kind'] == 'brief written' for e in events(day[1]))


def test_worktree_of_unconfigured_repository_is_refused(day, monkeypatch, capsys):
    (day[0] / '.wuwei/config.toml').write_text(
        '[[repos]]\nname = "example"\npath = "widget"\ndefault_branch = "master"\n')
    monkeypatch.setattr(day[2], 'repo_context', lambda repo, root=None: registry.Result(
        0, {'path': f'{repo}/.git', 'common_dir': f'{repo}/.git'}))
    assert brief(monkeypatch, 'body', 'builder', 'X', 'stray', '--worktree', 'tree') == 2
    assert 'repository is not configured in this workspace' in capsys.readouterr().err
    assert not (day[1] / 'briefs/stray.md').exists()
    assert not any(call[0] == 'merge_base' for call in day[2].calls)


def set_seats(seats, root):
    state._write_state(lambda data: data.update(seats=seats), root)


@pytest.mark.parametrize('role', ['quality', 'arch', 'security', 'goal', 'sentinel-quality'])
def test_gate_brief_accepts_dispatch_role_names(day, monkeypatch, role):
    assert brief(monkeypatch, 'Review it.', role, 'X', 'g', '--gate', '--worktree', 'tree') == 0
    charter = role if role.startswith('sentinel-') else 'sentinel-' + role
    assert f'charters/{charter}.md' in (day[1] / 'briefs/g.md').read_text()
    written = [e for e in events(day[1]) if e['kind'] == 'brief written']
    assert written[-1]['payload']['role'] == charter


def header(path):
    return path.read_text().split('\n\n', 1)[0].splitlines()


@pytest.mark.parametrize('role', ['quality', 'arch', 'security', 'goal'])
def test_gate_brief_names_probe_env(day, monkeypatch, role):  # #672
    assert brief(monkeypatch, 'Review it.', role, 'X', 'g', '--gate', '--worktree', 'tree') == 0
    lines = [line for line in header(day[1] / 'briefs/g.md') if line.startswith('Probe env:')]
    assert len(lines) == 1
    assert lines[0].startswith('Probe env: PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=')
    assert f'.wuwei/scratch/X/sentinel-{role}/pycache' in lines[0]
    assert 'run every probe, test and mutant in a copy of the worktree under your scratch directory' in lines[0]
    assert brief(monkeypatch, 'Build it.', 'builder', 'X', 'b') == 0
    assert 'Probe env:' not in (day[1] / 'briefs/b.md').read_text()
    from wuwei import brief as writer
    writer.write('steward', 'X', 's', 'body', root=day[0])
    assert 'Probe env:' not in (day[1] / 'briefs/s.md').read_text()


def test_probe_env_leaves_no_pycache(day, monkeypatch, tmp_path):  # #672 acceptance
    import os
    import shlex
    import subprocess
    assert brief(monkeypatch, 'Review it.', 'quality', 'X', 'g', '--gate', '--worktree', 'tree') == 0
    line = next(line for line in header(day[1] / 'briefs/g.md') if line.startswith('Probe env:'))
    env = dict(os.environ)
    env.update(part.split('=', 1) for part in shlex.split(line.removeprefix('Probe env: ').split('; ', 1)[0]))
    tree = tmp_path / 'probe'
    (tree / 'pkg').mkdir(parents=True)
    (tree / 'pkg/__init__.py').write_text('')
    (tree / 'pkg/mod.py').write_text('X = 1\n')
    subprocess.run([sys.executable, '-c', 'import pkg.mod'], cwd=tree, env=env, check=True)
    assert list(tree.rglob('__pycache__')) == []


def test_brief_body_from_option_or_file(day, monkeypatch, tmp_path):
    monkeypatch.setattr(sys, 'stdin', None)
    assert main(['seat', 'brief', 'builder', 'X', 'b1', '--body', 'inline body']) == 0
    assert 'inline body' in (day[1] / 'briefs/b1.md').read_text()
    source = tmp_path / 'body.txt'
    source.write_text('file body')
    assert main(['seat', 'brief', 'builder', 'X', 'b2', '--file', str(source)]) == 0
    assert 'file body' in (day[1] / 'briefs/b2.md').read_text()
    assert brief(monkeypatch, 'stdin body', 'builder', 'X', 'b3') == 0
    assert 'stdin body' in (day[1] / 'briefs/b3.md').read_text()


def test_brief_without_body_option_never_reads_stdin(day, monkeypatch, capsys):
    def blocked():
        raise AssertionError('stdin read')
    monkeypatch.setattr(sys, 'stdin', io.StringIO(''))
    monkeypatch.setattr(sys.stdin, 'read', blocked)
    assert main(['seat', 'brief', 'builder', 'X', 'b4']) == 2
    err = capsys.readouterr().err
    assert '--body' in err and '--file' in err
    assert not (day[1] / 'briefs/b4.md').exists()
    with pytest.raises(SystemExit) as exc:
        main(['seat', 'brief', 'builder', 'X', 'b5', '--body', 'x', '--file', '-'])
    assert exc.value.code == 2


def test_builder_brief_records_the_session_and_claims_nothing(day, monkeypatch):
    # #847: no session registry and no claims; the brief event still names its session.
    root, directory, _, _ = day
    monkeypatch.setenv('WUWEI_SESSION_ID', 'A')
    assert brief(monkeypatch, 'body', 'builder', 'X', 'b1') == 0
    data = state.read_state(root)
    assert 'claims' not in data and 'sessions' not in data
    assert events(directory)[-1]['payload']['session'] == 'A'
    monkeypatch.setenv('WUWEI_SESSION_ID', 'B')
    assert brief(monkeypatch, 'body', 'builder', 'X', 'b2') == 0


def test_unclaimed_builder_brief_without_session_records_no_claim(day, monkeypatch):
    root, _, _, _ = day
    assert brief(monkeypatch, 'body', 'builder', 'X', 'b1') == 0
    assert 'claims' not in state.read_state(root)


def mandate_prompt(day, monkeypatch, config=''):
    from wuwei import brief as briefs
    (day[0] / '.wuwei/config.toml').write_text('cap = 3\n' + config)
    if not (day[1] / 'briefs/mandate.md').exists():
        assert brief(monkeypatch, 'body', 'builder', 'X', 'mandate') == 0
    action = briefs.seat_action('builder', day[1] / 'briefs/mandate.md', day[0], day[0])
    return action['prompt']


def section(prompt, start):
    return next(line for line in prompt.splitlines() if line.startswith(start))


def test_builder_prompt_carries_the_mandate(day, monkeypatch):
    # Part 14: three fixed lines; no decision class, record or route.
    prompt = mandate_prompt(day, monkeypatch)
    assert prompt.splitlines()[0] == 'WUWEI brief: .wuwei/days/2026-09-28/briefs/mandate.md'
    lines = prompt[prompt.index('Mandate (design 5.2):'):].splitlines()[:4]
    assert lines == [
        'Mandate (design 5.2):',
        'Decide alone: what the brief, your charter and the engineering standards already answer.',
        'Record two-way choices under Assumptions: in the spec or PR body (what was assumed, why, '
        'what would overturn it).',
        "Name a one-way, scope, goal or trust-boundary question in your result (a sentinel's "
        "ESCALATE, a builder's Blocked: line); wuwei next asks the owner."]
    for text in ('decision record', 'decision route', 'D-n', 'decision class', '\u2014'):
        assert text not in prompt


def test_the_mandate_is_the_same_either_way(day, monkeypatch):
    default = mandate_prompt(day, monkeypatch)
    for config in ('[guards]\nenforce = true\n', '[guards]\nenforce = false\n'):
        assert mandate_prompt(day, monkeypatch, config) == default


def test_mandate_names_deploy_deny(day, monkeypatch):
    owner = section(mandate_prompt(day, monkeypatch, '[deploy]\ndeny = ["npm publish*"]\n'),
                    'Name a one-way')
    assert 'npm publish*' in owner and 'Trust surface' not in owner


def test_gate_brief_asks_for_assumption_review(day, monkeypatch):
    line = "Assumptions: review the item's Assumptions:"
    assert brief(monkeypatch, 'body', 'sentinel-arch', 'X', 'gate', '--worktree', 'tree') == 0
    assert line in (day[1] / 'briefs/gate.md').read_text()
    assert brief(monkeypatch, 'body', 'builder', 'X', 'plain') == 0
    assert line not in (day[1] / 'briefs/plain.md').read_text()


def test_second_opinion_brief_names_its_model(day, monkeypatch):
    from wuwei import brief as writer

    second = {'role': 'quality', 'runtime': 'codex', 'model': 'm1'}
    writer.write('sentinel-quality', 'X', 'q-1-codex', 'Review it.', worktree='tree',
                 second_opinion=second, root=day[0])
    header = (day[1] / 'briefs/q-1-codex.md').read_text().split('\n\n', 1)[0]
    assert 'Model: m1' in header.splitlines()
    writer.write('sentinel-quality', 'X', 'q-1', 'Review it.', worktree='tree', root=day[0])
    assert 'Model:' not in (day[1] / 'briefs/q-1.md').read_text()
    written = [e['payload'] for e in events(day[1]) if e['kind'] == 'brief written']
    assert written[-2]['second_opinion'] == 'codex:m1' and 'second_opinion' not in written[-1]


def spec_line(path):
    return [line for line in path.read_text().splitlines() if line.startswith('Spec:')]


def test_only_the_builder_brief_carries_the_spec_line(day, monkeypatch):
    import shutil
    from pathlib import Path
    root, directory, vcs, host = day
    assert brief(monkeypatch, 'body', 'builder', 'X', 'b1', '--worktree', 'tree') == 0
    [line] = spec_line(directory / 'briefs/b1.md')
    assert line.startswith('Spec: speckit strict;') and '/speckit.specify' in line
    assert '## Governing document' not in (directory / 'briefs/b1.md').read_text()
    assert 'create-new-feature.sh --json --short-name x' in line and 'specs/x or specs/*-x' in line
    shutil.copytree(Path(__file__).parent / 'fixtures/spec/speckit/specs', root / 'tree/specs')
    (root / 'tree/specs/001-a').rename(root / 'tree/specs/001-x')
    assert brief(monkeypatch, 'body', 'sentinel-arch', 'X', 'g1', '--worktree', 'tree') == 0
    assert spec_line(directory / 'briefs/g1.md') == []  # #667: the gate reads it with why --json
    state._write_state(lambda data: data['items']['X'].update(tier='light'), root)
    assert brief(monkeypatch, 'body', 'builder', 'X', 'b2', '--worktree', 'tree') == 0
    assert spec_line(directory / 'briefs/b2.md') == ['Spec: skipped (lead tier light)']
    (root / '.wuwei/config.toml').write_text('[spec]\nengine = "none"\n')
    assert brief(monkeypatch, 'body', 'builder', 'X', 'b3', '--worktree', 'tree') == 0
    assert spec_line(directory / 'briefs/b3.md') == []


def test_builder_brief_carries_the_governing_document(day, monkeypatch, capsys):
    root, directory, vcs, host = day
    (root / 'tree/docs').mkdir(parents=True, exist_ok=True)
    (root / 'tree/docs/prereg.md').write_text('# Pre\n## Pre-registration\nTen samples.\n\nA t-test.\n## Next\n')
    assert brief(monkeypatch, 'body', 'builder', 'X', 'b0', '--worktree', 'tree') == 0
    plain = (directory / 'briefs/b0.md').read_text()
    state._write_state(lambda data: data['items']['X'].update(governed_by='docs/prereg.md#Pre-registration'),
                       root)
    assert brief(monkeypatch, 'body', 'builder', 'X', 'b1', '--worktree', 'tree') == 0
    text = (directory / 'briefs/b1.md').read_text()
    assert text.endswith('\n\n## Pre-registration\nTen samples.\n\nA t-test.\n')
    assert 'body\n\n## Governing document\n\ndocs/prereg.md#Pre-registration (lines 2-5)' in text
    header = lambda brief_text: [line for line in brief_text.split('\n\n')[0].splitlines()
                                 if not line.startswith('Written:')]
    assert header(text) == header(plain)
    state._write_state(lambda data: data['items']['X'].update(governed_by='docs/missing.md'), root)
    capsys.readouterr()
    assert brief(monkeypatch, 'body', 'builder', 'X', 'b2', '--worktree', 'tree') == 2
    assert 'docs/missing.md is not a file' in capsys.readouterr().err
    assert not (directory / 'briefs/b2.md').exists()


def gate_brief(day, monkeypatch, role, name='d'):
    """The brief header lines for item X tiered standard."""
    state._write_state(lambda data: data['items']['X'].update(gates={'tier': 'standard'}), day[0])
    args = ('--gate', '--worktree', 'tree') if role != 'builder' else ()
    assert brief(monkeypatch, 'Review it.', role, 'X', name, *args) == 0
    return (day[1] / f'briefs/{name}.md').read_text().splitlines()


@pytest.mark.parametrize('role', ['builder', 'quality'])
def test_brief_has_no_docs_line(day, monkeypatch, role):
    # #841: the docs system is gone, even under a former [docs] config.
    with (day[0] / '.wuwei/config.toml').open('a') as stream:
        stream.write('[docs]\nsystem = "notion"\n')
    assert not any(line.startswith('Docs:') for line in gate_brief(day, monkeypatch, role))


@pytest.mark.parametrize('role,count', [('builder', 1), ('quality', 1), ('arch', 1), ('steward', 0)])
def test_builder_and_gate_briefs_name_the_live_read(day, monkeypatch, role, count):
    from wuwei import brief as writer
    if role == 'steward':
        writer.write('steward', 'X', 'l', 'body', root=day[0])
    else:
        gate_brief(day, monkeypatch, role, name='l')
    lines = (day[1] / 'briefs/l.md').read_text().splitlines()
    assert sum(line.startswith('Live: run bin/wuwei why X --json') for line in lines) == count


APPROVED = 'Approved as: owner: "only the annotator change"'


def brief_header(path):
    return path.read_text().split('\n\n', 1)[0].splitlines()


@pytest.mark.parametrize('role,count', [('builder', 1), ('arch', 1), ('quality', 1), ('security', 1),
                                        ('goal', 1), ('steward', 0)])
def test_builder_and_gate_briefs_quote_the_approval(day, monkeypatch, role, count):
    # #731: the owner's recorded approval settles the scope question, so every builder and gate brief quotes it.
    from wuwei import brief as writer
    state._write_state(lambda data: data['items']['X'].update(approved_as='owner: "only the annotator change"'),
                       day[0])
    if role == 'steward':
        writer.write('steward', 'X', 'l', 'body', root=day[0])
    else:
        gate_brief(day, monkeypatch, role, name='l')
    assert brief_header(day[1] / 'briefs/l.md').count(APPROVED) == count
    if count and role != 'builder':
        assert brief(monkeypatch, 'Delta.', role, 'X', 'l2', '--gate', '--worktree', 'tree') == 0
        assert APPROVED in brief_header(day[1] / 'briefs/l2.md')


def test_no_approval_line_without_the_record(day, monkeypatch):
    gate_brief(day, monkeypatch, 'arch', name='l')
    assert not any(line.startswith('Approved as:') for line in (day[1] / 'briefs/l.md').read_text().splitlines())


def test_item_added_with_a_note_has_it_in_every_gate_brief(day, monkeypatch):
    # #731 acceptance: an item approved with a note has the note under Approved as: in every gate brief.
    from wuwei import plan
    root = day[0]
    state._write_state(lambda data: data.update(gate_approved=True, goals=['G-1'], approved_items=[]),
                       root)
    plan.add('Y', root, goal='G-1', note='only the annotator change')
    state.transition('Y', 'implement', root)
    state.transition('Y', 'gate', root)
    state._write_state(lambda data: data['items']['Y'].update(gates={'tier': 'standard'}), root)
    for role in ('arch', 'quality', 'security'):
        assert brief(monkeypatch, 'Review it.', role, 'Y', f'g-{role}', '--gate', '--worktree', 'tree') == 0
        assert APPROVED in brief_header(day[1] / f'briefs/g-{role}.md')


@pytest.mark.parametrize('check,args,line', [
    ('.venv/bin/python -m pytest -q', ('builder', 'X', 'b'), True),
    ('.venv/bin/python -m pytest -q', ('quality', 'X', 'b', '--gate'), False),
    ('python3 -m pytest -q', ('builder', 'X', 'b'), False),
])
def test_builder_brief_names_the_check_interpreter(day, monkeypatch, check, args, line):
    # #520: the builder is told which interpreter its checks run with, so it never builds one.
    root = day[0]
    (root / '.wuwei/config.toml').write_text(
        f'[[repos]]\nname = "app"\npath = "app"\ndefault_branch = "main"\nfast_checks = ["{check}"]\n')
    (root / 'app/.git').mkdir(parents=True)
    python = root / 'app/.venv/bin/python'
    python.parent.mkdir(parents=True)
    python.write_text('')
    (root / 'worktrees/X').mkdir(parents=True)
    day[2].results['repo_context'] = registry.Result(0, {
        'path': str(root / 'worktrees/X'), 'common_dir': str((root / 'app/.git').resolve())})
    state._write_state(lambda data: data['items']['X'].update(approved_as='owner: "only the annotator change"'),
                       root)  # #731: read after the per-repo checks, still the item record
    assert brief(monkeypatch, 'Review it.', *args, '--worktree', 'worktrees/X') == 0
    text = (day[1] / 'briefs/b.md').read_text()
    assert APPROVED in text
    expected = f'Check interpreter: {check} runs with {python.resolve()} (main worktree)'
    assert (expected in text) == line
    assert text.count('Check interpreter:') == int(line)


NONE_LINE = ('Fast checks: none configured; CI and the gates are the evidence. '
             'Write "checks: none configured" in the PR body.')


@pytest.mark.parametrize('checks,none', [('[]', True), ('["make test"]', False)])
def test_builder_brief_names_no_fast_checks(day, monkeypatch, checks, none):
    # #600: an empty fast-check list is a state; the builder writes it in the PR body.
    root = day[0]
    (root / '.wuwei/config.toml').write_text(
        f'[[repos]]\nname = "app"\npath = "app"\ndefault_branch = "main"\nfast_checks = {checks}\n')
    (root / 'app/.git').mkdir(parents=True)
    (root / 'worktrees/X').mkdir(parents=True)
    state._write_state(lambda data: data.update(pace='careful'), root)
    day[2].results['repo_context'] = registry.Result(0, {
        'path': str(root / 'worktrees/X'), 'common_dir': str((root / 'app/.git').resolve())})
    assert brief(monkeypatch, 'Build it.', 'builder', 'X', 'b', '--worktree', 'worktrees/X') == 0
    text = (day[1] / 'briefs/b.md').read_text()
    assert (NONE_LINE in text) == none
    assert 'Checks:' not in text


def test_each_seat_gets_its_own_scratch_directory(day, monkeypatch, capsys):
    """#647: two seats on different items name and get different scratch directories."""
    assert brief(monkeypatch, 'per D-ABC-9', 'builder', 'X', 'refused') == 1
    assert not (day[0] / '.wuwei/scratch/X').exists()
    lines = []
    for item, name in (('X', 'sx'), ('Y', 'sy')):
        assert brief(monkeypatch, 'body', 'builder', item, name) == 0
        found = [line for line in (day[1] / f'briefs/{name}.md').read_text().splitlines()
                 if line.startswith('Scratch: ')]
        assert len(found) == 1
        assert found[0].startswith(f'Scratch: <your scratchpad>/{item}/builder/')
        assert f'.wuwei/scratch/{item}/builder/' in found[0]
        assert 'write every temporary file there' in found[0]
        assert (day[0] / f'.wuwei/scratch/{item}/builder').is_dir()
        lines.append(found[0])
    assert lines[0] != lines[1]


def test_measurement_builder_brief_names_workspace_scratch_only(day, monkeypatch):
    root = day[0]
    state._write_state(lambda data: data['items']['X'].update(kind='measure'), root)
    assert brief(monkeypatch, 'Write outputs under .wuwei/scratch/X/builder.',
                 'builder', 'X', 'measure-X') == 0
    text = (day[1] / 'briefs/measure-X.md').read_text()
    line = next(line for line in text.splitlines() if line.startswith('Scratch: '))
    assert '.wuwei/scratch/X/builder' in line
    assert '<your scratchpad>' not in line


def test_a_new_seat_moves_an_earlier_seats_scratch_aside(day, monkeypatch):
    """#734: a new seat starts in an empty directory; an earlier seat's files are moved, not lost."""
    old = day[0] / '.wuwei/scratch/X/builder'
    old.mkdir(parents=True)
    (old / 'stale.py').write_text('x = 1\n')
    assert brief(monkeypatch, 'body', 'builder', 'X', 'fresh') == 0
    assert old.is_dir() and not any(old.iterdir())
    assert (day[0] / '.wuwei/scratch/X/builder.20260928T120000.000000/stale.py').is_file()
    line = next(line for line in (day[1] / 'briefs/fresh.md').read_text().splitlines()
                if line.startswith('Scratch: '))
    assert 'move it aside with a timestamp suffix when it holds files you did not write' in line
    (day[0] / '.wuwei/scratch/Y/builder').mkdir(parents=True)
    assert brief(monkeypatch, 'body', 'builder', 'Y', 'empty') == 0
    assert [p.name for p in (day[0] / '.wuwei/scratch/Y').iterdir()] == ['builder']


def test_adhoc_prompt_helpers(tmp_path):
    # #676: an untyped subagent is matched to its seat by its launch prompt.
    from wuwei import brief as module
    rows = {'str': [{'type': 'system'}, {'type': 'user', 'message': {'content': 'Review it\nmore'}}],
            'list': [{'type': 'user', 'message': {'content': [
                {'type': 'text', 'text': 'Review it'}, {'type': 'image'}, {'type': 'text', 'text': 'more'}]}}],
            'none': [{'type': 'assistant', 'message': {'content': 'x'}}]}
    for name, lines in rows.items():
        (tmp_path / name).write_text(''.join(json.dumps(row) + '\n' for row in lines))
    assert module.first_prompt(tmp_path / 'str') == 'Review it\nmore'
    assert module.first_prompt(tmp_path / 'list') == 'Review it\nmore'
    assert module.first_prompt(tmp_path / 'none') is None
    digest = module.prompt_digest('Review it\nmore')
    assert digest == module.prompt_digest('  Review it\nmore\n') != module.prompt_digest('other')
    seat = {'role': 'adhoc', 'status': 'running', 'prompt_sha256': digest}
    data = {'seats': {
        'adhoc-1': {**seat, 'item': 'adhoc-1', 'trace_sessions': ['P:a1']},
        'adhoc-2': {**seat, 'item': 'adhoc-2'},
        'adhoc-3': {**seat, 'item': 'adhoc-3'},
        'adhoc-4': {**seat, 'item': 'adhoc-4', 'status': 'stopped'},
        'adhoc-5': {**seat, 'item': 'adhoc-5', 'prompt_sha256': 'other'},
        'b': {'role': 'builder', 'item': 'X', 'status': 'running', 'prompt_sha256': digest},
    }}
    assert module.adhoc_seat(data, digest, 'P:a1') == 'adhoc-1'
    assert module.adhoc_seat(data, digest, 'P:a2') == 'adhoc-2'
    data['seats']['adhoc-2']['trace_sessions'] = ['P:a2']
    assert module.adhoc_seat(data, digest, 'P:a3') == 'adhoc-3'
    data['seats']['adhoc-3']['status'] = 'stopped'
    assert module.adhoc_seat(data, digest, 'P:a3') is None
    assert module.adhoc_seat(data, 'missing', 'P:a9') is None


def test_issue_acceptance_ticket_recorded_after_the_brief(day, monkeypatch, capsys):
    # #667: a ticket recorded after the quality brief is read live by why --json.
    root, directory = day[0], day[1]
    gate_brief(day, monkeypatch, 'quality', name='q')
    assert 'bin/wuwei why X --json' in (directory / 'briefs/q.md').read_text()
    state._write_state(lambda data: data.update(tickets={'X': {'id': 'ENG-7', 'source': 'set'}}), root)
    capsys.readouterr()
    assert main(['why', 'X', '--json']) == 0
    assert json.loads(capsys.readouterr().out)['ticket'] == 'ENG-7'


NOT_FOUND = 'github.pr: could not run: gh exited 1 (acme/widget): gh: Not Found (HTTP 404)'
DENIED = 'github.pr: could not run: gh exited 1 (acme/widget): gh: Bad credentials (HTTP 401)'
WIDGET = '[[repos]]\nname = "acme/widget"\npath = "tree"\ndefault_branch = "main"\n'


def test_not_found_reads_the_404_reason():
    from wuwei import references
    assert references.not_found(NOT_FOUND) and references.not_found(ValueError(NOT_FOUND))
    assert not references.not_found(DENIED) and not references.not_found('')


def test_issue_reference_registers_with_a_warning(day, monkeypatch, capsys):
    # #740: a ticket is an issue; the pulls endpoint 404s on it and the brief still registers.
    (day[0] / '.wuwei/config.toml').write_text(WIDGET)
    day[3].results['pr'] = registry.Result(2, None, NOT_FOUND)
    state._write_state(lambda data: data.update(tickets={'X': {'id': 'acme/widget#24'}}), day[0])
    assert brief(monkeypatch, 'Ticket: acme/widget#24', 'builder', 'X', 'tk') == 0
    text = (day[1] / 'briefs/tk.md').read_text()
    assert "Counterpart acme/widget#24: not in the day's measured PR listing; kept as a reference" in text
    assert 'Ticket: acme/widget#24' in text
    assert any(e['kind'] == 'brief written' for e in events(day[1]))
    capsys.readouterr()
    assert main(['why', 'X', '--json']) == 0
    assert json.loads(capsys.readouterr().out)['ticket'] == 'acme/widget#24'


def test_a_counterpart_reads_the_days_listing_never_the_host(day, monkeypatch):
    # #907: a counterpart reference is optional evidence read from the day's PR listing; the
    # brief makes no code-host call for it, and one the listing lacks stays a reference (#740).
    (day[0] / '.wuwei/config.toml').write_text(WIDGET)
    pull = {'number': 7, 'state': 'open', 'head': 'a' * 40, 'checks': 'green', 'ref': 'acme/widget#7'}
    (day[1] / 'prs.json').write_text(json.dumps({'fetched_at': '2026-09-28T11:59:00+00:00', 'pulls': [pull]}))
    assert brief(monkeypatch, 'see acme/widget#7 and acme/widget#24', 'builder', 'X', 'cp') == 0
    text = (day[1] / 'briefs/cp.md').read_text()
    assert f'Counterpart acme/widget#7 (PR listing 2026-09-28T11:59:00+00:00): {json.dumps(pull)}' in text
    assert "Counterpart acme/widget#24: not in the day's measured PR listing; kept as a reference" in text
    assert [call for call in day[3].calls if call[0] == 'pr'] == []
    (day[1] / 'prs.json').write_text(json.dumps({'fetched_at': None, 'pulls': [pull], 'repos': {
        'acme/widget': {'at': '2026-09-28T11:59:00+00:00', 'failed': 'gh: HTTP 502'}}}))
    assert brief(monkeypatch, 'see acme/widget#7', 'builder', 'X', 'cq') == 0
    assert "Counterpart acme/widget#7: not in the day's measured PR listing" in (day[1] / 'briefs/cq.md').read_text()


def test_every_brief_names_the_doctor_and_the_install_rule(day, monkeypatch):
    """#645: one doctor for every seat; install findings are the owner's. #907: only after a
    failure whose refusal names no fix, never as a start step."""
    root, directory, vcs, host = day
    assert brief(monkeypatch, 'body', 'builder', 'X', 'b1') == 0
    assert brief(monkeypatch, 'per D-ABC-1', 'sentinel-arch', 'X', 's1', '--worktree', 'tree') == 0
    for name in ('b1', 's1'):
        assert brief_module.DOCTOR in (directory / f'briefs/{name}.md').read_text().split('\n\n', 1)[0], name
    for text in ('.wuwei/executable', 'doctor', 'owner', 'Next:'):
        assert text in brief_module.DOCTOR, text
    assert brief_module.DOCTOR.startswith('Doctor: only when a WUWEI command fails and its refusal names no fix')


# Issue #733: a CI-fix item's briefs list every run step of the job it names.

from test_calibrate import CI_FLOW  # noqa: E402

LINT_REF = '.github/workflows/ci.yml#lint'
CI_BLOCK = ('CI steps: this item fixes CI job lint (.github/workflows/ci.yml). Run every step below locally '
            'from the worktree root, not only the one that was red, and cite each as one row in your verdict '
            'or handoff: CI step <n>: PASS|FAIL|NOT RUN <what ran and what it showed>.\n'
            'CI step 1: lint / Ruff (.github/workflows/ci.yml:8)\n'
            '    ruff check .\n'
            'CI step 2: lint / Types (.github/workflows/ci.yml:10)\n'
            '    pip install mypy\n'
            '    mypy cli\n')


def ci_tree(tree):
    (tree / '.github/workflows').mkdir(parents=True)
    (tree / '.github/workflows/ci.yml').write_text(CI_FLOW)
    return tree


@pytest.mark.parametrize('text,expected', [
    ('fix the lint job', [LINT_REF]),
    ('CI job `lint` is red', [LINT_REF]),
    ('the Lint job', [LINT_REF]),
    ('Lint: failure https://example.test/run/1', [LINT_REF]),
    ('Lint (3.11): timed_out https://example.test/run/1', [LINT_REF]),
    ('write the test first', []),
    ('lint: fix the import order', []),
    ('fix the deploy job', []),
])
def test_ci_jobs_finds_the_named_job(tmp_path, text, expected):
    from wuwei import brief as brief_module
    assert brief_module.ci_jobs(text, ci_tree(tmp_path)) == expected


def test_ci_jobs_without_workflows(tmp_path):
    from wuwei import brief as brief_module
    assert brief_module.ci_jobs('fix the lint job', tmp_path) == []


def test_ci_steps_and_block(tmp_path):
    from wuwei import brief as brief_module
    tree = ci_tree(tmp_path)
    steps, missing = brief_module.ci_steps([LINT_REF], tree)
    assert steps == [
        {'n': 1, 'label': 'lint / Ruff', 'source': '.github/workflows/ci.yml:8', 'run': 'ruff check .'},
        {'n': 2, 'label': 'lint / Types', 'source': '.github/workflows/ci.yml:10', 'run': 'pip install mypy\nmypy cli'}]
    assert missing == []
    assert brief_module.ci_steps([LINT_REF, '.github/workflows/ci.yml#gone'], tree)[1] == [
        '.github/workflows/ci.yml#gone']
    assert brief_module.ci_block([], tree) == ''
    assert brief_module.ci_block([LINT_REF], tree) == CI_BLOCK
    assert brief_module.ci_block([LINT_REF, '.github/workflows/ci.yml#gone'], tree) == (
        CI_BLOCK + 'CI job .github/workflows/ci.yml#gone: not in the workflow file at this head\n')
    real = tmp_path / 'real.yml'
    real.write_text(CI_FLOW)
    (tree / '.github/workflows/ci.yml').unlink()
    (tree / '.github/workflows/ci.yml').symlink_to(real)
    with pytest.raises(ValueError, match='.github/workflows/ci.yml'):
        brief_module.ci_steps([LINT_REF], tree)


def test_builder_and_gate_briefs_list_every_step(day, monkeypatch):
    root, directory = day[0], day[1]
    ci_tree(root / 'tree')
    state._write_state(lambda data: data['items']['X'].update(title='fix the lint job'), root)
    assert brief(monkeypatch, 'Build it.', 'builder', 'X', 'b1', '--worktree', 'tree') == 0
    text = (directory / 'briefs/b1.md').read_text()
    assert text.endswith('Build it.\n' + CI_BLOCK)
    assert state.read_state(root)['items']['X']['ci_jobs'] == [LINT_REF]
    state._write_state(lambda data: data['items']['X'].pop('title'), root)
    from wuwei.dispatch import GATE_BODY
    assert brief(monkeypatch, GATE_BODY.format(item='X'), 'quality', 'X', 'g1', '--gate', '--worktree', 'tree') == 0
    assert (directory / 'briefs/g1.md').read_text().endswith(CI_BLOCK)
    copy = (directory / 'briefs/g1.md').read_text().split('\n\n', 1)[1].removesuffix('\n')  # as dispatch.opinion
    assert brief(monkeypatch, copy, 'quality', 'X', 'g2', '--gate', '--worktree', 'tree') == 0
    assert (directory / 'briefs/g2.md').read_text().count('CI step 1:') == 1


def test_a_brief_naming_no_job_is_unchanged(day, monkeypatch):
    root, directory = day[0], day[1]
    ci_tree(root / 'tree')
    assert brief(monkeypatch, 'Build it.', 'builder', 'X', 'b1', '--worktree', 'tree') == 0
    assert (directory / 'briefs/b1.md').read_text().endswith('\n\nBuild it.\n')
    assert 'ci_jobs' not in state.read_state(root)['items']['X']


def test_reference_reads_the_marker_on_any_line(tmp_path):
    # #660: a planner note before or around WUWEI's prompt keeps the marker readable.
    from wuwei import brief as module
    assert module.reference('WUWEI brief: a.md\nRead it') == 'a.md'
    assert module.reference('Note one\n\nWUWEI brief: a.md\nRead it') == 'a.md'
    assert module.reference('No marker here') is None
    assert module.reference('WUWEI brief: a.md\nWUWEI brief: b.md') == 'a.md'
    assert module.reference('Quote: WUWEI brief: a.md') is None
    rows = [{'type': 'user', 'message': {'content': 'Planner note: watch the cache.\n\nWUWEI brief: a.md\nRead it'}}]
    (tmp_path / 't').write_text(''.join(json.dumps(row) + '\n' for row in rows))
    assert module.transcript_reference(tmp_path / 't') == 'a.md'
