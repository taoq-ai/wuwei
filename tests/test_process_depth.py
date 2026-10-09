"""#567: process depth follows the tier."""

import json

import pytest

from wuwei import state, workspace
from test_dispatch import root, tiered  # noqa: F401  (fixture and helper)


def test_depth_reads_the_gate_tier_then_the_builder_prediction():
    from wuwei.dispatch import depth

    assert depth({}) == depth({'gates': {}}) == 'standard'
    assert depth({'depth': 'light'}) == 'light'
    assert depth({'depth': 'light'}, gate=True) == 'standard'  # a prediction never lightens a gate
    assert depth({'depth': 'light', 'gates': {'tier': 'full'}}) == 'full'
    assert depth({'depth': 'standard', 'gates': {'tier': 'light'}}, gate=True) == 'light'


def classes_of(root):
    from wuwei import dispatch
    return dispatch.classes(root, workspace.load_config(root), state.read_state(root)['items']['A'])


def test_classes_follow_the_tier(root, monkeypatch):
    tiered(root, monkeypatch, [('docs/guide.md', 3, 1)])
    record, found = classes_of(root)
    assert record['tier'] == 'light' and found == {}

    tiered(root, monkeypatch, [('cli/wuwei/guards/x.py', 3, 1)])
    record, found = classes_of(root)
    assert record['tier'] == 'standard'
    assert found == {'AUTH': ['cli/wuwei/guards/x.py'], 'ERR': ['cli/wuwei/guards/x.py']}

    tiered(root, monkeypatch, [('cli/wuwei/report.py', 3, 1)], track='FULL')
    from wuwei.dispatch import CLASS_PATHS
    record, found = classes_of(root)
    assert record['tier'] == 'full' and list(found) == [name for name, _ in CLASS_PATHS]


def test_classes_refuse_an_unread_diff(root, monkeypatch):
    from wuwei.registry import Result

    fake = tiered(root, monkeypatch, [])
    fake.results['diff_stat'] = Result(2, None, 'git failed')
    with pytest.raises(ValueError, match='git failed'):
        classes_of(root)


def test_sweep_classes_command(root, monkeypatch, capsys):
    from wuwei.__main__ import main

    monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
    tiered(root, monkeypatch, [('docs/guide.md', 3, 1)])
    assert main(['sweep', 'classes', 'repo']) == 0
    assert capsys.readouterr().out == 'Depth: light; no class sweep\n'
    tiered(root, monkeypatch, [('cli/wuwei/guards/x.py', 3, 1)])
    assert main(['sweep', 'classes', str(root / 'repo')]) == 0
    assert capsys.readouterr().out == ('Depth: standard\nAUTH: cli/wuwei/guards/x.py\n'
                                       'ERR: cli/wuwei/guards/x.py\n')
    assert main(['sweep', 'classes', 'elsewhere']) == 2
    assert 'no item has the worktree' in capsys.readouterr().err


def test_sweep_classes_is_read_only():
    from wuwei.commands import read_only
    assert read_only(['sweep', 'classes', 'worktrees/A'])


from test_brief import brief, day  # noqa: E402,F401  (helper and fixture)


def depth_day(day, diff, floor='light', trust=None, gates=None):
    from wuwei import registry
    root, directory, vcs, _ = day
    (root / 'tree').mkdir(exist_ok=True)
    trust_line = f'trust_paths = {trust!r}\n'.replace("'", '"') if trust else ''
    (root / '.wuwei/config.toml').write_text(
        '[[repos]]\nname = "acme/widget"\npath = "tree"\ndefault_branch = "main"\n'
        f'[repos.gates]\nfloor = "{floor}"\n' + trust_line)
    vcs.results.update(
        repo_context=registry.Result(0, {'path': str(root / 'tree'), 'common_dir': str(root / 'tree/.git')}),
        diff_stat=registry.Result(0, [{'path': p, 'additions': 3, 'deletions': 1} for p in diff]))
    if gates:
        state._write_state(lambda data: data['items']['X'].update(gates={'tier': gates}), root, reserved=False)
    return root, directory


