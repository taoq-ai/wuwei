"""Planner decisions use recorded evidence and never launch agents."""

import json

import pytest

from wuwei import state, workspace


PASS = 'Verdict: PASS\nHead: abc1234\nProbe: not run\nVAL: PASS\nBlocked: none\nGap: none\nChange: none\n'
FIX = ('Verdict: FIX\nHead: abc1234\n'
       '- P1 | cli/example.py:12 | fails when empty | blocks: yes\n'
       'Probe: not run\nVAL: PASS\nBlocked: none\nGap: none\nChange: none\n')


@pytest.fixture
def root(tmp_path, monkeypatch):
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('')
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00Z')
    state._write_state(lambda data: data.update(
        gate_approved=True, approved_items=['A'],
        items={'A': {'phase': 'planned', 'status': 'queued'}}), tmp_path, reserved=False)
    state.transition('A', 'implement', tmp_path)
    state.transition('A', 'gate', tmp_path)
    state._write_state(lambda data: data['seats'].update(builder={
        'item': 'A', 'role': 'builder', 'status': 'stopped'}), tmp_path, reserved=False)
    return tmp_path


def test_gate_dispatch_and_live_builder_refusal(root):
    from wuwei import dispatch

    assert dispatch.next_step('A', root) == {'action': 'gates', 'roles': ['arch', 'quality', 'security']}
    state._write_state(lambda data: data['seats'].update(builder={
        'item': 'A', 'role': 'builder', 'status': 'running'}), root, reserved=False)
    with pytest.raises(dispatch.Refused, match='builder'):
        dispatch.next_step('A', root)


def test_gate_dispatch_requires_builder_stand_down(root):
    from wuwei import dispatch

    state._write_state(lambda data: data['seats'].clear(), root, reserved=False)
    with pytest.raises(dispatch.Refused, match='stand down'):
        dispatch.next_step('A', root)


def record(root, role, name, text, round_name='initial'):
    from wuwei import dispatch

    directory = workspace.day_dir(root)
    (directory / 'briefs').mkdir(exist_ok=True)
    (directory / 'decisions').mkdir(exist_ok=True)
    (directory / 'briefs' / f'{name}.md').write_text('Head: abc1234\n')
    (directory / 'decisions' / f'gate-{name}.md').write_text(text)
    state._write_state(lambda data: data['seats'].update({
        name: {'item': 'A', 'role': 'sentinel-' + role, 'status': 'stopped',
               'brief': str((directory / 'briefs' / f'{name}.md').relative_to(root))}}),
        root, reserved=False)
    dispatch.receive('A', role, name, round_name, root)


def test_fix_pass_then_only_quality_delta(root):
    from wuwei import dispatch

    record(root, 'arch', 'arch-1', PASS)
    record(root, 'quality', 'quality-1', FIX + 'Simplicity: none\nDesign: none\n')
    with pytest.raises(dispatch.Refused, match='already received'):
        record(root, 'quality', 'quality-again', FIX + 'Simplicity: none\nDesign: none\n')
    assert dispatch.next_step('A', root)['roles'] == ['security']
    record(root, 'security', 'security-1', PASS)
    assert dispatch.next_step('A', root) == {'action': 'fix', 'roles': ['quality']}
    state.transition('A', 'fix', root)
    state.transition('A', 'delta', root)
    assert dispatch.next_step('A', root) == {'action': 'gates', 'roles': ['quality']}
    record(root, 'quality', 'quality-2', PASS + 'Simplicity: none\nDesign: none\n', 'delta')
    assert dispatch.next_step('A', root) == {'action': 'raise', 'notes': []}
    state.transition('A', 'fix', root)
    assert dispatch.next_step('A', root) == {
        'action': 'escalate', 'reason': 'fix round already used'}


def test_blocking_delta_escalates_and_bad_verdict_is_unmeasured(root):
    from wuwei import dispatch

    for role in ('arch', 'quality', 'security'):
        text = FIX if role == 'security' else PASS
        if role == 'quality':
            text += 'Simplicity: none\nDesign: none\n'
        record(root, role, role + '-1', text)
    state.transition('A', 'fix', root)
    state.transition('A', 'delta', root)
    record(root, 'security', 'security-2', FIX, 'delta')
    assert dispatch.next_step('A', root)['action'] == 'escalate'
    with pytest.raises(dispatch.Refused, match='already received'):
        record(root, 'security', 'security-3', FIX, 'delta')


def test_invalid_verdict_does_not_enter_trusted_state(root):
    from wuwei import dispatch

    with pytest.raises(dispatch.Refused, match='REJECT'):
        record(root, 'quality', 'quality-bad', 'Verdict: PASS\n')
    assert state.read_state(root)['gate_verdicts'] == {}


def test_discovery_trigger(root):
    from wuwei import dispatch

    assert dispatch.discovery('sweep', root) == {'action': 'discover'}
    assert dispatch.discovery('seat-free', root) == {'action': 'discover'}
    state._write_state(lambda data: data['items'].update({
        'B': {'phase': 'planned'}, 'C': {'phase': 'planned'}}), root, reserved=False)
    assert dispatch.discovery('seat-free', root) == {'action': 'none'}
    events = [json.loads(line)['kind'] for line in (workspace.day_dir(root) / 'events.jsonl').read_text().splitlines()]
    assert events.count('discovery.requested') == 2


