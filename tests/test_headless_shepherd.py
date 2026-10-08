"""#511: the headless shepherd sweeps owned PRs without a session and reports in the morning."""

import json
from types import SimpleNamespace

import pytest

from wuwei import merge, registry, shepherd, state, workspace
from wuwei.registry import Result
from test_stop import DAY, REF, case, own

TODAY = '2026-09-29'
NIGHT = TODAY + 'T02:00:00+00:00'


def test_day_pin_moves_day_dir_and_resets(case):
    root, _, _ = case
    assert workspace.day_dir(root).name == DAY
    workspace._DAY = '2026-09-01'
    try:
        assert workspace.day_dir(root) == root / '.wuwei/days/2026-09-01'
    finally:
        workspace._DAY = None
    assert workspace.day_dir(root).name == DAY


def test_owning_day_is_the_newest_approved_day_today_included(case, monkeypatch):
    root, _, _ = case
    yesterday = workspace.day_dir(root)
    monkeypatch.setenv('WUWEI_NOW', NIGHT)
    assert shepherd.owning_day(root) is None  # yesterday has state, but no approval
    monkeypatch.setenv('WUWEI_NOW', DAY + 'T12:00:00+00:00')
    state._write_state(lambda data: data.update(gate_approved=True), root, reserved=False)
    monkeypatch.setenv('WUWEI_NOW', NIGHT)
    assert shepherd.owning_day(root) == yesterday
    state.write_state(lambda data: None, root)  # a session wrote today's state, not approved
    assert shepherd.owning_day(root) == yesterday
    state._write_state(lambda data: data.update(gate_approved=True), root, reserved=False)
    assert shepherd.owning_day(root) == workspace.day_dir(root)


WEEKEND = '2026-10-01T02:00:00+00:00'


def clock_days(root, monkeypatch, *days):
    """The watch service writes clock state into every calendar day; none is approved."""
    for day in days:
        monkeypatch.setenv('WUWEI_NOW', day + 'T01:00:00+00:00')
        state.write_state(lambda data: None, root)


def test_the_weekend_sweep_skips_unapproved_clock_days(night, monkeypatch):
    """Review F2: Friday owns the PR while the watch writes state into Saturday and Sunday."""
    root, host, _, calls = night
    approve(host)
    clock_days(root, monkeypatch, '2026-09-29', '2026-09-30')
    monkeypatch.setenv('WUWEI_NOW', WEEKEND)
    assert shepherd.owning_day(root) == root / '.wuwei/days' / DAY
    assert shepherd.overnight(root) == 1
    assert calls['check'] == [REF] and len(events(root, 'shepherd.swept')) == 1
    assert shepherd.last_swept(root) == WEEKEND


def test_owning_day_is_none_without_any_day_state(tmp_path, monkeypatch):
    (tmp_path / '.wuwei/days').mkdir(parents=True)
    monkeypatch.setenv('WUWEI_NOW', NIGHT)
    assert shepherd.owning_day(tmp_path) is None


def fail(*args, **kwargs):
    pytest.fail('the headless sweep never calls the runtime')


@pytest.fixture
def night(case, monkeypatch):
    """Yesterday's approved day owns REF; the clock is 02:00 today with no state for today."""
    root, host, vcs = case
    own(root)
    state._write_state(lambda data: data.update(gate_approved=True), root, reserved=False)
    runtime = SimpleNamespace(dispatch=fail, headless=fail)
    monkeypatch.setattr(registry, 'load', lambda kind, config: {
        'code_host': host, 'vcs': vcs, 'runtime': runtime}[kind])
    calls = {'check': [], 'execute': [], 'ping': []}
    monkeypatch.setattr(merge, 'check', lambda ref, root=None, **kw: calls['check'].append(ref) or Result(0, {}))
    monkeypatch.setattr(merge, 'execute', lambda ref, root=None, **kw: calls['execute'].append(ref) or Result(0, {}))
    monkeypatch.setattr(shepherd, 'post_review_request', lambda root, ref: calls['ping'].append(ref) or 0)
    monkeypatch.setenv('WUWEI_NOW', NIGHT)
    return root, host, vcs, calls


