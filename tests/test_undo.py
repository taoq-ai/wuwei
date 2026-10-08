"""#557: measured reversibility (design 5.8): the undo registry, the rehearsal ledger, the
measured door, wuwei undo and wuwei undo rehearse."""

import json

import pytest

from test_decision import SUPERVISED, save, events
from test_decision_classes import record, route, ws  # noqa: F401 (ws is a fixture)
from test_reasons import NEXT_STEP

APP = 'Context: repo:fixture-org/app merges the change.'
REPOS = '''[[repos]]
name = "fixture-org/app"
path = "app"
default_branch = "main"
{deploys}
[[repos]]
name = "fixture-org/lib"
path = "lib"
default_branch = "main"
merge_deploys = false
'''


@pytest.fixture(autouse=True)
def real_ledger(rehearsed_undo, monkeypatch):
    """This file tests the ledger itself: the real reader, not the conftest stand-in."""
    from wuwei import undo
    monkeypatch.setattr(undo, 'ledger', rehearsed_undo)


def repos(root, deploys=''):
    for name in ('app', 'lib'):
        (root / name).mkdir(exist_ok=True)
    (root / '.wuwei/config.toml').write_text(REPOS.format(deploys=deploys))


def merge_record(context=APP, door='two-way'):
    return record(cls='merge', door=door).replace('Context: tests/test_example.py records the failure.', context)


def fields_of(text):
    from wuwei import decision
    return decision.evaluate(text)[0]


def config_of(root):
    from wuwei import workspace
    return workspace.load_config(root)


# Phase 1: the registry and the ledger


def test_every_class_maps_to_a_kind_and_the_registry_is_closed():
    from wuwei import decision, undo
    assert set(undo.KIND) == set(decision.CLASSES) - {'other'}
    assert {name for name, kind in undo.KIND.items() if kind == 'commit'} == {
        'approach', 'retry', 'accept-residual', 'scope-cut', 'design', 'boundary', 'refactor',
        'dependency-bump'}
    assert {name for name, kind in undo.KIND.items() if kind == 'decision'} == {'park', 'defer', 're-plan'}
    assert (undo.KIND['merge'], undo.KIND['message']) == ('merge', 'message')
    assert set(undo.REGISTRY) == {'commit', 'decision', 'merge'} and 'message' not in undo.REGISTRY


def test_the_ledger_records_kinds_and_keeps_the_first(ws, monkeypatch):
    from wuwei import undo
    assert undo.ledger(ws) == {} and undo.missing(ws) == ['commit', 'decision', 'merge']
    undo.record(ws, 'commit', 'rehearsal')
    first = undo.ledger(ws)['commit']
    assert first['by'] == 'rehearsal' and first['at'].startswith('2026-09-28T12:00')
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T13:00:00+00:00')
    undo.record(ws, 'commit', 'undo')
    assert undo.ledger(ws)['commit'] == first
    assert undo.missing(ws) == ['decision', 'merge']


@pytest.mark.parametrize('text', ['{', '[]', '{"kinds": {"message": {"at": "x", "by": "undo"}}}',
                                  '{"kinds": {"commit": {"at": "x", "by": "seat"}}}',
                                  '{"kinds": {"commit": []}}', '{"other": {}}'])
def test_a_damaged_ledger_raises_and_counts_as_nothing(ws, text):
    from wuwei import undo
    path = ws / '.wuwei' / undo.NAME
    path.parent.mkdir(parents=True)
    path.write_text(text)
    with pytest.raises(ValueError) as caught:
        undo.ledger(ws)
    assert 'memory/rehearsals.json' in str(caught.value) and 'wuwei undo rehearse' in str(caught.value)
    assert undo.missing(ws) == ['commit', 'decision', 'merge']


def test_a_symlinked_ledger_is_damaged(ws, tmp_path):
    from wuwei import undo
    other = tmp_path / 'other.json'
    other.write_text('{"kinds": {}}')
    path = ws / '.wuwei' / undo.NAME
    path.parent.mkdir(parents=True)
    path.symlink_to(other)
    with pytest.raises(ValueError):
        undo.ledger(ws)


@pytest.mark.parametrize('kind', ['undo.done', 'undo.rehearsed'])
def test_undo_events_are_reserved(ws, kind, capsys):
    from wuwei.__main__ import main
    assert main(['event', kind, '{}']) == 1
    assert 'reserved' in capsys.readouterr().err


