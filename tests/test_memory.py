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
    memory.mkdir(parents=True)
    (memory / 'spine.md').write_text('# Spine\n')
    (tmp_path / '.wuwei/config.toml').write_text('')
    return tmp_path


def test_index_sorted_and_stable(tmp_path):
    root = workspace(tmp_path)
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
    assert before.decode().splitlines() == ['2026-09-26 | no report', '2026-09-27 | Yesterday']
    assert cli(root, 'index').returncode == 0
    assert index.read_bytes() == before


def test_payload_content_size_and_missing_source(tmp_path):
    root = workspace(tmp_path)
    (root / '.wuwei/memory/index.md').write_text('2026-09-27 | Summary\n')
    day = root / '.wuwei/days/2026-09-28'
    day.mkdir(parents=True)
    (day / 'state.json').write_text('{"cap": 2}')
    result = cli(root, 'payload')
    assert result.returncode == 0, result.stderr
    assert '# Spine' in result.stdout
    assert '2026-09-27 | Summary' in result.stdout
    assert 'Full day state: wuwei why <item>' in result.stdout and '"cap": 2' not in result.stdout
    content, size = result.stdout.rsplit('Size: ', 1)
    assert size == f'{len(content.encode())} bytes, {(len(content) + 3) // 4} estimated tokens\n'
    (root / '.wuwei/memory/index.md').unlink()
    result = cli(root, 'payload')
    assert result.returncode == 2
    assert 'index.md' in result.stderr


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


def test_payload_has_empty_promote_line(tmp_path):
    root = workspace(tmp_path)
    (root / '.wuwei/memory/index.md').write_text('')
    result = cli(root, 'payload')
    assert result.returncode == 0, result.stderr
    assert 'Last promote: none' in result.stdout


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


GOALS = ('# Goals\n\n## G-1\noutcome: Ship checkout v2\nmeasure: orders\ntarget: 3\n'
         'date: 2026-10-30\npriority: 1\n')


@pytest.mark.parametrize('case', ['full', 'bad goals', 'empty'])
def test_payload_opens_with_active_constraints(tmp_path, monkeypatch, case):
    from wuwei import memory, state
    monkeypatch.setenv('WUWEI_NOW', NOW)
    root = workspace(tmp_path)
    (root / '.wuwei/memory/index.md').write_text('')
    (root / '.wuwei/memory/goals.md').write_text('## nope\n' if case == 'bad goals' else GOALS)
    day = root / '.wuwei/days/2026-09-28'
    day.mkdir(parents=True)
    (day / 'plan.md').write_text('# Plan\n')
    running, stopped = (f'.wuwei/days/2026-09-28/briefs/{name}.md' for name in ('b1', 'b2'))

    def seed(data):
        if case == 'empty':
            return
        data.update(goals=['G-1'], gate_approved=True, approved_items=['ITEM-1'],
                    seats={'b1': {'item': 'ITEM-1', 'brief': running, 'status': 'running'},
                           'b2': {'item': 'ITEM-2', 'brief': stopped, 'status': 'stopped'},
                           # #676: an adhoc seat has no brief, so it is not a current brief
                           'adhoc-1': {'item': 'adhoc-1', 'role': 'adhoc', 'status': 'running'}},
                    builds={'ITEM-3': {'status': 'check', 'runtime': 'codex', 'brief': 'c3.md'},
                            'ITEM-4': {'status': 'merged', 'brief': 'c4.md'}},
                    decision_routes={'D-1': {}, 'D-2': {}},
                    decision_outcomes={'D-2': {'option': 'A', 'decided_by': 'owner'}})
    state._write_state(seed, root)
    content, size, _ = memory.session_payload(root)
    assert content.startswith('Rules:\nSpine:') and 'Active constraints:' not in content
    assert size == len(content.encode('utf-8'))
    content = memory.constraints(root, state.read_state(root))
    assert content.startswith('Active constraints:\n')
    if case == 'full':
        assert 'Goals: G-1 Ship checkout v2 (target 3 by 2026-10-30)' in content
        assert 'Plan: .wuwei/days/2026-09-28/plan.md (approved: ITEM-1)' in content
        assert 'Open decisions' not in content  # part 14: no decision record is open
        assert f'Current briefs: ITEM-1 b1 {running}; ITEM-3 build c3.md\n' in content
        assert stopped not in content
    elif case == 'bad goals':
        assert 'Goals: unmeasured: goals line 1' in content
    else:
        assert 'Goals: none\n' in content and 'Plan: not approved\n' in content
        assert 'Open decisions' not in content and 'Current briefs: none\n' in content


