"""A scripted delivery day, collected by the default PR test suite."""

import json
import time

import pytest

@pytest.fixture
def day(tmp_path, monkeypatch):
    from fakes.day import Day
    return Day(tmp_path / 'workspace', monkeypatch)


@pytest.mark.xdist_group('timing')
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
    action = day.next()
    tier = action.pop('tier')
    assert [command.split()[:4] for command in action.pop('commands')] == [
        ['wuwei', 'seat', 'brief', role] for role in ('arch', 'quality', 'security')]
    assert action == {'action': 'gates', 'roles': ['arch', 'quality', 'security'], 'seats': []}
    assert tier['tier'] == 'standard' and tier['roles'] == ['arch', 'quality', 'security']
    day.raise_pr(expected=1)
    assert not any(call[0] == 'create_pr' for call in day.host.calls)
    for role in ('arch', 'quality', 'security'):
        day.gate(role, 'FIX' if role == 'quality' else 'PASS')
    assert day.next() == {'action': 'fix', 'roles': ['quality'], 'command': 'wuwei build next A'}
    day.raise_pr(expected=1)
    assert day.data['items']['A']['phase'] == 'fix'
    day.fix()
    assert day.head != initial_head
    delta = day.next()
    assert (delta['action'], delta['roles']) == ('gates', ['quality'])
    assert [row['action'] for row in delta['seats']] == ['continue']
    day.gate('quality', 'PASS', round_name='delta')
    assert 'quality-delta' not in day.data['seats']
    assert day.data['seats']['quality-initial']['status'] == 'stopped'
    assert {k: day.next()[k] for k in ('action', 'notes')} == {'action': 'raise', 'notes': []}
    day.raise_pr()
    assert day.data['items']['A']['phase'] == 'raised'
    assert day.data['raised_prs'] == [day.ref]
    assert day.data['items']['A']['pr'] == day.ref
    from wuwei import merge
    held = []
    assert merge.item_evidence(day.root, day.ref, day.data, held) == 'A' and held == []
    assert day.data['pr_reviewers'][day.ref] == ['reviewer', 'lead']
    assert len([call for call in day.host.calls if call[0] == 'create_pr']) == 1
    assert any(call[0] == 'request_reviewers' for call in day.host.calls)
    rows = json.loads(day.run('pr', 'state'))
    assert rows[0]['state'] == 'waiting'
    day.run('pr', 'ping', day.ref)
    assert day.data['channel_posts'][0]['status'] == 'posted'
    assert len(day.chat.calls) == 1
    day.patch.setenv('WUWEI_NOW', '2026-09-29T12:30:00Z')
    # Part 14: the open PR holds the close; no decision record does.
    assert 'A is still open' in day.run('close', expected=1)
    day.run('retro')
    day.run('close', '--check', 'retro')
    assert 'A is still open' in day.run('close', expected=1)
    # A replayed server-side merge is external evidence, not a forged local outcome.
    day.host.results['pr'].data.update(state='closed', merged=True,
        merged_at='2026-09-29T12:00:00Z', merge_commit=day.head)
    assert json.loads(day.run('pr', 'state'))[0]['state'] == 'merged'
    assert day.data['items']['A']['phase'] == 'merged'
    day.run('report')
    assert '## Decisions answered' not in (day.directory / 'report.md').read_text()
    assert not list((day.directory / 'decisions').glob('D-*.md'))  # SC-002
    day.run('close')
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
    # Design 5.10: no source write is refused for the spec (#843); one spec.step per step.
    refusals = [row['payload']['reason'] for row in events if row['kind'] == 'hook.refusal']
    assert not [reason for reason in refusals if 'spec mode' in reason]
    assert sorted(row['payload']['step'] for row in events if row['kind'] == 'spec.step') == sorted([
        'specify', 'clarify', 'plan', 'tasks', 'analyze', 'checklist', 'implement'])
    assert 'seat stop unmatched' not in kinds
    from wuwei import metrics
    assert metrics.collect(day.root)['fix_rounds_per_item'] == {'A': 1}
    assert not [call for call in day.calls if call[:2] == ('state', 'transition') or call[0] == 'runtime']
    assert time.monotonic() - started < 20


def test_fix_round_and_delta_with_fresh_agents(day):
    # #614: Claude Code's Agent has no resume. Each continue runs as a fresh Agent with the
    # returned prompt, a new agent id and its own transcript; the hooks bind it to the round.
    day.plan()
    day.approve()
    day.run('plan', 'session', 'planner')
    day.build('builder-initial')
    for role in ('arch', 'quality', 'security'):
        day.gate(role, 'FIX' if role == 'quality' else 'PASS')
    day.runtime.fresh = True
    day.fix()
    assert day.data['builds']['A']['agent_id'] == 'builder-initial-fresh'
    assert day.data['items']['A']['phase'] == 'delta'
    day.gate('quality', 'PASS', round_name='delta')
    assert day.data['seats']['quality-initial']['agent_id'] == 'quality-initial-fresh'
    assert {k: day.next()[k] for k in ('action', 'notes')} == {'action': 'raise', 'notes': []}
    gates = [row['payload'] for row in day.events if row['kind'] == 'gate.received']
    assert (gates[-1]['role'], gates[-1]['round'], gates[-1]['verdict']) == ('quality', 'delta', 'PASS')
    assert 'seat stop unmatched' not in [row['kind'] for row in day.events]