# Phase 2: the measured door


def rehearse_all(root, kinds=('commit', 'decision', 'merge')):
    from wuwei import undo
    for kind in kinds:
        undo.record(root, kind, 'rehearsal')


@pytest.mark.parametrize('cls', ['retry', 'design', 'park', 'defer'])
def test_a_rehearsed_kind_keeps_its_door(ws, cls):
    from wuwei import undo
    rehearse_all(ws)
    assert undo.measured(fields_of(record(cls=cls)), ws, config_of(ws))[1] is None


def test_the_reasons_of_the_measured_door(ws):
    from wuwei import undo
    measured = lambda text: undo.measured(fields_of(text), ws, config_of(ws))  # noqa: E731
    assert measured(record(cls='retry')) == (
        'commit', 'the commit undo was never rehearsed in this workspace; run wuwei undo rehearse commit')
    rehearse_all(ws)
    assert measured(record(cls='message')) == (
        'message', 'a message has no undo (4.9); ask the owner: wuwei decision route sends the card')
    assert measured(record(cls='other')) == (
        None, 'other has no registered undo; ask the owner: wuwei decision route sends the card')
    from test_decision import LEGACY
    assert measured(LEGACY)[1] == 'no class has no registered undo; ask the owner: wuwei decision route sends the card'


def test_the_merge_door(ws):
    from wuwei import undo
    rehearse_all(ws)
    repos(ws)
    measured = lambda text: undo.measured(fields_of(text), ws, config_of(ws))[1]  # noqa: E731
    assert measured(merge_record('Context: the change.')) == (
        'a merge record names no repository; add repo:<org>/<name> to Context')
    deploys = ('a merge to repo:fixture-org/app deploys (merge_deploys is not false, 4.6); '
               'ask the owner: wuwei decision route sends the card')
    assert measured(merge_record()) == deploys
    assert measured(merge_record('Context: repo:fixture-org/app and repo:fixture-org/lib.')) == deploys
    assert 'repo:fixture-org/none deploys' in measured(merge_record('Context: repo:fixture-org/none.'))
    assert measured(merge_record('Context: repo:fixture-org/lib.')) is None
    repos(ws, 'merge_deploys = false')
    assert measured(merge_record('Context: repo:fixture-org/app and repo:fixture-org/lib.')) is None
    (ws / '.wuwei' / undo.NAME).write_text(json.dumps({'kinds': {}}))
    assert measured(merge_record()) == (
        'the merge undo was never rehearsed in this workspace; run wuwei undo rehearse merge; '
        'it counts after the first wuwei undo of a merge here')


def test_a_damaged_ledger_lowers_the_door_with_the_fix(ws):
    from wuwei import undo
    path = ws / '.wuwei' / undo.NAME
    path.parent.mkdir(parents=True)
    path.write_text('{')
    reason = undo.measured(fields_of(record(cls='retry')), ws, config_of(ws))[1]
    assert reason.startswith('memory/rehearsals.json is damaged') and NEXT_STEP.search(reason)


def lint(root, text, capsys, name='D-3.md'):
    from wuwei.__main__ import main
    path = save(root, text, name)
    code = main(['decision', 'lint', str(path)])
    out = capsys.readouterr()
    assert path.read_text() == text
    return code, (out.out + out.err).strip().splitlines()


@pytest.mark.parametrize('posture', ['observe', 'guarded', 'strict'])
def test_the_lint_reports_the_correction_and_keeps_its_exit(ws, capsys, posture):
    repos(ws)
    with (ws / '.wuwei/config.toml').open('a') as config:
        config.write(f'[security]\nposture = "{posture}"\n')
    code, lines = lint(ws, merge_record(), capsys)
    assert code == 0 and lines[0].startswith('OK: A') and lines[1] == (
        'Reversibility: one-way, not two-way: a merge to repo:fixture-org/app deploys '
        '(merge_deploys is not false, 4.6); ask the owner: wuwei decision route sends the card')
    code, lines = lint(ws, record(cls='retry'), capsys)
    assert code == 0 and lines[1].endswith('run wuwei undo rehearse commit')
    code, lines = lint(ws, record(cls='message'), capsys)
    assert code == 0 and 'a message has no undo (4.9)' in lines[1]
    code, lines = lint(ws, record(cls='retry', door='one-way'), capsys)
    assert code == 0 and len(lines) == 1


