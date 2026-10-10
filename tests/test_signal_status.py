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
    directory = day(tmp_path, state_data, [
        {'kind': kind, 'payload': {}, 'ts': NOW}
        for kind in ('security.finding', 'decision.one_way', 'watch: clock')])
    (tmp_path / '.wuwei/config.toml').write_text('')
    before = {p.name: p.read_bytes() for p in directory.iterdir()}
    line = cli(tmp_path, 'status', '--line')
    structured = cli(tmp_path, 'status', '--json')
    full = cli(tmp_path, 'status')
    assert line.returncode == structured.returncode == full.returncode == 0
    assert line.stdout.count('\n') == 1
    assert 'pages 1' in line.stdout and 'nudges 1' in line.stdout
    assert '2 building' in line.stdout
    assert 'reply 2026-09-28T13:00:00+02:00' in full.stdout
    assert 'meeting 2026-09-28T16:00:00+02:00' in full.stdout
    data = json.loads(structured.stdout)
    # #562: the line skips these; status and --json keep them.
    assert {'cruise', 'plugin', 'template', 'next_meeting', 'next_reply_due', 'sessions', 'seats'} <= data.keys()
    assert 'sessions 0' in full.stdout and 'plugin ' in full.stdout
    assert data['pages'] == 1 and data['nudges'] == 1
    assert data['phases']['spec'] == 1 and data['cap'] == 2
    assert data['next_reply_due'] == '2026-09-28T13:00:00+02:00'
    assert {p.name: p.read_bytes() for p in directory.iterdir()} == before


def test_status_line_names_running_seats_and_checks(tmp_path, monkeypatch, capsys):
    from wuwei.__main__ import main
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
        assert main(['status']) == 0
        full = capsys.readouterr().out
        assert main(['status', '--json']) == 0
        running = json.loads(capsys.readouterr().out)['running']
    finally:
        child.kill()
        child.wait()
    assert 'seats 3/2 (reviewer, builder, builder)' in line and 'running' not in line
    assert ('running reviewer D start unrecorded\nrunning builder A 09:10\nrunning builder B 09:20\n'
            'running checks C 09:25\n') in full
    assert running == [['', 'reviewer', 'D'],
                       ['2026-09-28T09:10:00+02:00', 'builder', 'A'],
                       ['2026-09-28T09:20:00+02:00', 'builder', 'B'],
                       ['2026-09-28T09:25:00+02:00', 'checks', 'C']]
    state_file = directory / 'state.json'
    state_file.write_text(json.dumps({'cap': 2, 'gate_approved': True, 'items': {}}))
    assert main(['status']) == 0
    assert 'running' not in capsys.readouterr().out


def test_status_counts_every_nonzero_phase(tmp_path, monkeypatch, capsys):
    from wuwei.__main__ import main
    day(tmp_path, {'cap': 2, 'items': {'A': {'phase': 'delta'}, 'B': {'phase': 'merged'}}})
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', NOW)
    assert main(['status', '--line']) == 0
    line = capsys.readouterr().out
    assert '1 in review' in line and '1 shipped' in line and 'building' not in line
    assert main(['status', '--json']) == 0
    assert json.loads(capsys.readouterr().out)['phases'] == {'delta': 1, 'merged': 1}


@pytest.mark.parametrize('recorded,shown', [({'acme/widget#7': [], 'acme/widget#8': ['alice']}, True),
                                             ({'acme/widget#8': ['alice']}, False)])
def test_status_line_names_a_solo_pr(tmp_path, monkeypatch, capsys, recorded, shown):
    from wuwei.__main__ import main
    day(tmp_path, {'cap': 1, 'items': {}, 'pr_reviewers': recorded})
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', NOW)
    assert main(['status']) == 0
    assert ('reviewers: none (solo)' in capsys.readouterr().out) is shown


@pytest.mark.parametrize('name', ['state.json', 'state.snapshot.json'])
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
    assert result.stdout.startswith('WUWEI no plan yet | pages 0 · nudges 0')
    result = cli(tmp_path, 'status', '--json')
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['gate_approved'] is False


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


def test_next_due_uses_instant_across_offsets(tmp_path):
    day(tmp_path, {'items': {}, 'cap': 1,
                   'reply_obligations': [{'due': '2026-09-28T11:30:00+02:00'},
                                         {'due': '2026-09-28T10:00:00+00:00'}]})
    result = cli(tmp_path, 'status', '--json')
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['next_reply_due'] == '2026-09-28T11:30:00+02:00'


def test_reply_due_at_1500_appears_in_status_line(tmp_path):
    day(tmp_path, {'items': {}, 'cap': 1,
                   'reply_obligations': [{'person': 'Pat', 'due': '2026-09-28T15:00:00+02:00'}]})
    result = cli(tmp_path, 'status')
    assert result.returncode == 0, result.stderr
    assert 'reply 2026-09-28T15:00:00+02:00' in result.stdout
    assert 'meeting unmeasured' in result.stdout


def test_status_reads_next_meeting_from_configured_calendar(tmp_path, monkeypatch):
    from wuwei import registry
    from wuwei.commands.status import snapshot
    directory = day(tmp_path, {'items': {}, 'cap': 1})
    (tmp_path / '.wuwei/config.toml').write_text('[adapters]\ncalendar = "ics"\n')
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T12:00:00+02:00')
    class Calendar:
        def events(self, since, until, root=None):
            return registry.Result(0, [
                {'start': '2026-09-28T17:00:00+02:00', 'summary': 'Later'},
                {'start': '2026-09-28T14:00:00+02:00', 'summary': 'Soon'}])
    monkeypatch.setattr(registry, 'load', lambda kind, config: Calendar())
    assert snapshot(directory)['next_meeting'] == '2026-09-28T14:00:00+02:00'


