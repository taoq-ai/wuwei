"""Issue 742: nudges.mode, off under autonomous, next names a runnable command."""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
NOW = '2026-09-28T12:00:00+02:00'


def config(root, text=''):
    (root / '.wuwei').mkdir(parents=True, exist_ok=True)
    (root / '.wuwei/config.toml').write_text(text)


@pytest.mark.parametrize('text,expected', [
    ('', 'off'),
    ('[autonomy]\nmode = "supervised"\n', 'next'),
    *[(f'[nudges]\nmode = "{mode}"\n{autonomy}', mode) for mode in ('off', 'next', 'all')
      for autonomy in ('', '[autonomy]\nmode = "supervised"\n')],
])
def test_nudge_mode_follows_autonomy_unless_set(tmp_path, text, expected):
    from wuwei import workspace
    config(tmp_path, text)
    loaded = workspace.load_config(tmp_path)
    assert workspace.nudge_mode(loaded) == expected
    if not text:
        assert loaded['nudges']['mode'] == ''


EVENTS = [{'kind': 'watch: read-failed', 'payload': {'reason': 'could not read the tracker'}},
          {'kind': 'merge.unmeasured', 'payload': {'pr': 'acme/widget#1'}},
          {'kind': 'draft.created', 'payload': {'id': 'DR-1'}},
          {'kind': 'steward.due', 'payload': {'tool_calls': 50}},
          {'kind': 'security.finding'}]
FIX = {'gate_approved': True, 'approved_items': ['A'], 'items': {'A': {'phase': 'fix'}}}


def day(root, monkeypatch, state_data=None, events=EVENTS, text=''):
    monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
    monkeypatch.setenv('WUWEI_NOW', NOW)
    directory = root / '.wuwei/days/2026-09-28'
    directory.mkdir(parents=True)
    if state_data is not None:
        (directory / 'state.json').write_text(json.dumps({'cap': 1, 'items': {}, **state_data}))
    (directory / 'events.jsonl').write_text(''.join(json.dumps(e) + '\n' for e in events))
    if text is not None:
        config(root, text)
    return directory


@pytest.mark.parametrize('text,mode,kept', [
    ('', 'off', 'pages'), ('[nudges]\nmode = "all"\n', 'all', 'all'),
    ('[nudges]\nmode = "next"\n', 'next', 'pages'), (None, 'all', 'all')])
def test_surfaced_filters_by_mode(tmp_path, monkeypatch, text, mode, kept):
    from wuwei.commands import status
    directory = day(tmp_path, monkeypatch, {}, text=text)
    rows = status.attention(directory)
    assert len(rows) == 5 and sum(row['tier'] == 'page' for row in rows) == 1
    found, shown = status.surfaced(directory, rows)
    assert found == mode
    assert shown == (rows if kept == 'all' else [row for row in rows if row['tier'] == 'page'])


def ready(directory, data=None):
    from wuwei.commands import status
    return [row for row in status.surfaced(directory, status.attention(directory), data)[1]
            if row['tier'] == 'nudge']


def test_next_names_a_ready_fix_round_once(tmp_path, monkeypatch):
    directory = day(tmp_path, monkeypatch, FIX, [], '[nudges]\nmode = "next"\n')
    rows = ready(directory)
    assert rows == ready(directory) and len(rows) == 1
    assert rows[0]['source'] == 'round.ready' and 'wuwei build next A' in rows[0]['reason']


@pytest.mark.parametrize('running', [
    {'seats': {'S-1': {'status': 'running', 'role': 'builder', 'item': 'A'}}},
    {'builds': {'A': {'check': {'pid': 'parent', 'started_at': NOW}}}}])
def test_next_is_quiet_while_the_round_runs(tmp_path, monkeypatch, running):
    import os
    if 'builds' in running:
        running['builds']['A']['check']['pid'] = os.getppid()
    directory = day(tmp_path, monkeypatch, {**FIX, **running}, [], '[nudges]\nmode = "next"\n')
    assert ready(directory) == []


@pytest.mark.parametrize('extra,expected', [
    ({}, 1), ({'close_requested': True}, 0),
    ({'items': {'A': {'phase': 'merged'}, 'B': {'phase': 'implement'}}}, 0)])
def test_next_names_a_pending_close(tmp_path, monkeypatch, extra, expected):
    data = {'gate_approved': True, 'approved_items': ['A', 'B'],
            'items': {'A': {'phase': 'merged'}, 'B': {'phase': 'parked', 'resume_phase': 'fix'}},
            **extra}
    directory = day(tmp_path, monkeypatch, data, [], '[nudges]\nmode = "next"\n')
    rows = ready(directory)
    assert len(rows) == expected
    if rows:
        assert rows[0]['source'] == 'close.ready' and 'wuwei close' in rows[0]['reason']


@pytest.mark.parametrize('replied,expected', [(True, ['decision.answered']), (False, [])])
def test_next_keeps_an_answered_card(tmp_path, monkeypatch, replied, expected):
    events = [{'kind': 'decision.replied', 'ts': '2026-09-28T11:00:00+02:00',
               'payload': {'id': 'D-2', 'option': 'A'}}] if replied else []
    routes = {'D-2': {'reversibility': 'two-way', 'recommendation': 'A'}}
    directory = day(tmp_path, monkeypatch, {'decision_routes': routes}, events,
                    '[nudges]\nmode = "next"\n')
    assert [row['source'] for row in ready(directory)] == expected


