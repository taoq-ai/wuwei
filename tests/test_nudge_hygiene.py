"""Issue 786: nudges expire, repeats combine on their subject and the list is capped."""

from datetime import datetime, timedelta
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
NOW = '2026-09-28T12:00:00+02:00'
ALL = '[nudges]\nmode = "all"\n'


def at(minutes):
    """The timestamp this many minutes before NOW."""
    return (datetime.fromisoformat(NOW) - timedelta(minutes=minutes)).isoformat()


def day(root, monkeypatch, events=(), text=ALL, state_data=None, raw=''):
    monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
    monkeypatch.setenv('WUWEI_NOW', NOW)
    directory = root / '.wuwei/days/2026-09-28'
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'state.json').write_text(json.dumps({'cap': 1, 'items': {}, **(state_data or {})}))
    (directory / 'events.jsonl').write_text(raw + ''.join(json.dumps(e) + '\n' for e in events))
    (root / '.wuwei/config.toml').write_text(text)
    return directory


def read_failed(pr, minutes):
    return {'kind': 'watch: read-failed', 'payload': {'pr': pr, 'reason': 'could not read'}, 'ts': at(minutes)}


def tracker(item, minutes=0, exit=2):
    payload = {'item': item, 'exit': exit} if exit == 0 else {'item': item, 'exit': exit, 'reason': 'label not found'}
    return {'kind': 'tracker.call', 'payload': payload, 'ts': at(minutes)}


def test_settings_have_defaults_and_minimums(tmp_path):
    from wuwei import workspace
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('')
    nudges = workspace.load_config(tmp_path)['nudges']
    assert (nudges['ttl_hours'], nudges['max_open']) == (24, 20)
    for key in ('ttl_hours', 'max_open'):
        (tmp_path / '.wuwei/config.toml').write_text(f'[nudges]\n{key} = 0\n')
        with pytest.raises(workspace.ConfigError, match=f'nudges.{key}'):
            workspace.load_config(tmp_path)


def test_repeats_fold_into_one_row_per_subject(tmp_path, monkeypatch):
    from wuwei.commands import status
    events = [read_failed('acme/widget#1', minutes) for minutes in range(49, -1, -1)]
    directory = day(tmp_path, monkeypatch, events)
    rows = [row for row in status.attention(directory) if row['source'] == 'watch: read-failed']
    assert [(row['count'], row['ts']) for row in rows] == [(50, at(0))]
    day(tmp_path, monkeypatch, events + [read_failed('acme/widget#2', 30)] * 25)
    rows = [row for row in status.attention(directory) if row['source'] == 'watch: read-failed']
    assert sorted(row['count'] for row in rows) == [25, 50]


def test_a_later_silent_event_clears_its_subject(tmp_path, monkeypatch):
    from wuwei.commands import status
    directory = day(tmp_path, monkeypatch, [tracker('A', 3), tracker('B', 2), tracker('A', 1, exit=0)])
    rows = [row for row in status.attention(directory) if row['source'] == 'tracker.call']
    assert len(rows) == 1 and rows[0]['count'] == 1 and rows[0]['ts'] == at(2)


def test_unreadable_lists_and_pages(tmp_path, monkeypatch):
    from wuwei.commands import status
    warning = {'kind': 'hook.warning', 'payload': {'reason': ['a', 'b']}, 'ts': at(1)}
    finding = {'kind': 'security.finding', 'payload': {}, 'ts': at(1)}
    directory = day(tmp_path, monkeypatch, [{'kind': 'x', 'ts': at(5)}, warning, warning, finding, finding],
                    raw='not json\nnot json\nnot json\n')
    rows = status.attention(directory)
    unreadable = [row for row in rows if row['source'] == 'unreadable event']
    assert [(row['count'], row['ts']) for row in unreadable] == [(3, None)]
    assert [row['count'] for row in rows if row['source'] == 'hook.warning'] == [2]
    assert [row['count'] for row in rows if row['source'] == 'security.finding'] == [1, 1]


