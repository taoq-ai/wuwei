"""#902: every action WUWEI emits runs in its real consumer (the command, through the planner's
PreToolUse hook, and the Agent launch guard) and ends in progress, a genuine wait or a specific
owner decision; next and dispatch next take one gate decision."""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
import shlex
import subprocess
from pathlib import Path

import pytest

from wuwei import state, workspace
from wuwei.__main__ import main

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def day(tmp_path, monkeypatch):
    from fakes.day import Day
    return Day(tmp_path / 'workspace', monkeypatch)


def act(day, *args):
    """(exit, stdout, stderr) of one planner command, through its PreToolUse hook first."""
    day.bash(args)
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(list(map(str, args)))
    return code, out.getvalue(), err.getvalue()


def dispatch_next(day):
    code, out, err = act(day, 'dispatch', 'next', 'A')
    assert code in (0, 1) and out, (code, out, err)
    return json.loads(out)


def run(day, action):
    """Do what an action names, as the planner does: its commands, then each seat through the
    Agent guard and its receive."""
    for command in action.get('commands', []):
        day.run(*shlex.split(command)[1:])
    for seat in action.get('seats', []):
        day.execute(seat)
        if seat.get('receive'):
            day.run(*shlex.split(seat['receive'])[1:])
    if action['action'] == 'check':
        day.run(*shlex.split(action['command'])[1:])


def follow(day, steps=('gates', 'check'), limit=8):
    """Run dispatch next's steps until one is not in steps; a step with nothing to run fails."""
    for _ in range(limit):
        action = dispatch_next(day)
        if action['action'] not in steps:
            return action
        assert action.get('commands') or action.get('seats') or action['action'] == 'check', (
            f'a step with nothing to run: {action}')
        run(day, action)
    raise AssertionError(f'no progress after {limit} steps: {action}')


def started(day):
    day.plan()
    day.approve()
    day.run('plan', 'session', 'planner')
    day.build('builder-initial')


def passed(day):
    started(day)
    for role in ('arch', 'quality', 'security'):
        day.gate(role, 'PASS')


def to_delta(day):
    """quality said FIX and the fix round ran: the item is in delta."""
    started(day)
    for role in ('arch', 'quality', 'security'):
        day.gate(role, 'FIX' if role == 'quality' else 'PASS')
    day.fix()
    day.runtime.verdict = 'PASS'
    assert day.data['items']['A']['phase'] == 'delta'


def commit(day, name='docs/note.md'):
    """A commit outside a fix round: the worktree HEAD moves past the receipts."""
    path = day.repo / name
    path.parent.mkdir(exist_ok=True)
    path.write_text('moved\n')
    for argv in (['add', '--', name], ['-c', 'user.name=Builder', '-c', 'user.email=builder@example.test',
                                         'commit', '-q', '-m', 'moved', '--', name]):
        subprocess.run(['git', '-C', str(day.repo), *argv], env=dict(os.environ), capture_output=True, check=True)


def test_a_missing_initial_receipt_in_delta_is_gated_and_received(day):
    # Contradiction 1: next_step named receive for a missing initial in delta; receive refused it.
    from wuwei import merge
    to_delta(day)
    state._write_state(lambda data: data['gate_verdicts'].pop('A:arch:initial'), day.root)
    assert follow(day)['action'] == 'raise'
    data = day.data
    assert data['gate_verdicts']['A:arch:initial']['head'] == day.head
    assert merge._recorded_gates(day.root, day.head, data['gate_verdicts'], 'A', data['items']) == (0, '')