def events(root, kind, day=DAY):
    from wuwei import watch
    return [row['payload'] for row in watch.records(root / '.wuwei/days' / day / 'events.jsonl')
            if row['kind'] == kind]


def approve(host):
    host.results['reviews'] = Result(0, [{'id': 5, 'author': 'reviewer', 'is_bot': False,
        'state': 'approved', 'sha': 'a' * 40, 'body': '', 'submitted_at': DAY + 'T23:00:00+00:00'}])


def register_planner(root, day=None):
    from wuwei import sessions
    workspace._DAY = day
    try:
        if not (workspace.day_dir(root) / 'state.json').exists():
            state.write_state(lambda data: None, root)
        sessions.touch(root, 'S1', hook='SessionStart', cwd=str(root))
        state._write_state(lambda data: data.update(planner_session_id='S1'), root, reserved=False)
    finally:
        workspace._DAY = None


@pytest.mark.parametrize('day', [None, DAY])
def test_live_planner_owns_the_prs(night, capsys, monkeypatch, day):
    root, host, _, calls = night
    approve(host)
    register_planner(root, day)
    from wuwei import pr_actions
    monkeypatch.setattr(pr_actions, 'evaluate', fail)
    assert shepherd.overnight(root) == 0
    assert 'shepherd: planner live' in capsys.readouterr().out
    assert calls == {'check': [], 'execute': [], 'ping': []}
    assert not events(root, 'shepherd.overnight') and not events(root, 'shepherd.swept')
    assert not (root / '.wuwei/days' / DAY / 'overnight.md').exists()


def test_a_failed_sweep_unpins_the_day(night, monkeypatch, capsys):
    root, _, _, _ = night
    from wuwei import pr_actions
    def broken(root):
        raise OSError('disk gone')
    monkeypatch.setattr(pr_actions, 'evaluate', broken)
    assert shepherd.overnight(root) == 2
    assert 'disk gone' in capsys.readouterr().out
    assert workspace._DAY is None


def test_nothing_owned_is_clean(case, tmp_path, monkeypatch, capsys):
    root, _, _ = case
    state._write_state(lambda data: data.update(gate_approved=True), root, reserved=False)
    monkeypatch.setenv('WUWEI_NOW', NIGHT)
    assert shepherd.overnight(root) == 0
    empty = tmp_path / 'empty'
    (empty / '.wuwei/days').mkdir(parents=True)
    assert shepherd.overnight(empty) == 0
    assert capsys.readouterr().out.count('shepherd: no owned PRs') == 2
    assert not events(root, 'shepherd.overnight') and not events(root, 'shepherd.swept')


CLEARED = 'merge cleared by policy; merge waits for the morning (#524)'


def test_an_approval_at_night_is_checked_and_queued_for_the_morning(night):
    """Review F4: until #524 lands the sweep only reads merge check; the morning merges."""
    root, host, _, calls = night
    approve(host)
    assert shepherd.overnight(root) == 1
    assert calls['check'] == [REF] and calls['execute'] == []
    assert events(root, 'shepherd.overnight') == [
        {'pr': REF, 'state': 'approved', 'outcome': 'queued', 'reason': CLEARED, 'evidence': []}]
    assert len(events(root, 'shepherd.swept')) == 1
    assert not (root / '.wuwei/days' / TODAY / 'events.jsonl').exists()
    assert f'{REF} approved: {CLEARED}. Run: bin/wuwei pr act {REF}' in (
        root / '.wuwei/days' / DAY / 'overnight.md').read_text()


def test_a_refused_merge_is_queued_with_the_policy_reason(night, monkeypatch):
    root, host, _, calls = night
    approve(host)
    reason = 'merge policy: merge.auto is off; the owner merges; ask the owner'
    monkeypatch.setattr(merge, 'check', lambda ref, root=None, **kw: Result(1, None, reason))
    assert shepherd.overnight(root) == 1
    assert calls['execute'] == []
    row, = events(root, 'shepherd.overnight')
    assert (row['outcome'], row['reason']) == ('queued', reason)


def test_a_second_sweep_repeats_nothing(night):
    root, host, _, calls = night
    approve(host)
    assert shepherd.overnight(root) == 1
    assert shepherd.overnight(root) == 1
    assert calls['check'] == [REF, REF] and calls['execute'] == []
    assert len(events(root, 'shepherd.overnight')) == 1
    assert len(events(root, 'shepherd.swept')) == 2


