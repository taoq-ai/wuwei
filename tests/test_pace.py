"""#579: the day pace (careful, steady, fast)."""

import itertools

import pytest

from wuwei import state, workspace
from test_dispatch import root, tiered  # noqa: F401  (fixture and helper)


def test_current_reads_the_day_then_the_config_default():
    from wuwei import pace
    config = {'pace': {'default': 'careful'}}
    assert pace.current({'pace': 'fast'}, config) == 'fast'
    assert pace.current({}, config) == 'careful'


@pytest.mark.parametrize('answer,expected', [
    ('Approve', 'fast'), ('Approve (Recommended)', 'fast'), ('Approve at careful', 'careful'),
    ('steady', 'steady')])
def test_label_maps_the_card_answer(answer, expected):
    from wuwei import pace
    assert pace.label(answer, 'fast') == expected


@pytest.mark.parametrize('answer', ['Change something', 'quick'])
def test_label_refuses_other_answers(answer):
    from wuwei import pace
    with pytest.raises(ValueError, match='careful, steady or fast'):
        pace.label(answer, 'fast')


@pytest.mark.parametrize('key', ['pace', 'pace_card'])
def test_pace_state_is_producer_owned(root, key):
    with pytest.raises(state.StateError, match='wuwei plan'):
        state.set_state(key, 'fast', root)


def test_config_keys_default_and_validate(tmp_path):
    config = workspace.load_config(tmp_path, raw='[[repos]]\nname = "acme/widget"\npath = "repo"\n'
                                                 'default_branch = "main"\n')
    assert config['pace']['default'] == 'steady'
    assert config['repos'][0]['tests'] == ''
    with pytest.raises(workspace.ConfigError, match='careful or steady or fast'):
        workspace.load_config(tmp_path, raw='[pace]\ndefault = "quick"\n')


# Phase 2: the tier rule.

def test_adjust_table():
    from wuwei import pace
    assert pace.adjust('steady', 'light', 'x matches guards/*', False, True) == ('light', 'light', [])
    assert pace.adjust('careful', 'light', None, False, True) == ('standard', 'standard', ['pace careful'])
    assert pace.adjust('careful', 'standard', 'x matches guards/*', False, True) == (
        'full', 'full', ['pace careful: x matches guards/*'])
    assert pace.adjust('fast', 'standard', 'x matches guards/*', False, True) == (
        'full', 'full', ['pace fast: x matches guards/*'])
    assert pace.adjust('fast', 'standard', None, False, True) == (
        'standard', 'light', ['pace fast: light depth'])
    assert pace.adjust('fast', 'standard', None, True, True) == ('standard', 'standard', [])
    assert pace.adjust('fast', 'standard', None, False, False) == ('standard', 'standard', [])
    assert pace.adjust('fast', 'light', None, False, True) == ('light', 'light', [])
    from wuwei.dispatch import TIERS
    for value, tier, guard, flagged, measured in itertools.product(
            pace.PACES, TIERS, (None, 'g'), (False, True), (False, True)):
        got, depth, _ = pace.adjust(value, tier, guard, flagged, measured)
        assert TIERS.index(got) >= TIERS.index(tier)
        assert TIERS.index(depth) <= TIERS.index(got)


def set_pace(root, value):
    state._write_state(lambda data: data.update(pace=value), root, reserved=False)


def tier_record(root):
    from wuwei import dispatch
    return dispatch.next_step('A', root)['tier']


def test_fast_lightens_a_plain_standard_item(root, monkeypatch):
    from wuwei import dispatch
    tiered(root, monkeypatch, [('cli/wuwei/report.py', 3, 1)], floor='standard')
    set_pace(root, 'fast')
    record = tier_record(root)
    assert (record['tier'], record['roles'], record['depth']) == (
        'standard', ['arch', 'quality', 'security'], 'light')
    assert 'pace fast: light depth' in record['reasons']
    row = state.read_state(root)['items']['A']
    assert dispatch.depth(row, gate=True) == 'light'