@pytest.mark.parametrize('moved', [False, True])
@pytest.mark.parametrize('late,expected', [('FIX', 'fix'), ('PARK', 'parked'), ('ESCALATE', 'escalate')])
def test_a_late_initial_that_blocks_is_judged_as_an_initial_verdict(day, late, expected, moved):
    # review F1, D1: a late initial FIX, PARK or ESCALATE opens the fix round, parks or asks the
    # owner until a fix round opens; it is never waved through by a delta re-read, also after a
    # commit outside a fix round moved the head and every gate re-read it.
    from wuwei import merge
    to_delta(day)
    state._write_state(lambda data: data['gate_verdicts'].pop('A:arch:initial'), day.root)
    day.runtime.verdict = late
    while 'A:arch:initial' not in day.data['gate_verdicts']:
        run(day, dispatch_next(day))
    assert day.data['gate_verdicts']['A:arch:initial']['verdict'] == late
    if moved:
        day.runtime.verdict = 'PASS'
        commit(day)
    action = follow(day)
    assert action['action'] == expected, action
    if expected == 'escalate':
        assert action['command'] == 'wuwei dispatch next A' and action['card']
    if expected == 'fix':  # the fix round answers it: from here it is an ordinary initial FIX
        assert 'late' not in day.data['gate_verdicts']['A:arch:initial']
    phase = day.data['items']['A']['phase']
    assert phase == {'fix': 'fix', 'parked': 'parked', 'escalate': 'delta'}[expected]
    data = day.data
    assert merge._recorded_gates(day.root, day.head, data['gate_verdicts'], 'A', data['items'])[0] == 1


def test_a_missing_initial_receipt_in_the_fix_round_lets_the_builder_go_on(day):
    started(day)
    for role in ('arch', 'quality', 'security'):
        day.gate(role, 'FIX' if role == 'quality' else 'PASS')
    assert dispatch_next(day)['action'] == 'fix'
    state._write_state(lambda data: data['gate_verdicts'].pop('A:arch:initial'), day.root)
    assert dispatch_next(day) == {'action': 'fix', 'roles': ['quality'], 'command': 'wuwei build next A'}


def test_a_verdict_file_changed_after_its_receipt_does_not_block_the_merge_gate(day):
    # Contradiction 2: merge said receive the verdict again; receive refuses a current receipt.
    from wuwei import merge
    passed(day)
    path = day.directory / 'decisions/gate-arch-initial.md'
    path.write_text(path.read_text().replace('Verdict: PASS', 'Verdict: FIX')
                    + '- P1 | memory/demo.py:1 | fails when edited after receipt | blocks: yes\n')
    code, _, err = act(day, 'dispatch', 'receive', 'A', 'arch', 'arch-initial')
    assert code == 1 and 'already received' in err
    data = day.data
    assert merge._recorded_gates(day.root, day.head, data['gate_verdicts'], 'A', data['items']) == (0, '')


def test_a_stale_gate_receipt_rereads_on_a_seat_the_guard_accepts(day):
    # Contradiction 3: a stale receipt at gate was offered as a continue; with no Agent resume the
    # launch guard accepted a reused brief only through delta_due, so it refused it.
    passed(day)
    day.runtime.fresh = True  # Claude Code's Agent has no resume
    commit(day)
    assert follow(day)['action'] == 'raise'
    assert {record['head'] for record in day.data['gate_verdicts'].values()} == {day.head}


@pytest.mark.parametrize('lost', ['agent_id', 'unmeasured', 'missing'])
def test_a_lost_delta_seat_is_replaced_by_a_fresh_one(day, lost):
    # Contradiction 4: the charter permits a fresh seat when the original is lost; _seats offered none.
    to_delta(day)

    def lose(data):
        if lost == 'agent_id':
            data['seats']['quality-initial'].pop('agent_id')
        elif lost == 'unmeasured':
            data['seats']['quality-initial']['status'] = 'unmeasured'
        else:
            data['seats'].pop('quality-initial')
    state._write_state(lose, day.root)
    assert follow(day)['action'] == 'raise'
    delta = day.data['gate_verdicts']['A:quality:delta']
    assert (delta['verdict'], delta['head']) == ('PASS', day.head)


def test_a_shepherd_that_stopped_without_a_pr_is_retried_then_parked(day):
    # Contradiction 5: raise_action returned only a why lookup once shepherd-A existed.
    passed(day)
    day.runtime.raises = False
    first = dispatch_next(day)
    assert first['action'] == 'raise' and first['commands']
    run(day, first)
    run(day, dispatch_next(day))  # its launch; the seat stops with no PR
    retry = dispatch_next(day)
    assert retry['action'] == 'raise' and 'shepherd-A-2' in retry['commands'][0]
    run(day, retry)
    run(day, dispatch_next(day))
    # twice without a PR: a specific owner decision, the resume card of the parked item
    code, out, _ = act(day, 'next', '--json')
    found = json.loads(out)
    assert found['decision']['command'] == 'wuwei plan resume A', found
    assert day.data['items']['A']['phase'] == 'parked'


