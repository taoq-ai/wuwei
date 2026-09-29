"""A scripted delivery day, collected by the default PR test suite."""

import json
import time

import pytest

@pytest.fixture
def day(tmp_path, monkeypatch):
    from fakes.day import Day
    return Day(tmp_path / 'workspace', monkeypatch)


def test_scripted_day(day):
    started = time.monotonic()
    day.plan()
    assert day.data['gate_approved'] is False
    assert day.run('dispatch', 'next', 'A', expected=1)
    day.run('plan', 'approve', '--items', 'A', expected=1)
    day.approve()
    assert day.data['approved_items'] == ['A']
    assert day.data['items']['A']['phase'] == 'planned'
    day.run('plan', 'session', 'planner')
    day.transition('implement')
    day.build('builder-initial')
    initial_head = day.head
    assert day.data['seats']['builder-initial']['status'] == 'stopped'
    day.transition('gate')
    assert day.next() == {'action': 'gates', 'roles': ['arch', 'quality', 'security']}
    day.raise_pr(expected=1)
    assert not any(call[0] == 'create_pr' for call in day.host.calls)
    for role in ('arch', 'quality', 'security'):
        day.gate(role, 'FIX' if role == 'quality' else 'PASS')
    assert day.next() == {'action': 'fix', 'roles': ['quality']}
    day.raise_pr(expected=1)
    day.transition('fix')
    day.build('builder-fix')
    assert day.head != initial_head
    day.transition('delta')
    assert day.next() == {'action': 'gates', 'roles': ['quality']}
    day.gate('quality', 'PASS', round_name='delta')
    assert day.next() == {'action': 'raise', 'notes': []}
    day.raise_pr()
    day.transition('raised')
    assert day.data['raised_prs'] == [day.ref]
    assert day.data['items']['A']['pr'] == day.ref
    from wuwei import merge
    assert merge.item_evidence(day.root, day.ref, day.data) == 'A'
    assert day.data['pr_reviewers'][day.ref] == ['reviewer', 'lead']
    assert len([call for call in day.host.calls if call[0] == 'create_pr']) == 1
    assert any(call[0] == 'request_reviewers' for call in day.host.calls)
    rows = json.loads(day.run('pr', 'state'))
    assert rows[0]['state'] == 'waiting'
    day.run('pr', 'ping-check', day.ref)
    day.run('pr', 'ping', day.ref)
    assert day.data['channel_posts'][0]['status'] == 'posted'
    assert len(day.chat.calls) == 1
    day.run('close', expected=1)
    assert json.loads(day.hook('Stop', expected=2))['decision'] == 'block'
    day.run('retro')
    day.run('close', '--check', 'retro')
    day.run('close', expected=1)
    assert json.loads(day.hook('Stop', expected=2))['decision'] == 'block'
    # A replayed server-side merge is external evidence, not a forged local outcome.
    day.host.results['pr'].data.update(state='closed', merged=True,
        merged_at='2026-09-29T12:00:00Z', merge_commit=day.head)
    assert json.loads(day.run('pr', 'state'))[0]['state'] == 'merged'
    day.transition('merged')
    day.run('report')
    assert (day.directory / 'report.md').is_file()
    day.run('close')
    day.hook('Stop')
    assert day.data['close_requested'] is True
    assert all(seat['status'] == 'stopped' for seat in day.data['seats'].values())
    events = day.events
    transitions = [row['payload']['phase'] for row in events if row['kind'] == 'state.transition']
    assert transitions == ['implement', 'gate', 'fix', 'delta', 'raised', 'merged']
    gates = [row['payload'] for row in events if row['kind'] == 'gate.received']
    assert [(row['role'], row['round'], row['verdict']) for row in gates] == [
        ('arch', 'initial', 'PASS'), ('quality', 'initial', 'FIX'),
        ('security', 'initial', 'PASS'), ('quality', 'delta', 'PASS')]
    kinds = [row['kind'] for row in events]
    assert kinds.index('plan.approved') < kinds.index('seat launched') < kinds.index('gate.received') < kinds.index('pr.raised')
    assert kinds.count('seat.usage') == 2
    assert kinds.count('retro.captured') == 7
    assert 'seat stop unmatched' not in kinds
    assert json.loads(day.run('metrics'))['fix_rounds_per_item'] == {'A': 1}
    assert time.monotonic() - started < 20


def test_agent_surface_without_scanner_is_unmeasured(day):
    day.plan(agent_surface=True)
    day.approve()
    day.transition('implement')
    day.build('builder-initial')
    day.transition('gate')
    day.gate('arch', 'PASS')
    day.gate('quality', 'PASS')
    output = day.gate('security', 'PASS', expected=2)
    assert 'unmeasured' in output
    assert 'A:security:initial' not in day.data['gate_verdicts']
    assert day.next() == {'action': 'gates', 'roles': ['security']}
    day.raise_pr(expected=1)
    assert not any(call[0] == 'create_pr' for call in day.host.calls)
    assert not any(row['kind'] == 'gate.received' and row['payload']['role'] == 'security'
                   for row in day.events)


def test_unconfirmed_plugin_change_denies_pretooluse(day):
    day.run('integrity', 'check')
    for command in ('python3 -m pytest -q', 'for x in a; do echo "$x"; done', 'export X=1'):
        day.hook('PreToolUse', tool_name='Bash', tool_input={'command': command})
    (day.plugin / 'charters/builder.md').write_text('Changed without owner confirmation.\n')
    day.run('integrity', 'check', expected=1)
    output = day.hook('PreToolUse', expected=2, tool_name='Read',
                      tool_input={'file_path': str(day.repo / 'memory/demo.py')})
    assert json.loads(output)['hookSpecificOutput']['permissionDecision'] == 'deny'
    assert day.events[-1]['kind'] == 'hook.refusal'
    assert 'plugin integrity' in day.events[-1]['payload']['reason']
    outside = day.root.parent / 'outside'
    outside.mkdir()
    day.hook('PreToolUse', cwd=str(outside), tool_name='Read',
             tool_input={'file_path': str(outside / 'note.md')})
