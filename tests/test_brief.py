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
    return main(['brief', *args, '--file', '-'])


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


def test_brief_records_item_worktree(day, monkeypatch):
    assert brief(monkeypatch, 'body', 'builder', 'X', 'tree-brief', '--worktree', 'tree') == 0
    assert state.read_state(day[0])['items']['X']['worktree'] == str((day[0] / 'tree').resolve())


def test_lead_and_steward_briefs_create_no_item(day, monkeypatch):
    from wuwei import brief as brief_module
    assert brief(monkeypatch, 'body', 'lead', 'DISCOVERY', 'lead-1') == 0
    brief_module.write('steward', 'day', 'steward-1', 'body', root=day[0])
    assert (day[1] / 'briefs/lead-1.md').is_file() and (day[1] / 'briefs/steward-1.md').is_file()
    assert set(state.read_state(day[0])['items']) == {'X'}


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
    state._write_state(lambda data: data.update(items={'X': {'phase': 'implement'}}, seats={}), tmp_path, reserved=False)
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
    state._write_state(lambda data: data.update(seats=seats), root, reserved=False)


@pytest.mark.parametrize('role', ['quality', 'arch', 'security', 'sentinel-quality'])
def test_gate_brief_accepts_dispatch_role_names(day, monkeypatch, role):
    assert brief(monkeypatch, 'Review it.', role, 'X', 'g', '--gate', '--worktree', 'tree') == 0
    charter = role if role.startswith('sentinel-') else 'sentinel-' + role
    assert f'charters/{charter}.md' in (day[1] / 'briefs/g.md').read_text()
    written = [e for e in events(day[1]) if e['kind'] == 'brief written']
    assert written[-1]['payload']['role'] == charter


def test_brief_body_from_option_or_file(day, monkeypatch, tmp_path):
    monkeypatch.setattr(sys, 'stdin', None)
    assert main(['brief', 'builder', 'X', 'b1', '--body', 'inline body']) == 0
    assert 'inline body' in (day[1] / 'briefs/b1.md').read_text()
    source = tmp_path / 'body.txt'
    source.write_text('file body')
    assert main(['brief', 'builder', 'X', 'b2', '--file', str(source)]) == 0
    assert 'file body' in (day[1] / 'briefs/b2.md').read_text()
    assert brief(monkeypatch, 'stdin body', 'builder', 'X', 'b3') == 0
    assert 'stdin body' in (day[1] / 'briefs/b3.md').read_text()


def test_brief_without_body_option_never_reads_stdin(day, monkeypatch, capsys):
    def blocked():
        raise AssertionError('stdin read')
    monkeypatch.setattr(sys, 'stdin', io.StringIO(''))
    monkeypatch.setattr(sys.stdin, 'read', blocked)
    assert main(['brief', 'builder', 'X', 'b4']) == 2
    err = capsys.readouterr().err
    assert '--body' in err and '--file' in err
    assert not (day[1] / 'briefs/b4.md').exists()
    with pytest.raises(SystemExit) as exc:
        main(['brief', 'builder', 'X', 'b5', '--body', 'x', '--file', '-'])
    assert exc.value.code == 2


def test_builder_brief_claims_item_for_the_session(day, monkeypatch, capsys):
    root, directory, _, _ = day
    monkeypatch.setenv('WUWEI_SESSION_ID', 'A')
    assert brief(monkeypatch, 'body', 'builder', 'X', 'b1') == 0
    data = state.read_state(root)
    assert data['claims'] == {'X': 'A'} and 'A' in data['sessions']
    assert events(directory)[-1]['payload']['session'] == 'A'
    monkeypatch.setenv('WUWEI_SESSION_ID', 'B')
    before = events(directory)
    assert brief(monkeypatch, 'body', 'builder', 'X', 'b2') == 2
    assert 'claimed by live session A' in capsys.readouterr().err
    assert not (directory / 'briefs/b2.md').exists() and events(directory) == before
    assert brief(monkeypatch, 'body', 'sentinel-arch', 'X', 'gate', '--worktree', 'tree') == 0
    monkeypatch.delenv('WUWEI_SESSION_ID')
    assert brief(monkeypatch, 'body', 'builder', 'X', 'b3') == 2
    monkeypatch.setenv('WUWEI_SESSION_ID', 'B')
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T13:00:00+00:00')
    assert brief(monkeypatch, 'body', 'builder', 'X', 'b4') == 0
    assert state.read_state(root)['claims'] == {'X': 'B'}


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
    prompt = mandate_prompt(day, monkeypatch)
    assert prompt.splitlines()[0] == 'WUWEI brief: .wuwei/days/2026-09-28/briefs/mandate.md'
    for text in ('Mandate (design 5.2):', 'Decide alone:', 'Decide and record:',
                 'Go to the owner', 'Nothing else is a question.'):
        assert text in prompt
    record, owner = section(prompt, 'Decide and record:'), section(prompt, 'Go to the owner')
    assert 'under Assumptions:' in record and 'retry, park, accept-residual, merge' in record
    assert 'defer, scope-cut, re-plan, dependency-bump, message, other' in owner
    assert '\u2014' not in prompt


