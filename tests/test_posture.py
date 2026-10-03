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
    assert 'owner-only actions block in every posture' in out.out
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
        assert area in workspace.AREAS or (key == 'agent_launch.check_mcp' and area is None)
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
