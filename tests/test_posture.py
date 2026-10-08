"""Security posture (#331): one table, one resolver, floors, guard areas and surfaces."""

import pytest

from wuwei import workspace
from wuwei.__main__ import main
from wuwei.workspace import ConfigError

GUARDED = {'integrity': 'block', 'mcp': 'warn', 'publish': 'block', 'records': 'block',
           'outward': 'warn', 'seats': 'warn'}
OBSERVE = {**{area: 'warn' for area in GUARDED}, 'records': 'block'}


def load(raw):
    return workspace.load_config('.', raw=raw)


def test_default_config_is_guarded():
    config = load('')
    assert config['security'] == {'required': False, 'posture': 'guarded',
                                  'areas': {area: '' for area in workspace.AREAS}}
    assert workspace.posture(config) == ('guarded', GUARDED)


def test_postures_and_overrides():
    assert workspace.posture(load('[security]\nposture = "observe"\n')) == ('observe', OBSERVE)
    assert workspace.posture(load('[security]\nposture = "strict"\n')) == (
        'strict', {area: 'block' for area in workspace.AREAS})
    assert workspace.posture(load('[security.areas]\nmcp = "off"\n')) == (
        'guarded', {**GUARDED, 'mcp': 'off'})
    assert workspace.posture(load('[security]\nposture = "strict"\n[guards]\nmode = "shadow"\n')) == (
        'observe', OBSERVE)
    assert workspace.posture(load('[security.areas]\nrecords = "block"\n'))[1] == GUARDED


@pytest.mark.parametrize('raw,key', [('[security]\nposture = "loose"\n', 'security.posture'),
                                     ('[security.areas]\nmcp = "maybe"\n', 'security.areas.mcp')])
def test_invalid_values_name_the_key(raw, key):
    with pytest.raises(ConfigError, match=key):
        load(raw)


@pytest.mark.parametrize('value', ['warn', 'off'])
def test_records_floor(value):
    with pytest.raises(ConfigError, match=r'security\.areas\.records.*floor'):
        load(f'[security.areas]\nrecords = "{value}"\n')


@pytest.fixture
def checked(tmp_path, monkeypatch):
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / '.wuwei').mkdir()

    def check(raw, capsys):
        (tmp_path / '.wuwei/config.toml').write_text('[adapters]\ncode_host="none"\n' + raw)
        code = main(['config', 'check'])
        return code, capsys.readouterr()
    return check


def test_config_check_floor_finding(checked, capsys):
    code, out = checked('[security.areas]\nrecords = "warn"\n', capsys)
    assert code == 1
    assert 'security.areas.records' in out.err and 'floor' in out.err


def test_config_check_mcp_block_line(checked, capsys):
    # #351: a non-empty scanner.mcp.block is named against the posture default; reported only.
    plain, _ = checked('[security]\nposture = "observe"\n', capsys)
    code, out = checked('[security]\nposture = "observe"\n[scanner.mcp]\nblock = ["critical"]\n', capsys)
    [line] = [line for line in out.out.splitlines() if 'scanner.mcp.block' in line]
    assert code == plain and 'scanner.mcp.block (critical)' in line and 'no effect under observe' in line
    _, out = checked('[scanner.mcp]\nblock = ["critical"]\n', capsys)
    [line] = [line for line in out.out.splitlines() if 'scanner.mcp.block' in line]
    assert 'on top of the guarded default' in line and 'no effect' not in line
    _, out = checked('[security.areas]\nmcp = "off"\n[scanner.mcp]\nblock = ["critical"]\n', capsys)
    assert 'no effect under guarded (mcp: off)' in out.out
    _, out = checked('', capsys)
    assert 'scanner.mcp.block' not in out.out