# Phase 3: the routing point writes it


def routes(root):
    from wuwei import state
    return state.read_state(root).get('decision_routes', {})


def outcomes(root):
    from wuwei import state
    return state.read_state(root).get('decision_outcomes', {})


def test_a_deploying_merge_record_is_corrected_on_its_first_route(ws, capsys):
    repos(ws)
    path = save(ws, merge_record())
    code, out = route(ws, capsys)
    lines = out.splitlines()
    assert code == 0 and lines[0] == 'owner' and lines[-1].startswith(
        'Reversibility: one-way, not two-way: a merge to repo:fixture-org/app deploys')
    text = path.read_text()
    assert 'Reversibility: one-way' in text and 'Reversibility: two-way' not in text
    assert text.count('Notes: Reversibility corrected at 2026-09-28T12:00:00+00:00: a merge to') == 1
    assert routes(ws)['D-3']['reversibility'] == 'one-way' and 'D-3' not in outcomes(ws)
    before = text
    assert route(ws, capsys) == (0, 'owner') and path.read_text() == before


def test_an_unrehearsed_commit_goes_to_the_owner_until_it_ran(ws, capsys):
    from wuwei import undo
    save(ws, record(cls='retry'))
    code, out = route(ws, capsys)
    assert code == 0 and out.splitlines() == [
        'owner', 'Reversibility: one-way, not two-way: the commit undo was never rehearsed in '
        'this workspace; run wuwei undo rehearse commit']
    undo.record(ws, 'commit', 'rehearsal')
    save(ws, record(cls='retry'), name='D-4.md')
    assert route(ws, capsys, 'D-4') == (0, 'mandate')
    assert route(ws, capsys) == (0, 'owner') and 'D-3' not in outcomes(ws)


def test_an_unsure_park_record_is_corrected(ws, capsys):
    from wuwei import undo
    undo.record(ws, 'commit', 'rehearsal')
    path = save(ws, record(cls='park', door='unsure'))
    code, out = route(ws, capsys)
    assert code == 0 and out.splitlines()[0] == 'owner'
    assert 'not unsure: the decision undo was never rehearsed' in out
    assert 'Reversibility: one-way' in path.read_text()


def test_a_record_taken_before_the_ledger_is_never_rewritten(ws, capsys, monkeypatch):
    from wuwei import undo
    real = undo.ledger
    monkeypatch.setattr(undo, 'ledger', lambda root: {'commit': {'at': 'x', 'by': 'rehearsal'}})
    path = save(ws, record(cls='retry'))
    assert route(ws, capsys) == (0, 'mandate')
    taken = path.read_text()
    monkeypatch.setattr(undo, 'ledger', real)
    assert route(ws, capsys) == (0, 'mandate') and path.read_text() == taken


def test_a_rehearsed_commit_routes_as_today(ws, capsys):
    from wuwei import undo
    undo.record(ws, 'commit', 'rehearsal')
    code, lines = lint(ws, record(cls='retry'), capsys)
    assert code == 0 and len(lines) == 1
    assert route(ws, capsys) == (0, 'mandate')
    (ws / '.wuwei/config.toml').write_text(SUPERVISED)
    path = save(ws, record(cls='retry'), name='D-4.md')
    assert route(ws, capsys, 'D-4') == (0, 'seat')
    assert path.read_text() == record(cls='retry')


def test_an_external_route_is_corrected_first(ws, capsys):
    from wuwei import state
    from wuwei.__main__ import main
    state._write_state(lambda data: data['items'].update(alpha={
        'goal': 'G-1', 'flags': {'trust_surface': False, 'boundary_relevant': False,
                                 'agent_surface': False}}), ws, reserved=False)
    path = save(ws, record(cls='retry'))
    assert main(['decision', 'route', 'D-3', '--external', 'alpha']) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0] == 'owner' and out[1].endswith('run wuwei undo rehearse commit')
    assert 'Reversibility: one-way' in path.read_text()
    assert routes(ws)['D-3']['reversibility'] == 'one-way'


# Phase 4: undo and rehearse