def test_a_shepherd_retry_raises_the_pr(day):
    passed(day)
    day.runtime.raises = False
    for _ in range(2):
        run(day, dispatch_next(day))
    day.runtime.raises = True
    for _ in range(2):
        run(day, dispatch_next(day))
    assert day.data['items']['A']['phase'] == 'raised'


def test_a_blocked_stop_passes_the_strict_spec_stop_guard(tmp_path):
    # Contradiction 6: _common.md Decisions 1 has a builder stop on an owner-only question; in
    # strict mode the stop guard (guards.spec.check_stop) demanded the spec artifacts first.
    from wuwei import specmode
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('[spec]\nengine = "speckit"\nmode = "strict"\n')
    config, tree = workspace.load_config(tmp_path), tmp_path / 'tree'
    tree.mkdir()
    artifact = tree / 'specs/a/spec.md'
    artifact.parent.mkdir(parents=True)
    artifact.write_text('# Spec\n')
    row = {'phase': 'implement', 'status': 'running'}
    assert specmode.named(tmp_path, config, 'A', row, tree, 'Blocked: none\nGap: none\nChange: none\n')[0] == 1
    result = specmode.named(tmp_path, config, 'A', row, tree,
                            'Blocked: none; context for the gates\nGap: none\nChange: none\n')
    assert result[0] == 1 and 'final message must name the spec artifacts' in result[1]
    assert specmode.named(tmp_path, config, 'A', row, tree,
                          'Blocked: none; context for the gates\nspecs/a\n')[0] == 0
    text = 'Blocked: the schema change needs the owner\nGap: none\nChange: none\n'
    assert specmode.named(tmp_path, config, 'A', row, tree, text) == (0, '')


@pytest.mark.parametrize('context', ['', ' This needs owner approval.', '\nThis needs owner approval.'])
def test_a_blocked_builder_stops_and_the_owner_is_asked_before_its_checks(day, context):
    # Contradiction 6: a builder stops on an owner-only question; strict spec mode demanded the
    # spec artifacts first, and a later build check sent it back to write them.
    from fakes import owner
    day.plan()
    day.approve()
    day.run('plan', 'session', 'planner')
    day.runtime.spec, day.runtime.blocked = False, 'the schema change needs the owner'
    day.brief('builder', 'builder-initial')
    day.execute(json.loads(day.run('build', 'next', 'A')))  # its SubagentStop passes the spec guard
    code, out, _ = act(day, 'build', 'next', 'A')
    asked = json.loads(out)
    assert (code, asked['action'], asked['command']) == (1, 'escalate', 'wuwei build next A')
    assert asked['reason'] == 'builder blocked: the schema change needs the owner; ask this card verbatim'
    found = json.loads(act(day, 'next', '--json')[1])
    assert found['decision']['card'] == asked['card']
    card = {**asked['card'], 'question': asked['card']['question'] + context}
    owner._record(day.root, card, 'Yes', 'planner-session', None)
    day.runtime.spec, day.runtime.blocked = True, None
    action = json.loads(day.run('build', 'next', 'A'))
    assert action['action'] == 'continue' and 'the schema change needs the owner' in action['feedback']
    day.steps({**action, 'brief': str(day.root / day.data['builds']['A']['brief']), 'worktree': str(day.repo)})
    assert day.data['items']['A']['phase'] == 'gate'


