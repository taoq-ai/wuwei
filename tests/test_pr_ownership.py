"""PR ownership from fake code-host evidence, never network or cached PR state."""

from datetime import datetime
import io
import json
import sys

import pytest

from wuwei import pr_actions, registry, state, watch, workspace
from wuwei.__main__ import main
from wuwei.registry import Result
from test_stop import case, own, advance, disposition, payload, REF


@pytest.fixture(autouse=True)
def integrity_measured(case):
    from fakes.integrity import seed
    seed(case[0])


def measure(root, refs=None):
    assert hasattr(pr_actions, 'evaluate'), 'PR ownership state producer missing'
    return pr_actions.evaluate(root, refs)


def review(host, status='approved', *, body=''):
    host.results['reviews'] = Result(0, [{'id': 5, 'author': 'reviewer', 'is_bot': False,
        'state': status, 'sha': host.results['pr'].data['head'], 'body': body,
        'submitted_at': workspace.now().isoformat()}])


def thread(host, author='reviewer'):
    host.results['threads'].data['threads'] = [{'id': 'T17', 'resolved': False,
        'outdated': False, 'comments': [{'id': 3, 'author': author, 'is_bot': False,
            'body': 'Please explain', 'created_at': workspace.now().isoformat()}]}]


@pytest.mark.parametrize('condition,expected,action', [
    ('conflict', 'conflicted', 'rebase'), ('red', 'ci_red', 'fix round'),
    ('changes', 'changes_requested', 'triage'), ('thread', 'threads_unanswered', 'triage'),
    ('approval', 'approved', 'wuwei merge'), ('merged', 'merged', ''),
    ('waiting', 'waiting', ''), ('closed', 'closed', 'decision'),
])
def test_fresh_states_and_dispatch(case, condition, expected, action):
    root, host, _ = case
    own(root)
    if condition == 'conflict':
        host.results['pr'].data['mergeable'] = False
    elif condition == 'red':
        host.results['checks'] = Result(0, [{'name': 'tests', 'sha': 'a' * 40,
            'state': 'completed', 'conclusion': 'failure'}])
    elif condition in ('changes', 'approval'):
        review(host, 'changes_requested' if condition == 'changes' else 'approved')
    elif condition == 'thread':
        thread(host)
    elif condition in ('merged', 'closed'):
        host.results['pr'].data.update(state='closed', merged=condition == 'merged')
    code, rows = measure(root)
    row, = rows
    assert row['pr'] == REF and row['state'] == expected
    assert action in row['action']
    assert row['exit'] == code == int(bool(action))
    if action:
        assert row['deadline'] and row['dispatch']
    else:
        assert row['deadline'] is None
    if condition == 'conflict':
        assert row['dispatch']['steps'] == ['rebase', 'resolve', 'fast_checks', 'push']
        assert row['dispatch']['worktree'] == 'item'
    if condition in ('changes', 'thread'):
        assert row['dispatch']['routes'] == {
            'fix_request': 'fix_round', 'question': 'outbound_tier_then_reply',
            'disagreement': 'owner_decision', 'scope_change': 'owner_decision'}
    if condition == 'approval':
        assert row['dispatch']['fallback'] == 'merge_decision'
    assert {call[0] for call in host.calls} <= {'pr', 'checks', 'reviews', 'threads'}


def test_pr_action_event_carries_observed_state(case):
    root, host, _ = case
    own(root)
    host.results['pr'].data.update(state='closed', merged=True)
    measure(root)
    lines = (workspace.day_dir(root) / 'events.jsonl').read_text().splitlines()
    event = [json.loads(line) for line in lines if json.loads(line)['kind'] == 'pr.action'][-1]
    assert event['payload']['state'] == 'merged'


def test_startup_failure_is_ci_red_and_wakes_poll(case):
    root, host, _ = case
    own(root)
    assert watch.poll(root) == 0
    host.results['checks'] = Result(0, [{'name': 'tests', 'sha': 'a' * 40,
        'state': 'completed', 'conclusion': 'startup_failure'}])
    code, rows = measure(root)
    assert code == rows[0]['exit'] == 1
    assert rows[0]['state'] == 'ci_red'
    assert watch.poll(root) == 1
    assert watch.saved(root)['wake']['prs'] == [REF]
    assert watch.poll(root) == 0