def test_mandate_follows_class_levels(day, monkeypatch):
    prompt = mandate_prompt(day, monkeypatch, '[decisions.cruise.levels]\napproach = 1\n')
    assert 'Assumptions:' not in section(prompt, 'Decide and record:')
    assert 'approach, defer' in section(prompt, 'Go to the owner')
    prompt = mandate_prompt(day, monkeypatch, '[decisions.cruise]\nenabled = false\n')
    assert section(prompt, 'Decide and record:') == 'Decide and record: none.'


def test_mandate_names_interview_risk_and_deploy_deny(day, monkeypatch):
    (day[0] / '.wuwei/charters').mkdir()
    (day[0] / '.wuwei/charters/lead.md').write_text(
        '# Lead\n\n## Owner preferences (interview)\n'
        '- risk: Also set trust_surface for changes touching: billing.\n')
    owner = section(mandate_prompt(day, monkeypatch, '[deploy]\ndeny = ["npm publish*"]\n'),
                    'Go to the owner')
    assert 'billing' in owner and 'npm publish*' in owner


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


def test_mcp_unmeasured_in_brief_header(day, monkeypatch):
    from wuwei import mcp
    assert brief(monkeypatch, 'body', 'builder', 'X', 'plain') == 0
    assert 'MCP unmeasured' not in (day[1] / 'briefs/plain.md').read_text()
    (day[0] / '.wuwei/ziran').mkdir()
    mcp._write(day[0], {'exit': 2, 'day': '2026-09-28', 'generation': 'g', 'pending': None, 'reports': [],
                        'reason': 'MCP registry unmeasured', 'severities': [], 'unmeasured': [['remote', '0' * 64]],
                        'decided': [['aws', '1' * 64]]})
    assert brief(monkeypatch, 'body', 'builder', 'X', 'flagged') == 0
    assert 'MCP unmeasured: aws, remote' in (day[1] / 'briefs/flagged.md').read_text()


def spec_line(path):
    return [line for line in path.read_text().splitlines() if line.startswith('Spec:')]


def test_builder_and_gate_briefs_carry_the_spec_line(day, monkeypatch):
    import shutil
    from pathlib import Path
    root, directory, vcs, host = day
    assert brief(monkeypatch, 'body', 'builder', 'X', 'b1', '--worktree', 'tree') == 0
    [line] = spec_line(directory / 'briefs/b1.md')
    assert line.startswith('Spec: speckit strict;') and '/speckit.specify' in line
    assert 'create-new-feature.sh --json --short-name x' in line and 'specs/x or specs/*-x' in line
    shutil.copytree(Path(__file__).parent / 'fixtures/spec/speckit/specs', root / 'tree/specs')
    (root / 'tree/specs/001-a').rename(root / 'tree/specs/001-x')
    assert brief(monkeypatch, 'body', 'sentinel-arch', 'X', 'g1', '--worktree', 'tree') == 0
    assert spec_line(directory / 'briefs/g1.md') == ['Spec: speckit artifacts: specs/001-x']
    state._write_state(lambda data: data['items']['X'].update(tier='light'), root, reserved=False)
    assert brief(monkeypatch, 'body', 'builder', 'X', 'b2', '--worktree', 'tree') == 0
    assert spec_line(directory / 'briefs/b2.md') == ['Spec: skipped (lead tier light)']
    (root / '.wuwei/config.toml').write_text('[spec]\nengine = "none"\n')
    assert brief(monkeypatch, 'body', 'builder', 'X', 'b3', '--worktree', 'tree') == 0
    assert spec_line(directory / 'briefs/b3.md') == []


def docs_brief(day, monkeypatch, role, system='notion', tier='standard', docs=None, name='d'):
    with (day[0] / '.wuwei/config.toml').open('a') as stream:
        stream.write(f'[docs]\nsystem = "{system}"\n')
    def update(data):
        data['items']['X']['gates'] = {'tier': tier}
        if docs:
            data['items']['X']['docs'] = docs
    state._write_state(update, day[0], reserved=False)
    args = ('--gate', '--worktree', 'tree') if role != 'builder' else ()
    assert brief(monkeypatch, 'Review it.', role, 'X', name, *args) == 0
    return [line for line in (day[1] / f'briefs/{name}.md').read_text().splitlines()
            if line.startswith('Docs:')]


def test_quality_brief_names_the_missing_docs_value(day, monkeypatch):
    line, = docs_brief(day, monkeypatch, 'quality')
    assert line.startswith('Docs: required (tier standard); value missing')
    assert 'DOC: FINDING' in line and 'bin/wuwei plan set X docs=' in line


def test_quality_brief_shows_the_recorded_value(day, monkeypatch):
    line, = docs_brief(day, monkeypatch, 'quality', docs={'value': 'none', 'reason': 'internal refactor'})
    assert 'value none (internal refactor)' in line


def test_light_quality_brief_is_not_required(day, monkeypatch):
    assert docs_brief(day, monkeypatch, 'quality', tier='light') == ['Docs: not required (tier light).']


def test_builder_brief_has_the_docs_rule(day, monkeypatch):
    line, = docs_brief(day, monkeypatch, 'builder')
    assert line.startswith('Docs: notion;') and 'bin/wuwei plan set X docs=' in line


@pytest.mark.parametrize('role,system', [('arch', 'notion'), ('quality', 'none'), ('builder', 'none')])
def test_no_docs_line(day, monkeypatch, role, system):
    assert docs_brief(day, monkeypatch, role, system=system) == []
