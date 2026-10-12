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
WARN = [
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
    ({'kind': 'steward.due', 'payload': {'tool_calls': 50}}, 'Work'),
    ({'kind': 'calibration.drift', 'payload': {'repo': 'acme/widget', 'changed': ['ci_checks']}}, 'Work'),
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


@pytest.mark.parametrize('event,lane', WARN)
def test_warn_triggers(event, lane):
    from wuwei.signal import classify
    assert classify(event, {'now': NOW}) == ('warn', lane)


@pytest.mark.parametrize('event,lane', SILENT)
def test_silent_triggers(event, lane):
    from wuwei.signal import classify
    assert classify(event, {}) == ('silent', lane)


def test_escalation_without_running_seat_is_warn():
    from wuwei.signal import classify
    assert classify({'kind': 'item.escalated', 'payload': {'item': 'A'}},
                    {'seats': {}}) == ('warn', 'Decisions')


def test_status_line_reads_the_day_and_writes_nothing(tmp_path):
    state_data = {'cap': 2, 'items': {'A': {'phase': 'implement'},
                                     'B': {'phase': 'spec'}, 'C': {'phase': 'merged'}},
                  'reply_obligations': [{'due': '2026-09-28T14:00:00+02:00'},
                                        {'due': '2026-09-28T13:00:00+02:00'}],
                  'meetings': [{'start': '2026-09-28T16:00:00+02:00'}]}
    directory = day(tmp_path, state_data, [
        {'kind': kind, 'payload': {}, 'ts': NOW}
        for kind in ('security.finding', 'decision.one_way', 'watch: clock')])
    (tmp_path / '.wuwei/config.toml').write_text('')
    before = {p.name: p.read_bytes() for p in directory.iterdir()}
    line = cli(tmp_path, 'status', '--line')
    assert line.returncode == 0, line.stderr
    assert line.stdout.count('\n') == 1
    assert 'pages 1' in line.stdout and 'nudges' not in line.stdout
    assert '2 building' in line.stdout and 'reply' not in line.stdout
    assert {p.name: p.read_bytes() for p in directory.iterdir()} == before


def test_status_line_names_running_seats_and_checks(tmp_path, monkeypatch, capsys):
    from wuwei.__main__ import main
    from wuwei.commands import status
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', NOW)
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
    try:
        directory = day(tmp_path, {'cap': 2, 'gate_approved': True, 'items': {
            name: {'phase': 'implement'} for name in 'ABCD'}, 'seats': {
            'builder-1': {'status': 'running', 'role': 'builder', 'item': 'A',
                          'started_at': '2026-09-28T09:10:00+02:00'},
            'builder-2': {'status': 'running', 'role': 'builder', 'item': 'B',
                          'started_at': '2026-09-28T09:20:00+02:00'},
            'checker-1': {'status': 'running', 'role': 'reviewer', 'item': 'D'}},
            'builds': {'C': {'status': 'check', 'check': {
                'started_at': '2026-09-28T09:25:00+02:00', 'pid': child.pid}}}})
        assert main(['status', '--line']) == 0
        line = capsys.readouterr().out
        running = status.snapshot(directory)['running']
    finally:
        child.kill()
        child.wait()
    assert 'seats 3/2 (reviewer, builder, builder)' in line and 'running' not in line
    assert running == [('', 'reviewer', 'D'),
                       ('2026-09-28T09:10:00+02:00', 'builder', 'A'),
                       ('2026-09-28T09:20:00+02:00', 'builder', 'B'),
                       ('2026-09-28T09:25:00+02:00', 'checks', 'C')]


def test_status_counts_every_nonzero_phase(tmp_path, monkeypatch, capsys):
    from wuwei.__main__ import main
    from wuwei.commands import status
    directory = day(tmp_path, {'cap': 2, 'items': {'A': {'phase': 'delta'}, 'B': {'phase': 'merged'}}})
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', NOW)
    assert main(['status', '--line']) == 0
    line = capsys.readouterr().out
    assert '1 in review' in line and '1 shipped' in line and 'building' not in line
    assert status.snapshot(directory)['phases'] == {'delta': 1, 'merged': 1}


@pytest.mark.parametrize('name', ['state.json'])  # #844: the snapshot is never read for the day
def test_unreadable_state_fails_closed(tmp_path, name):
    directory = day(tmp_path)
    (directory / name).write_text('{broken')
    result = cli(tmp_path, 'status', '--line')
    assert result.returncode == 2
    assert result.stdout == 'WUWEI ? unmeasured\n'


@pytest.mark.parametrize('state_data', [None, {'cap': 1, 'items': {}}])
def test_no_plan_yet_before_the_gate(tmp_path, state_data):
    day(tmp_path, state_data)
    result = cli(tmp_path, 'status', '--line')
    assert result.returncode == 0, result.stderr
    assert result.stdout == 'WUWEI no plan yet | pages 0\n'


def test_approved_gate_has_no_plan_yet_prefix(tmp_path):
    day(tmp_path, {'cap': 1, 'items': {}, 'gate_approved': True})
    result = cli(tmp_path, 'status', '--line')
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith('WUWEI seats 0/1 | pages 0') and 'no plan yet' not in result.stdout


def test_init_prints_snippet_without_owner_settings_write(tmp_path):
    result = cli(tmp_path, 'init')
    assert result.returncode == 0, result.stderr
    snippet = result.stdout.splitlines()[1]
    assert json.loads(snippet) == {'statusLine': {'type': 'command',
        'command': str(ROOT / 'bin/wuwei') + ' status --line'}}


def test_budget_below_threshold_is_silent():
    from wuwei.signal import classify
    assert classify({'kind': 'budget.usage', 'payload': {'fraction': .79}}, {}) == ('silent', 'Work')


def test_status_line_ignores_a_damaged_cruise_file(tmp_path):
    # #814: cruise is gone; a stale memory/cruise.json is never read.
    day(tmp_path, {'items': {}, 'cap': 1})
    (tmp_path / '.wuwei/memory').mkdir(parents=True, exist_ok=True)
    (tmp_path / '.wuwei/memory/cruise.json').write_text('not json')
    result = cli(tmp_path, 'status', '--line')
    assert result.returncode == 0, result.stderr
    assert 'cruise' not in result.stdout


@pytest.mark.parametrize('kind', ['state.set', 'state.transition', 'seat started', 'seat stopped',
                                  'plan.approved', 'state.import', 'build.started',
                                  'build.launched', 'build.checked', 'verdict.rejected'])
def test_routine_progress_is_silent(kind):
    from wuwei.signal import classify
    assert classify({'kind': kind}, {}) == ('silent', 'Work')


def test_tracker_none_is_silent_but_tracker_failure_warns():
    from wuwei.signal import classify
    event = {'kind': 'tracker.call', 'payload': {'exit': 2, 'reason': 'tracker adapter is none'}}
    assert classify(event, {})[0] == 'silent'
    event['payload']['reason'] = ('tracker adapter is none, so tracker updates are skipped; to reach '
                                  'the tracker, the owner sets adapters.tracker with bin/wuwei config set')
    assert classify(event, {})[0] == 'silent'
    assert {classify({'kind': f'duty.{step}', 'payload': {}}, {})[0]
            for step in ('due', 'done', 'skipped')} == {'silent'}
    event['payload']['reason'] = 'tracker call unmeasured: OSError'
    assert classify(event, {})[0] == 'warn'


def test_emitted_kinds_have_intended_tiers():
    from wuwei.signal import classify
    emitted = emitted_kinds(sorted((ROOT / 'cli/wuwei').rglob('*.py')))
    emitted.update(['retro.gap', 'retro.captured', 'security.canary', 'security.honeytoken'])
    emitted.add('state.write')  # default writer kind
    emitted.update(['traces.gap', 'traces.slow'])  # traces.check picks its kind (#659)
    emitted.add('watch: observation')  # watch.save's default kind
    emitted.update(['spec.step', 'spec.skipped', 'spec.warned'])  # specmode.once(kind)
    expected = {'security.canary': 'page', 'security.honeytoken': 'page',
                'scanner.finding': 'page', 'state.write': 'silent',
                'state.transition': 'silent', 'seat stopped': 'silent',
                'seat launched': 'silent', 'brief written': 'silent',
                'worktree.adopted': 'silent', 'worktree.created': 'silent',
                'fast_checks.record': 'silent', 'retro.captured': 'silent',
                'seat.usage': 'silent', 'cap.derived': 'silent', 'build.parked': 'warn',
                'build.fix_opened': 'silent', 'polish.skipped': 'warn', 'pr.action.done': 'silent',
                'retro.gap': 'warn', 'seat stop unmatched': 'warn',
                'seat adhoc': 'silent', 'subagent.untraced': 'warn',
                'traces.gap': 'warn', 'traces.slow': 'warn', 'hook.refusal': 'silent',
                'guard.would_refuse': 'silent', 'config.newer_template': 'warn',
                'hook.warning': 'warn',
                'verdict.rejected': 'silent',
                'adapter: none': 'silent', 'reply: acknowledged': 'silent',
                'reply: thread_posted': 'silent', 'pr.raised': 'silent',
                'pr.claimed': 'silent',
                'pr.reviewers_selected': 'silent', 'pr.review_posted': 'silent',
                'reviewer.unresolved': 'silent',
                'watch: observation': 'silent',
                'plan.session': 'silent', 'gate.asked': 'silent', 'pr.disposition': 'silent', 'pr.action': 'warn',
                'day.close_requested': 'silent', 'day.closed': 'silent', 'next.action': 'silent', 'merge.unmeasured': 'warn',
                'merge.metric': 'silent', 'merge.policy_blocked': 'warn', 'base.red': 'page',
                'gate.received': 'silent', 'gate.tiered': 'silent', 'gate.delta_head': 'silent',
                'plan.added': 'silent', 'finding.noted': 'silent',
                'tracker.call': 'warn',
                'tracker.created': 'silent', 'tracker.folded': 'silent', 'duty.due': 'silent',
                'duty.done': 'silent', 'duty.skipped': 'silent',
                'tracker.logged': 'silent', 'plan.set': 'silent',
                'steward.run': 'silent',
                'plan.disposed': 'silent', 'plan.resumed': 'silent',
                'calibration.drift': 'warn',
                'doctor.fixed': 'silent', 'outward.ai_tells': 'silent',
                'outward.to_owner': 'silent',
                'spec.step': 'silent', 'spec.skipped': 'silent', 'spec.override': 'silent',
                'spec.warned': 'warn',
                **{f'telemetry.{name}': 'warn' if name == 'ready' else 'silent' for name in TELEMETRY}}
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
    assert classify(event, {'seats': {}}) == ('warn', 'Decisions')


@pytest.mark.parametrize('page,spoof', [
    ('security.finding', 'security.resolved'),
    ('base.red', 'base.green'),
    ('dead_man.hit', 'dead_man.cleared'),
    ('budget.cap', 'budget.cleared'),
    ('day.blocked', 'day.unblocked'),
    ('decision.one_way', 'decision.resolved'),
    ('person.ask', 'person.answered'),
])
def test_seat_event_cannot_clear_day_page(tmp_path, page, spoof):
    payload = {'id': 'same', 'blocking': True, 'due': NOW}
    day(tmp_path, {'items': {}, 'cap': 1}, [{'kind': page, 'payload': payload},
                                             {'kind': spoof, 'payload': {'id': 'same'}}])
    result = cli(tmp_path, 'status', '--line')
    assert result.returncode == 0, result.stderr
    assert 'pages 1' in result.stdout


def test_status_counts_escalation_from_current_state(tmp_path):
    directory = day(tmp_path, {'items': {'A': {'phase': 'escalated', 'resume_phase': 'implement'}},
                               'cap': 1, 'seats': {'builder': {'item': 'A', 'role': 'builder', 'status': 'running'}}},
                    [{'kind': 'watch: clock', 'payload': {}, 'ts': NOW}])
    (tmp_path / '.wuwei/config.toml').write_text('')
    assert 'pages 1' in cli(tmp_path, 'status', '--line').stdout
    (directory / 'state.json').write_text(json.dumps({'items': {'A': {'phase': 'implement'}},
                                                       'cap': 1, 'seats': {}}))
    assert 'pages 0' in cli(tmp_path, 'status', '--line').stdout


def test_old_event_signal_expires_at_day_boundary(tmp_path):
    day(tmp_path, {'items': {}, 'cap': 1},
        [{'kind': 'budget.cap', 'ts': '2026-09-27T23:59:00+02:00'}])
    assert 'pages 0' in cli(tmp_path, 'status', '--line').stdout


def test_recursion_error_never_blanks_status(tmp_path, monkeypatch, capsys):
    from wuwei.commands import status
    from argparse import Namespace
    day(tmp_path, {'items': {}, 'cap': 1})
    monkeypatch.setattr(status.workspace, 'day_dir', lambda: tmp_path / '.wuwei/days/2026-09-28')
    monkeypatch.setattr(status, 'snapshot', lambda directory: (_ for _ in ()).throw(RecursionError()))
    assert status.run(Namespace(line=True, width=status.WIDTH)) == 2
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
    assert json.loads(result.stdout.splitlines()[1])['statusLine']['command'] == (
        shlex.quote(str(ROOT / 'bin/wuwei')) + ' status --line')


ROUTED = {'D-2': {'reversibility': 'unsure', 'recommendation': 'defer'}}


def status_of(tmp_path, monkeypatch, events):
    from wuwei.commands import status
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', NOW)
    directory = day(tmp_path, {'items': {}, 'cap': 1, 'gate_approved': True}, events)
    (tmp_path / '.wuwei/config.toml').write_text('')
    data = status.snapshot(directory)
    return data, status.line(data), status.attention(directory)


CLOCK = {'kind': 'watch: clock', 'payload': {}, 'ts': NOW}  # a day before #847: a silent row


def test_restart_on_the_status_line(tmp_path, monkeypatch):
    from wuwei.commands import status
    data, line, _ = status_of(tmp_path, monkeypatch, [CLOCK])
    assert data['restart'] == '' and 'restart' not in line
    text = 'restart Claude Code: hooks 0.11.0 still running (plugin 0.12.0 installed)'
    assert status.line({**data, 'restart': text}).startswith(
        'WUWEI restart Claude Code: hooks 0.11.0 still running | seats 0/1 | pages 0')


def test_scan_skips_silent_lines_undecoded(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from wuwei.commands import status
    stamp = {'ts': NOW}
    events = ([{'kind': 'state.write', 'payload': {'item': f'I{n}'}, **stamp} for n in range(50)]
              + [{'kind': 'watch: clock', 'payload': {}, **stamp},
                 {'kind': 'hook.warning', 'payload': {'reason': 'lint finding'}, **stamp}])
    directory = day(tmp_path, events=events)
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', NOW)
    expected = status.attention(directory)
    seen = []
    monkeypatch.setattr(status, 'json', SimpleNamespace(
        loads=lambda line, **kw: seen.append(line) or json.loads(line, **kw), dumps=json.dumps))
    rows = status.attention(directory)
    assert len(seen) == 1 and not any('state.write' in line for line in seen)
    assert rows == expected
    assert any(row['source'] == 'hook.warning' and row['reason'] == 'lint finding' for row in rows)


def test_scan_decodes_torn_silent_line(tmp_path, monkeypatch):
    from wuwei.commands import status
    directory = day(tmp_path, events=[])
    (directory / 'events.jsonl').write_text('{"kind": "state.write", "payload": {"a": 1}\n')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', NOW)
    rows = status.attention(directory)
    assert any(row['source'] == 'unreadable event' for row in rows)


def test_scan_kind_alternation_matches_exactly_the_skipped_kinds():
    # #346: the skipped kinds as a prefix tree; the same strings as a plain alternation.
    import re
    from wuwei.commands import status
    from wuwei.signal import SILENT
    small = ['seat', 'seat launched', 'state.set', 'a.b']
    pattern = re.compile(status._alternation(small))
    assert all(pattern.fullmatch(word) for word in small)
    assert not any(pattern.fullmatch(word) for word in ('sea', 'seat ', 'seat l', 'state', 'axb', '', 'a.bc'))
    pattern = re.compile(status._alternation(sorted(status.SKIP)))
    assert all(pattern.fullmatch(kind) for kind in status.SKIP)
    others = ({kind[:-1] for kind in status.SKIP} | {kind + 's' for kind in status.SKIP}
              | set(SILENT)) - status.SKIP
    assert others and not any(pattern.fullmatch(kind) for kind in others)


def test_scan_reads_the_day_with_universal_newlines(tmp_path, monkeypatch):
    # #346: scan decodes the bytes itself; CR LF and a lone CR still end lines as read_text's did.
    from wuwei.commands import status
    warning = json.dumps({'kind': 'hook.warning', 'payload': {'reason': 'one'}, 'ts': NOW})
    silent = json.dumps({'kind': 'state.write', 'payload': {}, 'ts': NOW})
    directory = day(tmp_path, events=[])
    path = directory / 'events.jsonl'
    path.write_bytes(f'{silent}\r\n{warning}\r{warning}\n{silent}\r'.encode())
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', NOW)
    rows = status.attention(directory)
    assert sum(row['count'] for row in rows if row['source'] == 'hook.warning') == 2  # #786: folded
    assert not any(row['source'] == 'unreadable event' for row in rows)
    path.write_bytes(b'{"kind": "hook.warning", "payload": {"reason": "\xff"}, "ts": "' + NOW.encode() + b'"}\n')
    with pytest.raises(UnicodeDecodeError):
        status.attention(directory)


def test_scan_skip_matches_decoding_every_line(tmp_path, monkeypatch):
    # The skipped runs change no row and no line number: the same day decoded line by line.
    from wuwei.commands import status
    silent = {'kind': 'state.write', 'payload': {'detail': '{"ts": "x"}'}, 'ts': NOW}
    events = [silent, {'kind': 'hook.warning', 'payload': {'reason': 'one'}, 'ts': NOW}, silent, silent,
              CLOCK, {'kind': 'hook.warning', 'payload': {'reason': 'one'}, 'ts': NOW}, silent]
    directory = day(tmp_path, events=events)
    with (directory / 'events.jsonl').open('a') as stream:
        stream.write('\n{"kind": "seat stopped", "payload": {"a": {"b": 1}}\n'
                     + json.dumps(silent) + '\n{"kind": "hook.warning", "ts": "' + NOW + '"}')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', NOW)
    skipped = status.attention(directory)
    monkeypatch.setattr(status, 'LINES', r'([^\n]*)\n?')
    assert skipped == status.attention(directory)
    assert sum(row['count'] for row in skipped if row['source'] == 'hook.warning') == 3  # #786: folded
    assert any(row['source'] == 'unreadable event' for row in skipped)


NONE_EVENT = {'kind': 'adapter: none', 'payload': {'adapter': 'none', 'kind': 'scanner', 'call': 'audit',
                                                   'exit': 2, 'reason': 'unmeasured', 'performed': False}}


def test_issue_acceptance_adapter_none_is_silent(tmp_path, monkeypatch, capsys):
    from wuwei.__main__ import main
    from wuwei.commands.status import attention
    from wuwei.signal import classify
    assert classify(NONE_EVENT, {}) == ('silent', 'Work')
    directory = day(tmp_path, {'cap': 1, 'items': {}}, [NONE_EVENT, NONE_EVENT])
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', NOW)
    assert attention(directory) == []
    assert main(['status', '--line']) == 0
    assert capsys.readouterr().out == 'WUWEI no plan yet | pages 0\n'


@pytest.mark.parametrize('kind', ['outward.ai_tells', 'outward.lint', 'outward.to_owner'])
def test_outward_events_are_silent(kind):
    from wuwei.signal import classify
    assert classify({'kind': kind, 'payload': {}}, {})[0] == 'silent'


TELEMETRY = ('skipped', 'unsent', 'shared', 'ready', 'off')


@pytest.mark.parametrize('name', TELEMETRY)
def test_telemetry_events_are_quiet(name):
    # #422, design 5.13: telemetry.ready is a warning, the rest are silent.
    from wuwei.signal import classify
    assert classify({'kind': f'telemetry.{name}'}, {})[0] == ('warn' if name == 'ready' else 'silent')


def test_status_line_shows_running_seats_per_goal(tmp_path):
    items = {'A': {'phase': 'implement', 'goal': 'G-1'}, 'B': {'phase': 'implement', 'goal': 'G-2'}}
    seats = {name: {'id': name, 'role': role, 'item': item, 'status': 'running'}
             for name, role, item in (('a-1', 'builder', 'A'), ('b-1', 'builder', 'B'),
                                      ('g-1', 'sentinel-arch', 'A'))}
    day(tmp_path, {'cap': 3, 'items': items, 'seats': seats, 'gate_approved': True})
    result = cli(tmp_path, 'status', '--line')
    assert result.returncode == 0, result.stderr
    assert 'seats 3/3 (builder, builder, sentinel-arch)' in result.stdout
    (tmp_path / '.wuwei/days/2026-09-28/state.json').write_text(json.dumps(
        {'cap': 3, 'items': items, 'gate_approved': False}))
    assert 'seats' not in cli(tmp_path, 'status', '--line').stdout


def test_status_snapshot_holds_what_the_line_renders(tmp_path, monkeypatch):
    # #848: status is the line alone; the board is wuwei next.
    from wuwei.commands import status
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', NOW)
    directory = day(tmp_path, {'cap': 1, 'items': {}})
    (tmp_path / '.wuwei/config.toml').write_text('template_version = "0.1.0"\n')
    data = status.snapshot(directory)
    assert set(data) == {'pages', 'cap', 'cap_bound', 'gate_approved', 'phases', 'running', 'plan',
                         'enforce', 'restart'}
    assert data['plan'] is False
    (directory / 'plan.md').write_text('# Plan\n')
    assert status.snapshot(directory)['plan'] is True


ROLES = ('lead', 'arch', 'quality', 'security')
STALE = 'restart Claude Code: hooks 0.12.0 and 0.15.0 still running (plugin 0.16.0 installed)'


def four_seats(tmp_path, monkeypatch):
    """Issue 521: four running seats on one item and a live fast check, gate approved."""
    from wuwei.commands import status
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', NOW)
    seats = {role: {'status': 'running', 'role': role, 'item': 'ITEM-1',
                    'started_at': f'2026-09-28T09:{10 * n:02d}:00+02:00'}
             for n, role in enumerate(ROLES, 1)}
    directory = day(tmp_path, {'cap': 1, 'gate_approved': True, 'items': {'ITEM-1': {'phase': 'implement'}},
                               'seats': seats, 'builds': {'ITEM-1': {'status': 'check', 'check': {
                                   'started_at': '2026-09-28T09:45:00+02:00', 'pid': os.getppid()}}}})
    return status.snapshot(directory)


def tokens(text):
    return [token for group in text.removeprefix('WUWEI ').split(' | ') for token in group.split(' · ')]


def test_issue_acceptance_the_line_starts_with_the_restart_and_fits(tmp_path, monkeypatch):
    import re
    from wuwei.commands import status
    data = {**four_seats(tmp_path, monkeypatch), 'restart': STALE}
    line = status.line(data)
    assert len(line) <= 100
    assert line.startswith('WUWEI restart Claude Code: hooks 0.12.0 and 0.15.0 still running')
    assert 'pages 0' in line and 'nudges' not in line
    assert 'ITEM-1' not in line and not re.search(r'\d\d:\d\d', line) and '(plugin' not in line
    whole = tokens(status.line(data, 10 ** 6))
    assert all(token in whole or token.startswith('seats 4/1 (') for token in tokens(line))


def test_issue_acceptance_nothing_to_do_starts_with_the_counts(tmp_path, monkeypatch):
    from wuwei.commands import status
    data = four_seats(tmp_path, monkeypatch)
    assert status.line(data) == (
        'WUWEI 1 building · seats 4/1 (lead, arch, quality, security) | pages 0')
    assert status.line({**data, 'enforce': False}).endswith('| pages 0 · observe')
    assert status.line({**data, 'running': [], 'phases': {}}) == 'WUWEI seats 0/1 | pages 0'
    for moved in ('watch', 'sessions', 'meeting', 'reply', 'running', 'loops', 'bound',
                  'unplanned', 'checks'):
        assert moved not in status.line({**data, 'cap_bound': 'budget'})
    # #658: the seats token names the rule that set CAP; before the gate there is none
    assert 'seats 4/1 by budget (lead, ' in status.line({**data, 'cap_bound': 'budget'})
    assert ' by ' not in status.line({**data, 'cap_bound': ''})


def test_the_line_names_the_one_thing_to_do_first(tmp_path, monkeypatch):
    from wuwei.commands import status
    directory = day(tmp_path, {'cap': 1, 'items': {}})
    result = cli(tmp_path, 'status', '--line')
    assert (result.returncode, result.stdout) == (0, 'WUWEI no plan yet | pages 0\n')
    (directory / 'plan.md').write_text('# Plan\n')
    assert cli(tmp_path, 'status', '--line').stdout == 'WUWEI gate waiting | pages 0\n'
    data = four_seats(tmp_path / 'b', monkeypatch)
    assert status.line(data).startswith('WUWEI 1 building')
    assert status.line({**data, 'restart': STALE}).startswith('WUWEI restart Claude Code')
    assert status.line({**data, 'gate_approved': False, 'plan': True}).startswith('WUWEI gate waiting |')


def test_a_narrow_line_cuts_the_roles_then_drops_whole_tokens(tmp_path, monkeypatch):
    from wuwei.commands import status
    data = four_seats(tmp_path, monkeypatch)
    assert status.line(data, 70) == (
        'WUWEI 1 building · seats 4/1 (lead, arch, quality, security) | pages 0')
    assert status.line(data, 61) == 'WUWEI 1 building · seats 4/1 (lead, arch, +2 more) | pages 0'
    assert status.line(data, 56) == 'WUWEI 1 building · seats 4/1 (lead, +3 more) | pages 0'
    assert status.line(data, 47) == 'WUWEI 1 building | pages 0'
    assert status.line(data, 26) == 'WUWEI 1 building | pages 0'
    assert status.line(data, 22) == 'WUWEI 1 building'
    assert status.line(data, 5) == 'WUWEI 1 building'
    assert status.line({**data, 'restart': STALE}, 5) == 'WUWEI ' + STALE.split(' (plugin')[0]


SAMPLE = {'planned': 5, 'spec': 1, 'implement': 1, 'gate': 1, 'raised': 1, 'merged': 3}


def sample_day(tmp_path, monkeypatch, phases=SAMPLE):
    """Issue 641: cap 3, one builder seat, the day's items across the phases."""
    return {**four_seats(tmp_path, monkeypatch), 'cap': 3, 'phases': dict(phases),
            'running': [('2026-09-28T09:10:00+02:00', 'builder', 'ITEM-1')]}


def test_issue_641_the_line_counts_the_days_items_in_words(tmp_path, monkeypatch):
    import re
    from wuwei.commands import status
    data = sample_day(tmp_path, monkeypatch)
    assert status.line(data) == (
        'WUWEI 5 planned · 2 building · 2 in review · 3 shipped · seats 1/3 (builder) | pages 0')
    for text in (status.line(data),):
        assert all(text[:match.start()].endswith('seats ') for match in re.finditer(r'\d+/\d+', text)), text


def test_issue_641_parked_and_escalated_follow_shipped(tmp_path, monkeypatch):
    from wuwei.commands import status
    data = sample_day(tmp_path, monkeypatch, {**SAMPLE, 'escalated': 1, 'parked': 1, 'odd': 2})
    assert '3 shipped · 1 parked · 1 escalated · 2 odd · seats 1/3' in status.line(data, 10 ** 6)


def test_status_line_width_flag(tmp_path):
    seats = {role: {'status': 'running', 'role': role, 'item': 'ITEM-1'} for role in ROLES}
    day(tmp_path, {'cap': 1, 'gate_approved': True, 'items': {}, 'seats': seats})
    result = cli(tmp_path, 'status', '--line', '--width', '42')
    assert result.returncode == 0, result.stderr
    assert result.stdout == 'WUWEI seats 4/1 (lead, +3 more) | pages 0\n'
    assert cli(tmp_path, 'status', '--line', '--width', '40').stdout == 'WUWEI seats 4/1 (+4 more) | pages 0\n'
    assert cli(tmp_path, 'status', '--line', '--width', 'x').returncode == 2


def test_status_without_the_line_flag_is_refused(tmp_path):
    day(tmp_path)
    result = cli(tmp_path, 'status')
    assert (result.returncode, result.stdout) == (2, '') and '--line' in result.stderr


def at(minutes):
    """The timestamp this many minutes before NOW."""
    from datetime import datetime, timedelta
    return (datetime.fromisoformat(NOW) - timedelta(minutes=minutes)).isoformat()


def scan_day(root, monkeypatch, events=(), raw=''):
    """#786: a day with config.toml, rewritten in place on each call."""
    monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
    monkeypatch.setenv('WUWEI_NOW', NOW)
    directory = root / '.wuwei/days/2026-09-28'
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'state.json').write_text(json.dumps({'cap': 1, 'items': {}}))
    (directory / 'events.jsonl').write_text(raw + ''.join(json.dumps(e) + '\n' for e in events))
    (root / '.wuwei/config.toml').write_text('')
    return directory


def read_failed(pr, minutes):
    return {'kind': 'watch: read-failed', 'payload': {'pr': pr, 'reason': 'could not read'}, 'ts': at(minutes)}


def tracker(item, minutes=0, exit=2):
    payload = {'item': item, 'exit': exit} if exit == 0 else {'item': item, 'exit': exit, 'reason': 'label not found'}
    return {'kind': 'tracker.call', 'payload': payload, 'ts': at(minutes)}


def test_repeats_fold_into_one_row_per_subject(tmp_path, monkeypatch):
    from wuwei.commands import status
    events = [read_failed('acme/widget#1', minutes) for minutes in range(49, -1, -1)]
    directory = scan_day(tmp_path, monkeypatch, events)
    rows = [row for row in status.attention(directory) if row['source'] == 'watch: read-failed']
    assert [(row['count'], row['ts']) for row in rows] == [(50, at(0))]
    scan_day(tmp_path, monkeypatch, events + [read_failed('acme/widget#2', 30)] * 25)
    rows = [row for row in status.attention(directory) if row['source'] == 'watch: read-failed']
    assert sorted(row['count'] for row in rows) == [25, 50]


def test_a_later_silent_event_clears_its_subject(tmp_path, monkeypatch):
    from wuwei.commands import status
    directory = scan_day(tmp_path, monkeypatch, [tracker('A', 3), tracker('B', 2), tracker('A', 1, exit=0)])
    rows = [row for row in status.attention(directory) if row['source'] == 'tracker.call']
    assert len(rows) == 1 and rows[0]['count'] == 1 and rows[0]['ts'] == at(2)


def test_unreadable_lists_and_pages(tmp_path, monkeypatch):
    from wuwei.commands import status
    warning = {'kind': 'hook.warning', 'payload': {'reason': ['a', 'b']}, 'ts': at(1)}
    finding = {'kind': 'security.finding', 'payload': {}, 'ts': at(1)}
    directory = scan_day(tmp_path, monkeypatch, [{'kind': 'x', 'ts': at(5)}, warning, warning, finding, finding],
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
    directory = scan_day(tmp_path, monkeypatch, [gap] * 3 + [untraced] * 3)
    assert sum(row['count'] for row in status.attention(directory) if row['source'] == 'traces.gap') == 3
    probes = {'state': {'result': 'ok', 'value': 'ok'}, 'planner': {'result': 'ok', 'value': 'ok'},
              'seats': {'result': 'ok', 'value': 'none stuck'}}
    rows = {row['name']: row['value'] for row in doctor._day(tmp_path, workspace.load_config(tmp_path), probes)}
    assert rows['traces'] == '3 gaps today'
    assert rows['untraced subagents'] == '3 stopped with no seat today'


# Attention rows (moved from test_quiet_sweeps.py with the watch, #847).

@pytest.fixture
def attention_root(tmp_path, monkeypatch):
    from wuwei import state
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00+00:00')
    state._write_state(lambda data: None, tmp_path)
    return tmp_path


def test_attention_shows_current_conditions(attention_root):
    from wuwei import state, workspace
    from wuwei.commands.status import attention
    root = attention_root
    state.append_event('decision.one_way', {'blocking': False}, root)
    state.append_event('work.outside_goals', {}, root)
    rows = attention(workspace.day_dir(root))
    assert {row['source'] for row in rows} == {'decision.one_way', 'work.outside_goals'}


def test_scanner_findings_are_one_row_per_chain_class(attention_root):
    # #870: doctor lists a scanner finding once per chain (or rule), with its count.
    from wuwei import state, workspace
    from wuwei.commands.status import attention
    root = attention_root
    for chain, sessions in ((['Read', 'WebFetch'], 'abc'), (['Bash', 'WebFetch'], 'de')):
        for session in sessions:
            state.append_event('scanner.finding', {'chain': chain, 'risk_level': 'critical', 'session_id': session,
                                                   'reason': 'scanner chain ' + ' -> '.join(chain)}, root)
    for _ in range(2):
        state.append_event('scanner.finding', {'tier': 'page', 'source': 'tool_trace', 'rule': 'security.honeytoken'}, root)
    rows = [row for row in attention(workspace.day_dir(root)) if row['source'] == 'scanner.finding']
    assert sorted((row['reason'], row['count'], row['tier']) for row in rows) == [
        ('scanner chain Bash -> WebFetch', 2, 'page'), ('scanner chain Read -> WebFetch', 3, 'page'),
        ('scanner.finding', 2, 'page')]


def test_merge_policy_warning_is_per_pr_and_clears_on_merge(attention_root):
    from wuwei import state, workspace
    from wuwei.commands.status import attention
    root = attention_root
    directory = workspace.day_dir(root)
    for _ in range(2):
        state.append_event('merge.policy_blocked', {'pr': 'x/y#1'}, root)
    assert len(attention(directory)) == 1
    state.append_event('pr.action', {'pr': 'x/y#1', 'tier': 'silent', 'state': 'approved'}, root)
    assert len(attention(directory)) == 1
    state.append_event('pr.action', {'pr': 'x/y#1', 'tier': 'silent', 'state': 'merged'}, root)
    assert attention(directory) == []


def test_attention_on_a_workspace_without_day_state_lists_nothing(tmp_path, monkeypatch):
    from wuwei import workspace
    from wuwei.commands.status import attention
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    assert attention(workspace.day_dir(tmp_path)) == []


class _Broken:
    def isatty(self):
        return False

    def read(self):
        raise OSError('stdin closed')


def test_status_line_saves_claude_window_readings(tmp_path, monkeypatch, capsys):
    # #845: the status line stdin's rate_limits are the Claude readings; the line never changes.
    import io
    import time
    from wuwei.__main__ import main
    day(tmp_path, {'cap': 2, 'gate_approved': True, 'items': {'A': {'phase': 'implement'}}})

    def pipe(text, close=True):
        read, write = os.pipe()
        os.write(write, text.encode())
        if close:
            os.close(write)
        return os.fdopen(read)
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', NOW)
    cache = tmp_path / '.wuwei/windows.json'

    def run(stdin):
        monkeypatch.setattr(sys, 'stdin', stdin)
        assert main(['status', '--line']) == 0
        return capsys.readouterr().out
    plain = run(pipe(''))
    started = time.monotonic()
    assert run(pipe('', close=False)) == plain and time.monotonic() - started < 2  # F8: an open pipe never hangs
    for stdin in (pipe('{"model": {}}'), pipe('{not json'), pipe('[1]'), pipe('{"rate_limits": 7}'),
                  io.StringIO('{"rate_limits": {}}'), _Broken()):
        assert run(stdin) == plain and not cache.exists()
    payload = {'rate_limits': {'five_hour': {'used_percentage': 42, 'resets_at': 1790611200},
                               'seven_day': {'used_percentage': 18.5, 'resets_at': 1791043200}}}
    assert run(pipe(json.dumps(payload))) == plain
    assert json.loads(cache.read_text()) == {'claude': {
        'five_hour': {'used_percent': 42, 'resets_at': '2026-09-28T16:00:00+00:00'},
        'seven_day': {'used_percent': 18.5, 'resets_at': '2026-10-03T16:00:00+00:00'}}}