def test_comment_after_our_last_reply_and_answer(case):
    root, host, _ = case
    own(root)
    thread(host, 'builder')
    assert measure(root)[1][0]['state'] == 'waiting'
    comments = host.results['threads'].data['threads'][0]['comments']
    comments.append({**comments[0], 'id': 4, 'author': 'reviewer'})
    assert measure(root)[1][0]['state'] == 'threads_unanswered'
    comments.append({**comments[0], 'id': 5})
    assert measure(root)[1][0]['state'] == 'waiting'


@pytest.mark.parametrize('change', ['error_body', 'timeout', 'unknown_mergeable',
    'bad_checks', 'bad_reviews', 'bad_threads', 'wrong_head', 'bad_merged'])
def test_unreadable_is_per_pr_exit_two(case, change):
    root, host, _ = case
    own(root)
    if change == 'error_body':
        host.results['pr'] = Result(0, {'message': 'API error', 'documentation_url': 'docs'})
    elif change == 'timeout':
        host.results['pr'] = Result(2, None, 'timeout')
    elif change == 'unknown_mergeable':
        host.results['pr'].data['mergeable'] = None
    elif change == 'bad_merged':
        host.results['pr'].data['merged'] = 'true'
    elif change == 'wrong_head':
        host.results['checks'] = Result(0, [{'name': 'tests', 'sha': 'b' * 40,
            'state': 'completed', 'conclusion': 'success'}])
    else:
        host.results[change.removeprefix('bad_')] = Result(0, {'error': 'unreadable'})
    code, rows = measure(root)
    assert code == rows[0]['exit'] == 2
    assert rows[0]['pr'] == REF and rows[0]['reason']


def test_cli_union_filter_and_partial_failure(case, monkeypatch, capsys):
    root, host, _ = case
    own(root)
    other = 'acme/widget#8'
    state._write_state(lambda data: data.update(claimed_prs=[REF, other]), root, reserved=False)
    original = host.pr
    def read(ref, root=None):
        return Result(2, None, 'API unavailable') if ref == REF else Result(0,
            {**original(ref, root=root).data, 'number': 8, 'state': 'closed', 'merged': True})
    monkeypatch.setattr(host, 'pr', read)
    assert main(['pr', 'state']) == 2
    rows = json.loads(capsys.readouterr().out)
    assert [(r['pr'], r['exit']) for r in rows] == [(REF, 2), (other, 0)]
    assert main(['pr', 'state', other]) == 0
    assert len(json.loads(capsys.readouterr().out)) == 1
    assert main(['pr', 'state', 'acme/widget#9']) == 2


def test_review_window_and_config(case, monkeypatch):
    root, host, _ = case
    own(root)
    config = workspace.load_config(root)['pr']
    assert config['action_minutes'] == 30 and config['review_window'] == 120
    with (root / '.wuwei/config.toml').open('a') as stream:
        stream.write('\n[pr]\nreview_window=5\naction_minutes=10\n')
    assert measure(root)[1][0]['state'] == 'waiting'
    advance(monkeypatch, 301)
    row = measure(root)[1][0]
    assert row['state'] == 'review_stale'
    assert row['dispatch']['steps'] == ['request_reviewers', 'post_review_channel']
    assert (workspace.now() - datetime.fromisoformat(row['deadline'])).total_seconds() == -600


@pytest.mark.parametrize('key', ['action_minutes', 'review_window'])
@pytest.mark.parametrize('value', ['0', '-1', 'true', '"30"'])
def test_timing_config_rejects_invalid(case, key, value):
    root, _, _ = case
    with (root / '.wuwei/config.toml').open('a') as stream:
        stream.write(f'\n[pr]\n{key}={value}\n')
    with pytest.raises(ValueError):
        workspace.load_config(root)


@pytest.mark.parametrize('seconds,blocked,tier', [(1799, False, 'silent'),
    (1800, False, 'silent'), (1801, True, 'nudge'), (3599, True, 'nudge'), (3600, True, 'page')])
