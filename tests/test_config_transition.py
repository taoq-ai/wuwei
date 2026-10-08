"""Issue 353: keys from a newer template warn, and the owner is told to restart Claude Code."""

import io
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from wuwei import workspace

ROOT = Path(__file__).resolve().parents[1]
# No security material in these fixtures, so the outward guard has nothing to read.
TEMPLATE = (ROOT / 'templates/workspace/config.toml').read_text().replace('required = true', 'required = false')
TYPO = TEMPLATE.replace('block = ["critical"]\n', 'block = ["critical"]\nblok = ["high"]\n')
STRICT = TYPO.replace('posture = "guarded"', 'posture = "strict"')


def typo_line(text):
    return text.splitlines().index('blok = ["high"]') + 1


WARNING = 'unknown key scanner.mcp.blok at line {}; did you mean scanner.mcp.block?'


@pytest.fixture
def ws(tmp_path, monkeypatch):
    from fakes.integrity import seed
    root = tmp_path / 'ws'
    (root / '.wuwei').mkdir(parents=True)
    (root / '.wuwei/config.toml').write_text(TYPO)
    seed(root)
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    return root


def write(root, text):
    (root / '.wuwei/config.toml').write_text(text)


def replay(monkeypatch, capsys, root, session='test'):
    from wuwei.commands import hook
    payload = {'session_id': session, 'transcript_path': str(root / 'transcript.jsonl'),
               'cwd': str(root), 'hook_event_name': 'PreToolUse',
               'tool_name': 'Bash', 'tool_input': {'command': 'ls'}}
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(payload)))
    capsys.readouterr()
    code = hook.run(SimpleNamespace(event='PreToolUse'))
    return code, capsys.readouterr().out


def test_unknown_key_warns_with_the_nearest_key(ws):
    found = []
    # #345 leaves block unset in the template, so the guarded posture default applies.
    assert workspace.load_config(ws, warnings=found)['scanner']['mcp']['block'] == []
    assert found == ['config.toml: ' + WARNING.format(typo_line(TYPO))]
    again = []
    workspace.load_config(ws, warnings=again)  # the memo keeps the warnings
    assert again == found


def test_strict_refuses_the_unknown_key(ws):
    write(ws, STRICT)
    with pytest.raises(workspace.ConfigError) as caught:
        workspace.load_config(ws)
    assert str(caught.value) == 'config.toml: ' + WARNING.format(typo_line(STRICT)) + '; run bin/wuwei config check after the fix'


def test_strict_without_a_near_key_says_remove_it(ws):
    write(ws, 'nonsense = 1\n[security]\nposture = "strict"\n')
    with pytest.raises(workspace.ConfigError) as caught:
        workspace.load_config(ws)
    assert 'unknown key nonsense at line 1; remove it or use a documented key' in str(caught.value)


@pytest.mark.parametrize('text', [
    TYPO,
    TYPO.replace('posture = "guarded"', 'posture = "observe"'),
    TYPO.replace('[guards]\n', '[guards]\nmode = "shadow"\n'),
], ids=['guarded', 'observe', 'shadow'])
def test_tool_calls_pass_below_strict(ws, monkeypatch, capsys, text):
    write(ws, text)
    code, out = replay(monkeypatch, capsys, ws)
    assert code == 0 and "deny" not in out, out


def test_strict_tool_call_is_refused(ws, monkeypatch, capsys):
    write(ws, STRICT)
    code, out = replay(monkeypatch, capsys, ws)
    assert code == 2 and 'unknown key scanner.mcp.blok' in out


def test_template_version_is_a_documented_key(ws):
    write(ws, TEMPLATE.replace('template_version = ""', 'template_version = "0.1.0"'))
    found = []
    assert workspace.load_config(ws, warnings=found)['template_version'] == '0.1.0'
    assert found == []


