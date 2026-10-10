"""#551: the hook-routed day driven only by wuwei next --json; the planner never picks the order."""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
import re
import shlex
import sys
import time

import pytest

from wuwei import metrics, workspace
from wuwei.__main__ import main


def prepare(day, skip=()):
    """The walking day's workspace: the planner session, a calibrated repository, the item
    worktree stub and every setup question but those in skip answered on an earlier day."""
    day.patch.setenv('WUWEI_SESSION_ID', 'planner')
    (day.root / '.wuwei/calibration.json').write_text('{"acme/widget": {"date": "2026-09-29"}}\n')

    def worktree(repo, branch, path, root, vcs, identity=None, existing=False):
        # The VCS boundary: the item worktree is the fixture repository the fakes check.
        path.parent.mkdir(exist_ok=True)
        path.symlink_to(day.repo)
        return {'path': str(path), 'branch': branch}
    day.patch.setattr(workspace, 'create_worktree', worktree)
    # Not the first day: the calibration questions were answered on an earlier one (#530 asks
    # them any day until answered).
    from wuwei import interview
    (day.root / '.wuwei/days/2026-09-28').mkdir(parents=True)
    (day.root / '.wuwei/days/2026-09-28/interview.json').write_text(json.dumps(
        {row['id']: {'acme/widget': ''} if row['scope'] == 'repo' else '' for row in interview.QUESTIONS
         if row['id'] not in skip}))
    return day


@pytest.fixture
def day(tmp_path, monkeypatch):
    from fakes.day import Day
    return prepare(Day(tmp_path / 'workspace', monkeypatch, solo=True))


def call(day, argv, stdin=''):
    out, err = io.StringIO(), io.StringIO()
    with day.patch.context() as patch, redirect_stdout(out), redirect_stderr(err):
        patch.setattr(sys, 'stdin', io.StringIO(stdin))
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


def bash(day, command):
    """The planner's Bash call: PreToolUse, the command, then the PostToolUse span."""
    argv = shlex.split(command)
    assert argv[0] == 'wuwei', command
    day.bash(argv[1:])
    code, out, err = call(day, argv[1:])
    assert code in (0, 1), (command, code, out, err)
    day.hook('PostToolUse', tool_name='Bash', tool_input={'command': command})
    return out


def launch(day, action):
    if action['agent_type'].startswith('wuwei:sentinel-'):
        # Quality asks for one fix in the initial round; every other verdict passes.
        initial = action['action'] == 'launch'
        if not initial:  # #567: a light fix is re-read by the same seat, never a delta review
            light = day.data['items']['A']['gates']['tier'] == 'light'
            assert action['feedback'].startswith('Re-read:' if light else 'Delta review:'), action
        day.runtime.verdict = 'FIX' if initial and action['agent_type'] == 'wuwei:sentinel-quality' else 'PASS'
    day.execute(action)


def walk(day, card, after=None, looks=1):
    """Walk wuwei next until done: card(day, action) answers a card row, after(day, action)
    runs after each action; each turn ends with a Stop. Returns the last action."""
    for _ in range(80):
        for _ in range(looks):
            action = json.loads(bash(day, 'wuwei next --json'))
        kind = action['action']
        if kind == 'done':
            return action
        assert kind != 'card' or action.get('widget'), action  # an owner-only card stops the day
        if kind in ('run', 'check'):
            bash(day, action['command'])
        elif kind in ('launch', 'continue'):
            launch(day, action)
            if action['state'] == 'lead':  # its then: save the lead's JSON answer with Write
                (day.directory / 'lead.json').write_text(json.dumps(day.proposal(['A'])))
        elif kind == 'card':
            card(day, action)
        elif kind in ('set', 'gates'):
            for entry in action.get('entries', [action]):
                for command in entry.get('commands', []):
                    bash(day, command)
                for seat in entry.get('seats', []) + ([entry] if entry.get('agent_type') else []):
                    launch(day, seat)
        else:
            assert kind == 'wait', action
        if after:
            after(day, action)
        # The turn ends; a Stop the close guard blocks is the guard doing its job.
        call(day, ['hook', 'Stop'], json.dumps({
            'session_id': 'planner', 'cwd': str(day.root), 'hook_event_name': 'Stop',
            'transcript_path': str(day.root / 'planner.jsonl'), 'stop_hook_active': False}))
    pytest.fail(f'the day did not close: {action}')