def test_status_calendar_failure_is_unmeasured(tmp_path, monkeypatch):
    from wuwei import registry
    from wuwei.commands.status import snapshot
    directory = day(tmp_path, {'items': {}, 'cap': 1}, [{'kind': 'security.finding'}])
    (tmp_path / '.wuwei/config.toml').write_text('[adapters]\ncalendar = "ics"\n')
    class Calendar:
        def events(self, since, until, root=None):
            return registry.Result(2, reason='calendar unavailable')
    monkeypatch.setattr(registry, 'load', lambda kind, config: Calendar())
    result = snapshot(directory)
    assert result['next_meeting'] is None
    assert result['pages'] == 1
    monkeypatch.setenv('WUWEI_CALENDAR_URL', 'invalid-url')
    line = cli(tmp_path, 'status')
    assert line.returncode == 0, line.stderr
    assert 'pages 1' in line.stdout
    assert 'meeting unmeasured' in line.stdout


@pytest.mark.parametrize('kind', ['state.set', 'state.transition', 'seat started', 'seat stopped',
                                  'plan.approved', 'state.import', 'build.started',
                                  'build.launched', 'build.checked', 'verdict.rejected'])
def test_routine_progress_is_silent(kind):
    from wuwei.signal import classify
    assert classify({'kind': kind}, {}) == ('silent', 'Work')


def test_tracker_none_is_silent_but_tracker_failure_nudges():
    from wuwei.signal import classify
    event = {'kind': 'tracker.call', 'payload': {'exit': 2, 'reason': 'tracker adapter is none'}}
    assert classify(event, {})[0] == 'silent'
    event['payload']['reason'] = 'tracker call unmeasured: OSError'
    assert classify(event, {})[0] == 'nudge'