@pytest.fixture
def cruised(ws, capsys):
    """A park record taken as a cruise answer at L2 under the defaults, undo until 13:00."""
    from wuwei import state, undo
    undo.record(ws, 'decision', 'rehearsal')
    path = save(ws, record(cls='park'))
    assert route(ws, capsys) == (0, 'mandate')
    (ws / '.wuwei' / undo.NAME).unlink()  # an empty ledger again, so the undo's own row shows
    assert state.read_state(ws)['decision_outcomes']['D-3']['undo_until']
    return path


def undo_cli(*args):
    from wuwei.__main__ import main
    return main(['undo', *args])


def test_wuwei_undo_reverts_a_cruise_answer_and_records_the_exercise(ws, cruised, capsys, monkeypatch):
    from wuwei import sessions, state, undo
    monkeypatch.setattr(sessions, 'gate_topics',
                        lambda root, session: (frozenset({sessions.card_topic('D-3', 'Undo')}), True))
    assert undo_cli('D-3', '--answer', 'Undo') == 0
    assert capsys.readouterr().out.strip() == 'owner: ask with wuwei decision show D-3 --widget'
    reversed_, = [e['payload'] for e in events(ws) if e['kind'] == 'decision.reversed']
    assert reversed_['undo'] is True and 'D-3' not in state.read_state(ws)['decision_outcomes']
    text = cruised.read_text()
    assert 'Decided-by: owner' in text and 'Outcome: pending' in text
    assert undo.ledger(ws)['decision']['by'] == 'undo'


def test_the_dm_undo_records_the_exercise_too(ws, cruised):
    from types import SimpleNamespace
    from wuwei import undo
    from wuwei.commands.decision import undo as decision_undo
    assert decision_undo(SimpleNamespace(id='D-3', answer='Undo'), root=ws, where='in the DM')[0] == 0
    assert undo.ledger(ws)['decision']['by'] == 'undo'


def nothing_written(root, before):
    from wuwei import undo
    assert len(events(root)) == before and undo.ledger(root) == {}


def test_a_seat_closed_or_missing_window_writes_nothing(ws, cruised, capsys, monkeypatch):
    def no_terminal(value, **kwargs):
        raise OSError('no terminal')
    monkeypatch.setattr('wuwei.integrity._host_confirm', no_terminal)
    before = len(events(ws))
    assert undo_cli('D-3') == 1
    assert capsys.readouterr().err.strip() == 'run wuwei undo D-3 in a host terminal and answer y'
    nothing_written(ws, before)
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T13:00:00+00:00')
    assert undo_cli('D-3') == 1 and 'undo window closed' in capsys.readouterr().err
    save(ws, record(cls='retry', radius='item DIV-1'), name='D-4.md')
    from wuwei import undo
    real, undo.ledger = undo.ledger, lambda root: {'commit': {'at': 'x', 'by': 'rehearsal'}}
    try:
        route(ws, capsys, 'D-4')
    finally:
        undo.ledger = real
    before = len(events(ws))
    assert undo_cli('D-4') == 1 and 'has no undo window' in capsys.readouterr().err
    nothing_written(ws, before)


from test_merge import REF, case, merged  # noqa: E402,F401 (case is a fixture)


def merge_event(root):
    from wuwei import merge, watch, workspace
    assert merge.poll(root) == 0
    day = workspace.day_dir(root)
    number = next(n for n, row in enumerate(watch.records(day / 'events.jsonl'), 1)
                  if row['kind'] == 'merge.completed')
    return f'{day.name}:{number}'


def test_wuwei_undo_of_a_merge_event_opens_the_revert_pr(case, capsys, monkeypatch):
    from wuwei import dispatch, state, undo, workspace
    root, host = merged(case)
    monkeypatch.setattr(dispatch, 'tracker_call', lambda *args: None)
    target = merge_event(root)
    monkeypatch.setattr('wuwei.integrity._host_confirm', lambda value, **kwargs: False)
    before = len(events(root))
    assert undo_cli(target) == 1 and 'declined' in capsys.readouterr().err
    nothing_written(root, before)

    def no_terminal(value, **kwargs):
        raise OSError('no terminal')
    monkeypatch.setattr('wuwei.integrity._host_confirm', no_terminal)
    assert undo_cli(target) == 1
    assert capsys.readouterr().err.strip() == f'run wuwei undo {target} in a host terminal and answer y'
    nothing_written(root, before)
    monkeypatch.setattr('wuwei.integrity._host_confirm', lambda value, **kwargs: True)
    assert undo_cli(target) == 0
    url = 'https://github.com/example/project/pull/8'
    assert url in capsys.readouterr().out
    assert ('revert_pr', (REF,), root) in host.calls
    assert state.read_state(root)['merges'][REF]['revert_pr'] == url
    done, = [e['payload'] for e in events(root) if e['kind'] == 'undo.done']
    assert done == {'target': target, 'kind': 'merge', 'pr': REF, 'revert_pr': url}
    assert undo.ledger(root)['merge']['by'] == 'undo'
    day = workspace.day_dir(root).name
    assert undo_cli(f'{day}:1') == 1
    assert 'has no registered undo, so it cannot be undone here; run wuwei why' in capsys.readouterr().err
    assert undo_cli(f'{day}:9999') == 1


