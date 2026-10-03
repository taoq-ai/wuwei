"""Profiles are applied in process at the hook boundary."""

import io
import json
import sys
from types import SimpleNamespace

import pytest

from wuwei import workspace
from wuwei.commands import hook
from wuwei.guards import Guard


@pytest.fixture
def configured(tmp_path, monkeypatch):
    from wuwei import registry
    monkeypatch.setattr(registry, 'load', lambda kind, config: pytest.fail(f'unexpected port read: {kind}'))
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T12:00:00Z')
    directory = tmp_path / '.wuwei'
    directory.mkdir()
    (directory / 'config.toml').write_text('''
[owner]
name = "Pat Example"
pronouns = "they/them"
[outbound]
work_channels = ["Cwork"]
[outward.max_length]
slack = 3
chat = 3
[security]
posture = "strict" # #331: these tests pin the outward lint blocking; guarded warns.
''')
    from fakes.integrity import seed
    seed(tmp_path)
    return tmp_path


def replay(root, monkeypatch, capsys, *, tool='mcp__slack__post_message', inputs=None):
    payload = {'cwd': str(root), 'tool_name': tool,
               'tool_input': inputs if inputs is not None else {'text': 'Thanks', 'channel': 'Cwork'},
               'hook_event_name': 'PreToolUse', 'session_id': 'test',
               'transcript_path': str(root / 'transcript.jsonl'), 'tool_use_id': 'call'}
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(payload)))
    code = hook.run(SimpleNamespace(event='PreToolUse'))
    output = capsys.readouterr()
    return code, output.out, output.err


def set_profile(root, profile):
    path = root / '.wuwei/config.toml'
    if profile is not None:
        path.write_text(f'profile = {json.dumps(profile)}\n' + path.read_text())


@pytest.mark.parametrize('profile', [None, 'strict', 'standard'])
@pytest.mark.parametrize('relaxable', [False, True])
@pytest.mark.parametrize('code', [0, 1, 2])
def test_dispatcher_profile_matrix(configured, monkeypatch, capsys, profile, relaxable, code):
    set_profile(configured, profile)
    # A plain record isolates dispatcher behavior from discovery validation.
    guard = SimpleNamespace(event='PreToolUse', matcher=None,
                            check=lambda p: (code, 'redacted reason' if code else ''),
                            profile_relaxable=relaxable)
    monkeypatch.setattr(hook, 'discover', lambda: [guard])
    result, out, err = replay(configured, monkeypatch, capsys)
    warns = profile == 'standard' and relaxable and code == 1
    assert result == (0 if code == 0 or warns else 2)
    if warns:
        assert out == ''
        assert err == 'warning: redacted reason\n'
        events, = (configured / '.wuwei').glob('days/*/events.jsonl')
        assert json.loads(events.read_text().strip())['payload'] == {
            'reason': 'redacted reason', 'tool': 'mcp__slack__post_message'}
    elif code:
        assert json.loads(out)['hookSpecificOutput']['permissionDecision'] == 'deny'
        assert 'redacted reason' in err
    else:
        assert out == err == ''


def test_guard_metadata_defaults_to_blocking():
    guard = Guard('PreToolUse', None, lambda p: (1, 'reason'))
    assert getattr(guard, 'profile_relaxable', None) is False


@pytest.mark.parametrize('invalid', ['yes', 1, None])
def test_invalid_metadata_fails_discovery(monkeypatch, invalid):
    import wuwei.guards as guards
    guard = Guard('PreToolUse', None, lambda p: (0, ''), profile_relaxable=invalid)
    monkeypatch.setattr(guards.pkgutil, 'iter_modules', lambda *a: [SimpleNamespace(name='example.guard')])
    monkeypatch.setattr(guards, 'import_module', lambda name: SimpleNamespace(GUARDS=[guard]))
    with pytest.raises(ValueError, match='profile_relaxable'):
        guards.discover()


def test_only_outward_lint_is_relaxable():
    from wuwei.guards import discover
    guards = [guard for guard in discover() if guard.profile_relaxable]
    assert len(guards) == 1
    assert guards[0].check.__module__ == 'wuwei.guards.outward'
    assert guards[0].check.__name__ == 'check_lint'