def test_emitted_kinds_have_intended_tiers():
    from wuwei.signal import classify
    emitted = emitted_kinds(sorted((ROOT / 'cli/wuwei').rglob('*.py')))
    emitted.update(['retro.gap', 'retro.captured', 'security.canary', 'security.honeytoken'])
    emitted.update(['draft.sent', 'draft.failed'])  # dynamic final outcome
    emitted.update(['draft.sending', 'draft.approved'])  # drafts.approve picks its writer kind
    emitted.add('state.write')  # default writer kind
    emitted.update(['watch: observation', 'session: compact'])  # writer default and locked append
    emitted.update(['remote.started', 'remote.resumed'])  # one conditional writer kind
    emitted.update(['spec.step', 'spec.skipped', 'spec.warned'])  # specmode.once(kind)
    expected = {'draft.created': 'nudge', 'draft.sending': 'silent', 'draft.approved': 'silent',
                'worktree.hooks_skipped': 'nudge',
                'draft.sent': 'silent', 'draft.dropped': 'silent', 'draft.failed': 'nudge',
                'mcp.finding': 'nudge', 'mcp.checked': 'nudge', 'mcp.decided': 'silent',
                'security.canary': 'page', 'security.honeytoken': 'page',
                'scanner.finding': 'page', 'state.write': 'silent', 'state.set': 'silent',
                'state.transition': 'silent', 'seat stopped': 'silent',
                'seat launched': 'silent', 'brief written': 'silent',
                'brief.pack': 'silent', 'brief.answer': 'silent',
                'session.seen': 'silent', 'session.rotated': 'silent', 'item.claimed': 'silent',
                'worktree.adopted': 'silent',
                'fast_checks.record': 'silent', 'retro.captured': 'silent',
                'seat.usage': 'silent', 'cap.derived': 'silent', 'build.parked': 'nudge',
                'build.fix_opened': 'silent', 'pr.action.done': 'silent',
                'pr.action.decision': 'silent',
                'retro.gap': 'nudge', 'seat stop unmatched': 'nudge',
                'traces.gap': 'nudge', 'hook.refusal': 'silent',
                'guard.would_refuse': 'silent', 'config.newer_template': 'nudge',
                'hook.warning': 'nudge',
                'verdict.rejected': 'silent', 'decision.rejected': 'nudge',
                    'decision.decided': 'silent', 'decision.routed': 'silent',
                    'decision.digest': 'silent', 'decision.replied': 'silent', 'decision.escalated': 'silent',
                'adapter: none': 'silent', 'reply: acknowledged': 'silent',
                'reply: thread_posted': 'silent', 'pr.raised': 'silent',
                'pr.claimed': 'silent',
                'pr.reviewers_selected': 'silent', 'pr.review_posted': 'silent',
                'reviewer.unresolved': 'silent',
                'watch: sweep': 'nudge', 'watch: clock': 'silent', 'heartbeat: clock': 'silent',
                'watch: heartbeat': 'silent', 'watch: observation': 'silent',
                'watch: read-failed': 'nudge', 'pr.changed': 'nudge',
                'session: compact': 'silent', 'session: wake-seen': 'silent',
                'plan.session': 'silent', 'gate.asked': 'silent', 'pr.disposition': 'silent', 'pr.action': 'nudge',
                'day.close_requested': 'silent', 'day.closed': 'silent', 'next.action': 'silent', 'merge.unmeasured': 'nudge',
                'merge.metric': 'silent', 'merge.policy_blocked': 'nudge', 'base.red': 'page',
                'gate.received': 'silent', 'gate.tiered': 'silent', 'discovery.requested': 'silent',
                'discovery.intake': 'silent', 'plan.added': 'silent',
                'plan.proposed': 'nudge', 'build.requested': 'nudge',
                'tracker.call': 'nudge',
                'tracker.created': 'silent', 'tracker.skipped': 'silent', 'tracker.folded': 'silent',
                'tracker.logged': 'silent', 'plan.set': 'silent',
                'discovery.unmeasured': 'nudge', 'steward.notes': 'nudge',
                'steward.run': 'silent', 'steward.due': 'nudge',
                'steward.acknowledged': 'silent', 'inbox.redacted': 'silent',
                'memory.folded': 'silent', 'memory.consolidated': 'silent',
                'listen: clock': 'silent', 'listen: wake': 'silent',
                'remote.pending': 'silent', 'remote.started': 'silent',
                'remote.resumed': 'silent', 'remote.stopped': 'silent',
                'remote.ignored': 'silent', 'remote.refused': 'page', 'remote.acknowledged': 'silent',
                'remote.confirmed': 'silent', 'calibration.drift': 'nudge',
                'shepherd.dispatched': 'silent', 'shepherd.finished': 'nudge',
                'shepherd.overnight': 'silent', 'shepherd.swept': 'silent', 'pr.notified': 'silent',
                'negotiation.loop': 'nudge', 'negotiation.notified': 'silent',
                'decision.waited': 'nudge', 'doctor.fixed': 'silent', 'outward.ai_tells': 'silent', 'outward.lint': 'silent',
                'outward.unknown_tool': 'nudge', 'outward.to_owner': 'silent',
                'spec.step': 'silent', 'spec.skipped': 'silent', 'spec.override': 'silent',
                'spec.warned': 'nudge', 'docs.set': 'silent', 'docs.written': 'silent',
                'docs.exempt': 'silent', 'outbound.proposed': 'silent', 'outbound.learned': 'silent', 'outbound.thread': 'silent',
                'config.set': 'silent',
                'grant.asked': 'silent', 'grant.used': 'silent', 'grant.revoked': 'silent',
                'decision.reversed': 'nudge', 'decision.notified': 'silent', 'cruise.carded': 'silent', 'pace.set': 'silent', 'pace.carded': 'silent', 'decision.shadow': 'silent',
                'undo.rehearsed': 'silent', 'undo.done': 'silent',
                'cruise.burn': 'nudge',
                **{f'telemetry.{name}': 'nudge' if name == 'ready' else 'silent' for name in TELEMETRY}}
    assert emitted == set(expected)
    for kind, tier in expected.items():
        assert classify({'kind': kind}, {})[0] == tier
    assert classify({'kind': 'build.iteration'}, {})[0] == 'silent'
    assert classify({'kind': 'shepherd.finished', 'payload': {'exit': 0}}, {})[0] == 'silent'
    assert classify({'kind': 'shepherd.finished', 'payload': {'exit': 1}}, {})[0] == 'nudge'


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
    ('security.finding', 'security.resolved', 1),
    ('base.red', 'base.green', 1),
    ('dead_man.hit', 'dead_man.cleared', 1),
    ('budget.cap', 'budget.cleared', 1),
    ('day.blocked', 'day.unblocked', 1),
    ('decision.one_way', 'decision.resolved', 1),
    ('person.ask', 'person.answered', 1),
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
                               'cap': 1, 'seats': {'builder': {'item': 'A', 'status': 'running'}}},
                    [{'kind': 'watch: clock', 'payload': {}, 'ts': NOW}])
    (tmp_path / '.wuwei/config.toml').write_text('')
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
    assert json.loads(result.stdout.splitlines()[1])['statusLine']['command'] == (
        shlex.quote(str(ROOT / 'bin/wuwei')) + ' status --line')


@pytest.mark.parametrize('kind,tier', [('created', 'nudge'), ('sending', 'silent'),
                                      ('sent', 'silent'), ('dropped', 'silent'), ('failed', 'nudge')])
def test_draft_events_use_decisions_lane(kind, tier):
    from wuwei.signal import classify
    assert classify({'kind': 'draft.' + kind}, {}) == (tier, 'Decisions')


ROUTED = {'D-2': {'reversibility': 'unsure', 'recommendation': 'defer'}}


@pytest.mark.parametrize('outcomes,count', [
    ({}, 1),
    ({'D-2': {'decided_by': 'owner', 'option': 'A', 'outcome': 'A'}}, 0),
])
def test_routed_decision_nudges_until_answered(tmp_path, monkeypatch, capsys, outcomes, count):
    from wuwei.__main__ import main
    day(tmp_path, {'cap': 1, 'items': {'A': {'phase': 'raised'}}, 'decision_routes': ROUTED,
                   'decision_outcomes': outcomes})
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', NOW)
    assert main(['nudges', '--json']) == 0
    rows = [row for row in json.loads(capsys.readouterr().out) if row['source'] == 'decision.pending']
    assert rows == [{'tier': 'nudge', 'source': 'decision.pending', 'lane': 'Decisions',
                     'reason': 'D-2 pending owner decision'}][:count]
    assert main(['status', '--line']) == 0
    assert f'nudges {count}' in capsys.readouterr().out


def test_invalid_decision_ledger_is_unmeasured(tmp_path, monkeypatch, capsys):
    from wuwei.__main__ import main
    day(tmp_path, {'cap': 1, 'items': {}, 'decision_routes': ['D-2']})
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', NOW)
    assert main(['nudges', '--json']) == 2
    capsys.readouterr()
    assert main(['status', '--line']) == 2
    assert capsys.readouterr().out == 'WUWEI ? unmeasured\n'