def test_status_line_and_json_follow_the_mode(tmp_path, monkeypatch, capsys):
    from wuwei.__main__ import main
    from wuwei.commands import status
    directory = day(tmp_path, monkeypatch, {})
    data = status.snapshot(directory)
    assert (data['nudges'], data['nudges_mode'], data['pages']) == (0, 'off', 1)
    text = status.line(status.snapshot(directory, line=True))
    assert 'pages 1' in text and 'nudges' not in text
    assert main(['status', '--json']) == 0
    shown = json.loads(capsys.readouterr().out)
    assert (shown['nudges'], shown['nudges_mode']) == (0, 'off')
    config(tmp_path, '[nudges]\nmode = "all"\n')
    raw = sum(row['tier'] == 'nudge' for row in status.attention(directory))
    assert raw == 4 and status.snapshot(directory)['nudges'] == raw
    assert f'nudges {raw}' in status.line(status.snapshot(directory, line=True))
    (directory / 'state.json').write_text(json.dumps({'cap': 1, **FIX}))
    config(tmp_path, '[nudges]\nmode = "next"\n')
    assert 'nudges 1' in status.line(status.snapshot(directory, line=True))


def test_a_snapshot_without_a_mode_keeps_the_nudge_token():
    from wuwei.commands import status
    data = {'gate_approved': True, 'phases': {}, 'cap': 1, 'pages': 0, 'nudges': 3}
    assert 'nudges 3' in status._render(status._groups(data))


def test_wuwei_nudges_lists_what_the_mode_shows(tmp_path, monkeypatch, capsys):
    from wuwei.__main__ import main
    from wuwei.commands import nudges, status
    directory = day(tmp_path, monkeypatch, {})
    page = [row for row in status.attention(directory) if row['tier'] == 'page']
    assert main(['nudges', '--json']) == 0
    assert json.loads(capsys.readouterr().out) == page
    assert main(['nudges']) == 0
    assert [text.split(':')[0] for text in capsys.readouterr().out.splitlines()] == ['page']
    assert main(['nudges', '--all', '--json']) == 0
    assert json.loads(capsys.readouterr().out) == status.attention(directory)
    assert nudges.run(type('A', (), {'json': True})()) == 0
    assert json.loads(capsys.readouterr().out) == page
    (directory / 'state.json').write_text(json.dumps({'cap': 1, **FIX}))
    (directory / 'events.jsonl').write_text('')
    config(tmp_path, '[nudges]\nmode = "next"\n')
    assert main(['nudges']) == 0
    assert capsys.readouterr().out == 'nudge: A fix round is ready: run wuwei build next A\n'


@pytest.mark.parametrize('text', ['', '[nudges]\nmode = "next"\n', '[nudges]\nmode = "all"\n'])
def test_wuwei_nudges_before_the_day_starts(tmp_path, monkeypatch, capsys, text):
    from wuwei.__main__ import main
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', NOW)
    config(tmp_path, text)
    assert main(['nudges']) == 0
    assert capsys.readouterr().out == 'No open pages or nudges.\n'


def test_board_and_doctor_follow_the_mode(tmp_path, monkeypatch):
    from wuwei import workspace
    from wuwei.commands import board, doctor
    directory = day(tmp_path, monkeypatch, {},
                    [*EVENTS, {'kind': 'traces.gap', 'payload': {'reason': 'a gap'}}])
    text = board.read(tmp_path)[0]
    attention = text.split('Attention', 1)[1]
    assert 'page' in attention and 'nudge' not in attention
    probes = {name: {'result': 'ok', 'value': 'ok'} for name in ('state', 'planner', 'seats')}
    rows = {row['name']: row for row in doctor._day(tmp_path, workspace.load_config(tmp_path), probes)}
    assert 'nudges.mode off' in rows['nudges']['value']
    assert 'wuwei nudges --all' in rows['nudges']['value']
    assert 'nudges --all' in rows['traces']['fix']
    assert rows['security.finding']['status'] == 'fail'


@pytest.mark.parametrize('answer,expected', [('Autonomous', 'off'), ('Supervised', 'next')])
def test_the_autonomy_answer_sets_the_nudge_mode(tmp_path, answer, expected):
    # The answer's autonomy.mode sets the mode through the "" default; writing nudges.mode too
    # would make every configured workspace without the key ask the autonomy question again.
    from wuwei import interview, workspace
    row = next(row for row in interview.QUESTIONS if row['id'] == 'autonomy')
    effects = next(result for name, _, result in row['choices'] if name == answer)
    assert 'nudges.mode' not in effects
    config(tmp_path, ''.join(f'{key} = "{value}"\n' for key, value in effects.items()))
    assert workspace.nudge_mode(workspace.load_config(tmp_path)) == expected


def test_unknown_nudge_mode_is_refused(tmp_path):
    from wuwei import workspace
    config(tmp_path, '[nudges]\nmode = "sometimes"\n')
    with pytest.raises(workspace.ConfigError):
        workspace.load_config(tmp_path)
