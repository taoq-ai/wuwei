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
    from wuwei.consolidation import day_records
    assert (base / 'archive/2026/2026-08-01.tar.gz').is_file()
    assert day_records(tmp_path, '2026-08-01')['report.md'] == 'Old day\n'


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


def test_35_days_archive_five_tarballs_and_index_keeps_raw_days(tmp_path, monkeypatch):
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
    assert len(list((base / 'archive/2026').glob('*.tar.gz'))) == 5
    assert len(list((base / 'days').iterdir())) == 30
    write_index(tmp_path)
    assert sum(' | Summary ' in line for line in (base / 'memory/index.md').read_text().splitlines()) == 30
    assert calls and all(path.startswith(('archive/', 'memory/index.md', 'memory/digests/'))
                         for path in calls[0])
    assert 'memory/digests/2026-W35.md' in calls[0] and 'memory/digests/2026-08.md' in calls[0]


def test_raw_day_move_is_refused(tmp_path, monkeypatch):
    base = workspace(tmp_path)
    (base / 'days/2026-08-01').mkdir(parents=True)
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    code, _ = check_bash({'cwd': str(tmp_path), 'tool_input': {
        'command': 'mv .wuwei/days/2026-08-01 .wuwei/archive/'}})
    assert code == 1


def _tarball(base, day, members):
    import io
    import tarfile
    target = base / 'archive' / day[:4] / f'{day}.tar.gz'
    target.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(target, 'w:gz') as tar:
        for name, text, kind in members:
            info = tarfile.TarInfo(name)
            if kind == 'file':
                data = text.encode()
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
            else:
                info.type, info.linkname = tarfile.SYMTYPE, text
                tar.addfile(info)
    return target


def test_day_records_reads_raw_legacy_and_tarball_days(tmp_path):
    from wuwei.consolidation import day_records
    base = workspace(tmp_path)
    expected = {'report.md': 'Report\n', 'decisions/D-1.md': 'Question: x\n'}
    for parent in ('days/2026-08-01', 'archive/2026-08-02'):
        for name, text in expected.items():
            (base / parent / name).parent.mkdir(parents=True, exist_ok=True)
            (base / parent / name).write_text(text)
    _tarball(base, '2026-08-03', [(f'2026-08-03/{name}', text, 'file') for name, text in expected.items()])
    for day in ('2026-08-01', '2026-08-02', '2026-08-03'):
        assert day_records(tmp_path, day) == expected
    assert day_records(tmp_path, '2026-08-04') is None


def test_day_records_refuses_unsafe_days_and_members(tmp_path):
    import pytest
    from wuwei.consolidation import day_records
    base = workspace(tmp_path)
    (base / 'days').mkdir()
    (base / 'days/2026-08-01').symlink_to(tmp_path)
    with pytest.raises(ValueError):
        day_records(tmp_path, '2026-08-01')
    for day, member, kind in (('2026-08-02', '../x', 'file'), ('2026-08-03', '/2026-08-03/x', 'file'),
                              ('2026-08-04', '2026-08-04/link', 'link'), ('2026-08-05', 'other/x', 'file'),
                              ('2026-08-06', '2026-08-06/../../x', 'file')):
        _tarball(base, day, [(member, 'x', kind)])
        with pytest.raises(ValueError):
            day_records(tmp_path, day)
    target = _tarball(base, '2026-08-07', [('2026-08-07/report.md', 'Report\n' * 500, 'file')])
    target.write_bytes(target.read_bytes()[:40])
    with pytest.raises((ValueError, OSError)):
        day_records(tmp_path, '2026-08-07')


def _vcs(monkeypatch, calls=None):
    class VCS:
        def workspace_commit(self, repo, paths, root=None):
            (calls if calls is not None else []).append(paths)
            return registry.Result(0, None)
        def workspace_changes(self, *a, **kw):
            return registry.Result(0, [])
    monkeypatch.setattr(registry, 'load', lambda *args: VCS())


