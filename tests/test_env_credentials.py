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
from wuwei.commands.config import PIN_MISSING

ROOT = Path(__file__).resolve().parents[1]
KEY = 'opaque-example-credential'
VARIABLES = ('LINEAR_API_KEY', 'SLACK_BOT_TOKEN', 'SLACK_USER_TOKEN',
             'SLACK_OWNER_DM_CHANNEL', 'GREPTILE_API_KEY', 'WUWEI_CALENDAR_URL',
             'NOTION_TOKEN', 'CONFLUENCE_EMAIL', 'CONFLUENCE_API_TOKEN', 'JIRA_SITE', 'JIRA_EMAIL',
             'JIRA_API_TOKEN', 'GITHUB_TRACKER_TOKEN')


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


def test_env_write_sets_lines_and_keeps_the_rest(case):
    from wuwei import env
    path = case / '.wuwei/env'
    env.write(case, {'SLACK_OWNER_DM_CHANNEL': 'D0123ABC'})
    assert path.read_text() == 'SLACK_OWNER_DM_CHANNEL=D0123ABC\n'
    assert path.stat().st_mode & 0o777 == 0o600
    write_env(case, '# private\nLINEAR_API_KEY=a\nSLACK_BOT_TOKEN=old\n')
    token = 'xoxb-' + 'test-1'
    env.write(case, {'SLACK_BOT_TOKEN': token, 'SLACK_OWNER_DM_CHANNEL': 'D0123ABC'})
    assert path.read_text() == ('# private\nLINEAR_API_KEY=a\nSLACK_BOT_TOKEN=' + token
                                + '\nSLACK_OWNER_DM_CHANNEL=D0123ABC\n')
    assert path.stat().st_mode & 0o777 == 0o600
    with env.session():
        env.load(case)
        assert os.environ['SLACK_BOT_TOKEN'] == token
    before = path.read_text()
    for values in ({'CUSTOM': 'x'}, {'SLACK_BOT_TOKEN': 'a b'}, {'SLACK_BOT_TOKEN': 'a"b'},
                   {'SLACK_BOT_TOKEN': 'a\nb'}, {'SLACK_BOT_TOKEN': ''}):
        with pytest.raises(ValueError):
            env.write(case, values)
    assert path.read_text() == before
    path.unlink()
    (case / 'elsewhere').write_text('')
    path.symlink_to(case / 'elsewhere')
    with pytest.raises(ValueError):
        env.write(case, {'SLACK_OWNER_DM_CHANNEL': 'D0123ABC'})
    assert (case / 'elsewhere').read_text() == ''


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
    ('inbound="slack"', '[control_plane]\nowner="T1/U1"\n',
     ('SLACK_BOT_TOKEN', 'SLACK_USER_TOKEN', 'SLACK_OWNER_DM_CHANNEL')),
    ('review_bot="greptile"', '', ('GREPTILE_API_KEY',)),
    ('calendar="ics"', '', ('WUWEI_CALENDAR_URL',)),
    ('runtime="codex"', '', ('codex.command',)),
    ('', '[docs]\nsystem="notion"\n', ('NOTION_TOKEN',)),
    ('', '[docs]\nsystem="confluence"\n', ('CONFLUENCE_EMAIL', 'CONFLUENCE_API_TOKEN')),
    ('tracker="jira"', '', ('JIRA_SITE', 'JIRA_EMAIL', 'JIRA_API_TOKEN')),
    ('tracker="github"', '', ('GITHUB_TRACKER_TOKEN',)),
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