def test_fast_and_careful_raise_guard_code_to_full(root, monkeypatch):
    tiered(root, monkeypatch, [('cli/wuwei/guards/x.py', 3, 1)])
    set_pace(root, 'fast')
    record = tier_record(root)
    assert record['tier'] == 'full' and record.get('depth', 'full') == 'full'
    assert 'pace fast: cli/wuwei/guards/x.py matches guards/*' in record['reasons']


def test_fast_keeps_a_flagged_item_at_standard_depth(root, monkeypatch):
    tiered(root, monkeypatch, [('cli/wuwei/report.py', 3, 1)], flags=['trust_surface'])
    set_pace(root, 'fast')
    record = tier_record(root)
    assert record['tier'] == 'standard' and 'depth' not in record


def test_careful_raises_a_docs_only_item_to_three_gates(root, monkeypatch):
    tiered(root, monkeypatch, [('docs/guide.md', 3, 1)], floor='standard')
    set_pace(root, 'careful')
    record = tier_record(root)
    assert record['tier'] == 'standard' and record['roles'] == ['arch', 'quality', 'security']
    assert not any(reason.startswith('docs-only') for reason in record['reasons'])


def test_careful_raises_light_to_standard(root, monkeypatch):
    tiered(root, monkeypatch, [('src/app.py', 3, 1)])
    set_pace(root, 'careful')
    record = tier_record(root)
    assert record['tier'] == 'standard' and record['roles'] == ['arch', 'quality', 'security']
    assert 'pace careful' in record['reasons']


def test_steady_records_are_unchanged(root, monkeypatch):
    tiered(root, monkeypatch, [('src/app.py', 3, 1)])
    set_pace(root, 'steady')
    assert tier_record(root) == {'tier': 'light', 'computed': 'light', 'roles': ['quality'],
                                 'reasons': ['4 changed lines within light_max_lines 100']}


def test_fast_light_depth_skips_the_class_sweep(root, monkeypatch, capsys):
    from wuwei.__main__ import main
    monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
    tiered(root, monkeypatch, [('cli/wuwei/report.py', 3, 1)], floor='standard')
    set_pace(root, 'fast')
    assert main(['sweep', 'classes', 'repo']) == 0
    assert capsys.readouterr().out == 'Depth: light; no class sweep\n'


@pytest.mark.parametrize('value,expected', [('fast', 'Re-read:'), ('steady', 'Delta review:')])
def test_fast_fix_round_is_re_read(root, value, expected, monkeypatch):
    from test_dispatch import built, gate_fix, live_head
    from wuwei import dispatch
    built(root)
    state._write_state(lambda data: data['items']['A'].update(gates={
        'tier': 'standard', 'computed': 'standard', 'reasons': [], 'roles': ['arch', 'quality', 'security'],
        **({'depth': 'light'} if value == 'fast' else {})}), root, reserved=False)
    gate_fix(root)
    state._write_state(lambda data: data['seats']['quality-1'].update(
        agent_id='agent-quality-1', head='abc1234' + '0' * 33), root, reserved=False)
    dispatch.next_step('A', root)
    live_head(monkeypatch, 'def5678' + '0' * 33)
    state.transition('A', 'delta', root)
    [action] = dispatch.next_step('A', root)['seats']
    assert action['feedback'].startswith(expected)


# Phase 3: checks and push evidence.

from test_commit_push import SHA, guard, payload, set_fast_checks, workspace_case  # noqa: E402,F401


def with_tests(root, tests='python3 -m pytest -q'):
    text = (root / '.wuwei/config.toml').read_text().replace(
        'fast_checks = ["unit"]\n', f'fast_checks = ["unit"]\ntests = "{tests}"\n')
    (root / '.wuwei/config.toml').write_text(text)


def commands(root, fake=None, diff=()):
    from wuwei import fast_checks
    from wuwei.registry import Result
    if fake is not None:
        fake.results['diff_stat'] = Result(0, [{'path': p, 'additions': 1, 'deletions': 0} for p in diff])
    config = workspace.load_config(root)
    return fast_checks.commands(root, config, config['repos'][0], root / 'repo')