def test_poll_produces_deadline_stop_and_signal(case, monkeypatch, seconds, blocked, tier):
    from wuwei.guards.stop import check
    from wuwei.signal import classify
    root, host, _ = case
    own(root)
    host.results['pr'].data['mergeable'] = False
    assert watch.poll(root) == 0
    assert REF in watch.saved(root).get('actions', {}), 'poll did not produce conflict action'
    deadline = watch.saved(root)['actions'][REF]['deadline']
    advance(monkeypatch, seconds)
    watch.poll(root)
    code, reason = check(payload(root, stop_hook_active=False))
    assert code == int(blocked), reason
    if blocked:
        assert REF in reason and 'conflicted' in reason and 'rebase' in reason
    assert watch.saved(root)['actions'][REF]['deadline'] == deadline
    events = watch.records(workspace.day_dir(root) / 'events.jsonl')
    signals = [classify(row, {})[0] for row in events if row['kind'] == 'pr.action']
    assert tier in signals
    assert signals.count('page') <= 1 and signals.count('nudge') <= 1
    watch.poll(root)
    later = watch.records(workspace.day_dir(root) / 'events.jsonl')
    assert sum(classify(row, {})[0] != 'silent' for row in later if row['kind'] == 'pr.action') == sum(
        value != 'silent' for value in signals)


def test_poll_classification_failure_preserves_change_wake(case, capsys):
    root, host, _ = case
    own(root)
    host.results['pr'].data['mergeable'] = False
    assert watch.poll(root) == 0
    actions = watch.saved(root)['actions']
    host.results['pr'].data.update(head='b' * 40, mergeable=None)
    assert watch.poll(root) == 2
    events = watch.records(workspace.day_dir(root) / 'events.jsonl')
    changed = [row for row in events if row['kind'] == 'pr.changed']
    assert len(changed) == 1
    assert changed[0]['payload']['pr'] == REF
    assert changed[0]['payload']['fields'] == ['head', 'mergeable']
    assert watch.saved(root)['wake']['prs'] == [REF]
    assert watch.saved(root)['prs'][REF] == watch.snapshot(host, REF, root)
    assert watch.saved(root)['actions'] == actions
    assert 'mergeability unmeasured' in capsys.readouterr().out
    assert watch.poll(root) == 2
    events = watch.records(workspace.day_dir(root) / 'events.jsonl')
    assert sum(row['kind'] == 'pr.changed' for row in events) == 1


def test_deadline_survives_churn_failure_and_recurs_after_resolution(case, monkeypatch):
    root, host, _ = case
    own(root)
    host.results['pr'].data['mergeable'] = False
    first = measure(root)[1][0]['deadline']
    advance(monkeypatch, 1801)
    host.results['pr'].data.update(head='c' * 40, updated_at=workspace.now().isoformat())
    assert measure(root)[1][0]['deadline'] == first
    good = host.results['pr']
    host.results['pr'] = Result(2, None, 'timeout')
    assert measure(root)[0] == 2
    assert watch.saved(root)['actions'][REF]['deadline'] == first
    host.results['pr'] = good
    host.results['pr'].data['mergeable'] = True
    assert measure(root)[1][0]['state'] == 'waiting'
    assert REF not in watch.saved(root)['actions']
    host.results['pr'].data['mergeable'] = False
    assert measure(root)[1][0]['deadline'] > first


def test_parked_conflict_is_exempt_but_carried_is_not(case, monkeypatch):
    from wuwei.guards.stop import check
    root, host, _ = case
    own(root)
    host.results['pr'].data['mergeable'] = False
    measure(root)
    assert disposition(case) == 0
    advance(monkeypatch, 3601)
    assert check(payload(root)) == (0, '')
    assert measure(root)[1][0]['parked'] is True
    assert disposition(case, 'carried') == 0
    assert check(payload(root))[0] == 1
    host.results['threads'].data['comments'][0]['author'] = 'seat'
    assert check(payload(root))[0] == 2


def test_review_window_does_not_slide_on_comment_churn(case, monkeypatch):
    root, host, _ = case
    own(root)
    measure(root)
    advance(monkeypatch, 7201)
    host.results['pr'].data['updated_at'] = workspace.now().isoformat()
    assert measure(root)[1][0]['state'] == 'review_stale'
    host.results['pr'].data['head'] = 'b' * 40
    assert measure(root)[1][0]['state'] == 'waiting'


def test_stop_reads_fresh_and_completes_without_poll(case, monkeypatch):
    from wuwei.guards.stop import check
    root, host, _ = case
    own(root)
    host.results['pr'].data['mergeable'] = False
    assert check(payload(root))[0] == 0
    advance(monkeypatch, 1801)
    assert check(payload(root))[0] == 1
    host.results['pr'].data['mergeable'] = True
    assert check(payload(root))[0] == 0
    assert not watch.saved(root)['actions']