@pytest.mark.parametrize('profile', [None, 'strict', 'standard'])
@pytest.mark.parametrize('text,channel,invalid', [
    ('Ack', 'Cwork', False),
    ('Thanks', 'Cwork', False),
    ('Thanks', 'Cclient', False),
    ('Thanks', 'Cwork', True),
])
def test_outward_hook_profiles(configured, monkeypatch, capsys, profile, text, channel, invalid):
    set_profile(configured, profile)
    if invalid:
        with (configured / '.wuwei/config.toml').open('a') as stream:
            stream.write('\n[outward]\npatterns = ["["]\n')
    result, out, err = replay(configured, monkeypatch, capsys,
                              inputs={'text': text, 'channel': channel})
    blocked = invalid or channel == 'Cclient' or (text == 'Thanks' and profile != 'standard')
    assert result == (2 if blocked else 0)
    assert text not in err
    if blocked:
        assert json.loads(out)['hookSpecificOutput']['permissionDecision'] == 'deny'
    elif text == 'Thanks':
        assert out == ''
        assert err == 'warning: outward: channel length exceeded\n'
    else:
        assert out == err == ''


def test_lint_guard_returns_findings_without_applying_profile(configured, capsys):
    from wuwei.guards import discover
    set_profile(configured, 'standard')
    guards = [guard for guard in discover() if guard.profile_relaxable]
    assert len(guards) == 1
    code, reason = guards[0].check({'cwd': str(configured), 'tool_name': 'mcp__slack__post_message',
                                   'tool_input': {'text': 'Thanks', 'channel': 'Cwork'}})
    assert code == 1
    assert 'channel length exceeded' in reason
    assert capsys.readouterr().err == ''


def test_standard_outward_warning_records_tool_and_reason(configured, monkeypatch, capsys):
    set_profile(configured, 'standard')
    assert replay(configured, monkeypatch, capsys)[0] == 0
    events, = (configured / '.wuwei').glob('days/*/events.jsonl')
    record, = [json.loads(line) for line in events.read_text().splitlines()
               if json.loads(line)['kind'] == 'hook.warning']
    assert record['payload'] == {'reason': 'outward: channel length exceeded',
                                 'tool': 'mcp__slack__post_message'}


@pytest.mark.parametrize('profile', ['strict', 'standard'])
@pytest.mark.parametrize('channel', ['Cwork', 'Cclient'])
def test_direct_port_preserves_profile_and_tiers(configured, monkeypatch, capsys, profile, channel):
    from wuwei import registry
    set_profile(configured, profile)
    performed = []

    @registry.outward_operation('chat')
    def post(channel, text, root=None):
        performed.append(text)
        return registry.Result(0)

    result = post(channel, 'Thanks', root=configured)
    allowed = profile == 'standard' and channel == 'Cwork'
    assert result.exit == (0 if allowed else 1)
    assert performed == (['Thanks'] if allowed else [])
    assert ('warning:' in capsys.readouterr().err) == allowed
    events = list((configured / '.wuwei').glob('days/*/events.jsonl'))
    if allowed:
        record, = [json.loads(line) for line in events[0].read_text().splitlines()
                   if json.loads(line)['kind'] == 'hook.warning']
        assert record['payload'] == {'reason': 'outward: channel length exceeded', 'tool': 'chat'}
    elif channel == 'Cclient':
        record, = [json.loads(line) for line in events[0].read_text().splitlines()]
        assert record['kind'] == 'draft.created'
        assert record['payload']['channel'] == 'chat'
        assert 'Thanks' not in events[0].read_text()
    else:
        assert not events


@pytest.mark.parametrize('command,reason', [
    ('gh pr merge 17 --squash', 'merge'),
    ('env gh pr merge 17 --admin', 'admin'),
    ('sh -c "gh pr review 17 --approve"', 'approval'),
    ('gh api repos/example/project/pulls/17/merge -X PUT', 'merge'),
    ('gh api repos/example/project/pulls/17/reviews -f event=APPROVE', 'approval'),
    ('terraform apply', 'terraform'),
    ('command gh release create v1', 'release'),
    ('bash -c "kubectl apply -f deployment.yml"', 'kubectl'),
    ('echo "gh pr merge 17"', 'plain command'),
])
@pytest.mark.parametrize('profile', ['strict', 'standard'])
def test_hard_guards_under_each_profile(configured, monkeypatch, capsys, command, reason, profile):
    set_profile(configured, profile)
    result, out, err = replay(configured, monkeypatch, capsys, tool='Bash', inputs={'command': command})
    assert result == 2
    assert json.loads(out)['hookSpecificOutput']['permissionDecision'] == 'deny'
    assert reason in err
    assert 'warning:' not in err