def test_light_item_skips_spec(day):
    day.runtime.spec = False
    day.plan(tier='light')
    day.approve()
    day.run('plan', 'session', 'planner')
    day.build('builder-initial')
    assert day.data['items']['A']['phase'] == 'gate'
    kinds = [(row['kind'], row['payload']) for row in day.events if row['kind'].startswith('spec.')]
    assert kinds == [('spec.skipped', {'item': 'A', 'reason': 'lead tier light'})]


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
    assert {k: day.next()[k] for k in ('action', 'notes')} == {'action': 'raise', 'notes': []}
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
    assert '1 shipped · seats 0/4' in day.run('status', '--line')  # CAP 4 derived from the fixture host (#528)
    day.run('retro')
    day.run('close', '--check', 'retro')
    day.run('close')
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


def test_day_names_the_reintroduced_bug(day, monkeypatch):
    from wuwei.guards import Guard, edges
    monkeypatch.setattr(edges, 'GUARDS', [*edges.GUARDS, Guard('PreToolUse', 'Bash', refuse_launcher)])
    with pytest.raises(AssertionError, match='wuwei plan propose'):
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
    action = day.next()
    tier = action.pop('tier')
    # The security seat stopped with a rejected verdict: its receive is still due.
    assert action.pop('commands') == ['wuwei dispatch receive A security security-initial']
    assert action == {'action': 'gates', 'roles': ['security'], 'seats': []}
    assert tier['tier'] == 'standard' and tier['roles'] == ['arch', 'quality', 'security']
    day.raise_pr(expected=1)
    assert not any(call[0] == 'create_pr' for call in day.host.calls)
    assert not any(row['kind'] == 'gate.received' and row['payload']['role'] == 'security'
                   for row in day.events)


def integrity_check(day):
    """#848: the SessionStart check the integrity command ran."""
    from wuwei import integrity
    return integrity.check(day.root).exit


def test_unconfirmed_plugin_change_warns_and_never_denies_pretooluse(day):
    # #839: integrity warns at session start; no tool call is refused for it.
    assert integrity_check(day) == 0
    for command in ('python3 -m pytest -q', 'for x in a; do echo "$x"; done', 'export X=1'):
        day.hook('PreToolUse', tool_name='Bash', tool_input={'command': command})
    (day.plugin / 'charters/builder.md').write_text('Changed without owner confirmation.\n')
    assert integrity_check(day) == 1
    day.hook('PreToolUse', tool_name='Read', tool_input={'file_path': str(day.repo / 'memory/demo.py')})
    events = day.directory / 'events.jsonl'
    assert not events.exists() or not any(row['kind'] == 'hook.refusal' for row in day.events)
    outside = day.root.parent / 'outside'
    outside.mkdir()
    day.hook('PreToolUse', cwd=str(outside), tool_name='Read',
             tool_input={'file_path': str(outside / 'note.md')})


def test_enforce_off_records_force_push_and_keeps_records_refused(day):
    # #837: guards.enforce = false logs what a guard would refuse; the records floor still blocks.
    setting = '[guards]\nenforce = false\n'
    from adapters.vcs import git
    from wuwei import registry
    from wuwei.registry import Result
    config = day.root / '.wuwei/config.toml'
    config.write_text(config.read_text().replace(
        'fast_checks', 'identity = {name = "Builder", email = "builder@example.test"}\nfast_checks')
        + setting)
    # The day fixture has no Git identity (git var exits 128); report the configured one.
    identity = {'name': 'Builder', 'email': 'builder@example.test'}
    day.patch.setattr(registry.load('vcs', None), 'commit_context', lambda repo, *args, root=None: Result(
        0, {**git.repo_context(repo).data, 'author': identity, 'committer': identity}))
    assert day.hook('PreToolUse', cwd=str(day.repo), tool_name='Bash',
                    tool_input={'command': 'git push --force origin main'}) == ''
    event = day.events[-1]
    assert event['kind'] == 'guard.would_refuse' and event['payload']['guard'] == 'edges'
    assert 'force' in event['payload']['reason'].lower()
    assert event['payload']['target'] == 'git push --force origin main'
    assert not {'area', 'level', 'posture'} & set(event['payload'])
    output = day.hook('PreToolUse', expected=2, tool_name='Write', tool_input={
        'file_path': str(day.directory / 'state.json'), 'content': '{}'})
    denied = json.loads(output)['hookSpecificOutput']
    assert denied['permissionDecision'] == 'deny'
    assert 'posture:' not in denied['permissionDecisionReason']
    from wuwei import report
    assert report.shadow_lines([day.directory])[0].startswith('- edges: 1 ')
    assert integrity_check(day) == 0
    (day.plugin / 'charters/builder.md').write_text('Changed without owner confirmation.\n')
    assert integrity_check(day) == 1
    # #839: integrity warns at session start; a tool call is neither refused nor logged for it.
    count = len(day.events)
    assert day.hook('PreToolUse', tool_name='Read',
                    tool_input={'file_path': str(day.repo / 'memory/demo.py')}) == ''
    assert len(day.events) == count


def test_background_handback_day(tmp_path, monkeypatch):
    # #473: every background seat ends with a SubagentHandback and no last_assistant_message;
    # the day records the same seats, results and events as with the plain-text ending.
    from fakes.day import Day
    seen = []
    for handback in (False, True):
        with monkeypatch.context() as patch:
            day = Day(tmp_path / f'handback-{handback}', patch)
            day.runtime.handback = handback
            day.plan()
            day.approve()
            day.run('plan', 'session', 'planner')
            day.build('builder-initial')
            for role in ('arch', 'quality', 'security'):
                day.gate(role, 'PASS')
            seen.append(({name: seat['status'] for name, seat in day.data['seats'].items()},
                         day.data['builds']['A']['result']['text'],
                         [(row['kind'], row['payload'].get('name')) for row in day.events
                          if row['kind'] in ('seat launched', 'seat stopped', 'seat.usage', 'retro.captured')]))
    assert seen[0] == seen[1]
    assert all(status == 'stopped' for status in seen[1][0].values())