def test_a_pr_merged_by_a_person_is_recorded_once(night):
    root, host, _, calls = night
    host.results['pr'].data.update(merged=True, state='closed')
    assert shepherd.overnight(root) == 0
    assert shepherd.overnight(root) == 0
    assert [row['outcome'] for row in events(root, 'shepherd.overnight')] == ['merged']
    assert calls['execute'] == []


def test_a_review_comment_at_night_is_queued_never_answered(night):
    root, host, vcs, _ = night
    host.results['threads'].data['threads'] = [{'id': 'T17', 'resolved': False, 'outdated': False,
        'path': 'src/app.py', 'comments': [{'id': 3, 'author': 'bob', 'is_bot': False,
            'body': 'Why\n  this   name?', 'created_at': DAY + 'T23:00:00+00:00'}]}]
    assert shepherd.overnight(root) == 1
    row, = events(root, 'shepherd.overnight')
    assert (row['state'], row['outcome']) == ('threads_unanswered', 'queued')
    assert row['evidence'] == ['thread T17 by bob on src/app.py: Why this name?']
    assert not {'comment', 'request_reviewers', 'merge'} & {call[0] for call in host.calls}
    data = state.read_state(directory=root / '.wuwei/days' / DAY)
    assert not data.get('drafts') and not data.get('pr_action_decisions') and not data.get('builds')
    assert not list((root / '.wuwei/days' / DAY / 'decisions').glob('D-*.md'))
    assert not vcs.calls


@pytest.mark.parametrize('change, current, line', [
    ('ci_red', 'ci_red', 'check tests: failure'),
    ('conflicted', 'conflicted', 'conflicts with its base'),
    ('changes', 'changes_requested', 'review 5 by bob: Please rename it'),
    ('closed', 'closed', 'closed without merge'),
])
def test_model_work_is_queued_with_its_evidence(night, change, current, line):
    root, host, vcs, calls = night
    if change == 'ci_red':
        host.results['checks'] = Result(0, [{'sha': 'a' * 40, 'name': 'tests', 'state': 'completed',
                                             'conclusion': 'failure'}])
    elif change == 'conflicted':
        host.results['pr'].data['mergeable'] = False
    elif change == 'closed':
        host.results['pr'].data['state'] = 'closed'
    else:
        host.results['reviews'] = Result(0, [{'id': 5, 'author': 'bob', 'is_bot': False,
            'state': 'changes_requested', 'sha': 'a' * 40, 'body': 'Please rename it',
            'submitted_at': DAY + 'T23:00:00+00:00'}])
    assert shepherd.overnight(root) == 1
    row, = events(root, 'shepherd.overnight')
    assert (row['state'], row['outcome'], row['evidence']) == (current, 'queued', [line])
    assert not vcs.calls and calls == {'check': [], 'execute': [], 'ping': []}
    assert not state.read_state(directory=root / '.wuwei/days' / DAY).get('builds')


def stale(root):
    state._write_state(lambda data: data.setdefault('watch', {}).update(
        reviews={REF: {'head': 'a' * 40, 'since': DAY + 'T00:00:00+00:00'}}), root, reserved=False,
        directory=root / '.wuwei/days' / DAY)


@pytest.mark.parametrize('code, text, outcome, exit', [
    (0, '', 'pinged', 0),
    (1, 'outward: draft D1 held for the owner', 'queued', 1),
    (2, 'review post unmeasured: timeout', 'unmeasured', 2),
])
def test_a_stale_review_is_pinged_under_the_tiers(night, monkeypatch, code, text, outcome, exit):
    root, _, _, calls = night
    stale(root)
    def ping(root, ref):
        calls['ping'].append(ref)
        print(text)
        return code
    monkeypatch.setattr(shepherd, 'post_review_request', ping)
    assert shepherd.overnight(root) == exit
    assert calls['ping'] == [REF]
    row, = events(root, 'shepherd.overnight')
    assert (row['state'], row['outcome'], row['reason']) == ('review_stale', outcome, text)


