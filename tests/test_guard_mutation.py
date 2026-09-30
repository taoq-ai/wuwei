"""A registered guard must fail its own assertion when its check is disabled."""

import pytest

from wuwei.guards import discover


# Each row gives one observable refusal, error, or side effect for a guard.
PROBES = {
    ('agent_launch', 'PreToolUse', 'Agent', 'check'):
        ('Agent', {'prompt': 'launch without brief', 'description': 'build',
                   'subagent_type': 'wuwei:builder'}, 1),
    ('agent_launch', 'SubagentStop', None, 'stop'): ('stop event', {}, 'event'),
    ('commit_push', 'PreToolUse', 'Bash', 'check'): ('Bash', {'command': 'git push "'}, 2),
    ('decision', 'PostToolUse', 'Write|Edit|MultiEdit|NotebookEdit|Bash', 'check_write'):
        ('Write', {}, 2),
    ('decision', 'PreToolUse', 'AskUserQuestion', 'check_question'):
        ('AskUserQuestion', {'questions': [{}]}, 2),
    ('deploy', 'PreToolUse', 'Bash', 'check'): ('Bash', {'command': 'terraform apply'}, 1),
    ('integrity', 'PreToolUse', None, 'check'): ('Bash', {'command': 'echo hi'}, 2),
    ('integrity', 'SessionStart', None, 'session_start'): ('Bash', {}, 1),
    ('lifecycle', 'PreCompact', None, 'pre_compact'): ('Bash', {}, 2),
    ('lifecycle', 'SessionStart', None, 'session_start'): ('Bash', {}, 2),
    ('lifecycle', 'Stop', None, 'stop'): ('Bash', {}, 'message'),
    ('lifecycle', 'SubagentStop', None, 'subagent_stop'): ('Bash', {}, 'message'),
    ('outward', 'PreToolUse', None, 'check_tier'): ('mcp__slack__post_message', {}, 2),
    ('outward', 'PreToolUse', None, 'check_lint'): ('mcp__slack__post_message', {}, 2),
    ('pr', 'PreToolUse', 'Bash', 'check'): ('Bash', {'command': 'gh pr review --approve'}, 1),
    ('protect_state', 'PreToolUse', 'Bash', 'check_bash'):
        ('Bash', {'command': 'echo x > .wuwei/days/2026-09-29/state.json'}, 1),
    ('protect_state', 'PreToolUse', 'Write|Edit|MultiEdit|NotebookEdit', 'check_file'):
        ('Write', {}, 2),
    ('stop', 'Stop', None, 'check'): ('Bash', {}, 2),
    ('traces', 'PostToolUse', None, 'check'): ('Bash', {}, 2),
    ('verdict', 'PostToolUse', 'Write|Edit|MultiEdit|NotebookEdit|Bash', 'check_write'):
        ('Write', {}, 2),
    ('verdict', 'SubagentStop', None, 'check_write'): ('Write', {}, 2),
    ('verdict', 'SubagentStop', None, 'check_retro'): ('Bash', {}, 1),
}

SPECIAL_TESTS = {
    ('wuwei.merge', 'check'): 'test_disabling_merge_policy_makes_its_probe_red',
    ('wuwei.decision', 'lint'): 'test_disabling_decision_lint_makes_its_probe_red',
    ('wuwei.guards.deploy', 'check'): 'test_disabling_guard_makes_its_probe_red',
    ('wuwei.guards.protect_state', '_owner_action'): 'test_disabling_owner_rule_makes_its_probe_red',
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
    from wuwei import decision, merge

    required = {(merge.check.__module__, merge.check.__name__),
                (decision.lint.__module__, decision.lint.__name__),
                ('wuwei.guards.deploy', 'check'),
                ('wuwei.guards.protect_state', '_owner_action')}
    covered = {name for name, test in SPECIAL_TESTS.items() if callable(globals().get(test))}
    assert not missing_guards(required, covered), 'special policy lacks a mutation test'
    assert ('deploy', 'PreToolUse', 'Bash', 'check') in PROBES


def test_disabling_merge_policy_makes_its_probe_red(tmp_path):
    from wuwei import merge

    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('')

    def assert_refused(check):
        assert check('example/project#1', tmp_path).exit == 1

    assert_refused(merge.check)
    with pytest.raises(AssertionError):
        assert_refused(lambda *args: merge.Result(0, {}, ''))


def test_disabling_decision_lint_makes_its_probe_red():
    from wuwei import decision

    def assert_refused(lint):
        assert lint('Question: bad')[0] == 1

    assert_refused(decision.lint)
    with pytest.raises(AssertionError):
        assert_refused(lambda text: (0, ''))


def test_disabling_owner_rule_makes_its_probe_red(tmp_path, monkeypatch):
    from wuwei.guards import protect_state

    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('')
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    payload = {'cwd': str(tmp_path), 'tool_name': 'Bash',
               'tool_input': {'command': 'W=watch; bin/wuwei $W uninstall'}}

    def assert_refused():
        assert protect_state.check_bash(payload)[0] == 2

    assert_refused()
    monkeypatch.setattr(protect_state, '_owner_action', lambda *args, **kwargs: None)
    with pytest.raises(AssertionError):
        assert_refused()


def assert_probe(check, row, root, monkeypatch):
    from wuwei import workspace

    tool, tool_input, expected = row
    payload = {'cwd': str(root), 'tool_name': tool, 'tool_input': tool_input,
               'session_id': 'mutation', 'agent_id': 'mutation'}
    events = []
    if expected == 'event':
        from wuwei import state
        payload['agent_type'] = 'wuwei:builder'
        monkeypatch.setattr(state, 'append_event', lambda *args, **kwargs: events.append(args))
    elif expected == 'message':
        payload['cwd'] = 'relative'
    elif check.__module__.endswith('.lifecycle') and tool == 'Bash':
        payload['cwd'] = 'relative'
    elif check.__module__.endswith('.stop'):
        payload['cwd'] = 'relative'
    elif check.__module__.endswith('.traces'):
        monkeypatch.setattr(workspace, 'guard_scope', lambda _: (_ for _ in ()).throw(ValueError('scope')))
    elif check.__module__.endswith('.verdict') and check.__name__ == 'check_retro':
        payload.update(agent_type='wuwei:builder', last_assistant_message='')
    result = check(payload)
    if expected == 'event':
        assert events, 'seat stop must record an unmatched event'
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