@pytest.mark.parametrize('name, value, expected', [
    ('GITHUB_TRACKER_TOKEN', 'github_pat_11ABC_def0', ''),
    ('JIRA_API_TOKEN', 'ATATT3xFfGF0-abc_DEF=12AB34CD', ''),
    ('GITHUB_TRACKER_TOKEN', 'gh auth token', 'contains whitespace'),
    ('LINEAR_API_KEY', 'lin_api_one\tlin_api_two', 'contains whitespace'),
    ('GITHUB_TRACKER_TOKEN', '/tmp/token.txt', 'looks like a path'),
    ('GITHUB_TRACKER_TOKEN', '~/token', 'looks like a path'),
    ('NOTION_TOKEN', './secret', 'looks like a path'),
    ('NOTION_TOKEN', '../secret', 'looks like a path'),
    ('GITHUB_TRACKER_TOKEN', '$(gh_auth_token)', 'looks like a command (shell characters)'),
    ('SLACK_BOT_TOKEN', 'xoxb-1|pbcopy', 'looks like a command (shell characters)'),
    ('GH_TOKEN', '"ghp_x', 'looks like a command (shell characters)'),
    ('WUWEI_CALENDAR_URL', 'https://example.test/a b.ics', ''),
    ('JIRA_SITE', 'https://acme.atlassian.net', ''),
    ('JIRA_EMAIL', 'pat@example.test', ''),
])
def test_malformed_names_the_shape_never_the_value(case, monkeypatch, name, value, expected):
    from wuwei import env
    assert env.malformed(name) == ''
    monkeypatch.setenv(name, value)
    assert env.malformed(name) == expected


def test_config_check_under_gh_auth_needs_no_token(case, capsys):
    (case / '.wuwei/config.toml').write_text(
        '[adapters]\ncode_host="none"\ntracker="github"\n[tracker]\nauth="gh"\n')
    assert main(['config', 'check']) == 0
    assert '  tracker.github: gh login (tracker.auth = "gh"; GITHUB_TRACKER_TOKEN not set)' in capsys.readouterr().out
    from wuwei.commands import config
    assert config.missing(workspace.load_config(case)) == []
    write_env(case, 'GITHUB_TRACKER_TOKEN=' + KEY + '\n')
    assert main(['config', 'check']) == 0
    output = capsys.readouterr().out
    assert '  tracker.github: GITHUB_TRACKER_TOKEN: set (used before tracker.auth = "gh")' in output
    assert KEY not in output


def test_config_check_reports_a_malformed_token_without_printing_it(case, capsys):
    (case / '.wuwei/config.toml').write_text('[adapters]\ncode_host="none"\ntracker="github"\n')
    write_env(case, 'GITHUB_TRACKER_TOKEN=gh auth token ' + KEY + '\n')
    assert main(['config', 'check']) == 1
    captured = capsys.readouterr()
    assert 'tracker.github: GITHUB_TRACKER_TOKEN: malformed (contains whitespace)' in captured.out
    assert KEY not in captured.out + captured.err and 'gh auth token' not in captured.out + captured.err


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


REPO = '[[repos]]\nname = "acme/widget"\npath = "repo"\ndefault_branch = "main"\n'


@pytest.fixture
def host(case, monkeypatch):
    from fakes.code_host import Fake
    fake = Fake()
    real = registry.load
    monkeypatch.setattr(registry, 'load', lambda kind, config: fake if kind == 'code_host'
                        else real(kind, config))
    (case / '.wuwei/config.toml').write_text('[adapters]\ncode_host="none"\n' + REPO)
    return fake


def protected(**changes):
    from fakes.replay import recordings
    data = next(c for c in recordings('code_host') if c['operation'] == 'protection')['data']
    return registry.Result(0, {**data, **changes})


CLASSIC_404 = {'exit': 1, 'stderr': 'gh: Not Found (HTTP 404)'}
CLASSIC_LINE = 'acme/widget main: classic protection: none visible (404: unprotected or no admin)'


def check_through_github(case, monkeypatch, steps, extra=''):
    from fakes.replay import install_replay
    (case / '.wuwei/config.toml').write_text('[adapters]\ncode_host="github"\n' + REPO + extra)
    install_replay(monkeypatch, 'gh', [{'exit': 0}, *steps])
    return main(['config', 'check'])


SQUASH = {'stdout': '{"allow_squash_merge": true}'}  # #524: the repository read