def test_config_check_prints_the_warning(ws, monkeypatch, capsys):
    from fakes.code_host import Fake as CodeHost
    from wuwei import registry
    from wuwei.commands import config
    from wuwei.registry import Result
    code_host = CodeHost()
    code_host.auth_status = lambda root=None: Result(0)
    real = registry.load
    monkeypatch.setattr(registry, 'load', lambda kind, cfg: code_host if kind == 'code_host' else real(kind, cfg))
    monkeypatch.setenv('WUWEI_WORKSPACE', str(ws))
    config.run(SimpleNamespace())
    err = capsys.readouterr().err
    assert ('wuwei config check: warning: config.toml: ' + WARNING.format(typo_line(TYPO))) in err


def test_config_check_reports_two_tables(ws, monkeypatch, capsys):
    from fakes.code_host import Fake as CodeHost
    from wuwei import registry
    from wuwei.commands import config
    from wuwei.registry import Result
    code_host = CodeHost()
    code_host.auth_status = lambda root=None: Result(0)
    real = registry.load
    monkeypatch.setattr(registry, 'load', lambda kind, cfg: code_host if kind == 'code_host' else real(kind, cfg))
    monkeypatch.setenv('WUWEI_WORKSPACE', str(ws))
    text = TEMPLATE.replace('[outward]\n', '[outward]\nwork_channels = ["C1"]\n')
    write(ws, text)
    lines = text.splitlines()
    good, bad = lines.index('work_channels = []') + 1, lines.index('work_channels = ["C1"]') + 1
    assert config.run(SimpleNamespace()) == 1
    err = capsys.readouterr().err
    assert (f'wuwei config check: work_channels is set in [outbound] (line {good}) and [outward] '
            f'(line {bad})') in err


def plugin(tmp_path, version, marker=False):
    directory = tmp_path / 'cache' / version
    (directory / '.claude-plugin').mkdir(parents=True)
    (directory / '.claude-plugin/plugin.json').write_text(json.dumps({'name': 'wuwei', 'version': version}))
    if marker:
        (directory / '.in_use').mkdir()
        (directory / '.in_use' / str(os.getpid())).write_text('')
    return directory


@pytest.fixture
def installed(tmp_path, monkeypatch):
    from wuwei import integrity
    directory = plugin(tmp_path, '0.12.0')
    monkeypatch.setattr(integrity, 'PLUGIN', directory)
    return directory


def test_version_and_release(installed):
    from wuwei import integrity
    assert integrity.version() == '0.12.0'
    assert integrity.release('0.13.0') == (0, 13, 0)
    assert integrity.release('') is None and integrity.release('1.x') is None
    (installed / '.claude-plugin/plugin.json').unlink()
    assert integrity.version() == ''


def test_newer_template(installed):
    from wuwei import integrity
    assert integrity.newer_template({'template_version': '0.13.0'}) == ('0.12.0', '0.13.0')
    for template in ('0.12.0', '0.11.0', '', 'dev'):
        assert integrity.newer_template({'template_version': template}) is None


def test_other_versions(tmp_path, monkeypatch):
    from wuwei import integrity
    plugin(tmp_path, '0.12.0', marker=True)
    monkeypatch.setattr(integrity, 'PLUGIN', plugin(tmp_path, '0.13.0', marker=True))
    assert integrity.other_versions() == ['0.12.0']
    for item in (tmp_path / 'cache/0.12.0/.in_use').iterdir():
        item.unlink()
    assert integrity.other_versions() == []
    (tmp_path / 'cache/0.12.0/.in_use').rmdir()
    assert integrity.other_versions() == []


def test_restart_text(tmp_path, installed):
    from wuwei import integrity
    assert integrity.restart({'template_version': '0.12.0'}) == ''
    assert integrity.restart(None) == ''
    assert integrity.restart({'template_version': '0.13.0'}) == (
        'restart Claude Code: hooks 0.12.0 still running (plugin 0.13.0 installed)')
    plugin(tmp_path, '0.11.0', marker=True)
    assert integrity.restart({'template_version': '0.12.0'}) == (
        'restart Claude Code: hooks 0.11.0 still running (plugin 0.12.0 installed)')
    assert integrity.restart(None) == (
        'restart Claude Code: hooks 0.11.0 still running (plugin 0.12.0 installed)')
    plugin(tmp_path, '0.10.0', marker=True)
    assert integrity.restart({'template_version': '0.13.0'}) == (
        'restart Claude Code: hooks 0.10.0, 0.11.0 and 0.12.0 still running (plugin 0.13.0 installed)')


