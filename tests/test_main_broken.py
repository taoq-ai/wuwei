"""#648: one broken main is one fix item; the items it breaks wait on it, then rerun."""

import json
from pathlib import Path

import pytest

from wuwei import dispatch, fast_checks, registry, state, workspace
from wuwei.commands import build
from test_build import events
from test_build_next import launch, seat, stop  # noqa: F401 (seat is a fixture)
from test_dispatch import day_set  # noqa: F401 (a fixture)
from test_next import approved, coarse, root  # noqa: F401 (root is a fixture)

LINT = "cli/untouched.py:3:1: F401 'os' imported but unused"
FIX = 'fix-main-app-cli-untouched-py'


def lint(error=LINT):
    return registry.Result(1, {'test_ids': [], 'error': error})


@pytest.fixture
def tree(tmp_path):
    for name in ('cli/untouched.py', 'cli/own.py'):
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text('')
    return tmp_path


@pytest.mark.parametrize('error,held', [
    (LINT, True),
    ('  --> cli/untouched.py:3:1', True),
    ('./cli/untouched.py:3: error: Name "x" is not defined', True),
    ('cli/own.py:3:1: F401', False),
    (LINT + '\ncli/own.py:4:1: F401', False),
    ('cli/missing.py:3:1: F401', False),
    ('../cli/untouched.py:3:1: F401', False),
    ('broken', False),
    (LINT + '\nFAILED tests/test_x.py::test_one', False),
    ('ERROR tests/test_x.py\n' + LINT, False),
])
def test_unchanged_holds_only_lint_locations_on_unchanged_files(tree, error, held):
    found = fast_checks.unchanged([('ruff check .', {'test_ids': [], 'error': error})], {'cli/own.py'}, tree)
    assert found == ([('ruff check .', 'cli/untouched.py')] if held else [])


def test_unchanged_needs_every_failure_held(tree):
    other = {'error': 'cli/own.py:1:1: E1'}
    assert fast_checks.unchanged([('a', {'error': LINT}), ('b', {'error': LINT})], set(), tree) == [
        ('a', 'cli/untouched.py'), ('b', 'cli/untouched.py')]
    assert fast_checks.unchanged([('a', {'error': LINT}), ('b', other)], {'cli/own.py'}, tree) == []
    assert fast_checks.unchanged([('a', {'test_ids': ['t'], 'error': LINT})], set(), tree) == []
    assert fast_checks.unchanged([('a', 'text')], set(), tree) == []


def write(root, change):
    path = workspace.day_dir(root) / 'state.json'
    data = json.loads(path.read_text())
    change(data)
    path.unlink()
    path.write_text(json.dumps(data))


@pytest.fixture
def held_day(seat, monkeypatch):
    """A and B building on one goal, each changing its own file; both stopped, awaiting checks."""
    root, repo, _, _, _ = seat
    other = root / 'other'
    for tree in (repo, other):
        for name in ('cli/untouched.py', 'cli/a.py', 'cli/b.py'):
            (tree / name).parent.mkdir(parents=True, exist_ok=True)
            (tree / name).write_text('')
    write(root, lambda data: data.update(
        gate_approved=True, goals=['G-1'], approved_items=['A', 'B'],
        items={name: {'phase': 'implement', 'status': 'running', 'goal': 'G-1'} for name in 'AB'}))
    launch(seat, build.next_action('A', root=root))
    assert stop(seat) == (0, '')
    record = state.read_state(root)['builds']['A']
    write(root, lambda data: data['builds'].update(B={**record, 'worktree': str(other.resolve())}))
    own = {str(Path(record['worktree'])): 'cli/a.py', str(other.resolve()): 'cli/b.py'}
    monkeypatch.setattr(dispatch, '_changes', lambda root, config, row: (None, [{'path': own[row['worktree']]}]))
    return root, record, other, seat


def check(root, item, *results):
    return build.complete_checks(item, list(results), root=root)