def test_classic_404_with_no_rulesets_is_a_finding(case, monkeypatch, capsys):
    assert check_through_github(case, monkeypatch, [CLASSIC_404, {'stdout': '[[]]'}, SQUASH]) == 1
    output = capsys.readouterr().out
    assert CLASSIC_LINE in output
    for line in ('required checks: missing (require status checks on main)',
                 'required reviews: missing', 'force pushes: missing (block force pushes on main)',
                 'deletions: missing (block deletions of main)'):
        assert f'acme/widget main: {line}' in output
    assert 'unmeasured' not in output and 'protected ref' not in output


def test_ruleset_only_protection_is_clean(case, monkeypatch, capsys):
    rules = [{'type': 'required_status_checks', 'parameters': {
                 'strict_required_status_checks_policy': True,
                 'required_status_checks': [{'context': 'unit'}]}},
             {'type': 'pull_request', 'parameters': {
                 'required_approving_review_count': 1, 'dismiss_stale_reviews_on_push': False,
                 'require_code_owner_review': False, 'require_last_push_approval': False,
                 'required_review_thread_resolution': False}},
             {'type': 'non_fast_forward'}, {'type': 'deletion'}]
    steps = [CLASSIC_404, {'stdout': json.dumps([rules])}, SQUASH]
    assert check_through_github(case, monkeypatch, steps, 'review_required_checks = ["unit"]\n') == 0
    output = capsys.readouterr().out
    assert CLASSIC_LINE in output
    for line in ('required checks: ok (unit)', 'required reviews: ok', 'force pushes: ok', 'deletions: ok'):
        assert f'acme/widget main: {line}' in output


def test_invisible_repository_is_unmeasured(case, monkeypatch, capsys):
    assert check_through_github(case, monkeypatch, [CLASSIC_404, CLASSIC_404]) == 2
    assert 'acme/widget main: protection: unmeasured' in capsys.readouterr().out


def test_required_checks_lists_names(host, case, capsys):
    (case / '.wuwei/config.toml').write_text(
        '[adapters]\ncode_host="none"\n' + REPO + 'review_required_checks = ["unit"]\n')
    security, unit = {'name': 'Security', 'app_id': None}, {'name': 'unit', 'app_id': None}
    host.results['protection'] = protected(required_checks=[unit, security])
    assert main(['config', 'check']) == 0
    assert 'required checks: ok (Security, unit)' in capsys.readouterr().out
    host.results['protection'] = protected(required_checks=[security])
    assert main(['config', 'check']) == 1
    assert ('required checks: missing (require status checks on main: unit; required now: Security)'
            in capsys.readouterr().out)


def test_missing_reviews_names_the_review_gate_check(host, capsys):
    checks = [*protected().data['required_checks'], {'name': 'Review Gate', 'app_id': None}]
    host.results['protection'] = protected(approvals=0, required_checks=checks)
    assert main(['config', 'check']) == 1
    assert ('required reviews: missing (require at least 1 approving review on main, or set '
            'shepherd.min_reviewers = 0 for a solo owner; the required check Review Gate '
            '(shepherd.review_gate_check) may be satisfying it)') in capsys.readouterr().out
    host.results['protection'] = protected(approvals=0)
    assert main(['config', 'check']) == 1
    output = capsys.readouterr().out
    assert 'shepherd.min_reviewers = 0 for a solo owner)\n' in output
    assert 'review_gate_check' not in output


def test_protection_without_classic_is_unmeasured(host, capsys):
    data = protected().data
    del data['classic']
    host.results['protection'] = registry.Result(0, data)
    assert main(['config', 'check']) == 2
    assert 'protection: unmeasured' in capsys.readouterr().out


def test_unreadable_protection_is_unmeasured(host, capsys):
    host.results['protection'] = registry.Result(2, None, 'github.protection: could not run: gh exited 1')
    assert main(['config', 'check']) == 2
    output = capsys.readouterr()
    assert 'acme/widget main: protection: unmeasured' in output.out
    assert 'gh exited 1' in output.err


def test_fully_protected_branch_is_clean(host, capsys):
    host.results['protection'] = protected()
    assert main(['config', 'check']) == 0
    output = capsys.readouterr().out
    for name in ('protected ref', 'required checks', 'required reviews', 'force pushes', 'deletions'):
        assert f'acme/widget main: {name}: ok' in output