def test_archive_packs_every_file_and_legacy_directories(tmp_path, monkeypatch):
    import tarfile
    from wuwei.consolidation import archive_days, day_records
    base = workspace(tmp_path)
    _vcs(monkeypatch)
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00+02:00')
    day = base / 'days/2026-08-10'
    (day / 'decisions').mkdir(parents=True)
    (day / 'report.md').write_text('R\n')
    (day / 'decisions/D-1.md').write_text('Q\n')
    (base / 'archive/2026-08-01').mkdir(parents=True)
    (base / 'archive/2026-08-01/report.md').write_text('Legacy\n')
    assert sorted(archive_days(tmp_path)) == ['2026-08-01', '2026-08-10']
    assert not day.exists() and not (base / 'archive/2026-08-01').exists()
    with tarfile.open(base / 'archive/2026/2026-08-10.tar.gz') as tar:
        assert {m.name for m in tar.getmembers() if m.isfile()} == {
            '2026-08-10/report.md', '2026-08-10/decisions/D-1.md'}
    assert day_records(tmp_path, '2026-08-01') == {'report.md': 'Legacy\n'}


def test_archive_refuses_existing_tarball_and_symlinks(tmp_path, monkeypatch):
    import pytest
    from wuwei.consolidation import archive_days
    base = workspace(tmp_path)
    _vcs(monkeypatch)
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00+02:00')
    day = base / 'days/2026-08-10'
    day.mkdir(parents=True)
    (day / 'report.md').write_text('R\n')
    (base / 'archive/2026').mkdir(parents=True)
    (base / 'archive/2026/2026-08-10.tar.gz').write_text('x')
    with pytest.raises(ValueError):
        archive_days(tmp_path)
    assert (day / 'report.md').exists()
    (base / 'archive/2026/2026-08-10.tar.gz').unlink()
    (day / 'link.md').symlink_to(day / 'report.md')
    with pytest.raises(ValueError):
        archive_days(tmp_path)
    assert not (base / 'archive/2026/2026-08-10.tar.gz').exists() and (day / 'report.md').exists()


def test_expired_lists_raw_and_legacy_days_past_the_window(tmp_path, monkeypatch):
    from wuwei.consolidation import expired
    base = workspace(tmp_path)
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00+02:00')
    for name in ('days/2026-08-01', 'days/2026-09-28', 'archive/2026-08-02'):
        (base / name).mkdir(parents=True)
    assert [p.relative_to(base).as_posix() for p in expired(tmp_path)] == [
        'days/2026-08-01', 'archive/2026-08-02']


DECISION = '''Question: Carry parked items?
Context: Two items waited all week.
Options:
| Option | Description |
| --- | --- |
| carry | Do carry parked items |
| defer | Defer until tomorrow |
Musts:
| Criterion | carry | defer |
| --- | --- | --- |
| Safe | pass | pass |
Wants:
| Criterion | Weight | carry | defer |
| --- | --- | --- | --- |
| Flow | 10 | 8 | 2 |
Recommendation: carry
Confidence: high
Reversibility: two-way
Blast radius: own branch
Pre-mortem: Items pile up.
Revisit: Items pile up.
Decided-by: owner
Outcome: carry
'''


def forgetting(tmp_path, monkeypatch):
    base = workspace(tmp_path)
    monkeypatch.setenv('WUWEI_NOW', '2026-10-03T12:00:00+02:00')
    return base


def note_file(base, slug, body, created='2026-07-01', summary=None):
    path = base / 'memory/notes' / f'{slug}.md'
    path.write_text(f'---\ntype: reference\nsummary: {summary or slug}\naliases: []\nstatus: active\n'
                    f'created: {created}\n---\n{body}\n')
    return path


def test_unreferenced_note_is_proposed_for_archive(tmp_path, monkeypatch):
    from wuwei.consolidation import forget_proposals
    base = forgetting(tmp_path, monkeypatch)
    note_file(base, 'retry-policy', 'Back off three times.')
    note_file(base, 'young', 'New lesson.', created='2026-09-03')
    assert forget_proposals(tmp_path) == [{
        'kind': 'unreferenced', 'action': 'archive', 'target': '.wuwei/memory/notes/retry-policy.md',
        'evidence': 'retry-policy: named by no brief, decision or retro since 2026-08-04 (60 days)'}]
    _tarball(base, '2026-08-19', [('2026-08-19/briefs/x.md', 'Read notes/retry-policy.md first.\n', 'file')])
    assert forget_proposals(tmp_path) == []