def depth_line(directory, name):
    header = (directory / f'briefs/{name}.md').read_text().split('\n\n', 1)[0]
    return [line for line in header.splitlines() if line.startswith('Depth:')]


def test_builder_brief_names_its_depth(day, monkeypatch):
    root, directory = depth_day(day, ['docs/guide.md'])
    assert brief(monkeypatch, 'body', 'builder', 'X', 'b-light', '--worktree', 'tree') == 0
    [line] = depth_line(directory, 'b-light')
    assert line.startswith('Depth: light; skip: the class sweep')
    assert f'wuwei sweep classes {root / "tree"}' in line and 'retro note' in line
    assert state.read_state(root)['items']['X']['depth'] == 'light'
    depth_day(day, ['cli/wuwei/report.py'], floor='standard')
    assert brief(monkeypatch, 'body', 'builder', 'X', 'b-std', '--worktree', 'tree') == 0
    [line] = depth_line(directory, 'b-std')
    assert line == (f'Depth: standard; before handoff run wuwei sweep classes {root / "tree"} '
                    'and report one CLASS line per class it lists')
    assert state.read_state(root)['items']['X']['depth'] == 'standard'


def test_depth_is_written_only_by_the_brief(day):
    with pytest.raises(state.StateError, match='wuwei brief'):
        state.set_state('items.X.depth', 'light', day[0])


@pytest.mark.parametrize('diff,tier,trust,expected', [
    (['cli/wuwei/guards/x.py'], 'standard', None,
     'Depth: standard; step zero: run (cli/wuwei/guards/x.py matches guards/*)'),
    (['cli/wuwei/report.py'], 'standard', None,
     'Depth: standard; step zero: skip (no guard code or trust path in the diff); '
     'write Mutation: skipped (depth standard)'),
    (['billing/pay.py'], 'standard', ['billing/*'],
     'Depth: standard; step zero: run (billing/pay.py matches billing/*)'),
    (['cli/wuwei/report.py'], 'full', None, 'Depth: full; step zero: run'),
    (['docs/guide.md'], 'light', None,
     'Depth: light; skip: gate step zero, the Probe or Mutation row, the class-sweep line, '
     'the Simplicity and Design rows, the retro note when every line would be none; '
     'verdict: Verdict:, Head:, findings'),
])
def test_gate_brief_says_when_step_zero_runs(day, monkeypatch, diff, tier, trust, expected):
    _, directory = depth_day(day, diff, trust=trust, gates=tier)
    assert brief(monkeypatch, 'Review it.', 'quality', 'X', 'g', '--gate', '--worktree', 'tree') == 0
    assert depth_line(directory, 'g') == [expected]


def test_gate_brief_ignores_the_builder_prediction(day, monkeypatch):
    root, directory = depth_day(day, ['cli/wuwei/report.py'])
    state._write_state(lambda data: data['items']['X'].update(depth='light'), root, reserved=False)
    assert brief(monkeypatch, 'Review it.', 'quality', 'X', 'g', '--gate', '--worktree', 'tree') == 0
    assert depth_line(directory, 'g')[0].startswith('Depth: standard; step zero: skip')


def test_launch_prompt_repeats_the_depth_line(day, monkeypatch):
    from wuwei import brief as briefs
    root, directory = depth_day(day, ['docs/guide.md'])
    assert brief(monkeypatch, 'body', 'builder', 'X', 'b-light', '--worktree', 'tree') == 0
    prompt = briefs.launch_prompt(directory / 'briefs/b-light.md', 'charter.md', root=root)
    assert prompt.endswith('\n' + depth_line(directory, 'b-light')[0])
    assert prompt.split('\n\n', 1)[1].startswith('Mandate (design 5.2):')
    plain = directory / 'briefs/plain.md'
    plain.write_text('Item: X\n\nbody\nDepth: not a header line\n')
    assert briefs.launch_prompt(plain, 'charter.md', root=root).endswith('Nothing else is a question.')