def test_an_unreadable_pr_does_not_stop_the_others(night):
    root, host, _, calls = night
    approve(host)
    other = 'acme/widget#8'
    state._write_state(lambda data: data.update(raised_prs=[REF, other]), root, reserved=False,
                       directory=root / '.wuwei/days' / DAY)
    assert shepherd.overnight(root) == 2
    rows = {row['pr']: row for row in events(root, 'shepherd.overnight')}
    assert rows[other]['outcome'] == 'unmeasured' and 'PR state unmeasured' in rows[other]['reason']
    assert rows[REF]['outcome'] == 'queued' and calls['check'] == [REF] and calls['execute'] == []


@pytest.mark.parametrize('kind', ['shepherd.overnight', 'shepherd.swept'])
def test_overnight_events_are_producer_only(case, capsys, kind):
    from wuwei.__main__ import main
    assert main(['event', kind, '{}']) == 1
    assert 'sweep obligations --headless' in capsys.readouterr().err


def test_overnight_lines_render_events_and_the_morning_queue(tmp_path, monkeypatch):
    day = tmp_path / DAY
    assert shepherd.overnight_lines(day) == []
    def add(kind, at, **payload):
        monkeypatch.setenv('WUWEI_NOW', f'{TODAY}T{at}:00+00:00')
        state.append_event(kind, payload, directory=day)
    for number, current, outcome, reason, evidence in (
            (1, 'approved', 'queued', 'merge policy: soak window has not passed', []),
            (2, 'threads_unanswered', 'queued', 'triage review threads', ['thread T1 by bob: why?']),
            (3, 'review_stale', 'pinged', '', []),
            (4, 'ci_red', 'queued', 'start a fix round', ['check tests: failure'])):
        add('shepherd.overnight', '01:00', pr=f'acme/widget#{number}', state=current, outcome=outcome,
            reason=reason, evidence=evidence)
    add('shepherd.swept', '01:00', exit=1)
    add('shepherd.overnight', '02:00', pr='acme/widget#1', state='approved', outcome='merged',
        reason='', evidence=[])
    add('shepherd.swept', '02:00', exit=1)
    lines = shepherd.overnight_lines(day)
    assert lines[0].startswith(f'## Overnight (days/{DAY}: 2 sweeps, last {TODAY}T02:00')
    assert [line.split(' ', 2)[2] for line in lines if line.startswith('- ')] == [
        'acme/widget#1 approved: queued: merge policy: soak window has not passed',
        'acme/widget#2 threads_unanswered: queued: triage review threads',
        'acme/widget#3 review_stale: pinged', 'acme/widget#4 ci_red: queued: start a fix round',
        'acme/widget#1 approved: merged']
    queue = lines[lines.index('Morning queue (first items today):') + 1:]
    assert queue == [
        '1. acme/widget#2 threads_unanswered: triage review threads. Run: bin/wuwei pr act acme/widget#2',
        '   - thread T1 by bob: why?',
        '2. acme/widget#4 ci_red: start a fix round. Run: bin/wuwei pr act acme/widget#4',
        '   - check tests: failure', '']


def test_sweep_obligations_headless_runs_one_sweep_under_the_lock(night, capsys):
    import fcntl
    from wuwei.__main__ import main
    root, host, _, calls = night
    approve(host)
    assert main(['sweep', 'obligations', '--headless']) == 1
    assert calls['check'] == [REF] and len(events(root, 'shepherd.swept')) == 1
    with (root / '.wuwei/shepherd.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert main(['sweep', 'obligations', '--headless']) == 2
    assert 'another shepherd holds the workspace lock' in capsys.readouterr().out
    assert len(events(root, 'shepherd.swept')) == 1


@pytest.fixture
def host_terminal(case, tmp_path, monkeypatch):
    from wuwei.commands import watch as watch_command
    monkeypatch.delenv('WUWEI_SESSION_ID', raising=False)
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path / 'config'))
    monkeypatch.setattr(watch_command, 'service_platform', lambda: 'linux')
    calls = []
    monkeypatch.setattr(registry, 'watch_service', lambda: SimpleNamespace(call=calls.append))
    return case[0], calls


