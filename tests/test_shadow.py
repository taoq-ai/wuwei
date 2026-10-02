"""Shadow mode (#308): the producer-only event, the report, status and the mode writers."""

import pytest

from wuwei import report, state, workspace
from wuwei.__main__ import main


@pytest.fixture
def root(tmp_path, monkeypatch):
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00Z')
    monkeypatch.chdir(tmp_path)
    return tmp_path


def refused(root, guard, target, day='2026-09-29'):
    state.append_event('guard.would_refuse', {'guard': guard, 'reason': 'refused', 'target': target,
                                              'session': 's', 'item': None},
                       directory=root / '.wuwei/days' / day)


def test_would_refuse_is_producer_only(root, capsys):
    assert main(['event', 'guard.would_refuse', '{}']) == 1
    assert 'reserved; written by wuwei hook (shadow mode)' in capsys.readouterr().err


def test_shadow_lines_group_and_name_candidates(root):
    days = root / '.wuwei/days'
    assert report.shadow_lines([days / '2026-09-28', days / '2026-09-29']) == []
    for target in ('git push --force origin a', 'git push --force origin b'):
        refused(root, 'commit_push', target, '2026-09-28')
    refused(root, 'pr', 'gh pr create --fill', '2026-09-28')
    refused(root, 'commit_push', 'git push origin x')
    for target in ('git push --force origin c', 'git  push --force'):
        refused(root, 'commit_push', target)
    directories = [days / '2026-09-28', days / '2026-09-29']
    assert report.shadow_lines(directories) == [
        '- commit_push: 5 (git push --force: 4, git push origin: 1)',
        '- pr: 1 (gh pr create: 1)',
        '',
        'Candidates for a guard fix or a calibration proposal:',
        '- commit_push: git push --force (4 times, no later incident)',
    ]
    state.append_event('base.red', {}, directory=days / '2026-09-29')
    assert report.shadow_lines(directories)[-1] == 'none'


def test_shadow_candidates_need_more_than_three_and_no_later_page(root):
    days = root / '.wuwei/days'
    state.append_event('base.red', {}, directory=days / '2026-09-29')
    for _ in range(3):
        refused(root, 'pr', 'gh pr merge 1')
    assert report.shadow_lines([days / '2026-09-29'])[-1] == 'none'
    refused(root, 'pr', 'gh pr merge 2')
    assert report.shadow_lines([days / '2026-09-29'])[-1] == '- pr: gh pr merge (4 times, no later incident)'
    for form in ('a', 'b', 'c', 'd'):
        refused(root, 'pr', f'gh {form}')
    assert report.shadow_lines([days / '2026-09-29'])[0] == (
        '- pr: 8 (gh pr merge: 4, gh a: 1, gh b: 1)')


def test_shadow_report_command(root, capsys, tmp_path_factory, monkeypatch):
    assert main(['shadow', 'report']) == 0
    assert capsys.readouterr().out == '# WUWEI shadow report\n\nnone\n'
    refused(root, 'pr', 'gh pr merge 1', '2026-09-28')
    refused(root, 'commit_push', 'git push --force')
    assert main(['shadow', 'report']) == 0
    assert '- pr: 1' in capsys.readouterr().out
    (root / '.wuwei/config.toml').write_text('[guards]\nmode = "shadow"\nshadow_since = "2026-09-29"\n')
    assert main(['shadow', 'report']) == 0
    out = capsys.readouterr().out
    assert '- commit_push: 1' in out and '- pr:' not in out
    (root / '.wuwei/days/2026-09-29/events.jsonl').chmod(0o644)
    with (root / '.wuwei/days/2026-09-29/events.jsonl').open('a') as events:
        events.write('not json\n')
    assert main(['shadow', 'report']) == 2
    outside = tmp_path_factory.mktemp('outside')
    monkeypatch.delenv('WUWEI_WORKSPACE')
    monkeypatch.chdir(outside)
    assert main(['shadow', 'report']) == 2


@pytest.mark.parametrize('config,shadow,nudged', [
    ('', False, False),
    ('mode = "enforce"\nshadow_since = "2026-09-22"', False, False),
    ('mode = "shadow"', True, False),
    ('mode = "shadow"\nshadow_since = "2026-09-23"', True, False),
    ('mode = "shadow"\nshadow_since = "2026-09-22"', True, True),
    ('mode = "shadow"\nshadow_days = 3\nshadow_since = "2026-09-25"', True, True),
])
def test_status_shows_shadow_and_nudges_once(root, config, shadow, nudged):
    from wuwei.commands import status
    (root / '.wuwei/config.toml').write_text(f'[guards]\n{config}\n')
    state._write_state(lambda data: None, root, reserved=False)
    directory = workspace.day_dir(root)
    data = status.snapshot(directory)
    assert data['shadow'] is shadow
    assert (' | shadow' in status.line(data)) is shadow
    rows = [row for row in status.attention(directory) if row['source'] == 'guards.shadow']
    assert data['nudges'] == len(rows) == int(nudged)
    if nudged:
        assert rows[0]['tier'] == 'nudge'
        assert 'guards.mode = "enforce"' in rows[0]['reason'] and 'guards.shadow_days' in rows[0]['reason']


@pytest.mark.parametrize('mode', ['enforce', 'shadow'])
def test_session_start_says_shadow_mode_is_on(root, mode):
    from wuwei.guards import lifecycle
    (root / '.wuwei/config.toml').write_text(f'[guards]\nmode = "{mode}"\n')
    message = lifecycle.session_start({'cwd': str(root)})[1]
    assert ('Shadow mode is on' in message and 'bin/wuwei shadow report' in message) is (mode == 'shadow')