@pytest.mark.parametrize('outcomes', [{}, {'D-2': {'decided_by': 'owner', 'option': 'A', 'outcome': 'A'}}])
def test_issue_acceptance_a_phone_answer_shows_on_the_host(tmp_path, monkeypatch, capsys, outcomes):
    from wuwei.__main__ import main
    replies = [{'kind': 'decision.replied', 'ts': '2026-09-28T11:00:00+02:00',
                'payload': {'id': 'D-2', 'option': option}} for option in 'AB']
    day(tmp_path, {'cap': 1, 'items': {}, 'decision_routes': ROUTED, 'decision_outcomes': outcomes},
        replies)
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', NOW)
    reason = 'D-2 answered from the phone: option A, confirm with wuwei decide D-2 A'
    expected = [] if outcomes else [reason]
    assert main(['nudges', '--json']) == 0
    rows = [row for row in json.loads(capsys.readouterr().out) if 'D-2' in row['reason']]
    assert rows == [{'tier': 'nudge', 'source': 'decision.answered', 'lane': 'Decisions',
                     'reason': reason}][:len(expected)]
    assert main(['status']) == 0
    text = capsys.readouterr().out
    assert ('phone answers 1' in text) == bool(expected) and reason not in text
    assert f'nudges {len(expected)}' in text
    assert main(['status', '--json']) == 0
    assert json.loads(capsys.readouterr().out)['answered'] == expected


def test_issue_acceptance_four_phone_answers_are_one_status_segment(tmp_path, monkeypatch, capsys):
    from wuwei.__main__ import main
    ids = [f'D-{n}' for n in range(1, 5)]
    replies = [{'kind': 'decision.replied', 'ts': '2026-09-28T11:00:00+02:00',
                'payload': {'id': identifier, 'option': option}} for identifier, option in zip(ids, 'ABAA')]
    routes = {identifier: {'reversibility': 'two-way', 'recommendation': 'A'} for identifier in ids}
    day(tmp_path, {'cap': 1, 'items': {}, 'decision_routes': routes}, replies)
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', NOW)
    reasons = [f'{identifier} answered from the phone: option {option}, '
               f'confirm with wuwei decide {identifier} {option}' for identifier, option in zip(ids, 'ABAA')]
    assert main(['status']) == 0
    text = capsys.readouterr().out.strip()
    assert text.count('phone answers') == 1 and 'phone answers 4' in text
    assert 'answered from the phone' not in text
    assert main(['nudges', '--json']) == 0
    rows = [row['reason'] for row in json.loads(capsys.readouterr().out) if row['source'] == 'decision.answered']
    assert rows == reasons
    assert main(['status', '--json']) == 0
    assert json.loads(capsys.readouterr().out)['answered'] == reasons


def test_status_json_shows_recorded_tiers(tmp_path, monkeypatch, capsys):
    from wuwei.__main__ import main
    light = {'tier': 'light', 'computed': 'light', 'reasons': ['3 changed lines within light_max_lines 100'],
             'roles': ['quality']}
    day(tmp_path, {'cap': 1, 'items': {'A': {'phase': 'gate', 'gates': light}, 'B': {'phase': 'gate'}}})
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', NOW)
    assert main(['status', '--json']) == 0
    assert json.loads(capsys.readouterr().out)['gates'] == {'A': light}


def beat_line(health, page='', ts=NOW):
    return {'kind': 'heartbeat: clock', 'ts': ts,
            'payload': {'health': health, 'probes': {}, 'drift': [], 'page': page, 'ping': 'off'}}


def status_of(tmp_path, monkeypatch, events):
    from wuwei.commands import status
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', NOW)
    directory = day(tmp_path, {'items': {}, 'cap': 1, 'gate_approved': True}, events)
    (tmp_path / '.wuwei/config.toml').write_text('')
    data = status.snapshot(directory)
    return data, status.full(data), status.attention(directory)


CLOCK = {'kind': 'watch: clock', 'payload': {}, 'ts': NOW}
PAGE_TEXT = 'heartbeat integrity failed: page: plugin integrity: cli/x.py changed after the cached verdict'


def test_heartbeat_health_on_the_status_line(tmp_path, monkeypatch):
    data, line, rows = status_of(tmp_path, monkeypatch, [CLOCK, beat_line('ok')])
    assert data['health'] == 'ok' and 'health ok' in line and 'pages 0' in line
    assert not [row for row in rows if row['source'] == 'heartbeat']


def test_degraded_heartbeat_pages_once_and_clears(tmp_path, monkeypatch):
    data, line, rows = status_of(tmp_path, monkeypatch, [CLOCK, beat_line('degraded', PAGE_TEXT),
                                                         beat_line('degraded', PAGE_TEXT)])
    assert 'health degraded' in line and 'pages 1' in line
    assert [(row['tier'], row['reason']) for row in rows if row['source'] == 'heartbeat'] == [
        ('page', PAGE_TEXT)]


def test_ok_heartbeat_clears_the_page(tmp_path, monkeypatch):
    data, line, rows = status_of(tmp_path, monkeypatch, [CLOCK, beat_line('degraded', PAGE_TEXT),
                                                         beat_line('ok')])
    assert 'health ok' in line and 'pages 0' in line