def test_counts_that_read_rows_sum_count(tmp_path, monkeypatch):
    from wuwei import workspace
    from wuwei.commands import doctor, status
    gap = {'kind': 'traces.gap', 'payload': {'reason': 'r', 'span': 's', 'session': 's'}, 'ts': at(1)}
    untraced = {'kind': 'subagent.untraced', 'ts': at(1),
                'payload': {'agent_type': 'Explore', 'agent_id': 'a1', 'reason': 'no seat'}}
    directory = day(tmp_path, monkeypatch, [gap] * 3 + [untraced] * 3)
    assert status.snapshot(directory)['trace_gaps'] == 3
    probes = {'state': {'result': 'ok', 'value': 'ok'}, 'planner': {'result': 'ok', 'value': 'ok'},
              'seats': {'result': 'ok', 'value': 'none stuck'}}
    rows = {row['name']: row['value'] for row in doctor._day(tmp_path, workspace.load_config(tmp_path), probes)}
    assert rows['traces'] == '3 gaps today'
    assert rows['untraced subagents'] == '3 stopped with no seat today'


def shown(directory):
    """What the surfaces show: the tidied list (#786 F1)."""
    from wuwei.commands import status
    return status.surfaced(directory, status.attention(directory))[1]


def test_quiet_nudges_expire(tmp_path, monkeypatch):
    from wuwei.commands import status
    gap = {'kind': 'retro.gap', 'payload': {'reason': 'no retro'}, 'ts': at(120)}
    text = ALL + 'ttl_hours = 1\n'
    directory = day(tmp_path, monkeypatch, [gap], text)
    rows = shown(directory)
    assert not [row for row in rows if row['source'] == 'retro.gap']
    dropped, = [row for row in rows if row['source'] == 'nudges.dropped']
    assert (dropped['tier'], dropped['expired'], dropped['dropped']) == ('nudge', 1, 0)
    assert 'nudges.ttl_hours = 1' in dropped['reason']
    day(tmp_path, monkeypatch, [gap, {**gap, 'ts': at(10)}], text)
    rows = shown(directory)
    assert [row['count'] for row in rows if row['source'] == 'retro.gap'] == [2]
    assert not [row for row in rows if row['source'] == 'nudges.dropped']


def test_the_open_list_is_capped(tmp_path, monkeypatch):
    from wuwei.commands import status
    finding = {'kind': 'security.finding', 'payload': {}, 'ts': at(50)}
    calls = [tracker(f'I{number}', 20 - number) for number in range(1, 9)]
    text = ALL + 'max_open = 5\n'
    directory = day(tmp_path, monkeypatch, [finding] + calls, text)
    rows = shown(directory)
    assert [row['source'] for row in rows if row['tier'] == 'page'] == ['security.finding']
    kept = [row['reason'] for row in rows if row['source'] == 'tracker.call']
    assert len(kept) == 4
    assert [row for row in rows if row['source'] == 'tracker.call'] == [
        row for row in rows if row['source'] == 'tracker.call' and row['ts'] in {at(20 - n) for n in (5, 6, 7, 8)}]
    dropped, = [row for row in rows if row['source'] == 'nudges.dropped']
    assert (dropped['dropped'], dropped['expired']) == (4, 0)
    status_line = status.line(status.snapshot(directory, line=True))
    assert 'pages 1' in status_line and 'nudges 5' in status_line
    day(tmp_path, monkeypatch, [finding] + calls[:5], text)
    rows = shown(directory)
    assert len(rows) == 6 and not [row for row in rows if row['source'] == 'nudges.dropped']
    day(tmp_path, monkeypatch, [finding] + calls, text, {'decision_routes': {'D-1': {}}})
    rows = shown(directory)
    nudges = [row for row in rows if row['tier'] == 'nudge']
    assert [row['source'] for row in nudges].count('decision.pending') == 1
    assert {row['ts'] for row in nudges if row['source'] == 'tracker.call'} == {at(20 - n) for n in (6, 7, 8)}
    dropped, = [row for row in rows if row['source'] == 'nudges.dropped']
    assert dropped['dropped'] == 5


