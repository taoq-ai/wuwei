"""Workspace-only credentials and value-free readiness diagnostics."""

from argparse import Namespace
import io
import json
import os
from pathlib import Path
import plistlib
import shlex
import subprocess
import sys
from types import SimpleNamespace

import pytest

from wuwei import registry, state, workspace
from wuwei.__main__ import main

ROOT = Path(__file__).resolve().parents[1]
KEY = 'opaque-example-credential'
VARIABLES = ('LINEAR_API_KEY', 'SLACK_BOT_TOKEN', 'SLACK_USER_TOKEN',
             'SLACK_OWNER_DM_CHANNEL', 'GREPTILE_API_KEY', 'WUWEI_CALENDAR_URL')


@pytest.fixture
def case(tmp_path, monkeypatch):
    monkeypatch.setattr(os, 'environ', os.environ.copy())
    for name in (*VARIABLES, 'WUWEI_WORKSPACE'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)
    directory = tmp_path / '.wuwei'
    directory.mkdir()
    (directory / 'config.toml').write_text('[adapters]\ncode_host="none"\ntracker="linear"\n')
    return tmp_path


def write_env(root, content, mode=0o600):
    path = root / '.wuwei/env'
    path.write_text(content)
    path.chmod(mode)
    return path


def test_linear_authenticates_from_file(case, monkeypatch, capsys):
    from adapters.tracker import linear
    write_env(case, 'LINEAR_API_KEY=' + KEY + '\n')
    received = []

    def request(url, token, payload, **kwargs):
        received.append(token)
        return {'data': {'issue': {'history': {'nodes': [], 'pageInfo': {'hasNextPage': False}}}}}

    monkeypatch.setattr(linear, 'request', request)
    from wuwei.commands import config
    def run(args):
        result = linear.history('EX-1')
        return result.exit
    monkeypatch.setattr(config, 'run', run)
    assert main(['config', 'check']) == 0
    assert received == [KEY]
    assert KEY not in str(capsys.readouterr())


def test_literal_file_and_environment_precedence(case, monkeypatch):
    from wuwei.commands import config
    write_env(case, '# comment\n\nLINEAR_API_KEY="file-value"\nEXAMPLE=$(touch never) # literal\n')
    monkeypatch.setenv('LINEAR_API_KEY', KEY)
    observed = {}
    def run(args):
        observed.update({name: os.environ.get(name) for name in ('LINEAR_API_KEY', 'EXAMPLE')})
        return 0
    monkeypatch.setattr(config, 'run', run)
    assert main(['config', 'check']) == 0
    assert observed == {'LINEAR_API_KEY': KEY, 'EXAMPLE': '$(touch never) # literal'}
    assert not (case / 'never').exists()


@pytest.mark.parametrize('runner', ['codex', 'fast-check'])
def test_seat_children_do_not_inherit_credentials(tmp_path, monkeypatch, runner):
    from adapters.checks import local
    from adapters.runtime import codex
    from wuwei import env

    directory = tmp_path / '.wuwei'
    directory.mkdir()
    for name in env.CREDENTIALS:
        monkeypatch.setenv(name, KEY)
    monkeypatch.delenv('LINEAR_API_KEY')
    monkeypatch.delenv('PRIVATE_FILE_VALUE', raising=False)
    monkeypatch.setenv('PRIVATE_OVERRIDE', KEY)
    monkeypatch.setenv('PUBLIC_VALUE', 'keep-me')
    write_env(tmp_path, f'LINEAR_API_KEY={KEY}\nPRIVATE_FILE_VALUE={KEY}\n'
              'PRIVATE_OVERRIDE=file-default\n')
    private = (*env.CREDENTIALS, 'PRIVATE_FILE_VALUE', 'PRIVATE_OVERRIDE')
    names = (*private, 'PUBLIC_VALUE', 'PATH')
    if runner == 'fast-check':
        monkeypatch.setenv('GIT_DIR', '/invalid/git-dir')
        names += ('GIT_DIR',)
    probe = tmp_path / 'probe.py'
    probe.write_text(
        'import json, os\nfrom pathlib import Path\n'
        f'names = {names!r}\n'
        "Path('observed.json').write_text(json.dumps(\n"
        '    {k: os.environ[k] for k in names if k in os.environ}))\n'
        "print(json.dumps({'jobId': 'fixture-job', 'workspaceRoot': os.getcwd()}))\n")
    command = [sys.executable, str(probe)]
    (directory / 'config.toml').write_text('[codex]\ncommand=' + json.dumps(command) + '\n')
    with env.session():
        env.load(tmp_path)
        if runner == 'codex':
            result = codex.dispatch('builder', str(probe), str(tmp_path), True, root=tmp_path)
        else:
            result = local.run(tmp_path, shlex.join(command), root=tmp_path)
        assert result.exit == 0, result.reason
        assert all(os.environ[name] == KEY for name in private)
        observed = json.loads((tmp_path / 'observed.json').read_text())
        assert observed == {'PUBLIC_VALUE': 'keep-me', 'PATH': os.environ['PATH']}


