"""Issue #443: week and month digests built from day records in one fixed shape."""

from datetime import date
import json
import tarfile

import pytest

from wuwei import redact, workspace as workspace_module


WEEK = '''# Week 2026-W40 (2026-09-28 to 2026-10-04)

## Decisions
- 2026-09-30 D-1: Retry the import with backoff? Outcome: backoff
- 2026-10-01 D-2: Should the seats carry it? Outcome: carry
- 2026-10-02 D-4: decided keep

## Lessons
- 2026-09-30 landed: builder.md patch: Run the fast checks before the gate.
- 2026-10-01 rejected: planner.md add

## Metrics
- 2026-09-30 Escaped defects: 0; baseline: 0
- 2026-10-01 unmeasured
- 2026-10-02 unmeasured

## Incidents
- 2026-10-01 mcp.finding: 1

## Items
- 2026-09-30 closed: ITEM-1, ITEM-2; carried: ITEM-3; parked: ITEM-4
'''


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


@pytest.fixture
def root(tmp_path, monkeypatch):
    base = tmp_path / '.wuwei'
    (base / 'memory/notes').mkdir(parents=True)
    (base / 'charters').mkdir()
    # #533: the owner reads the digest, so an outward.patterns list does not hide its free text.
    write(base / 'config.toml', '[outward]\npatterns = ["\\\\bseats?\\\\b"]\n')
    monkeypatch.setenv('WUWEI_NOW', '2026-10-03T12:00:00+02:00')
    monkeypatch.setattr(redact, 'VALUES', {'sekrit-value'})
    day = base / 'days/2026-09-30'
    write(day / 'decisions/D-1.md', 'Question: Retry the import with backoff?\nOutcome: backoff\n')
    write(day / 'report.md', '# WUWEI report 2026-09-30\n\n## Outcome\n- Escaped defects: 0; baseline: 0\n'
          '\n## Merged\n- ITEM-1\n')
    write(day / 'state.json', json.dumps({'items': {
        'ITEM-1': {'phase': 'merged'}, 'ITEM-2': {'phase': 'merged'},
        'ITEM-3': {'phase': 'building'}, 'ITEM-4': {'phase': 'parked'}}}))
    day = base / 'days/2026-10-01'
    write(day / 'decisions/D-2.md', 'Question: Should the seats carry it?\nOutcome: carry\n')
    write(day / 'decisions/D-3.md', 'Question: Still open?\nOutcome: pending\n')
    write(day / 'events.jsonl', json.dumps({'kind': 'mcp.finding', 'payload': {'severity': 'high'}})
          + '\n' + json.dumps({'kind': 'mcp.finding', 'payload': {'severity': 'low'}}) + '\n')
    write(base / 'days/2026-10-02/decisions/D-4.md', 'Question: Keep src/app.py as is?\nOutcome: keep\n')
    write(base / 'memory/ledger.jsonl', ''.join(json.dumps(row) + '\n' for row in (
        {'date': '2026-09-30', 'run_id': 'a', 'target': '.wuwei/charters/builder.md', 'action': 'patch',
         'status': 'landed', 'reason': 'Run the fast checks before the gate.', 'evidence': 'x'},
        {'date': '2026-10-01', 'run_id': 'b', 'target': '.wuwei/charters/planner.md', 'action': 'add',
         'status': 'rejected', 'reason': 'token sekrit-value leaked', 'evidence': 'x'},
        {'date': '2026-09-01', 'run_id': 'c', 'target': '.wuwei/charters/lead.md', 'action': 'add',
         'status': 'landed', 'reason': 'Out of period.', 'evidence': 'x'})))
    return tmp_path


def test_period_names_the_iso_week_and_the_month():
    from wuwei import digest
    name, title, dates = digest.period(date(2026, 10, 3), 'week')
    assert (name, title) == ('2026-W40', '# Week 2026-W40 (2026-09-28 to 2026-10-04)')
    assert dates[0] == date(2026, 9, 28) and dates[-1] == date(2026, 10, 4) and len(dates) == 7
    name, title, dates = digest.period(date(2026, 10, 3), 'month')
    assert (name, title, len(dates)) == ('2026-10', '# Month 2026-10', 31)


def test_build_has_the_fixed_shape_and_keeps_only_clean_free_text(root):
    from wuwei import digest
    _, title, dates = digest.period(date(2026, 10, 3), 'week')
    text = digest.build(root, title, dates, workspace_module.load_config(root))
    assert text == WEEK
    for leaked in ('src/app.py', 'sekrit-value', 'Out of period'):
        assert leaked not in text


def test_build_writes_none_for_empty_sections(root):
    from wuwei import digest
    text = digest.build(root, '# Week 2026-W30 (x)', [date(2026, 7, 20)], workspace_module.load_config(root))
    assert text == '# Week 2026-W30 (x)\n' + ''.join(
        f'\n## {name}\nnone\n' for name in ('Decisions', 'Lessons', 'Metrics', 'Incidents', 'Items'))


def test_write_is_idempotent_reads_tarballs_and_honours_off(root, monkeypatch):
    from wuwei import digest
    path = digest.write(root, date(2026, 10, 3), 'week')
    assert path == root / '.wuwei/memory/digests/2026-W40.md' and path.read_text() == WEEK
    before = path.stat().st_mtime_ns
    assert digest.write(root, date(2026, 10, 3), 'week') == path
    assert path.stat().st_mtime_ns == before and path.read_text() == WEEK
    day = root / '.wuwei/days/2026-09-30'
    target = root / '.wuwei/archive/2026/2026-09-30.tar.gz'
    target.parent.mkdir(parents=True)
    with tarfile.open(target, 'x:gz') as tar:
        tar.add(day, arcname=day.name)
    import shutil
    shutil.rmtree(day)
    path.unlink()
    assert digest.write(root, date(2026, 10, 3), 'week').read_text() == WEEK
    month = digest.write(root, date(2026, 10, 3), 'month')
    assert month.name == '2026-10.md' and month.read_text().startswith('# Month 2026-10\n')
    assert digest.latest(root) == (month, path)
    write(root / '.wuwei/config.toml', '[memory]\ndigest = "off"\n')
    path.unlink()
    assert digest.write(root, date(2026, 10, 3), 'week') is None and not path.exists()


def test_write_refuses_a_symlinked_digest_directory(root, tmp_path_factory):
    from wuwei import digest
    (root / '.wuwei/memory/digests').symlink_to(tmp_path_factory.mktemp('elsewhere'))
    with pytest.raises(ValueError):
        digest.write(root, date(2026, 10, 3), 'week')


def test_latest_is_empty_without_digests(root):
    from wuwei import digest
    assert digest.latest(root) == (None, None)
