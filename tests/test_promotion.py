"""Proposal promotion and adherence contracts."""

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


def test_add_patch_and_archive_land(tmp_path):
    base = setup(tmp_path)
    proposal(base)
    assert cli(tmp_path, 'promote').returncode == 0
    assert (base / 'charters/builder.md').read_text().endswith('Check tests before review.\n')
    assert ledger(base)[0]['status'] == 'landed'
    proposal(base, 'two', action='patch', old_text='Check tests before review.',
             text='Check tests and lint before review.')
    assert cli(tmp_path, 'promote').returncode == 0
    assert (base / 'charters/builder.md').read_text().endswith('Check tests and lint before review.\n')
    note = base / 'memory/notes/old.md'
    note.write_text('---\ntype: reference\nsummary: Old\naliases: []\nstatus: active\ncreated: 2026-09-01\n---\nOld fact\n')
    proposal(base, 'three', target='.wuwei/memory/notes/old.md', action='archive', text='')
    assert cli(tmp_path, 'promote').returncode == 0
    assert not note.exists()
    assert (base / 'memory/archive/old.md').exists()


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


def test_missing_evidence_and_missing_fold_survivor_rejected(tmp_path):
    base = setup(tmp_path)
    proposal(base, evidence='.wuwei/days/' + DAY + '/missing.md')
    assert cli(tmp_path, 'promote').returncode == 1
    assert 'evidence' in ledger(base)[0]['reason']
    (base / 'memory/notes/old.md').write_text('---\ntype: reference\nsummary: Old\naliases: []\nstatus: active\ncreated: 2026-09-01\n---\nBody\n')
    proposal(base, target='.wuwei/memory/notes/old.md', action='fold',
             survivor='.wuwei/memory/notes/absent.md')
    assert cli(tmp_path, 'promote').returncode == 1
    assert 'survivor' in ledger(base)[1]['reason']


def test_payload_groups_last_run(tmp_path):
    base = setup(tmp_path)
    assert 'Last promote: none' in cli(tmp_path, 'payload').stdout
    proposal(base)
    proposal(base, 'two', target='charters/plugin.md')
    assert cli(tmp_path, 'promote').returncode == 1
    payload = cli(tmp_path, 'payload')
    assert payload.returncode == 0
    assert 'Last promote 2026-09-28: landed 1 (.wuwei/charters/builder.md); rejected 1 (charters/plugin.md:' in payload.stdout


def test_consolidate_lists_unloaded_note_past_probation(tmp_path):
    base = setup(tmp_path)
    (base / 'memory/notes/old.md').write_text('---\ntype: reference\nsummary: Old\naliases: []\nstatus: active\ncreated: 2026-09-01\n---\nBody\n')
    result = cli(tmp_path, 'consolidate')
    assert result.returncode == 1, result.stderr
    assert 'old' in result.stdout and 'archive candidate' in result.stdout


def test_note_add_refuses_symlinked_wuwei(tmp_path):
    outside = tmp_path / 'outside'
    setup(outside)
    root = tmp_path / 'workspace'
    root.mkdir()
    (root / '.wuwei').symlink_to(outside / '.wuwei', target_is_directory=True)
    result = cli(root, 'note', 'add', 'unsafe', '--type', 'hub', '--summary', 'Unsafe')
    assert result.returncode == 2
    assert not (outside / '.wuwei/memory/notes/unsafe.md').exists()


def test_trace_load_prevents_idle_candidate_and_capacity_ranks(tmp_path):
    base = setup(tmp_path)
    for slug in ('read', 'idle', 'new'):
        created = '2026-09-27' if slug == 'new' else '2026-09-01'
        (base / 'memory/notes' / (slug + '.md')).write_text(
            f'---\ntype: reference\nsummary: {slug}\naliases: []\nstatus: active\ncreated: {created}\n---\nBody\n')
    (base / 'config.toml').write_text('[memory]\nmax_notes = 1\n')
    trace = {'resourceSpans': [{'scopeSpans': [{'spans': [{'attributes': [
        {'key': 'gen_ai.tool.name', 'value': {'stringValue': 'Read'}},
        {'key': 'gen_ai.tool.arguments', 'value': {'stringValue': json.dumps(
            {'file_path': '.wuwei/memory/notes/read.md'})}},
    ]}]}]}]}
    (base / 'days' / DAY / 'traces.jsonl').write_text(json.dumps(trace) + '\n')
    result = cli(tmp_path, 'consolidate')
    assert result.returncode == 1, result.stderr
    assert 'idle: archive candidate (0 loads)' in result.stdout
    assert 'read: archive candidate' in result.stdout
    assert 'new:' not in result.stdout


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