@pytest.mark.parametrize('changes,extra,line', [
    ({'required_checks': []}, '', 'required checks: missing'),
    ({}, 'review_required_checks = ["unit"]\n', 'required checks: missing (require status checks on main: unit; required now: lint, tests)'),
    ({'approvals': 0}, '', 'required reviews: missing'),
    ({'allow_force_pushes': True}, '', 'force pushes: missing (block force pushes on main)'),
    ({'allow_deletions': True}, '', 'deletions: missing (block deletions of main)'),
])
def test_each_protection_gap_is_a_finding(host, case, capsys, changes, extra, line):
    (case / '.wuwei/config.toml').write_text('[adapters]\ncode_host="none"\n' + REPO + extra)
    host.results['protection'] = protected(**changes)
    assert main(['config', 'check']) == 1
    assert f'acme/widget main: {line}' in capsys.readouterr().out


URL_LINE = 'acme/widget main: fix in https://github.com/acme/widget/settings/branches'


def gh_api(output):
    import shlex
    lines = [line for line in output.splitlines() if 'or run in your own terminal: ' in line]
    assert len(lines) <= 1, lines
    return shlex.split(lines[0].split('or run in your own terminal: ', 1)[1]) if lines else None


@pytest.mark.parametrize('extra,expected,absent', [
    ('', ['required_pull_request_reviews[required_approving_review_count]=1', 'required_status_checks=null'],
     'required_status_checks[strict]=false'),
    ('review_required_checks = ["unit"]\n', ['required_status_checks[contexts][]=unit'],
     'required_status_checks=null'),
    ('[shepherd]\nmin_reviewers = 0\n', ['required_pull_request_reviews=null'],
     'required_pull_request_reviews[required_approving_review_count]=1'),
])
def test_unprotected_branch_prints_the_fix(host, case, capsys, extra, expected, absent):
    config = REPO + extra if extra.startswith('review') else extra + REPO
    (case / '.wuwei/config.toml').write_text('[adapters]\ncode_host="none"\n' + config)
    host.results['protection'] = protected(classic=False, approvals=0, required_checks=[],
                                           allow_force_pushes=None, allow_deletions=None)
    assert main(['config', 'check']) == 1
    output = capsys.readouterr().out
    assert URL_LINE in output
    argv = gh_api(output)
    assert argv[:5] == ['gh', 'api', '-X', 'PUT', 'repos/acme/widget/branches/main/protection']
    for value in ('allow_force_pushes=false', 'allow_deletions=false', *expected):
        assert value in argv
    assert absent not in argv


def test_protected_branch_prints_only_the_url(host, capsys):
    host.results['protection'] = protected(approvals=0)
    assert main(['config', 'check']) == 1
    output = capsys.readouterr().out
    assert URL_LINE in output and gh_api(output) is None
    host.results['protection'] = protected()
    assert main(['config', 'check']) == 0
    output = capsys.readouterr().out
    assert 'settings/branches' not in output and gh_api(output) is None


def test_solo_owner_exemption(host, case, capsys):
    (case / '.wuwei/config.toml').write_text(
        '[adapters]\ncode_host="none"\n[shepherd]\nmin_reviewers = 0\n' + REPO)
    host.results['protection'] = protected(approvals=0)
    assert main(['config', 'check']) == 0
    assert 'required reviews: ok (solo owner: shepherd.min_reviewers = 0)' in capsys.readouterr().out


def test_malformed_protection_is_unmeasured(host, capsys):
    data = protected().data
    del data['allow_deletions']
    host.results['protection'] = registry.Result(0, data)
    assert main(['config', 'check']) == 2
    assert 'protection: unmeasured' in capsys.readouterr().out