@pytest.mark.xdist_group('timing')
@pytest.mark.parametrize('looks,tier', [(1, 'standard'), (2, 'standard'), (1, 'light')])
def test_the_day_closes_walking_only_next(day, looks, tier):
    if tier == 'light':  # #567: the repository floor and the lead allow light
        from functools import partial
        with (day.root / '.wuwei/config.toml').open('a') as config:
            config.write('[repos.gates]\nfloor = "light"\n')
        day.proposal = partial(day.proposal, tier='light')
        day.runtime.spec = False  # no spec engine at light (#280)
    # looks 2: the planner asks next again before each action; asking is not doing (#551 review).
    started, asks, merged = time.monotonic(), [], []

    def card(day, action):
        for widget in action['widget']:
            bash(day, widget['record'].replace('<label>', widget['options'][0]['label']))
            day.hook('PostToolUse', tool_name='AskUserQuestion', tool_input={'questions': [widget]})
            asks.append(widget)

    def after(day, action):
        if action['state'] == 'pr' and not merged:
            # The code host merges; the watch records it with pr state.
            day.host.results['pr'].data.update(state='closed', merged=True,
                                               merged_at='2026-09-29T12:00:00Z', merge_commit=day.head)
            assert call(day, ['pr', 'state'])[0] == 0
            merged.append(True)
    walk(day, card, after, looks)
    assert day.data['items']['A']['phase'] == 'merged'
    assert any(row['kind'] == 'day.closed' for row in day.events)
    assert (day.directory / 'report.md').is_file()
    assert (day.directory / 'retro' / f'{day.directory.name}.md').is_file()
    for command in (('doctor', '--section', 'pr-flow'), ('mcp', 'check'), ('promote',)):
        assert command in day.calls, command
    value = metrics.collect(day.root)
    assert value['off_path'] == 0, metrics.path(metrics._events(day.directory),
                                                metrics._traces(day.directory), 'planner')
    assert value['planner_asks'] == len(asks) and value['planner_turns'] > 0
    assert value['cycle_minutes']['A'] >= 0
    assert value['cycle_by_tier'][tier]['median_minutes'] < metrics.CYCLE_TARGETS[tier]
    assert day.data['items']['A']['gates']['tier'] == tier
    builder = next(row['payload']['path'] for row in day.events if row['kind'] == 'brief written'
                   and row['payload']['role'] == 'builder')
    assert f'Depth: {tier};' in (day.root / builder).read_text()
    assert time.monotonic() - started < 60


def ask(day, widget, label):
    """The planner's card: the owner's answer reaches the hook first (#529), then the record."""
    day.hook('PostToolUse', tool_name='AskUserQuestion', tool_input={'questions': [widget]},
             tool_response={'answers': {widget['question']: label}})
    return bash(day, widget['record'].replace('<label>', label).removeprefix('bin/'))


def held(day, payload, label):
    """A held call: its card from the reason, answered with label, then the same call passes."""
    reason = day.hook('PreToolUse', 2, **payload)
    command = re.search(r'bin/(wuwei (?:decision show D-\d+|drafts show draft-[0-9a-f]{32}))', reason)
    assert command, reason
    [widget] = json.loads(bash(day, command[1] + ' --widget'))
    ask(day, widget, label)
    day.hook('PreToolUse', 0, **payload)
    return command[1].split()[-1]


HEAD = {'protection': {'required_checks': [{'name': 'tests', 'app_id': 1}], 'approvals': 1, 'strict': True,
                       'merge_queue': False, 'require_code_owner_reviews': False, 'require_last_push_approval': False,
                       'dismiss_stale_reviews': True, 'conversation_resolution': True, 'enforce_admins': True,
                       'squash': True},
        'files': [{'path': 'memory/demo.py', 'previous_path': None, 'status': 'modified', 'additions': 1,
                   'deletions': 1, 'patch': '@@ -1 +1 @@\n-VALUE = 0\n+VALUE = 2\n'}],
        'history': {'files': [], 'commits': []}}


def approve_at_head(day):
    """The reviewer approves at the head and the required check is green (tests/test_merge.py)."""
    from wuwei.registry import Result
    head = day.head
    day.host.results.update({key: Result(0, value) for key, value in HEAD.items()})
    day.host.results.update(
        reviews=Result(0, [{'id': 1, 'author': 'reviewer', 'is_bot': False, 'sha': head, 'state': 'approved',
                            'body': '', 'submitted_at': '2026-09-29T11:00:00Z'}]),
        checks=Result(0, [{'name': 'tests', 'sha': head, 'app_id': 1, 'state': 'completed', 'conclusion': 'success'}]),
        merge=Result(0, {'accepted': True, 'sha': head}))
    day.host.results['pr'].data.update(additions=1, deletions=1, changed_files=1)


