"""Generated memory index and session payload contracts."""

import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
NOW = '2026-09-28T12:34:56+02:00'


def cli(root, *args):
    return subprocess.run(
        [sys.executable, '-P', '-m', 'wuwei', *args],
        env={**os.environ, 'PYTHONPATH': str(ROOT / 'cli'),
             'WUWEI_WORKSPACE': str(root), 'WUWEI_NOW': NOW},
        capture_output=True, text=True,
    )


def workspace(tmp_path):
    memory = tmp_path / '.wuwei/memory'
    (memory / 'notes').mkdir(parents=True)
    (memory / 'spine.md').write_text('# Spine\n')
    (tmp_path / '.wuwei/config.toml').write_text('')
    return tmp_path


def note(root, slug, summary='Current', body='Body', status='active'):
    path = root / '.wuwei/memory/notes' / f'{slug}.md'
    path.write_text(f'---\ntype: reference\nsummary: {summary}\naliases: []\nstatus: {status}\n---\n{body}\n')
    return path


def test_index_sorted_stable_and_body_change_only_one_line(tmp_path):
    root = workspace(tmp_path)
    note(root, 'zeta', 'Zed', 'Short')
    changed = note(root, 'alpha', 'First', 'Old body')
    note(root, 'retired', status='archived')
    for date, report in [('2026-09-27', 'Yesterday\nDetails'), ('2026-09-26', None),
                         ('2026-09-28', 'Today')]:
        day = root / '.wuwei/days' / date
        day.mkdir(parents=True)
        if report is not None:
            (day / 'report.md').write_text(report)
    result = cli(root, 'index')
    assert result.returncode == 0, result.stderr
    index = root / '.wuwei/memory/index.md'
    before = index.read_bytes()
    lines = before.decode().splitlines()
    assert len(lines) == 4
    assert lines[0].startswith('alpha | reference | First | ')
    assert lines[1].startswith('zeta | reference | Zed | ')
    assert lines[2:] == ['2026-09-26 | no report', '2026-09-27 | Yesterday']
    assert cli(root, 'index').returncode == 0
    assert index.read_bytes() == before
    changed.write_text(changed.read_text().replace('Old body', 'A much longer body'))
    assert cli(root, 'index').returncode == 0
    after = index.read_text().splitlines()
    assert after[0] != lines[0]
    assert after[1:] == lines[1:]


def test_index_invalid_note_and_capacity(tmp_path):
    root = workspace(tmp_path)
    note(root, 'valid')
    (root / '.wuwei/memory/notes/broken.md').write_text('broken')
    (root / '.wuwei/config.toml').write_text('[memory]\nmax_notes = 1\n')
    result = cli(root, 'index')
    assert result.returncode == 1
    assert 'INVALID broken: missing frontmatter' in (root / '.wuwei/memory/index.md').read_text()
    note(root, 'second')
    result = cli(root, 'index')
    assert result.returncode == 1
    assert 'overflow: 1' in result.stderr
    assert len((root / '.wuwei/memory/index.md').read_text().splitlines()) == 3


def test_payload_content_size_and_missing_source(tmp_path):
    root = workspace(tmp_path)
    (root / '.wuwei/memory/index.md').write_text('a | reference | Summary | 10 tokens\n')
    day = root / '.wuwei/days/2026-09-28'
    day.mkdir(parents=True)
    (day / 'state.json').write_text('{"cap": 2}')
    result = cli(root, 'payload')
    assert result.returncode == 0, result.stderr
    assert '# Spine' in result.stdout
    assert 'a | reference | Summary' in result.stdout
    assert '"cap": 2' in result.stdout
    content, size = result.stdout.rsplit('Size: ', 1)
    assert size == f'{len(content.encode())} bytes, {(len(content) + 3) // 4} estimated tokens\n'
    (root / '.wuwei/memory/index.md').unlink()
    result = cli(root, 'payload')
    assert result.returncode == 2
    assert 'index.md' in result.stderr


def test_index_config_finding_and_missing_config_is_unrun(tmp_path):
    root = workspace(tmp_path)
    config = root / '.wuwei/config.toml'
    config.write_text('[memory]\nmax_notes = 0\n')
    result = cli(root, 'index')
    assert result.returncode == 1
    assert 'memory.max_notes' in result.stderr
    assert not (root / '.wuwei/memory/index.md').exists()
    config.unlink()
    assert cli(root, 'index').returncode == 2