def test_unmeasured_outranks_missing_across_repositories(host, case, capsys):
    (case / '.wuwei/config.toml').write_text('[adapters]\ncode_host="none"\n' + REPO +
                                             REPO.replace('acme/widget', 'acme/other').replace('"repo"', '"other"'))
    results = iter([protected(approvals=0),
                    registry.Result(2, None, 'gh exited 1')])
    host.protection = lambda repo, branch, root=None: next(results)
    assert main(['config', 'check']) == 2


def test_write_token_in_env_file_is_a_finding(host, case, capsys):
    host.results['protection'] = protected()
    host.results['token_scopes'] = registry.Result(0, {'scopes': ['repo']})
    write_env(case, 'GH_TOKEN=' + KEY + '\n')
    assert main(['config', 'check']) == 1
    output = str(capsys.readouterr())
    assert 'GH_TOKEN (.wuwei/env): write scopes repo' in output and KEY not in output
    assert ('token_scopes', ('GH_TOKEN',), None) in host.calls


def test_env_file_token_shadowed_by_environment_is_unmeasured(host, case, monkeypatch, capsys):
    host.results['protection'] = protected()
    host.results['token_scopes'] = registry.Result(0, {'scopes': ['read:org']})
    write_env(case, 'GH_TOKEN=' + KEY + '\n')
    monkeypatch.setenv('GH_TOKEN', 'shellreadonly')
    assert main(['config', 'check']) == 2
    captured = capsys.readouterr()
    assert 'GH_TOKEN (.wuwei/env): unmeasured' in captured.out
    assert 'shadows' in captured.err
    assert KEY not in str(captured) and 'shellreadonly' not in str(captured)


def test_write_token_in_environment_is_a_finding(host, monkeypatch, capsys):
    host.results['protection'] = protected()
    host.results['token_scopes'] = registry.Result(0, {'scopes': ['repo', 'workflow']})
    monkeypatch.setenv('GITHUB_TOKEN', KEY)
    assert main(['config', 'check']) == 1
    output = str(capsys.readouterr())
    assert 'GITHUB_TOKEN (the environment): write scopes repo, workflow' in output
    assert KEY not in output


@pytest.mark.parametrize('result,expected,text', [
    (registry.Result(0, {'scopes': ['read:org']}), 0, 'GH_TOKEN (the environment): read-only'),
    (registry.Result(2, None, 'token scopes unmeasured'), 2, 'GH_TOKEN (the environment): unmeasured'),
])
def test_token_scope_outcomes(host, monkeypatch, capsys, result, expected, text):
    host.results['protection'] = protected()
    host.results['token_scopes'] = result
    monkeypatch.setenv('GH_TOKEN', KEY)
    assert main(['config', 'check']) == expected
    assert text in capsys.readouterr().out


def test_no_tokens_is_clean_without_a_scope_read(host, capsys):
    host.results['protection'] = protected()
    assert main(['config', 'check']) == 0
    output = capsys.readouterr().out
    assert 'GH_TOKEN: not set' in output and 'GITHUB_TOKEN: not set' in output
    assert all(call[0] != 'token_scopes' for call in host.calls)


def test_fresh_init_prints_publishing_layout_once(tmp_path, monkeypatch, capsys):
    from wuwei.commands import init
    monkeypatch.setattr(init, '_register_mcp', lambda root: 0)
    assert main(['init', str(tmp_path)]) == 0
    output = capsys.readouterr().out
    assert 'default_branch' in output and 'GH_TOKEN' in output and 'wuwei config check' in output
    assert main(['init', str(tmp_path), '--upgrade']) == 0
    assert 'wuwei config check' not in capsys.readouterr().out


def test_owner_dm_channel_is_not_redacted(case, monkeypatch):
    # A channel id is an identifier: stored events must keep it so the listener can match it.
    from wuwei import env, redact
    write_env(case, f'SLACK_BOT_TOKEN={KEY}\nSLACK_OWNER_DM_CHANNEL=D0123ABC\n'
                    'WUWEI_TOTP_SECRET=other-private-value\n')
    with env.session():
        env.load(case)
        assert redact.known_values('D0123ABC/1.000001') == 'D0123ABC/1.000001'
        assert redact.known_values(KEY + ' other-private-value') == '[REDACTED] [REDACTED]'
    (case / '.wuwei/env').unlink()
    monkeypatch.setenv('SLACK_OWNER_DM_CHANNEL', 'D0123ABC')
    monkeypatch.setenv('SLACK_BOT_TOKEN', KEY)
    with env.session():
        assert redact.known_values('D0123ABC ' + KEY) == 'D0123ABC [REDACTED]'