def test_commands_follow_the_pace(workspace_case):
    root, fake = workspace_case
    with_tests(root)
    (root / 'repo/tests').mkdir()
    (root / 'repo/tests/test_a.py').write_text('')
    assert commands(root) == ['unit']
    set_pace(root, 'careful')
    assert commands(root) == ['unit', 'python3 -m pytest -q']
    set_pace(root, 'fast')
    assert commands(root, fake, ['tests/test_a.py', 'tests/test_gone.py', 'cli/x.py']) == [
        'python3 -m pytest -q tests/test_a.py']
    assert commands(root, fake, ['cli/x.py']) == ['unit']
    from wuwei.registry import Result
    fake.results['diff_stat'] = Result(2, None, 'git failed')
    assert commands(root) == ['unit']


def test_fast_without_a_test_command_runs_the_fast_checks(workspace_case):
    root, fake = workspace_case
    set_pace(root, 'fast')
    assert commands(root, fake, ['tests/test_a.py']) == ['unit']
    set_pace(root, 'careful')
    assert commands(root) == ['unit']


def test_record_runs_the_pace_commands_and_times_them(workspace_case, monkeypatch):
    from types import SimpleNamespace
    from wuwei import fast_checks, registry
    from wuwei.registry import Result
    root, fake = workspace_case
    with_tests(root)
    set_pace(root, 'careful')
    calls = []
    monkeypatch.setattr(registry, 'load', lambda kind, config: SimpleNamespace(
        run=lambda path, command, timeout=None, root=None: calls.append(command) or Result(0)) if kind == 'checks' else fake)
    assert fast_checks.record(root / 'repo') == 0
    assert calls == ['unit', 'python3 -m pytest -q']
    records = state.read_state(root)['fast_checks']['example/project']
    assert all(type(row['seconds']) in (int, float) for row in records.values())


def test_push_evidence_follows_the_pace(workspace_case):
    root, fake = workspace_case
    with_tests(root)
    (root / 'repo/tests').mkdir()
    (root / 'repo/tests/test_a.py').write_text('')
    from wuwei.registry import Result
    fake.results['diff_stat'] = Result(0, [{'path': 'tests/test_a.py', 'additions': 1, 'deletions': 0}])
    touched = {'python3 -m pytest -q tests/test_a.py': {'sha': SHA, 'exit': 0}}
    set_fast_checks(root, {'example/project': touched})
    push = payload(root, 'git push origin feature')
    set_pace(root, 'fast')
    assert guard().check(push)[0] == 0
    set_pace(root, 'steady')
    code, reason = guard().check(push)
    assert code == 1 and 'fast check "unit"' in reason
    set_pace(root, 'careful')
    set_fast_checks(root, {'example/project': {'unit': {'sha': SHA, 'exit': 0}}})
    code, reason = guard().check(push)
    assert code == 1 and 'fast check "python3 -m pytest -q"' in reason


from test_build_next import launch, seat, stop  # noqa: E402,F401


def test_build_check_completes_on_the_pace_commands(seat):
    from wuwei import registry
    from wuwei.__main__ import main
    from wuwei.commands import build
    root, _, _, _, results = seat
    config = root / '.wuwei/config.toml'
    config.write_text(config.read_text().replace('fast_checks=["test"]\n', 'fast_checks=["test"]\ntests="suite"\n'))
    set_pace(root, 'careful')
    launch(seat, build.next_action('A', root=root))
    assert stop(seat) == (0, '')
    results += [registry.Result(0), registry.Result(1, {'test_ids': ['test_two'], 'error': 'failure'})]
    assert main(['build', 'check', 'A']) == 1
    assert state.read_state(root)['builds']['A']['commands'] == ['test', 'suite']


def test_checks_line_names_what_the_pace_runs():
    from wuwei.brief import checks_line
    assert checks_line('steady', 'pytest') is None and checks_line('fast', '') is None
    assert checks_line('careful', 'pytest').startswith('Checks: careful; the fast checks and pytest before the PR')
    assert 'not configured locally (repos.tests); CI runs it' in checks_line('careful', '')
    assert checks_line('fast', 'pytest').startswith(
        'Checks: fast; pytest on the test files your diff changes, never the full suite; CI is the gate')


from test_brief import brief, day  # noqa: E402,F401
from test_process_depth import depth_day, depth_line  # noqa: E402