def test_state_set_refuses_symlinked_wuwei(tmp_path):
    outside = tmp_path / 'outside'
    setup(outside)
    root = tmp_path / 'workspace'
    root.mkdir()
    (root / '.wuwei').symlink_to(outside / '.wuwei', target_is_directory=True)
    result = cli(root, 'state', 'set', 'probe', 'true')
    assert result.returncode == 2
    assert not (outside / '.wuwei/days' / DAY / 'state.json').exists()


def test_memory_writes_are_reserved_for_dedicated_cli(tmp_path, monkeypatch):
    base = setup(tmp_path)
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    from wuwei.guards.protect_state import check_file
    for path in ('.wuwei/memory/ledger.jsonl', '.wuwei/memory/notes/old.md',
                 '.wuwei/charters/builder.md', '.wuwei/days/2026-09-28/traces.jsonl'):
        payload = {'cwd': str(tmp_path), 'tool_input': {'file_path': path}}
        code, _ = check_file(payload)
        assert code == 1, path


def test_guard_refusal_event_kind_cannot_be_forged(tmp_path):
    setup(tmp_path)
    result = cli(tmp_path, 'event', 'hook.refusal', '{}')
    assert result.returncode == 1
    assert not (tmp_path / '.wuwei/days' / DAY / 'events.jsonl').exists()


def test_guard_refusals_are_counted_from_events(tmp_path, monkeypatch, capsys):
    setup(tmp_path)
    monkeypatch.setenv('WUWEI_NOW', DAY + 'T12:00:00+02:00')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    from wuwei.commands.hook import refuse
    from wuwei.promotion import adherence_counts
    assert refuse('PreToolUse', 'deploy: refused by rule', cwd=tmp_path) == 2
    assert adherence_counts(tmp_path)['guard_refusals'] == {'deploy: refused by rule': 1}


def test_new_note_cannot_be_archived_during_probation(tmp_path):
    base = setup(tmp_path)
    note = base / 'memory/notes/new.md'
    note.write_text('---\ntype: reference\nsummary: New\naliases: []\nstatus: active\ncreated: 2026-09-27\n---\nBody\n')
    proposal(base, target='.wuwei/memory/notes/new.md', action='archive')
    assert cli(tmp_path, 'promote').returncode == 1
    assert 'probation' in ledger(base)[0]['reason']
    assert note.exists()


def test_malformed_proposal_is_rejected_and_logged(tmp_path):
    base = setup(tmp_path)
    (base / 'days' / DAY / 'proposals/one.json').write_text('[]')
    assert cli(tmp_path, 'promote').returncode == 1
    assert ledger(base)[0]['status'] == 'rejected'


def test_external_read_does_not_count_as_workspace_note_load(tmp_path):
    base = setup(tmp_path)
    (base / 'memory/notes/old.md').write_text('---\ntype: reference\nsummary: Old\naliases: []\nstatus: active\ncreated: 2026-09-01\n---\nBody\n')
    trace = {'resourceSpans': [{'scopeSpans': [{'spans': [{'attributes': [
        {'key': 'gen_ai.tool.name', 'value': {'stringValue': 'Read'}},
        {'key': 'gen_ai.tool.arguments', 'value': {'stringValue': json.dumps(
            {'file_path': '/outside/memory/notes/old.md'})}},
    ]}]}]}]}
    (base / 'days' / DAY / 'traces.jsonl').write_text(json.dumps(trace) + '\n')
    assert 'old: archive candidate (0 loads)' in cli(tmp_path, 'consolidate').stdout


def test_capacity_uses_load_rate_not_absolute_load_count(tmp_path):
    base = setup(tmp_path)
    (base / 'config.toml').write_text('[memory]\nmax_notes = 1\n')
    for slug, created in (('old', '2026-08-01'), ('recent', '2026-09-10')):
        (base / 'memory/notes' / (slug + '.md')).write_text(
            f'---\ntype: reference\nsummary: {slug}\naliases: []\nstatus: active\ncreated: {created}\n---\nBody\n')
    spans = []
    for slug in ('old', 'old', 'recent'):
        spans.append({'attributes': [
            {'key': 'gen_ai.tool.name', 'value': {'stringValue': 'Read'}},
            {'key': 'gen_ai.tool.arguments', 'value': {'stringValue': json.dumps(
                {'file_path': '.wuwei/memory/notes/' + slug + '.md'})}},
        ]})
    trace = {'resourceSpans': [{'scopeSpans': [{'spans': spans}]}]}
    (base / 'days' / DAY / 'traces.jsonl').write_text(json.dumps(trace) + '\n')
    result = cli(tmp_path, 'consolidate')
    assert result.returncode == 1, result.stderr
    assert 'old: archive candidate' in result.stdout
    assert 'recent: archive candidate' not in result.stdout