@pytest.mark.parametrize('problem', ['mode', 'syntax', 'symlink', 'directory', 'nul', 'encoding'])
def test_invalid_env_fails_without_values(case, capsys, problem):
    path = write_env(case, 'LINEAR_API_KEY=' + KEY + '\n')
    if problem == 'mode':
        path.chmod(0o644)
    elif problem == 'syntax':
        path.write_text(KEY + '\n')
    elif problem == 'symlink':
        path.rename(case / 'private')
        path.symlink_to(case / 'private')
    elif problem == 'directory':
        path.unlink()
        path.mkdir()
    elif problem == 'nul':
        path.write_text('LINEAR_API_KEY=' + KEY + '\0\n')
    else:
        path.write_bytes(b'LINEAR_API_KEY=\xff')
    assert main(['config', 'check']) == 2
    output = str(capsys.readouterr())
    assert KEY not in output
    assert '.wuwei/env' in output


def test_known_values_redacted_before_truncation_and_persistence(case, monkeypatch, capsys):
    from wuwei.commands import config
    from wuwei.redact import redact
    write_env(case, 'LINEAR_API_KEY=' + KEY + '\nCUSTOM=unrecognized-private-value\n')
    def run(args):
        state.append_event('example', {KEY: 'prefix ' + KEY}, case)
        state.append_jsonl(workspace.day_dir(case) / 'traces.jsonl',
                           {'result': 'unrecognized-private-value'})
        assert KEY[:10] not in redact('x' * 505 + KEY + 'x' * 2000)
        print(KEY)
        print(json.dumps({'reason': 'unrecognized-private-value'}), file=sys.stderr)
        raise ValueError('refusal ' + KEY)
    monkeypatch.setattr(config, 'run', run)
    assert main(['config', 'check']) == 2
    output = str(capsys.readouterr())
    persisted = ''.join(p.read_text() for p in workspace.day_dir(case).glob('*.jsonl'))
    for secret in (KEY, 'unrecognized-private-value'):
        assert secret not in output + persisted
    assert '[REDACTED]' in output and '[REDACTED]' in persisted


def test_env_write_payload_is_private_even_for_new_values():
    from wuwei.redact import redact
    result = redact({'file_path': '.wuwei/env', 'content': 'CUSTOM=novel-value'})
    assert result['content'] == '[REDACTED]'


def test_hook_loads_payload_workspace_and_keeps_outside_clean(case, monkeypatch, capsys):
    from wuwei.commands import hook
    write_env(case, 'LINEAR_API_KEY=' + KEY + '\n')
    outside = case.parent / 'outside'
    outside.mkdir()
    monkeypatch.chdir(outside)
    payload = {'session_id': 'example', 'transcript_path': 'trace.jsonl',
               'cwd': str(case), 'hook_event_name': 'PreToolUse',
               'tool_name': 'Bash', 'tool_input': {'command': 'ls'}}
    observed = []
    def check(payload):
        observed.append(os.environ.get('LINEAR_API_KEY'))
        return 2, 'refused ' + KEY
    monkeypatch.setattr(hook, 'discover', lambda: [SimpleNamespace(
        event='PreToolUse', matcher=None, profile_relaxable=False, check=check)])
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(payload)))
    assert main(['hook', 'PreToolUse']) == 2
    assert observed == [KEY]
    assert KEY not in str(capsys.readouterr())
    write_env(case, 'broken', 0o644)
    monkeypatch.setenv('WUWEI_WORKSPACE', str(case))
    payload['cwd'] = str(outside)
    monkeypatch.setattr(hook, 'discover', lambda: [])
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(payload)))
    assert main(['hook', 'PreToolUse']) == 0