def test_fast_builder_brief_runs_light_depth_and_touched_tests(day, monkeypatch):
    root, directory = depth_day(day, ['cli/wuwei/report.py'], floor='standard')
    config = root / '.wuwei/config.toml'
    config.write_text(config.read_text().replace('default_branch = "main"\n',
                                                 'default_branch = "main"\ntests = "pytest"\n'))
    set_pace(root, 'fast')
    assert brief(monkeypatch, 'body', 'builder', 'X', 'b-fast', '--worktree', 'tree') == 0
    assert depth_line(directory, 'b-fast')[0].startswith('Depth: light; skip: the class sweep')
    assert state.read_state(root)['items']['X']['depth'] == 'light'
    header = (directory / 'briefs/b-fast.md').read_text().split('\n\n', 1)[0]
    assert 'Checks: fast; pytest on the test files your diff changes' in header


# Phase 4: host and seats.

import os  # noqa: E402

from test_calibrate import ports, usage_day, workspace_root  # noqa: E402,F401


def test_host_measures_the_load_and_the_token_costs(workspace_root, monkeypatch):
    from wuwei import calibrate
    (workspace_root / '.wuwei/config.toml').write_text('[budget]\ntokens_per_day = 200000\n')
    config = workspace.load_config(workspace_root)
    monkeypatch.setattr(os, 'getloadavg', lambda: (34.04, 20.0, 10.0))
    limits = calibrate.host(workspace_root, config)
    assert limits['load'] == 34.0
    assert (limits['per_seat_tokens'], limits['used_tokens']) == (None, None)
    usage_day(workspace_root, '2026-09-30', 100000, 100000)
    limits = calibrate.host(workspace_root, config)
    assert (limits['per_seat_tokens'], limits['used_tokens']) == (100000, 0)

    def unavailable():
        raise OSError('no load average')
    monkeypatch.setattr(os, 'getloadavg', unavailable)
    assert calibrate.host(workspace_root, config)['load'] is None


HOT = {'cap': 4, 'seats': 4, 'bound': 'host', 'cores': 10, 'load': 34.0}
HOLD = ('host load 34.0 at or over 10 cores (pace fast); the next seat launches when the load '
        'falls below 10')


def test_seats_rule():
    from wuwei import pace
    assert pace.seats('careful', HOT) == (3, 'pace careful', None)
    assert pace.seats('careful', {**HOT, 'cap': 1}) == (1, 'pace careful', None)
    assert pace.seats('fast', HOT) == (4, 'load', HOLD)
    for value, limits in (('fast', {**HOT, 'load': 3.0}), ('steady', HOT), ('fast', {**HOT, 'load': None}),
                          ('fast', {'cap': 4, 'seats': 4, 'bound': 'unmeasured'})):
        assert pace.seats(value, limits) == (limits['cap'], limits['bound'], None)


from test_parallel_dispatch import approved, launch_set  # noqa: E402
from test_parallel_dispatch import day as pday  # noqa: E402,F401


def test_fast_on_a_saturated_host_holds_every_launch(pday, monkeypatch):
    approved(pday)
    monkeypatch.setattr(os, 'getloadavg', lambda: (34.0, 30.0, 20.0))
    monkeypatch.setattr(os, 'cpu_count', lambda: 10)
    set_pace(pday.root, 'fast')
    entries, rows = launch_set(pday)
    assert entries == [(item, 'wait') for item in 'ABCD']
    assert all(row['reason'] == HOLD for row in rows)
    assert pday.data['cap_bound'] == 'load'
    line = pday.run('status', '--line')
    assert 'pace fast' in line and 'held by load' in line


def test_careful_plans_cap_minus_one(pday):
    approved(pday)
    set_pace(pday.root, 'careful')
    entries, _ = launch_set(pday)
    assert entries == [('A', 'start'), ('B', 'start'), ('C', 'start'), ('D', 'wait')]
    assert 'pace careful' in pday.run('status', '--line')


def test_status_line_has_no_pace_token_at_steady(pday):
    approved(pday)
    assert 'pace' not in pday.run('status', '--line')
    set_pace(pday.root, 'steady')
    assert 'pace' not in pday.run('status', '--line')


