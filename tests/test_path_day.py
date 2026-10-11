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
from wuwei.commands.next import THEN


def prepare(day):
    """The walking day's workspace: the planner session, a calibrated repository and the item
    worktree stub."""
    day.patch.setenv('WUWEI_SESSION_ID', 'planner')
    (day.root / '.wuwei/calibration.json').write_text('{"acme/widget": {"date": "2026-09-29"}}\n')

    def worktree(repo, branch, path, root, vcs, **kwargs):
        # The VCS boundary: the item worktree is the fixture repository the fakes check.
        path.parent.mkdir(exist_ok=True)
        path.symlink_to(day.repo)
        return {'path': str(path), 'branch': branch}
    day.patch.setattr(workspace, 'create_worktree', worktree)
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
        quality = getattr(day, 'quality', 'FIX')  # part 14: ESCALATE asks the owner on dispatch next's card
        day.runtime.verdict = quality if initial and action['agent_type'] == 'wuwei:sentinel-quality' else 'PASS'
    day.execute(action)


def owner_step(day, command):
    """Run a command; when it prints an Owner step card the owner answers Yes and it runs again."""
    out = bash(day, command)
    if 'Owner step' in out or '"card"' in out:
        from fakes.owner import answer_card
        answer_card(day.root, out, session='planner')
        out = bash(day, command)
    return out


def launched(action, kind):
    return any(entry['kind'] == kind for entry in action.get('launches', ()))


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
            out = bash(day, action['command'])
            if action['then'] == THEN['owner-step'] and '"card"' in out:  # the owner answers the card
                from fakes.owner import answer_card
                answer_card(day.root, out, session='planner')
                bash(day, action['command'])
        elif kind in ('launch', 'continue'):
            launch(day, action)
            if action['state'] == 'lead':  # its then: save the lead's JSON answer with Write
                (day.directory / 'lead.json').write_text(json.dumps(day.proposal(['A'])))
        elif kind == 'card':
            card(day, action)
        elif kind == 'set':  # #844: every launch and duty, then the one decision
            for entry in action['launches']:
                if entry['action'] in ('run', 'check', 'polish') and entry.get('command'):
                    owner_step(day, entry['command'])
                for command in entry.get('commands', []):
                    bash(day, command)
                for seat in entry.get('seats', []) + ([entry] if entry.get('agent_type') else []):
                    launch(day, seat)
            for duty in action['duties']:
                bash(day, duty['record'].replace('<link>', 'https://chat.example/p1'))
            if action['decision']:
                owner_step(day, action['decision']['command'])
        else:
            assert kind == 'wait', action
        if after:
            after(day, action)
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
        if launched(action, 'pr') and not merged:
            # The code host merges; pr state records it.
            day.host.results['pr'].data.update(state='closed', merged=True,
                                               merged_at='2026-09-29T12:00:00Z', merge_commit=day.head)
            assert call(day, ['pr', 'state'])[0] == 0
            merged.append(True)
    walk(day, card, after, looks)
    assert day.data['items']['A']['phase'] == 'merged'
    assert any(row['kind'] == 'day.closed' for row in day.events)
    assert (day.directory / 'report.md').is_file()
    assert (day.directory / 'retro' / f'{day.directory.name}.md').is_file()
    for command in (('doctor', '--section', 'pr-flow'), ('retro', '--promote')):
        assert command in day.calls, command
    value = metrics.collect(day.root)
    assert value['off_path'] == 0, metrics.path(metrics._events(day.directory),
                                                metrics._traces(day.directory), 'planner')
    assert value['planner_asks'] == len(asks) and 'planner_turns' not in value
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


def allowed(day, payload):
    """#838: an unlisted send: the planner runs the config set line the refusal names, the owner
    answers its Owner step card, the line is written and the same call passes."""
    from fakes.owner import answer_card
    reason = json.loads(day.hook('PreToolUse', 2, **payload))['hookSpecificOutput']['permissionDecisionReason']
    line = re.search(r"bin/(wuwei config set outward\.allow '[^']*' --add)", reason)
    assert line, reason
    argv = shlex.split(line[1])[1:]
    code, _, err = call(day, argv)
    assert code == 1 and 'Owner step: ' in err, err
    answer_card(day.root, err, session='planner')
    assert call(day, argv)[0] == 0
    day.hook('PreToolUse', 0, **payload)
    return 'allowed'