def test_init_and_upgrade_provision_private_env(tmp_path, monkeypatch):
    from wuwei.commands import init
    monkeypatch.setattr(init, '_register_mcp', lambda root: 0)
    args = Namespace(path=str(tmp_path), upgrade=False, dry_run=False)
    assert init.run(args) == 0
    path = tmp_path / '.wuwei/env'
    assert path.read_text() == ''
    assert path.stat().st_mode & 0o777 == 0o600
    ignore = path.parent / '.gitignore'
    assert '/env' in ignore.read_text().splitlines()
    path.unlink()
    ignore.write_text('/owner-file\n')
    args.upgrade = True
    args.dry_run = True
    assert init.run(args) == 0
    assert not path.exists() and ignore.read_text() == '/owner-file\n'
    args.dry_run = False
    assert init.run(args) == 0
    assert path.stat().st_mode & 0o777 == 0o600
    path.write_text('LINEAR_API_KEY=' + KEY)
    assert init.run(args) == 0
    assert path.read_text() == 'LINEAR_API_KEY=' + KEY
    assert ignore.read_text().splitlines().count('/env') == 1
    assert '/owner-file' in ignore.read_text()


@pytest.mark.parametrize('entry', ['bin', 'module', 'watch'])
def test_entry_paths(case, entry, monkeypatch):
    write_env(case, 'LINEAR_API_KEY=' + KEY + '\n')
    environment = {**os.environ, 'PYTHONPATH': str(ROOT / 'cli')}
    command = [str(ROOT / 'bin/wuwei')]
    if entry == 'module':
        command = [sys.executable, '-P', '-m', 'wuwei']
    if entry == 'watch':
        from wuwei.commands import watch
        monkeypatch.setattr(watch, 'service_platform', lambda: 'darwin')
        monkeypatch.setattr(registry, 'watch_service', lambda: SimpleNamespace(call=lambda args: None))
        assert watch.run(Namespace(watch_action='install', once=False, dry_run=False)) == 0
        path = next((Path.home() / 'Library/LaunchAgents').glob('*.plist'))
        data = plistlib.loads(path.read_bytes())
        assert data['ProgramArguments'][1:] == ['watch']
        assert KEY not in path.read_text()
        command = data['ProgramArguments'][:1]
        environment.update(data['EnvironmentVariables'])
    result = subprocess.run([*command, 'config', 'check'], cwd=case, env=environment,
                            text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert 'LINEAR_API_KEY: set' in result.stdout
    assert KEY not in result.stdout + result.stderr


@pytest.mark.parametrize('adapter,settings,required', [
    ('tracker="linear"', '', ('LINEAR_API_KEY',)),
    ('chat="slack"', '', ('SLACK_BOT_TOKEN', 'SLACK_USER_TOKEN', 'SLACK_OWNER_DM_CHANNEL')),
    ('review_bot="greptile"', '', ('GREPTILE_API_KEY',)),
    ('calendar="ics"', '', ('WUWEI_CALENDAR_URL',)),
    ('runtime="codex"', '', ('codex.command',)),
])
def test_config_reports_missing_and_set(case, monkeypatch, capsys, adapter, settings, required):
    path = case / '.wuwei/config.toml'
    path.write_text('[adapters]\ncode_host="none"\n' + adapter + '\n' + settings)
    assert main(['config', 'check']) == 1
    output = str(capsys.readouterr())
    assert all(name in output for name in required)
    assert 'missing' in output
    if 'codex.command' in required:
        path.write_text(path.read_text() + '[codex]\ncommand=["' + KEY + '"]\n')
    else:
        write_env(case, '\n'.join(name + '=' + KEY for name in required) + '\n')
    assert main(['config', 'check']) == 0
    output = str(capsys.readouterr())
    assert all(name in output for name in required)
    assert 'set' in output and KEY not in output


@pytest.mark.parametrize('identity,token,expected', [
    ('connector', 'SLACK_BOT_TOKEN', 0), ('connector', 'SLACK_USER_TOKEN', 0),
    ('custom_app', 'SLACK_USER_TOKEN', 1), ('custom_app', 'SLACK_BOT_TOKEN', 0),
])
def test_slack_token_alternatives(case, identity, token, expected, capsys):
    (case / '.wuwei/config.toml').write_text(
        '[adapters]\ncode_host="none"\nchat="slack"\n[chat]\nidentity="' + identity + '"\n')
    write_env(case, token + '=' + KEY + '\nSLACK_OWNER_DM_CHANNEL=private-channel\n')
    assert main(['config', 'check']) == expected
    assert KEY not in str(capsys.readouterr())


@pytest.mark.parametrize('outcome,expected', [(0, 0), (1, 1), ('missing', 2), ('timeout', 2)])
def test_github_auth_through_adapter(case, monkeypatch, capsys, outcome, expected):
    (case / '.wuwei/config.toml').write_text('[adapters]\ncode_host="github"\n')
    calls = []
    def run(argv, **kwargs):
        calls.append(argv)
        if outcome == 'missing':
            raise FileNotFoundError(KEY)
        if outcome == 'timeout':
            raise subprocess.TimeoutExpired(argv, 30, stderr=KEY)
        return SimpleNamespace(returncode=outcome, stdout=KEY, stderr=KEY)
    monkeypatch.setattr(subprocess, 'run', run)
    assert main(['config', 'check']) == expected
    assert calls == [['gh', 'auth', 'status', '--hostname', 'github.com']]
    output = str(capsys.readouterr())
    assert 'gh auth' in output and KEY not in output


def test_missing_tool_takes_priority_over_missing_variable(case, monkeypatch, capsys):
    (case / '.wuwei/config.toml').write_text('[adapters]\ncode_host="github"\ntracker="linear"\n')
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError()))
    assert main(['config', 'check']) == 2
    output = str(capsys.readouterr())
    assert 'gh auth' in output and 'LINEAR_API_KEY: missing' in output