# Phase 5: the advice.

import json  # noqa: E402
import re  # noqa: E402
from datetime import datetime  # noqa: E402

NOW = datetime.fromisoformat('2026-10-08T09:00:00+00:00')
IDLE = {'cap': 4, 'seats': 4, 'bound': 'host', 'cores': 10, 'load': 1.0}
GOALS = {'G-1': {'date': '2026-10-30'}, 'G-2': {'date': '2026-10-10'}}


def queue(tiers, goal='G-2', paths=()):
    return {'goals': ['G-1', 'G-2'], 'envelope': {'start': '09:00', 'end': '17:00', 'net_build_hours': 6},
            'candidates': [{'id': chr(65 + index), 'goal': goal, 'track': 'SLICE', 'tier': tier,
                            'flags': {'trust_surface': False, 'boundary_relevant': False, 'agent_surface': False},
                            **({'paths': list(paths)} if paths else {})}
                           for index, tier in enumerate(tiers)]}


@pytest.fixture
def ws(tmp_path):
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('')
    return tmp_path


def advise(root, data, limits=IDLE, raw=''):
    from wuwei import pace
    (root / '.wuwei/config.toml').write_text(raw)
    return pace.advise(root, workspace.load_config(root), data, GOALS, limits, NOW)


def test_a_light_queue_with_a_near_goal_advises_fast(ws):
    advice = advise(ws, queue(['light'] * 7 + ['standard'] * 2))
    assert advice['pace'] == 'fast' and advice['binding'] == 'queue'
    first, second, wish = advice['lines']
    assert re.fullmatch(r'9 items, 7 light, 2 standard, G-2 due 2026-10-10: fast, 4 seats, '
                        r'expected close \d\d:\d\d', first), first
    assert second.startswith('Host 10 cores, load 1.0, last suite unmeasured;') and second.endswith('binding: queue')
    assert wish == 'Your default is steady; the advice is fast (binding: queue)'
    assert len(advise(ws, queue(['light'] * 9), raw='[pace]\ndefault = "fast"\n')['lines']) == 2


def test_guard_items_advise_careful(ws):
    advice = advise(ws, queue(['standard'] * 2, paths=['cli/wuwei/guards/x.py']))
    assert advice['pace'] == 'careful'
    assert '2 items touching guard code' in advice['lines'][0] and ': careful,' in advice['lines'][0]
    assert advice['lines'][1].endswith('binding: queue; steady unlocks once they merge')


def test_a_saturated_host_caps_the_advice_at_steady(ws):
    advice = advise(ws, queue(['light'] * 9), {**IDLE, 'load': 34.0})
    assert (advice['pace'], advice['binding']) == ('steady', 'host')
    assert advice['lines'][1].endswith('binding: host; fast unlocks when the load average falls below 10')
    assert 'load 34.0' in advice['lines'][1]


def test_the_budget_advises_against_but_never_changes_the_pace(ws):
    limits = {**IDLE, 'per_seat_tokens': 1000, 'used_tokens': 0}
    advice = advise(ws, queue(['light'] * 7 + ['standard'] * 2), limits, '[budget]\ntokens_per_day = 12000\n')
    assert (advice['pace'], advice['binding'], advice['reach']) == ('fast', 'budget', 6)
    assert 'budget reaches 6 of 9 items at fast: advised against' in advice['lines'][1]
    covered = advise(ws, queue(['light'] * 2), limits, '[budget]\ntokens_per_day = 12000\n')
    assert covered['binding'] == 'queue' and 'budget covers the queue' in covered['lines'][1]


def test_host_line_reads_the_last_suite(ws):
    from wuwei import pace
    raw = '[[repos]]\nname = "acme/widget"\npath = "repo"\ndefault_branch = "main"\ntests = "pytest"\n'
    (ws / '.wuwei/config.toml').write_text(raw)
    config = workspace.load_config(ws)
    assert pace.host_line(ws, IDLE, config) == 'Host 10 cores, load 1.0, last suite unmeasured'
    day = ws / '.wuwei/days/2026-10-07'
    day.mkdir(parents=True)
    (day / 'state.json').write_text(json.dumps({'fast_checks': {'acme/widget': {
        'pytest': {'sha': 'a' * 40, 'exit': 0, 'seconds': 840}}}}))
    assert pace.host_line(ws, {**IDLE, 'load': None}, config) == 'Host 10 cores, load unmeasured, last suite 14 min'


