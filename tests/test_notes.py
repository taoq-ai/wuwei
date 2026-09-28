"""Note creation and reusable frontmatter contract."""

import os
from pathlib import Path
from types import SimpleNamespace
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
NOW = '2026-09-28T12:34:56+02:00'


def cli(root, *args):
    return subprocess.run(
        [sys.executable, '-S', '-m', 'wuwei', *args],
        env={**os.environ, 'PYTHONPATH': str(ROOT / 'cli'),
             'WUWEI_WORKSPACE': str(root), 'WUWEI_NOW': NOW},
        capture_output=True, text=True,
    )


@pytest.fixture
def workspace(tmp_path):
    (tmp_path / '.wuwei/memory/notes').mkdir(parents=True)
    return tmp_path


def test_add_note(workspace):
    result = cli(workspace, 'note', 'add', 'system-shape', '--type', 'decision',
                 '--summary', 'The system uses local files', '--alias', 'architecture',
                 '--body', 'Why: Local files can be inspected offline.')
    assert result.returncode == 0, result.stderr
    from wuwei.notes import parse_note
    path = workspace / '.wuwei/memory/notes/system-shape.md'
    fields, body = parse_note(path.read_text())
    assert fields == {'type': 'decision', 'summary': 'The system uses local files',
                      'aliases': ['architecture'], 'status': 'active', 'created': '2026-09-28'}
    assert body == 'Why: Local files can be inspected offline.\n'


@pytest.mark.parametrize('args,reason', [
    (('missing', '--type', 'reference'), 'summary'),
    (('blank', '--type', 'reference', '--summary', '  '), 'summary'),
    (('multiline', '--type', 'reference', '--summary', 'first\nsecond'), 'summary'),
    (('decision', '--type', 'decision', '--summary', 'A choice', '--body', 'What happened'), 'Why:'),
    (('../escape', '--type', 'reference', '--summary', 'Good'), 'slug'),
    (('bad-alias', '--type', 'reference', '--summary', 'Good', '--alias', 'a,b'), 'alias'),
])
def test_add_refuses_invalid(workspace, args, reason):
    result = cli(workspace, 'note', 'add', *args)
    assert result.returncode == 1, result.stderr
    assert reason in result.stderr
    assert not list((workspace / '.wuwei/memory/notes').iterdir())


def test_add_never_overwrites(workspace):
    path = workspace / '.wuwei/memory/notes/existing.md'
    path.write_text('keep')
    result = cli(workspace, 'note', 'add', 'existing', '--type', 'hub', '--summary', 'New')
    assert result.returncode == 1
    assert 'exists' in result.stderr
    assert path.read_text() == 'keep'


def test_add_missing_workspace(tmp_path):
    result = cli(tmp_path, 'note', 'add', 'test', '--type', 'hub', '--summary', 'Good')
    assert result.returncode == 2
    assert '.wuwei' in result.stderr


def test_add_preserves_non_ascii_summary(workspace):
    result = cli(workspace, 'note', 'add', 'cafe', '--type', 'hub', '--summary', 'Café', '--alias', 'Résumé')
    assert result.returncode == 0, result.stderr
    content = (workspace / '.wuwei/memory/notes/cafe.md').read_text()
    assert 'summary: "Café"' in content
    assert 'aliases: ["Résumé"]' in content


def test_add_refuses_symlinked_notes_directory(workspace, tmp_path):
    outside = tmp_path.parent / f'{tmp_path.name}-outside'
    outside.mkdir()
    directory = workspace / '.wuwei/memory/notes'
    directory.rmdir()
    directory.symlink_to(outside, target_is_directory=True)
    result = cli(workspace, 'note', 'add', 'escape', '--type', 'hub', '--summary', 'Good')
    assert result.returncode == 2
    assert not list(outside.iterdir())


def test_add_refuses_notes_directory_outside_workspace(workspace, tmp_path):
    outside = tmp_path.parent / f'{tmp_path.name}-memory'
    (outside / 'notes').mkdir(parents=True)
    memory = workspace / '.wuwei/memory'
    (memory / 'notes').rmdir()
    memory.rmdir()
    memory.symlink_to(outside, target_is_directory=True)
    result = cli(workspace, 'note', 'add', 'escape', '--type', 'hub', '--summary', 'Good')
    assert result.returncode == 2
    assert not list((outside / 'notes').iterdir())