HEAD = {'protection': {'required_checks': [{'name': 'tests', 'app_id': 1}], 'approvals': 1, 'strict': True,
                       'merge_queue': False, 'require_code_owner_reviews': False, 'require_last_push_approval': False,
                       'dismiss_stale_reviews': True, 'conversation_resolution': True, 'enforce_admins': True,
                       'methods': ['squash']},
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
@pytest.mark.parametrize('posture', [False, True])
def test_enforce_day(tmp_path, monkeypatch, posture):
    # #530 E, part 14, #837: a whole day with guards.enforce false and true. The quality gate says
    # ESCALATE and the owner answers dispatch next's Owner step card; no decision record is
    # written. Log-only, the owner answers the gate, that card and one unlisted send; enforced,
    # every owner-only action asks on a card. #816: the repository's merge policy merges either way.
    from fakes.day import Day
    started, answered, steps = time.monotonic(), [], set()
    autonomous = not posture
    day = prepare(Day(tmp_path / 'workspace', monkeypatch))
    day.quality = 'ESCALATE'
    # Spec mode runs advisory with guards.enforce = false (design 5.10): no spec-first refusal.
    day.runtime.spec = not autonomous
    path = day.root / '.wuwei/config.toml'
    path.write_text(path.read_text().replace('fast_checks = ["demo-check"]\n',
                                             'fast_checks = ["demo-check"]\nmerge_deploys = false\n'
                                             'merge = {auto = true, soak_minutes = 0}\n')
                    + f'[guards]\nenforce = {str(posture).lower()}\n'
                    + '[deploy]\nworkflows = ["deploy.yml"]\n')

    def card(day, action):
        for widget in action['widget']:
            labels = [option['label'] for option in widget['options']]
            label = (next((name for name in labels if name.startswith('Allow')), None)
                     or next((name for name in labels if 'Recommended' in name), labels[0]))
            ask(day, widget, label)
            answered.append((action['state'], action.get('item'), widget['header'], label))

    def planner(**fields):
        return {'session_id': 'planner', 'cwd': str(day.root), 'transcript_path': str(day.root / 'planner.jsonl'),
                'hook_event_name': 'PreToolUse', **fields}

    def after(day, action):
        if launched(action, 'pr') and 'ping' not in steps:
            steps.add('ping')
            bash(day, f'wuwei pr ping {day.ref}')
            approve_at_head(day)
            steps.add(allowed(day, planner(tool_name='mcp__slack__post_message',
                                           tool_input={'channel': 'C0CLIENT', 'text': 'The fix ships today.'})))
        if any(row[0] == 'merge' for row in day.host.calls) and 'merged' not in steps:
            steps.add('merged')
            day.host.results['pr'].data.update(state='closed', merged=True,
                                               merged_at='2026-09-29T12:00:00Z', merge_commit=day.head)
            assert call(day, ['pr', 'state'])[0] == 0
            if not autonomous:  # a deploy is a publish target: its Owner step card (I18, #816)
                from fakes.owner import answer_card
                deploy = planner(tool_name='Bash', tool_input={'command': 'gh workflow run deploy.yml -R acme/widget'})
                refused = json.loads(day.hook('PreToolUse', 2, **deploy))['hookSpecificOutput']
                answer_card(day.root, refused['permissionDecisionReason'], session='planner')
                day.hook('PreToolUse', 0, **deploy)
                steps.add('deployed')
    walk(day, card, after)

    data, events = day.data, day.events
    kinds = [row['kind'] for row in events]
    assert workspace.load_config(day.root)['guards']['enforce'] is posture
    assert data['items']['A']['phase'] == 'merged' and 'day.closed' in kinds
    assert not list((day.directory / 'decisions').glob('D-*.md'))  # SC-002: no item writes a record
    assert [row['payload']['verdict'] for row in events if row['kind'] == 'gate.received'
            and row['payload']['role'] == 'quality'][0] == 'ESCALATE'
    fix = next(row['payload'] for row in events if row['kind'] == 'build.fix_opened')
    assert fix['item'] == 'A' and any(row['kind'] == 'gate.asked' for row in events)
    assert [row[1] for row in day.host.calls if row[0] == 'merge'] == [(day.ref, day.head, 'squash')]
    for row in events:
        if row['kind'] == 'hook.refusal':
            reason = row['payload']['reason']
            assert 'specify first' in reason or re.search(
                r"config set outward\.allow '[^']*' --add|Owner step: ", reason), reason
    assert not any(row['kind'].startswith('grant.') for row in events)
    report = (day.directory / 'report.md').read_text()
    assert 'decision_routes' not in data and '## Taken under mandate' not in report
    assert 'allowed' in steps and 'drafts' not in data
    assert workspace.load_config(day.root)['outward']['allow'] == ['mcp__slack__post_message']
    if autonomous:
        assert sorted({state for state, *_ in answered}) == ['gate']
        assert '## Grants' not in report
    else:
        assert {'merged', 'deployed'} <= steps
    assert time.monotonic() - started < 60


class Reached(Exception):
    pass


def test_fresh_day_goals_reach_an_approved_plan(day):
    # #603, #833: a fresh day's proposed goals approve at the gate, and the approval records them.
    from test_plan import LEAD_GOALS, TEMPLATE
    from wuwei import registry
    from wuwei.registry import Result
    (day.root / '.wuwei/memory/goals.md').write_text(TEMPLATE.read_text(encoding='utf-8'))
    propose = day.proposal
    day.proposal = lambda *args, **kwargs: {**propose(*args, **kwargs), 'goals': LEAD_GOALS}
    # The owner commit is the VCS boundary; the fixture workspace memory is not a repository.
    day.patch.setattr(registry.load('vcs', None), 'workspace_owner_commit', lambda *args, **kwargs: Result(0),
                      raising=False)

    def card(day, action):
        for widget in action['widget']:
            ask(day, widget, widget['options'][0]['label'])

    def after(day, action):
        if day.data.get('gate_approved'):
            raise Reached
    with pytest.raises(Reached):
        walk(day, card, after)
    assert '## G-2' in (day.root / '.wuwei/memory/goals.md').read_text()
    action = json.loads(bash(day, 'wuwei next --json'))
    assert action['state'] != 'goals', action


def test_multi_repository_dispatch_runs(day):
    # #603: with two repositories every start command next returns exits 0 and names --repo.
    with (day.root / '.wuwei/config.toml').open('a') as config:
        config.write('[[repos]]\nname = "acme/other"\npath = "other"\ndefault_branch = "main"\n')
    (day.root / 'other').mkdir()
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
            started.extend(command for entry in action['launches'] for command in entry.get('commands', []))
            if started:
                raise Reached
    with pytest.raises(Reached):
        walk(day, card, after)
    assert 'wuwei worktree add A --repo acme/widget' in started, started