def pace_call(root, command, **extra):
    from wuwei.guards.protect_state import check_bash
    return check_bash({'hook_event_name': 'PreToolUse', 'session_id': 'planner-1', 'cwd': str(root),
                       'tool_name': 'Bash', 'tool_input': {'command': command}, **extra})


def test_only_the_planner_sets_the_pace_below_strict(root):
    from wuwei import plan
    plan.session('planner-1', root)
    assert pace_call(root, 'bin/wuwei plan set pace=fast') == (0, '')
    code, reason = pace_call(root, 'bin/wuwei plan set pace=fast', agent_id='seat-1')
    assert code == 1 and 'Spec overrides are an owner action' in reason
    assert pace_call(root, 'bin/wuwei plan set pace=fast --reason x')[0] == 1
    assert pace_call(root, 'bin/wuwei plan set pace=$X')[0] != 0
    assert pace_call(root, 'bin/wuwei plan set A spec=skipped --reason x')[0] == 1
    with (root / '.wuwei/config.toml').open('a') as stream:
        stream.write('[security]\nposture = "strict"\n')
    code, reason = pace_call(root, 'bin/wuwei plan set pace=fast')
    assert code == 1 and 'host terminal' in reason


def test_gate_then_text_and_off_path_accept_any_approve_label():
    from wuwei import metrics
    from wuwei.commands.next import THEN
    assert 'On any Approve option run its record command with <label> replaced by' in THEN['gate']
    assert metrics._matches('wuwei plan approve --items A --goals-confirmed --pace "Approve at fast"',
                            'wuwei plan approve --items A --goals-confirmed --pace "<label>"')


def test_pace_command_prints_the_pace_the_inputs_and_the_balance(pday):
    from wuwei.commands import read_only
    approved(pday)
    set_pace(pday.root, 'fast')
    lines = pday.run('pace').splitlines()
    assert lines[0].startswith('Pace: fast (advice ') and 'your default steady' in lines[0]
    assert lines[1].startswith('Advice: 4 items')
    assert lines[2].startswith('Inputs: Host 4 cores, load ') and 'wish steady' in lines[2] and 'budget' in lines[2]
    assert lines[3].startswith('Balance: binding ')
    assert read_only(['pace'])
    (pday.directory / 'state.json').chmod(0o600)
    (pday.directory / 'state.json').write_text('{')
    assert 'wuwei pace:' in pday._main(('pace',), 2, '', ('pace',))


# Phase 7: measurement and the default card.

from test_process_depth import at, mroot  # noqa: E402,F401


def paced_day(monkeypatch, root, day, item, value, cards=0, names=None):
    at(monkeypatch, root, f'{day}T09:00:00+00:00', 'plan.approved', {'items': [item]})
    state._write_state(lambda data: data.update(pace=value, items={item: {
        'phase': 'merged', 'gates': {'tier': 'light', 'computed': 'light'}}},
        decision_routes={f'D-{n}': {} for n in range(1, cards + 1)}), root, reserved=False)
    at(monkeypatch, root, f'{day}T10:00:00+00:00', 'state.transition',
       {'item': item, 'phase': 'merged', 'phase_changes': {item: 'merged'}})
    if names:
        path = workspace.day_dir(root) / 'briefs' / f'{item}-builder.md'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f'Fix the regression {names} left.\n')
        at(monkeypatch, root, f'{day}T10:30:00+00:00', 'brief written',
           {'name': f'{item}-builder', 'item': item, 'role': 'builder', 'path': str(path.relative_to(root))})