def test_config_check_prints_posture(checked, capsys):
    plain, _ = checked('', capsys)
    code, out = checked('[security.areas]\nmcp = "off"\n', capsys)
    assert code == plain
    assert 'Posture: guarded (from security.posture)\n' in out.out
    assert '  mcp: off (security.areas)\n' in out.out
    assert '  records: block (floor)\n' in out.out
    assert '  seats: warn\n' in out.out
    assert 'owner-only actions ask on a card below strict' in out.out  # #530
    assert 'block in every posture' not in out.out
    assert 'deprecated' not in out.out
    code, out = checked('[security]\nposture = "guarded"\n[guards]\nmode = "shadow"\n', capsys)
    assert code == plain
    assert ('Posture: observe (from guards.mode = "shadow", deprecated; run doctor --fix)\n'
            in out.out)
    assert len([line for line in out.out.splitlines() if 'deprecated' in line]) == 1
    assert not [line for line in out.out.splitlines() if 'guarded' in line]
    code, out = checked('[security]\nposture = "observe"\n', capsys)
    assert 'Posture: observe (from security.posture)\n' in out.out and 'deprecated' not in out.out


def test_posture_source():
    assert workspace.posture_source(load('')) == 'security.posture'
    assert (workspace.posture_source(load('[guards]\nmode = "shadow"\n'))
            == 'guards.mode = "shadow", deprecated; run doctor --fix')


def stub(module, name='check'):
    def check(payload):
        return 0, ''
    check.__module__, check.__name__ = f'wuwei.guards.{module}', name
    return check


def test_guard_areas_table():
    from wuwei import guards
    assert {key for key in guards.AREAS if '.' not in key} == set(guards.MODULES)
    for key, area in guards.AREAS.items():
        assert area in workspace.AREAS or (key in ('agent_launch.check_mcp', 'spec') and area is None)
    from importlib import import_module
    for key in guards.OWNER_ONLY:
        module, _, function = key.partition('.')
        assert module in guards.MODULES
        assert not function or callable(getattr(import_module(f'wuwei.guards.{module}'), function))
    assert guards.level(stub('agent_launch', 'check_mcp'), OBSERVE) == (
        'agent_launch', None, 'block', '')
    for check in (stub('outward', 'check_tier'), stub('deploy'), stub('pr')):
        decided = guards.level(check, OBSERVE)
        assert decided[2] == 'block' and 'owner-only' in decided[3]
    decided = guards.level(stub('protect_state', 'check_file'), OBSERVE)
    assert decided[:3] == ('protect_state', 'records', 'block') and 'floor' in decided[3]
    assert guards.level(stub('commit_push'), OBSERVE) == (
        'commit_push', 'publish', 'warn', 'posture: publish = warn (set security.areas.publish)')
    assert guards.level(stub('outward', 'check_call'), OBSERVE)[2] == 'warn'
    assert guards.level(stub('agent_launch'), GUARDED)[1:3] == ('seats', 'warn')
    assert guards.level(lambda payload: (1, 'x'), GUARDED)[1:] == (None, 'block', '')
    # #471: the owner-question citation check warns outside strict; record writes keep the floor.
    for levels in (GUARDED, OBSERVE):
        assert guards.level(stub('decision', 'check_question'), levels)[1:3] == ('outward', 'warn')
    strict = {area: 'block' for area in workspace.AREAS}
    assert guards.level(stub('decision', 'check_question'), strict)[2] == 'block'
    assert guards.level(stub('decision', 'check_write'), GUARDED)[:3] == ('decision', 'records', 'block')


@pytest.mark.parametrize('posture,tier', [('guarded', 'nudge'), ('strict', 'nudge'),
                                          ('observe', 'silent'), (None, 'silent')])
def test_would_refuse_tier(posture, tier):
    from wuwei.signal import classify
    payload = {'guard': 'outward', 'reason': 'r'} | ({'posture': posture} if posture else {})
    assert classify({'kind': 'guard.would_refuse', 'payload': payload}, {})[0] == tier