@pytest.mark.parametrize('events', [
    [beat_line('degraded', PAGE_TEXT, ts='2026-09-28T09:00:00+02:00'),
     {'kind': 'watch: clock', 'payload': {}, 'ts': '2026-09-28T09:00:00+02:00'}],
    [CLOCK, beat_line('fine')],
    [CLOCK, {'kind': 'heartbeat: clock', 'payload': 'broken', 'ts': NOW}],
])
def test_unmeasured_heartbeat_has_no_page(tmp_path, monkeypatch, events):
    data, line, rows = status_of(tmp_path, monkeypatch, events)
    assert data['health'] == 'unmeasured' and 'health unmeasured' in line
    assert not [row for row in rows if row['source'] == 'heartbeat']


def test_no_heartbeat_line_has_no_health_part(tmp_path, monkeypatch):
    data, line, _ = status_of(tmp_path, monkeypatch, [CLOCK])
    assert data['health'] is None and 'health' not in line


def changed(summary=None, pr='example/project#7'):
    payload = {'pr': pr, 'fields': ['checks']}
    if summary:
        payload['summary'] = summary
    return {'kind': 'pr.changed', 'payload': payload, 'ts': NOW}


def test_pr_changed_nudge_is_first_carries_the_summary_and_clears_at_wake_seen(tmp_path, monkeypatch):
    events = [CLOCK, {'kind': 'build.parked', 'payload': {'reason': 'older'}, 'ts': NOW},
              changed('PR example/project#7: check ci failed'),
              changed('PR example/project#7: check ci passed')]
    data, line, rows = status_of(tmp_path, monkeypatch, events)
    assert (rows[0]['source'], rows[0]['reason']) == ('pr.changed', 'PR example/project#7: check ci passed')
    assert sum(row['source'] == 'pr.changed' for row in rows) == 1
    assert 'prs 1 changed' in line and 'nudges 2' in line
    seen = {'kind': 'session: wake-seen', 'payload': {'at': NOW}, 'ts': NOW}
    data, line, rows = status_of(tmp_path / 'b', monkeypatch, [*events, seen])
    assert [row['source'] for row in rows] == ['build.parked']
    assert 'prs' not in line


def test_old_pr_changed_without_summary_names_the_fields(tmp_path, monkeypatch):
    _, _, rows = status_of(tmp_path, monkeypatch, [CLOCK, changed()])
    assert rows[0]['reason'] == 'example/project#7 changed: checks'


def test_negotiation_loop_tiers():
    from wuwei.signal import classify
    loop = {'kind': 'negotiation.loop', 'payload': {'item': 'alpha', 'past_goal': False}}
    assert classify(loop, {}) == ('nudge', 'Work')
    loop['payload']['past_goal'] = True
    assert classify(loop, {}) == ('page', 'Work')
    assert classify({'kind': 'negotiation.notified'}, {})[0] == 'silent'
    assert classify({'kind': 'decision.waited'}, {}) == ('nudge', 'Decisions')


def test_status_line_counts_loops(tmp_path, monkeypatch):
    reason = 'alpha is going back and forth: 2 records'
    loop = {'kind': 'negotiation.loop', 'ts': NOW,
            'payload': {'item': 'alpha', 'past_goal': False, 'reason': reason}}
    data, line, rows = status_of(tmp_path, monkeypatch, [loop])
    assert data['loops'] == 1 and ' · loops 1' in line
    assert [row['reason'] for row in rows if row['source'] == 'negotiation.loop'] == [reason]


def test_status_line_without_loops(tmp_path, monkeypatch):
    data, line, _ = status_of(tmp_path, monkeypatch, [])
    assert data['loops'] == 0 and 'loops' not in line


def test_restart_on_the_status_line(tmp_path, monkeypatch):
    from wuwei.commands import status
    data, line, _ = status_of(tmp_path, monkeypatch, [CLOCK])
    assert data['restart'] == '' and 'restart' not in line
    text = 'restart Claude Code: hooks 0.11.0 still running (plugin 0.12.0 installed)'
    assert status.line({**data, 'restart': text}).startswith(
        'WUWEI restart Claude Code: hooks 0.11.0 still running | seats 0/1 | pages 0')
    assert status.full({**data, 'restart': text}).startswith(f'WUWEI {text}\n')


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
    expected = status.scan(directory)
    seen = []
    monkeypatch.setattr(status, 'json', SimpleNamespace(
        loads=lambda line, **kw: seen.append(line) or json.loads(line, **kw), dumps=json.dumps))
    rows, watch, *_ = status.scan(directory)
    assert len(seen) == 2 and not any('state.write' in line for line in seen)
    assert (rows, watch, *_) == expected
    assert any(row['source'] == 'hook.warning' and row['reason'] == 'lint finding' for row in rows)


def test_scan_decodes_torn_silent_line(tmp_path, monkeypatch):
    from wuwei.commands import status
    directory = day(tmp_path, events=[])
    (directory / 'events.jsonl').write_text('{"kind": "state.write", "payload": {"a": 1}\n')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', NOW)
    rows, *_ = status.scan(directory)
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
    rows, *_ = status.scan(directory)
    assert [row['source'] for row in rows].count('hook.warning') == 2
    assert not any(row['source'] == 'unreadable event' for row in rows)
    path.write_bytes(b'{"kind": "hook.warning", "payload": {"reason": "\xff"}, "ts": "' + NOW.encode() + b'"}\n')
    with pytest.raises(UnicodeDecodeError):
        status.scan(directory)


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
    skipped = status.scan(directory)
    monkeypatch.setattr(status, 'LINES', r'([^\n]*)\n?')
    assert skipped == status.scan(directory)
    assert [row['source'] for row in skipped[0]].count('hook.warning') == 3
    assert any(row['source'] == 'unreadable event' for row in skipped[0])


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
    assert 'nudges 0' in capsys.readouterr().out