def test_rehearse_commit_on_a_scratch_repository(ws, capsys, tmp_path, monkeypatch):
    from wuwei import undo
    import tempfile
    seen = []
    real = tempfile.TemporaryDirectory

    def tracked(*args, **kwargs):
        made = real(*args, **kwargs)
        seen.append(made.name)
        return made
    monkeypatch.setattr(tempfile, 'TemporaryDirectory', tracked)
    assert undo_cli('rehearse', 'commit') == 0
    assert capsys.readouterr().out.strip() == 'rehearsed commit'
    rehearsed, = [e['payload'] for e in events(ws) if e['kind'] == 'undo.rehearsed']
    assert rehearsed == {'kind': 'commit'} and undo.ledger(ws)['commit']['by'] == 'rehearsal'
    from pathlib import Path
    assert seen and not any(Path(name).exists() for name in seen)


def test_a_failed_commit_rehearsal_writes_nothing(ws, capsys, monkeypatch):
    from wuwei import registry, undo
    from wuwei.registry import Result
    adapter = type('Vcs', (), {'rehearse_revert': staticmethod(
        lambda path, root=None: Result(2, None, 'git.rehearse_revert: could not run: git missing'))})
    monkeypatch.setattr(registry, 'load', lambda kind, config: adapter)
    assert undo_cli('rehearse', 'commit') == 2
    err = capsys.readouterr().err
    assert 'git missing' in err and NEXT_STEP.search(err)
    assert undo.ledger(ws) == {} and not (ws / '.wuwei/days').exists()


def test_rehearse_decision_on_a_scratch_workspace(ws, capsys, monkeypatch):
    import os
    from wuwei import state, undo, workspace
    monkeypatch.setenv('WUWEI_WORKSPACE', str(ws))
    assert undo_cli('rehearse', 'decision') == 0
    assert capsys.readouterr().out.strip() == 'rehearsed decision'
    assert os.environ['WUWEI_WORKSPACE'] == str(ws)
    assert undo.ledger(ws)['decision']['by'] == 'rehearsal'
    assert [e['payload'] for e in events(ws)] == [{'kind': 'decision'}]
    data = state.read_state(ws)
    assert not data.get('decision_routes') and not data.get('decision_outcomes')
    assert not (workspace.day_dir(ws) / 'decisions').exists()
    assert not (ws / '.wuwei/memory/cruise.json').exists()


def test_rehearse_decision_restores_an_unset_workspace(ws, capsys):
    import os
    assert undo_cli('rehearse', 'decision') == 0 and 'WUWEI_WORKSPACE' not in os.environ


def test_a_failed_decision_rehearsal_writes_nothing(ws, capsys, monkeypatch):
    from wuwei import undo
    monkeypatch.setattr('wuwei.commands.decision.undo', lambda args, **kwargs: (1, 'no'))
    assert undo_cli('rehearse', 'decision') == 2
    assert NEXT_STEP.search(capsys.readouterr().err)
    assert undo.ledger(ws) == {} and not (ws / '.wuwei/days').exists()


@pytest.mark.parametrize('kind,expected', [
    ('merge', 'merge: its undo is a revert PR on the code host, which has no scratch target; '
              'it counts after the first wuwei undo <event id> of a merge here'),
    ('message', 'message has no scratch rehearsal; run wuwei undo rehearse commit or wuwei undo rehearse decision'),
    ('nonsense', 'nonsense has no scratch rehearsal; run wuwei undo rehearse commit or wuwei undo rehearse decision'),
])
def test_kinds_without_a_scratch_rehearsal(ws, capsys, kind, expected):
    assert undo_cli('rehearse', kind) == 1
    assert capsys.readouterr().err.strip() == expected


