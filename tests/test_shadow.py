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


@pytest.mark.parametrize('argv', [['shadow', 'report'], ['cruise', 'budget']])
def test_the_retired_commands_are_unknown(root, argv):
    # #814: the day report's ## Shadow section replaces shadow report; cruise is gone.
    with pytest.raises(SystemExit) as exit_:
        main(argv)
    assert exit_.value.code == 2


OBSERVE = '[security]\nposture = "observe"\n'


@pytest.mark.parametrize('config,posture', [
    ('', 'guarded'),
    ('[security]\nposture = "strict"\n[guards]\nshadow_since = "2026-09-22"', 'strict'),
    ('[guards]\nmode = "enforce"\nshadow_since = "2026-09-22"', 'guarded'),
    (OBSERVE, 'observe'),
    (OBSERVE + '[guards]\nshadow_since = "2026-09-23"', 'observe'),
    (OBSERVE + '[guards]\nshadow_since = "2026-09-22"', 'observe'),
    (OBSERVE + '[guards]\nshadow_days = 3\nshadow_since = "2026-09-25"', 'observe'),
    # The deprecated #308 form is observe.
    ('[guards]\nmode = "shadow"\nshadow_since = "2026-09-22"', 'observe'),
])
def test_status_shows_posture(root, config, posture):
    from wuwei.commands import status
    (root / '.wuwei/config.toml').write_text(config)
    state._write_state(lambda data: None, root, reserved=False)
    directory = workspace.day_dir(root)
    data = status.snapshot(directory)
    assert data['posture'] == posture
    for name in ('observe', 'strict'):
        assert (f' · {name}' in status.line(data)) is (name == posture)
    assert 'guarded' not in status.line(data)
    assert not [row for row in status.attention(directory) if row['source'] == 'guards.shadow']


@pytest.mark.parametrize('config,on', [('', False), ('[guards]\nmode = "shadow"\n', True), (OBSERVE, True),
                                       ('[security]\nposture = "strict"\n', False)])
def test_session_start_says_observe_is_on(root, config, on):
    from wuwei.guards import lifecycle
    (root / '.wuwei/config.toml').write_text(config)
    message = lifecycle.session_start({'cwd': str(root)})[1]
    assert ('Observe posture is on' in message and '## Shadow section' in message) is on