@pytest.mark.xdist_group('timing')
@pytest.mark.parametrize('choice', ['Autonomous', 'Supervised'])
def test_posture_day(tmp_path, monkeypatch, choice):
    # #530 E: a whole day under the setup answer. Under autonomous the owner answers the gate and
    # one client draft; under supervised every owner-only action asks on a card.
    from fakes.day import Day
    from test_decision_classes import LEAD, record
    from wuwei import interview, workspace
    started, answered, steps, routes = time.monotonic(), [], set(), {}
    autonomous = choice == 'Autonomous'
    day = prepare(Day(tmp_path / 'workspace', monkeypatch), skip={'autonomy'})
    # Spec mode runs advisory under observe (design 5.10): no spec-first refusal to meet.
    day.runtime.spec = not autonomous
    path = day.root / '.wuwei/config.toml'
    path.write_text(path.read_text().replace('fast_checks = ["demo-check"]\n',
                                             'fast_checks = ["demo-check"]\nmerge_deploys = false\n')
                    + '[outbound]\nchannel_classes = {C0CLIENT = "client"}\n[deploy]\nworkflows = ["deploy.yml"]\n')

    def card(day, action):
        for widget in action['widget']:
            labels = [option['label'] for option in widget['options']]
            label = (choice if action['state'] == 'calibrate' else
                     next((name for name in labels if name.startswith('Allow')), None)
                     or next((name for name in labels if 'Recommended' in name), labels[0]))
            if action['state'] == 'calibrate':
                autonomy = next(row for row in interview.QUESTIONS if row['id'] == 'autonomy')
                assert widget['header'] == autonomy['header'] and choice in labels, widget
            ask(day, widget, label)
            answered.append((action['state'], action.get('item'), widget['header'], label))

    def planner(**fields):
        return {'session_id': 'planner', 'cwd': str(day.root), 'transcript_path': str(day.root / 'planner.jsonl'),
                'hook_event_name': 'PreToolUse', **fields}

    def after(day, action):
        phase = day.data['items'].get('A', {}).get('phase')
        if phase in ('fix', 'delta', 'raised') and 'records' not in steps:
            steps.add('records')
            decisions = day.directory / 'decisions'
            for name, text in (('routine', record(cls='retry', door='unsure', radius='item A')),
                               ('consequential', record(radius='outside')),
                               ('exploratory', record(radius='item A', wants=LEAD))):
                ident = f'D-{len(list(decisions.glob("D-*.md"))) + 1}'
                (decisions / f'{ident}.md').write_text(text)
                routes[name] = (ident, bash(day, f'wuwei decision route {ident}').splitlines()[0])
        if action['state'] == 'pr' and 'ping' not in steps:
            steps.add('ping')
            bash(day, f'wuwei pr ping-check {day.ref}')
            bash(day, f'wuwei pr ping {day.ref}')
            if not any(row['status'] == 'posted' for row in day.data.get('channel_posts', [])):
                pending = [key for key, row in day.data.get('drafts', {}).items() if row['status'] == 'pending']
                [widget] = json.loads(bash(day, f'wuwei drafts show {pending[0]} --widget'))
                ask(day, widget, 'Send now')
                bash(day, f'wuwei pr ping {day.ref}')
            approve_at_head(day)
            steps.add(held(day, planner(tool_name='mcp__slack__post_message',
                                        tool_input={'channel': 'C0CLIENT', 'text': 'The fix ships today.'}),
                           'Send now'))
        if any(row[0] == 'merge' for row in day.host.calls) and 'merged' not in steps:
            steps.add('merged')
            day.host.results['pr'].data.update(state='closed', merged=True,
                                               merged_at='2026-09-29T12:00:00Z', merge_commit=day.head)
            assert call(day, ['pr', 'state'])[0] == 0
            if not autonomous:  # a deploy is a publish target: a card under both answers (I18)
                steps.add(held(day, planner(tool_name='Bash', tool_input={
                    'command': 'gh workflow run deploy.yml -R acme/widget'}), 'Allow once'))
    walk(day, card, after)

    data, events = day.data, day.events
    kinds = [row['kind'] for row in events]
    assert workspace.load_config(day.root)['autonomy']['mode'] == choice.lower()
    assert data['items']['A']['phase'] == 'merged' and 'day.closed' in kinds
    assert [row[1] for row in day.host.calls if row[0] == 'merge'] == [(day.ref, day.head)]
    for row in events:
        if row['kind'] == 'hook.refusal':
            reason = row['payload']['reason']
            assert 'specify first' in reason or re.search(r'bin/wuwei (?:decision show D-|drafts show draft-)', reason), reason
    grants = {(row['kind'], row['payload'].get('action')) for row in events if row['kind'].startswith('grant.')}
    report = (day.directory / 'report.md').read_text()
    if autonomous:
        extra = [f"{ident}: {row['cisr']}, grant {data.get('grants', {}).get(ident, {}).get('action')}"
                 for ident, row in data.get('decision_routes', {}).items()]
        assert not extra, extra
        assert sorted({state for state, *_ in answered}) == ['calibrate', 'gate']
        assert [(state, header) for state, _, header, _ in answered if state == 'calibrate'] == [('calibrate', 'Autonomy')]
        assert [row['destination'] for row in data['drafts'].values()] == ['C0CLIENT'], data['drafts']
        assert {name: verdict for name, (_, verdict) in routes.items()} == dict.fromkeys(
            ('routine', 'consequential', 'exploratory'), 'mandate')
        used = [row['payload'] for row in events if row['kind'] == 'grant.used']
        assert [(row['decision'], row['action']) for row in used] == [('merge.default_tier', 'merge')]
        assert 'grant.asked' not in kinds
        mandate = report[report.index('## Taken under mandate'):]
        mandate = mandate[:mandate.index('\n## ', 3)]
        lines = [line for line in mandate.splitlines() if line.startswith('- ')]
        assert lines[0].startswith(f"- {routes['consequential'][0]}"), mandate
        for ident, _ in routes.values():
            line = next(line for line in lines if line.startswith(f'- {ident}'))
            assert f'decisions/{ident}.md' in line and f'reverse: bin/wuwei decide {ident}' in line, line
        assert 'merge' in report[report.index('## Grants'):].split('\n## ', 1)[0]
    else:
        assert {('grant.asked', 'merge'), ('grant.asked', 'deploy')} <= grants, grants
        cisr = {row.get('cisr') for row in data['decision_routes'].values()}
        assert {'Consequential', 'Exploratory'} <= cisr, data['decision_routes']
        assert any(row['destination'] == 'C0CLIENT' for row in data['drafts'].values())
        assert {'merged'} <= steps and any(step.startswith('D-') for step in steps)
    assert time.monotonic() - started < 60