# Phase 5: upgrade and doctor


@pytest.mark.parametrize('dry_run', [False, True])
def test_init_upgrade_lists_the_unrehearsed_kinds(tmp_path, monkeypatch, capsys, dry_run):
    from test_guide import initialised, upgrade
    project = initialised(tmp_path, monkeypatch)
    capsys.readouterr()
    upgrade(project, dry_run)
    out = capsys.readouterr().out
    assert ('Undo not rehearsed: commit, decision, merge; run wuwei undo rehearse <kind> '
            '(a merge counts after its first wuwei undo)') in out
    assert 'No workspace changes needed' in out


# Invariants (design 5.8 Measured reversibility; tests/test_invariants.py is not on this base)

LEDGERS = ((), ('commit',), ('commit', 'decision'), ('commit', 'decision', 'merge'))


@pytest.mark.parametrize('kinds', LEDGERS)
@pytest.mark.parametrize('deploys', [True, False])
@pytest.mark.parametrize('mode', ['autonomous', 'supervised'])
def test_invariant_a_two_way_only_with_a_registered_rehearsed_undo(ws, capsys, kinds, deploys, mode):
    from wuwei import decision, state, undo
    repos(ws, '' if deploys else 'merge_deploys = false')
    with (ws / '.wuwei/config.toml').open('a') as config:
        config.write(f'[autonomy]\nmode = "{mode}"\n')
    rehearse_all(ws, kinds)
    number = 0
    for cls in decision.CLASSES:
        for door in ('one-way', 'two-way', 'unsure'):
            number += 1
            path = save(ws, merge_record(door=door).replace('Class: merge', f'Class: {cls}'), name=f'D-{number}.md')
            assert route(ws, capsys, f'D-{number}')[0] == 0
            data = state.read_state(ws)
            row = data.get('decision_outcomes', {}).get(f'D-{number}') or data['decision_routes'][f'D-{number}']
            written = fields_of(path.read_text())['Reversibility']
            kind = undo.KIND.get(cls)
            backed = kind in undo.REGISTRY and kind in kinds and not (kind == 'merge' and deploys)
            assert row['reversibility'] == written
            assert written == ('one-way' if not backed else door), (cls, door, kinds, deploys, mode)


@pytest.mark.parametrize('door', ['two-way', 'unsure'])
def test_invariant_b_a_message_is_never_two_way(ws, capsys, door):
    from types import SimpleNamespace
    from wuwei.commands.decision import owner_outcome
    rehearse_all(ws)
    path = save(ws, record(cls='message', door=door))
    assert route(ws, capsys)[1].splitlines()[0] == 'owner'
    assert 'Reversibility: one-way' in path.read_text()
    code, message = owner_outcome(SimpleNamespace(id='D-3', option='A'), root=ws, where='in the DM')
    assert code == 1 and 'only a two-way decision is decided from the DM' in message


def test_invariant_c_undo_needs_a_card_a_dm_or_a_terminal(ws, cruised, capsys, monkeypatch):
    # The event branch is pinned in test_wuwei_undo_of_a_merge_event_opens_the_revert_pr.
    from wuwei import workspace

    def no_terminal(value, **kwargs):
        raise OSError('no terminal')
    monkeypatch.setattr('wuwei.integrity._host_confirm', no_terminal)
    day = workspace.day_dir(ws)
    before = {path: path.read_bytes() for path in day.rglob('*') if path.is_file()}
    assert undo_cli('D-3', '--answer', 'Undo') == 1
    assert {path: path.read_bytes() for path in day.rglob('*') if path.is_file()} == before
    assert not (ws / '.wuwei' / 'memory/rehearsals.json').exists()


@pytest.mark.parametrize('posture', ['observe', 'guarded', 'strict'])
def test_invariant_d_the_correction_never_changes_a_lint_exit(ws, capsys, posture):
    (ws / '.wuwei/config.toml').write_text(f'[security]\nposture = "{posture}"\n')
    corrected = lint(ws, record(cls='retry'), capsys)
    rehearse_all(ws)
    clean = lint(ws, record(cls='retry'), capsys)
    assert corrected[0] == clean[0] == 0 and len(corrected[1]) == 2 and len(clean[1]) == 1
