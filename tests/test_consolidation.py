"""Weekly consolidation contracts."""

from datetime import date, timedelta
from pathlib import Path

from wuwei import registry
from wuwei.guards.protect_state import check_bash


def workspace(tmp_path):
    base = tmp_path / '.wuwei'
    (base / 'memory/notes').mkdir(parents=True)
    (base / 'charters').mkdir()
    (base / '.git').mkdir()
    (base / 'config.toml').write_text('')
    (base / 'memory/CHANGELOG.md').write_text('')
    return base


def test_missing_changelog_does_not_block_day_archive(tmp_path, monkeypatch):
    from wuwei.commands.consolidate import run
    from wuwei import workspace as workspace_module

    base = workspace(tmp_path)
    (base / 'memory/CHANGELOG.md').unlink()
    (base / 'charters/lead.md').write_text('- Keep evidence.\n')
    day = base / 'days/2026-08-01'
    day.mkdir(parents=True)
    (day / 'report.md').write_text('Old day\n')
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00+02:00')
    monkeypatch.setattr(workspace_module, 'find_workspace', lambda: tmp_path)
    monkeypatch.setattr(registry, 'load', lambda *args: type('VCS', (), {
        'workspace_commit': lambda *a, **kw: registry.Result(0, None)})())

    assert run(None) == 0
    assert (base / 'archive/2026-08-01/report.md').read_text() == 'Old day\n'


def test_review_finds_conflicting_local_charter_rules(tmp_path):
    from wuwei.consolidation import note_findings
    base = workspace(tmp_path)
    (base / 'charters/lead.md').write_text('- Do review the final report.\n')
    (base / 'charters/planner.md').write_text('- Do not review the final report.\n')
    assert any('contradiction' in item for item in note_findings(tmp_path))


def test_review_finds_near_duplicate_local_charter_rules(tmp_path):
    from wuwei.consolidation import note_findings
    base = workspace(tmp_path)
    (base / 'charters/lead.md').write_text('- Record the final result after review.\n')
    (base / 'charters/planner.md').write_text('- Record the final results after review.\n')
    assert any('near-duplicate charter' in item for item in note_findings(tmp_path))


def test_review_finds_near_duplicate_notes(tmp_path):
    from wuwei.consolidation import note_findings
    base = workspace(tmp_path)
    for name, body in (('one', 'Record the final result.'),
                       ('two', 'Record the final results.')):
        (base / 'memory/notes' / (name + '.md')).write_text(
            '---\ntype: reference\nsummary: Final result\naliases: []\nstatus: active\n---\n'
            + body + '\n')
    assert any('near-duplicate' in item for item in note_findings(tmp_path))


def test_fold_snapshots_memory_and_charters_before_move(tmp_path, monkeypatch):
    from wuwei import promotion
    base = workspace(tmp_path)
    (base / 'memory/notes/old.md').write_text('---\ntype: reference\nsummary: One\naliases: []\nstatus: active\ncreated: 2026-08-01\n---\nOriginal\n')
    (base / 'memory/notes/live.md').write_text('---\ntype: reference\nsummary: One\naliases: []\nstatus: active\ncreated: 2026-08-01\n---\nSurvivor\n')
    (base / 'charters/lead.md').write_text('Original charter\n')
    (base / 'days/2026-09-29').mkdir(parents=True)
    (base / 'days/2026-09-29/report.md').write_text('Evidence\n')
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00+02:00')
    class VCS:
        def workspace_changes(self, *a, **kw):
            return registry.Result(0, [])
        def workspace_commit(self, *a, **kw):
            return registry.Result(0, None)
    monkeypatch.setattr(registry, 'load', lambda *args: VCS())
    promotion._apply(tmp_path, {'target': '.wuwei/memory/notes/old.md', 'action': 'fold',
        'survivor': '.wuwei/memory/notes/live.md', 'reason': 'duplicate',
        'evidence': '.wuwei/days/2026-09-29/report.md'})
    assert (base / 'memory/archive/old.md').read_text().endswith('Original\n')
    snapshots = list((base / 'memory/snapshots').iterdir())
    assert len(snapshots) == 1
    assert (snapshots[0] / 'memory/notes/old.md').read_text().endswith('Original\n')
    assert (snapshots[0] / 'charters/lead.md').read_text() == 'Original charter\n'
    assert (base / 'memory/notes/live.md').exists()
    assert 'Original' in (base / 'memory/notes/live.md').read_text()
    assert 'live |' in (base / 'memory/index.md').read_text()
    assert 'old |' not in (base / 'memory/index.md').read_text()


def test_35_days_archive_five_and_index_keeps_summaries(tmp_path, monkeypatch):
    from wuwei.consolidation import archive_days
    from wuwei.memory import write_index
    base = workspace(tmp_path)
    calls = []
    class VCS:
        def workspace_commit(self, repo, paths, root=None):
            calls.append(paths)
            return registry.Result(0, None)
    monkeypatch.setattr(registry, 'load', lambda *args: VCS())
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00+02:00')
    for age in range(1, 36):
        day = base / 'days' / (date(2026, 9, 29) - timedelta(days=age)).isoformat()
        day.mkdir(parents=True)
        (day / 'report.md').write_text(f'Summary {age}\n')
    assert len(archive_days(tmp_path)) == 5
    assert len(list((base / 'archive').iterdir())) == 5
    assert len(list((base / 'days').iterdir())) == 30
    write_index(tmp_path)
    assert sum(' | Summary ' in line for line in (base / 'memory/index.md').read_text().splitlines()) == 35
    assert calls and all(path.startswith(('days/', 'archive/', 'memory/index.md')) for path in calls[0])


def test_raw_day_move_is_refused(tmp_path, monkeypatch):
    base = workspace(tmp_path)
    (base / 'days/2026-08-01').mkdir(parents=True)
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    code, _ = check_bash({'cwd': str(tmp_path), 'tool_input': {
        'command': 'mv .wuwei/days/2026-08-01 .wuwei/archive/'}})
    assert code == 1