def test_one_broken_main_holds_both_items_on_one_fix_item(held_day):
    # Acceptance 1
    root, _, _, _ = held_day
    assert check(root, 'A', lint()) == 1
    assert check(root, 'B', lint()) == 1
    data = state.read_state(root)
    assert list(data['main_broken']) == [FIX]
    entry = data['main_broken'][FIX]
    assert (entry['repo'], entry['check'], entry['path'], entry['items']) == ('app', 'test', 'cli/untouched.py', ['A', 'B'])
    assert data['items'][FIX]['phase'] == 'planned' and FIX in data['approved_items']
    assert data['items'][FIX]['title'].startswith('Fix main: cli/untouched.py')
    for name in 'AB':
        action = data['builds'][name]['action']
        assert action['action'] == 'wait' and action['fix'] == FIX and FIX in action['reason']
        assert 'fix_rounds' not in data['builds'][name]
        assert state.held(data, name) == FIX
    day = workspace.day_dir(root)
    assert [(e['payload']['item'], e['payload']['fix']) for e in events(day) if e['kind'] == 'build.held'] == [
        ('A', FIX), ('B', FIX)]
    assert len([e for e in events(day) if e['kind'] == 'plan.added']) == 1


@pytest.mark.parametrize('case', ['own', 'uncommitted', 'mixed', 'unreadable', 'test'])
def test_an_items_own_failure_goes_back_to_its_builder(held_day, monkeypatch, case):
    root, _, _, _ = held_day
    results = [lint()]
    if case == 'own':
        results = [lint('cli/a.py:3:1: F401')]
    elif case == 'uncommitted':
        monkeypatch.setattr(registry.load('vcs', {}), 'status',
                            lambda *a, **kw: registry.Result(0, [{'path': 'cli/untouched.py'}]))
    elif case == 'mixed':
        state._write_state(lambda data: data['builds']['A'].update(commands=['one', 'two']), root, reserved=False)
        results = [lint(), lint('cli/a.py:1:1: E1')]
    elif case == 'unreadable':
        monkeypatch.setattr(dispatch, '_changes', lambda *a: (_ for _ in ()).throw(ValueError('no remote')))
    else:
        results = [registry.Result(1, {'test_ids': ['tests/test_x.py::t'], 'error': LINT})]
    assert check(root, 'A', *results) == 1
    data = state.read_state(root)
    assert data['builds']['A']['action']['action'] == 'continue'
    assert 'main_broken' not in data and FIX not in data['items']


def test_release_after_the_fix_merges_then_checks_rerun(held_day):
    # Acceptance 2
    root, record, other, seat = held_day
    check(root, 'A', lint())
    check(root, 'B', lint())
    day = workspace.day_dir(root)
    wait = build.next_action('A', root=root)
    before = (day / 'events.jsonl').read_bytes()
    assert build.next_action('A', root=root) == wait and wait['action'] == 'wait'
    assert (day / 'events.jsonl').read_bytes() == before
    write(root, lambda data: data['items'][FIX].update(phase='merged'))
    released = {'A': build.next_action('A', root=root),
                'B': build.next_action('B', root / record['brief'], other, root=root)}
    for action in released.values():
        assert action['action'] == 'continue' and action['resume'] == 'agent-builder'
        assert FIX in action['feedback'] and 'Rebase' in action['feedback']
        assert 'change nothing else' in action['feedback']
    assert build.next_action('A', root=root) == released['A']
    assert [e['payload']['item'] for e in events(day) if e['kind'] == 'build.released'] == ['A', 'B']
    assert 'fix_rounds' not in state.read_state(root)['builds']['A']
    launch(seat, released['A'], released['A']['resume'])
    assert stop(seat) == (0, '')
    assert check(root, 'A', registry.Result(0)) == 0
    assert state.read_state(root)['items']['A']['phase'] == 'gate'


def test_a_parked_fix_releases_and_the_failure_is_not_held_again(held_day):
    root, _, _, seat = held_day
    check(root, 'A', lint())
    write(root, lambda data: data['items'][FIX].update(phase='parked', resume_phase='planned'))
    action = build.next_action('A', root=root)
    assert action['action'] == 'continue' and 'parked' in action['feedback']
    launch(seat, action, action['resume'])
    assert stop(seat) == (0, '')
    check(root, 'A', lint())
    action = state.read_state(root)['builds']['A']['action']
    assert action['action'] == 'continue' and 'F401' in action['feedback']