NEWER = STRICT.replace('template_version = ""', 'template_version = "0.13.0"')


def newer_events(root):
    path = workspace.day_dir(root) / 'events.jsonl'
    rows = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    return [row['payload'] for row in rows if row['kind'] == 'config.newer_template']


def test_old_hook_passes_and_records_once_per_session(ws, installed, monkeypatch, capsys):
    write(ws, NEWER)
    for session in ('one', 'one', 'two', 'wuwei-heartbeat'):
        code, out = replay(monkeypatch, capsys, ws, session)
        assert code == 0 and 'deny' not in out, out
    assert newer_events(ws) == [{'plugin': '0.12.0', 'template': '0.13.0', 'session': 'one'},
                                {'plugin': '0.12.0', 'template': '0.13.0', 'session': 'two'}]


def test_same_version_template_still_refuses_under_strict(ws, installed, monkeypatch, capsys):
    write(ws, NEWER.replace('"0.13.0"', '"0.12.0"'))
    code, out = replay(monkeypatch, capsys, ws)
    assert code == 2 and 'unknown key scanner.mcp.blok' in out
    assert newer_events(ws) == []


def test_newer_template_event_is_reserved(ws, monkeypatch, capsys):
    from wuwei.commands import event
    assert event.EVENT_PRODUCERS['config.newer_template'] == 'wuwei hook PreToolUse'


@pytest.fixture
def newest(tmp_path, monkeypatch):
    from wuwei import integrity
    monkeypatch.setattr(integrity, 'PLUGIN', plugin(tmp_path, '0.13.0'))


@pytest.mark.parametrize('before', ['""', '"0.12.0"', '"dev"'])
def test_stamp_raises_the_version(newest, before):
    import tomllib
    from wuwei.commands.init import _stamp
    text = f'cap = 1\ntemplate_version = {before} # kept comment\n[owner]\nname = "x"\n'
    stamped = _stamp(text)
    assert stamped == text.replace(before, '"0.13.0"')


def test_stamp_adds_a_missing_key_at_the_top_level(newest):
    import tomllib
    from wuwei.commands.init import _stamp
    stamped = _stamp('[owner]\nname = "x"\n')
    assert tomllib.loads(stamped) == {'template_version': '0.13.0', 'owner': {'name': 'x'}}


def test_stamp_never_lowers_or_guesses(newest):
    from wuwei import integrity
    from wuwei.commands.init import _stamp
    newer = 'template_version = "0.14.0"\n'
    assert _stamp(newer) == newer
    (integrity.PLUGIN / '.claude-plugin/plugin.json').unlink()
    assert _stamp('cap = 1\n') == 'cap = 1\n'


def upgrade_output(tmp_path, monkeypatch, capsys, dry_run, others):
    from wuwei import integrity
    from wuwei.commands import init
    monkeypatch.setattr(integrity, 'other_versions', lambda: others)
    assert init.run(SimpleNamespace(path=str(tmp_path), upgrade=False, dry_run=False)) == 0
    capsys.readouterr()
    init.run(SimpleNamespace(path=str(tmp_path), upgrade=True, dry_run=dry_run))
    return capsys.readouterr().out.splitlines()


def test_upgrade_ends_with_the_restart_line(tmp_path, monkeypatch, capsys):
    from wuwei import integrity
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    assert upgrade_output(tmp_path, monkeypatch, capsys, False, ['0.11.0'])[-1] == integrity.RESTART


@pytest.mark.parametrize('dry_run,others', [(True, ['0.11.0']), (False, [])])
def test_upgrade_restart_line_only_when_needed(tmp_path, monkeypatch, capsys, dry_run, others):
    from wuwei import integrity
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    assert integrity.RESTART not in upgrade_output(tmp_path, monkeypatch, capsys, dry_run, others)


def test_release_notes_carry_the_restart_line():
    from wuwei import integrity
    workflow = (ROOT / '.github/workflows/release.yml').read_text()
    assert 'append_body: true' in workflow and integrity.RESTART in workflow