def test_nudges_print_count_and_age(tmp_path, monkeypatch, capsys):
    from wuwei.__main__ import main
    from wuwei.commands import nudges, status
    events = [read_failed('acme/widget#1', minutes) for minutes in range(169, 119, -1)]
    directory = day(tmp_path, monkeypatch, events)
    assert main(['nudges', '--all']) == 0
    assert capsys.readouterr().out == 'nudge: could not read (50 times, last 2 h ago). Run: wuwei next\n'
    assert main(['nudges', '--all', '--json']) == 0
    assert capsys.readouterr().out == json.dumps(status.attention(directory)) + '\n'
    day(tmp_path, monkeypatch, [read_failed('acme/widget#1', 7)])
    assert main(['nudges', '--all']) == 0
    assert capsys.readouterr().out == 'nudge: could not read (last 7 min ago). Run: wuwei next\n'
    row = {'tier': 'nudge', 'source': 'build.parked', 'reason': 'A parked'}
    assert nudges.line(row, 1) == 'nudge: A parked. Run: wuwei next'
    day(tmp_path, monkeypatch, [{'kind': 'retro.gap', 'payload': {'reason': 'r'}, 'ts': at(120)}],
        ALL + 'ttl_hours = 1\n')
    assert main(['nudges']) == 0
    assert capsys.readouterr().out == ('nudge: 1 expired after nudges.ttl_hours = 1, '
                                       '0 dropped over nudges.max_open = 20\n')


def test_observe_would_refuse_is_a_shadow_line_not_a_nudge(tmp_path, monkeypatch, capsys):
    # Passes on main before any #786 change: signal.classify makes it silent under observe.
    from wuwei import state
    from wuwei.__main__ import main
    day(tmp_path, monkeypatch, text='[security]\nposture = "observe"\n' + ALL)
    state.append_event('guard.would_refuse', {
        'guard': 'pr', 'area': 'publish', 'level': 'warn', 'posture': 'observe', 'reason': 'refused',
        'exit': 1, 'target': 'gh pr create', 'session': 's', 'item': None}, tmp_path)
    assert main(['nudges', '--all', '--json']) == 0
    assert not [row for row in json.loads(capsys.readouterr().out) if row['source'] == 'guard.would_refuse']
    assert main(['shadow', 'report']) == 0
    assert sum(line.startswith('- pr: 1') for line in capsys.readouterr().out.splitlines()) == 1


def test_configuration_names_the_dropped_row():
    text = (ROOT / 'docs/site/configuration.md').read_text()
    row, = [line for line in text.splitlines() if line.startswith('| `nudges.max_open`')]
    assert 'nudges.dropped' in row


def test_health_counts_and_all_see_rows_the_cap_drops(tmp_path, monkeypatch, capsys):
    from wuwei import workspace
    from wuwei.__main__ import main
    from wuwei.commands import doctor, status
    gap = {'kind': 'traces.gap', 'payload': {'item': 'A', 'reason': 'r'}, 'ts': at(300)}
    calls = [tracker(f'I{number}', 10) for number in range(25)]
    directory = day(tmp_path, monkeypatch, [gap] * 3 + calls)
    snap = status.snapshot(directory)
    assert (snap['trace_gaps'], snap['nudges']) == (3, 20)
    probes = {'state': {'result': 'ok', 'value': 'ok'}, 'planner': {'result': 'ok', 'value': 'ok'},
              'seats': {'result': 'ok', 'value': 'none stuck'}}
    rows = {row['name']: row['value'] for row in doctor._day(tmp_path, workspace.load_config(tmp_path), probes)}
    assert rows['traces'] == '3 gaps today'
    assert main(['nudges', '--all', '--json']) == 0
    shown = json.loads(capsys.readouterr().out)
    assert len(shown) == 26 and not [row for row in shown if row['source'] == 'nudges.dropped']