@pytest.mark.parametrize('changed', ['missing-token', 'wrong-command'])
def test_issue_940_blocked_build_names_the_mismatched_answer(day, changed):
    from fakes import owner
    day.plan()
    day.approve()
    day.run('plan', 'session', 'planner')
    day.runtime.blocked = 'the schema change needs the owner'
    day.brief('builder', 'builder-initial')
    day.execute(json.loads(day.run('build', 'next', 'A')))
    asked = json.loads(act(day, 'build', 'next', 'A')[1])
    card = dict(asked['card'])
    card['question'] = (card['question'].rsplit(' (', 1)[0] if changed == 'missing-token'
                        else card['question'].replace('build next', 'dispatch next') + ' Context.')
    owner._record(day.root, card, 'Yes', 'planner-session', None)
    code, out, _ = act(day, 'build', 'next', 'A')
    refused = json.loads(out)
    assert (code, refused['action']) == (1, 'escalate')
    assert 'did not match' in refused['reason']
    assert ('answered card matched token' if changed == 'wrong-command'
            else 'answered card matched command') in refused['reason']
    assert refused['card'] == asked['card']
    decision = json.loads(act(day, 'next', '--json')[1])['decision']
    assert 'did not match' in decision['why']


def test_a_blocked_builder_the_owner_says_no_to_parks(day):
    from fakes import owner
    day.plan()
    day.approve()
    day.run('plan', 'session', 'planner')
    day.runtime.blocked = 'the schema change needs the owner'
    day.brief('builder', 'builder-initial')
    day.execute(json.loads(day.run('build', 'next', 'A')))
    asked = json.loads(act(day, 'build', 'next', 'A')[1])
    owner._record(day.root, asked['card'], 'No', 'planner-session', None)
    code, out, _ = act(day, 'build', 'next', 'A')
    assert json.loads(out)['action'] == 'parked' and day.data['items']['A']['phase'] == 'parked'


def test_the_broken_config_recovery_commands_pass_the_hook(tmp_path, monkeypatch, capsys):
    # Contradiction 7: recovery.md prescribes config check and init --upgrade (doctor --fix offers
    # it); the hook let only repair reads and config set through.
    from test_config_failure import BROKEN, replay
    from fakes.integrity import seed
    root = tmp_path / 'ws'
    (root / '.wuwei').mkdir(parents=True)
    (root / '.wuwei/config.toml').write_text(BROKEN)
    seed(root)
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    launcher = str(ROOT / 'bin/wuwei')
    code, out, _ = replay(monkeypatch, capsys, root, 'PreToolUse', 'Bash', {'command': 'ls'})
    reason = json.loads(out)['hookSpecificOutput']['permissionDecisionReason']
    assert 'bin/wuwei config check' in reason and 'bin/wuwei doctor --fix' in reason
    for argv in ('config check', 'doctor --fix', 'doctor --fix --apply init-upgrade'):
        code, out, _ = replay(monkeypatch, capsys, root, 'PreToolUse', 'Bash', {'command': f'{launcher} {argv}'})
        assert (code, out) == (0, ''), argv
    from wuwei.sessions import owner_card
    card = {key: value for key, value in owner_card('bin/wuwei doctor --fix', 'x', 'abc').items() if key != 'record'}
    code, _, _ = replay(monkeypatch, capsys, root, 'PreToolUse', 'AskUserQuestion', {'questions': [card]})
    assert code == 0
    for argv in ('init --upgrade', 'plan session x'):
        code, _, _ = replay(monkeypatch, capsys, root, 'PreToolUse', 'Bash', {'command': f'{launcher} {argv}'})
        assert code == 2, argv


def test_docs_agree_on_owner_actions_and_integrity():
    # Contradictions 8 and 9: the docs against the lead charter and the warning-only integrity.
    from wuwei.commands.next import ENFORCE
    docs = ROOT / 'docs/site'
    assert 'pre-approves' not in (docs / 'reference.md').read_text()
    assert 'does not pre-approve' in (docs / 'reference.md').read_text()
    assert 'block tools' not in (docs / 'index.md').read_text()
    assert 'integrity' not in ENFORCE[True].split('block')[0]
    recovery = (docs / 'recovery.md').read_text()
    assert 'doctor --fix' in recovery.split('### config.toml does not load')[1].split('###')[0]


