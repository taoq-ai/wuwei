"""One switch, guards.enforce (#837): the hook blocks or logs each refusal; the floor blocks."""

import pytest

from wuwei import workspace

CAP = 'seat not registered: running build seats 2 at CAP 2; wait for a build seat to finish, then retry'
MISMATCH = ('seat not registered: Agent role does not match logged brief role; write the brief '
            'again with bin/wuwei brief, then launch with the name and role it returns')
CANARY = 'outward: security.canary'
MISSING = ('brief .wuwei/days/2026-09-28/briefs/never.md does not exist; '
           'run bin/wuwei brief sentinel-arch <item> <name> first')


def fixed(module, code, reason, name='check'):
    def check(payload):
        return code, reason
    check.__module__, check.__name__ = f'wuwei.guards.{module}', name
    return check


def test_default_config_enforces():
    config = workspace.load_config('.', raw='')
    assert config['guards'] == {'enforce': True}
    assert config['security'] == {'required': False}
    for name in ('POSTURES', 'AREAS', 'AREA_LEVELS', 'FLOORS', 'posture', 'posture_source'):
        assert not hasattr(workspace, name), name
    for key in ('security.posture', 'security.areas', 'guards.mode', 'guards.shadow_days',
                'guards.shadow_since'):
        assert key in workspace.RETIRED


def test_floor_keys_name_guard_modules():
    from importlib import import_module
    from wuwei import guards
    for key in guards.FLOOR | guards.LOG_ONLY:
        module, _, function = key.partition('.')
        assert module in guards.MODULES
        assert not function or callable(getattr(import_module(f'wuwei.guards.{module}'), function))
    for name in ('AREAS', 'OWNER_ONLY', 'level'):
        assert not hasattr(guards, name), name


# (check, reason, blocks with enforce on, blocks with enforce off)
TABLE = [
    (fixed('commit_push', 1, 'commit refused'), True, False),
    (fixed('integrity', 2, 'integrity gate'), True, False),
    (fixed('spec', 1, 'spec missing'), True, False),
    (fixed('stop', 1, 'stop refused'), True, False),
    (fixed('pr', 1, 'pr raise: pre-PR gates not passed'), True, False),
    (fixed('pr', 1, 'push to the default branch is refused'), True, True),
    (fixed('pr', 1, 'merge policy requires an explicit PR'), True, True),
    (fixed('pr', 1, 'admin merge is refused'), True, True),
    (fixed('pr', 1, 'PR approval is refused'), True, True),
    (fixed('deploy', 1, 'deploy refused'), True, True),
    (fixed('answers', 2, 'answer not recorded'), True, True),
    (fixed('lifecycle', 2, 'lifecycle failed'), True, True),
    (fixed('verdict', 1, 'verdict lint'), True, True),
    (fixed('protect_state', 1, 'state write', 'check_file'), True, True),
    (fixed('protect_state', 1, 'state bash', 'check_bash'), True, True),
    (fixed('protect_state', 1, 'another item scratch', 'check_scratch'), False, False),
    (fixed('traces', 2, 'RuntimeError: could not run PostToolUse guard'), False, False),
    (fixed('outward', 1, 'outward lint', 'check_lint'), False, False),
    (fixed('outward', 1, 'held send', 'check_tier'), True, True),
    (fixed('outward', 1, CANARY, 'check_lint'), True, True),
    (fixed('agent_launch', 1, MISMATCH), True, False),
    (fixed('agent_launch', 2, MISSING), True, True),
    (fixed('agent_launch', 1, CAP), False, False),
    (fixed('agent_launch', 1, 'seat not registered: running seats 4 at host seat ceiling'), False, False),
    (fixed('agent_launch', 1, 'seat not registered: free memory 1 bytes below floor 2'), False, False),
    (fixed('agent_launch', 1, 'seat not registered: P-1 has no ticket: the planner proposes one'), False, False),
]


@pytest.mark.parametrize('enforce', [True, False])
@pytest.mark.parametrize('check,on,off', TABLE)
def test_hook_table(tmp_path, monkeypatch, enforce, check, on, off):
    from wuwei.commands import hook
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text(f'[guards]\nenforce = {str(enforce).lower()}\n')
    monkeypatch.setenv('WUWEI_NOW', '2026-10-03T12:00:00Z')
    code, reason = check({})
    payload = {'session_id': 's', 'tool_name': 'Bash', 'tool_input': {'command': 'git push'},
               'cwd': str(tmp_path)}
    blocks = on if enforce else off
    enforced = hook.enforce(payload, [(check, reason, code)], tmp_path)
    assert enforced == ([(check.__module__.rsplit('.', 1)[-1], reason, code)] if blocks else [])
    logged = events(tmp_path, 'guard.would_refuse')
    if blocks:
        assert not logged
    else:
        [event] = logged
        assert set(event) == {'guard', 'reason', 'exit', 'target', 'session', 'item'}
        assert event['reason'] == reason and event['exit'] == code


