"""Proposal promotion contracts."""

import json
import os
from pathlib import Path
import subprocess
import sys

from wuwei import memory

ROOT = Path(__file__).resolve().parents[1]
DAY = '2026-09-28'


def setup(root):
    base = root / '.wuwei'
    (base / 'memory/notes').mkdir(parents=True)
    (base / 'charters').mkdir()
    (base / '.git').mkdir()
    (base / 'days' / DAY / 'proposals').mkdir(parents=True)
    (base / 'config.toml').write_text('')
    (base / 'memory/spine.md').write_text('Spine\n')
    (base / 'memory/index.md').write_text('')
    return base


def cli(root, *args):
    # Promotion policy tests use a PATH stub; real git history has one integrity smoke test.
    tools = root / 'tools'
    tools.mkdir(exist_ok=True)
    git = tools / 'git'
    git.write_text("#!/bin/sh\ncase \" $* \" in *' log '*) printf '\\036wuwei\\000';; esac\nexit 0\n")
    git.chmod(0o755)
    return subprocess.run([sys.executable, '-P', '-m', 'wuwei', *args],
                          env={**os.environ, 'PATH': str(tools) + os.pathsep + os.environ['PATH'],
                               'PYTHONPATH': str(ROOT / 'cli'),
                               'WUWEI_WORKSPACE': str(root),
                               'WUWEI_NOW': DAY + 'T12:00:00+02:00'},
                          capture_output=True, text=True)


def proposal(base, name='one', **changes):
    data = {'target': '.wuwei/charters/builder.md', 'action': 'add',
            'text': 'Check tests before review.\n', 'reason': 'Observed failure',
            'evidence': '.wuwei/days/' + DAY + '/report.md'}
    data.update(changes)
    (base / 'days' / DAY / 'report.md').write_text('Evidence\n')
    (base / 'days' / DAY / 'proposals' / (name + '.json')).write_text(json.dumps(data))


def ledger(base):
    return [json.loads(line) for line in (base / 'memory/ledger.jsonl').read_text().splitlines()]


def test_plugin_charter_rejected_with_reason(tmp_path):
    base = setup(tmp_path)
    proposal(base, target='charters/builder.md')
    result = cli(tmp_path, 'promote')
    assert result.returncode == 1, result.stderr
    assert ledger(base)[0]['status'] == 'rejected'
    assert 'target' in ledger(base)[0]['reason']
    assert not (base / 'charters/builder.md').exists()


def test_note_and_voice_targets_are_rejected(tmp_path):
    """#833: promote lands charter overrides only."""
    base = setup(tmp_path)
    (base / 'memory/notes/old.md').write_text('Old fact\n')
    (base / 'memory/voice.md').write_text('## internal\n')
    proposal(base, target='.wuwei/memory/notes/old.md', action='patch', old_text='Old fact', text='New fact')
    proposal(base, 'two', target='.wuwei/memory/voice.md', action='add', text='- never: hype\n')
    assert cli(tmp_path, 'promote').returncode == 1
    for record in ledger(base):
        assert record['status'] == 'rejected'
        assert record['reason'] == ('target must be a WUWEI charter override; use a path under '
                                    '.wuwei/charters')
    assert (base / 'memory/notes/old.md').read_text() == 'Old fact\n'


def test_duplicate_add_rejected_in_favour_of_patch(tmp_path):
    base = setup(tmp_path)
    (base / 'charters/builder.md').write_text('Check tests before review.\n')
    proposal(base)
    assert cli(tmp_path, 'promote').returncode == 1
    assert 'patch' in ledger(base)[0]['reason']


def test_promote_does_not_replay_processed_proposal(tmp_path):
    base = setup(tmp_path)
    proposal(base)
    assert cli(tmp_path, 'promote').returncode == 0
    first = ledger(base)
    assert first[0]['status'] == 'landed'
    second = cli(tmp_path, 'promote')
    assert second.returncode == 0, second.stderr
    assert second.stdout == ''
    assert ledger(base) == first
    assert (base / 'days' / DAY / 'proposals/one.landed').exists()


