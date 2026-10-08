"""#551: the hook-routed day driven only by wuwei next --json; the planner never picks the order."""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
import shlex
import sys
import time

import pytest

from wuwei import metrics, workspace
from wuwei.__main__ import main


@pytest.fixture
def day(tmp_path, monkeypatch):
    from fakes.day import Day
    day = Day(tmp_path / 'workspace', monkeypatch, solo=True)
    monkeypatch.setenv('WUWEI_SESSION_ID', 'planner')
    (day.root / '.wuwei/calibration.json').write_text('{"acme/widget": {"date": "2026-09-29"}}\n')

    def worktree(repo, branch, path, root, vcs, identity=None, existing=False):
        # The VCS boundary: the item worktree is the fixture repository the fakes check.
        path.parent.mkdir(exist_ok=True)
        path.symlink_to(day.repo)
        return {'path': str(path), 'branch': branch}
    monkeypatch.setattr(workspace, 'create_worktree', worktree)
    # Not the first day: the calibration questions were asked on an earlier one.
    (day.root / '.wuwei/days/2026-09-28').mkdir(parents=True)
    return day


def call(day, argv, stdin=''):
    out, err = io.StringIO(), io.StringIO()
    with day.patch.context() as patch, redirect_stdout(out), redirect_stderr(err):
        patch.setattr(sys, 'stdin', io.StringIO(stdin))
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


def bash(day, command):
    """The planner's Bash call: PreToolUse, the command, then the PostToolUse span."""
    argv = shlex.split(command)
    assert argv[0] == 'wuwei', command
    day.bash(argv[1:])
    code, out, err = call(day, argv[1:])
    assert code in (0, 1), (command, code, out, err)
    day.hook('PostToolUse', tool_name='Bash', tool_input={'command': command})
    return out


def launch(day, action):
    if action['agent_type'].startswith('wuwei:sentinel-'):
        # Quality asks for one fix in the initial round; every other verdict passes.
        initial = action['action'] == 'launch'
        if not initial:  # #567: a light fix is re-read by the same seat, never a delta review
            light = day.data['items']['A']['gates']['tier'] == 'light'
            assert action['feedback'].startswith('Re-read:' if light else 'Delta review:'), action
        day.runtime.verdict = 'FIX' if initial and action['agent_type'] == 'wuwei:sentinel-quality' else 'PASS'
    day.execute(action)


@pytest.mark.parametrize('looks,tier', [(1, 'standard'), (2, 'standard'), (1, 'light')])
def test_the_day_closes_walking_only_next(day, looks, tier):
    if tier == 'light':  # #567: the repository floor and the lead allow light
        from functools import partial
        with (day.root / '.wuwei/config.toml').open('a') as config:
            config.write('[repos.gates]\nfloor = "light"\n')
        day.proposal = partial(day.proposal, tier='light')
        day.runtime.spec = False  # no spec engine at light (#280)
    # looks 2: the planner asks next again before each action; asking is not doing (#551 review).
    started, asks, merged = time.monotonic(), 0, False
    for _ in range(80):
        for _ in range(looks):
            action = json.loads(bash(day, 'wuwei next --json'))
        kind = action['action']
        if kind == 'done':
            break
        assert kind != 'card' or action.get('widget'), action  # an owner-only card stops the day
        if kind in ('run', 'check'):
            bash(day, action['command'])
        elif kind in ('launch', 'continue'):
            launch(day, action)
            if action['state'] == 'lead':  # its then: save the lead's JSON answer with Write
                (day.directory / 'lead.json').write_text(json.dumps(day.proposal(['A'])))
        elif kind == 'card':
            for widget in action['widget']:
                bash(day, widget['record'].replace('<label>', widget['options'][0]['label']))
                day.hook('PostToolUse', tool_name='AskUserQuestion', tool_input={'questions': [widget]})
                asks += 1
        elif kind in ('set', 'gates'):
            for entry in action.get('entries', [action]):
                for command in entry.get('commands', []):
                    bash(day, command)
                for seat in entry.get('seats', []) + ([entry] if entry.get('agent_type') else []):
                    launch(day, seat)
        else:
            assert kind == 'wait', action
        if action['state'] == 'pr' and not merged:
            # The code host merges; the watch records it with pr state.
            day.host.results['pr'].data.update(state='closed', merged=True,
                                               merged_at='2026-09-29T12:00:00Z', merge_commit=day.head)
            assert call(day, ['pr', 'state'])[0] == 0
            merged = True
        # The turn ends; a Stop the close guard blocks is the guard doing its job.
        call(day, ['hook', 'Stop'], json.dumps({
            'session_id': 'planner', 'cwd': str(day.root), 'hook_event_name': 'Stop',
            'transcript_path': str(day.root / 'planner.jsonl'), 'stop_hook_active': False}))
    else:
        pytest.fail(f'the day did not close: {action}')
    assert day.data['items']['A']['phase'] == 'merged'
    assert any(row['kind'] == 'day.closed' for row in day.events)
    assert (day.directory / 'report.md').is_file()
    assert (day.directory / 'retro' / f'{day.directory.name}.md').is_file()
    for command in (('doctor', '--section', 'pr-flow'), ('mcp', 'check'), ('promote',)):
        assert command in day.calls, command
    value = metrics.collect(day.root)
    assert value['off_path'] == 0, metrics.path(metrics._events(day.directory),
                                                metrics._traces(day.directory), 'planner')
    assert value['planner_asks'] == asks and value['planner_turns'] > 0
    assert value['cycle_minutes']['A'] >= 0
    assert value['cycle_by_tier'][tier]['median_minutes'] < metrics.CYCLE_TARGETS[tier]
    assert day.data['items']['A']['gates']['tier'] == tier
    builder = next(row['payload']['path'] for row in day.events if row['kind'] == 'brief written'
                   and row['payload']['role'] == 'builder')
    assert f'Depth: {tier};' in (day.root / builder).read_text()
    assert time.monotonic() - started < 60