def test_issue_acceptance_nudges_print_lines(tmp_path, monkeypatch, capsys):
    from wuwei.__main__ import main
    from wuwei.commands.status import attention
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', NOW)
    assert main(['nudges']) == 0
    assert capsys.readouterr().out == 'No open pages or nudges.\n'
    assert main(['nudges', '--json']) == 0
    assert capsys.readouterr().out == '[]\n'
    checked = {'kind': 'mcp.checked', 'payload': {'exit': 2}}
    events = [checked, checked, NONE_EVENT, NONE_EVENT,
              {'kind': 'decision.replied', 'ts': '2026-09-28T11:00:00+02:00',
               'payload': {'id': 'D-2', 'option': 'A'}},
              {'kind': 'build.parked', 'payload': {'reason': 'ITEM-1 parked'}}]
    directory = day(tmp_path, {'cap': 1, 'items': {}, 'decision_routes': {'D-1': {}, 'D-2': {}}}, events)
    expected = {
        'mcp.checked': 'nudge: The last MCP registry check did not pass or could not run (2 times). '
                       'Run: wuwei mcp check',
        'build.parked': 'nudge: ITEM-1 parked. Run: wuwei next',
        'decision.pending': 'nudge: D-1 pending owner decision. Run: wuwei decision show D-1',
        'decision.answered': 'nudge: D-2 answered from the phone: option A, '
                             'confirm with wuwei decide D-2 A'}
    rows = attention(directory)
    assert main(['nudges']) == 0
    assert capsys.readouterr().out.splitlines() == list(dict.fromkeys(expected[r['source']] for r in rows))
    assert main(['nudges', '--json']) == 0
    assert capsys.readouterr().out == json.dumps(rows, allow_nan=False) + '\n'
    assert [r['source'] for r in rows].count('mcp.checked') == 2
    (directory / 'events.jsonl').write_text('')
    (directory / 'state.json').write_text(json.dumps({'cap': 1, 'items': {}}))
    assert main(['nudges']) == 0
    assert capsys.readouterr().out == 'No open pages or nudges.\n'


def row_of(source, reason, tier='nudge'):
    return {'tier': tier, 'source': source, 'lane': 'Work', 'reason': reason}


@pytest.mark.parametrize('source,reason,expected', [
    ('item.escalated', 'ITEM-1', 'nudge: ITEM-1 is escalated and waits for you. Run: wuwei why ITEM-1'),
    ('draft.created', 'DR-1', 'nudge: An outward draft waits for owner approval. Run: bin/wuwei drafts'),
    ('watch: health', 'watch is dead', 'nudge: watch is dead. Run: wuwei doctor'),
    ('listen: health', 'listen is dead', 'nudge: listen is dead. Run: wuwei doctor'),
    ('watch: sweep:unmeasured', 'x', 'nudge: A sweep could not read a record (unmeasured). Run: wuwei doctor'),
    ('decision.answered', 'D-2 answered, confirm with decision outcome D-2 A',
     'nudge: D-2 answered, confirm with decision outcome D-2 A'),
    ('decision.pending', '', 'nudge: . Run: wuwei next'),
    ('build.parked', 'start with /wuwei:wuwei-plan', 'nudge: start with /wuwei:wuwei-plan'),
])
def test_nudge_line_actions(source, reason, expected):
    from wuwei.commands import nudges
    assert nudges.line(row_of(source, reason), 1) == expected


def test_nudge_page_and_nudge_stay_apart(tmp_path, monkeypatch, capsys):
    from wuwei.commands import nudges
    rows = [row_of('x', 'same'), row_of('x', 'same', 'page'), row_of('x', 'same')]
    monkeypatch.setattr(nudges, 'attention', lambda directory: rows)
    day(tmp_path, {'cap': 1, 'items': {}})
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', NOW)
    assert nudges.run(type('A', (), {'json': False})()) == 0
    assert capsys.readouterr().out.splitlines() == [
        'nudge: same (2 times). Run: wuwei next', 'page: same. Run: wuwei next']


def test_outward_ai_tells_is_silent_and_reserved(capsys):
    from wuwei.signal import classify
    from wuwei.__main__ import main
    assert classify({'kind': 'outward.ai_tells', 'payload': {}}, {})[0] == 'silent'
    assert main(['event', 'outward.ai_tells', '{}']) == 1
    assert 'humanize_lint' in capsys.readouterr().err


def test_outward_lint_is_silent_and_reserved(capsys):
    from wuwei.signal import classify
    from wuwei.__main__ import main
    assert classify({'kind': 'outward.lint', 'payload': {}}, {})[0] == 'silent'
    assert main(['event', 'outward.lint', '{}']) == 1
    assert 'check_lint' in capsys.readouterr().err


def test_outward_to_owner_is_silent_and_reserved(capsys):
    from wuwei.signal import classify
    from wuwei.__main__ import main
    assert classify({'kind': 'outward.to_owner', 'payload': {}}, {})[0] == 'silent'
    assert main(['event', 'outward.to_owner', '{}']) == 1
    assert 'check_tier' in capsys.readouterr().err


TELEMETRY = ('skipped', 'unsent', 'shared', 'ready', 'presented', 'off')