def test_duplicate_notes_fold_into_the_more_loaded_note(tmp_path, monkeypatch):
    from wuwei import promotion
    from wuwei.consolidation import forget_proposals
    base = forgetting(tmp_path, monkeypatch)
    (base / 'days/2026-10-02').mkdir(parents=True)
    (base / 'days/2026-10-02/briefs').mkdir()
    (base / 'days/2026-10-02/briefs/b.md').write_text('alpha beta\n')
    note_file(base, 'alpha', 'Record the final result.', summary='Final result')
    note_file(base, 'beta', 'Record the final results.', summary='Final result')
    monkeypatch.setattr(promotion, 'adherence_counts', lambda root: {'note_loads': {'beta': 4}})
    assert forget_proposals(tmp_path) == [{
        'kind': 'duplicate', 'action': 'fold', 'target': '.wuwei/memory/notes/alpha.md',
        'survivor': '.wuwei/memory/notes/beta.md',
        'evidence': 'alpha, beta: near-duplicate notes (0.99); beta has 4 loads, alpha 0'}]


def test_superseded_rule_drops_the_earlier_line_in_one_charter_only(tmp_path, monkeypatch):
    from wuwei.consolidation import forget_proposals, note_findings
    base = forgetting(tmp_path, monkeypatch)
    (base / 'charters/builder.md').write_text(
        '# Builder\n- Record the final result after review.\n- Keep evidence.\n'
        '- Record the final results after review.\n')
    assert forget_proposals(tmp_path) == [{
        'kind': 'superseded', 'action': 'drop', 'target': '.wuwei/charters/builder.md',
        'old_text': '- Record the final result after review.\n',
        'evidence': 'builder.md line 2 is superseded by line 4 (0.99)'}]
    (base / 'charters/builder.md').write_text('- Record the final result after review.\n')
    (base / 'charters/lead.md').write_text('- Record the final results after review.\n')
    assert forget_proposals(tmp_path) == []
    assert note_findings(tmp_path) == ['builder.md, lead.md: near-duplicate charter rules']


def test_rule_contradicted_by_an_answered_decision_is_dropped(tmp_path, monkeypatch):
    from wuwei.consolidation import forget_proposals
    base = forgetting(tmp_path, monkeypatch)
    (base / 'charters/planner.md').write_text('- Do not carry parked items.\n')
    (base / 'days/2026-10-01/decisions').mkdir(parents=True)
    (base / 'days/2026-10-01/decisions/D-2.md').write_text(DECISION)
    (base / 'days/2026-10-01/decisions/D-3.md').write_text(DECISION.replace('Outcome: carry', 'Outcome: pending'))
    assert forget_proposals(tmp_path) == [{
        'kind': 'contradicted', 'action': 'drop', 'target': '.wuwei/charters/planner.md',
        'old_text': '- Do not carry parked items.\n',
        'evidence': 'D-2 on 2026-10-01 chose carry: Do carry parked items'}]


ARCHIVE = {'kind': 'unreferenced', 'action': 'archive', 'target': '.wuwei/memory/notes/old.md',
           'evidence': 'old: named by no brief, decision or retro since 2026-08-04 (60 days)'}
DROP = {'kind': 'superseded', 'action': 'drop', 'target': '.wuwei/charters/builder.md',
        'old_text': '- Keep A.\n', 'evidence': 'builder.md line 1 is superseded by line 2 (0.90)'}


def test_merge_proposals_numbers_dedups_and_respects_declines(tmp_path, monkeypatch):
    import json
    import pytest
    from wuwei.consolidation import merge_proposals
    base = forgetting(tmp_path, monkeypatch)
    path = base / 'memory/forget.json'
    pending = merge_proposals(tmp_path, [ARCHIVE])
    assert pending == [{**ARCHIVE, 'id': 'F-1', 'status': 'pending', 'created': '2026-10-03'}]
    assert json.loads(path.read_text()) == {'F-1': pending[0]}
    before = path.stat().st_mtime_ns
    assert merge_proposals(tmp_path, [ARCHIVE]) == pending and path.stat().st_mtime_ns == before
    rows = json.loads(path.read_text())
    rows['F-1']['status'] = 'declined'
    path.write_text(json.dumps(rows))
    assert merge_proposals(tmp_path, [ARCHIVE]) == []
    assert merge_proposals(tmp_path, [ARCHIVE, DROP]) == [
        {**DROP, 'id': 'F-2', 'status': 'pending', 'created': '2026-10-03'}]
    for broken in ('{nope', '[]', '{"F-1": {"id": "F-1"}}'):
        path.write_text(broken)
        with pytest.raises(ValueError):
            merge_proposals(tmp_path, [])
    path.unlink()
    path.symlink_to(base / 'config.toml')
    with pytest.raises(ValueError):
        merge_proposals(tmp_path, [])


