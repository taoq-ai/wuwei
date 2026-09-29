"""Workspace contracts, including real CLI processes without site packages."""

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
    assert (workspace / 'config.toml').read_bytes() == (ROOT / 'templates/workspace/config.toml').read_bytes()


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
            'user_file': '~/.claude.json'}},
        'security': {'required': False},
        'owner': {'name': '', 'pronouns': '', 'handles': []}, 'repos': [], 'cap': 1,
        'prioritisation': {'framework': 'wsjf'},
        'discovery': {'min_queue': 2, 'autostart': 'strict'},
        'tracker': {'backlog_filter': '', 'states': {'in_review': 'In Review', 'done': 'Done'}},
        'chat': {'identity': 'connector'},
        'host': {'free_memory_mb': 1024, 'seats': 4, 'reservation_timeout_seconds': 14400}, 'profile': 'strict',
            'memory': {'max_notes': 60, 'note_line_cap': 80, 'probation_days': 10, 'state_entry_cap': 3},
            'metrics': {'transcripts': '~/.claude/projects'},
            'consolidation': {'archive_after_days': 30, 'similarity_threshold': 0.85},
            'voice': {'sources': {}, 'review_prs': []},
        'build': {'max_iterations': 8, 'stuck_after': 3,
                  'poll_interval_seconds': 5, 'poll_timeout_seconds': 3600},
        'codex': {'command': [], 'timeout_seconds': 300},
        'watch': {'clock_seconds': 600, 'dead_seconds': 1200, 'stale_seconds': 900,
                  'sweep_seconds': 7200},
        'steward': {'every_tool_calls': 50},
        'pr': {'poll_seconds': 120, 'action_minutes': 30, 'review_window': 120},
            'shepherd': {'review_channel': '', 'lead_login': '', 'review_gate_check': 'Review Gate',
                         'min_reviewers': 1,
                         'author_windows_days': [90, 180], 'tie_commits': 2,
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
        'adapters': {'tracker': 'none', 'chat': 'none', 'review_bot': 'none',
                     'runtime': 'claude', 'scanner': 'none',
                     'code_host': 'github', 'vcs': 'git', 'host': 'local',
                     'checks': 'local', 'tts': 'say' if sys.platform == 'darwin' else 'none', 'calendar': 'none',
                     'transcripts': 'none'},
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
    assert cli(tmp_path, 'config', 'check').returncode == 0


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
    write_config(tmp_path, text)
    result = cli(tmp_path, 'config', 'check')
    assert result.returncode == 1, result.stderr
    assert key in result.stderr and f'line {line}' in result.stderr
    assert 'config.toml' in result.stderr and 'unknown key' in result.stderr


def test_unknown_key_without_known_line(tmp_path, monkeypatch):
    from wuwei import workspace
    write_config(tmp_path, 'typo = 1')
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
])
def test_invalid_config_values(tmp_path, text, key):
    write_config(tmp_path, text)
    result = cli(tmp_path, 'config', 'check')
    assert result.returncode == 1, result.stderr
    assert key in result.stderr and 'expected' in result.stderr


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
        'repos = []\n',
        '[[repos]]\nname = "b"\npath = "b"\ndefault_branch = "main"\n# b stays here',
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
                                                      'pronouns = "they/them"\nmystery = 1'))
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