def test_payload_corrupt_state_fails_closed(tmp_path):
    root = workspace(tmp_path)
    (root / '.wuwei/memory/index.md').write_text('')
    day = root / '.wuwei/days/2026-09-28'
    day.mkdir(parents=True)
    (day / 'state.json').write_text('{bad')
    result = cli(root, 'payload')
    assert result.returncode == 2
    assert 'state.json' in result.stderr
    assert not result.stdout


def test_index_invalid_utf8_note_is_a_finding(tmp_path):
    root = workspace(tmp_path)
    index = root / '.wuwei/memory/index.md'
    index.write_text('stale\n')
    (root / '.wuwei/memory/notes/broken.md').write_bytes(b'\xff')
    result = cli(root, 'index')
    assert result.returncode == 1
    assert 'INVALID broken:' in index.read_text()
    assert 'stale' not in index.read_text()


def test_index_invalid_utf8_report_replaces_stale_index(tmp_path):
    root = workspace(tmp_path)
    index = root / '.wuwei/memory/index.md'
    index.write_text('stale\n')
    day = root / '.wuwei/days/2026-09-27'
    day.mkdir(parents=True)
    (day / 'report.md').write_bytes(b'\xff')
    result = cli(root, 'index')
    assert result.returncode == 1
    assert '2026-09-27 | INVALID report:' in index.read_text()
    assert 'stale' not in index.read_text()


def test_payload_has_no_promote_line(tmp_path):
    root = workspace(tmp_path)
    (root / '.wuwei/memory/index.md').write_text('')
    result = cli(root, 'payload')
    assert result.returncode == 0, result.stderr
    assert 'Last promote:' not in result.stdout


@pytest.mark.parametrize('location', ['days/day', 'archive/day', 'days/report'])
def test_index_refuses_symlinked_day_or_report(tmp_path, location):
    root = workspace(tmp_path)
    outside = tmp_path.parent / f'{tmp_path.name}-outside'
    outside.mkdir()
    (outside / 'report.md').write_text('Outside secret\n')
    if location.endswith('/day'):
        parent = root / '.wuwei' / location.split('/')[0]
        parent.mkdir()
        (parent / '2026-09-27').symlink_to(outside, target_is_directory=True)
    else:
        day = root / '.wuwei/days/2026-09-27'
        day.mkdir(parents=True)
        (day / 'report.md').symlink_to(outside / 'report.md')
    result = cli(root, 'index')
    assert result.returncode == 2
    assert 'symlink' in result.stderr
    assert 'Outside secret' not in result.stdout


def test_index_missing_notes_directory_is_unrun(tmp_path):
    root = workspace(tmp_path)
    (root / '.wuwei/memory/notes').rmdir()
    result = cli(root, 'index')
    assert result.returncode == 2
    assert 'notes' in result.stderr


def test_index_invalid_slug_cannot_inject_line(tmp_path):
    root = workspace(tmp_path)
    note(root, 'bad\nforged')
    result = cli(root, 'index')
    assert result.returncode == 1
    assert "INVALID 'bad\\nforged': invalid slug" in (root / '.wuwei/memory/index.md').read_text()


def test_index_sorts_days_across_live_and_archive_and_rejects_compact_date(tmp_path):
    root = workspace(tmp_path)
    for parent, dates in [('days', ('2026-09-27', '20260921')),
                          ('archive', ('2026-09-26',))]:
        for day in dates:
            (root / '.wuwei' / parent / day).mkdir(parents=True)
    result = cli(root, 'index')
    assert result.returncode == 0, result.stderr
    assert (root / '.wuwei/memory/index.md').read_text().splitlines() == [
        '2026-09-26 | no report', '2026-09-27 | no report']


def test_index_mode_matches_template(tmp_path):
    root = workspace(tmp_path)
    result = cli(root, 'index')
    assert result.returncode == 0, result.stderr
    assert (root / '.wuwei/memory/index.md').stat().st_mode & 0o777 == 0o644