THREE = 'Verdict: PASS\nHead: abc1234\nFindings: none\n'
LIGHT_FIX = 'Verdict: FIX\nHead: abc1234\n- P1 | cli/example.py:12 | fails when empty | blocks: yes\n'


@pytest.mark.parametrize('text', [THREE, LIGHT_FIX])
@pytest.mark.parametrize('quality', [True, False])
def test_light_lint_accepts_three_rows(text, quality):
    from wuwei import verdict
    assert verdict.lint(text, quality=quality, class_sweep=True, light=True)[0] == 0
    assert verdict.lint(text, quality=quality, class_sweep=True)[0] == 1


@pytest.mark.parametrize('text,reason', [
    ('Verdict: FIX\nHead: abc1234\n', 'no finding with severity'),
    ('Verdict: FIX\nHead: abc1234\n- P1 | fails when empty | blocks: yes\n', 'file:line'),
    (THREE + 'Verdict: FIX\n', 'exactly one Verdict'),
    ('Verdict: PASS\nFindings: none\n', 'Head:'),
    ('Verdict: PASS\nHead: abc1234\n- P1 | cli/example.py:12 | fails when empty | blocks: yes\n',
     'PASS verdict carries a blocking finding'),
    (THREE + 'Blocked: none\n', "retro note missing 'Gap:' line"),
])
def test_light_lint_keeps_every_other_check(text, reason):
    from wuwei import verdict
    code, message = verdict.lint(text, quality=True, class_sweep=True, light=True)
    assert code == 1 and reason in message


def gate_file(root, tier=None, depth=None, seat='quality-1'):
    directory = workspace.day_dir(root)
    (directory / 'decisions').mkdir(exist_ok=True)
    path = directory / 'decisions' / f'gate-{seat}.md'
    path.write_text(THREE)

    def update(data):
        data['seats']['quality-1'] = {'item': 'A', 'role': 'sentinel-quality', 'status': 'stopped'}
        if tier:
            data['items']['A']['gates'] = {'tier': tier}
        if depth:
            data['items']['A']['depth'] = depth
    state._write_state(update, root, reserved=False)
    return path


@pytest.mark.parametrize('tier,depth,seat,code', [
    ('light', None, 'quality-1', 0),
    ('standard', None, 'quality-1', 1),
    (None, 'light', 'quality-1', 1),  # a builder prediction never lightens a gate
    ('light', None, 'unknown-1', 1),
])
def test_lint_file_reads_the_gate_tier(root, tier, depth, seat, code):
    from wuwei import verdict
    path = gate_file(root, tier, depth, seat)
    assert verdict.lint_file(path, role='sentinel-quality', root=root)[0] == code


def test_lint_file_outside_a_workspace_is_standard(tmp_path):
    from wuwei import verdict
    (tmp_path / 'decisions').mkdir()
    path = tmp_path / 'decisions/gate-quality-1.md'
    path.write_text(THREE)
    assert verdict.lint_file(path, role='sentinel-quality')[0] == 1


SHA = 'a' * 40


@pytest.mark.parametrize('tier,code', [('light', 0), ('standard', 1)])
def test_pr_gate_check_accepts_recorded_light_verdicts(tmp_path, tier, code):
    from wuwei.guards import pr
    directory = workspace.day_dir(tmp_path) / 'decisions'
    directory.mkdir(parents=True)
    (directory / 'gate-9-quality.md').write_text(THREE.replace('abc1234', SHA))
    items = {'9': {'gates': {'tier': tier, 'roles': ['quality']}}}
    records = {'9:quality:initial': {'item': '9', 'role': 'quality', 'round': 'initial', 'verdict': 'PASS',
                                     'head': SHA, 'blocks': False, 'notes': [],
                                     'file': str((directory / 'gate-9-quality.md').relative_to(tmp_path))}}
    if code:
        with pytest.raises(ValueError, match='quality verdict'):
            pr._recorded_gates(tmp_path, SHA, records, '9', items)
    else:
        assert pr._recorded_gates(tmp_path, SHA, records, '9', items) == (0, '')