@pytest.mark.parametrize('name', TELEMETRY)
def test_telemetry_events_are_cli_only_and_quiet(tmp_path, monkeypatch, capsys, name):
    # #422, design 5.13: telemetry.ready is a nudge, the rest are silent; the CLI writes all six.
    from wuwei.__main__ import main
    from wuwei.signal import classify
    assert classify({'kind': f'telemetry.{name}'}, {})[0] == ('nudge' if name == 'ready' else 'silent')
    day(tmp_path, {})
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', NOW)
    assert main(['event', f'telemetry.{name}', '{}']) == 1
    assert 'written by wuwei telemetry or wuwei sweep' in capsys.readouterr().err


def test_status_line_shows_running_seats_per_goal(tmp_path):
    items = {'A': {'phase': 'implement', 'goal': 'G-1'}, 'B': {'phase': 'implement', 'goal': 'G-2'}}
    seats = {name: {'id': name, 'role': role, 'item': item, 'status': 'running'}
             for name, role, item in (('a-1', 'builder', 'A'), ('b-1', 'builder', 'B'),
                                      ('g-1', 'sentinel-arch', 'A'))}
    day(tmp_path, {'cap': 3, 'items': items, 'seats': seats, 'gate_approved': True})
    result = cli(tmp_path, 'status', '--line')
    assert result.returncode == 0, result.stderr
    assert 'seats 3/3 (builder, builder, sentinel-arch)' in result.stdout
    assert 'builders G-1 1, G-2 1' in cli(tmp_path, 'status').stdout  # no cap_bound: before #528
    (tmp_path / '.wuwei/days/2026-09-28/state.json').write_text(json.dumps(
        {'cap': 3, 'items': items, 'gate_approved': False}))
    assert 'seats' not in cli(tmp_path, 'status', '--line').stdout


def test_status_json_names_plan_decisions_and_versions(tmp_path):
    from wuwei import integrity
    routes = {'D-7': {'reversibility': 'unsure'}, 'D-8': {'reversibility': 'unsure'}}
    directory = day(tmp_path, {'cap': 1, 'items': {}, 'decision_routes': routes, 'decision_outcomes': {
        'D-8': {'decided_by': 'owner', 'option': 'A', 'outcome': 'A'}}})
    (tmp_path / '.wuwei/config.toml').write_text('template_version = "0.1.0"\n')
    data = json.loads(cli(tmp_path, 'status', '--json').stdout)
    assert (data['plan'], data['decisions'], data['plugin'], data['template']) == (
        False, ['D-7'], integrity.version(), '0.1.0')
    assert {'pages', 'nudges', 'cap', 'cap_bound', 'gate_approved', 'phases', 'next_reply_due',
            'next_meeting', 'sessions', 'seats', 'running', 'gates', 'watch', 'listen', 'health',
            'loops', 'answered', 'trace_gaps', 'prs_changed', 'solo', 'posture', 'restart'} <= set(data)
    (directory / 'plan.md').write_text('# Plan\n')
    assert json.loads(cli(tmp_path, 'status', '--json').stdout)['plan'] is True


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
    assert 'pages 0' in line and 'nudges 0' in line
    assert 'ITEM-1' not in line and not re.search(r'\d\d:\d\d', line) and '(plugin' not in line
    whole = tokens(status.line(data, 10 ** 6))
    assert all(token in whole or token.startswith('seats 4/1 (') for token in tokens(line))


def test_issue_acceptance_nothing_to_do_starts_with_the_counts(tmp_path, monkeypatch):
    from wuwei.commands import status
    data = four_seats(tmp_path, monkeypatch)
    assert status.line(data) == (
        'WUWEI 1 building · seats 4/1 (lead, arch, quality, security) | pages 0 · nudges 0')
    assert status.line({**data, 'posture': 'observe'}).endswith('| pages 0 · nudges 0 · observe')
    assert status.line({**data, 'running': [], 'phases': {}}) == 'WUWEI seats 0/1 | pages 0 · nudges 0'
    for moved in ('watch', 'listen', 'sessions', 'meeting', 'reply', 'running', 'loops', 'bound',
                  'unplanned', 'checks'):
        assert moved not in status.line({**data, 'cap_bound': 'budget'})
    # #658: the seats token names the rule that set CAP; before the gate there is none
    assert 'seats 4/1 by budget (lead, ' in status.line({**data, 'cap_bound': 'budget'})
    assert ' by ' not in status.line({**data, 'cap_bound': ''})


def test_the_line_names_the_one_thing_to_do_first(tmp_path, monkeypatch):
    from wuwei.commands import status
    directory = day(tmp_path, {'cap': 1, 'items': {}})
    result = cli(tmp_path, 'status', '--line')
    assert (result.returncode, result.stdout) == (0, 'WUWEI no plan yet | pages 0 · nudges 0\n')
    (directory / 'plan.md').write_text('# Plan\n')
    assert cli(tmp_path, 'status', '--line').stdout == 'WUWEI gate waiting | pages 0 · nudges 0\n'
    data = {**four_seats(tmp_path / 'b', monkeypatch), 'decisions': ['D-7', 'D-8']}
    assert status.line(data).startswith('WUWEI decision D-7 waiting | 1 building')
    assert status.line({**data, 'restart': STALE}).startswith('WUWEI restart Claude Code')
    assert status.line({**data, 'gate_approved': False, 'plan': True}).startswith('WUWEI gate waiting |')