def test_delta_nonblocking_residual_becomes_review_note(root):
    from wuwei import dispatch

    record(root, 'arch', 'arch-1', PASS)
    record(root, 'quality', 'quality-1', FIX + 'Simplicity: none\nDesign: none\n')
    record(root, 'security', 'security-1', PASS)
    state.transition('A', 'fix', root)
    state.transition('A', 'delta', root)
    residual = FIX.replace('blocks: yes', 'blocks: no')
    record(root, 'quality', 'quality-2', residual + 'Simplicity: none\nDesign: none\n', 'delta')
    outcome = dispatch.next_step('A', root)
    assert outcome['action'] == 'raise'
    assert 'cli/example.py:12' in outcome['notes'][0]
    state.transition('A', 'fix', root)
    assert dispatch.next_step('A', root) == {
        'action': 'escalate', 'reason': 'fix round already used'}


def test_delta_refuses_role_that_already_passed(root):
    from wuwei import dispatch

    record(root, 'arch', 'arch-1', PASS)
    record(root, 'quality', 'quality-1', FIX + 'Simplicity: none\nDesign: none\n')
    record(root, 'security', 'security-1', PASS)
    state.transition('A', 'fix', root)
    state.transition('A', 'delta', root)
    with pytest.raises(dispatch.Refused, match='did not need a delta'):
        record(root, 'arch', 'arch-2', PASS, 'delta')


def test_receive_rejects_wrong_head(root):
    from wuwei import dispatch

    with pytest.raises(dispatch.Refused, match='HEAD'):
        record(root, 'arch', 'arch-wrong', PASS.replace('abc1234', 'def5678'))
    assert state.read_state(root)['gate_verdicts'] == {}


def test_receive_rechecks_current_worktree_head(root, monkeypatch):
    from wuwei import dispatch, registry
    from wuwei.registry import Result

    class VCS:
        def head(self, tree, *, root):
            return Result(0, {'sha': 'def5678'})

    monkeypatch.setattr(registry, 'load', lambda kind, config: VCS())
    directory = workspace.day_dir(root)
    (directory / 'briefs').mkdir(exist_ok=True)
    (directory / 'decisions').mkdir(exist_ok=True)
    (directory / 'briefs/arch.md').write_text('Head: abc1234\nWorktree: ' + str(root) + '\n')
    (directory / 'decisions/gate-arch.md').write_text(PASS)
    state._write_state(lambda data: data['seats'].update(arch={
        'item': 'A', 'role': 'sentinel-arch', 'status': 'stopped',
        'brief': str((directory / 'briefs/arch.md').relative_to(root))}),
        root, reserved=False)
    with pytest.raises(dispatch.Refused, match='current worktree HEAD'):
        dispatch.receive('A', 'arch', 'arch', root=root)


def test_receive_accepts_short_head_against_full_brief(root):
    from wuwei import dispatch

    directory = workspace.day_dir(root)
    (directory / 'briefs').mkdir(exist_ok=True)
    (directory / 'decisions').mkdir(exist_ok=True)
    (directory / 'briefs/arch.md').write_text('HEAD: ' + 'a' * 40 + '\n')
    (directory / 'decisions/gate-arch.md').write_text(PASS.replace('abc1234', 'a' * 7))
    state._write_state(lambda data: data['seats'].update(arch={
        'item': 'A', 'role': 'sentinel-arch', 'status': 'stopped',
        'brief': str((directory / 'briefs/arch.md').relative_to(root))}),
        root, reserved=False)
    assert dispatch.receive('A', 'arch', 'arch', root=root)['verdict'] == 'PASS'


def test_receive_accepts_short_current_worktree_head(root, monkeypatch):
    from wuwei import dispatch, registry
    from wuwei.registry import Result

    class VCS:
        def head(self, tree, *, root):
            return Result(0, {'sha': 'a' * 40})

    monkeypatch.setattr(registry, 'load', lambda kind, config: VCS())
    directory = workspace.day_dir(root)
    (directory / 'briefs').mkdir(exist_ok=True)
    (directory / 'decisions').mkdir(exist_ok=True)
    (directory / 'briefs/arch.md').write_text('HEAD: ' + 'a' * 40 +
                                             '\nWorktree: ' + str(root) + '\n')
    (directory / 'decisions/gate-arch.md').write_text(PASS.replace('abc1234', 'a' * 7))
    state._write_state(lambda data: data['seats'].update(arch={
        'item': 'A', 'role': 'sentinel-arch', 'status': 'stopped',
        'brief': str((directory / 'briefs/arch.md').relative_to(root))}),
        root, reserved=False)
    assert dispatch.receive('A', 'arch', 'arch', root=root)['verdict'] == 'PASS'


def test_cli_next_contract(root, monkeypatch, capsys):
    from wuwei.__main__ import main

    monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
    assert main(['dispatch', 'next', 'A']) == 0
    assert json.loads(capsys.readouterr().out)['roles'] == ['arch', 'quality', 'security']
    assert main(['dispatch', 'next', 'UNKNOWN']) == 1
    assert 'approved' in capsys.readouterr().err