def test_obligation_verdict_is_met_by_a_light_verdict(root):
    from wuwei import obligations
    path = gate_file(root, 'light')
    path.write_text(THREE.replace('abc1234', SHA))
    data = state.read_state(root)
    assert obligations._gate_recorded(path.parent.parent, SHA, data)
    data['items']['A']['gates'] = {'tier': 'standard'}
    assert not obligations._gate_recorded(path.parent.parent, SHA, data)


from test_retro import events as retro_events, seat  # noqa: E402,F401  (helper and fixture)


@pytest.mark.parametrize('tier,text,kind,code', [
    ('light', 'Verdict: PASS', 'retro.captured', 0),
    ('standard', 'Verdict: PASS', 'retro.gap', 1),
    ('light', 'Blocked: none', 'retro.gap', 1),
])
def test_light_seat_without_a_retro_note_records_none(seat, tier, text, kind, code):
    from pathlib import Path
    from wuwei.guards.verdict import check_retro
    root = Path(seat['cwd'])
    state._write_state(lambda data: data.update(
        items={'A': {'phase': 'planned', 'gates': {'tier': tier}}},
        seats={'quality-1': {'item': 'A', 'role': 'sentinel-quality', 'status': 'running',
                             'agent_id': 'seat-one'}}), root, reserved=False)
    seat.update(agent_type='wuwei:sentinel-quality', last_assistant_message=text)
    assert check_retro(seat)[0] == code
    event = retro_events(seat)[-1]
    assert event['kind'] == kind
    if kind == 'retro.captured':
        assert event['payload']['fields'] == {'Blocked': 'none', 'Gap': 'none', 'Change': 'none'}


@pytest.mark.parametrize('light', [True, False])
def test_light_fix_is_re_read_by_the_same_seat(root, light):
    from test_dispatch import FIX, built, gate_fix, record
    from wuwei import dispatch

    built(root)
    if light:
        state._write_state(lambda data: data['items']['A'].update(
            gates={'tier': 'light', 'computed': 'light', 'reasons': [], 'roles': ['quality']}),
            root, reserved=False)
        record(root, 'quality', 'quality-1', FIX + 'Simplicity: none\nDesign: none\n')
    else:
        gate_fix(root)
    state._write_state(lambda data: data['seats']['quality-1'].update(
        agent_id='agent-quality-1', head='abc1234' + '0' * 33), root, reserved=False)
    dispatch.next_step('A', root)
    state.transition('A', 'delta', root)
    [action] = dispatch.next_step('A', root)['seats']
    assert action['action'] == 'continue' and action['resume'] == 'agent-quality-1'
    assert action['receive'] == 'wuwei dispatch receive A quality quality-1 --round delta'
    feedback = action['feedback']
    if light:
        assert feedback.startswith('Re-read:') and 'Delta review' not in feedback
        assert 'Verdict:' in feedback and 'Head:' in feedback and 'blocks: no' in feedback
        assert 'did not change' not in feedback
    else:
        assert feedback.startswith('Delta review:')
        # #623: no scope widening after round one
        assert 'did not change is blocks: no, unless it is a trust-boundary security finding' in feedback


from test_decision_classes import record as decision_record, route, ws  # noqa: E402,F401
from test_decision import save  # noqa: E402


def show(capsys, *args):
    from wuwei.__main__ import main
    code = main(['decision', 'show', 'D-3', *args])
    return code, capsys.readouterr().out


