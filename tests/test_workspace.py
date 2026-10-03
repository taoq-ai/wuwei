"""Workspace contracts, including real CLI processes without site packages."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def fake_credential_tools(tmp_path_factory, monkeypatch):
    tools = tmp_path_factory.mktemp('credential-tools')
    gh = tools / 'gh'
    gh.write_text('#!/bin/sh\n[ "$*" = "auth status --hostname github.com" ] || exit 2\n')
    gh.chmod(0o755)
    monkeypatch.setenv('PATH', str(tools) + os.pathsep + os.environ.get('PATH', ''))


def cli(cwd, *args, **env):
    environment = {k: v for k, v in os.environ.items()
                   if k not in ('WUWEI_WORKSPACE', 'WUWEI_NOW')}
    return subprocess.run(
        [sys.executable, '-S', '-P', '-m', 'wuwei', *args], cwd=cwd,
        env={**environment, 'PYTHONPATH': str(ROOT / 'cli'), **env},
        capture_output=True, text=True,
    )


@pytest.mark.parametrize('explicit', [False, True])
def test_init_layout(tmp_path, explicit):
    target = tmp_path / 'body of work' if explicit else tmp_path
    result = cli(tmp_path, 'init', *([str(target)] if explicit else []))
    assert result.returncode == 0, result.stderr
    workspace = target / '.wuwei'
    for name in ('config.toml', 'memory/spine.md', 'memory/index.md',
                 'memory/CHANGELOG.md', 'memory/voice.md'):
        assert (workspace / name).is_file()
    for name in ('charters', 'memory/notes', 'days', 'archive'):
        assert (workspace / name).is_dir()
    assert not any(p.is_dir() for p in (workspace / 'days').iterdir())
    assert not list(workspace.rglob('.gitkeep'))
    version = json.loads((ROOT / '.claude-plugin/plugin.json').read_text())['version']
    assert (workspace / 'config.toml').read_text() == (ROOT / 'templates/workspace/config.toml').read_text().replace(
        'template_version = ""', f'template_version = "{version}"', 1)


@pytest.mark.parametrize('flags,posture,since', [
    (('--shadow',), 'observe', '2026-09-29'), (('--posture', 'observe'), 'observe', '2026-09-29'),
    (('--posture', 'strict'), 'strict', ''), ((), 'guarded', '')])
def test_init_posture(tmp_path, flags, posture, since):
    from wuwei import workspace
    result = cli(tmp_path, 'init', *flags, WUWEI_NOW='2026-09-29T12:00:00Z')
    assert result.returncode == 0, result.stderr
    config = workspace.load_config(tmp_path)
    assert config['guards'] == {'mode': 'enforce', 'shadow_days': 7, 'shadow_since': since}
    assert workspace.posture(config)[0] == posture
    import tomllib
    raw = tomllib.loads((tmp_path / '.wuwei/config.toml').read_text())
    assert (raw['security']['posture'], raw['guards']['shadow_since']) == (posture, since)
    for upgrade in (('--shadow',), ('--posture', 'strict')):
        result = cli(tmp_path, 'init', '--upgrade', *upgrade)
        assert result.returncode == 2 and upgrade[0] in result.stderr


@pytest.mark.parametrize('kind', ['directory', 'file', 'symlink'])
def test_init_never_overwrites(tmp_path, kind):
    target = tmp_path / '.wuwei'
    if kind == 'directory':
        target.mkdir()
        (target / 'precious').write_text('keep')
    elif kind == 'file':
        target.write_text('keep')
    else:
        target.symlink_to(tmp_path / 'absent')
    result = cli(tmp_path, 'init')
    assert result.returncode == 1, result.stderr
    assert 'exists' in result.stderr
    if kind == 'directory':
        assert list(target.iterdir()) == [target / 'precious']
    elif kind == 'file':
        assert target.read_text() == 'keep'
    else:
        assert target.is_symlink() and not target.exists()


def test_init_io_failure(tmp_path):
    target = tmp_path / 'file'
    target.write_text('keep')
    result = cli(tmp_path, 'init', str(target))
    assert result.returncode == 2
    assert str(target) in result.stderr and 'Traceback' not in result.stderr


@pytest.mark.parametrize('failure', [OSError, KeyboardInterrupt])
def test_init_copy_failure_is_retryable(tmp_path, monkeypatch, failure):
    from argparse import Namespace
    from wuwei.commands import init

    def interrupted_copy(source, destination, **kwargs):
        Path(destination).mkdir(exist_ok=True)
        (Path(destination) / 'config.toml').write_text('')
        raise failure('interrupted copy')

    with monkeypatch.context() as patch:
        patch.setattr(init.shutil, 'copytree', interrupted_copy)
        with pytest.raises(failure):
            init.run(Namespace(path=str(tmp_path)))
    assert not (tmp_path / '.wuwei').exists()
    assert not list(tmp_path.iterdir())
    assert init.run(Namespace(path=str(tmp_path))) == 0


def write_config(root, text):
    workspace = root / '.wuwei'
    workspace.mkdir(exist_ok=True)
    (workspace / 'config.toml').write_text(text)


def test_initialized_config_checks(tmp_path):
    assert cli(tmp_path, 'init').returncode == 0
    result = cli(tmp_path, 'config', 'check')
    assert result.returncode == 0, result.stderr


def test_initialized_memory_lint(tmp_path):
    assert cli(tmp_path, 'init').returncode == 0
    result = cli(tmp_path, 'memory', 'lint')
    assert result.returncode == 0, result.stderr


def test_config_defaults_and_independence(tmp_path):
    from wuwei import workspace
    from wuwei.workspace import load_config
    write_config(tmp_path, '')
    config = load_config(tmp_path)
    outbound = config.pop('outbound')
    assert outbound['work_channels'] == outbound['company_domains'] == []
    assert outbound['people'] == {} and outbound['sensitive_keywords']
    outward = config.pop('outward')
    assert outward['patterns'] and outward['tool_patterns']
    assert outward['banned_characters'] == ['emoji', '\u2014', '\u2015', '\u2e3a', '\u2e3b']
    assert outward['max_length'] == {}
    assert config == {
        'scanner': {'severity_threshold': 'high', 'mcp': {
            'project_file': '.mcp.json', 'plugins_file': '~/.claude/plugins/installed_plugins.json',
            'user_file': '~/.claude.json', 'timeout_seconds': 60, 'block': []}},
        'security': {'required': False, 'posture': 'guarded',
                     'areas': {area: '' for area in workspace.AREAS}},
        'owner': {'name': '', 'pronouns': '', 'handles': [], 'timezone': '', 'verbosity': {
            'default': 'brief', 'decisions': '', 'digest': '', 'nudges': '', 'dm': '', 'report': ''}},
        'repos': [], 'cap': 1, 'template_version': '', 'calibrate': {'fast_check_seconds': 60},
        'prioritisation': {'framework': 'wsjf'},
        'discovery': {'min_queue': 2, 'autostart': 'strict'},
        'tracker': {'backlog_filter': '', 'states': {'in_review': 'In Review', 'done': 'Done'}},
        'chat': {'identity': 'connector'},
        'control_plane': {'content': 'summary', 'owner': ''},
        'host': {'free_memory_mb': 1024, 'seats': 4, 'reservation_timeout_seconds': 14400}, 'profile': 'strict',
            'memory': {'max_notes': 60, 'note_line_cap': 80, 'probation_days': 10, 'state_entry_cap': 3},
            'metrics': {'transcripts': '~/.claude/projects', 'band_margin': 0.2},
            'consolidation': {'archive_after_days': 30, 'similarity_threshold': 0.85},
            'voice': {'sources': {}, 'review_prs': []},
        'build': {'max_iterations': 8, 'stuck_after': 3,
                  'poll_interval_seconds': 5, 'poll_timeout_seconds': 3600},
        'codex': {'command': [], 'timeout_seconds': 300},
        'gates': {'second_opinion': 'off', 'second_opinion_role': 'quality'},
            'watch': {'clock_seconds': 600, 'dead_seconds': 1200, 'stale_seconds': 900,
                      'sweep_seconds': 7200, 'ping_url': ''},
        'sessions': {'stale_seconds': 3600,
                     'rotate_after': {'turns': 0, 'compactions': 0, 'clock': ''}},
        'listen': {'poll_seconds': 60, 'dead_seconds': 300}, 'responder': {'enabled': True},
        'steward': {'every_tool_calls': 50, 'loop_window_hours': 4, 'loop_threshold': 9},
        'decisions': {'wait_hours': 24, 'cruise': {'enabled': True, 'levels': {}}},
        'pr': {'poll_seconds': 120, 'action_minutes': 30, 'review_window': 120},
            'shepherd': {'review_channel': '', 'lead_login': '', 'review_gate_check': 'Review Gate',
                         'min_reviewers': 1,
                         'author_windows_days': [90, 180], 'tie_commits': 2, 'autostart': False,
                     'source_exclude': ['specs/*', '*.lock', '*lock.json', '*.generated.*', 'generated/*'],
                     'authors': {}},
        'retro': {'repo': '.', 'charter_paths': ['.wuwei/charters'],
                  'changelog': '.wuwei/memory/CHANGELOG.md'},
        'calendar': {'url': ''},
        'brief': {'lead_minutes': 30, 'style': {'length': 'standard', 'speed': 180},
                  'remote': 'origin',
                  'prior_branch_pattern': '*{item}*',
                  'full_path_patterns': []},
        'boundary': {}, 'environments': {},
        'deploy': {'workflows': [], 'deny': []},
        'guards': {'mode': 'enforce', 'shadow_days': 7, 'shadow_since': ''},
        'adapters': {'tracker': 'none', 'chat': 'none', 'review_bot': 'none',
                     'runtime': 'claude', 'scanner': 'none',
                     'code_host': 'github', 'vcs': 'git', 'host': 'local',
                     'checks': 'local', 'tts': 'say' if sys.platform == 'darwin' else 'none', 'calendar': 'none',
                     'transcripts': 'none', 'inbound': 'none', 'redactor': 'builtin'},
    }
    outward['patterns'].append('changed')
    assert 'changed' not in load_config(tmp_path)['outward']['patterns']


def test_all_config_fields(tmp_path):
    from wuwei.workspace import load_config
    write_config(tmp_path, '''cap = 3
profile = "standard"
[owner]
name = "Pat"
pronouns = "they/them"
[[repos]]
name = "app"
path = "../app"
default_branch = "main"
fast_checks = ["python -m pytest -q"]
[[repos]]
name = "docs"
path = "../docs"
default_branch = "trunk"
[host]
free_memory_mb = 0
seats = 4
[boundary]
api = "Public API"
[environments]
staging = "Staging host"
[outward]
patterns = ["pending draft"]
banned_characters = ["!"]
[outward.max_length]
"team.chat" = 500
[adapters]
tracker = "none"
chat = "none"
review_bot = "none"
runtime = "none"
scanner = "none"
''')
    config = load_config(tmp_path)
    assert config['repos'][0]['default_branch'] == 'main'
    assert config['repos'][1]['fast_checks'] == []
    assert config['outward']['max_length']['team.chat'] == 500
    assert config['adapters']['tracker'] == 'none'
    # Repository names that are not owner/repo cannot be read from the host: unmeasured.
    result = cli(tmp_path, 'config', 'check')
    assert result.returncode == 2 and 'protection: unmeasured' in result.stdout


@pytest.mark.parametrize('text,key,line', [
    ('cap = 1\nfoo.bar = 1', 'foo', 2),
    ('[owner]\nname="x"\n[host]\nextra.a = 1', 'host.extra', 4),
    ('repos = [{name="a", path="/a", default_branch="main"},\n {pth="b"}]', 'repos.1.pth', 2),
    ('# capp is a typo\ncapp = 2\n', 'capp', 2),
    ('[owner]\nname = "a"\n[host]\nseatz = 2\n', 'host.seatz', 4),
    ('[[repos]]\nname = "a"\npath = "/a"\ndefault_branch = "main"\n[[repos]]\npth = "b"\n', 'repos.1.pth', 6),
    ('[adaptrs]\nruntime = "claude"\n', 'adaptrs', 1),
    ('[outward.max_lenght]\nchat = 2\n', 'outward.max_lenght', 1),
    ('owner.nmae = "a"\n', 'owner.nmae', 1),
    ('owner = { nmae = "a" }\n', 'owner.nmae', 1),
    ('[host]\n"seatz" = 2\n', 'host.seatz', 2),
])
def test_unknown_key_line(tmp_path, text, key, line):
    from wuwei import workspace
    # #353: unknown keys refuse only under strict; appending keeps the line numbers.
    write_config(tmp_path, text.rstrip('\n') + '\n[security]\nposture = "strict"\n')
    with pytest.raises(workspace.ConfigError) as error:
        workspace.load_config(tmp_path)
    assert f'config.toml: unknown key {key} at line {line};' in str(error.value)


def test_unknown_key_without_known_line(tmp_path, monkeypatch):
    from wuwei import workspace
    write_config(tmp_path, 'typo = 1\n[security]\nposture = "strict"')
    monkeypatch.setattr(workspace, '_key_line', lambda raw, path: None)
    with pytest.raises(workspace.ConfigError) as error:
        workspace.load_config(tmp_path)
    assert 'unknown key typo;' in str(error.value)
    assert 'at line' not in str(error.value)


@pytest.mark.parametrize('text,key', [
    ('cap = true', 'cap'), ('cap = 0', 'cap'), ('cap = 1.5', 'cap'),
    ('profile = "relaxed"', 'profile'), ('owner = "Pat"', 'owner'),
    ('repos = ["app"]', 'repos.0'),
    ('[[repos]]\nname="a"\npath="/a"\ndefault_branch="main"\nfast_checks = [1]', 'repos.0.fast_checks.0'),
    ('[owner]\npronouns = []', 'owner.pronouns'),
    ('[host]\nfree_memory_mb = -1', 'host.free_memory_mb'),
    ('[host]\nseats = 0', 'host.seats'),
    ('[outward]\npatterns = [false]', 'outward.patterns.0'),
    ('[outward]\nbanned_characters = 1', 'outward.banned_characters'),
    ('[outward.max_length]\nchat = 0', 'outward.max_length.chat'),
    ('[boundary]\napi = {}', 'boundary.api'),
    ('[environments]\nprod = 1', 'environments.prod'),
    ('[adapters]\nscanner = false', 'adapters.scanner'),
    ('[shepherd]\nmin_reviewers = -1', 'shepherd.min_reviewers'),
    ('[sessions]\nrotate_after = { turns = -1 }', 'sessions.rotate_after.turns'),
    ('[scanner.mcp]\nblock = ["severe"]', 'scanner.mcp.block'),
    ('[scanner.mcp]\ntimeout_seconds = 0', 'scanner.mcp.timeout_seconds'),
])
def test_invalid_config_values(tmp_path, text, key):
    write_config(tmp_path, text)
    result = cli(tmp_path, 'config', 'check')
    assert result.returncode == 1, result.stderr
    assert key in result.stderr and 'expected' in result.stderr


def test_owner_zone(tmp_path):
    from zoneinfo import ZoneInfo
    from wuwei.workspace import load_config, zone
    write_config(tmp_path, '')
    assert zone(load_config(tmp_path)) is None
    write_config(tmp_path, '[owner]\ntimezone = "Europe/Amsterdam"\n')
    assert zone(load_config(tmp_path)) == ZoneInfo('Europe/Amsterdam')
    write_config(tmp_path, '[owner]\ntimezone = "Mars/Base"\n')
    with pytest.raises(ValueError, match='owner.timezone'):
        zone(load_config(tmp_path))


def test_owner_verbosity(tmp_path):
    from wuwei import workspace
    write_config(tmp_path, '')
    config = workspace.load_config(tmp_path)
    assert config['owner']['verbosity'] == {'default': 'brief', 'decisions': '', 'digest': '',
                                            'nudges': '', 'dm': '', 'report': ''}
    write_config(tmp_path, '[owner.verbosity]\ndefault = "full"\ndm = "brief"\n')
    config = workspace.load_config(tmp_path)
    assert workspace.verbosity(config, 'dm') == 'brief'
    assert workspace.verbosity(config, 'report') == 'full'
    for text in ('default = "short"', 'dm = "loud"'):
        write_config(tmp_path, f'[owner.verbosity]\n{text}\n')
        with pytest.raises(workspace.ConfigError):
            workspace.load_config(tmp_path)
    write_config(tmp_path, '[owner.verbosity]\nretro = "full"\n')
    found = []
    workspace.load_config(tmp_path, warnings=found)  # #353: unknown keys warn below strict
    assert found and 'unknown key owner.verbosity.retro' in found[0]
    (tmp_path / '.wuwei/config.toml').write_text(
        (ROOT / 'templates/workspace/config.toml').read_text(encoding='utf-8'), encoding='utf-8')
    assert workspace.load_config(tmp_path)['owner']['verbosity']['default'] == 'brief'


def test_guards_mode(tmp_path):
    from wuwei import workspace
    write_config(tmp_path, '')
    assert workspace.load_config(tmp_path)['guards'] == {
        'mode': 'enforce', 'shadow_days': 7, 'shadow_since': ''}
    write_config(tmp_path, '[guards]\nmode = "shadow"\nshadow_since = "2026-09-25"\n')
    assert workspace.load_config(tmp_path)['guards']['mode'] == 'shadow'
    for text, key in (('mode = "off"', 'guards.mode'), ('shadow_days = 0', 'guards.shadow_days'),
                      ('shadow_since = "next week"', 'guards.shadow_since'),
                      ('shadow_since = "20260925"', 'guards.shadow_since')):
        write_config(tmp_path, f'[guards]\n{text}\n')
        with pytest.raises(workspace.ConfigError, match=key):
            workspace.load_config(tmp_path)


def test_outward_humanize_keys(tmp_path):
    from wuwei import workspace
    write_config(tmp_path, '')
    rules = workspace.load_config(tmp_path)['outward']
    assert rules['humanize'] is True and rules['humanize_strict'] is False
    assert rules['humanize_kinds'] == ['dm', 'tracker', 'docs', 'pr', 'review']
    write_config(tmp_path, '[outward]\nhumanize_kinds = ["chat"]\n')
    with pytest.raises(workspace.ConfigError, match='humanize_kinds'):
        workspace.load_config(tmp_path)
    (tmp_path / '.wuwei/config.toml').write_text(
        (ROOT / 'templates/workspace/config.toml').read_text(encoding='utf-8'), encoding='utf-8')
    assert workspace.load_config(tmp_path)['outward']['humanize'] is True


def test_solo_owner_min_reviewers_zero(tmp_path):
    from wuwei.workspace import load_config
    write_config(tmp_path, '[shepherd]\nmin_reviewers = 0')
    assert load_config(tmp_path)['shepherd']['min_reviewers'] == 0


@pytest.mark.parametrize('content', [b'cap = [', b'\xff'])
def test_invalid_config_text(tmp_path, content):
    write_config(tmp_path, '')
    (tmp_path / '.wuwei/config.toml').write_bytes(content)
    result = cli(tmp_path, 'config', 'check')
    assert result.returncode == 1, result.stderr
    assert 'config.toml' in result.stderr and 'Traceback' not in result.stderr


def test_missing_config(tmp_path):
    (tmp_path / '.wuwei').mkdir()
    result = cli(tmp_path, 'config', 'check')
    assert result.returncode == 2
    assert 'config.toml' in result.stderr


@pytest.fixture
def clean_environment(monkeypatch):
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    monkeypatch.delenv('WUWEI_NOW', raising=False)


def test_find_nearest_workspace(tmp_path, monkeypatch, clean_environment):
    from wuwei.workspace import find_workspace, load_config
    write_config(tmp_path, 'cap = 2')
    inner = tmp_path / 'inner'
    inner.mkdir()
    write_config(inner, 'cap = 3')
    nested = inner / 'a/b'
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)
    assert find_workspace() == inner
    assert find_workspace(tmp_path) == tmp_path
    assert load_config()['cap'] == 3
    assert cli(nested, 'config', 'check').returncode == 0


def test_workspace_override(tmp_path, monkeypatch, clean_environment):
    from wuwei.workspace import find_workspace, load_config
    write_config(tmp_path, 'cap = 2')
    selected = tmp_path / 'selected'
    selected.mkdir()
    write_config(selected, 'cap = 4')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('WUWEI_WORKSPACE', 'selected')
    assert find_workspace() == selected
    assert load_config()['cap'] == 4
    assert cli(tmp_path, 'config', 'check', WUWEI_WORKSPACE=str(selected)).returncode == 0


def test_missing_workspace_and_invalid_override(tmp_path, monkeypatch, clean_environment):
    from wuwei.workspace import find_workspace
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError, match='wuwei init'):
        find_workspace()
    write_config(tmp_path, '')
    for override in ('missing', ''):
        monkeypatch.setenv('WUWEI_WORKSPACE', override)
        with pytest.raises((FileNotFoundError, ValueError), match='WUWEI_WORKSPACE'):
            find_workspace()
        result = cli(tmp_path, 'config', 'check', WUWEI_WORKSPACE=override)
        assert result.returncode == 2 and 'WUWEI_WORKSPACE' in result.stderr


@pytest.mark.parametrize('timestamp,date', [
    ('2026-09-28T23:59:00-07:00', '2026-09-28'),
    ('2026-09-29T00:00:00Z', '2026-09-29'),
    ('2026-09-30T12:30:00', '2026-09-30'),
])
def test_day_dir_deterministic(tmp_path, monkeypatch, clean_environment, timestamp, date):
    from wuwei.workspace import day_dir, now
    write_config(tmp_path, '')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('WUWEI_NOW', timestamp)
    assert now().isoformat().startswith(date)
    assert now().utcoffset() is not None
    expected = tmp_path / '.wuwei/days' / date
    assert day_dir() == day_dir(tmp_path) == expected
    assert not expected.exists()


def test_clock_can_be_replaced(tmp_path, monkeypatch, clean_environment):
    from datetime import datetime
    from wuwei import workspace
    before = datetime.now().astimezone()
    assert before <= workspace.now() <= datetime.now().astimezone()
    monkeypatch.setattr(workspace, 'now', lambda: datetime(2030, 1, 2).astimezone())
    assert workspace.day_dir(tmp_path) == tmp_path / '.wuwei/days/2030-01-02'


@pytest.mark.parametrize('timestamp', ['', 'nope', '2026-09-28'])
def test_invalid_clock(monkeypatch, timestamp):
    from wuwei.workspace import now
    monkeypatch.setenv('WUWEI_NOW', timestamp)
    with pytest.raises(ValueError, match='WUWEI_NOW.*ISO'):
        now()


@pytest.mark.parametrize('kind', ['tracker', 'chat', 'review_bot', 'runtime', 'scanner'])
def test_unknown_adapter_name(tmp_path, kind):
    write_config(tmp_path, f'[adapters]\n{kind} = "missing"\n')
    result = cli(tmp_path, 'config', 'check')
    assert result.returncode == 1, result.stderr
    assert f'adapters.{kind}' in result.stderr
    from wuwei import registry
    assert 'known names: ' + ', '.join(registry.known(kind)) in result.stderr
    assert 'line 2' in result.stderr


def test_unknown_adapter_without_known_line(tmp_path, monkeypatch):
    from wuwei import workspace
    write_config(tmp_path, '[adapters]\nscanner = "missing"')
    monkeypatch.setattr(workspace, '_key_line', lambda raw, path: None)
    with pytest.raises(workspace.ConfigError, match='adapters.scanner.*known names: none') as error:
        workspace.load_config(tmp_path)
    assert 'at line' not in str(error.value)


@pytest.mark.parametrize('text,key,line', [
    ('[[repos]]\nname = "app"\n', 'repos.0.path', 1),
    ('[[repos]]\npath = "../app"\n', 'repos.0.name', 1),
    ('[[repos]]\nname = "app"\npath = ""\n', 'repos.0.path', 3),
    ('[[repos]]\nname = " "\npath = "../app"\n', 'repos.0.name', 2),
    ('[[repos]]\nname = "app"\npath = " "\n', 'repos.0.path', 3),
    ('[[repos]]\nname = ""\npath = "../app"\n', 'repos.0.name', 2),
    ('[[repos]]\nname = "a"\npath = "/a"\ndefault_branch = "main"\n[[repos]]\nname = "b"\n', 'repos.1.path', 5),
    ('[[repos]]\nname = "a"\npath = "/a"\ndefault_branch = "main"\n[[repos]]\nname = "b"\npath = ""', 'repos.1.path', 7),
])
def test_required_repository_fields(tmp_path, text, key, line):
    write_config(tmp_path, text)
    result = cli(tmp_path, 'config', 'check')
    assert result.returncode == 1, result.stderr
    assert f'{key}: required' in result.stderr
    assert f'line {line}' in result.stderr


def test_required_repository_field_without_known_line(tmp_path, monkeypatch):
    from wuwei import workspace
    write_config(tmp_path, '[[repos]]\nname = "app"\n')
    monkeypatch.setattr(workspace, '_key_line', lambda raw, path: None)
    with pytest.raises(workspace.ConfigError, match='repos.0.path: required') as error:
        workspace.load_config(tmp_path)
    assert 'at line' not in str(error.value)


@pytest.mark.parametrize('text,line', [
    ('[[repos]]\nname = "app"\npath = "/a"\ndefault_branch = "main"\n[[repos]]\nname = "app"\npath = "/b"\ndefault_branch = "main"', 6),
    ('repos = [{name="app", path="/a", default_branch="main"}, {name="app", path="/b", default_branch="main"}]', 1),
])
def test_duplicate_repository_names(tmp_path, text, line):
    write_config(tmp_path, text)
    result = cli(tmp_path, 'config', 'check')
    assert result.returncode == 1, result.stderr
    assert 'repos.1.name: duplicate' in result.stderr and 'app' in result.stderr
    assert f'line {line}' in result.stderr


@pytest.mark.parametrize('alias', ['same', 'absolute', 'normalized', 'symlink', 'home'])
def test_duplicate_repository_paths(tmp_path, alias):
    checkout = tmp_path / 'checkout'
    checkout.mkdir()
    (tmp_path / 'alias').symlink_to(checkout, target_is_directory=True)
    first = str(Path.home()) if alias == 'home' else 'checkout'
    second = {'same': 'checkout', 'absolute': str(checkout),
              'normalized': './checkout/../checkout', 'symlink': 'alias', 'home': '~'}[alias]
    write_config(tmp_path, f'[[repos]]\nname = "app"\npath = "{first}"\ndefault_branch = "main"\n'
                 f'[[repos]]\nname = "alias"\npath = "{second}"\ndefault_branch = "main"\n')
    result = cli(checkout, 'config', 'check', WUWEI_WORKSPACE=str(tmp_path))
    assert result.returncode == 1, result.stderr
    assert 'repos.1.path: duplicate' in result.stderr
    assert 'line 7' in result.stderr


def test_init_staging_prefix(tmp_path, monkeypatch):
    from argparse import Namespace
    from wuwei.commands import init

    copytree = init.shutil.copytree
    staging = []

    def observe(source, destination, *args, **kwargs):
        staging.append(Path(destination))
        return copytree(source, destination, *args, **kwargs)

    monkeypatch.setattr(init.shutil, 'copytree', observe)
    assert init.run(Namespace(path=str(tmp_path))) == 0
    assert staging[0].name.startswith('.wuwei-init-')
    assert not staging[0].exists()


def test_config_requires_default_branch(tmp_path):
    write_config(tmp_path, '[[repos]]\nname="test"\npath="repo"\n')
    result = cli(tmp_path, 'config', 'check')
    assert result.returncode == 1 and 'default_branch' in result.stderr


def test_init_records_runtime_location(tmp_path):
    assert cli(tmp_path, 'init').returncode == 0
    assert (tmp_path / '.wuwei/executable').read_text().strip() == str(ROOT / 'bin/wuwei')


def previous_workspace(root):
    directory = root / '.wuwei'
    (directory / 'charters').mkdir(parents=True)
    # Shape from the first workspace template, before memory, brief and deploy settings.
    (directory / 'config.toml').write_text('''# Owner comment stays.
cap = 3
profile = "standard"
repos = []
[owner]
name = "Pat"
pronouns = "they/them"
[host]
free_memory_mb = 2048
seats = 2
[adapters]
tracker = "none"
chat = "none"
review_bot = "none"
runtime = "claude"
scanner = "none"
[boundary]
[environments]
[outward]
patterns = []
banned_characters = []
[outward.max_length]
''')
    (directory / 'executable').write_text(str(root / 'previous-plugin/bin/wuwei') + '\n')
    (directory / 'charters/builder.md').write_text('---\nversion: 0.9.0\n---\nLocal builder\n')
    return directory


def test_upgrade_previous_workspace(tmp_path):
    import tomllib

    directory = previous_workspace(tmp_path)
    result = cli(tmp_path, 'init', '--upgrade')
    assert result.returncode == 0, result.stderr
    raw = (directory / 'config.toml').read_text()
    config = tomllib.loads(raw)
    assert '# Owner comment stays.' in raw
    assert config['cap'] == 3 and config['owner']['name'] == 'Pat'
    assert config['host']['free_memory_mb'] == 2048
    assert config['memory']['max_notes'] == 60
    assert config['host']['reservation_timeout_seconds'] == 14400
    assert '# Report stale reservations' in raw
    assert config['adapters']['checks'] == 'local'
    assert config['outward']['patterns'] == []
    assert (directory / 'executable').read_text() == str(ROOT / 'bin/wuwei') + '\n'
    assert 'builder.md' in result.stdout and '0.9.0' in result.stdout
    assert (directory / 'charters/builder.md').read_text().endswith('Local builder\n')
    assert 'statusLine' in result.stdout
    assert cli(tmp_path, 'config', 'check').returncode == 0
    assert 'repos = []\n' in raw.splitlines(keepends=True)


def test_upgrade_removes_empty_repos_before_tables(tmp_path):
    import tomllib

    directory = previous_workspace(tmp_path)
    config_path = directory / 'config.toml'
    config_path.write_text(config_path.read_text()
                           + '\n[[repos]]\nname = "app"\npath = "repo"\ndefault_branch = "main"\n')
    before = {path: path.read_bytes() for path in directory.rglob('*') if path.is_file()}
    preview = cli(tmp_path, 'init', '--upgrade', '--dry-run')
    assert preview.returncode == 0, preview.stderr
    assert 'Would upgrade config.toml: remove repos = []' in preview.stdout
    assert before == {path: path.read_bytes() for path in directory.rglob('*') if path.is_file()}

    result = cli(tmp_path, 'init', '--upgrade')
    assert result.returncode == 0, result.stderr
    assert 'Upgraded config.toml: remove repos = []' in result.stdout
    raw = config_path.read_text()
    assert 'repos = []\n' not in raw.splitlines(keepends=True)
    assert '# Owner comment stays.' in raw
    assert tomllib.loads(raw)['repos'][0]['name'] == 'app'

    after = {path: path.read_bytes() for path in directory.rglob('*') if path.is_file()}
    again = cli(tmp_path, 'init', '--upgrade')
    assert again.returncode == 0, again.stderr
    assert 'No workspace changes needed' in again.stdout
    assert after == {path: path.read_bytes() for path in directory.rglob('*') if path.is_file()}


def test_upgrade_is_idempotent(tmp_path):
    directory = previous_workspace(tmp_path)
    assert cli(tmp_path, 'init', '--upgrade').returncode == 0
    before = {path: path.read_bytes() for path in directory.rglob('*') if path.is_file()}
    result = cli(tmp_path, 'init', '--upgrade')
    assert result.returncode == 0, result.stderr
    assert 'No workspace changes needed' in result.stdout
    assert before == {path: path.read_bytes() for path in directory.rglob('*') if path.is_file()}


def test_upgrade_preserves_nonadjacent_repo_tables(tmp_path):
    assert cli(tmp_path, 'init').returncode == 0
    config_path = tmp_path / '.wuwei/config.toml'
    raw = config_path.read_text().replace(
        '[prioritisation]\n',
        '[[repos]]\nname = "b"\npath = "b"\ndefault_branch = "main"\n# b stays here\n\n[prioritisation]\n',
        1,
    ) + '\n[[repos]]\nname = "a"\npath = "a"\ndefault_branch = "main"\n# a stays here\n'
    config_path.write_text(raw)
    before = config_path.read_bytes()

    preview = cli(tmp_path, 'init', '--upgrade', '--dry-run')
    assert preview.returncode == 0, preview.stderr
    assert 'No workspace changes needed' in preview.stdout
    assert 'Would upgrade' not in preview.stdout
    assert config_path.read_bytes() == before

    result = cli(tmp_path, 'init', '--upgrade')
    assert result.returncode == 0, result.stderr
    assert 'No workspace changes needed' in result.stdout
    assert 'Upgraded' not in result.stdout
    assert config_path.read_bytes() == before


def test_upgrade_dry_run_does_not_write(tmp_path):
    directory = previous_workspace(tmp_path)
    before = {path: path.read_bytes() for path in directory.rglob('*') if path.is_file()}
    result = cli(tmp_path, 'init', '--upgrade', '--dry-run')
    assert result.returncode == 0, result.stderr
    assert 'Would upgrade config.toml' in result.stdout
    assert 'Would upgrade executable pointer' in result.stdout
    assert 'builder.md' in result.stdout
    assert before == {path: path.read_bytes() for path in directory.rglob('*') if path.is_file()}


def test_upgrade_rejects_unknown_key_without_writes(tmp_path):
    directory = previous_workspace(tmp_path)
    config_path = directory / 'config.toml'
    config_path.write_text(config_path.read_text().replace('pronouns = "they/them"',
                                                      'pronouns = "they/them"\nmystery = 1')
                           + '[security]\nposture = "strict"\n')
    before = {path: path.read_bytes() for path in directory.rglob('*') if path.is_file()}
    result = cli(tmp_path, 'init', '--upgrade')
    assert result.returncode == 1
    assert 'unknown key owner.mystery at line 8' in result.stderr
    assert before == {path: path.read_bytes() for path in directory.rglob('*') if path.is_file()}


def test_upgrade_handles_configured_repo_tables(tmp_path):
    import tomllib

    directory = previous_workspace(tmp_path)
    config_path = directory / 'config.toml'
    config_path.write_text(config_path.read_text().replace('profile = "standard"\n', '').replace('repos = []',
        '[[repos]]\nname = "app"\npath = "repo"\ndefault_branch = "main"'))
    result = cli(tmp_path, 'init', '--upgrade')
    assert result.returncode == 0, result.stderr
    config = tomllib.loads(config_path.read_text())
    assert config['repos'][0]['name'] == 'app'
    assert config['cap'] == 3 and config['profile'] == 'strict'


def test_upgrade_malformed_config_fails_closed(tmp_path):
    directory = previous_workspace(tmp_path)
    (directory / 'config.toml').write_text('[owner\nname = "Pat"\n')
    result = cli(tmp_path, 'init', '--upgrade')
    assert result.returncode == 2
    assert 'wuwei init:' in result.stderr
    assert (directory / 'executable').read_text() == str(tmp_path / 'previous-plugin/bin/wuwei') + '\n'


def test_upgrade_write_failure_preserves_files_and_can_retry(tmp_path, monkeypatch, capsys):
    from argparse import Namespace
    from wuwei.commands import init

    directory = previous_workspace(tmp_path)
    before = {path: path.read_bytes() for path in directory.rglob('*') if path.is_file()}
    def fail_write(path, text, **kwargs):
        raise OSError('disk full')

    with monkeypatch.context() as patch:
        patch.setattr(init.workspace, 'atomic_write', fail_write)
        assert init.run(Namespace(path=str(tmp_path), upgrade=True, dry_run=False)) == 2
    output = capsys.readouterr()
    assert 'disk full' in output.err
    assert 'Upgraded' not in output.out
    assert before == {path: path.read_bytes() for path in directory.rglob('*') if path.is_file()}
    assert init.run(Namespace(path=str(tmp_path), upgrade=True, dry_run=False)) == 0


def test_upgrade_reports_only_changed_charter_versions(tmp_path):
    directory = previous_workspace(tmp_path)
    current = (ROOT / 'charters/builder.md').read_text()
    (directory / 'charters/builder.md').write_text(current.replace('Builder charter', 'Local builder'))
    result = cli(tmp_path, 'init', '--upgrade', '--dry-run')
    assert result.returncode == 0, result.stderr
    assert 'Charter override needs review' not in result.stdout


def test_upgrade_config_without_trailing_newline(tmp_path):
    directory = previous_workspace(tmp_path)
    config_path = directory / 'config.toml'
    config_path.write_text('[owner]\nname = "Pat"')
    result = cli(tmp_path, 'init', '--upgrade')
    assert result.returncode == 0, result.stderr
    assert 'name = "Pat"\n# Added' in config_path.read_text()
    assert cli(tmp_path, 'config', 'check').returncode == 0


def test_upgrade_never_changes_multiline_owner_value(tmp_path):
    directory = previous_workspace(tmp_path)
    config_path = directory / 'config.toml'
    raw = config_path.read_text().replace('name = "Pat"',
        'name = """Pat\n[host]\nThis is a name\n"""')
    config_path.write_text(raw)
    result = cli(tmp_path, 'init', '--upgrade')
    assert result.returncode in (0, 2)
    if result.returncode == 0:
        import tomllib
        assert tomllib.loads(config_path.read_text())['owner']['name'] == 'Pat\n[host]\nThis is a name\n'
    else:
        assert 'wuwei init:' in result.stderr
        assert config_path.read_text() == raw


def test_upgrade_rejects_symlinked_config_without_writes(tmp_path):
    directory = previous_workspace(tmp_path)
    config_path = directory / 'config.toml'
    original = tmp_path / 'owner-config.toml'
    original.write_bytes(config_path.read_bytes())
    raw = original.read_text()
    config_path.unlink()
    config_path.symlink_to(original)
    result = cli(tmp_path, 'init', '--upgrade')
    assert result.returncode == 2
    assert 'symlinks' in result.stderr
    assert original.read_text() == raw


def test_nul_repo_path_is_config_finding(tmp_path):
    from wuwei.workspace import ConfigError, load_config
    write_config(tmp_path, '[[repos]]\nname="app"\npath="bad\\u0000path"\ndefault_branch="main"\n')
    with pytest.raises(ConfigError, match='repos.0.path'):
        load_config(tmp_path)


def test_config_parsed_once_per_text(tmp_path, monkeypatch):
    from wuwei import workspace
    (tmp_path / '.wuwei').mkdir()
    path = tmp_path / '.wuwei/config.toml'
    path.write_text('cap = 2\n')
    parsed = []
    loads = workspace.tomllib.loads
    monkeypatch.setattr(workspace.tomllib, 'loads', lambda text: parsed.append(text) or loads(text))
    first = workspace.load_config(tmp_path)
    first['cap'] = 9
    assert workspace.load_config(tmp_path)['cap'] == 2
    assert len(parsed) == 1
    path.write_text('cap = 3\n')
    assert workspace.load_config(tmp_path)['cap'] == 3
    assert len(parsed) == 2
    path.write_text('cap = 0\n')
    for _ in range(2):
        with pytest.raises(workspace.ConfigError):
            workspace.load_config(tmp_path)
    assert len(parsed) == 4


CACHE = '.wuwei/generated/config.cache.json'


def counted_parse(monkeypatch):
    import tomllib
    parsed, loads = [], tomllib.loads
    monkeypatch.setattr(tomllib, 'loads', lambda text: parsed.append(text) or loads(text))
    return parsed


def fresh_load(root, monkeypatch, warnings=None, writes=True):
    """load_config as a new hook process sees it (one that writes the parsed copy on a
    miss, as __main__ sets for hooks and the status line): no in-process memo, only files."""
    from wuwei import workspace
    monkeypatch.setattr(workspace, '_CONFIGS', {})
    monkeypatch.setattr(workspace, 'CONFIG_CACHE_WRITES', writes)
    return workspace.load_config(root, warnings=warnings)


def test_config_cache_only_hooks_and_the_status_line_write_it(tmp_path, monkeypatch):
    from wuwei import workspace
    write_config(tmp_path, 'cap = 2\n')
    assert workspace.CONFIG_CACHE_WRITES is False  # Every other command stays read-only.
    assert fresh_load(tmp_path, monkeypatch, writes=False)['cap'] == 2
    assert not (tmp_path / '.wuwei/generated').exists()
    fresh_load(tmp_path, monkeypatch)
    parsed = counted_parse(monkeypatch)
    assert fresh_load(tmp_path, monkeypatch, writes=False)['cap'] == 2
    assert parsed == []  # A current copy serves every command.


def test_config_cache_hit_skips_the_parse(tmp_path, monkeypatch):
    write_config(tmp_path, (ROOT / 'templates/workspace/config.toml').read_text())
    parsed = counted_parse(monkeypatch)
    first = fresh_load(tmp_path, monkeypatch)
    assert (tmp_path / CACHE).is_file() and len(parsed) == 1
    written = (tmp_path / CACHE).stat().st_mtime_ns
    assert fresh_load(tmp_path, monkeypatch) == first
    assert len(parsed) == 1
    assert (tmp_path / CACHE).stat().st_mtime_ns == written  # A hit writes nothing.


@pytest.mark.parametrize('text', ['cap = 12\n', 'cap = 3\n'], ids=['size', 'same-size-same-mtime'])
def test_config_cache_is_stale_when_the_text_changes(tmp_path, monkeypatch, text):
    write_config(tmp_path, 'cap = 2\n')
    path = tmp_path / '.wuwei/config.toml'
    before = path.stat()
    assert fresh_load(tmp_path, monkeypatch)['cap'] == 2
    path.write_text(text)
    # A rewrite inside one coarse timestamp tick keeps mtime, size and inode: the text decides.
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    parsed = counted_parse(monkeypatch)
    assert fresh_load(tmp_path, monkeypatch)['cap'] == int(text.split()[-1])
    assert len(parsed) == 1
    assert fresh_load(tmp_path, monkeypatch)['cap'] == int(text.split()[-1])
    assert len(parsed) == 1


def test_config_cache_survives_a_touch(tmp_path, monkeypatch):
    write_config(tmp_path, 'cap = 2\n')
    fresh_load(tmp_path, monkeypatch)
    path = tmp_path / '.wuwei/config.toml'
    os.utime(path, ns=(path.stat().st_atime_ns, path.stat().st_mtime_ns + 10**9))
    parsed = counted_parse(monkeypatch)
    assert fresh_load(tmp_path, monkeypatch)['cap'] == 2
    assert parsed == []


@pytest.mark.parametrize('change', ['plugin', 'layout'])
def test_config_cache_is_stale_for_another_version(tmp_path, monkeypatch, change):
    from wuwei import integrity, workspace
    write_config(tmp_path, 'cap = 2\n')
    fresh_load(tmp_path, monkeypatch)
    if change == 'plugin':
        monkeypatch.setattr(integrity, 'version', lambda: '999.0.0')
    else:
        monkeypatch.setattr(workspace, 'CONFIG_CACHE_VERSION', workspace.CONFIG_CACHE_VERSION + 1)
    parsed = counted_parse(monkeypatch)
    assert fresh_load(tmp_path, monkeypatch)['cap'] == 2
    assert fresh_load(tmp_path, monkeypatch)['cap'] == 2
    assert len(parsed) == 1  # Parsed once, then the rewritten copy serves this version.


@pytest.mark.parametrize('content', [b'{', b'[]', b'\xff', b'{"key": 1, "config": [], "warnings": 3}\n', b''])
def test_config_cache_unreadable_is_ignored(tmp_path, monkeypatch, content):
    write_config(tmp_path, 'cap = 2\n')
    expected = fresh_load(tmp_path, monkeypatch)
    (tmp_path / CACHE).write_bytes(content)
    assert fresh_load(tmp_path, monkeypatch) == expected
    parsed = counted_parse(monkeypatch)
    assert fresh_load(tmp_path, monkeypatch) == expected
    assert parsed == []  # Rewritten by the parse that ignored it.


def test_config_cache_forged_text_is_a_miss(tmp_path, monkeypatch):
    write_config(tmp_path, 'cap = 2\n')
    fresh_load(tmp_path, monkeypatch)
    data = json.loads((tmp_path / CACHE).read_text())
    data['config']['cap'] = 9
    data['key']['text'] = 'cap = 9\n'
    (tmp_path / CACHE).write_text(json.dumps(data))
    assert fresh_load(tmp_path, monkeypatch)['cap'] == 2


def test_config_cache_missing_directory(tmp_path, monkeypatch):
    write_config(tmp_path, 'cap = 2\n')
    assert not (tmp_path / '.wuwei/generated').exists()
    assert fresh_load(tmp_path, monkeypatch)['cap'] == 2
    assert (tmp_path / CACHE).is_file()


@pytest.mark.skipif(os.geteuid() == 0, reason='root writes through file modes')
def test_config_cache_unwritable_directory(tmp_path, monkeypatch):
    write_config(tmp_path, 'cap = 2\n')
    (tmp_path / '.wuwei/generated').mkdir()
    (tmp_path / '.wuwei/generated').chmod(0o500)
    try:
        assert fresh_load(tmp_path, monkeypatch)['cap'] == 2
        assert not (tmp_path / CACHE).exists()
    finally:
        (tmp_path / '.wuwei/generated').chmod(0o700)


def test_config_cache_symlink_is_ignored(tmp_path, monkeypatch):
    write_config(tmp_path, 'cap = 2\n')
    fresh_load(tmp_path, monkeypatch)
    forged = tmp_path / 'forged.json'
    data = json.loads((tmp_path / CACHE).read_text())
    data['config']['cap'] = 9
    forged.write_text(json.dumps(data))
    (tmp_path / CACHE).unlink()
    (tmp_path / CACHE).symlink_to(forged)
    assert fresh_load(tmp_path, monkeypatch)['cap'] == 2


def test_config_cache_keeps_the_warnings(tmp_path, monkeypatch):
    write_config(tmp_path, 'cap = 2\ncapp = 3\n[owner]\nhandle = "x"\n')
    fresh, cached = [], []
    parsed = counted_parse(monkeypatch)
    first = fresh_load(tmp_path, monkeypatch, warnings=fresh)
    assert fresh_load(tmp_path, monkeypatch, warnings=cached) == first
    assert len(parsed) == 1
    assert cached == fresh and len(fresh) == 2 and 'did you mean cap?' in fresh[0]


def test_config_cache_deleted_changes_nothing(tmp_path, monkeypatch):
    write_config(tmp_path, (ROOT / 'templates/workspace/config.toml').read_text() + 'capp = 3\n')
    with_cache, without = [], []
    fresh_load(tmp_path, monkeypatch)
    first = fresh_load(tmp_path, monkeypatch, warnings=with_cache)  # served from the cache
    (tmp_path / CACHE).unlink()
    assert fresh_load(tmp_path, monkeypatch, warnings=without) == first
    assert without == with_cache and with_cache


def test_config_cache_only_for_the_file(tmp_path, monkeypatch):
    from wuwei import workspace
    write_config(tmp_path, 'cap = 2\n')
    monkeypatch.setattr(workspace, 'CONFIG_CACHE_WRITES', True)
    assert workspace.load_config(tmp_path, raw='cap = 5\n')['cap'] == 5
    assert not (tmp_path / CACHE).exists()  # A candidate text is not the file.
    write_config(tmp_path, 'cap = 0\n')
    for _ in range(2):
        with pytest.raises(workspace.ConfigError):
            fresh_load(tmp_path, monkeypatch)
    assert not (tmp_path / CACHE).exists()  # Findings are never cached.


def test_config_cache_is_no_workspace_finding(tmp_path, monkeypatch):
    from wuwei import integrity, workspace
    write_config(tmp_path, 'cap = 2\n')
    (tmp_path / '.wuwei/memory').mkdir()
    (tmp_path / '.wuwei/memory/spine.md').write_text('Memory\n')
    integrity.initialize(tmp_path / '.wuwei')
    fresh_load(tmp_path, monkeypatch)
    assert (tmp_path / CACHE).is_file()
    assert integrity.workspace_check(tmp_path).exit == 0


def test_repository_gate_defaults_and_floor_choices(tmp_path):
    from wuwei.workspace import ConfigError, load_config
    repo = '[[repos]]\nname="a"\npath="/a"\ndefault_branch="main"\n'
    write_config(tmp_path, repo)
    assert load_config(tmp_path)['repos'][0]['gates'] == {
        'floor': 'standard', 'light_max_lines': 100,
        'trust_paths': ['guards/*', 'state.py', 'adapters/*', '.claude-plugin/*', '.github/*',
                        'ci/*', 'workflows/*', 'deploy/*', 'infra/*']}
    for text, key in (('floor = "lowest"', 'repos.0.gates.floor'),
                      ('light_max_lines = -1', 'repos.0.gates.light_max_lines')):
        write_config(tmp_path, repo + '[repos.gates]\n' + text + '\n')
        with pytest.raises(ConfigError, match=key):
            load_config(tmp_path)


@pytest.mark.parametrize('text, expected', [
    ('', []),
    ('[adapters]\ntracker = "linear"\n', ['LINEAR_API_KEY']),
    ('[adapters]\nchat = "slack"\n', ['SLACK_BOT_TOKEN or SLACK_USER_TOKEN', 'SLACK_OWNER_DM_CHANNEL']),
    ('[adapters]\nruntime = "codex"\n', ['codex.command']),
    ('[adapters]\ninbound = "slack"\n',
     ['SLACK_BOT_TOKEN or SLACK_USER_TOKEN', 'SLACK_OWNER_DM_CHANNEL', 'control_plane.owner']),
])
def test_config_missing_is_the_offline_check(tmp_path, monkeypatch, text, expected):
    from wuwei.commands.config import missing
    from wuwei.workspace import load_config
    for name in ('LINEAR_API_KEY', 'SLACK_BOT_TOKEN', 'SLACK_USER_TOKEN', 'SLACK_OWNER_DM_CHANNEL'):
        monkeypatch.delenv(name, raising=False)
    write_config(tmp_path, text)
    assert missing(load_config(tmp_path)) == expected


def test_shepherd_autostart_defaults_off(tmp_path):
    from wuwei.workspace import load_config
    write_config(tmp_path, '')
    assert load_config(tmp_path)['shepherd']['autostart'] is False
    write_config(tmp_path, '[shepherd]\nautostart = true')
    assert load_config(tmp_path)['shepherd']['autostart'] is True


def test_decisions_config(tmp_path):
    from wuwei.workspace import ConfigError, load_config
    write_config(tmp_path, '[decisions.cruise.levels]\napproach = 1\n')
    assert load_config(tmp_path)['decisions']['cruise']['levels'] == {'approach': 1}
    for text, key in (('[decisions.cruise.levels]\nmerge = 4', 'decisions.cruise.levels.merge'),
                      ('[decisions.cruise.levels]\nmessage = 2', 'decisions.cruise.levels.message'),
                      ('[decisions.cruise.levels]\nunknown = 1', 'decisions.cruise.levels.unknown'),
                      ('[decisions.cruise]\nmargin = 0.2', 'decisions.cruise.margin')):
        write_config(tmp_path, text + '\n[security]\nposture = "strict"\n')
        with pytest.raises(ConfigError, match=key):
            load_config(tmp_path)


def test_second_opinion_config(tmp_path):
    from wuwei.workspace import ConfigError, load_config
    write_config(tmp_path, '')
    assert load_config(tmp_path)['gates'] == {'second_opinion': 'off', 'second_opinion_role': 'quality'}
    write_config(tmp_path, '[gates]\nsecond_opinion = "codex:gpt-6-astra"\nsecond_opinion_role = "security"\n')
    assert load_config(tmp_path)['gates'] == {'second_opinion': 'codex:gpt-6-astra',
                                              'second_opinion_role': 'security'}
    for value in ('codex', 'codex:', 'codex:bad model', 'unknown:m', 'claude:opus', 'none:m'):
        write_config(tmp_path, f'[gates]\nsecond_opinion = "{value}"\n')
        with pytest.raises(ConfigError, match='gates.second_opinion'):
            load_config(tmp_path)
    write_config(tmp_path, '[gates]\nsecond_opinion_role = "goal"\n')
    with pytest.raises(ConfigError, match='gates.second_opinion_role'):
        load_config(tmp_path)


def test_init_stamps_the_template_version(tmp_path):
    import json
    import tomllib
    version = json.loads((ROOT / '.claude-plugin/plugin.json').read_text())['version']
    assert cli(tmp_path, 'init').returncode == 0
    config = tomllib.loads((tmp_path / '.wuwei/config.toml').read_text())
    assert config['template_version'] == version
    again = cli(tmp_path, 'init', '--upgrade')
    assert again.returncode == 0, again.stderr
    assert 'No workspace changes needed' in again.stdout


def test_upgrade_stamps_a_previous_workspace(tmp_path):
    import json
    import tomllib
    version = json.loads((ROOT / '.claude-plugin/plugin.json').read_text())['version']
    directory = previous_workspace(tmp_path)
    before = {path: path.read_bytes() for path in directory.rglob('*') if path.is_file()}
    preview = cli(tmp_path, 'init', '--upgrade', '--dry-run')
    assert f'Would upgrade config.toml: template_version {version}' in preview.stdout
    assert before == {path: path.read_bytes() for path in directory.rglob('*') if path.is_file()}
    result = cli(tmp_path, 'init', '--upgrade')
    assert f'Upgraded config.toml: template_version {version}' in result.stdout
    assert tomllib.loads((directory / 'config.toml').read_text())['template_version'] == version


def test_upgrade_warns_about_unknown_keys(tmp_path):
    directory = previous_workspace(tmp_path)
    config_path = directory / 'config.toml'
    config_path.write_text(config_path.read_text().replace('seats = 2', 'seats = 2\nseatz = 3'))
    result = cli(tmp_path, 'init', '--upgrade')
    assert result.returncode == 0, result.stderr
    assert 'wuwei init: warning: config.toml: unknown key host.seatz at line 11; did you mean host.seats?' in result.stderr


def trial(root, monkeypatch, mode='shadow'):
    from types import SimpleNamespace
    from wuwei.commands import init
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    assert init.run(SimpleNamespace(path=str(root), upgrade=False, dry_run=False)) == 0
    path = root / '.wuwei/config.toml'
    path.write_text(path.read_text().replace('[guards]\n', f'[guards]\nmode = "{mode}"\n', 1)
                    .replace('shadow_since = ""', 'shadow_since = "2026-09-29"', 1))
    return path


def upgraded(root, capsys, dry_run=False):
    from types import SimpleNamespace
    from wuwei.commands import init
    capsys.readouterr()
    code = init.run(SimpleNamespace(path=str(root), upgrade=True, dry_run=dry_run))
    return code, capsys.readouterr()


def test_upgrade_retires_shadow_mode(tmp_path, monkeypatch, capsys):
    import tomllib
    path = trial(tmp_path, monkeypatch)
    before = path.read_text()
    code, out = upgraded(tmp_path, capsys, dry_run=True)
    assert code == 0 and path.read_text() == before
    assert out.out.splitlines() == [
        'Would upgrade config.toml: guards.mode = "shadow" becomes security.posture = "observe"']
    code, out = upgraded(tmp_path, capsys)
    assert code == 0, out.err
    raw = path.read_text()
    config = tomllib.loads(raw)
    assert config['security']['posture'] == 'observe' and 'mode' not in config['guards']
    assert config['guards']['shadow_since'] == '2026-09-29' and config['guards']['shadow_days'] == 7
    assert raw == before.replace('mode = "shadow"\n', '', 1).replace(
        'posture = "guarded"', 'posture = "observe"', 1)
    assert 'No workspace changes needed' in upgraded(tmp_path, capsys)[1].out


def test_upgrade_removes_enforce_mode(tmp_path, monkeypatch, capsys):
    import tomllib
    path = trial(tmp_path, monkeypatch, 'enforce')
    code, out = upgraded(tmp_path, capsys, dry_run=True)
    assert out.out.splitlines() == [
        'Would upgrade config.toml: remove guards.mode = "enforce" (the default)']
    assert upgraded(tmp_path, capsys)[0] == 0
    config = tomllib.loads(path.read_text())
    assert 'mode' not in config['guards'] and config['security']['posture'] == 'guarded'


@pytest.mark.parametrize('security', ['', '[security]\nposture = "strict"\n'])
def test_upgrade_shadow_keeps_observe(tmp_path, monkeypatch, capsys, security):
    import tomllib
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    path = previous_workspace(tmp_path) / 'config.toml'
    path.write_text(path.read_text() + security + '[guards]\nmode = "shadow"\n')
    code, out = upgraded(tmp_path, capsys)
    assert code == 0, out.err
    config = tomllib.loads(path.read_text())
    assert config['security']['posture'] == 'observe' and 'mode' not in config['guards']


def test_upgrade_refuses_unreachable_mode(tmp_path, monkeypatch, capsys):
    path = trial(tmp_path, monkeypatch)
    path.write_text(path.read_text().replace('mode = "shadow"', '"mode" = "shadow"', 1))
    before = {p: p.read_bytes() for p in (tmp_path / '.wuwei').rglob('*') if p.is_file()}
    code, out = upgraded(tmp_path, capsys)
    assert code == 2 and 'cannot safely retire guards.mode' in out.err
    assert before == {p: p.read_bytes() for p in (tmp_path / '.wuwei').rglob('*') if p.is_file()}


def test_load_config_returns_independent_copies(tmp_path):
    # #346: the memo hands out copies (copy_data, not copy.deepcopy); a caller's edits stay its own.
    from wuwei import state, workspace
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('[owner]\nhandles = ["owner"]\n')
    first = workspace.load_config(tmp_path)
    first['owner']['handles'].append('intruder')
    first['outbound']['sensitive_keywords'].clear()
    first['repos'].append({})
    second = workspace.load_config(tmp_path)
    assert second['owner']['handles'] == ['owner'] and second['repos'] == []
    assert second['outbound']['sensitive_keywords'] == workspace.SCHEMA['outbound']['sensitive_keywords'][1]
    assert workspace.SCHEMA['outbound']['sensitive_keywords'][1]
    data = state.read_state(directory=tmp_path / 'day')
    data['items']['x'] = {}
    data['goals'].append('G-1')
    assert state.read_state(directory=tmp_path / 'day') == state.DAY_DEFAULTS
    assert state.DAY_DEFAULTS['items'] == {} and state.DAY_DEFAULTS['goals'] == []