def test_config_check_reports_owner_name(case, capsys):
    from wuwei import outward
    write_env(case, 'LINEAR_API_KEY=' + KEY + '\n')
    assert main(['config', 'check']) == 0
    output = capsys.readouterr().out
    assert 'Owner:' in output and output.count(outward.OWNER_UNSET) == 1
    path = case / '.wuwei/config.toml'
    path.write_text(path.read_text() + '[owner]\nname = "Robin Example"\n')
    assert main(['config', 'check']) == 0
    output = capsys.readouterr().out
    assert 'owner.name: set' in output and outward.OWNER_UNSET not in output


@pytest.mark.parametrize('pin, line, expected', [
    ('', PIN_MISSING, 1),
    ('U1', 'control_plane.owner: invalid', 1),
    ('T1/U1', 'control_plane.owner: set', 0),
])
@pytest.mark.parametrize('secret', ['', 'JBSWY3DPEHPK3PXP'])
def test_issue_acceptance_empty_pin_is_a_config_finding(case, monkeypatch, capsys, pin, line, expected, secret):
    monkeypatch.delenv('WUWEI_TOTP_SECRET', raising=False)
    path = case / '.wuwei/config.toml'
    path.write_text('[adapters]\ncode_host="none"\ninbound="slack"\n[control_plane]\nowner="' + pin + '"\n')
    write_env(case, 'SLACK_BOT_TOKEN=' + KEY + '\nSLACK_OWNER_DM_CHANNEL=D1\n'
              + ('WUWEI_TOTP_SECRET=' + secret + '\n' if secret else ''))
    assert main(['config', 'check']) == expected
    output = capsys.readouterr().out
    assert 'Control plane:\n  ' + line in output
    assert ('WUWEI_TOTP_SECRET: set' if secret else
            'WUWEI_TOTP_SECRET: missing (confirm replies are the only second factor)') in output
    assert (pin == '' or pin not in output) and (secret == '' or secret not in output)


def test_no_control_plane_section_without_an_inbound_adapter(case, capsys):
    (case / '.wuwei/config.toml').write_text('[adapters]\ncode_host="none"\n')
    assert main(['config', 'check']) == 0
    assert 'Control plane:' not in capsys.readouterr().out


def test_docs_credentials(case, monkeypatch, capsys):
    from wuwei import env
    (case / '.wuwei/config.toml').write_text('[adapters]\ncode_host="none"\n[docs]\nsystem="notion"\n')
    assert main(['config', 'check']) == 1
    assert 'docs.notion: NOTION_TOKEN: missing' in capsys.readouterr().out
    for name in ('NOTION_TOKEN', 'CONFLUENCE_EMAIL', 'CONFLUENCE_API_TOKEN'):
        monkeypatch.setenv(name, KEY)
    assert not {'NOTION_TOKEN', 'CONFLUENCE_EMAIL', 'CONFLUENCE_API_TOKEN'} & set(env.child_environment())


def test_tracker_credentials_are_private(case, monkeypatch):
    from wuwei import env, redact
    for name in ('JIRA_API_TOKEN', 'JIRA_EMAIL', 'GITHUB_TRACKER_TOKEN', 'JIRA_SITE'):
        monkeypatch.setenv(name, name.lower() + '-value')
    assert not {'JIRA_API_TOKEN', 'JIRA_EMAIL', 'GITHUB_TRACKER_TOKEN',
                'JIRA_SITE'} & env.child_environment().keys()
    with env.session():
        text = redact.known_values('jira_api_token-value jira_email-value '
                                   'github_tracker_token-value jira_site-value')
    assert text == '[REDACTED] [REDACTED] [REDACTED] jira_site-value'