def test_warnings_outside_observe_nudge_once_per_guard(tmp_path, monkeypatch):
    from wuwei import state
    from wuwei.commands import status
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00Z')
    state._write_state(lambda data: None, tmp_path, reserved=False)
    directory = workspace.day_dir(tmp_path)
    for guard, area in [('outward', 'outward')] * 3 + [('agent_launch', 'seats')]:
        state.append_event('guard.would_refuse', {
            'guard': guard, 'area': area, 'level': 'warn', 'posture': 'guarded', 'reason': 'r',
            'target': 't', 'session': 's', 'item': None}, tmp_path)
    rows = [row for row in status.attention(directory) if row['source'] == 'guard.would_refuse']
    assert [row['tier'] for row in rows] == ['nudge', 'nudge']
    assert {row['reason'] for row in rows} == {'outward: r (warn: security.areas.outward)',
                                               'agent_launch: r (warn: security.areas.seats)'}


def fixed(module, code, reason):
    def check(payload):
        return code, reason
    check.__module__ = f'wuwei.guards.{module}'
    return check


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
    text = 'commit_push specific\nposture: publish = block (set security.areas.publish)'
    assert code == 2 and out.err == text + '\n'
    assert json.loads(out.out)['hookSpecificOutput']['permissionDecisionReason'] == text
    [event] = events(guarded, 'hook.refusal')
    assert event['reason'] == text
    assert [row['guard'] for row in event['refusals']] == ['commit_push', 'deploy', 'integrity']


def test_one_reason_integrity_last(guarded, monkeypatch, capsys):
    code, out = hook_call(guarded, monkeypatch, capsys, guards=[
        fixed('integrity', 2, 'integrity gate'), fixed('deploy', 2, 'deploy generic')])
    assert out.err.splitlines() == ['deploy generic']  # #530: no owner-only line below strict
    code, out = hook_call(guarded, monkeypatch, capsys, guards=[fixed('integrity', 2, 'integrity gate')])
    assert out.err.splitlines()[0] == 'integrity gate'


def test_publish_reason_has_no_posture_line(guarded, monkeypatch, capsys):
    # #478: an owner-only deploy reason names its card; the hook adds no posture line.
    import json
    reason = ('publish: gh workflow run deploy.yml on fixture-org/app is a deploy (deploy.workflows), '
              'owner-only under guarded; the owner decides: bin/wuwei decision show D-1 --widget')
    code, out = hook_call(guarded, monkeypatch, capsys, guards=[fixed('deploy', 1, reason)])
    assert code == 2 and out.err == reason + '\n'
    assert json.loads(out.out)['hookSpecificOutput']['permissionDecisionReason'] == reason


def test_one_reason_observe_keeps_floor(guarded, monkeypatch, capsys):
    (guarded / '.wuwei/config.toml').write_text('[security]\nposture = "observe"\n')
    code, out = hook_call(guarded, monkeypatch, capsys, guards=[
        fixed('commit_push', 1, 'commit_push specific'), fixed('deploy', 2, 'deploy generic')])
    assert code == 2 and out.err.splitlines() == ['deploy generic']
    [event] = events(guarded, 'guard.would_refuse')
    assert event['reason'] == 'commit_push specific'


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


def test_opaque_refusals_give_one_warning(guarded, monkeypatch, capsys):
    # #530: owner-only guards that could not read an opaque call warn once under guarded.
    (guarded / 'loop.sh').write_text('gh pr view 7\n')
    code, out = hook_call(guarded, monkeypatch, capsys, command='bash loop.sh', guards=[
        fixed('deploy', 2, 'deploy: could not inspect'), fixed('pr', 2, 'PR guard could not run'),
        fixed('commit_push', 2, 'unparsed')])
    assert code == 0, out.err
    [event] = events(guarded, 'guard.would_refuse')
    assert event['reason'].startswith('opaque: script loop.sh;') and event['level'] == 'warn'


def test_opaque_reason_error_enforces(guarded, monkeypatch, capsys):
    from wuwei import shell
    def broken(*args, **kwargs):
        raise RuntimeError('boom')
    monkeypatch.setattr(shell, 'unreadable', broken)
    code, out = hook_call(guarded, monkeypatch, capsys, command='bash loop.sh',
                          guards=[fixed('deploy', 2, 'deploy: could not inspect')])
    assert code == 2 and 'deploy: could not inspect' in out.err


