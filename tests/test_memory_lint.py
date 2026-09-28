"""Memory lint reports actionable note findings without writing state."""

from datetime import date
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from wuwei import memory

ROOT = Path(__file__).resolve().parents[1]


def workspace(tmp_path, monkeypatch, config=''):
    (tmp_path / '.wuwei/memory/notes').mkdir(parents=True)
    (tmp_path / '.wuwei/config.toml').write_text(config)
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T12:00:00+02:00')
    return tmp_path


def note(root, slug='topic', summary='Current', body='Body', created=None):
    path = root / '.wuwei/memory/notes' / f'{slug}.md'
    created_line = f'created: {created}\n' if created else ''
    path.write_text(f'---\ntype: reference\nsummary: {summary}\naliases: []\nstatus: active\n{created_line}---\n{body}\n')
    return path


def test_stale_summary_uses_latest_body_date(tmp_path, monkeypatch):
    root = workspace(tmp_path, monkeypatch)
    note(root, summary='Current as of 2026-09-20', body='2026-09-21 revised')
    assert any('stale summary' in finding for finding in memory.lint(root))
    note(root, summary='Current as of 2026-09-21', body='2026-09-20 old')
    assert memory.lint(root) == []


def test_line_cap_default_and_override(tmp_path, monkeypatch):
    root = workspace(tmp_path, monkeypatch)
    note(root, body='\n'.join(['line'] * 74))
    assert memory.lint(root) == []
    note(root, body='\n'.join(['line'] * 75))
    assert any('line cap' in finding for finding in memory.lint(root))
    (root / '.wuwei/config.toml').write_text('[memory]\nnote_line_cap = 90\n')
    assert memory.lint(root) == []


def test_state_note_reports_four_dated_entries(tmp_path, monkeypatch):
    root = workspace(tmp_path, monkeypatch)
    note(root, 'project-state', body='\n'.join(f'## 2026-09-{day:02d} update' for day in range(20, 24)))
    assert any('dated entries' in finding for finding in memory.lint(root))
    note(root, 'project-state', body='\n'.join(f'## 2026-09-{day:02d} update' for day in range(20, 23)))
    assert memory.lint(root) == []


def test_raw_intake_needs_outbound_route(tmp_path, monkeypatch):
    root = workspace(tmp_path, monkeypatch)
    note(root, 'raw-intake', body='An unprocessed observation')
    assert any('unrouted intake' in finding for finding in memory.lint(root))
    note(root, 'raw-intake', body='Routed to [topic](topic.md)')
    assert memory.lint(root) == []
    note(root, 'raw-intake', body='Routed to [[topic]]')
    assert memory.lint(root) == []


def test_promoted_proposal_routes_intake(tmp_path, monkeypatch):
    root = workspace(tmp_path, monkeypatch)
    note(root, 'raw-intake', body='An observation')
    assert any('unrouted intake' in finding for finding in memory.lint(root))
    (root / '.wuwei/memory/ledger.jsonl').write_text(json.dumps({
        'target': 'notes/topic.md', 'action': 'patch',
        'evidence': 'memory/notes/raw-intake.md', 'date': '2026-09-27'
    }) + '\n')
    assert memory.lint(root) == []


def test_never_loaded_after_workday_probation(tmp_path, monkeypatch):
    root = workspace(tmp_path, monkeypatch)
    note(root, created='2026-09-10')
    assert any('archive candidate' in finding for finding in memory.lint(root))
    note(root, created='2026-09-15')
    assert memory.lint(root) == []


def test_read_trace_clears_archive_candidate(tmp_path, monkeypatch):
    root = workspace(tmp_path, monkeypatch)
    path = note(root, created='2026-09-10')
    day = root / '.wuwei/days/2026-09-25'
    day.mkdir(parents=True)
    span = {'resourceSpans': [{'scopeSpans': [{'spans': [{'attributes': [
        {'key': 'gen_ai.tool.name', 'value': {'stringValue': 'Read'}},
        {'key': 'gen_ai.tool.arguments', 'value': {'stringValue': json.dumps({'file_path': str(path)})}},
        {'key': 'gen_ai.agent.name', 'value': {'stringValue': 'builder'}},
    ]}]}]}]}
    (day / 'traces.jsonl').write_text(json.dumps(span) + '\n')
    assert memory.lint(root) == []


def test_bad_trace_fails_closed(tmp_path, monkeypatch):
    root = workspace(tmp_path, monkeypatch)
    note(root, created='2026-09-10')
    day = root / '.wuwei/days/2026-09-25'
    day.mkdir(parents=True)
    (day / 'traces.jsonl').write_text('{bad\n')
    with pytest.raises(ValueError, match='traces.jsonl'):
        memory.lint(root)


def test_cli_three_state_exits(tmp_path, monkeypatch):
    root = workspace(tmp_path, monkeypatch)

    def run():
        return subprocess.run([sys.executable, '-P', '-m', 'wuwei', 'memory', 'lint'],
                              env={**os.environ, 'PYTHONPATH': str(ROOT / 'cli'),
                                   'WUWEI_WORKSPACE': str(root), 'WUWEI_NOW': '2026-09-28T12:00:00+02:00'},
                              capture_output=True, text=True)

    clean = run()
    assert clean.returncode == 0, clean.stderr
    note(root, summary='As of 2026-09-20', body='2026-09-21 changed')
    finding = run()
    assert finding.returncode == 1, finding.stderr
    assert 'stale summary' in finding.stdout
    (root / '.wuwei/config.toml').unlink()
    unreadable = run()
    assert unreadable.returncode == 2
    assert 'config.toml' in unreadable.stderr


def test_state_entry_cap_override(tmp_path, monkeypatch):
    root = workspace(tmp_path, monkeypatch, '[memory]\nstate_entry_cap = 2\n')
    note(root, 'state', body='2026-09-20 first\n2026-09-21 second\n2026-09-22 third')
    assert any('dated entries' in finding for finding in memory.lint(root))


def test_malformed_note_and_ledger_fail_closed(tmp_path, monkeypatch):
    root = workspace(tmp_path, monkeypatch)
    path = note(root, 'raw-intake')
    path.write_text('not a note')
    with pytest.raises(ValueError, match='frontmatter'):
        memory.lint(root)
    note(root, 'raw-intake')
    (root / '.wuwei/memory/ledger.jsonl').write_text('{bad\n')
    with pytest.raises(ValueError):
        memory.lint(root)


def test_archived_note_is_not_linted(tmp_path, monkeypatch):
    root = workspace(tmp_path, monkeypatch)
    path = note(root, 'raw-intake', summary='As of 2026-09-20',
                body='2026-09-21 changed', created='2026-09-10')
    path.write_text(path.read_text().replace('status: active', 'status: archived'))
    assert memory.lint(root) == []