def test_a_merged_fix_gets_a_successor_and_a_fix_item_never_holds_itself(held_day):
    root, _, _, _ = held_day
    write(root, lambda data: data['items'].update({FIX: {'phase': 'merged', 'goal': 'G-1'}}))
    check(root, 'A', lint())
    assert state.read_state(root)['builds']['A']['action']['fix'] == FIX + '-2'
    successor = FIX + '-2'
    write(root, lambda data: (data['items'][successor].update(phase='implement'),
                              data['builds'].update({successor: data['builds'].pop('B')})))
    check(root, successor, lint())
    assert state.read_state(root)['builds'][successor]['action']['action'] == 'continue'


def test_no_hold_when_the_fix_item_cannot_be_admitted(held_day):
    root, _, _, _ = held_day
    write(root, lambda data: data['items']['A'].pop('goal'))
    check(root, 'A', lint())
    data = state.read_state(root)
    assert data['builds']['A']['action']['action'] == 'continue' and 'main_broken' not in data


def test_launch_set_gives_a_held_item_no_seat(day_set, monkeypatch):
    root, _ = day_set
    state._write_state(lambda data: data.update(builds={'B': {'status': 'ready', 'action': {
        'action': 'wait', 'fix': 'P1', 'reason': 'main is broken: fix item P1'}}}), root, reserved=False)
    monkeypatch.setattr(build, 'next_action', lambda item, root=None: state.read_state(root)['builds'][item]['action'])
    value = dispatch.launch_set(root)
    assert value['building'] == 0
    entries = {row['item']: row for row in value['entries']}
    assert entries['B']['action'] == 'wait' and 'P1' in entries['B']['reason']
    assert sum(row['action'] == 'start' for row in value['entries']) == 3 and entries['P1']['action'] == 'start'


def test_the_fix_items_brief_reads_main_broken(day_set):
    root, _ = day_set
    state._write_state(lambda data: data.update(main_broken={'P3': {
        'repo': 'app', 'scope': 'Fix main: cli/untouched.py fails ruff', 'evidence': 'ruff fails there'}}),
        root, reserved=False)
    assert dispatch.candidate(root, 'P3')['repo'] == 'app'
    assert dispatch._start(root, 'P3', [])[-1].endswith(
        "'Implement P3: Fix main: cli/untouched.py fails ruff. Evidence: ruff fails there.'")


def test_next_skips_held_items_and_offers_the_fix(root):
    wait = {'status': 'ready', 'action': {'action': 'wait', 'fix': 'F', 'reason': 'held'}}
    for phase, expected in (('planned', ('dispatch', 'wuwei dispatch next --all')),
                            ('merged', ('build', 'wuwei build next A'))):
        approved(root, {'A': ('implement', {}), 'B': ('implement', {}), 'F': (phase, {})}, cap=2,
                 builds={'A': wait, 'B': wait})
        found = coarse(root)
        assert (found['state'], found['command']) == expected
    approved(root, {'A': ('implement', {})}, builds={'A': wait})
    found = coarse(root)
    assert found['state'] == 'wait' and 'A' in found['why'] and 'F' in found['why']


def test_builder_charter_says_a_broken_main_is_not_fixed_in_the_branch():
    top = Path(__file__).resolve().parents[1]
    sentence = 'A repository check that fails only on files your item does not change means main is broken'
    for path in ('charters/builder.md', 'agents/builder.md'):
        assert sentence in (top / path).read_text(encoding='utf-8'), path


@pytest.mark.parametrize('kind', ['build.held', 'build.released'])
def test_hold_events_are_reserved_and_silent(root, capsys, kind):
    from wuwei import signal
    from wuwei.__main__ import main
    capsys.readouterr()
    assert main(['event', kind, '{}']) == 1
    assert f'{kind}: reserved; written by wuwei build' in capsys.readouterr().err
    assert signal.classify({'kind': kind, 'payload': {}}, {})[0] == 'silent'


def test_codex_loop_exits_on_a_held_item(tmp_path, monkeypatch, capsys):
    from test_build import setup
    repo, brief, _, runtime = setup(tmp_path, monkeypatch, [])
    monkeypatch.setattr(build, 'next_action', lambda *a, **kw: {'action': 'wait', 'fix': 'F', 'reason': 'main is broken'})
    assert build.run_loop('A', str(brief), str(repo), root=tmp_path) == 1
    assert 'A waits: main is broken' in capsys.readouterr().err and runtime.calls == []
