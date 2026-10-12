"""#908: repository, goal, parent item, scope and title carry through admission and briefing."""

import shlex

import pytest

from wuwei import dispatch, plan, state, workspace

REPOS = ('acme/app', 'beta/app', 'gamma/app')


@pytest.fixture
def day(tmp_path, monkeypatch):
    """Three repositories that share a short name and a file; two goals; A builds in beta/app."""
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text(''.join(
        f'[[repos]]\nname = "{name}"\npath = "{name.split("/")[0]}"\ndefault_branch = "main"\n' for name in REPOS))
    for name in REPOS:
        (tmp_path / name.split('/')[0] / 'cli').mkdir(parents=True)
        (tmp_path / name.split('/')[0] / 'cli/app.py').write_text('')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', '2026-10-12T10:00:00+02:00')
    flags = {key: False for key in plan.FLAGS}
    state._write_state(lambda data: data.update(
        gate_approved=True, goals=['G-1', 'G-2'], approved_items=['A'],
        items={'A': {'phase': 'implement', 'status': 'running', 'goal': 'G-2', 'repo': 'beta/app',
                     'track': 'SLICE', 'flags': flags}}), tmp_path)
    return tmp_path


def repos(root):
    return workspace.load_config(root)['repos']


def body(commands):
    return shlex.split(commands[-1])[-1]


def test_a_seat_finding_keeps_its_items_repository_and_goal(day, capsys):
    from wuwei.__main__ import main
    assert main(['seat', 'note', '--fix', 'Pin ruff in CI', '--item', 'A']) == 0
    ident = capsys.readouterr().out.strip()
    found = state.read_state(day)['seat_findings'][ident]
    assert (found['item'], found['repo'], found['goal']) == ('A', 'beta/app', 'G-2')
    assert main(['plan', 'add', ident, '--from-finding']) == 0
    row = state.read_state(day)['items'][ident]
    assert (row['goal'], row['repo'], row['parent'], row['title']) == ('G-2', 'beta/app', 'A', 'Pin ruff in CI')
    commands = dispatch._start(day, ident, repos(day))
    assert commands[0] == f'wuwei worktree add {ident} --repo beta/app'
    assert body(commands) == f'Implement {ident}: Pin ruff in CI. Evidence: seat finding in A.'


def test_a_seat_finding_in_an_approved_item_takes_the_repository_its_proposal_names(day, capsys):
    import json
    from wuwei.__main__ import main
    (workspace.day_dir(day) / 'proposal.json').write_text(json.dumps({'candidates': [{'id': 'P', 'repo': 'gamma/app'}]}))
    state._write_state(lambda data: data['items'].update(P={'phase': 'planned', 'goal': 'G-1'}), day)
    assert main(['seat', 'note', '--fix', 'Drop the dead flag', '--item', 'P']) == 0
    found = state.read_state(day)['seat_findings'][capsys.readouterr().out.strip()]
    assert (found['item'], found['repo'], found['goal']) == ('P', 'gamma/app', 'G-1')


def test_a_seat_note_names_an_item_of_today(day, capsys):
    from wuwei.__main__ import main
    assert main(['seat', 'note', '--fix', 'Pin ruff in CI', '--item', 'Z']) == 1
    assert 'no item Z today' in capsys.readouterr().err
    assert not state.read_state(day).get('seat_findings')


def test_a_finding_with_no_item_asks_for_its_goal_then_its_repository(day, capsys):
    from wuwei.__main__ import main
    assert main(['seat', 'note', '--fix', 'Pin ruff in CI']) == 0
    ident = capsys.readouterr().out.strip()
    with pytest.raises(state.StateError, match=f'run bin/wuwei plan add {ident} --from-finding --goal <one of G-1, G-2>'):
        plan.add(ident, day, source='finding')
    with pytest.raises(ValueError, match=f'run bin/wuwei plan add {ident} --from-finding --goal G-1 --repo <one of'):
        plan.add(ident, day, goal='G-1', source='finding')
    assert ident not in state.read_state(day)['items']
    assert main(['plan', 'add', ident, '--from-finding', '--goal', 'G-1', '--repo', 'gamma/app']) == 0
    row = state.read_state(day)['items'][ident]
    assert (row['goal'], row['repo'], 'parent' in row) == ('G-1', 'gamma/app', False)


def test_an_owner_item_admitted_by_title_keeps_it(day):
    plan.add('OWN-1', day, goal='G-1', title='Rotate the deploy key', repo='acme/app')
    assert state.read_state(day)['items']['OWN-1']['title'] == 'Rotate the deploy key'
    assert body(dispatch._start(day, 'OWN-1', repos(day))) == 'Implement OWN-1: Rotate the deploy key.'
    plan.add('OWN-2', day, goal='G-1', repo='acme/app')
    assert 'title' not in state.read_state(day)['items']['OWN-2']


def test_start_uses_the_recorded_worktree_outside_worktrees(day):
    elsewhere = day / 'checkouts/b'
    elsewhere.mkdir(parents=True)
    plan.add('B', day, goal='G-1', repo='gamma/app')
    state._write_state(lambda data: data['items']['B'].update(worktree=str(elsewhere)), day)
    commands = dispatch._start(day, 'B', repos(day))
    assert len(commands) == 1 and not (day / 'worktrees/B').exists()
    assert shlex.split(commands[0])[:7] == ['wuwei', 'seat', 'brief', 'builder', 'B', 'builder-B', '--worktree']
    assert shlex.split(commands[0])[7] == str(elsewhere)


def test_three_repositories_with_one_pr_number_and_one_file(day, monkeypatch):
    from fakes.code_host import Fake
    from wuwei import registry
    (day / '.wuwei/config.toml').write_text((day / '.wuwei/config.toml').read_text()
                                            + '[owner]\nhandles = ["Builder"]\n')
    host = Fake()
    load = registry.load
    monkeypatch.setattr(registry, 'load', lambda kind, config: host if kind == 'code_host' else load(kind, config))
    rows, _ = plan._owner_prs(workspace.load_config(day), day, [])
    assert [(row['id'], row['pr']) for row in rows] == [
        ('PR-acme_app-12', 'acme/app#12'), ('PR-beta_app-12', 'beta/app#12'), ('PR-gamma_app-12', 'gamma/app#12')]
    assert [plan.adopted_id(repos(day), name, 12) for name in REPOS] == [row['id'] for row in rows]
    assert plan.adopted_id(repos(day)[:1], 'acme/app', 12) == 'PR-12'