class Reached(Exception):
    pass


def test_fresh_day_goals_reach_an_approved_plan(day):
    # #603: a fresh day's proposed goals approve at the gate, then the goals row records them.
    from test_plan import LEAD_GOALS, TEMPLATE
    (day.root / '.wuwei/memory/goals.md').write_text(TEMPLATE.read_text(encoding='utf-8'))
    propose = day.proposal
    day.proposal = lambda *args, **kwargs: {**propose(*args, **kwargs), 'goals': LEAD_GOALS}

    def card(day, action):
        for widget in action['widget']:
            ask(day, widget, widget['options'][0]['label'])

    def after(day, action):
        if day.data.get('gate_approved'):
            raise Reached
    with pytest.raises(Reached):
        walk(day, card, after)
    action = json.loads(bash(day, 'wuwei next --json'))
    assert (action['state'], action['command']) == (
        'goals', f'wuwei goals edit --file .wuwei/days/{day.directory.name}/goals.md'), action
    from wuwei import registry
    from wuwei.registry import Result
    # The owner commit is the VCS boundary; the fixture workspace memory is not a repository.
    day.patch.setattr(registry.load('vcs', None), 'workspace_owner_commit', lambda *args, **kwargs: Result(0),
                      raising=False)
    bash(day, action['command'])
    assert '## G-2' in (day.root / '.wuwei/memory/goals.md').read_text()


def test_multi_repository_dispatch_runs(day):
    # #603: with two repositories every start command next returns exits 0 and names --repo.
    from wuwei import interview
    with (day.root / '.wuwei/config.toml').open('a') as config:
        config.write('[[repos]]\nname = "acme/other"\npath = "other"\ndefault_branch = "main"\n')
    (day.root / 'other').mkdir()
    (day.root / '.wuwei/days/2026-09-28/interview.json').write_text(json.dumps(
        {row['id']: dict.fromkeys(('acme/widget', 'acme/other'), '') if row['scope'] == 'repo' else ''
         for row in interview.QUESTIONS}))
    propose = day.proposal

    def proposal(*args, **kwargs):
        value = propose(*args, **kwargs)
        for row in value['candidates']:
            row['repo'] = 'acme/widget'
        return value
    day.proposal = proposal
    started = []

    def card(day, action):
        for widget in action['widget']:
            ask(day, widget, widget['options'][0]['label'])

    def after(day, action):
        if action['action'] == 'set':
            started.extend(command for entry in action['entries'] for command in entry.get('commands', []))
            if started:
                raise Reached
    with pytest.raises(Reached):
        walk(day, card, after)
    assert 'wuwei worktree add A --repo acme/widget' in started, started