def test_unreadable_config_blocks(tmp_path):
    from wuwei.commands import hook
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('[guards\n')
    check = fixed('outward', 1, 'outward lint', 'check_lint')
    assert hook.enforce({}, [(check, 'outward lint', 1)], tmp_path) == [('outward', 'outward lint', 1)]
    assert hook.enforce({}, [(check, 'outward lint', 1)], None) == [('outward', 'outward lint', 1)]


@pytest.fixture
def guarded(tmp_path, monkeypatch):
    from fakes.integrity import seed
    root = tmp_path / 'workspace'
    (root / '.wuwei').mkdir(parents=True)
    (root / '.wuwei/config.toml').write_text('')
    seed(root)
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    monkeypatch.setenv('WUWEI_NOW', '2026-10-03T12:00:00Z')
    return root


def hook_call(root, monkeypatch, capsys, event='PreToolUse', command='git push', guards=None):
    import io
    import json
    import sys
    from types import SimpleNamespace
    from wuwei.commands import hook
    from wuwei.guards import Guard
    if guards is not None:
        monkeypatch.setattr(hook, 'discover', lambda: [Guard(event, None, check) for check in guards])
    payload = {'hook_event_name': event, 'session_id': 'fixture', 'cwd': str(root),
               'transcript_path': str(root / 'transcript.jsonl'), 'tool_name': 'Bash',
               'tool_input': {'command': command}}
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(payload)))
    code = hook.run(SimpleNamespace(event=event))
    return code, capsys.readouterr()


def events(root, kind):
    import json
    return [json.loads(line)['payload'] for path in root.glob('.wuwei/days/*/events.jsonl')
            for line in path.read_text().splitlines() if json.loads(line)['kind'] == kind]


def test_one_reason_most_specific(guarded, monkeypatch, capsys):
    import json
    code, out = hook_call(guarded, monkeypatch, capsys, guards=[
        fixed('commit_push', 1, 'commit_push specific'), fixed('deploy', 2, 'deploy generic'),
        fixed('integrity', 2, 'integrity gate')])
    assert code == 2 and out.err == 'commit_push specific\n'
    assert json.loads(out.out)['hookSpecificOutput']['permissionDecisionReason'] == 'commit_push specific'
    [event] = events(guarded, 'hook.refusal')
    assert event['reason'] == 'commit_push specific'
    assert [row['guard'] for row in event['refusals']] == ['commit_push', 'deploy', 'integrity']


def test_one_reason_integrity_last(guarded, monkeypatch, capsys):
    code, out = hook_call(guarded, monkeypatch, capsys, guards=[
        fixed('integrity', 2, 'integrity gate'), fixed('deploy', 2, 'deploy generic')])
    assert out.err.splitlines() == ['deploy generic']
    code, out = hook_call(guarded, monkeypatch, capsys, guards=[fixed('integrity', 2, 'integrity gate')])
    assert out.err.splitlines()[0] == 'integrity gate'


def test_enforce_off_keeps_the_floor(guarded, monkeypatch, capsys):
    (guarded / '.wuwei/config.toml').write_text('[guards]\nenforce = false\n')
    code, out = hook_call(guarded, monkeypatch, capsys, guards=[
        fixed('commit_push', 1, 'commit_push specific'), fixed('deploy', 2, 'deploy generic')])
    assert code == 2 and out.err.splitlines() == ['deploy generic']
    [event] = events(guarded, 'guard.would_refuse')
    assert event['reason'] == 'commit_push specific'


def test_traces_exception_never_blocks(guarded, monkeypatch, capsys):
    def record(payload):
        raise RuntimeError('recorder broke')
    record.__module__ = 'wuwei.guards.traces'
    code, out = hook_call(guarded, monkeypatch, capsys, event='PostToolUse', guards=[record])
    assert code == 0, out.err
    assert not events(guarded, 'hook.refusal')
    [event] = events(guarded, 'guard.would_refuse')
    assert event['guard'] == 'traces'


def test_one_reason_session_start_unchanged(guarded, monkeypatch, capsys):
    import json
    code, out = hook_call(guarded, monkeypatch, capsys, event='SessionStart', guards=[
        fixed('deploy', 2, 'first'), fixed('integrity', 2, 'second')])
    context = json.loads(out.out)['hookSpecificOutput']['additionalContext']
    assert code == 0 and 'first' in context and 'second' in context
    assert out.err.splitlines() == ['first', 'second']