def test_upgrade_loads_credentials_before_adapter_calls(case, monkeypatch):
    from wuwei.commands import init
    write_env(case, 'LINEAR_API_KEY=' + KEY + '\n')
    observed = []
    monkeypatch.setattr(init, '_register_mcp', lambda root: observed.append(
        os.environ.get('LINEAR_API_KEY')) or 0)
    assert main(['init', '--upgrade']) == 0
    assert observed == [KEY]


def test_env_is_loaded_before_argument_errors(case, capsys):
    write_env(case, 'LINEAR_API_KEY=' + KEY + '\n')
    with pytest.raises(SystemExit):
        main(['config', KEY])
    assert KEY not in str(capsys.readouterr())


def test_watch_command_loads_before_tick(case, monkeypatch):
    from wuwei import watch
    write_env(case, 'LINEAR_API_KEY=' + KEY + '\n')
    observed = []
    monkeypatch.setattr(watch, 'tick', lambda root: observed.append(os.environ.get('LINEAR_API_KEY')) or 0)
    assert main(['watch', '--once']) == 0
    assert observed == [KEY]


def test_output_redacts_values_split_across_writes(case, monkeypatch, capsys):
    from wuwei.commands import config
    write_env(case, 'LINEAR_API_KEY=' + KEY + '\n')
    def run(args):
        print(KEY[:8], KEY[8:], sep='')
        sys.stderr.write(KEY[:8])
        sys.stderr.write(KEY[8:])
        return 0
    monkeypatch.setattr(config, 'run', run)
    assert main(['config', 'check']) == 0
    output = capsys.readouterr()
    assert KEY not in output.out + output.err
    assert output.err == '[REDACTED]'


@pytest.mark.parametrize('tool,inputs', [
    ('Write', {'file_path': '.wuwei/env', 'content': 'WUWEI_NOW=changed'}),
    ('Edit', {'file_path': '.wuwei/env', 'old_string': 'old', 'new_string': 'new'}),
    ('Bash', {'command': 'echo WUWEI_NOW=changed > .wuwei/env'}),
])
def test_env_is_protected_like_configuration(case, tool, inputs):
    from wuwei.guards.protect_state import check_file, check_bash
    check = check_bash if tool == 'Bash' else check_file
    code, reason = check({'cwd': str(case), 'tool_name': tool, 'tool_input': inputs})
    assert code == 1, reason


def test_hook_resolves_credentials_despite_legacy_override(case, monkeypatch):
    from wuwei.commands import hook
    legacy = case.parent / 'legacy'
    (legacy / '.wuwei').mkdir(parents=True)
    (legacy / '.wuwei/config.toml').write_text('')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(legacy))
    write_env(case, 'LINEAR_API_KEY=' + KEY + '\n')
    payload = {'session_id': 'example', 'transcript_path': 'trace.jsonl',
               'cwd': str(case), 'hook_event_name': 'PreToolUse',
               'tool_name': 'Bash', 'tool_input': {'command': 'ls'}}
    observed = []
    monkeypatch.setattr(hook, 'discover', lambda: [SimpleNamespace(
        event='PreToolUse', matcher=None, profile_relaxable=False,
        check=lambda payload: (observed.append(os.environ.get('LINEAR_API_KEY')) or 0, ''))])
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(payload)))
    assert main(['hook', 'PreToolUse']) == 0
    assert observed == [KEY]