def tiered(tmp_path, budget=None):
    root = workspace(tmp_path)
    if budget:
        (root / '.wuwei/config.toml').write_text(f'[memory]\nbudget_tokens = {budget}\n')
    # A note line an older index still holds is not loaded.
    (root / '.wuwei/memory/index.md').write_text(
        'retry | reference | Retry policy | 10 tokens\n2026-09-27 | # Report one\n')
    return root


def test_payload_loads_rules_then_today(tmp_path, monkeypatch):
    from wuwei import memory
    monkeypatch.setenv('WUWEI_NOW', NOW)
    content, _, _ = memory.session_payload(tiered(tmp_path))
    assert content == ('Rules:\nSpine:\n# Spine\n\n'
                       'Today:\n2026-09-27 | # Report one\nFull day state: wuwei why <item>\nLast promote: none\n')


def test_payload_over_budget_leaves_today_out(tmp_path, monkeypatch):
    from wuwei import memory
    monkeypatch.setenv('WUWEI_NOW', NOW)
    content, size, tokens = memory.session_payload(tiered(tmp_path, budget=20))
    assert 'Today:' not in content and '2026-09-27 |' not in content and 'retry |' not in content
    assert content == ('Rules:\nSpine:\n# Spine\n\nMemory budget: 27 of 20 estimated tokens; '
                       'today left out (wuwei why <item>).\n')
    assert size == len(content.encode()) and tokens == memory.estimated_tokens(content)


def test_session_start_names_the_spine_over_budget(tmp_path, monkeypatch):
    from wuwei.guards import lifecycle
    monkeypatch.setenv('WUWEI_NOW', NOW)
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    root = tiered(tmp_path, budget=5)
    code, text = lifecycle.session_start({'cwd': str(root), 'hook_event_name': 'SessionStart'})
    assert code >= 1
    assert 'memory: the payload exceeds memory.budget_tokens (' in text
    assert '; shorten .wuwei/memory/spine.md' in text
    assert 'consolidate' not in text


BLOCK = '''<!-- wuwei:memory:start -->
## WUWEI rules

Generated by wuwei memory export from the workspace charters.
Change them through wuwei promote; edits here are overwritten.

### builder
- Run the fast checks before the gate.

### planner
- Do not carry parked items.
<!-- wuwei:memory:end -->
'''


def exporting(tmp_path, export_to=None):
    root = workspace(tmp_path)
    if export_to:
        (root / '.wuwei/config.toml').write_text(f'[memory]\nexport_to = "{export_to}"\n')
    charters = root / '.wuwei/charters'
    charters.mkdir()
    (charters / 'builder.md').write_text('# Builder\n- Run the fast checks before the gate.\n')
    (charters / 'planner.md').write_text('- Do not carry parked items.\n')
    (charters / 'lead.md').write_text('# Lead, no rules\n')
    return root