def test_opaque_records_floor_still_blocks(guarded, monkeypatch, capsys):
    (guarded / '.wuwei/config.toml').write_text('[security]\nposture = "observe"\n')
    code, out = hook_call(guarded, monkeypatch, capsys, command='bash loop.sh',
                          guards=[fixed('protect_state', 2, 'state write')])
    assert code == 2 and 'state write' in out.err


@pytest.mark.parametrize('posture', ['observe', 'guarded', 'strict'])
def test_pr_raise_refusals_follow_publish(guarded, monkeypatch, capsys, posture):
    # #530: a PR create refusal follows the publish area; the merge policy stays owner-only.
    from wuwei.guards import NO_REVIEWER, RAISE
    (guarded / '.wuwei/config.toml').write_text(f'[security]\nposture = "{posture}"\n')
    raise_reason = RAISE + 'pre-PR gates not passed'
    code, out = hook_call(guarded, monkeypatch, capsys, command='gh pr create',
                          guards=[fixed('pr', 1, raise_reason)])
    if posture == 'observe':
        assert code == 0 and events(guarded, 'guard.would_refuse')[-1]['reason'] == raise_reason
    else:
        assert code == 2 and out.err.splitlines() == [
            raise_reason, 'posture: publish = block (set security.areas.publish)']
    code, out = hook_call(guarded, monkeypatch, capsys, command='gh pr create',
                          guards=[fixed('pr', 1, NO_REVIEWER)])
    assert (code, out.err) == ((0, '') if posture == 'observe' else (2, NO_REVIEWER + '\n'))
    code, out = hook_call(guarded, monkeypatch, capsys, command='gh pr merge 7',
                          guards=[fixed('pr', 1, 'merge policy requires an explicit PR')])
    assert code == 2 and 'owner-only' in out.err
    card = 'publish: git push on example/project has no recorded evidence; the owner decides'
    code, out = hook_call(guarded, monkeypatch, capsys, guards=[fixed('commit_push', 1, card)])
    if posture != 'observe':
        assert out.err == card + '\n'


def test_owner_only_line_below_strict(tmp_path):
    # #530: below strict an owner-only refusal names its card or its fix, so the hook drops the
    # owner-only line, except the #524 merge family; the records floor is labelled in every posture.
    from wuwei.commands import hook
    (tmp_path / '.wuwei').mkdir()
    merge = 'merge policy requires an explicit PR; use wuwei merge <pr>'
    owner = 'posture: publish = block (owner-only action; no setting lowers it)'
    records = 'posture: records = block (floor; no setting lowers it)'
    canary = fixed('outward', 1, 'outward: security.canary')
    canary.__name__ = 'check_tier'
    marker = ('owner disposition markers must be posted by the owner; '
              'ask the owner to post the marker comment')
    rows = [(fixed('deploy', 1, 'deploy generic'), 'deploy generic', 1),
            (fixed('pr', 1, 'other'), 'other', 1), (fixed('pr', 1, merge), merge, 1),
            (canary, 'outward: security.canary', 1), (fixed('pr', 1, marker), marker, 1)]
    for posture in ('observe', 'guarded', 'strict'):
        (tmp_path / '.wuwei/config.toml').write_text(f'[security]\nposture = "{posture}"\n')
        below = '' if posture != 'strict' else owner
        assert hook.posture({}, rows, tmp_path) == [
            ('deploy', 'deploy generic', below, 1), ('pr', 'other', below, 1),
            ('pr', merge, owner, 1), ('outward', 'outward: security.canary', records, 1),
            ('pr', marker, records, 1)]


def test_orientation_says_owner_only_asks_below_strict():
    # #530: no orientation text says owner-only actions refuse with no way through below strict.
    from wuwei import guide
    from wuwei.commands.next import POSTURES
    for text in (POSTURES['observe'], POSTURES['guarded'], guide.text()):
        assert 'on a card' in text and 'merges and approvals stay owner-only' in text, text
        assert 'owner-only commands are refused in every posture' not in text