def test_add_and_patch_land(tmp_path):
    base = setup(tmp_path)
    proposal(base)
    assert cli(tmp_path, 'promote').returncode == 0
    assert (base / 'charters/builder.md').read_text().endswith('Check tests before review.\n')
    assert ledger(base)[0]['status'] == 'landed'
    proposal(base, 'two', action='patch', old_text='Check tests before review.',
             text='Check tests and lint before review.')
    assert cli(tmp_path, 'promote').returncode == 0
    assert (base / 'charters/builder.md').read_text().endswith('Check tests and lint before review.\n')


def test_dirty_changelog_rejects_before_charter_write(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from wuwei import promotion, registry

    base = setup(tmp_path)
    proposal(base)
    monkeypatch.setenv('WUWEI_NOW', DAY + 'T12:00:00+02:00')
    commits = []
    monkeypatch.setattr(registry, 'load', lambda *a: SimpleNamespace(
        workspace_changes=lambda *a, **kw: registry.Result(0, ['memory/CHANGELOG.md']),
        workspace_commit=lambda *a, **kw: commits.append(a) or registry.Result(0)))

    assert promotion.promote(tmp_path)[0]['status'] == 'rejected'
    assert not (base / 'charters/builder.md').exists()
    assert (base / 'days' / DAY / 'proposals/one.rejected').exists()
    assert not commits


def test_promote_uses_configured_changelog(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from wuwei import promotion, registry

    base = setup(tmp_path)
    (base / 'config.toml').write_text('[retro]\nchangelog = ".wuwei/memory/retro-history.md"\n')
    proposal(base)
    monkeypatch.setenv('WUWEI_NOW', DAY + 'T12:00:00+02:00')
    commits = []
    monkeypatch.setattr(registry, 'load', lambda *a: SimpleNamespace(
        workspace_changes=lambda *a, **kw: registry.Result(0, []),
        workspace_commit=lambda repo, paths, **kw: commits.append(paths) or registry.Result(0)))

    assert promotion.promote(tmp_path)[0]['status'] == 'landed'
    assert '- ' + DAY in (base / 'memory/retro-history.md').read_text()
    assert not (base / 'memory/CHANGELOG.md').exists()
    assert commits == [['charters/builder.md', 'memory/retro-history.md', 'memory/ledger.jsonl']]


def test_missing_evidence_rejected(tmp_path):
    base = setup(tmp_path)
    proposal(base, evidence='.wuwei/days/' + DAY + '/missing.md')
    assert cli(tmp_path, 'promote').returncode == 1
    assert 'evidence' in ledger(base)[0]['reason']


def test_payload_groups_last_run(tmp_path):
    base = setup(tmp_path)
    assert 'Last promote: none' in cli(tmp_path, 'payload').stdout
    proposal(base)
    proposal(base, 'two', target='charters/plugin.md')
    assert cli(tmp_path, 'promote').returncode == 1
    payload = cli(tmp_path, 'payload')
    assert payload.returncode == 0
    assert 'Last promote 2026-09-28: landed 1 (.wuwei/charters/builder.md); rejected 1 (charters/plugin.md:' in payload.stdout


def test_symlinked_ledger_fails_closed(tmp_path):
    base = setup(tmp_path)
    outside = tmp_path / 'outside.jsonl'
    outside.write_text('')
    (base / 'memory/ledger.jsonl').symlink_to(outside)
    proposal(base)
    result = cli(tmp_path, 'promote')
    assert result.returncode == 2
    assert outside.read_text() == ''


def test_patch_must_rewrite_existing_rule(tmp_path):
    base = setup(tmp_path)
    (base / 'charters/builder.md').write_text('Old rule.\n')
    proposal(base, action='patch', old_text='Other rule.', text='New rule.')
    assert cli(tmp_path, 'promote').returncode == 1
    assert (base / 'charters/builder.md').read_text() == 'Old rule.\n'


def test_memory_writes_are_reserved_for_dedicated_cli(tmp_path, monkeypatch):
    base = setup(tmp_path)
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    from wuwei.guards.protect_state import check_file
    for path in ('.wuwei/memory/ledger.jsonl', '.wuwei/memory/notes/old.md',
                 '.wuwei/charters/builder.md', '.wuwei/days/2026-09-28/traces.jsonl'):
        payload = {'cwd': str(tmp_path), 'tool_input': {'file_path': path}}
        code, _ = check_file(payload)
        assert code == 1, path


def test_malformed_proposal_is_rejected_and_logged(tmp_path):
    base = setup(tmp_path)
    (base / 'days' / DAY / 'proposals/one.json').write_text('[]')
    assert cli(tmp_path, 'promote').returncode == 1
    assert ledger(base)[0]['status'] == 'rejected'


def fake_vcs(monkeypatch, commits=None):
    from wuwei import registry

    class VCS:
        def workspace_changes(self, *a, **kw):
            return registry.Result(0, [])

        def workspace_commit(self, repo, paths, root=None):
            (commits if commits is not None else []).append(paths)
            return registry.Result(0, None)
    monkeypatch.setattr(registry, 'load', lambda *args: VCS())


def drop(base, old_text, target='.wuwei/charters/builder.md'):
    (base / 'days' / DAY / 'report.md').write_text('Evidence\n')
    return {'target': target, 'action': 'patch', 'text': '', 'old_text': old_text,
            'reason': 'superseded', 'evidence': '.wuwei/days/' + DAY + '/report.md'}


def test_charter_patch_with_empty_text_drops_one_rule(tmp_path, monkeypatch):
    import pytest
    from wuwei import promotion
    base = setup(tmp_path)
    monkeypatch.setenv('WUWEI_NOW', DAY + 'T12:00:00+02:00')
    fake_vcs(monkeypatch)
    charter = base / 'charters/builder.md'
    charter.write_text('# Builder\n- Keep A.\n- Drop B.\n- Keep C.\n')
    changed = promotion._apply(tmp_path, drop(base, '- Drop B.\n'))
    assert charter.read_text() == '# Builder\n- Keep A.\n- Keep C.\n'
    dropped = base / 'memory/archive/dropped-rules.md'
    assert dropped.read_text() == f'- {DAY} builder.md: Drop B.\n'
    assert changed == [charter, dropped]
    charter.write_text('- Twice.\n- Twice.\n- Keep A.\n')
    for old_text in ('- Twice.\n', 'Keep A.\n', '- Keep', '- Keep A.\n- Twice.\n'):
        with pytest.raises(ValueError):
            promotion._apply(tmp_path, drop(base, old_text))
    note = base / 'memory/notes/one.md'
    note.write_text('---\ntype: reference\nsummary: One\naliases: []\nstatus: active\n---\n- Body.\n')
    with pytest.raises(ValueError, match='charter override'):
        promotion._apply(tmp_path, drop(base, '- Body.\n', target='.wuwei/memory/notes/one.md'))


def test_land_records_what_promote_records(tmp_path, monkeypatch):
    from wuwei import promotion
    base = setup(tmp_path)
    monkeypatch.setenv('WUWEI_NOW', DAY + 'T12:00:00+02:00')
    commits = []
    fake_vcs(monkeypatch, commits)
    proposal(base)
    [promoted] = promotion.promote(tmp_path)
    (base / 'charters/builder.md').unlink()
    data = {'target': '.wuwei/charters/builder.md', 'action': 'add', 'text': 'Check tests before review.\n',
            'reason': 'Observed failure', 'evidence': '.wuwei/days/' + DAY + '/report.md'}
    record = promotion.land(tmp_path, data, day=DAY, run=promoted['run_id'],
                            ledger=base / 'memory/ledger.jsonl', name='F-1')
    assert record == promoted and ledger(base) == [promoted, promoted]
    assert len(commits) == 2 and commits[0] == commits[1]


def test_promote_command_exports_after_a_landing(tmp_path, monkeypatch, capsys):
    import pytest
    from wuwei.commands import promote as promote_command
    base = setup(tmp_path)
    monkeypatch.setenv('WUWEI_NOW', DAY + 'T12:00:00+02:00')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    fake_vcs(monkeypatch)
    calls = []
    monkeypatch.setattr(memory, 'export', lambda root=None: calls.append(root) or (None, True))
    proposal(base, target='charters/builder.md')
    assert promote_command.run(None) == 1 and calls == []
    proposal(base, name='two')
    assert promote_command.run(None) == 0 and len(calls) == 1

    def broken(root=None):
        raise ValueError('memory.export_to must not use a symlink')
    monkeypatch.setattr(memory, 'export', broken)
    proposal(base, name='three', text='Run the linter.\n')
    assert promote_command.run(None) == 2
    assert 'wuwei promote export: memory.export_to must not use a symlink' in capsys.readouterr().err