@pytest.mark.parametrize('inside', [False, True])
@pytest.mark.parametrize('command', ['python3 -m pytest -q', 'for x in a b; do echo "$x"; done', 'export X=1'])
def test_irrelevant_commands(configured, monkeypatch, capsys, inside, command):
    set_profile(configured, 'standard')
    root = configured if inside else configured / '..' / 'unrelated'
    root.mkdir(exist_ok=True)
    assert replay(root, monkeypatch, capsys, tool='Bash', inputs={'command': command}) == (0, '', '')


@pytest.mark.parametrize('location', ['outside', 'repo', 'worktree', 'target'])
def test_outward_profile_scope(configured, monkeypatch, capsys, location):
    set_profile(configured, 'standard')
    sibling = configured.parent / (configured.name + '-sibling')
    sibling.mkdir(exist_ok=True)
    if location in ('outside', 'repo', 'target'):
        monkeypatch.setenv('WUWEI_WORKSPACE', str(configured))
    if location == 'repo':
        with (configured / '.wuwei/config.toml').open('a') as stream:
            stream.write(f'\n[[repos]]\nname = "example/project"\npath = "../{sibling.name}"\ndefault_branch = "main"\n')
    if location == 'worktree':
        (sibling / '.git').mkdir()
        (sibling / '.git/wuwei-workspace').write_text(str(configured))
    inputs = {'text': 'Thanks', 'channel': 'Cwork'}
    if location == 'target':
        inputs['repo'] = str(configured)
    result, out, err = replay(sibling, monkeypatch, capsys, inputs=inputs)
    assert result == 0, err
    assert out == ''
    assert ('warning:' in err) == (location != 'outside')


def test_warning_does_not_hide_later_refusal(configured, monkeypatch, capsys):
    set_profile(configured, 'standard')
    monkeypatch.setattr(hook, 'discover', lambda: [
        Guard('PreToolUse', None, lambda p: (1, 'lint reason'), profile_relaxable=True),
        Guard('PreToolUse', None, lambda p: (1, 'hard refusal')),
    ])
    result, out, err = replay(configured, monkeypatch, capsys)
    assert result == 2
    assert json.loads(out)['hookSpecificOutput']['permissionDecisionReason'] == 'hard refusal'
    assert err == 'warning: lint reason\nhard refusal\n'


@pytest.mark.parametrize('result', [None, (1, ''), (False, 'invalid'), (2, 'unavailable')])
def test_standard_does_not_relax_invalid_or_unrun_results(configured, monkeypatch, capsys, result):
    set_profile(configured, 'standard')
    monkeypatch.setattr(hook, 'discover', lambda: [
        Guard('PreToolUse', None, lambda p: result, profile_relaxable=True)])
    code, out, err = replay(configured, monkeypatch, capsys)
    assert code == 2
    assert json.loads(out)['hookSpecificOutput']['permissionDecision'] == 'deny'
    assert err and 'warning:' not in err


def test_invalid_profile_cannot_allow_a_finding(configured, monkeypatch, capsys):
    set_profile(configured, 'unknown')
    monkeypatch.setattr(hook, 'discover', lambda: [
        Guard('PreToolUse', None, lambda p: (1, 'lint'), profile_relaxable=True)])
    code, out, err = replay(configured, monkeypatch, capsys)
    assert code == 2
    assert 'profile' in err and 'warning:' not in err
    assert json.loads(out)['hookSpecificOutput']['permissionDecision'] == 'deny'


def test_direct_check_missing_profile_fails_closed(configured):
    from wuwei import outward
    config = workspace.load_config(configured)
    del config['profile']
    code, reason = outward.check_call({'text': 'Thanks', 'channel': 'Cwork'}, configured, config, {'slack'})
    assert code == 2
    assert reason