def test_next_and_dispatch_next_take_one_gate_decision(day):
    # derive offered a gate step for a build back at its checks; dispatch next refused it.
    passed(day)
    commit(day)
    found = json.loads(act(day, 'next', '--json')[1])
    [entry] = found['launches']
    assert entry['action'] == 'check'  # the moved head goes back to its fast checks
    code, out, _ = act(day, 'next', '--json')
    [entry] = json.loads(out)['launches']
    assert (code, entry['kind'], entry['action']) == (0, 'build', 'check'), entry
    day.run(*shlex.split(entry['command'])[1:])
    [entry] = json.loads(act(day, 'next', '--json')[1])['launches']
    assert entry['kind'] == 'gates' and entry['commands']


def test_a_polish_offer_is_offered_as_polish(tmp_path, monkeypatch):
    # derive said raise where dispatch next offered polish.
    from test_dispatch import PASS, record
    from wuwei import derive, dispatch
    root = tmp_path
    (root / '.wuwei').mkdir()
    (root / '.wuwei/config.toml').write_text('[spec]\nengine = "none"\n')
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00Z')
    state._write_state(lambda data: data.update(
        gate_approved=True, approved_items=['A'], items={'A': {'phase': 'gate', 'status': 'queued'}}), root)
    state._write_state(lambda data: data['seats'].update(builder={
        'item': 'A', 'role': 'builder', 'status': 'stopped'}), root)
    note = PASS + '## Findings\n- P3 | cli/example.py:3 | fails when renamed later | blocks: no\nSimplicity: none\nDesign: none\n'
    for role in ('arch', 'quality', 'security'):
        record(root, role, f'{role}-1', note)
    data, config = state.read_state(root), workspace.load_config(root)
    [launch] = derive.offers(data, root, config)['launches']
    assert launch['kind'] == 'polish'
    assert dispatch.resolve_offer(root, launch)['action'] == 'polish'


def test_a_stale_second_opinion_reruns_through_dispatch_opinion(tmp_path, monkeypatch):
    # review F2: a stale role@codex was briefed as a Claude seat under its base role's fresh name
    # (a duplicate brief the second refuses) and dispatch opinion returned the stale record.
    import test_dispatch
    from test_dispatch import FakeRuntime, PASS, QUALITY_PASS, record, standard
    from wuwei import dispatch, registry
    root = tmp_path
    (root / '.wuwei').mkdir()
    (root / '.wuwei/config.toml').write_text(
        '[spec]\nengine = "none"\n[gates]\nsecond_opinion = "codex:m1"\nsecond_opinion_when = []\n')
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00Z')
    state._write_state(lambda data: data.update(
        gate_approved=True, approved_items=['A'], items={'A': {'phase': 'gate', 'status': 'queued'}}), root)
    state._write_state(lambda data: data['seats'].update(builder={
        'item': 'A', 'role': 'builder', 'status': 'stopped'}), root)
    standard(root)
    for role, name in (('arch', 'arch-1'), ('security', 'security-1')):
        record(root, role, name, PASS, agent_id='ag-' + role)
    record(root, 'quality', 'quality-1', QUALITY_PASS, agent_id='ag-q')
    record(root, 'quality@codex', 'quality-1-codex', QUALITY_PASS, runtime='codex', model='m1')
    assert dispatch.next_step('A', root)['action'] == 'raise'
    current = 'def5678' + '0' * 33
    (root / 'tree/.git').mkdir(parents=True)
    (root / 'tree/.git/HEAD').write_text(current + '\n')
    state._write_state(lambda data: data['items']['A'].update(worktree='tree'), root)
    found = dispatch.next_step('A', root)
    assert found['roles'] == test_dispatch.ALL + ['quality@codex']
    assert len(found['commands']) == len(set(found['commands'])) == 3
    assert not any('codex' in command for command in found['commands'])
    runtime = FakeRuntime()
    real = registry.load
    monkeypatch.setattr(registry, 'load', lambda kind, config: runtime if kind == 'runtime' else real(kind, config))
    with pytest.raises(dispatch.Refused, match='write the quality gate brief first'):
        dispatch.opinion('A', root)  # never the stale record; it reruns once the fresh brief exists