@pytest.mark.parametrize('command', ['python3 -m pytest -q', 'for f in *; do echo "$f"; done', 'export X=1'])
def test_unrelated_shell_remains_unblocked(case, monkeypatch, capsys, command):
    root, _, _ = case
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps({**payload(root),
        'hook_event_name': 'PreToolUse', 'tool_name': 'Bash', 'tool_input': {'command': command}})))
    assert main(['hook', 'PreToolUse']) == 0


def test_stop_outside_scope_and_other_session(case, monkeypatch):
    from wuwei.guards.stop import check
    root, host, _ = case
    own(root)
    host.results['pr'].data['mergeable'] = False
    measure(root)
    advance(monkeypatch, 1801)
    assert check(payload(root.parent)) == (0, '')
    assert check(payload(root, session_id='builder')) == (0, '')


def test_next_day_does_not_inherit_action_deadline(case, monkeypatch):
    root, host, _ = case
    own(root)
    host.results['pr'].data['mergeable'] = False
    first = measure(root)[1][0]['deadline']
    advance(monkeypatch, 86400)
    own(root)
    assert measure(root)[1][0]['deadline'] > first


@pytest.mark.parametrize('change', ['bad_deadline', 'bad_state', 'bad_actions', 'future_review'])
def test_corrupt_ledgers_fail_closed_without_repair(case, change):
    root, host, _ = case
    own(root)
    host.results['pr'].data['mergeable'] = False
    measure(root)
    def corrupt(data):
        value = data['watch']
        if change == 'bad_deadline':
            value['actions'][REF]['deadline'] = 'bad'
        elif change == 'bad_state':
            value['actions'][REF]['state'] = 'nonsense'
        elif change == 'bad_actions':
            value['actions'] = []
        else:
            value['reviews'][REF]['since'] = '2099-01-01T00:00:00Z'
    state._write_state(corrupt, root, reserved=False)
    assert measure(root)[0] == 2


@pytest.mark.parametrize('path', ['watch.actions', 'watch.reviews', 'pr_dispositions'])
def test_action_and_parking_state_reserved(case, path):
    assert main(['state', 'set', path, '{}']) == 1


@pytest.mark.parametrize('kind', ['pr.action', 'pr.action.reset', 'pr.disposition',
                                  'pr.action.done', 'pr.reply.drafted', 'pr.action.decision',
                                  'build.fix_opened'])
def test_action_events_reserved(case, kind):
    assert main(['event', kind, '{"tier":"silent"}']) == 1


@pytest.mark.parametrize('command,expected', [
    ("curl -X POST https://api.github.com/repos/o/r/issues/1/comments "
     "-d '{\"body\":\"WUWEI parked x\"}'", 2),
    ('''wget --post-data='{"body":"WUWEI carried x"}' https://api.github.com/repos/o/r/issues/1/comments''', 2),
    ("python -c 'print(\"WUWEI parked x\")'", 2),
    ("node -e 'console.log(\"WUWEI carried x\")'", 2),
    ("sh -c 'echo WUWEI parked x'", 2),
    ("gh pr list; echo 'WUWEI parked x'", 2),
    ("echo 'WUWEI parked x' | gh pr list", 2),
    ("echo 'WUWEI parked' | gh pr comment 1 --body-file -", 2),
    ("gh pr list --search 'WUWEI parked in:comments'", 0),
    ("gh search issues 'WUWEI carried'", 0),
    ('gh api repos/o/r/issues/1/comments', 0),
    ("gh api repos/o/r/issues/1/comments --jq 'map(select(.body == \"WUWEI parked x\"))'", 0),
    ("gh api repos/o/r/issues/1/comments -XGET --header 'X-Query: WUWEI carried x'", 0),
    *[(f"gh {form} {flag} 'WUWEI'' parked x'", 2)
      for form, flag in [
          ('pr comment 1', '--body'), ('pr create', '--title'),
          ('pr edit 1', '--body'), ('pr review 1 --comment', '--body'),
          ('pr merge 1', '--subject'), ('issue comment 1', '--body'),
          ('issue create', '--title'), ('issue edit 1', '--body'),
          ('release create v1', '--notes'), ('release edit v1', '--notes'),
          ('-R o/r pr comment 1', '--body'),
      ]],
    *[(f"gh api repos/o/r/issues/1/comments {option}", 2) for option in [
        "-f body='WUWEI'' carried x'", "-Fbody='WUWEI'' carried x'",
        "--field body='WUWEI'' carried x'", "--raw-field=body='WUWEI'' carried x'",
        "--input 'WUWEI'' carried x'", "-X POST --header 'WUWEI'' carried x'",
        "-XPATCH --header 'WUWEI'' carried x'", "--method PUT --header 'WUWEI'' carried x'",
        "--method=DELETE --header 'WUWEI'' carried x'",
    ]],
])
def test_disposition_argv_only_blocks_text_writes(case, monkeypatch, capsys, command, expected):
    root, _, _ = case
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps({**payload(root),
        'hook_event_name': 'PreToolUse', 'tool_name': 'Bash',
        'tool_input': {'command': command}})))
    assert main(['hook', 'PreToolUse']) == expected
    if expected:
        reason = ('cannot inspect outbound stdin' if command.endswith('--body-file -')
                  else 'owner disposition')
        assert reason in capsys.readouterr().out