def forget_setup(tmp_path, monkeypatch, rows):
    import json
    from wuwei import memory
    base = forgetting(tmp_path, monkeypatch)
    _vcs(monkeypatch)
    note_file(base, 'old', 'Old lesson.')
    (base / 'charters/builder.md').write_text('- Keep A.\n- Keep A now.\n')
    (base / 'memory/forget.json').write_text(json.dumps(
        {row['id']: {**row, 'status': 'pending', 'created': '2026-10-03'} for row in rows}))
    exports = []
    monkeypatch.setattr(memory, 'export', lambda root: exports.append(root) or (None, False), raising=False)
    return base, exports


def events(base):
    import json
    path = base / 'days/2026-10-03/events.jsonl'
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def test_forget_apply_archives_logs_and_exports(tmp_path, monkeypatch):
    import json
    from wuwei.consolidation import forget, read_forget
    base, exports = forget_setup(tmp_path, monkeypatch, [{**ARCHIVE, 'id': 'F-1'}])
    asked = []
    row = forget(tmp_path, 'F-1', 'apply', confirm=lambda fingerprint, prompt: asked.append(prompt) or True)
    assert row['status'] == 'applied' and read_forget(tmp_path)['F-1']['status'] == 'applied'
    assert asked and 'F-1' in asked[0] and ARCHIVE['evidence'] in asked[0]
    assert (base / 'memory/archive/old.md').is_file() and not (base / 'memory/notes/old.md').exists()
    ledger = [json.loads(line) for line in (base / 'memory/ledger.jsonl').read_text().splitlines()]
    assert [(r['status'], r['target'], r['evidence']) for r in ledger] == [
        ('landed', ARCHIVE['target'], '.wuwei/memory/forget.json')]
    assert [(e['kind'], e['payload']) for e in events(base)] == [('memory.folded', {
        'id': 'F-1', 'kind': 'unreferenced', 'action': 'archive', 'target': ARCHIVE['target'],
        'archive': 'memory/archive/old.md'})]
    assert exports == [tmp_path]
    from wuwei.commands.event import EVENT_PRODUCERS
    assert {'memory.folded', 'memory.consolidated'} <= set(EVENT_PRODUCERS)


def test_forget_no_keep_and_refusals(tmp_path, monkeypatch):
    import pytest
    from wuwei.consolidation import forget, read_forget
    base, exports = forget_setup(tmp_path, monkeypatch, [{**ARCHIVE, 'id': 'F-1'}, {**DROP, 'id': 'F-2'}])
    with pytest.raises(PermissionError):
        forget(tmp_path, 'F-1', 'apply', confirm=lambda fingerprint, prompt: False)
    assert (base / 'memory/notes/old.md').exists() and not (base / 'memory/ledger.jsonl').exists()
    assert read_forget(tmp_path)['F-1']['status'] == 'pending'

    def refuse(*args, **kwargs):
        raise AssertionError('keep must not ask')
    assert forget(tmp_path, 'F-1', 'keep', confirm=refuse)['status'] == 'declined'
    for ident in ('F-1', 'F-9'):
        with pytest.raises(ValueError):
            forget(tmp_path, ident, 'apply', confirm=lambda fingerprint, prompt: True)
    (base / 'charters/builder.md').write_text('- Keep B.\n')
    with pytest.raises(ValueError):
        forget(tmp_path, 'F-2', 'apply', confirm=lambda fingerprint, prompt: True)
    assert (base / 'memory/ledger.jsonl').read_text().count('"rejected"') == 1
    assert read_forget(tmp_path)['F-2']['status'] == 'pending' and events(base) == [] and exports == []


