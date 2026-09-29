"""Issue 92 attention and status contracts."""

import json
import ast
import os
from pathlib import Path
import shlex
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
NOW = '2026-09-28T12:00:00+02:00'


def emitted_kinds(sources):
    emitted = set()
    for source in sources:
        tree = ast.parse(source.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for keyword in node.keywords:
                if keyword.arg == 'kind' and isinstance(keyword.value, ast.Constant):
                    emitted.add(keyword.value.value)
            if (isinstance(node.func, ast.Name) and node.func.id == 'append_event'
                    or isinstance(node.func, ast.Attribute) and node.func.attr == 'append_event'):
                if node.args and isinstance(node.args[0], ast.Constant):
                    emitted.add(node.args[0].value)
    return emitted


def cli(root, *args, input=None):
    return subprocess.run([sys.executable, '-P', '-m', 'wuwei', *args],
                          input=input, text=True, capture_output=True,
                          cwd=root, env={**os.environ, 'PYTHONPATH': str(ROOT / 'cli'),
                                         'WUWEI_WORKSPACE': str(root), 'WUWEI_NOW': NOW})


def day(root, state_data=None, events=()):
    directory = root / '.wuwei/days/2026-09-28'
    directory.mkdir(parents=True)
    if state_data is not None:
        (directory / 'state.json').write_text(json.dumps(state_data))
    (directory / 'events.jsonl').write_text(''.join(json.dumps(e) + '\n' for e in events))
    return directory


PAGE = [
    ({'kind': 'item.escalated', 'payload': {'item': 'A'}}, 'Decisions'),
    ({'kind': 'day.blocked'}, 'Work'),
    ({'kind': 'security.finding'}, 'Work'),
    ({'kind': 'base.red'}, 'Work'),
    ({'kind': 'decision.one_way', 'payload': {'blocking': True}}, 'Decisions'),
    ({'kind': 'dead_man.hit'}, 'Work'),
    ({'kind': 'budget.cap'}, 'Work'),
    ({'kind': 'person.ask', 'payload': {'due': '2026-09-28T11:00:00+02:00'}}, 'People'),
]
NUDGE = [
    ({'kind': 'decision.one_way'}, 'Decisions'),
    ({'kind': 'merge.policy_blocked'}, 'Decisions'),
    ({'kind': 'work.outside_goals'}, 'Decisions'),
    ({'kind': 'budget.usage', 'payload': {'fraction': .8}}, 'Work'),
    ({'kind': 'person.ask', 'payload': {'due': '2026-09-28T13:00:00+02:00'}}, 'People'),
    ({'kind': 'mystery'}, 'Work'),
    ({'kind': 'watch: sweep', 'payload': {'owed': 1, 'unreadable': 0}}, 'Work'),
    ({'kind': 'watch: sweep', 'payload': {'owed': 0, 'unreadable': 1}}, 'Work'),
    ({'kind': 'watch: sweep', 'payload': {'owed': 0, 'unreadable': 'unknown'}}, 'Work'),
    ({'kind': 'watch: sweep', 'payload': {'owed': 0}}, 'Work'),
    ({'kind': 'watch: sweep', 'payload': {'unreadable': 0}}, 'Work'),
    (None, 'Work'),
]
SILENT = [
    ({'kind': 'item.progress'}, 'Work'),
    ({'kind': 'decision.two_way'}, 'Decisions'),
    ({'kind': 'merge.auto'}, 'Work'),
    ({'kind': 'reply: acknowledged'}, 'Work'),
    ({'kind': 'watch: sweep', 'payload': {'owed': 0, 'unreadable': 0}}, 'Work'),
]


@pytest.mark.parametrize('event,lane', PAGE)
def test_page_triggers(event, lane):
    from wuwei.signal import classify
    state = {'items': {'A': {'phase': 'escalated'}},
             'seats': {'builder': {'item': 'A', 'status': 'running'}}, 'now': NOW}
    assert classify(event, state) == ('page', lane)


@pytest.mark.parametrize('event,lane', NUDGE)
def test_nudge_triggers(event, lane):
    from wuwei.signal import classify
    assert classify(event, {'now': NOW}) == ('nudge', lane)


@pytest.mark.parametrize('event,lane', SILENT)
def test_silent_triggers(event, lane):
    from wuwei.signal import classify
    assert classify(event, {}) == ('silent', lane)


def test_escalation_without_running_seat_is_nudge():
    from wuwei.signal import classify
    assert classify({'kind': 'item.escalated', 'payload': {'item': 'A'}},
                    {'seats': {}}) == ('nudge', 'Decisions')


def test_signal_cli_reads_event_from_stdin(tmp_path):
    day(tmp_path, {'items': {}, 'cap': 1})
    result = cli(tmp_path, 'signal', 'classify', input=json.dumps({'kind': 'security.finding'}))
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {'tier': 'page', 'lane': 'Work'}


def test_status_line_and_json_share_snapshot(tmp_path):
    state_data = {'cap': 2, 'items': {'A': {'phase': 'implement'},
                                     'B': {'phase': 'spec'}, 'C': {'phase': 'merged'}},
                  'reply_obligations': [{'due': '2026-09-28T14:00:00+02:00'},
                                        {'due': '2026-09-28T13:00:00+02:00'}],
                  'meetings': [{'start': '2026-09-28T16:00:00+02:00'}]}
    directory = day(tmp_path, state_data, [{'kind': 'security.finding'},
                                           {'kind': 'decision.one_way'}])
    before = {p.name: p.read_bytes() for p in directory.iterdir()}
    line = cli(tmp_path, 'status', '--line')
    structured = cli(tmp_path, 'status', '--json')
    assert line.returncode == structured.returncode == 0
    assert line.stdout.count('\n') == 1
    assert 'pages 1' in line.stdout and 'nudges 1' in line.stdout
    assert 'spec 1/2' in line.stdout and 'implement 1/2' in line.stdout
    assert 'reply 2026-09-28T13:00:00+02:00' in line.stdout
    assert 'meeting 2026-09-28T16:00:00+02:00' in line.stdout
    data = json.loads(structured.stdout)
    assert data['pages'] == 1 and data['nudges'] == 1
    assert data['phases']['spec'] == 1 and data['cap'] == 2
    assert data['next_reply_due'] == '2026-09-28T13:00:00+02:00'
    assert {p.name: p.read_bytes() for p in directory.iterdir()} == before


@pytest.mark.parametrize('contents', [None, '{broken'])
def test_unreadable_state_fails_closed(tmp_path, contents):
    directory = day(tmp_path)
    if contents is not None:
        (directory / 'state.json').write_text(contents)
    result = cli(tmp_path, 'status', '--line')
    assert result.returncode == 2
    assert result.stdout == 'WUWEI ? unmeasured\n'


def test_init_prints_snippet_without_owner_settings_write(tmp_path):
    result = cli(tmp_path, 'init')
    assert result.returncode == 0, result.stderr
    snippet = result.stdout.splitlines()[-1]
    assert json.loads(snippet) == {'statusLine': {'type': 'command',
        'command': str(ROOT / 'bin/wuwei') + ' status --line'}}


def test_budget_below_threshold_is_silent():
    from wuwei.signal import classify
    assert classify({'kind': 'budget.usage', 'payload': {'fraction': .79}}, {}) == ('silent', 'Work')


def test_next_due_uses_instant_across_offsets(tmp_path):
    day(tmp_path, {'items': {}, 'cap': 1,
                   'reply_obligations': [{'due': '2026-09-28T11:30:00+02:00'},
                                         {'due': '2026-09-28T10:00:00+00:00'}]})
    result = cli(tmp_path, 'status', '--json')
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['next_reply_due'] == '2026-09-28T11:30:00+02:00'


@pytest.mark.parametrize('kind', ['state.set', 'state.transition', 'seat started', 'seat stopped'])
def test_routine_progress_is_silent(kind):
    from wuwei.signal import classify
    assert classify({'kind': kind}, {}) == ('silent', 'Work')


def test_emitted_kinds_have_intended_tiers():
    from wuwei.signal import classify
    emitted = emitted_kinds(sorted((ROOT / 'cli/wuwei').rglob('*.py')))
    emitted.update(['retro.gap', 'retro.captured'])
    emitted.add('state.write')  # default writer kind
    emitted.update(['watch: observation', 'session: compact'])  # writer default and locked append
    expected = {'state.write': 'silent', 'state.set': 'silent',
                'state.transition': 'silent', 'seat stopped': 'silent',
                'seat launched': 'silent', 'brief written': 'silent',
                'fast_checks.record': 'silent', 'retro.captured': 'silent',
                'seat.usage': 'silent', 'build.parked': 'nudge',
                'retro.gap': 'nudge', 'seat stop unmatched': 'nudge',
                'hook.post_tool_use_error': 'nudge', 'hook.refusal': 'silent',
                'hook.warning': 'nudge',
                'verdict.rejected': 'nudge', 'decision.rejected': 'nudge',
                'decision.decided': 'silent',
                'adapter: none': 'nudge', 'reply: acknowledged': 'silent',
                'watch: sweep': 'nudge', 'watch: clock': 'silent',
                'watch: heartbeat': 'silent', 'watch: observation': 'silent',
                'watch: read-failed': 'nudge', 'pr.changed': 'nudge',
                'session: compact': 'silent', 'session: wake-seen': 'silent',
                'plan.session': 'silent'}
    assert emitted == set(expected)
    for kind, tier in expected.items():
        assert classify({'kind': kind}, {})[0] == tier
    assert classify({'kind': 'build.iteration'}, {})[0] == 'silent'


def test_emitted_kinds_scan_both_writer_forms_in_nested_files(tmp_path):
    nested = tmp_path / 'commands'
    nested.mkdir()
    (nested / 'writer.py').write_text("append_event('bare.kind')\nstate.append_event('qualified.kind')\n")
    assert emitted_kinds(sorted(tmp_path.rglob('*.py'))) == {'bare.kind', 'qualified.kind'}


def test_transition_to_escalated_uses_running_seat():
    from wuwei.signal import classify
    event = {'kind': 'state.transition', 'payload': {'item': 'A', 'phase': 'escalated'}}
    assert classify(event, {'seats': {'builder': {'item': 'A', 'status': 'running'}}}) == ('page', 'Decisions')
    assert classify(event, {'seats': {}}) == ('nudge', 'Decisions')


@pytest.mark.parametrize('page,spoof,exit_code', [
    ('security.finding', 'security.resolved', 0),
    ('base.red', 'base.green', 0),
    ('dead_man.hit', 'dead_man.cleared', 0),
    ('budget.cap', 'budget.cleared', 0),
    ('day.blocked', 'day.unblocked', 0),
    ('decision.one_way', 'decision.resolved', 1),
    ('person.ask', 'person.answered', 0),
])
def test_seat_event_cannot_clear_day_page(tmp_path, page, spoof, exit_code):
    payload = {'id': 'same', 'blocking': True, 'due': NOW}
    day(tmp_path, {'items': {}, 'cap': 1}, [{'kind': page, 'payload': payload}])
    assert cli(tmp_path, 'event', spoof, json.dumps({'id': 'same'})).returncode == exit_code
    result = cli(tmp_path, 'status', '--json')
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['pages'] == 1


def test_status_counts_escalation_from_current_state(tmp_path):
    directory = day(tmp_path, {'items': {'A': {'phase': 'escalated', 'resume_phase': 'implement'}},
                               'cap': 1, 'seats': {'builder': {'item': 'A', 'status': 'running'}}})
    result = cli(tmp_path, 'status', '--json')
    assert json.loads(result.stdout)['pages'] == 1
    (directory / 'state.json').write_text(json.dumps({'items': {'A': {'phase': 'implement'}},
                                                       'cap': 1, 'seats': {}}))
    result = cli(tmp_path, 'status', '--json')
    assert json.loads(result.stdout)['pages'] == 0


def test_old_event_signal_expires_at_day_boundary(tmp_path):
    day(tmp_path, {'items': {}, 'cap': 1},
        [{'kind': 'budget.cap', 'ts': '2026-09-27T23:59:00+02:00'}])
    result = cli(tmp_path, 'status', '--json')
    assert json.loads(result.stdout)['pages'] == 0


def test_recursion_error_never_blanks_status(tmp_path, monkeypatch, capsys):
    from wuwei.commands import status
    from argparse import Namespace
    day(tmp_path, {'items': {}, 'cap': 1})
    monkeypatch.setattr(status.workspace, 'day_dir', lambda: tmp_path / '.wuwei/days/2026-09-28')
    monkeypatch.setattr(status, 'snapshot', lambda directory: (_ for _ in ()).throw(RecursionError()))
    assert status.run(Namespace(line=True, json=False)) == 2
    assert capsys.readouterr().out == 'WUWEI ? unmeasured\n'


def test_init_leaves_owner_settings_untouched(tmp_path):
    home = tmp_path / 'home'
    settings = home / '.claude/settings.json'
    settings.parent.mkdir(parents=True)
    settings.write_text('{"theme":"dark"}')
    workspace_root = tmp_path / 'workspace'
    workspace_root.mkdir()
    result = subprocess.run([sys.executable, '-P', '-m', 'wuwei', 'init'],
                            cwd=workspace_root, capture_output=True, text=True,
                            env={**os.environ, 'HOME': str(home),
                                 'PYTHONPATH': str(ROOT / 'cli')})
    assert result.returncode == 0, result.stderr
    assert settings.read_text() == '{"theme":"dark"}'
    assert json.loads(result.stdout.splitlines()[-1])['statusLine']['command'] == (
        shlex.quote(str(ROOT / 'bin/wuwei')) + ' status --line')