@pytest.mark.parametrize('kind', ['parked', 'carried'])
@pytest.mark.parametrize('command', [
    "gh pr comment 7 -R acme/widget --body 'WUWEI'' {kind} acme/widget#7 D-1 X'",
    r'gh pr comment 7 -R acme/widget --body WUWEI\ {kind}\ acme/widget#7',
    "gh api repos/acme/widget/issues/7/comments -f body='WUWEI'' {kind} x'",
])
def test_shell_parsed_body_cannot_forge_disposition(case, monkeypatch, capsys, kind, command):
    root, _, _ = case
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps({**payload(root),
        'hook_event_name': 'PreToolUse', 'tool_name': 'Bash',
        'tool_input': {'command': command.format(kind=kind)}})))
    assert main(['hook', 'PreToolUse']) == 2
    result = json.loads(capsys.readouterr().out)['hookSpecificOutput']
    assert 'owner disposition' in result['permissionDecisionReason']


@pytest.mark.parametrize('kind', ['parked', 'carried'])
@pytest.mark.parametrize('option', ['--body-file body.txt', '--body-file=body.txt', '-Fbody.txt',
    '--api-input', '--api-field'])
def test_existing_body_file_cannot_forge_disposition(case, monkeypatch, capsys, kind, option):
    root, _, _ = case
    marker = f'WUWEI {kind} {REF} D-1 {workspace.day_dir(root).name} ' + 'a' * 64
    text = json.dumps({'body': marker}) if option == '--api-input' else marker
    (root / 'body.txt').write_text(text)
    if option == '--api-input':
        command = 'gh api repos/acme/widget/issues/7/comments --method POST --input body.txt'
    elif option == '--api-field':
        command = 'gh api repos/acme/widget/issues/7/comments -F body=@body.txt'
    else:
        command = 'gh pr comment 7 -R acme/widget ' + option
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps({**payload(root),
        'hook_event_name': 'PreToolUse', 'tool_name': 'Bash', 'tool_input': {'command': command}})))
    assert main(['hook', 'PreToolUse']) == 2
    result = json.loads(capsys.readouterr().out)['hookSpecificOutput']
    assert 'owner disposition' in result['permissionDecisionReason']


def test_missing_body_file_is_unreadable_but_outside_scope_passes(case, monkeypatch, capsys):
    root, _, _ = case
    command = 'gh pr comment 7 -R acme/widget --body-file absent.txt'
    for cwd, expected in ((root, 2), (root.parent, 0)):
        monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps({**payload(cwd),
            'hook_event_name': 'PreToolUse', 'tool_name': 'Bash', 'tool_input': {'command': command}})))
        assert main(['hook', 'PreToolUse']) == expected
        if expected:
            assert 'cannot read outbound body file' in capsys.readouterr().out


def test_json_body_disposition_marker_is_checked_after_decoding(case, monkeypatch, capsys):
    root, _, _ = case
    marker = f'WUWEI parked {REF} D-1 {workspace.day_dir(root).name} ' + 'a' * 64
    (root / 'body.json').write_text(json.dumps({'body': marker}).replace('WUWEI ', 'WUWEI\\u0020'))
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps({**payload(root),
        'hook_event_name': 'PreToolUse', 'tool_name': 'Bash', 'tool_input': {'command':
        'gh api repos/acme/widget/issues/7/comments --input body.json'}})))
    assert main(['hook', 'PreToolUse']) == 2
    assert 'owner disposition' in capsys.readouterr().out
