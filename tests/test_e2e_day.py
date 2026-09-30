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
    day.build('builder-initial')
    initial_head = day.head
    assert day.data['seats']['builder-initial']['status'] == 'stopped'
    assert day.next() == {'action': 'gates', 'roles': ['arch', 'quality', 'security'], 'seats': []}
    day.raise_pr(expected=1)
    assert not any(call[0] == 'create_pr' for call in day.host.calls)
    for role in ('arch', 'quality', 'security'):
        day.gate(role, 'FIX' if role == 'quality' else 'PASS')
    assert day.next() == {'action': 'fix', 'roles': ['quality'], 'command': 'wuwei build next A'}
    day.raise_pr(expected=1)
    day.fix()
    assert day.head != initial_head
    delta = day.next()
    assert (delta['action'], delta['roles']) == ('gates', ['quality'])
    assert [row['action'] for row in delta['seats']] == ['continue']
    day.gate('quality', 'PASS', round_name='delta')
    assert 'quality-delta' not in day.data['seats']
    assert day.data['seats']['quality-initial']['status'] == 'stopped'
    assert day.next() == {'action': 'raise', 'notes': []}
    day.raise_pr()
    assert day.data['items']['A']['phase'] == 'raised'
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
    from wuwei import state
    state.append_event('watch: clock', {}, day.root)
    day.patch.setenv('WUWEI_NOW', '2026-09-29T12:30:00Z')
    pages = [row for row in json.loads(day.run('nudges')) if row['source'] == 'watch: health']
    assert [row['tier'] for row in pages] == ['page']
    state.append_event('watch: clock', {}, day.root)
    assert not [row for row in json.loads(day.run('nudges')) if row['source'] == 'watch: health']
    from test_decision import VALID
    (day.directory / 'decisions/D-1.md').write_text(VALID.replace(
        'Reversibility: two-way', 'Reversibility: one-way').replace('Decided-by: seat', 'Decided-by: owner'))
    day.run('decision', 'route', 'D-1')
    assert 'D-1: pending owner decision' in day.run('close', expected=1)
    assert json.loads(day.hook('Stop', expected=2))['decision'] == 'block'
    day.hook('Stop', stop_hook_active=True)
    day.run('retro')
    day.run('close', '--check', 'retro')
    day.patch.setattr('wuwei.integrity._host_confirm', lambda value, **kwargs: True)
    day.owner('decision', 'outcome', 'D-1', 'A')
    assert 'D-1' not in day.run('close', expected=1)
    assert json.loads(day.hook('Stop', expected=2))['decision'] == 'block'
    # A replayed server-side merge is external evidence, not a forged local outcome.
    day.host.results['pr'].data.update(state='closed', merged=True,
        merged_at='2026-09-29T12:00:00Z', merge_commit=day.head)
    assert json.loads(day.run('pr', 'state'))[0]['state'] == 'merged'
    assert day.data['items']['A']['phase'] == 'merged'
    day.run('report')
    assert '- D-1: A' in (day.directory / 'report.md').read_text()
    day.run('close')
    day.hook('Stop')
    assert day.data['close_requested'] is True
    assert all(seat['status'] == 'stopped' for seat in day.data['seats'].values())
    events = day.events
    transitions = [row['payload']['phase_changes']['A'] for row in events
                   if 'A' in row['payload'].get('phase_changes', {})]
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
    assert not [call for call in day.calls if call[:2] == ('state', 'transition') or call[0] == 'runtime']
    assert time.monotonic() - started < 20


def test_solo_daily_path(tmp_path, monkeypatch):
    """The fourth dry run: one item from plan to close using only the daily path page."""
    import re
    from pathlib import Path
    from fakes.day import Day
    day = Day(tmp_path / 'workspace', monkeypatch, solo=True)
    day.plan()
    day.approve()
    day.run('plan', 'session', 'planner')
    day.build('builder-initial')
    for role in ('arch', 'quality', 'security'):
        day.gate(role, 'FIX' if role == 'quality' else 'PASS')
    day.fix()
    day.gate('quality', 'PASS', round_name='delta')
    assert day.next() == {'action': 'raise', 'notes': []}
    day.raise_pr()
    assert day.data['pr_reviewers'][day.ref] == []
    assert len([call for call in day.host.calls if call[0] == 'create_pr']) == 1
    assert not any(call[0] == 'request_reviewers' for call in day.host.calls)
    assert day.chat.calls == []
    assert json.loads(day.run('pr', 'state'))[0]['state'] != 'merged'
    day.host.results['pr'].data.update(state='closed', merged=True,
        merged_at='2026-09-29T12:00:00Z', merge_commit=day.head)
    assert json.loads(day.run('pr', 'state'))[0]['state'] == 'merged'
    day.run('report')
    assert f'## Merged\n- A ({day.ref})' in (day.directory / 'report.md').read_text()
    assert 'merged 1/1' in day.run('status', '--line')
    day.run('retro')
    day.run('close', '--check', 'retro')
    day.run('close')
    day.hook('Stop')
    transitions = [row['payload']['phase_changes']['A'] for row in day.events
                   if 'A' in row['payload'].get('phase_changes', {})]
    assert transitions == ['implement', 'gate', 'fix', 'delta', 'raised', 'merged']
    assert not [call for call in day.calls if call[:2] == ('state', 'transition') or call[0] == 'runtime']
    page = (Path(__file__).resolve().parents[1] / 'docs/site/daily.md').read_text()
    for call in day.calls:
        # A gate brief's second word is a role, not a subcommand.
        words = call[:2] if len(call) > 1 and call[0] != 'brief' and re.fullmatch('[a-z][a-z-]*', call[1]) else call[:1]
        assert 'wuwei ' + ' '.join(words) in page, call


def refuse_launcher(payload):
    from fakes.day import LAUNCHER
    return (2, 'opaque script command') if str(LAUNCHER) in payload['tool_input']['command'] else (0, '')


def close_trap(payload):
    from wuwei.guards import stop
    return stop.check({**payload, 'stop_hook_active': False})


@pytest.mark.parametrize('mutation,match', [('launcher', 'wuwei rank'),
                                            ('close_trap', "'stop_hook_active': True")])
def test_day_names_the_reintroduced_bug(day, monkeypatch, mutation, match):
    from wuwei.guards import Guard, deploy, stop
    if mutation == 'launcher':
        monkeypatch.setattr(deploy, 'GUARDS', [*deploy.GUARDS, Guard('PreToolUse', 'Bash', refuse_launcher)])
    else:
        monkeypatch.setattr(stop, 'GUARDS', [Guard('Stop', None, close_trap)])
    with pytest.raises(AssertionError, match=match):
        test_scripted_day(day)


def test_agent_surface_without_scanner_is_unmeasured(day):
    day.plan(agent_surface=True)
    day.approve()
    day.build('builder-initial')
    day.gate('arch', 'PASS')
    day.gate('quality', 'PASS')
    output = day.gate('security', 'PASS', expected=2)
    assert 'unmeasured' in output
    assert 'A:security:initial' not in day.data['gate_verdicts']
    assert day.next() == {'action': 'gates', 'roles': ['security'], 'seats': []}
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