def test_forget_drop_lands_through_promotion(tmp_path, monkeypatch):
    from wuwei.consolidation import forget
    base, exports = forget_setup(tmp_path, monkeypatch, [{**DROP, 'id': 'F-2'}])
    forget(tmp_path, 'F-2', 'apply', confirm=lambda fingerprint, prompt: True)
    assert (base / 'charters/builder.md').read_text() == '- Keep A now.\n'
    assert (base / 'memory/archive/dropped-rules.md').read_text() == '- 2026-10-03 builder.md: Keep A.\n'
    assert events(base)[0]['payload']['archive'] == 'memory/archive/dropped-rules.md'


def test_issue_acceptance_consolidate_builds_the_tiers(tmp_path, monkeypatch, capsys):
    import json
    from argparse import Namespace
    from wuwei import memory, workspace as workspace_module
    from wuwei.commands.consolidate import run
    base = forgetting(tmp_path, monkeypatch)
    (base / 'memory/spine.md').write_text('# Spine\n')
    (base / 'charters/builder.md').write_text('- Keep evidence.\n')
    _vcs(monkeypatch)
    monkeypatch.setattr(workspace_module, 'find_workspace', lambda *a, **k: tmp_path)
    today = date(2026, 10, 3)
    for age in range(1, 46):
        day = base / 'days' / (today - timedelta(days=age)).isoformat()
        day.mkdir(parents=True)
        (day / 'report.md').write_text(f'# WUWEI report {day.name}\n\n## Outcome\n- Escaped defects: 0; baseline: 0\n')
        (day / 'state.json').write_text(json.dumps({'items': {'ITEM-1': {'phase': 'merged'}}}))
        (day / 'events.jsonl').write_text(json.dumps({'kind': 'note', 'payload': {}, 'ts': 'x'}) + '\n')
    assert run(Namespace(widget=False)) == 0
    assert len(list((base / 'archive/2026').glob('*.tar.gz'))) == 15
    assert len(list((base / 'days').iterdir())) == 31
    digests = sorted(path.name for path in (base / 'memory/digests').iterdir())
    assert digests == ['2026-08.md', '2026-09.md', '2026-10.md', '2026-W34.md', '2026-W35.md',
                       '2026-W36.md', '2026-W40.md']
    index = (base / 'memory/index.md').read_text().splitlines()
    assert sum(line[:4] == '2026' for line in index) == 30
    content, _, tokens = memory.session_payload(tmp_path)
    assert content.startswith('Digests:\n# Month 2026-10\n') and tokens <= 6000
    assert (tmp_path / 'CLAUDE.md').read_text().count('- Keep evidence.') == 1
    assert [e['kind'] for e in events(base)] == ['memory.consolidated']
    assert events(base)[0]['payload'] == {'archived': 15, 'pending': 0}
    capsys.readouterr()
    assert run(Namespace(widget=False)) == 0
    assert '2026-08-19: archived' not in capsys.readouterr().out


def test_consolidate_widget_asks_each_pending_proposal(tmp_path, monkeypatch, capsys):
    import json
    from argparse import Namespace
    from wuwei import workspace as workspace_module
    from wuwei.commands.consolidate import run
    base, _ = forget_setup(tmp_path, monkeypatch, [{**ARCHIVE, 'id': 'F-1'}])
    monkeypatch.setattr(workspace_module, 'find_workspace', lambda *a, **k: tmp_path)
    before = sorted(str(p) for p in base.rglob('*'))
    assert run(Namespace(widget=True)) == 1
    [widget] = json.loads(capsys.readouterr().out)
    assert widget['header'] == 'F-1' and widget['record'] == 'bin/wuwei memory forget F-1 <label>'
    assert [option['label'] for option in widget['options']] == ['apply', 'keep']
    assert widget['question'].startswith('Morning gate (days/2026-10-03/plan.md): F-1: ')
    assert ARCHIVE['evidence'] in widget['question']
    assert sorted(str(p) for p in base.rglob('*')) == before
    (base / 'memory/forget.json').write_text('{}')
    assert run(Namespace(widget=True)) == 0