def test_routine_mandate_record_shows_one_line(ws, capsys):
    from wuwei import decision
    path = save(ws, decision_record(cls='retry', door='unsure', radius='item DIV-1'))
    assert route(ws, capsys) == (0, 'mandate')
    fields, _ = decision.evaluate(path.read_text())
    code, out = show(capsys)
    assert code == 0 and out == (f"D-3 (Routine, mandate): {fields['Question']} Took A. "
                                 'Full record: wuwei decision show D-3 --full\n')
    assert show(capsys, '--full') == (0, path.read_text().rstrip() + '\n')
    assert show(capsys, '--widget') == (0, '[]\n')


@pytest.mark.parametrize('kwargs', [dict(radius='outside'), dict(door='one-way')])
def test_other_records_show_as_today(ws, capsys, kwargs):
    save(ws, decision_record(**kwargs))
    route(ws, capsys)
    code, out = show(capsys)
    assert code == 0 and len(out.splitlines()) > 1 and 'Routine, mandate' not in out


@pytest.fixture
def mroot(tmp_path, monkeypatch):
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    return tmp_path


def at(monkeypatch, root, ts, kind, payload):
    monkeypatch.setenv('WUWEI_NOW', ts)
    state.append_event(kind, payload, root)


def cycle_day(monkeypatch, root, day='2026-09-29', start=('plan.approved', {'items': ['A']}),
              merged_day=None, tier='light'):
    at(monkeypatch, root, f'{day}T09:00:00+00:00', *start)
    at(monkeypatch, root, f'{day}T09:20:00+00:00', 'brief written',
       {'name': 'quality-A', 'item': 'A', 'role': 'sentinel-quality', 'gate': True})
    at(monkeypatch, root, f'{day}T09:20:00+00:00', 'seat launched', {'name': 'quality-A', 'item': 'A'})
    at(monkeypatch, root, f'{day}T09:40:00+00:00', 'gate.received', {'item': 'A', 'role': 'quality'})
    merged_day = merged_day or day
    monkeypatch.setenv('WUWEI_NOW', f'{merged_day}T10:00:00+00:00')
    state._write_state(lambda data: data.update(items={'A': {'phase': 'planned', 'gates': {'tier': tier}}}),
                       root, reserved=False)
    at(monkeypatch, root, f'{merged_day}T10:00:00+00:00', 'state.transition',
       {'item': 'A', 'phase': 'merged', 'phase_changes': {'A': 'merged'}})


@pytest.mark.parametrize('start', [('plan.approved', {'items': ['A']}), ('plan.added', {'item': 'A'})])
def test_metrics_measure_cycle_time_per_tier(mroot, monkeypatch, start):
    from wuwei import metrics
    cycle_day(monkeypatch, mroot, start=start)
    value = metrics.collect(mroot)
    assert value['cycle_minutes'] == {'A': 60.0}
    assert value['gate_minutes'] == {'A': 20.0}
    assert value['cycle_by_tier'] == {'light': {'median_minutes': 60.0, 'items': 1, 'target': 60}}


def test_cycle_spans_days(mroot, monkeypatch):
    from wuwei import metrics
    cycle_day(monkeypatch, mroot, day='2026-09-28', merged_day='2026-09-29', tier='standard')
    value = metrics.collect(mroot)
    assert value['cycle_minutes'] == {'A': 1500.0}
    assert value['cycle_by_tier'] == {'standard': {'median_minutes': 1500.0, 'items': 1, 'target': 180}}


def test_no_merge_is_unmeasured(mroot, monkeypatch):
    from wuwei import metrics
    at(monkeypatch, mroot, '2026-09-29T09:00:00+00:00', 'plan.approved', {'items': ['A']})
    value = metrics.collect(mroot)
    assert value['cycle_minutes'] == value['gate_minutes'] == value['cycle_by_tier'] == 'unmeasured'


@pytest.mark.parametrize('level', ['brief', 'standard'])
def test_report_has_the_cycle_time_section(mroot, monkeypatch, level):
    from wuwei import report
    (mroot / '.wuwei/config.toml').write_text(f'[owner.verbosity]\nreport = "{level}"\n')
    cycle_day(monkeypatch, mroot)
    section = report.build(mroot).split('## Cycle time\n')[1].split('\n\n')[0]
    assert section == ('- light: median 60 minutes over 1 items (target 60)\n'
                       '- A (light): 60 minutes, gates 20 minutes')


