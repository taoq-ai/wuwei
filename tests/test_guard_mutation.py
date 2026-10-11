"""A registered guard must fail its own assertion when its check is disabled."""

from types import SimpleNamespace

import pytest

from wuwei.guards import discover


# Each row gives one observable refusal, error, or side effect for a guard.
PROBES = {
    ('agent_launch', 'PreToolUse', 'Agent', 'check'):
        ('Agent', {'prompt': 'launch without brief', 'description': 'build',
                   'subagent_type': 'wuwei:builder'}, 1),
    ('agent_launch', 'SubagentStop', None, 'stop'): ('stop event', {}, 'event'),
    ('answers', 'PostToolUse', 'AskUserQuestion', 'record_gate'):
        ('AskUserQuestion', {'questions': [{'header': 'Owner step'}]}, 2),
    ('edges', 'PreToolUse', 'Bash', 'check_bash'): ('Bash', {'command': 'gh pr review 7 --approve'}, 1),
    ('edges', 'PreToolUse', 'Bash', 'check_deploy'): ('Bash', {'command': 'terraform apply'}, 1),
    ('edges', 'PreToolUse', None, 'check_send'): ('mcp__slack__post_message', [], 2),
    ('integrity', 'SessionStart', None, 'session_start'): ('Bash', {}, 1),
    ('lifecycle', 'PreCompact', None, 'pre_compact'): ('Bash', {}, 2),
    ('lifecycle', 'SessionStart', None, 'session_start'): ('Bash', {}, 2),
    ('lifecycle', 'Stop', None, 'stop'): ('Bash', {}, 'message'),
    ('lifecycle', 'SubagentStop', None, 'subagent_stop'): ('Bash', {}, 'message'),
    ('outward', 'PreToolUse', None, 'check_lint'): ('mcp__slack__post_message', [], 2),
    ('protect_state', 'PreToolUse', 'Bash', 'check_bash'):
        ('Bash', {'command': 'echo x > .wuwei/days/2026-09-29/state.json'}, 1),
    ('protect_state', 'PreToolUse', 'Write|Edit|MultiEdit|NotebookEdit', 'check_file'):
        ('Write', {}, 2),
    ('protect_state', 'PreToolUse', 'Write|Edit|MultiEdit|NotebookEdit', 'check_scratch'):
        ('Write', {}, 2),
    ('spec', 'PostToolUse', 'Write|Edit|MultiEdit|NotebookEdit|Bash', 'check_record'):
        ('Write', {'file_path': 'specs/001-a/spec.md'}, 2),
    ('spec', 'SubagentStop', None, 'check_stop'): ('SubagentStop', {}, 2),
    ('stop', 'Stop', None, 'check'): ('Bash', {}, 2),
    ('traces', 'PostToolUse', None, 'check'): ('Bash', {}, 'event'),  # #837: never refuses
    ('verdict', 'PostToolUse', 'Write|Edit|MultiEdit|NotebookEdit|Bash', 'check_write'):
        ('Write', {}, 2),
    ('verdict', 'SubagentStop', None, 'check_write'): ('Write', {}, 2),
    ('verdict', 'SubagentStop', None, 'check_retro'): ('Bash', {}, 1),
}

SPECIAL_TESTS = {
    ('wuwei.merge', 'check'): 'test_disabling_merge_policy_makes_its_probe_red',
    ('wuwei.guards.edges', 'check_deploy'): 'test_disabling_guard_makes_its_probe_red',
    ('wuwei.commands.hook', 'reaches_workspace'): 'test_disabling_scope_gate_makes_outside_probe_red',
}


def key(guard):
    return (guard.check.__module__.rsplit('.', 1)[-1], guard.event,
            guard.matcher, guard.check.__name__)


def missing_guards(registered, probes):
    return sorted(set(registered) - set(probes), key=str)


def test_uncovered_guard_is_named(tmp_path, monkeypatch):
    import sys
    import wuwei.guards

    (tmp_path / 'dummy_guard.py').write_text(
        "from wuwei.guards import Guard\n"
        "def check(p): return (0, '')\n"
        "GUARDS = [Guard('PreToolUse', 'Bash', check)]\n")
    monkeypatch.setattr(wuwei.guards, '__path__', [*wuwei.guards.__path__, str(tmp_path)])
    monkeypatch.delitem(sys.modules, 'wuwei.guards.dummy_guard', raising=False)
    try:
        missing = missing_guards([key(g) for g in wuwei.guards.discover()], PROBES)
        assert missing == [('dummy_guard', 'PreToolUse', 'Bash', 'check')]
    finally:
        sys.modules.pop('wuwei.guards.dummy_guard', None)


