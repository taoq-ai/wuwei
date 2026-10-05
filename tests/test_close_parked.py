"""A disposed item never blocks the close through a measurement (#517)."""

import pytest

from test_stop import case  # noqa: F401  (fixture)
from wuwei import closing, plan, state, steward, workspace
from wuwei.__main__ import main
from wuwei.registry import Result

ITEMS = ('DIV-1', 'DIV-2', 'DIV-3')


def day(root, monkeypatch, park=ITEMS, open_item=None, vcs=None):
    names = [*park, *([open_item] if open_item else [])]
    state._write_state(lambda data: data.update(
        items={n: {'status': 'running', 'phase': 'planned', 'worktree': f'wt/{n}'} for n in names},
        approved_items=names), root, reserved=False)
    if open_item:
        (root / 'wt' / open_item).mkdir(parents=True)
        if vcs:
            vcs.results.update(branch=Result(0, {'name': 'div-4'}), pushed_branches=Result(0, []))
    for name in park:
        plan.dispose(name, 'parked', reason=f'blocked on {name}', root=root)
    monkeypatch.chdir(root)
    calls = []
    monkeypatch.setattr(steward, 'run', lambda root, trigger: calls.append(trigger))
    return calls


def test_parked_items_with_missing_worktrees_do_not_gate(case, monkeypatch):
    root, _, vcs = case
    day(root, monkeypatch)
    vcs.results['branch'] = Result(2, reason='must not be read')
    notes = []
    code, reason = closing.unresolved(root, [], notes=notes)
    assert (code, reason) == (0, '')
    assert notes == [f'{n}: parked (blocked on {n}), unmeasured: worktree missing' for n in ITEMS]


def test_failed_read_is_a_note_when_carried_and_exit_2_when_open(case, monkeypatch):
    root, _, vcs = case
    day(root, monkeypatch, park=(), open_item='DIV-4')
    vcs.results['branch'] = Result(2, reason='no commits')
    assert closing.unresolved(root, [])[0] == 2
    plan.dispose('DIV-4', 'carried', root=root)
    notes = []
    assert closing.unresolved(root, [], notes=notes) == (0, '')
    assert notes == ['DIV-4: carried, unmeasured: no commits']


def test_carried_pushed_branch_without_pr_still_found(case, monkeypatch):
    root, _, vcs = case
    day(root, monkeypatch, park=(), open_item='DIV-4')
    plan.dispose('DIV-4', 'carried', root=root)
    vcs.results['branch'] = Result(0, {'name': 'div-4'})
    vcs.results['pushed_branches'] = Result(0, ['div-4'])
    code, reason = closing.unresolved(root, [])
    assert code == 1 and 'pushed branch div-4 has no raised or claimed PR' in reason


def test_close_launches_retro_on_disposed_day(case, monkeypatch, capsys):
    root, _, _ = case
    calls = day(root, monkeypatch)
    assert main(['close']) == 0
    out = capsys.readouterr().out
    assert calls == ['close']
    assert all(f'{n}: parked (blocked on {n}), unmeasured: worktree missing' in out for n in ITEMS)


def test_close_with_open_item_does_not_launch_retro(case, monkeypatch, capsys):
    root, _, vcs = case
    calls = day(root, monkeypatch, open_item='DIV-4', vcs=vcs)
    assert main(['close']) == 1
    out = capsys.readouterr().out
    assert 'plan carry DIV-4' in out and 'plan park DIV-4' in out
    assert calls == []


@pytest.mark.parametrize('open_item,expected', [('DIV-4', 1), (None, 0)])
def test_close_why_writes_nothing(case, monkeypatch, capsys, open_item, expected):
    root, _, vcs = case
    calls = day(root, monkeypatch, open_item=open_item, vcs=vcs)
    directory = workspace.day_dir(root)
    before = [(directory / f).read_bytes() for f in ('state.json', 'events.jsonl')]
    capsys.readouterr()
    assert main(['close', '--why']) == expected
    lines = capsys.readouterr().out.splitlines()
    assert [line.split(':')[0] for line in lines] == [*ITEMS, *([open_item] if open_item else [])]
    if open_item:
        assert f'plan carry {open_item}' in lines[-1] and f'plan park {open_item}' in lines[-1]
    assert [(directory / f).read_bytes() for f in ('state.json', 'events.jsonl')] == before
    assert calls == []


def test_close_does_not_report_a_mandate_decision_as_pending(tmp_path, monkeypatch):
    # #530: a decision taken under the mandate is not a pending owner decision.
    from test_decision import VALID
    from wuwei import closing, state, workspace
    root = tmp_path
    (root / '.wuwei').mkdir()
    (root / '.wuwei/config.toml').write_text('')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00Z')
    directory = workspace.day_dir(root) / 'decisions'
    directory.mkdir(parents=True)
    (directory / 'D-1.md').write_text(VALID.replace('two-way', 'one-way').replace('Decided-by: seat', 'Decided-by: mandate'))
    state._write_state(lambda data: data.update(decision_outcomes={
        'D-1': {'option': 'A', 'decided_by': 'mandate', 'reversibility': 'one-way', 'cisr': 'Consequential'}}),
        root, reserved=False)
    assert 'D-1' not in closing.unresolved(root, [])[1]