def test_retro_names_the_tier_that_moved_most(mroot, monkeypatch):
    from datetime import datetime
    from wuwei import metrics, retro
    when = lambda day: datetime.fromisoformat(f'{day}T10:00:00+00:00')
    rows = [{'item': 'A', 'tier': 'light', 'merged_at': when('2026-09-22'), 'cycle_minutes': 90.0},
            {'item': 'B', 'tier': 'light', 'merged_at': when('2026-09-29'), 'cycle_minutes': 40.0},
            {'item': 'C', 'tier': 'standard', 'merged_at': when('2026-09-23'), 'cycle_minutes': 200.0},
            {'item': 'D', 'tier': 'standard', 'merged_at': when('2026-09-29'), 'cycle_minutes': 190.0}]
    today = when('2026-09-29')
    assert metrics.cycle_moved(rows, today) == (
        'Cycle time: light moved most, median 90 to 40 minutes week over week')
    assert metrics.cycle_moved(rows[1:2], today) == (
        'Cycle time: unmeasured (no tier merged in both weeks)')
    cycle_day(monkeypatch, mroot)
    monkeypatch.chdir(mroot)
    fields = {'Blocked': 'none', 'Gap': 'none', 'Change': 'none'}
    evidence = workspace.day_dir(mroot) / 'retro/role.json'
    evidence.parent.mkdir()
    evidence.write_text(json.dumps({'agent_id': 'b-1', 'agent_type': 'builder', 'fields': fields,
                                    'missing': [], 'invalid': []}))
    state.append_event('retro.captured', {'agent_id': 'b-1', 'agent_type': 'builder', 'fields': fields,
                                          'missing': [], 'invalid': [],
                                          'evidence': evidence.relative_to(mroot).as_posix()}, mroot)
    text = retro.compile(mroot).read_text()
    assert 'Cycle time: unmeasured (no tier merged in both weeks)' in text


def test_charters_follow_the_depth_line():
    from pathlib import Path
    charters = Path(__file__).resolve().parents[1] / 'charters'
    text = {name: (charters / f'{name}.md').read_text() for name in
            ('_common', 'builder', 'sentinel-quality', 'sentinel-arch', 'sentinel-security')}
    assert 'design 5.3' in text['_common'] and 'step zero: run' in text['_common']
    assert 'wuwei sweep classes' in text['builder']
    assert "brief's `Depth:` line says run" in text['sentinel-quality']
    assert all('Depth:' in text[name] for name in ('sentinel-arch', 'sentinel-security'))
    # The depth table replaces prose; it never adds a layer (pinned at the count before #567).
    assert len(text['_common'].splitlines()) + len(text['builder'].splitlines()) <= 65


@pytest.mark.parametrize('live,kind', [('standard', 'retro.gap'), ('light', 'retro.captured')])
def test_builder_retro_follows_the_live_diff_not_the_prediction(seat, monkeypatch, live, kind):
    from pathlib import Path
    from wuwei import dispatch
    from wuwei.guards.verdict import check_retro
    root = Path(seat['cwd'])
    monkeypatch.setattr(dispatch, 'tier', lambda root, config, row: {'tier': live})
    monkeypatch.setattr(workspace, 'load_config', lambda root: {})
    state._write_state(lambda data: data.update(
        items={'A': {'phase': 'implement', 'depth': 'light', 'worktree': 'tree'}},
        seats={'b-1': {'item': 'A', 'role': 'builder', 'status': 'running',
                       'agent_id': 'seat-one'}}), root, reserved=False)
    seat.update(agent_type='wuwei:builder', last_assistant_message='done')
    check_retro(seat)
    assert retro_events(seat)[-1]['kind'] == kind