@pytest.mark.parametrize('command', ['git config --get-all core.hooksPath', 'ls ~/'])
def test_reads_pass(guarded, monkeypatch, capsys, command):
    code, out = hook_call(guarded, monkeypatch, capsys, command=command)
    assert code == 0, out.err
    assert not events(guarded, 'hook.refusal') and not events(guarded, 'guard.would_refuse')


@pytest.mark.parametrize('enforce', ['true', 'false'])
def test_opaque_refusals_give_one_warning(guarded, monkeypatch, capsys, enforce):
    # #530: guards that could not read an opaque call naming no publish target warn once.
    (guarded / '.wuwei/config.toml').write_text(f'[guards]\nenforce = {enforce}\n')
    (guarded / 'loop.sh').write_text('gh pr view 7\n')
    code, out = hook_call(guarded, monkeypatch, capsys, command='bash loop.sh', guards=[
        fixed('deploy', 2, 'deploy: could not inspect'), fixed('pr', 2, 'PR guard could not run'),
        fixed('commit_push', 2, 'unparsed')])
    assert code == 0, out.err
    [event] = events(guarded, 'guard.would_refuse')
    assert event['reason'].startswith('opaque: script loop.sh;') and 'strict' not in event['reason']


def test_opaque_reason_error_enforces(guarded, monkeypatch, capsys):
    from wuwei import shell
    def broken(*args, **kwargs):
        raise RuntimeError('boom')
    monkeypatch.setattr(shell, 'unreadable', broken)
    code, out = hook_call(guarded, monkeypatch, capsys, command='bash loop.sh',
                          guards=[fixed('commit_push', 2, 'commit_push: could not inspect')])
    assert code == 2 and 'commit_push: could not inspect' in out.err


def test_opaque_floor_still_blocks(guarded, monkeypatch, capsys):
    (guarded / '.wuwei/config.toml').write_text('[guards]\nenforce = false\n')
    code, out = hook_call(guarded, monkeypatch, capsys, command='bash loop.sh',
                          guards=[fixed('protect_state', 2, 'state write', 'check_bash')])
    assert code == 2 and 'state write' in out.err


def test_logged_launch_refusal_is_shown_to_the_session(guarded, monkeypatch, capsys):
    # #660: a launch refusal the hook lets through is shown, never only recorded.
    import json
    (guarded / '.wuwei/config.toml').write_text('[guards]\nenforce = false\n')
    code, out = hook_call(guarded, monkeypatch, capsys, guards=[fixed('agent_launch', 1, 'launch reason')])
    assert code == 0
    [line] = out.out.splitlines()
    assert json.loads(line)['hookSpecificOutput'] == {
        'hookEventName': 'PreToolUse', 'additionalContext': 'launch reason'}
    assert [row['reason'] for row in events(guarded, 'guard.would_refuse')] == ['launch reason']
    code, out = hook_call(guarded, monkeypatch, capsys, guards=[fixed('outward', 1, 'outward reason')])
    assert code == 0 and out.out == ''
    code, out = hook_call(guarded, monkeypatch, capsys, guards=[
        fixed('agent_launch', 1, 'launch reason'), fixed('deploy', 2, 'deploy reason')])
    assert code == 2
    [line] = out.out.splitlines()
    assert json.loads(line)['hookSpecificOutput']['permissionDecisionReason'].startswith('deploy reason')
    (guarded / '.wuwei/config.toml').write_text('')
    code, out = hook_call(guarded, monkeypatch, capsys, guards=[fixed('agent_launch', 1, 'launch reason')])
    assert code == 2
    assert json.loads(out.out)['hookSpecificOutput']['permissionDecisionReason'] == 'launch reason'
    code, out = hook_call(guarded, monkeypatch, capsys, guards=[fixed('agent_launch', 1, CAP)])
    assert code == 0 and json.loads(out.out)['hookSpecificOutput']['additionalContext'] == CAP


@pytest.mark.parametrize('enforce', [None, True])
def test_would_refuse_is_silent(enforce):
    from wuwei.signal import classify
    payload = {'guard': 'outward', 'reason': 'r'} | ({'posture': 'guarded'} if enforce else {})
    assert classify({'kind': 'guard.would_refuse', 'payload': payload}, {})[0] == 'silent'
    assert classify({'kind': 'traces.unmatched', 'payload': {}}, {})[0] == 'warn'