def test_a_narrow_line_cuts_the_roles_then_drops_whole_tokens(tmp_path, monkeypatch):
    from wuwei.commands import status
    data = four_seats(tmp_path, monkeypatch)
    assert status.line(data, 81) == (
        'WUWEI 1 building · seats 4/1 (lead, arch, quality, security) | pages 0 · nudges 0')
    assert status.line(data, 72) == 'WUWEI 1 building · seats 4/1 (lead, arch, +2 more) | pages 0 · nudges 0'
    assert status.line(data, 67) == 'WUWEI 1 building · seats 4/1 (lead, +3 more) | pages 0 · nudges 0'
    assert status.line(data, 52) == 'WUWEI 1 building | pages 0 · nudges 0'
    assert status.line(data, 42) == 'WUWEI 1 building | pages 0 · nudges 0'
    assert status.line(data, 27) == 'WUWEI 1 building | pages 0'
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
        'WUWEI 5 planned · 2 building · 2 in review · 3 shipped · seats 1/3 (builder) | pages 0 · nudges 0')
    for text in (status.line(data), status.full(data)):
        assert all(text[:match.start()].endswith('seats ') for match in re.finditer(r'\d+/\d+', text)), text


def test_issue_641_parked_and_escalated_follow_shipped(tmp_path, monkeypatch):
    from wuwei.commands import status
    data = sample_day(tmp_path, monkeypatch, {**SAMPLE, 'escalated': 1, 'parked': 1, 'odd': 2})
    assert '3 shipped · 1 parked · 1 escalated · 2 odd · seats 1/3' in status.line(data, 10 ** 6)


def test_status_line_width_flag(tmp_path):
    seats = {role: {'status': 'running', 'role': role, 'item': 'ITEM-1'} for role in ROLES}
    day(tmp_path, {'cap': 1, 'gate_approved': True, 'items': {}, 'seats': seats})
    result = cli(tmp_path, 'status', '--line', '--width', '53')
    assert result.returncode == 0, result.stderr
    assert result.stdout == 'WUWEI seats 4/1 (lead, +3 more) | pages 0 · nudges 0\n'
    assert cli(tmp_path, 'status', '--line', '--width', '40').stdout == 'WUWEI seats 4/1 (+4 more) | pages 0\n'
    assert cli(tmp_path, 'status', '--line', '--width', 'x').returncode == 2


def test_issue_acceptance_status_shows_each_running_seat(tmp_path, monkeypatch):
    from wuwei.commands import status
    data = four_seats(tmp_path, monkeypatch)
    result = cli(tmp_path, 'status')
    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    assert lines[0] == 'WUWEI 1 building · seats 4/1 (lead, arch, quality, security)'
    assert [row for row in lines if row.startswith('running ')] == [
        'running lead ITEM-1 09:10', 'running arch ITEM-1 09:20', 'running quality ITEM-1 09:30',
        'running security ITEM-1 09:40', 'running checks ITEM-1 09:45']
    shown = status.full({**data, 'restart': STALE}).splitlines()
    assert shown[0] == 'WUWEI ' + STALE
    assert shown[1] == '1 building · seats 4/1 (lead, arch, quality, security)'


def test_status_without_a_flag_fails_closed(tmp_path):
    (day(tmp_path) / 'state.json').write_text('{broken')
    result = cli(tmp_path, 'status')
    assert (result.returncode, result.stdout) == (2, 'WUWEI ? unmeasured\n')


def test_status_shows_the_detail_the_line_drops(tmp_path, monkeypatch):
    from wuwei.commands import status
    data = {**four_seats(tmp_path, monkeypatch), 'cap_bound': 'budget', 'seats': {'G-1': 2},
            'watch': 'dead', 'listen': 'off', 'health': 'ok', 'sessions': 2, 'answered': ['x'],
            'loops': 1, 'prs_changed': 3, 'solo': True, 'trace_gaps': 2, 'pages': 1,
            'next_reply_due': '2026-09-28T15:00:00+02:00', 'next_meeting': None,
            'plugin': '0.16.0', 'template': '0.15.0', 'posture': 'observe'}
    shown = status.full(data).splitlines()
    assert shown[0] == 'WUWEI 1 building · seats 4/1 by budget (lead, arch, quality, security) · builders G-1 2'
    assert shown[6:] == [
        'pages 1 · nudges 0 · observe · phone answers 1 · loops 1 · prs 3 changed · reviewers: none (solo)'
        ' · traces: 2 gaps',
        'watch dead · listen off · health ok · sessions 2',
        'reply 2026-09-28T15:00:00+02:00 · meeting unmeasured',
        'plugin 0.16.0 · template 0.15.0']
    assert status.full({**data, 'plugin': '', 'template': None})[-len('plugin unmeasured · template none'):] == (
        'plugin unmeasured · template none')


def test_status_names_a_repository_with_no_fast_checks(tmp_path, monkeypatch):
    # #600: none configured is a state; full status says so per repository.
    from wuwei import fast_checks
    from wuwei.commands import status
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', NOW)
    directory = day(tmp_path, {'items': {}, 'cap': 1, 'gate_approved': True})
    (tmp_path / '.wuwei/config.toml').write_text(''.join(
        f'[[repos]]\nname = "acme/{name}"\npath = "{name}"\ndefault_branch = "main"\nfast_checks = {checks}\n'
        for name, checks in (('paper', '[]'), ('widget', '["make test"]'))))
    data = status.snapshot(directory)
    assert data['checks_none'] == ['acme/paper']
    shown = status.full(data).splitlines()
    assert f'acme/paper {fast_checks.NONE}' in shown
    assert not any('acme/widget' in line for line in shown)
    assert 'checks_none' not in status.snapshot(directory, line=True)