def test_export_writes_one_marked_block_and_keeps_other_text(tmp_path):
    from wuwei import memory
    root = exporting(tmp_path)
    path, changed = memory.export(root)
    assert path == root / 'CLAUDE.md' and changed and path.read_text() == BLOCK
    path.write_text('# Mine\n\n' + BLOCK.replace('parked', 'old') + '\nAfter.\n')
    assert memory.export(root) == (path, True)
    assert path.read_text() == '# Mine\n\n' + BLOCK + '\nAfter.\n'
    before = path.stat().st_mtime_ns
    assert memory.export(root) == (path, False) and path.stat().st_mtime_ns == before
    path.write_text('# Mine\n')
    memory.export(root)
    assert path.read_text() == '# Mine\n\n' + BLOCK


def test_export_refuses_unsafe_targets_and_broken_markers(tmp_path, tmp_path_factory):
    from wuwei import memory
    for target in ('/etc/claude.md', '../CLAUDE.md', '.wuwei/CLAUDE.md', 'linked/CLAUDE.md'):
        root = exporting(tmp_path_factory.mktemp('ws'), target)
        (root / 'linked').symlink_to(tmp_path_factory.mktemp('elsewhere'))
        with pytest.raises(ValueError):
            memory.export(root)
        assert not (root / '.wuwei/CLAUDE.md').exists() and not list((root / 'linked').iterdir())
    root = exporting(tmp_path)
    (root / 'CLAUDE.md').write_text('<!-- wuwei:memory:start -->\nno end\n')
    with pytest.raises(ValueError):
        memory.export(root)


OTHER = '<!-- other:start -->\nOther block.\n<!-- other:end -->\n'


def test_write_block_keeps_the_rules_block_and_owner_text(tmp_path, tmp_path_factory):
    from wuwei import memory
    root = exporting(tmp_path)
    path = root / 'CLAUDE.md'
    path.write_text('# Mine\n\n' + BLOCK)
    write = lambda block, **kw: memory.write_block(root, '<!-- other:start -->', '<!-- other:end -->',
                                                   block, 'bin/wuwei fix-it', **kw)
    assert write(OTHER, write=False) == (path, True) and path.read_text() == '# Mine\n\n' + BLOCK
    assert write(OTHER) == (path, True)
    assert path.read_text() == '# Mine\n\n' + BLOCK + '\n' + OTHER
    before = path.stat().st_mtime_ns
    assert write(OTHER) == (path, False) and path.stat().st_mtime_ns == before
    assert memory.export(root) == (path, False)
    assert write(OTHER.replace('Other', 'New')) == (path, True)
    assert path.read_text() == '# Mine\n\n' + BLOCK + '\n' + OTHER.replace('Other', 'New')
    for damaged in ('<!-- other:start -->\nno end\n', OTHER + OTHER):
        path.write_text(damaged)
        with pytest.raises(ValueError, match='bin/wuwei fix-it'):
            write(OTHER)
    for target in ('/etc/claude.md', '../CLAUDE.md', '.wuwei/CLAUDE.md', 'linked/CLAUDE.md'):
        root = exporting(tmp_path_factory.mktemp('ws'), target)
        (root / 'linked').symlink_to(tmp_path_factory.mktemp('elsewhere'))
        with pytest.raises(ValueError, match='memory.export_to'):
            memory.write_block(root, '<!-- other:start -->', '<!-- other:end -->', OTHER, 'x')
        assert not (root / '.wuwei/CLAUDE.md').exists() and not list((root / 'linked').iterdir())


def command(*argv):
    import argparse
    from wuwei.commands import memory as memory_command
    parser = argparse.ArgumentParser()
    memory_command.register(parser.add_subparsers(dest='command'))
    args = parser.parse_args(['memory', *argv])
    return args.func(args)


def test_memory_export_command(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    root = exporting(tmp_path)
    assert command('export', '--claude') == 0
    assert capsys.readouterr().out == f'export: {root / "CLAUDE.md"} written\n'
    assert command('export', '--claude') == 0
    assert capsys.readouterr().out.endswith('unchanged\n')
    for retired in (['show', '2026-10-01'], ['status'], ['forget', 'F-1', 'keep'], ['lint']):
        with pytest.raises(SystemExit):
            command(*retired)