def test_schedule_installs_the_shepherd_unit_in_a_host_terminal(host_terminal, capsys):
    from wuwei.__main__ import main
    root, calls = host_terminal
    label, path = workspace.watch_unit(root, 'linux', name='shepherd')
    assert label.startswith('wuwei-shepherd-')
    assert main(['shepherd', 'schedule', '--dry-run']) == 0
    out = capsys.readouterr().out
    assert label in out and 'bin/wuwei" shepherd\n' in out and not path.exists() and not calls
    assert main(['shepherd', 'schedule']) == 0
    assert 'bin/wuwei" shepherd\n' in path.read_text()
    assert ['systemctl', '--user', 'enable', '--now', path.name] in calls
    assert main(['shepherd', 'unschedule']) == 0
    assert not path.exists() and ['systemctl', '--user', 'disable', '--now', path.name] in calls


def posture(root, name):
    with (root / '.wuwei/config.toml').open('a') as handle:
        handle.write(f'\n[security]\nposture = "{name}"\n')


@pytest.mark.parametrize('verb', ['schedule', 'unschedule'])
@pytest.mark.parametrize('planned', [True, False])
def test_under_strict_a_session_gets_the_owner_action(host_terminal, monkeypatch, capsys, verb, planned):
    from wuwei.__main__ import main
    root, calls = host_terminal
    posture(root, 'strict')
    monkeypatch.setenv('WUWEI_SESSION_ID', 'S1')
    if planned:
        (workspace.day_dir(root) / 'plan.md').write_text('# Morning plan\n')
    assert main(['shepherd', verb, '--yes'] if verb == 'schedule' else ['shepherd', verb]) == 1
    action = json.loads(capsys.readouterr().out)
    assert action['action'] == 'owner_terminal' and action['command'] == f'bin/wuwei shepherd {verb}'
    assert action['why'] and action['then'] and 'widget' not in action
    assert not calls and not workspace.watch_unit(root, 'linux', name='shepherd')[1].exists()
    assert main(['shepherd', 'schedule', '--dry-run']) == 0
    assert 'wuwei-shepherd-' in capsys.readouterr().out


@pytest.mark.parametrize('name', ['observe', 'guarded'])
@pytest.mark.parametrize('planned', [True, False])
def test_in_a_session_the_card_answer_schedules(host_terminal, monkeypatch, capsys, name, planned):
    """Review F3: no new refusal under observe and guarded; the card's record command installs."""
    from wuwei import decision
    from wuwei.__main__ import main
    root, calls = host_terminal
    posture(root, name)
    monkeypatch.setenv('WUWEI_SESSION_ID', 'S1')
    unit = workspace.watch_unit(root, 'linux', name='shepherd')[1]
    if planned:
        (workspace.day_dir(root) / 'plan.md').write_text('# Morning plan\n')
    assert main(['shepherd', 'schedule']) == 0
    action = json.loads(capsys.readouterr().out)
    assert action['action'] == 'ask' and action['command'] == 'bin/wuwei shepherd schedule --yes'
    assert not calls and not unit.exists()
    if planned:
        widget = action['widget']
        assert widget['header'] == 'Shepherd' and widget['question'].startswith(decision.gate(root))
        assert widget['options'][0]['label'] == 'Schedule (Recommended)'
        assert widget['record'] == 'bin/wuwei shepherd schedule --yes'
        assert 'host terminal' not in json.dumps(widget)
    else:
        assert 'widget' not in action
    assert main(['shepherd', 'schedule', '--yes']) == 0
    assert unit.exists() and ['systemctl', '--user', 'enable', '--now', unit.name] in calls
    assert main(['shepherd', 'unschedule']) == 0
    assert not unit.exists()


def test_the_loop_sweeps_every_fifteen_minutes_under_its_own_lock(case, monkeypatch):
    from wuwei import watch
    root, _, _ = case
    served = []
    monkeypatch.setattr(watch, 'serve', lambda root, name, tick, delay, *, once=False: served.append(
        (root, name, tick, delay, once)) or 0)
    assert shepherd.loop(root) == 0 and shepherd.loop(root, once=True) == 0
    assert served == [(root, 'shepherd', shepherd.overnight, 900, False),
                      (root, 'shepherd', shepherd.overnight, 0, True)]