def test_add_syncs_note_and_directory(workspace, monkeypatch):
    from wuwei.commands import note
    from wuwei import workspace as workspace_module
    synced = []
    real_fsync = os.fsync

    def record_fsync(fd):
        synced.append(os.fstat(fd).st_mode)
        real_fsync(fd)

    monkeypatch.setenv('WUWEI_WORKSPACE', str(workspace))
    monkeypatch.setenv('WUWEI_NOW', NOW)
    monkeypatch.setattr(workspace_module.os, 'fsync', record_fsync)
    args = SimpleNamespace(slug='synced', type='hub', summary='Good', alias=[], body='')
    assert note.run_add(args) == 0
    import stat
    assert [stat.S_ISREG(mode) for mode in synced] == [True, False]


def test_parse_note_contract():
    from wuwei.notes import parse_note
    fields, body = parse_note('---\ntype: reference\nsummary: Current state\naliases: [first, second]\nstatus: archived\n---\nBody\n')
    assert fields == {'type': 'reference', 'summary': 'Current state',
                      'aliases': ['first', 'second'], 'status': 'archived'}
    assert body == 'Body\n'


def test_parse_note_crlf_and_quoted_colon():
    from wuwei.notes import parse_note
    fields, body = parse_note('---\r\ntype: hub\r\nsummary: "A: detail"\r\naliases: ["B: detail"]\r\nstatus: active\r\n---\r\nBody\r\n')
    assert fields['summary'] == 'A: detail'
    assert fields['aliases'] == ['B: detail']
    assert body == 'Body\n'


@pytest.mark.parametrize('raw,reason', [
    ('summary: Good\naliases: []\nstatus: active', 'frontmatter'),
    ('---\ntype: reference\naliases: []\nstatus: active\n---\n', 'summary'),
    ('---\ntype: wrong\nsummary: Good\naliases: []\nstatus: active\n---\n', 'type'),
    ('---\ntype: hub\nsummary: Good\naliases: nope\nstatus: active\n---\n', 'aliases'),
    ('---\ntype: hub\nsummary: Good\naliases: []\nstatus: wrong\n---\n', 'status'),
    ('---\ntype: decision\nsummary: Good\naliases: []\nstatus: active\n---\n', 'Why:'),
    ('---\ntype: hub\nsummary: Good\naliases: []\nstatus: active\nunknown: x\n---\n', 'unknown'),
    ('---\ntype: []\nsummary: Good\naliases: []\nstatus: active\n---\n', 'type'),
    ('---\ntype: hub\nsummary: Good\naliases: []\nstatus: []\n---\n', 'status'),
    ('---\ntype: hub\nsummary: Good\naliases: []\nstatus: active', 'closing'),
    ('---\ntype: hub\nsummary: Good\nsummary: Again\naliases: []\nstatus: active\n---\n', 'duplicate'),
    ('---\ntype: hub\nsummary: Good\naliases: []\nstatus: active\ncreated: nope\n---\n', 'created'),
    ('---\ntype: hub\nsummary: The note is\n  status: active\naliases: []\n---\n', 'frontmatter'),
])
def test_parse_note_rejects_invalid(raw, reason):
    from wuwei.notes import parse_note
    with pytest.raises(ValueError, match=reason):
        parse_note(raw)


@pytest.mark.parametrize('separator', ['\x0b', '\x0c', '\x1c', '\x1d', '\x1e', '\x85', '\u2028', '\u2029'])
def test_parse_note_rejects_hidden_summary_line(separator):
    from wuwei.notes import parse_note
    raw = f'---\ntype: hub\nsummary: a{separator}status: archived\naliases: []\n---\n'
    with pytest.raises(ValueError, match='summary'):
        parse_note(raw)


@pytest.mark.parametrize('separator', ['\x0b', '\x0c', '\x1c', '\x1d', '\x1e', '\x85', '\u2028', '\u2029'])
def test_parse_note_rejects_hidden_alias_line(separator):
    import json
    from wuwei.notes import parse_note
    alias = json.dumps('a' + separator + 'status: archived')
    raw = f'---\ntype: hub\nsummary: Good\naliases: [{alias}]\nstatus: active\n---\n'
    with pytest.raises(ValueError, match='aliases'):
        parse_note(raw)


def test_parse_note_rejects_unquoted_alias_trailing_separator():
    from wuwei.notes import parse_note
    raw = '---\ntype: hub\nsummary: Good\naliases: [a\u2028]\nstatus: active\n---\n'
    with pytest.raises(ValueError, match='aliases'):
        parse_note(raw)