def test_every_registered_guard_has_a_mutation_probe():
    missing = missing_guards([key(guard) for guard in discover()], PROBES)
    assert not missing, f'guards without mutation tests: {missing}'


def test_special_policies_have_mutation_probes():
    from wuwei import merge

    required = {(merge.check.__module__, merge.check.__name__),
                ('wuwei.guards.edges', 'check_deploy'),
                ('wuwei.commands.hook', 'reaches_workspace')}
    covered = {name for name, test in SPECIAL_TESTS.items() if callable(globals().get(test))}
    assert not missing_guards(required, covered), 'special policy lacks a mutation test'
    assert ('edges', 'PreToolUse', 'Bash', 'check_deploy') in PROBES


def test_disabling_merge_policy_makes_its_probe_red(tmp_path):
    from wuwei import merge

    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('')

    def assert_refused(check):
        assert check('example/project#1', tmp_path).exit == 1

    assert_refused(merge.check)
    with pytest.raises(AssertionError):
        assert_refused(lambda *args: merge.Result(0, {}, ''))



def test_disabling_scope_gate_makes_outside_probe_red(tmp_path, monkeypatch):
    from test_scope_first import TRIAL, assert_outside_clean, outside_dir
    from wuwei.commands import hook

    place = outside_dir(tmp_path, monkeypatch)
    assert_outside_clean(TRIAL, place)
    monkeypatch.setattr(hook, 'reaches_workspace', lambda *args: True)
    with pytest.raises(AssertionError):
        assert_outside_clean(TRIAL, place)


def assert_probe(check, row, root, monkeypatch):
    from wuwei import workspace

    tool, tool_input, expected = row
    payload = {'cwd': str(root), 'tool_name': tool, 'tool_input': tool_input,
               'session_id': 'mutation', 'agent_id': 'mutation'}
    events = []
    if expected == 'event':
        from wuwei import security, state
        payload['agent_type'] = 'wuwei:builder'
        monkeypatch.setattr(state, 'append_event', lambda *args, **kwargs: events.append(args))
        if check.__module__.endswith('.traces'):  # the recorder warns with a traces.gap event
            monkeypatch.setattr(security, 'load', lambda *a, **k: (_ for _ in ()).throw(OSError('load')))
    elif expected == 'message':
        payload['cwd'] = 'relative'
    elif check.__module__.endswith('.lifecycle') and tool == 'Bash':
        payload['cwd'] = 'relative'
    elif check.__module__.endswith('.stop'):
        payload['cwd'] = 'relative'
    elif check.__module__.endswith('.spec') and check.__name__ == 'check_stop':
        from wuwei.guards import agent_launch
        payload['agent_type'] = 'wuwei:builder'
        # A seat the day's state does not hold: the check reports it cannot run.
        monkeypatch.setattr(agent_launch, 'stopping_seat', lambda payload, root: (root / 'day', 'b', 'builder'))
    elif check.__module__.endswith('.spec'):
        monkeypatch.setattr(workspace, 'guard_scope', lambda _: (_ for _ in ()).throw(ValueError('scope')))
    elif check.__name__ == 'record_gate':
        del payload['agent_id']  # a main session, not a seat
    elif check.__name__ == 'check_stop':
        payload.update(agent_type='wuwei:builder', last_assistant_message='Add a cache?')
    elif check.__module__.endswith('.verdict') and check.__name__ == 'check_retro':
        payload.update(agent_type='wuwei:builder', last_assistant_message='')
    result = check(payload)
    if expected == 'event':
        assert events, 'the guard must record its event'
    elif expected == 'message':
        assert result[1], 'planner wake error must be reported'
    else:
        assert result[0] == expected, result


@pytest.mark.parametrize('guard', discover(), ids=lambda g: '.'.join((g.check.__module__.rsplit('.', 1)[-1], g.event, g.check.__name__)))
def test_disabling_guard_makes_its_probe_red(tmp_path, monkeypatch, guard):
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('')
    row = PROBES[key(guard)]
    if key(guard)[0] == 'integrity':
        from wuwei import integrity
        from wuwei.registry import Result

        directory = tmp_path / '.wuwei/integrity'
        directory.mkdir()
        (directory / 'verdict.json').write_text(
            '{"exit":1,"reason":"page: changed plugin"}')
        monkeypatch.setattr(integrity, 'check', lambda root: Result(1, reason='page: changed plugin'))
        monkeypatch.setattr(integrity, 'workspace_check', lambda root: Result(0))
    assert_probe(guard.check, row, tmp_path, monkeypatch)
    disabled = guard._replace(check=lambda _: (0, ''))
    with pytest.raises(AssertionError):
        assert_probe(disabled.check, row, tmp_path, monkeypatch)