def test_metrics_per_pace(mroot, monkeypatch):
    from wuwei import metrics
    assert metrics.by_pace(mroot) == 'unmeasured'
    paced_day(monkeypatch, mroot, '2026-09-28', 'A', 'steady', cards=2)
    paced_day(monkeypatch, mroot, '2026-09-29', 'B', 'fast')
    paced_day(monkeypatch, mroot, '2026-09-30', 'C', 'steady', names='B')
    assert {row['item']: row['pace'] for row in metrics.cycles(mroot)} == {'A': 'steady', 'B': 'fast', 'C': 'steady'}
    table = metrics.by_pace(mroot)
    assert table['steady'] | {'cycle_by_tier': None} == {'days': 2, 'merged': 2, 'escaped': 0, 'cards': 2,
                                                         'cycle_by_tier': None}
    assert (table['fast']['merged'], table['fast']['escaped']) == (1, 1)
    assert table['fast']['cycle_by_tier']['light']['median_minutes'] == 60.0
    assert metrics.collect(mroot)['by_pace'] == table


def test_report_and_retro_show_the_pace(mroot, monkeypatch):
    from wuwei import report
    paced_day(monkeypatch, mroot, '2026-09-29', 'B', 'fast')
    paced_day(monkeypatch, mroot, '2026-09-30', 'C', 'steady', names='B')
    section = report.build(mroot).split('## Pace\n')[1].split('\n\n')[0].splitlines()
    assert section[0] == 'Pace: steady (recommended unmeasured, binding unmeasured)'
    assert '- fast: 1 days, 1 merged, light median 60, 1 escaped, 0 cards' in section
    assert '- fast costs escaped defects: 1 of 1 merged' in section
    assert report.pace_lines(mroot, state.read_state(mroot))[1:] == section[1:]


def ten_days(paces=('steady',) * 5 + ('fast',) * 5):
    return {value: {'days': paces.count(value), 'merged': 10, 'escaped': 2 if value == 'fast' else 0,
                    'cards': 3, 'cycle_by_tier': {'light': {'median_minutes': 50.0, 'items': 10}}}
            for value in set(paces)}


def test_steward_proposes_a_default_pace_once(mroot, monkeypatch):
    from wuwei import decision, metrics, pace
    monkeypatch.setenv('WUWEI_NOW', '2026-09-30T09:00:00+00:00')
    config = workspace.load_config(mroot)
    monkeypatch.setattr(metrics, 'by_pace', lambda root: ten_days(('steady',) * 9))
    assert pace.propose_default(mroot, config) is None
    monkeypatch.setattr(metrics, 'by_pace', lambda root: ten_days(('steady',) * 4 + ('fast',) * 5))
    assert pace.propose_default(mroot, config) is None
    monkeypatch.setattr(metrics, 'by_pace', lambda root: ten_days())
    ident = pace.propose_default(mroot, config)
    fields, _ = decision.evaluate(decision.today_path(ident, mroot).read_text())
    assert sorted(row[1] for row in decision.options(fields)) == [
        'Keep the default pace steady', 'pace.default = fast', 'pace.default = steady']
    from wuwei.commands.setup import assignment
    assert assignment('pace.default = fast') == ('pace.default', 'fast')
    assert assignment('pace.default = quick') is None
    assert fields['Recommendation'] == 'steady' and 'fast costs escaped defects: 2 of 10 merged' in fields['Context']
    assert state.read_state(mroot)['pace_card']['id'] == ident
    assert pace.propose_default(mroot, config) is None
    from wuwei.__main__ import main
    import contextlib, io
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        assert main(['decision', 'show', ident, '--widget']) == 0
    assert '--from-card ' + ident in out.getvalue()


def test_docs_name_the_pace():
    from pathlib import Path
    site = Path(__file__).resolve().parents[1] / 'docs/site'
    concepts, daily = (site / 'concepts.md').read_text(), (site / 'daily.md').read_text()
    configuration, reference = (site / 'configuration.md').read_text(), (site / 'reference.md').read_text()
    assert '### Pace' in concepts and all(word in concepts for word in ('careful', 'steady', 'fast'))
    assert 'Approve at careful' in daily and 'wuwei plan set pace=' in daily and 'binding:' in daily
    assert '`pace.default`' in configuration and '`repos.tests`' in configuration and '`[pace]`' in configuration
    assert all(text in reference for text in ('`bin/wuwei pace`', '--pace', 'plan set pace='))
